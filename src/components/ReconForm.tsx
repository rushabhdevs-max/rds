"use client";

import { useRef, useState } from "react";

interface Summary {
  book_total: number;
  book_matched: number;
  ims_total: number;
  ims_matched: number;
  tiers: Record<string, number>;
}

interface RunResponse {
  jobId: string;
  summary: Summary;
  downloads: { xlsm: string; cf: string | null };
}

// Mirrors the engine's PERIOD_RE so we can prefill the period from a filename.
const PERIOD_RE =
  /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*'?\s*(\d{2})/i;

const FILE_FIELDS = [
  { name: "ims", label: "IMS / GSTR-2B", accept: ".xlsx", required: true, hint: "ims_<GSTIN>_<date>.xlsx" },
  { name: "cgst", label: "CGST Books", accept: ".xls,.xlsx", required: true, hint: "filename must contain 'cgst'" },
  { name: "igst", label: "IGST Books", accept: ".xls,.xlsx", required: true, hint: "filename must contain 'igst'" },
  { name: "sgst", label: "SGST Books", accept: ".xls,.xlsx", required: false, hint: "optional" },
  { name: "cf", label: "Carry-Forward", accept: ".xlsx", required: false, hint: "optional" },
  { name: "outward", label: "Outward Revenue Summary", accept: ".xlsx", required: false, hint: "optional — fills GSTR-3B §3.1(a)" },
] as const;

type FieldName = (typeof FILE_FIELDS)[number]["name"];

function detectPeriod(name: string): string | null {
  const m = PERIOD_RE.exec(name);
  if (!m) return null;
  const mon = m[1][0].toUpperCase() + m[1].slice(1, 3).toLowerCase();
  return `${mon}'${m[2]}`;
}

export function ReconForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const [files, setFiles] = useState<Partial<Record<FieldName, File>>>({});
  const [period, setPeriod] = useState("");
  const [utilLabel, setUtilLabel] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunResponse | null>(null);

  function onFileChange(name: FieldName, file: File | null) {
    setFiles((prev) => {
      const next = { ...prev };
      if (file) next[name] = file;
      else delete next[name];
      return next;
    });
    // Auto-detect the period from any newly chosen filename if not set yet.
    if (file && !period) {
      const p = detectPeriod(file.name);
      if (p) setPeriod(p);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!files.ims || !files.cgst || !files.igst) {
      setError("Please attach at least the IMS, CGST, and IGST files.");
      return;
    }

    const fd = new FormData();
    for (const { name } of FILE_FIELDS) {
      const f = files[name];
      if (f) fd.append(name, f);
    }
    fd.append("period", period.trim());
    fd.append("utilLabel", utilLabel.trim());

    setRunning(true);
    try {
      const res = await fetch("/api/recon", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Reconciliation failed.");
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
    setFiles({});
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
            IMS, CGST and IGST are required. SGST, Carry-Forward and Outward summary are optional.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {FILE_FIELDS.map((field) => (
              <label key={field.name} className="block">
                <span className="mb-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
                  {field.label}
                  {field.required && <span className="text-rose-500">*</span>}
                </span>
                <input
                  type="file"
                  name={field.name}
                  accept={field.accept}
                  required={field.required}
                  disabled={running}
                  onChange={(e) => onFileChange(field.name, e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
                />
                <span className="mt-1 block text-[11px] text-slate-400">{field.hint}</span>
              </label>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Parameters</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Return period</span>
              <input
                type="text"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                placeholder="May'26 (auto-detected)"
                disabled={running}
                className="block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100"
              />
              <span className="mt-1 block text-[11px] text-slate-400">
                Format Mon&apos;YY. Leave blank to auto-detect from filenames.
              </span>
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Utilisation label</span>
              <input
                type="text"
                value={utilLabel}
                onChange={(e) => setUtilLabel(e.target.value)}
                placeholder="ITC Utilisation in May-26"
                disabled={running}
                className="block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-100"
              />
              <span className="mt-1 block text-[11px] text-slate-400">
                Written to carry-forward rows that get matched.
              </span>
            </label>
          </div>
        </section>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={running}
            className="rounded-xl bg-gradient-to-br from-indigo-600 to-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? "Running reconciliation…" : "Run reconciliation"}
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
  const metrics = [
    { label: "Book entries matched", value: `${s.book_matched} / ${s.book_total}` },
    { label: "IMS invoices matched", value: `${s.ims_matched} / ${s.ims_total}` },
    { label: "Exact (Tier 1)", value: tiers["1-EXACT"] ?? 0 },
    {
      label: "Fuzzy / Value / Agg",
      value: `${tiers["2-FUZZY"] ?? 0} / ${tiers["3-VALUE"] ?? 0} / ${tiers["4-AGGREGATED"] ?? 0}`,
    },
  ];

  return (
    <section className="space-y-5 rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-emerald-800">Reconciliation complete</h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-lg font-semibold text-slate-800">{m.value}</div>
            <div className="mt-1 text-[11px] leading-tight text-slate-500">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <a
          href={result.downloads.xlsm}
          className="rounded-xl bg-gradient-to-br from-indigo-600 to-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
        >
          ↓ Download report (.xlsm)
        </a>
        {result.downloads.cf && (
          <a
            href={result.downloads.cf}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            ↓ Download updated carry-forward (.xlsx)
          </a>
        )}
      </div>
    </section>
  );
}
