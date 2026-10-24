// Amounts are shown in the currency printed on the document. Nothing is converted.
const formatters = new Map();

function formatter(currency) {
  const key = currency || '';
  if (!formatters.has(key)) {
    let fmt;
    try {
      fmt = currency
        ? new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
            style: 'currency',
            currency,
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
        : new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch {
      // Unknown code: show the code next to a plain number
      const plain = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      fmt = { format: (n) => `${currency} ${plain.format(n)}` };
    }
    formatters.set(key, fmt);
  }
  return formatters.get(key);
}

export function toNumber(value) {
  const num = Number(String(value ?? '').replace(/[^0-9.-]/g, ''));
  return Number.isFinite(num) ? num : NaN;
}

/** formatMoney('25.97', 'USD') -> "$25.97"; formatMoney('5900', 'INR') -> "₹5,900.00"; no currency -> "25.97" */
export function formatMoney(value, currency) {
  const num = toNumber(value);
  if (value === '' || value === null || value === undefined || Number.isNaN(num)) return '—';
  return formatter((currency || '').toUpperCase()).format(num);
}

/** Compact form for KPI tiles: $1.2K, ₹4.5L-style handled by Intl compact notation */
export function formatMoneyCompact(value, currency) {
  const num = toNumber(value);
  if (Number.isNaN(num)) return '—';
  if (Math.abs(num) < 100000) return formatMoney(num, currency);
  try {
    return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
      style: currency ? 'currency' : 'decimal',
      currency: currency || undefined,
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(num);
  } catch {
    return formatMoney(num, currency);
  }
}

export const COMMON_CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SGD', 'CAD', 'AUD', 'JPY', 'CNY'];
