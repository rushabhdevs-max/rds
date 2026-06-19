import { writeFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";
import {
  createJob,
  runRecon,
  ReconRunError,
  type ReconFileRole,
} from "@/lib/recon";

// Runs the Python engine + LibreOffice subprocess — must be the Node runtime,
// and the reconciliation can take a while on large months.
export const runtime = "nodejs";
export const maxDuration = 300;

/** Upload field name -> engine role. */
const FIELD_ROLES: Record<string, ReconFileRole> = {
  ims: "ims",
  cgst: "cgst",
  sgst: "sgst",
  igst: "igst",
  cf: "cf",
  outward: "outward",
};

const REQUIRED: ReconFileRole[] = ["ims", "cgst", "igst"];
const SAFE_NAME_RE = /[^A-Za-z0-9._'-]+/g;

export async function POST(req: Request) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "Expected a multipart/form-data upload." },
      { status: 400 },
    );
  }

  const job = await createJob();
  try {
    const files: Partial<Record<ReconFileRole, string>> = {};

    for (const [field, role] of Object.entries(FIELD_ROLES)) {
      const value = form.get(field);
      if (!value || typeof value === "string" || value.size === 0) continue;
      // Preserve the original filename (sanitised) so the engine's
      // keyword-based detection still recognises each file by substring.
      const safe = (value.name || `${role}.xlsx`).replace(SAFE_NAME_RE, "_");
      const dest = path.join(job.inDir, safe);
      const buf = Buffer.from(await value.arrayBuffer());
      await writeFile(dest, buf);
      files[role] = dest;
    }

    const missing = REQUIRED.filter((r) => !files[r]);
    if (missing.length > 0) {
      return NextResponse.json(
        { error: `Missing required file(s): ${missing.join(", ").toUpperCase()}.` },
        { status: 400 },
      );
    }

    const period = (form.get("period") as string | null) ?? "";
    const utilLabel = (form.get("utilLabel") as string | null) ?? "";

    const result = await runRecon(job, files, { period, utilLabel });

    return NextResponse.json({
      jobId: job.id,
      summary: result.summary,
      downloads: {
        xlsm: `/api/recon/download?job=${job.id}&kind=xlsm`,
        cf: result.cf ? `/api/recon/download?job=${job.id}&kind=cf` : null,
      },
    });
  } catch (err) {
    if (err instanceof ReconRunError) {
      // Engine-level failure (bad input, missing LibreOffice, etc.).
      return NextResponse.json({ error: err.message }, { status: 422 });
    }
    console.error("[/api/recon] error:", err);
    return NextResponse.json(
      { error: "Something went wrong while running the reconciliation." },
      { status: 500 },
    );
  }
}
