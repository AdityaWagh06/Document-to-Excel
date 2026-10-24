"""
Defensive outbound URL validation and safe HTTP client helper to mitigate SSRF (Server-Side Request Forgery).

Design Notes & SSRF Limitations:
1. URL validation performs scheme, format, credential, and DNS resolution checks against banned IP ranges
   (private, loopback, link-local, multicast, cloud metadata IP 169.254.169.254, and metadata hostnames).
2. Time-of-Check to Time-of-Use (TOCTOU) / DNS Rebinding Limitation:
   Standard pre-validation cannot completely prevent a malicious DNS server from returning a public IP during
   validation and a private IP during socket connection. For high-assurance environments, an egress HTTP proxy
   or network-level firewall rules should complement application-level checks. The helpers below re-validate
   every redirect hop and enforce strict timeouts and response size caps.
3. Local Tally Exception:
   Tally Prime / ERP 9 by default runs locally on HTTP port 9000. To preserve this required feature without
   exposing arbitrary internal endpoints, an explicit flag and strictly matched permitted URL
   (default: http://localhost:9000 or http://127.0.0.1:9000) are enforced.
"""

from __future__ import annotations
import ipaddress
import logging
import socket
import urllib.parse
from typing import Optional, Tuple, Set, Union
import requests

logger = logging.getLogger(__name__)

CLOUD_METADATA_HOSTS: Set[str] = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}

DISALLOWED_SCHEMES: Set[str] = {"file", "gopher", "ftp", "tftp", "ldap", "dict", "sftp", "data"}

# Maximum response size limit for downloaded remote media (16 MiB)
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def is_disallowed_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Returns True if the IP address is in a private, loopback, link-local, multicast, or reserved range."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or str(ip) == "169.254.169.254"
    )


def validate_url(
    url: str,
    allow_local_tally: bool = False,
    permitted_tally_url: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Validates an outbound target URL against SSRF rules.
    Returns (is_valid, error_message).
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string."

    stripped_url = url.strip()
    try:
        parsed = urllib.parse.urlparse(stripped_url)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if not parsed.scheme:
        return False, "Missing URL scheme."

    scheme = parsed.scheme.lower()
    if scheme in DISALLOWED_SCHEMES:
        return False, f"Disallowed URL scheme: '{scheme}'."

    # Reject URLs with embedded credentials (e.g. https://user:pass@host)
    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials are not allowed."

    # Validate hostname presence
    host = parsed.hostname
    if not host:
        return False, "Missing URL hostname."
    host_lower = host.lower()

    # Reject cloud metadata hostnames
    if host_lower in CLOUD_METADATA_HOSTS:
        return False, "Access to cloud metadata services is prohibited."

    # Handle explicitly permitted local Tally configuration
    if allow_local_tally and permitted_tally_url:
        try:
            parsed_tally = urllib.parse.urlparse(permitted_tally_url.strip())
            tally_host = (parsed_tally.hostname or "localhost").lower()
            tally_port = parsed_tally.port or 9000
            tally_scheme = parsed_tally.scheme.lower() or "http"

            req_port = parsed.port or (80 if scheme == "http" else 443)

            # Permitted Tally must exactly match the operator-configured host, port and
            # scheme (e.g. localhost, or host.docker.internal / a LAN IP when Tally runs
            # on another machine). Client-supplied URLs can never widen this.
            if (
                tally_scheme in ("http", "https")
                and scheme == tally_scheme
                and host_lower == tally_host
                and req_port == tally_port
            ):
                return True, ""
        except Exception:
            pass

    # For all standard outbound requests, require HTTPS
    if scheme != "https":
        return False, f"Insecure scheme '{scheme}'. External URLs must use HTTPS."

    # Check if host is an IP literal
    try:
        ip = ipaddress.ip_address(host_lower)
        if is_disallowed_ip(ip):
            return False, f"Target IP address '{ip}' is in a disallowed range (private/loopback/link-local/metadata)."
        return True, ""
    except ValueError:
        # Host is a domain name; resolve DNS
        pass

    try:
        port = parsed.port or 443
        addr_info = socket.getaddrinfo(host_lower, port, proto=socket.IPPROTO_TCP)
        if not addr_info:
            return False, f"DNS resolution yielded no addresses for '{host_lower}'."

        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if is_disallowed_ip(ip):
                    return False, f"Host '{host_lower}' resolves to disallowed IP '{ip_str}'."
            except ValueError:
                return False, f"Invalid resolved IP '{ip_str}'."

    except socket.gaierror as exc:
        return False, f"DNS resolution failed for '{host_lower}': {exc}"
    except Exception as exc:
        return False, f"DNS lookup error for '{host_lower}': {exc}"

    return True, ""


def safe_request(
    method: str,
    url: str,
    allow_local_tally: bool = False,
    permitted_tally_url: Optional[str] = None,
    max_redirects: int = 3,
    max_response_bytes: Optional[int] = MAX_RESPONSE_BYTES,
    connect_timeout: float = 5.0,
    read_timeout: float = 10.0,
    **requests_kwargs
) -> requests.Response:
    """
    Executes an outbound HTTP request while validating target URLs at every redirect hop,
    enforcing timeouts, and bounding maximum response payload size.
    """
    current_url = url
    redirect_count = 0

    while True:
        is_valid, error_msg = validate_url(
            current_url,
            allow_local_tally=allow_local_tally,
            permitted_tally_url=permitted_tally_url,
        )
        if not is_valid:
            # Mask complete URL in logs to avoid leaking query parameters or signatures
            parsed = urllib.parse.urlparse(current_url)
            safe_target = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            logger.warning("Blocked disallowed outbound request to %s: %s", safe_target, error_msg)
            raise ValueError(f"Disallowed or invalid URL: {error_msg}")

        # Always disable automated redirects to re-validate the target at every hop
        req_kwargs = dict(requests_kwargs)
        req_kwargs["allow_redirects"] = False
        req_kwargs["timeout"] = (connect_timeout, read_timeout)

        # For stream downloads
        stream = req_kwargs.get("stream", False)

        response = requests.request(method, current_url, **req_kwargs)

        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            redirect_count += 1
            if redirect_count > max_redirects:
                raise ValueError("Too many redirects.")

            location = response.headers.get("Location")
            if not location:
                raise ValueError("Redirect response missing Location header.")

            # Resolve relative redirect URLs against current URL
            current_url = urllib.parse.urljoin(current_url, location)
            continue

        # Enforce maximum response payload size if configured
        if max_response_bytes is not None:
            cl = response.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > max_response_bytes:
                raise ValueError(f"Response Content-Length ({cl} bytes) exceeds limit of {max_response_bytes} bytes.")

            if stream:
                total_bytes = 0
                chunks = []
                for chunk in response.iter_content(chunk_size=8192):
                    total_bytes += len(chunk)
                    if total_bytes > max_response_bytes:
                        raise ValueError(f"Response body exceeded maximum limit of {max_response_bytes} bytes.")
                    chunks.append(chunk)
                response._content = b"".join(chunks)

        return response
