import STR from '../../constants/strings';
import { FooterStat } from '../common/DashboardCards';

export default function Footer({ processedCount, itemsCount, avgAccuracy }) {
  return (
    <footer className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 p-8 text-white shadow-lg">
        <div className="grid gap-6 sm:grid-cols-4">
          <FooterStat label={STR.documentsProcessed} value={processedCount} />
          <FooterStat label={STR.itemsExtracted} value={itemsCount} />
          <FooterStat label={STR.avgAccuracy} value={`${avgAccuracy}%`} />
          <FooterStat label={STR.processingSpeed} value={STR.processingSpeedValue} />
        </div>
      </div>
    </footer>
  );
}
