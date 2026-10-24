import STR from '../../constants/strings';

export default function Footer() {
  return (
    <footer className="mx-auto max-w-7xl px-4 py-8 text-center text-xs text-slate-400 sm:px-6 lg:px-8">
      {STR.appName} · {STR.appTagline}
    </footer>
  );
}
