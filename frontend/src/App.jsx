import { useState, useMemo, useRef, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import STR from './constants/strings';

import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import LoginModal from './components/common/LoginModal';
import UploadPreviewCard from './components/document/UploadPreviewCard';
import RawOcrPanel from './components/document/RawOcrPanel';
import DataGridSection from './components/document/DataGridSection';
import DashboardSection from './components/document/DashboardSection';
import InvoiceSummary from './components/document/InvoiceSummary';
import InvoiceHistorySection from './components/document/InvoiceHistorySection';
import ErpIntegrationSection from './components/document/ErpIntegrationSection';
import WhatsAppAutomationSection from './components/document/WhatsAppAutomationSection';
import AnalyticsSection from './components/document/AnalyticsSection';

import { useDocumentProcessor } from './hooks/useDocumentProcessor';
import { useFilePreview } from './hooks/useFilePreview';
import { useToast } from './context/ToastContext';
import { checkSessionApi, logoutApi } from './services/api';

const lineItemEditable = (params) => params.data?.section === 'Line Items';
const lineItemValue = (key, fallback) => (params) =>
  params.data?.section === 'Line Items' ? params.data[key] || fallback : '—';

export default function App() {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState('dashboard');
  // undefined = still checking, null = signed out, string = signed-in user
  const [authUser, setAuthUser] = useState(undefined);
  const [sessionExpired, setSessionExpired] = useState(false);

  const fileInputRef = useRef(null);
  const processor = useDocumentProcessor(toast);
  const previewUrl = useFilePreview(processor.selectedFile);

  useEffect(() => {
    checkSessionApi().then((data) => {
      setAuthUser(data?.authenticated && data?.user ? data.user : null);
    });

    function handleUnauthorized() {
      setAuthUser((current) => {
        if (current) setSessionExpired(true);
        return current;
      });
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  useEffect(() => {
    if (!processor.hasUnsavedChanges) return undefined;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [processor.hasUnsavedChanges]);

  async function handleLogout() {
    try {
      await logoutApi();
    } catch {
      // Session is cleared locally either way
    } finally {
      setAuthUser(null);
      setActiveTab('dashboard');
    }
  }

  function openDocument(doc) {
    processor.loadDocument(doc);
    setActiveTab('extract');
  }

  const docCurrency = processor.documentState?.currency || '';
  const columnDefs = useMemo(
    () => [
      { field: 'section', headerName: 'Section', editable: false, width: 130, cellClass: 'text-slate-500' },
      {
        field: 'field',
        headerName: 'Field / description',
        editable: lineItemEditable,
        flex: 1.4,
        minWidth: 180,
        cellClass: (p) => (p.data?.section === 'Line Items' ? 'font-medium text-slate-900' : 'font-semibold text-slate-800'),
      },
      { field: 'value', headerName: 'Value / amount', editable: true, flex: 1, minWidth: 140, cellClass: 'font-semibold text-slate-900 bg-blue-50/40' },
      { field: 'qty', headerName: 'Qty', editable: lineItemEditable, width: 80, valueGetter: lineItemValue('qty', '1') },
      { field: 'unit_price', headerName: docCurrency ? `Rate (${docCurrency})` : 'Rate', editable: lineItemEditable, width: 105, valueGetter: lineItemValue('unit_price', '0.00') },
      { field: 'hsn_sac', headerName: 'HSN/SAC', editable: lineItemEditable, width: 100, valueGetter: lineItemValue('hsn_sac', '') },
      { field: 'tax_rate', headerName: 'Tax %', editable: lineItemEditable, width: 90, valueGetter: lineItemValue('tax_rate', '0%') },
    ],
    [docCurrency]
  );

  if (authUser === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (authUser === null) {
    return <LoginModal isOpen variant="page" onLoginSuccess={(data) => setAuthUser(data?.user || 'admin')} />;
  }

  const doc = processor.documentState;

  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <Header activeTab={activeTab} setActiveTab={setActiveTab} authUser={authUser} onLogoutClick={handleLogout} />

      <main id="main" className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8">
        {activeTab === 'dashboard' && (
          <DashboardSection
            authUser={authUser}
            onOpenDocument={openDocument}
            onGoToUpload={() => setActiveTab('extract')}
            onGoToHistory={() => setActiveTab('history')}
          />
        )}

        {activeTab === 'extract' && (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
            <section aria-label="Upload">
              <UploadPreviewCard
                selectedFile={processor.selectedFile}
                previewUrl={previewUrl}
                isDragging={processor.isDragging}
                isProcessing={processor.isProcessing}
                phase={processor.phase}
                uploadProgress={processor.uploadProgress}
                error={processor.error}
                handleFiles={processor.handleFiles}
                handleUpload={processor.handleUpload}
                fileInputRef={fileInputRef}
                setIsDragging={processor.setIsDragging}
              />
              {doc.id && <RawOcrPanel rawText={processor.rawText} />}
            </section>

            <section className="flex min-w-0 flex-col gap-4" aria-label="Extracted data">
              {doc.id && <InvoiceSummary doc={doc} />}

              <DataGridSection
                rowData={processor.rowData}
                columnDefs={columnDefs}
                handleGridChange={processor.handleGridChange}
                handleDownload={processor.handleDownload}
                documentState={doc}
                isSaving={processor.isSaving}
                hasUnsavedChanges={processor.hasUnsavedChanges}
                saveSuccess={processor.saveSuccess}
                saveError={processor.saveError}
                handleSaveChanges={processor.handleSaveChanges}
                handleVerify={processor.handleVerify}
              />
            </section>
          </div>
        )}

        {activeTab === 'history' && <InvoiceHistorySection onSelectDocument={openDocument} />}
        {activeTab === 'analytics' && <AnalyticsSection />}
        {activeTab === 'erp' && <ErpIntegrationSection />}
        {activeTab === 'whatsapp' && <WhatsAppAutomationSection />}
      </main>

      <Footer />

      <LoginModal
        isOpen={sessionExpired}
        onLoginSuccess={(data) => {
          setAuthUser(data?.user || authUser);
          setSessionExpired(false);
          toast.success('Signed in again. You can continue where you left off.');
        }}
      />
    </div>
  );
}
