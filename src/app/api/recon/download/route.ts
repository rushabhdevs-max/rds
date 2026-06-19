import { readFile } from "node:fs/promises";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { resolveJobFile } from "@/lib/recon";

export const runtime = "nodejs";

const META: Record<"xlsm" | "cf", { filename: string; type: string }> = {
  xlsm: {
    filename: "recon.xlsm",
    type: "application/vnd.ms-excel.sheet.macroEnabled.12",
  },
  cf: {
    filename: "Carry_Forward_Updated.xlsx",
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  },
};

export async function GET(req: NextRequest) {
  // Reading searchParams makes this handler dynamic (per-request) by design.
  const params = req.nextUrl.searchParams;
  const job = params.get("job") ?? "";
  const kind = params.get("kind");

  if (kind !== "xlsm" && kind !== "cf") {
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
