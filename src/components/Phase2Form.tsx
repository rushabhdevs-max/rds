"use client";

import { useRef, useState } from "react";

interface Summary {
  books_input: number;
  gstr2b_eligible: number;
  books_matched: number;
  gstr2b_matched: number;
  tiers: Record<string, number>;
  itc_recovered: number;
  itc_month_label?: string;
}

interface RunResponse {
  jobId: string;
  summary: Summary;
  downloads: { workbook: string; gstr2b: string };
}

// Mirrors the engine's PERIOD_RE so we can prefill the period from a filename.
const PERIOD_RE =
  /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*'?\s*(\d{2})/i;

function detectPeriod(name: string): string | null {
  const m = PERIOD_RE.exec(name);
  if (!m) return null;
  const mon = m[1][0].toUpperCase() + m[1].slice(1, 3).toLowerCase();
  return `${mon}'${m[2]}`;
}

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

export function Phase2Form() {
  const formRef = useRef<HTMLFormElement>(null);
  const [phase1, setPhase1] = useState<File | null>(null);
  const [gstr2b, setGstr2b] = useState<File | null>(null);
  const [period, setPeriod] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunResponse | null>(null);

  function onPick(setter: (f: File | null) => void, file: File | null) {
    setter(file);
    if (file && !period) {
      const p = detectPeriod(file.name);
      if (p) setPeriod(p);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!phase1 || !gstr2b) {
      setError("Please attach both the Phase 1 workbook and the GSTR-2B register.");
      return;
    }
    if (!period.trim()) {
      setError("A return period (e.g. May'26) is required.");
      return;
    }

    const fd = new FormData();
    fd.append("phase1", phase1);
    fd.append("gstr2b", gstr2b);
    fd.append("period", period.trim());

    setRunning(true);
    try {
      const res = await fetch("/api/recon/phase2", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Phase 2 reconciliation failed.");
        return;
      }
      setResult(data as RunResponse);
    } catch {
      setError("Network error — could not reach the server.");
    } finally {
      setRunning(false);
    }
  }

  function reset() {
    setPhase1(null);
    setGstr2b(null);
    setResult(null);
    setError(null);
    formRef.current?.reset();
  }

  return (
    <div className="space-y-6">
      <form ref={formRef} onSubmit={onSubmit} className="space-y-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Input files</h2>
          <p className="mb-4 text-xs text-slate-400">
            Both files are required. Phase 2 matches the Phase 1 &ldquo;Unmatched &ndash; Books
            only&rdquo; rows against the GSTR-2B register.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
                Phase 1 workbook <span className="text-rose-500">*</span>
              </span>
              <input
                type="file"
                name="phase1"
                accept=".xlsm"
                required
                disabled={running}
                onChange={(e) => onPick(setPhase1, e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
              />
              <span className="mt-1 block text-[11px] text-slate-400">
                .xlsm output from Phase 1 (must contain the Unmatched &ndash; Books only tab)
              </span>
            </label>
            <label className="block">
              <span className="mb-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
                GSTR-2B register <span className="text-rose-500">*</span>
              </span>
              <input
                type="file"
                name="gstr2b"
                accept=".xlsx"
                required
                disabled={running}
                onChange={(e) => onPick(setGstr2b, e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
              />
              <span className="mt-1 block text-[11px] text-slate-400">
                .xlsx register; eligible rows have a blank &ldquo;ITC Taken Month&rdquo;
              </span>
            </label>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Parameters</h2>
          <label className="block sm:max-w-xs">
            <span className="mb-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
              Return period <span className="text-rose-500">*</span>
            </span>
            <input
              type="text"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              placeholder="May'26"
              disabled={running}
              className="block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100"
            />
            <span className="mt-1 block text-[11px] text-slate-400">
              Stamped into matched GSTR-2B rows as &ldquo;ITC Taken Month&rdquo; (e.g. May-26).
            </span>
          </label>
        </section>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={running}
            className="rounded-xl bg-gradient-to-br from-indigo-600 to-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? "Running Phase 2…" : "Run Phase 2"}
          </button>
          {(result || error) && !running && (
            <button
              type="button"
              onClick={reset}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
            >
              Reset
            </button>
          )}
        </div>
      </form>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {result && <Results result={result} />}
    </div>
  );
}

function Results({ result }: { result: RunResponse }) {
  const s = result.summary;
  const tiers = s.tiers || {};
  const tierText = Object.keys(tiers).length
    ? Object.entries(tiers)
        .map(([t, n]) => `${t}: ${n}`)
        .join("  ·  ")
    : "—";

  const metrics = [
    { label: "Books rows read", value: s.books_input },
    { label: "GSTR-2B eligible", value: s.gstr2b_eligible },
    { label: "Books matched", value: s.books_matched },
    { label: "GSTR-2B stamped", value: s.gstr2b_matched },
  ];

  return (
    <section className="space-y-5 rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-emerald-800">Phase 2 complete</h2>
        <span className="text-sm text-emerald-700">
          ITC recovered:{" "}
          <span className="font-semibold">{INR.format(s.itc_recovered || 0)}</span>
          {s.itc_month_label ? `  ·  stamped ${s.itc_month_label}` : ""}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-lg font-semibold text-slate-800">{m.value}</div>
            <div className="mt-1 text-[11px] leading-tight text-slate-500">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="text-xs text-slate-500">
        <span className="font-medium text-slate-600">By tier:</span> {tierText}
      </div>

      <div className="flex flex-wrap gap-3">
        <a
          href={result.downloads.workbook}
          className="rounded-xl bg-gradient-to-br from-indigo-600 to-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
        >
          ↓ Download Phase 2 workbook (.xlsm)
        </a>
        <a
          href={result.downloads.gstr2b}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          ↓ Download updated GSTR-2B (.xlsx)
        </a>
      </div>
    </section>
  );
}
