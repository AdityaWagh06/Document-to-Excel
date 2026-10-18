import { useState, useRef } from 'react';
import { MessageSquare, Send, CheckCircle2, Upload, Phone, ShieldCheck } from 'lucide-react';
import { simulateWhatsAppApi } from '../../services/api';

export default function WhatsAppAutomationSection() {
  const [phone, setPhone] = useState('+91 98765 43210');
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatLog, setChatLog] = useState([
    {
      sender: 'System',
      text: '🤖 *WhatsApp Automation Service Active*\nSend invoice photos to this WhatsApp Business number to automatically extract structured data.',
      time: 'Just now',
    },
  ]);
  const fileInputRef = useRef(null);

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  }

  async function handleSendWhatsApp() {
    if (!selectedFile) {
      alert('Please select an invoice photo to send via WhatsApp.');
      return;
    }

    setLoading(true);
    const userMsg = { sender: 'User', image: previewUrl, time: new Date().toLocaleTimeString() };
    setChatLog((prev) => [...prev, userMsg]);

    try {
      const res = await simulateWhatsAppApi(selectedFile, phone);
      const botMsg = {
        sender: 'WhatsApp Bot',
        text: res.whatsapp_reply,
        document: res.document,
        time: new Date().toLocaleTimeString(),
      };
      setChatLog((prev) => [...prev, botMsg]);
      setSelectedFile(null);
      setPreviewUrl('');
    } catch (err) {
      setChatLog((prev) => [
        ...prev,
        { sender: 'System Error', text: `❌ WhatsApp Processing Failed: ${err.message}`, time: new Date().toLocaleTimeString() },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm border border-slate-100">
      <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
        <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl">
          <MessageSquare className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-slate-900">WhatsApp Business Automation</h3>
          <p className="text-xs text-slate-500">
            Allow users & suppliers to submit invoice images directly via WhatsApp Business API.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {/* Left Column: Webhook Setup info */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <h4 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" /> WhatsApp Webhook Configuration
            </h4>
            <p className="text-xs text-slate-600 mt-1">
              Configure your WhatsApp Business Cloud API App to send webhook webhooks to:
            </p>
            <code className="block mt-2 bg-slate-900 text-emerald-400 p-2.5 rounded-lg text-[11px] font-mono">
              GET/POST http://localhost:5000/api/v1/whatsapp/webhook
            </code>
            <p className="text-[11px] text-slate-500 mt-2">
              Verify Token: <span className="font-bold text-slate-700">DOCUMENT_EXCEL_WHATSAPP_TOKEN</span>
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h4 className="font-bold text-slate-900 text-sm mb-2">Simulate Sending WhatsApp Invoice</h4>

            <label className="block text-xs font-semibold text-slate-700 mb-1">Sender Mobile Number</label>
            <div className="flex items-center gap-2 mb-3">
              <Phone className="h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-200"
              />
            </div>

            <label className="block text-xs font-semibold text-slate-700 mb-1">Select Invoice Image</label>
            <input
              type="file"
              ref={fileInputRef}
              accept="image/*,.pdf"
              onChange={handleFileSelect}
              className="hidden"
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 border border-slate-200 mb-3"
            >
              <Upload className="h-4 w-4" /> {selectedFile ? selectedFile.name : 'Choose Invoice Photo'}
            </button>

            {previewUrl && (
              <div className="mb-3">
                <img src={previewUrl} alt="Preview" className="max-h-32 rounded-lg border object-contain mx-auto" />
              </div>
            )}

            <button
              onClick={handleSendWhatsApp}
              disabled={loading || !selectedFile}
              className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" /> {loading ? 'Processing Image...' : 'Send Invoice to WhatsApp'}
            </button>
          </div>
        </div>

        {/* Right Column: WhatsApp Chat Preview */}
        <div className="rounded-xl border border-slate-200 bg-slate-900 p-4 text-white flex flex-col h-[400px]">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></div>
              <span className="font-bold text-xs">WhatsApp Business Chat</span>
            </div>
            <span className="text-[10px] text-slate-400">{phone}</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {chatLog.map((msg, idx) => (
              <div
                key={idx}
                className={`max-w-[85%] rounded-xl p-3 text-xs ${
                  msg.sender === 'User'
                    ? 'ml-auto bg-emerald-700 text-white'
                    : 'mr-auto bg-slate-800 text-slate-200 border border-slate-700'
                }`}
              >
                <div className="text-[10px] font-bold opacity-75 mb-1">{msg.sender} • {msg.time}</div>
                {msg.image && (
                  <img src={msg.image} alt="Sent invoice" className="max-h-28 rounded mb-2 border border-emerald-600" />
                )}
                <div className="whitespace-pre-line font-sans">{msg.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
