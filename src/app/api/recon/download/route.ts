import { readFile } from "node:fs/promises";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { resolveJobFile, type DownloadKind } from "@/lib/recon";

export const runtime = "nodejs";

const XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12";
const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

const META: Record<DownloadKind, { filename: string; type: string }> = {
  xlsm: { filename: "recon.xlsm", type: XLSM },
  cf: { filename: "Carry_Forward_Updated.xlsx", type: XLSX },
  p2workbook: { filename: "recon_phase2.xlsm", type: XLSM },
  p2gstr2b: { filename: "GSTR-2B_updated.xlsx", type: XLSX },
};

function isDownloadKind(v: string | null): v is DownloadKind {
  return v !== null && Object.prototype.hasOwnProperty.call(META, v);
}

export async function GET(req: NextRequest) {
  // Reading searchParams makes this handler dynamic (per-request) by design.
  const params = req.nextUrl.searchParams;
  const job = params.get("job") ?? "";
  const kind = params.get("kind");

  if (!isDownloadKind(kind)) {
    return NextResponse.json({ error: "Invalid file kind." }, { status: 400 });
  }

  const filePath = await resolveJobFile(job, kind);
  if (!filePath) {
    return NextResponse.json(
      { error: "File not found or job expired." },
      { status: 404 },
    );
  }

  const { filename, type } = META[kind];
  const data = await readFile(filePath);
  // Copy into a fresh ArrayBuffer so the BodyInit type is exact.
  const body = new Uint8Array(data);
  return new NextResponse(body, {
    headers: {
      "Content-Type": type,
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Length": String(body.byteLength),
      "Cache-Control": "no-store",
    },
  });
}
