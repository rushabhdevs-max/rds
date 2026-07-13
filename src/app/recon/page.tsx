import type { Metadata } from "next";
import { ReconForm } from "@/components/ReconForm";
import { ReconNav } from "@/components/ReconNav";

export const metadata: Metadata = {
  title: "GST IMS ↔ Books Reconciliation",
  description:
    "Match Airpay's books of input credit against the government's IMS / GSTR-2B B2B invoices and generate a CFO-grade GSTR-3B workbook.",
};

export default function ReconPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-100 via-indigo-50 to-blue-100 px-4 py-10">
      <div className="mx-auto w-full max-w-3xl">
        <ReconNav active="phase1" />
        <header className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            GST IMS ↔ Books ITC Reconciliation
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Upload the monthly input files, run the four-tier matching engine, and download
            the GSTR-3B workbook plus the updated carry-forward ledger.
          </p>
        </header>
        <ReconForm />
      </div>
    </main>
  );
}
