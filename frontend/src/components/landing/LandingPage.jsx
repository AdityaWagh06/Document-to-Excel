import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  FileText,
  RefreshCw,
  MessageSquare,
  BarChart3,
  Zap,
  Cpu,
  Lock,
  Layers,
  Check,
  Download,
  Eye,
  SlidersHorizontal,
  ChevronRight,
  UploadCloud,
  FileCheck,
  Building2,
  Receipt,
  Smartphone,
  ExternalLink,
} from 'lucide-react';
import STR from '../../constants/strings';

// Pre-configured live demo document scenarios for interactive preview
const DEMO_SCENARIOS = {
  gst_tax: {
    id: 'gst_tax',
    label: 'Indian GST Tax Invoice',
    icon: Building2,
    badge: 'Standard GST B2B',
    vendor: 'Tata Consultancy Services Ltd',
    gstin: '27AAACT2727Q1ZW',
    gstinStatus: 'Valid Checksum (MH - 27)',
    invoiceNumber: 'TCS/2026/INV-9042',
    date: '24-Oct-2026',
    placeOfSupply: '27 - Maharashtra (Intra-State)',
    items: [
      { desc: 'Cloud & ERP Data Pipeline Setup', hsn: '998313', qty: 1, rate: 185000, amount: 185000, tax: '18%' },
      { desc: 'Annual AI OCR Document Automation License', hsn: '998319', qty: 12, rate: 15000, amount: 180000, tax: '18%' },
    ],
    subtotal: 365000,
    cgst: 32850,
    sgst: 32850,
    igst: 0,
    total: 430700,
    currency: 'INR',
    method: 'Gemini 3.5 Flash + Rules',
    confidence: '99.4%',
    ocrQuality: 'High (Digital PDF Layer)',
  },
  whatsapp_mobile: {
    id: 'whatsapp_mobile',
    label: 'WhatsApp Mobile Capture',
    icon: Smartphone,
    badge: 'Scanned / WhatsApp',
    vendor: 'Metro Industrial Peripherals & Co',
    gstin: '07AAAFM1234F1Z5',
    gstinStatus: 'Valid Checksum (DL - 07)',
    invoiceNumber: 'METRO/OCT/4412',
    date: '23-Oct-2026',
    placeOfSupply: '07 - Delhi to 27 - MH (Inter-State)',
    items: [
      { desc: 'Industrial High-Speed Barcode Scanners', hsn: '8471', qty: 4, rate: 12500, amount: 50000, tax: '18%' },
      { desc: 'Thermal Receipt Rolls (50-Pack)', hsn: '4811', qty: 10, rate: 900, amount: 9000, tax: '18%' },
    ],
    subtotal: 59000,
    cgst: 0,
    sgst: 0,
    igst: 10620,
    total: 69620,
    currency: 'INR',
    method: 'EasyOCR + Gemini Vision',
    confidence: '98.1%',
    ocrQuality: 'Medium (Camera Photo)',
  },
  tally_voucher: {
    id: 'tally_voucher',
    label: 'Inter-State Logistics Invoice',
    icon: Receipt,
    badge: 'Tally XML Ready',
    vendor: 'BlueDart Express Logistics Ltd',
    gstin: '29AABCB2212E1ZL',
    gstinStatus: 'Valid Checksum (KA - 29)',
    invoiceNumber: 'BD-LOG-882190',
    date: '21-Oct-2026',
    placeOfSupply: '29 - Karnataka (Inter-State)',
    items: [
      { desc: 'Express Surface Cargo Freight Services', hsn: '9965', qty: 1, rate: 42000, amount: 42000, tax: '18%' },
      { desc: 'Handling & Warehouse Fuel Surcharges', hsn: '9967', qty: 1, rate: 6800, amount: 6800, tax: '18%' },
    ],
    subtotal: 48800,
    cgst: 0,
    sgst: 0,
    igst: 8784,
    total: 57584,
    currency: 'INR',
    method: 'OpenAI gpt-4o-mini + Rules',
    confidence: '99.8%',
    ocrQuality: 'High (Scanned 300 DPI)',
  },
};

