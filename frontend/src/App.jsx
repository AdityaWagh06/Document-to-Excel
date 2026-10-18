import { useState, useMemo, useRef, useEffect } from 'react';
import { Zap, CheckCircle, Download, FileText, Hash } from 'lucide-react';
import STR from './constants/strings';

import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import LoginModal from './components/common/LoginModal';
import { SummaryCard, MetricCard } from './components/common/DashboardCards';
import UploadPreviewCard from './components/document/UploadPreviewCard';
import RawOcrPanel from './components/document/RawOcrPanel';
import DataGridSection from './components/document/DataGridSection';

import InvoiceHistorySection from './components/document/InvoiceHistorySection';
import ErpIntegrationSection from './components/document/ErpIntegrationSection';
import WhatsAppAutomationSection from './components/document/WhatsAppAutomationSection';
import AnalyticsSection from './components/document/AnalyticsSection';

import { useDocumentProcessor } from './hooks/useDocumentProcessor';
import { useFilePreview } from './hooks/useFilePreview';
import { checkSessionApi, logoutApi } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('extract');
  const [authUser, setAuthUser] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const fileInputRef = useRef(null);
  const processor = useDocumentProcessor();
  const previewUrl = useFilePreview(processor.selectedFile);

  // Synchronize authentication status and handle session expiration gracefully
  useEffect(() => {
    checkSessionApi().then((data) => {
      if (data?.authenticated && data?.user) {
        setAuthUser(data.user);
      }
    });

    function handleUnauthorized() {
      setIsAuthModalOpen(true);
    }

    function handleLoginSuccess(event) {
      setAuthUser(event.detail?.user || 'admin');
      setIsAuthModalOpen(false);
    }

    function handleLogoutSuccess() {
      setAuthUser(null);
    }

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    window.addEventListener('auth:login_success', handleLoginSuccess);
    window.addEventListener('auth:logout_success', handleLogoutSuccess);

    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
      window.removeEventListener('auth:login_success', handleLoginSuccess);
      window.removeEventListener('auth:logout_success', handleLogoutSuccess);
    };
  }, []);

  async function handleLogout() {
    try {
      await logoutApi();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setAuthUser(null);
    }
  }

  const columnDefs = useMemo(
    () => [
      {
        field: 'section',
        headerName: 'Section',
        editable: false,
        width: 140,
        cellClass: 'font-medium text-slate-500 bg-slate-50/50',
      },
      {
        field: 'field',
        headerName: 'Field / Description',
        editable: (params) => params.data?.section === 'Line Items',
        flex: 1.3,
        cellClass: (params) =>
          params.data?.section === 'Line Items'
            ? 'font-medium text-slate-900 cursor-pointer bg-white'
            : 'font-semibold text-slate-800 bg-slate-50/30',
      },
      {
        field: 'value',
        headerName: 'Value / Amount',
        editable: true,
        flex: 1.1,
        cellClass: 'font-semibold text-slate-900 cursor-pointer bg-blue-50/20',
      },
      {
        field: 'qty',
        headerName: 'Qty',
        editable: (params) => params.data?.section === 'Line Items',
        width: 80,
        valueGetter: (params) => (params.data?.section === 'Line Items' ? params.data.qty || '1' : '—'),
      },
      {
        field: 'unit_price',
        headerName: 'Rate (₹)',
        editable: (params) => params.data?.section === 'Line Items',
        width: 100,
        valueGetter: (params) => (params.data?.section === 'Line Items' ? params.data.unit_price || '0.00' : '—'),
      },
      {
        field: 'hsn_sac',
        headerName: 'HSN/SAC',
        editable: (params) => params.data?.section === 'Line Items',
        width: 95,
        valueGetter: (params) => (params.data?.section === 'Line Items' ? params.data.hsn_sac || '' : '—'),
      },
      {
        field: 'tax_rate',
        headerName: 'Tax Rate',
        editable: (params) => params.data?.section === 'Line Items',
        width: 95,
        valueGetter: (params) => (params.data?.section === 'Line Items' ? params.data.tax_rate || '0%' : '—'),
      },
      {
        field: 'confidence',
        headerName: 'Confidence',
        editable: false,
        width: 100,
        valueFormatter: (params) =>
          typeof params.value === 'number' ? `${Math.round(params.value * 100)}%` : params.value || '—',
      },
    ],
    []
  );

  const confidencePercent = Math.round((processor.documentState.confidence || 0) * 100);
  const ocrConfidencePercent = Math.round((processor.documentState.ocr_confidence || 0) * 100);
  const avgAccuracy = Math.round((confidencePercent + ocrConfidencePercent) / 2);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <Header
        processedCount={processor.processedCount}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        authUser={authUser}
        onLoginClick={() => setIsAuthModalOpen(true)}
        onLogoutClick={handleLogout}
      />

      <main className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8">
        {/* Tab 1: Scanner & Extraction */}
        {activeTab === 'extract' && (
          <div className="grid gap-8 lg:grid-cols-[1.1fr_1.3fr]">
            {/* Left Column: Upload & Preview */}
            <section>
              <UploadPreviewCard
                selectedFile={processor.selectedFile}
                previewUrl={previewUrl}
                isDragging={processor.isDragging}
                isProcessing={processor.isProcessing}
                error={processor.error}
                handleFiles={processor.handleFiles}
                handleUpload={processor.handleUpload}
                fileInputRef={fileInputRef}
                setIsDragging={processor.setIsDragging}
              />

              <RawOcrPanel rawText={processor.rawText} />
            </section>

            {/* Right Column: Extracted Data & Grid */}
            <section className="flex flex-col gap-6">
              {/* Extraction Header Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <SummaryCard label={STR.vendorLabel} value={processor.documentState.vendor || '—'} icon={<Zap className="h-4 w-4" />} />
                <SummaryCard label="GSTIN" value={processor.documentState.gstin || '—'} icon={<Hash className="h-4 w-4" />} />
                <SummaryCard label="Invoice #" value={processor.documentState.invoice_number || '—'} icon={<FileText className="h-4 w-4" />} />
                <SummaryCard label={STR.totalLabel} value={processor.documentState.total ? `₹ ${processor.documentState.total}` : '—'} icon={<Download className="h-4 w-4" />} />
              </div>

              {/* Confidence Metrics */}
              <div className="grid grid-cols-2 gap-4">
                <MetricCard
                  label={STR.extractionConfidenceLabel}
                  value={`${confidencePercent}%`}
                  color={confidencePercent >= 80 ? 'green' : confidencePercent >= 60 ? 'yellow' : 'red'}
                />
                <MetricCard
                  label={STR.ocrConfidenceLabel}
                  value={`${ocrConfidencePercent}%`}
                  color={ocrConfidencePercent >= 80 ? 'green' : ocrConfidencePercent >= 60 ? 'yellow' : 'red'}
                />
              </div>

              <DataGridSection
                rowData={processor.rowData}
                columnDefs={columnDefs}
                handleGridChange={processor.handleGridChange}
                handleDownload={processor.handleDownload}
                documentState={processor.documentState}
                isSaving={processor.isSaving}
                hasUnsavedChanges={processor.hasUnsavedChanges}
                saveSuccess={processor.saveSuccess}
                saveError={processor.saveError}
                handleSaveChanges={processor.handleSaveChanges}
              />
            </section>
          </div>
        )}

        {/* Tab 2: Invoice History */}
        {activeTab === 'history' && (
          <InvoiceHistorySection
            onSelectDocument={(doc) => {
              processor.loadDocument(doc);
              setActiveTab('extract');
            }}
          />
        )}

        {/* Tab 3: ERP Integration */}
        {activeTab === 'erp' && <ErpIntegrationSection />}

        {/* Tab 4: WhatsApp Automation */}
        {activeTab === 'whatsapp' && <WhatsAppAutomationSection />}

        {/* Tab 5: Analytics & Vendors */}
        {activeTab === 'analytics' && <AnalyticsSection />}
      </main>

      <Footer
        processedCount={processor.processedCount}
        itemsCount={(processor.documentState.items || []).length}
        avgAccuracy={avgAccuracy}
      />

      <LoginModal
        isOpen={isAuthModalOpen}
        onLoginSuccess={(data) => {
          setAuthUser(data?.user || 'admin');
          setIsAuthModalOpen(false);
        }}
      />
    </div>
  );
}
