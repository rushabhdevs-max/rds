"use client";

const QUICK_ACTIONS = [
  "How do I activate my PoS device?",
  "My device won't connect to network",
  "How do refunds work?",
  "Check settlement cycle",
  "How to integrate Airpay API?",
  "Error code E12 on swipe",
];

interface QuickActionsProps {
  onSelect: (query: string) => void;
}

export function QuickActions({ onSelect }: QuickActionsProps) {
  return (
    <div className="border-t border-slate-200 bg-white px-4 py-3">
      <p className="mb-2 text-xs font-medium text-slate-500">Suggested questions</p>
      <div className="flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action}
            onClick={() => onSelect(action)}
            className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
          >
            {action}
          </button>
        ))}
      </div>
    </div>
  );
}
