import Link from "next/link";

/** Small tab-style switcher shared by the Phase 1 and Phase 2 recon pages. */
export function ReconNav({ active }: { active: "phase1" | "phase2" }) {
  const tabs = [
    { key: "phase1", href: "/recon", label: "Phase 1 · Books ↔ IMS" },
    { key: "phase2", href: "/recon/phase2", label: "Phase 2 · Leftovers ↔ GSTR-2B" },
  ] as const;

  return (
    <nav className="mb-6 inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
      {tabs.map((t) => {
        const isActive = t.key === active;
        return (
          <Link
            key={t.key}
            href={t.href}
            className={
              isActive
                ? "rounded-lg bg-gradient-to-br from-indigo-600 to-blue-600 px-3.5 py-1.5 text-xs font-medium text-white"
                : "rounded-lg px-3.5 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100"
            }
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
