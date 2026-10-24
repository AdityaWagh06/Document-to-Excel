import { useEffect, useRef, useState } from 'react';
import { Send, Upload, Phone, ShieldCheck, FlaskConical, CheckCircle2, AlertTriangle, Copy } from 'lucide-react';
import { simulateWhatsAppApi, fetchSystemStatusApi } from '../../services/api';
import { useToast } from '../../context/ToastContext';

function Check({ ok, children }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      {ok ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
      ) : (
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
      )}
      <span className="text-slate-700">{children}</span>
    </li>
  );
}

export default function WhatsAppAutomationSection() {
  const toast = useToast();
  const [status, setStatus] = useState(null);
  const [phone, setPhone] = useState('+91 98765 43210');
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatLog, setChatLog] = useState([]);
  const fileInputRef = useRef(null);
  const webhookUrl = `${window.location.origin}/api/v1/whatsapp/webhook`;

  useEffect(() => {
    fetchSystemStatusApi()
      .then((s) => setStatus(s.whatsapp))
      .catch(() => setStatus(null));
  }, []);

  useEffect(() => () => previewUrl && URL.revokeObjectURL(previewUrl), [previewUrl]);

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(file.type.startsWith('image/') ? URL.createObjectURL(file) : '');
    }
    e.target.value = '';
  }

  async function handleSimulate() {
    if (!selectedFile) return;
    setLoading(true);
    setChatLog((prev) => [...prev, { sender: 'Supplier', image: previewUrl, file: selectedFile.name, time: new Date().toLocaleTimeString() }]);
    try {
      const res = await simulateWhatsAppApi(selectedFile, phone);
      setChatLog((prev) => [...prev, { sender: 'Auto-reply', text: res.whatsapp_reply, time: new Date().toLocaleTimeString() }]);
      toast.success('Simulated invoice processed and saved to Invoices.');
      setSelectedFile(null);
      setPreviewUrl('');
    } catch (err) {
      setChatLog((prev) => [...prev, { sender: 'Error', text: err.message, time: new Date().toLocaleTimeString() }]);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function copyWebhook() {
    try {
      await navigator.clipboard.writeText(webhookUrl);
      toast.success('Webhook URL copied.');
    } catch {
      toast.info(webhookUrl);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">WhatsApp invoice intake</h1>
        <p className="text-sm text-slate-500">
          Suppliers send an invoice photo or PDF to your WhatsApp Business number; it is processed and appears under Invoices.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="wa-setup">
          <h2 id="wa-setup" className="flex items-center gap-2 font-semibold text-slate-900">
            <ShieldCheck className="h-5 w-5 text-emerald-600" aria-hidden="true" /> Live setup (Meta WhatsApp Cloud API)
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Requires a Meta Business account with a WhatsApp Business phone number. In the Meta developer dashboard, set the webhook callback URL to:
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-lg bg-slate-900 px-3 py-2 font-mono text-xs text-emerald-300">{webhookUrl}</code>
            <button type="button" onClick={copyWebhook} className="rounded-lg border border-slate-300 p-2 hover:bg-slate-50" aria-label="Copy webhook URL">
              <Copy className="h-4 w-4 text-slate-600" />
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Use the verify token from your server's WHATSAPP_VERIFY_TOKEN setting and subscribe to the “messages” field. Meta requires a public HTTPS URL.
          </p>
          <ul className="mt-4 space-y-2">
            <Check ok={status?.webhook_secret_configured}>Signature secret (WHATSAPP_APP_SECRET)</Check>
            <Check ok={status?.verify_token_configured}>Verify token (WHATSAPP_VERIFY_TOKEN)</Check>
            <Check ok={status?.media_download_configured}>Access token to download media and reply (WHATSAPP_ACCESS_TOKEN)</Check>
          </ul>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="wa-sim">
          <h2 id="wa-sim" className="flex items-center gap-2 font-semibold text-slate-900">
            <FlaskConical className="h-5 w-5 text-violet-600" aria-hidden="true" /> Simulator
          </h2>
          <p className="mt-1 rounded-lg bg-violet-50 px-3 py-2 text-xs text-violet-800">
            Test only: nothing is sent to or received from WhatsApp. The file is processed exactly like a WhatsApp delivery and saved with a WhatsApp source tag.
          </p>

          {status && status.simulator_enabled === false ? (
            <p className="mt-4 text-sm text-slate-500">The simulator is disabled on this server.</p>
          ) : (
            <>
              <label htmlFor="wa-phone" className="mb-1 mt-4 block text-xs font-medium text-slate-700">Sender number</label>
              <div className="relative">
                <Phone className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                <input
                  id="wa-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                />
              </div>
              <input type="file" ref={fileInputRef} accept="image/png,image/jpeg,image/webp,application/pdf" onChange={handleFileSelect} className="hidden" />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <Upload className="h-4 w-4" /> <span className="truncate">{selectedFile ? selectedFile.name : 'Choose invoice photo or PDF'}</span>
              </button>
              <button
                type="button"
                onClick={handleSimulate}
                disabled={loading || !selectedFile}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                <Send className="h-4 w-4" /> {loading ? 'Processing…' : 'Simulate WhatsApp message'}
              </button>

              <div className="mt-4 max-h-72 space-y-2 overflow-y-auto rounded-xl bg-slate-100 p-3" aria-live="polite">
                {chatLog.length === 0 && <p className="py-6 text-center text-xs text-slate-500">Simulated conversation appears here.</p>}
                {chatLog.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`max-w-[85%] rounded-xl p-2.5 text-xs shadow-sm ${
                      msg.sender === 'Supplier' ? 'ml-auto bg-emerald-100 text-emerald-950' : msg.sender === 'Error' ? 'bg-rose-50 text-rose-900' : 'bg-white text-slate-800'
                    }`}
                  >
                    <div className="mb-1 text-[10px] font-semibold opacity-60">{msg.sender} · {msg.time}</div>
                    {msg.image && <img src={msg.image} alt="Sent invoice" className="mb-1 max-h-28 rounded" />}
                    {msg.file && !msg.image && <p className="font-medium">📄 {msg.file}</p>}
                    {msg.text && <div className="whitespace-pre-line">{msg.text}</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
