import type { Metadata } from "next";
import { Phase2Form } from "@/components/Phase2Form";
import { ReconNav } from "@/components/ReconNav";

export const metadata: Metadata = {
  title: "GST Reconciliation · Phase 2",
  description:
    "Second-pass reconciliation: match the Phase 1 leftover books rows against the GSTR-2B register and stamp ITC Taken Month.",
};

export default function Phase2Page() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-100 via-indigo-50 to-blue-100 px-4 py-10">
      <div className="mx-auto w-full max-w-3xl">
        <ReconNav active="phase2" />
        <header className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Phase 2 — Books leftovers ↔ GSTR-2B
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Upload a Phase 1 workbook and the GSTR-2B register. Phase 2 re-runs the matching
            engine over the still-unmatched books rows, moves any new matches into the workbook,
            and stamps <span className="font-medium">ITC Taken Month</span> on the matched
            GSTR-2B rows. Both source files are left untouched — you download fresh copies.
          </p>
        </header>
        <Phase2Form />
      </div>
    </main>
  );
}