export default function LandingPage({ onOpenLogin, onQuickDemoLogin }) {
  const [activeScenarioKey, setActiveScenarioKey] = useState('gst_tax');
  const [downloadFeedback, setDownloadFeedback] = useState(null);

  const scenario = DEMO_SCENARIOS[activeScenarioKey];

  const handleSimulatedDownload = (format) => {
    setDownloadFeedback(`Generating sample ${format} file...`);
    setTimeout(() => {
      setDownloadFeedback(`Sample ${format} ready! Sign in to export real document data.`);
      setTimeout(() => setDownloadFeedback(null), 3500);
    }, 600);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Background Decorative Gradients & Mesh */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[1000px] h-[550px] bg-gradient-to-tr from-indigo-600/25 via-violet-600/20 to-sky-500/15 blur-[120px] rounded-full" />
        <div className="absolute top-[35%] -left-48 w-96 h-96 bg-purple-600/15 blur-[140px] rounded-full" />
        <div className="absolute top-[60%] -right-48 w-[450px] h-[450px] bg-blue-600/15 blur-[150px] rounded-full" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b0a_1px,transparent_1px),linear-gradient(to_bottom,#1e293b0a_1px,transparent_1px)] bg-[size:4rem_4rem]" />
      </div>

      {/* Top Floating Glass Navigation */}
      <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-violet-700 text-white shadow-lg shadow-indigo-500/25 ring-1 ring-white/20">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold tracking-tight text-white">{STR.appName}</span>
                <span className="rounded-full border border-indigo-400/30 bg-indigo-500/10 px-2 py-0.5 text-[11px] font-semibold text-indigo-300">
                  v1.0 Pro
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Indian GST & ERP Document Automation</p>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#features" className="transition hover:text-white">Features</a>
            <a href="#interactive-demo" className="transition hover:text-white">Live Demo</a>
            <a href="#how-it-works" className="transition hover:text-white">How It Works</a>
            <a href="#integrations" className="transition hover:text-white">Integrations</a>
            <a href="#security" className="transition hover:text-white">Security</a>
          </nav>

          <div className="flex items-center gap-2.5 sm:gap-3">
            {onQuickDemoLogin && (
              <button
                type="button"
                onClick={onQuickDemoLogin}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-950/60 px-3 py-1.5 text-xs font-semibold text-indigo-200 transition hover:bg-indigo-900/60 hover:border-indigo-400/50"
              >
                <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                1-Click Demo Login
              </button>
            )}
            <button
              type="button"
              onClick={onOpenLogin}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:from-indigo-600 hover:to-violet-700 hover:shadow-indigo-500/40 active:scale-95"
            >
              <Lock className="h-3.5 w-3.5" />
              Sign in to App
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="relative z-10">
        {/* HERO SECTION */}
        <section className="relative pt-12 pb-20 sm:pt-20 sm:pb-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
            {/* Announcement Badge */}
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-950/50 px-3.5 py-1.5 text-xs font-medium text-indigo-300 backdrop-blur-md mb-8">
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Multi-Engine OCR (PaddleOCR/EasyOCR) + Schema-Checked AI</span>
              <ChevronRight className="h-3.5 w-3.5 text-indigo-400" />
            </div>

            {/* High-Impact Headline */}
            <h1 className="mx-auto max-w-4xl text-4xl font-extrabold tracking-tight text-white sm:text-6xl sm:leading-[1.15]">
              Turn Invoices & Documents into Clean{' '}
              <span className="bg-gradient-to-r from-indigo-400 via-violet-300 to-sky-400 bg-clip-text text-transparent">
                Excel & Tally ERP Data
              </span>
            </h1>

            {/* Subtitle */}
            <p className="mx-auto mt-6 max-w-2xl text-base sm:text-lg text-slate-300 sm:leading-relaxed">
              Read Indian GST invoices, scanned bills, and WhatsApp photos in seconds. Automatically validate
              GSTIN checksums, reconcile CGST/SGST/IGST tax math, and export directly to Excel, CSV, or Tally XML vouchers.
            </p>

            {/* Hero CTAs */}
            <div className="mt-8 sm:mt-10 flex flex-wrap items-center justify-center gap-4">
              <button
                type="button"
                onClick={onOpenLogin}
                className="inline-flex items-center gap-2.5 rounded-xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-violet-600 px-6 py-3.5 text-base font-semibold text-white shadow-xl shadow-indigo-600/30 transition hover:from-indigo-600 hover:to-violet-700 hover:shadow-indigo-600/50 active:scale-95"
              >
                <span>Launch Workspace</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              {onQuickDemoLogin && (
                <button
                  type="button"
                  onClick={onQuickDemoLogin}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/90 px-5 py-3.5 text-base font-medium text-slate-200 transition hover:bg-slate-800 hover:border-slate-600 active:scale-95"
                >
                  <Sparkles className="h-4 w-4 text-indigo-400" />
                  <span>Instant Demo Mode</span>
                </button>
              )}

              <a
                href="#interactive-demo"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-5 py-3.5 text-base font-medium text-slate-400 transition hover:text-white hover:bg-slate-900"
              >
                <Eye className="h-4 w-4" />
                <span>See Interactive Demo</span>
              </a>
            </div>

            {/* Key Value Metric Pills */}
            <div className="mt-14 grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4 max-w-4xl mx-auto">
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4 backdrop-blur-sm">
                <div className="text-2xl font-bold text-white">Every field</div>
                <div className="text-xs text-slate-400 mt-1">Reviewable before export</div>
              </div>
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4 backdrop-blur-sm">
                <div className="text-2xl font-bold text-emerald-400">Modulo-36</div>
                <div className="text-xs text-slate-400 mt-1">GSTIN Checksum Validated</div>
              </div>
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4 backdrop-blur-sm">
                <div className="text-2xl font-bold text-indigo-400">Your AI key</div>
                <div className="text-xs text-slate-400 mt-1">OpenAI, Gemini or rules-only</div>
              </div>
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4 backdrop-blur-sm">
                <div className="text-2xl font-bold text-violet-400">Flagged</div>
                <div className="text-xs text-slate-400 mt-1">Values not found in the document</div>
              </div>
            </div>
          </div>
        </section>

        {/* INTERACTIVE DEMO SHOWCASE SECTION */}
        <section id="interactive-demo" className="py-16 sm:py-24 border-t border-slate-800/80 bg-slate-900/30">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-10">
              <span className="text-xs font-semibold tracking-wider uppercase text-indigo-400">Live Simulation</span>
              <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">
                See How DocExtract Pro Processes Documents
              </h2>
              <p className="mt-3 text-sm sm:text-base text-slate-400">
                Switch between real-world scenarios to see extraction confidence, GST checksum verification,
                and instant data export.
              </p>
            </div>

            {/* Scenario Selector Tabs */}
            <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
              {Object.values(DEMO_SCENARIOS).map((s) => {
                const Icon = s.icon;
                const isSelected = activeScenarioKey === s.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setActiveScenarioKey(s.id)}
                    className={`flex items-center gap-2.5 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                      isSelected
                        ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/30 ring-1 ring-indigo-400/40'
                        : 'border border-slate-800 bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{s.label}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${isSelected ? 'bg-white/20 text-white' : 'bg-slate-800 text-slate-400'}`}>
                      {s.badge}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Interactive Showcase Card */}
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 sm:p-8 backdrop-blur-xl shadow-2xl">
              {/* Card Header Status Row */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5 mb-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                    <scenario.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-base sm:text-lg">{scenario.vendor}</h3>
                    <p className="text-xs text-slate-400">
                      Invoice No: <span className="font-mono text-slate-200">{scenario.invoiceNumber}</span> · Date: {scenario.date}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    {scenario.gstinStatus}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1 text-xs font-semibold text-indigo-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    Confidence: {scenario.confidence}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-xs text-slate-300 font-mono">
                    {scenario.method}
                  </span>
                </div>
              </div>

              {/* Grid: Left Document Preview Box / Right Extracted Structured Data */}
              <div className="grid gap-6 lg:grid-cols-12">
                {/* Left: Simulated Document Preview (4 Cols) */}
                <div className="lg:col-span-5 flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-950/70 p-5">
                  <div>
                    <div className="flex items-center justify-between text-xs text-slate-400 mb-3">
                      <span className="font-semibold uppercase tracking-wider text-slate-300">Document Scan View</span>
                      <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                        <Check className="h-3 w-3" /> OCR Processed
                      </span>
                    </div>

                    {/* Mock Invoice Visual */}
                    <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/50 p-4 space-y-3 font-mono text-xs">
                      <div className="border-b border-slate-800 pb-2">
                        <p className="text-sm font-bold text-white">{scenario.vendor}</p>
                        <p className="text-indigo-400 mt-0.5">GSTIN: {scenario.gstin}</p>
                        <p className="text-slate-400 text-[11px] mt-0.5">POS: {scenario.placeOfSupply}</p>
                      </div>

                      <div className="space-y-1.5 text-slate-300">
                        {scenario.items.map((it, idx) => (
                          <div key={idx} className="flex justify-between text-[11px] bg-slate-800/40 p-1.5 rounded">
                            <span className="truncate pr-2">{it.desc}</span>
                            <span className="text-white font-semibold">₹{it.amount.toLocaleString('en-IN')}</span>
                          </div>
                        ))}
                      </div>

                      <div className="border-t border-slate-800 pt-2 flex justify-between font-bold text-sm text-emerald-400">
                        <span>Total Payable:</span>
                        <span>₹{scenario.total.toLocaleString('en-IN')}</span>
                      </div>
                    </div>
                  </div>

                  {/* Document OCR Quality Footer */}
                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                    <span>Quality Index: <strong className="text-slate-200">{scenario.ocrQuality}</strong></span>
                    <button
                      type="button"
                      onClick={onOpenLogin}
                      className="text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1"
                    >
                      <span>Upload Your PDF</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>

                {/* Right: Extracted Structured Financial Fields (7 Cols) */}
                <div className="lg:col-span-7 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between text-xs mb-3">
                      <span className="font-semibold uppercase tracking-wider text-slate-300">Normalized ERP Line Items</span>
                      <span className="text-indigo-400 font-mono text-[11px]">Strict Typed Schema (No Inventions)</span>
                    </div>

                    {/* Items Table */}
                    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
                      <table className="w-full text-left text-xs">
                        <thead className="border-b border-slate-800 bg-slate-900/70 text-slate-400">
                          <tr>
                            <th className="px-3 py-2.5 font-medium">Description</th>
                            <th className="px-3 py-2.5 font-medium">HSN/SAC</th>
                            <th className="px-3 py-2.5 font-medium text-right">Qty</th>
                            <th className="px-3 py-2.5 font-medium text-right">Rate</th>
                            <th className="px-3 py-2.5 font-medium text-right">Taxable</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                          {scenario.items.map((item, idx) => (
                            <tr key={idx} className="hover:bg-slate-900/40">
                              <td className="px-3 py-2.5 font-sans font-medium text-white">{item.desc}</td>
                              <td className="px-3 py-2.5 text-indigo-300">{item.hsn}</td>
                              <td className="px-3 py-2.5 text-right">{item.qty}</td>
                              <td className="px-3 py-2.5 text-right">₹{item.rate.toLocaleString('en-IN')}</td>
                              <td className="px-3 py-2.5 text-right font-semibold text-emerald-400">₹{item.amount.toLocaleString('en-IN')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Tax Breakup Breakdown */}
                    <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-2.5">
                        <div className="text-slate-400 text-[10px] uppercase">Taxable Subtotal</div>
                        <div className="text-sm font-bold text-white mt-0.5">₹{scenario.subtotal.toLocaleString('en-IN')}</div>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-2.5">
                        <div className="text-slate-400 text-[10px] uppercase">CGST (9%)</div>
                        <div className="text-sm font-bold text-slate-200 mt-0.5">₹{scenario.cgst.toLocaleString('en-IN')}</div>
                      </div>
                      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-2.5">
                        <div className="text-slate-400 text-[10px] uppercase">SGST / IGST</div>
                        <div className="text-sm font-bold text-slate-200 mt-0.5">
                          ₹{(scenario.sgst || scenario.igst).toLocaleString('en-IN')}
                        </div>
                      </div>
                      <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-2.5">
                        <div className="text-emerald-400 text-[10px] uppercase font-sans font-semibold">Total Verified</div>
                        <div className="text-sm font-bold text-emerald-400 mt-0.5">₹{scenario.total.toLocaleString('en-IN')}</div>
                      </div>
                    </div>
                  </div>

                  {/* Actions & Feedback */}
                  <div className="mt-6 pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleSimulatedDownload('Excel (.xlsx)')}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 hover:text-white"
                      >
                        <Download className="h-3.5 w-3.5 text-emerald-400" />
                        Excel (.xlsx)
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSimulatedDownload('CSV')}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 hover:text-white"
                      >
                        <Download className="h-3.5 w-3.5 text-blue-400" />
                        CSV
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSimulatedDownload('Tally XML Voucher')}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 hover:text-white"
                      >
                        <RefreshCw className="h-3.5 w-3.5 text-purple-400" />
                        Tally XML
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={onOpenLogin}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                    >
                      <span>Process Real Documents in App</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {downloadFeedback && (
                    <div className="mt-3 rounded-lg border border-indigo-500/30 bg-indigo-950/60 p-2 text-xs text-indigo-200 text-center animate-fade-in">
                      {downloadFeedback}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CORE FEATURES BENTO GRID */}
        <section id="features" className="py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span className="text-xs font-semibold tracking-wider uppercase text-indigo-400">Enterprise Engineering</span>
              <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-5xl">
                Built for Accuracy & Data Privacy
              </h2>
              <p className="mt-4 text-base text-slate-400">
                A robust pipeline built specifically for Indian GST compliance, local document OCR, and automated accounting workflows.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {/* Feature 1 */}
              <div className="group rounded-3xl border border-slate-800 bg-slate-900/50 p-7 transition hover:border-indigo-500/40 hover:bg-slate-900/80">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 mb-5 group-hover:scale-105 transition">
                  <Cpu className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Multi-Tier OCR & PDF Text Layer</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Extracts crisp text layers from digital PDFs natively without lossy conversion. Scanned documents & images pass through EasyOCR and PaddleOCR with automatic de-skewing.
                </p>
              </div>

              {/* Feature 2 */}
              <div className="group rounded-3xl border border-slate-800 bg-slate-900/50 p-7 transition hover:border-violet-500/40 hover:bg-slate-900/80">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-600/20 text-violet-400 border border-violet-500/30 mb-5 group-hover:scale-105 transition">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Indian GST Rules & Checksums</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Automatic Modulo-36 GSTIN verification, state code cross-matching, intra-state CGST+SGST equality checks, and inter-state IGST verification to eliminate financial errors.
                </p>
              </div>

              {/* Feature 3 */}
              <div className="group rounded-3xl border border-slate-800 bg-slate-900/50 p-7 transition hover:border-sky-500/40 hover:bg-slate-900/80">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-600/20 text-sky-400 border border-sky-500/30 mb-5 group-hover:scale-105 transition">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Multi-Provider AI Intelligence</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Harness Google Gemini, OpenAI, or Groq with strict JSON schemas. Any extracted value not found in the source document is flagged and lowers the confidence score, so a person reviews it before export.
                </p>
              </div>

              {/* Feature 4 */}
              <div className="group rounded-3xl border border-slate-800 bg-slate-900/50 p-7 transition hover:border-purple-500/40 hover:bg-slate-900/80">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-purple-600/20 text-purple-400 border border-purple-500/30 mb-5 group-hover:scale-105 transition">
                  <RefreshCw className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Tally XML & Custom ERP Sync</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Direct XML-over-HTTP sync to Tally Prime servers or downloadable Tally XML vouchers. Also pushes clean JSON to your own ERP or any REST endpoint you configure.
                </p>
              </div>

              {/* Feature 5 */}
              <div className="group rounded-3xl border border-slate-800 bg-slate-900/50 p-7 transition hover:border-emerald-500/40 hover:bg-slate-900/80">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 mb-5 group-hover:scale-105 transition">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">WhatsApp Cloud API Automation</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Suppliers and drivers take a photo and send it to your WhatsApp Business number. DocExtract parses it immediately, files the invoice, and responds with extraction totals.
                </p>
              </div>

              {/* Feature 6 */}
              <div className="group rounded-3xl border border-slate-800 bg-slate-900/50 p-7 transition hover:border-pink-500/40 hover:bg-slate-900/80">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-pink-600/20 text-pink-400 border border-pink-500/30 mb-5 group-hover:scale-105 transition">
                  <Lock className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Enterprise Security & Isolation</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Keys never touch the client browser. Enforces SSRF defense, CSRF protection, rate limiting, and durable SQLite storage with complete audit trails.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* HOW IT WORKS PIPELINE */}
        <section id="how-it-works" className="py-20 sm:py-28 border-t border-slate-800/80 bg-slate-900/20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span className="text-xs font-semibold tracking-wider uppercase text-indigo-400">Streamlined Workflow</span>
              <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-5xl">
                From Document to Ledger in 3 Steps
              </h2>
            </div>

            <div className="grid gap-8 md:grid-cols-3 relative">
              {/* Step 1 */}
              <div className="relative rounded-3xl border border-slate-800 bg-slate-900/60 p-8">
                <div className="flex items-center justify-between mb-6">
                  <span className="text-3xl font-extrabold text-indigo-500">01</span>
                  <UploadCloud className="h-6 w-6 text-indigo-400" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Ingest Documents</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Drag & drop multi-page PDFs, high-res photos, camera uploads, or automate inbound ingestion via WhatsApp Business webhook.
                </p>
              </div>

              {/* Step 2 */}
              <div className="relative rounded-3xl border border-slate-800 bg-slate-900/60 p-8">
                <div className="flex items-center justify-between mb-6">
                  <span className="text-3xl font-extrabold text-violet-500">02</span>
                  <Cpu className="h-6 w-6 text-violet-400" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">AI Extraction & GST Audit</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  OCR reads raw text, Gemini or OpenAI extracts structured fields, and the GST rules engine validates math, checksums, and tax splits.
                </p>
              </div>

              {/* Step 3 */}
              <div className="relative rounded-3xl border border-slate-800 bg-slate-900/60 p-8">
                <div className="flex items-center justify-between mb-6">
                  <span className="text-3xl font-extrabold text-emerald-500">03</span>
                  <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Review & One-Click Export</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Human-in-the-loop review on an AG-Grid interface. Edit any value with live recalculation, then export to Excel, CSV, or post directly to Tally.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* SECURITY & ARCHITECTURE HIGHLIGHTS */}
        <section id="security" className="py-20 sm:py-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/40 p-8 sm:p-14">
              <div className="grid gap-10 lg:grid-cols-2 items-center">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-950/60 px-3 py-1 text-xs font-semibold text-indigo-300 mb-6">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                    Enterprise Security Standards
                  </div>
                  <h2 className="text-3xl font-bold text-white sm:text-4xl leading-tight">
                    Your Financial Data Stays Private and In Control
                  </h2>
                  <p className="mt-4 text-base text-slate-300 leading-relaxed">
                    DocExtract Pro is designed for corporate security. Keys and databases remain completely on your
                    private server or Docker container. Sensitive tokens are never leaked to the client browser.
                  </p>

                  <div className="mt-6 space-y-3 text-sm text-slate-300">
                    <div className="flex items-center gap-3">
                      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                        <Check className="h-3 w-3" />
                      </div>
                      <span>SSRF-Safe Outbound Requests (Blocks internal network probes)</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                        <Check className="h-3 w-3" />
                      </div>
                      <span>CSRF Tokens & Server-Side Session Revocation</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                        <Check className="h-3 w-3" />
                      </div>
                      <span>Local SQLite Storage with Write-Ahead Logging & Concurrency</span>
                    </div>
                  </div>

                  <div className="mt-8 flex items-center gap-4">
                    <button
                      type="button"
                      onClick={onOpenLogin}
                      className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500"
                    >
                      <span>Sign In to Your Workspace</span>
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-950/90 p-6 font-mono text-xs text-slate-300 space-y-2">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-slate-400">
                    <span>SYSTEM RUNTIME SPECS</span>
                    <span className="text-emerald-400">● SECURE & ACTIVE</span>
                  </div>
                  <p className="text-indigo-400 pt-2"># Backend Engine</p>
                  <p>Python 3.11 / Flask REST API / SQLite WAL</p>
                  <p className="text-indigo-400 pt-2"># Active AI Provider</p>
                  <p>Google Gemini 3.5 Flash (Free Tier & OpenAI Schema)</p>
                  <p className="text-indigo-400 pt-2"># Local OCR Engines</p>
                  <p>EasyOCR 1.7.1 + PyMuPDF Embedded Layer</p>
                  <p className="text-indigo-400 pt-2"># Authentication Guard</p>
                  <p>Session Cookies (HTTPOnly, SameSite=Lax, CSRF Guarded)</p>
                  <p className="text-indigo-400 pt-2"># Exporters Configured</p>
                  <p>Excel OpenPyXL, CSV RFC-4180, Tally XML Voucher 9.0</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* BOTTOM CALL TO ACTION BANNER */}
        <section className="py-16 sm:py-24 border-t border-slate-800/80 bg-slate-950 text-center">
          <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-extrabold text-white sm:text-4xl">
              Ready to Automate Your Document Workflow?
            </h2>
            <p className="mt-4 text-base text-slate-400 max-w-2xl mx-auto">
              Sign in to your private instance to upload invoices, verify line items, and export directly to your accounting software.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <button
                type="button"
                onClick={onOpenLogin}
                className="inline-flex items-center gap-2.5 rounded-xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-violet-600 px-7 py-3.5 text-base font-semibold text-white shadow-xl shadow-indigo-600/30 transition hover:from-indigo-600 hover:to-violet-700"
              >
                <span>Enter Workspace Now</span>
                <ArrowRight className="h-4 w-4" />
              </button>
              {onQuickDemoLogin && (
                <button
                  type="button"
                  onClick={onQuickDemoLogin}
                  className="inline-flex items-center gap-2 rounded-xl border border-indigo-500/30 bg-indigo-950/60 px-5 py-3.5 text-base font-semibold text-indigo-300 hover:bg-indigo-900/60"
                >
                  <Sparkles className="h-4 w-4 text-indigo-400" />
                  <span>Quick Demo Login</span>
                </button>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="border-t border-slate-800 bg-slate-950 py-10 text-xs text-slate-400">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <FileSpreadsheet className="h-4 w-4" />
            </div>
            <span className="font-semibold text-slate-200">{STR.appName}</span>
            <span>— AI Invoice & ERP Automation</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="hover:text-slate-200">Features</a>
            <a href="#interactive-demo" className="hover:text-slate-200">Interactive Demo</a>
            <a href="#security" className="hover:text-slate-200">Security</a>
            <button type="button" onClick={onOpenLogin} className="text-indigo-400 hover:text-indigo-300 font-semibold">
              Sign In
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
