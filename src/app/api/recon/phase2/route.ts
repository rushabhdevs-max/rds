import { writeFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";
import { createJob, runPhase2, ReconRunError } from "@/lib/recon";

// Runs the Python engine + LibreOffice/openpyxl subprocess — Node runtime,
// and the second pass can take a while on large registers.
export const runtime = "nodejs";
export const maxDuration = 300;

const SAFE_NAME_RE = /[^A-Za-z0-9._'-]+/g;

function safeName(name: string, fallback: string): string {
  return (name || fallback).replace(SAFE_NAME_RE, "_");
}

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

  const phase1 = form.get("phase1");
  const gstr2b = form.get("gstr2b");
  const period = ((form.get("period") as string | null) ?? "").trim();

  if (!phase1 || typeof phase1 === "string" || phase1.size === 0) {
    return NextResponse.json(
      { error: "The Phase 1 workbook (.xlsm) is required." },
      { status: 400 },
    );
  }
  if (!gstr2b || typeof gstr2b === "string" || gstr2b.size === 0) {
    return NextResponse.json(
      { error: "The GSTR-2B register (.xlsx) is required." },
      { status: 400 },
    );
  }
  if (!period) {
    return NextResponse.json(
      { error: "A return period (e.g. May'26) is required." },
      { status: 400 },
    );
  }

  const job = await createJob();
  try {
    const phase1Path = path.join(job.inDir, safeName(phase1.name, "phase1.xlsm"));
    const gstr2bPath = path.join(job.inDir, safeName(gstr2b.name, "gstr2b.xlsx"));
    await writeFile(phase1Path, Buffer.from(await phase1.arrayBuffer()));
    await writeFile(gstr2bPath, Buffer.from(await gstr2b.arrayBuffer()));

    const result = await runPhase2(job, phase1Path, gstr2bPath, period);

    return NextResponse.json({
      jobId: job.id,
      summary: result.summary,
      downloads: {
        workbook: `/api/recon/download?job=${job.id}&kind=p2workbook`,
        gstr2b: `/api/recon/download?job=${job.id}&kind=p2gstr2b`,
      },
    });
  } catch (err) {
    if (err instanceof ReconRunError) {
      return NextResponse.json({ error: err.message }, { status: 422 });
    }
    console.error("[/api/recon/phase2] error:", err);
    return NextResponse.json(
      { error: "Something went wrong while running Phase 2." },
      { status: 500 },
    );
  }
}
