"use client";

interface HeaderProps {
  onReset: () => void;
}

export function Header({ onReset }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-gradient-to-r from-indigo-600 to-blue-600 px-5 py-4 text-white">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 text-lg font-bold backdrop-blur">
          A
        </div>
        <div>
          <h1 className="text-base font-semibold leading-tight">Airpay PoS Support</h1>
          <div className="flex items-center gap-2 text-xs text-indigo-100">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-400"></span>
            <span>AirBot · Online</span>
          </div>
        </div>
      </div>
      <button
        onClick={onReset}
        className="rounded-md bg-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/20"
      >
        New chat
      </button>
    </header>
  );
}
