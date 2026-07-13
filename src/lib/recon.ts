import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

/**
 * Server-side bridge to the Python GST reconciliation engine
 * (`recon/gst_recon_agent.py`). The engine is invoked as a subprocess via the
 * `recon/recon_runner.py` JSON wrapper — we deliberately do not re-implement
 * any matching/GSTR-3B logic in TypeScript.
 *
 * This module is server-only; never import it from a client component.
 */

/** Summary returned by the engine's `run_recon`. */
export interface ReconSummary {
  book_total: number;
  book_matched: number;
  ims_total: number;
  ims_matched: number;
  tiers: Record<string, number>;
}

export interface ReconResult {
  ok: true;
  /** Absolute path to the generated .xlsm report. */
  xlsm: string | null;
  /** Absolute path to the updated carry-forward .xlsx, if a CF file was given. */
  cf: string | null;
  summary: ReconSummary;
}

interface ReconError {
  ok: false;
  error: string;
}

/** Inputs the engine can consume. Keyed by the role the engine expects. */
export type ReconFileRole = "ims" | "cgst" | "sgst" | "igst" | "cf" | "outward";

export interface ReconRunOptions {
  /** Return period e.g. `May'26`. Empty → engine auto-detects from filenames. */
  period?: string;
  /** Status label written to matched carry-forward rows. */
  utilLabel?: string;
}

const REPO_ROOT = process.cwd();
const RUNNER = path.join(REPO_ROOT, "recon", "recon_runner.py");
const PHASE2_RUNNER = path.join(REPO_ROOT, "recon", "phase2_runner.py");
const PYTHON_BIN = process.env.RECON_PYTHON || "python3";
const JOBS_ROOT = path.join(os.tmpdir(), "gst-recon");

/** Job directories older than this are swept on the next run. */
const JOB_TTL_MS = 60 * 60 * 1000; // 1 hour

/** A persisted reconciliation job on local disk. */
export interface ReconJob {
  id: string;
  dir: string;
  inDir: string;
  outDir: string;
  resultJson: string;
}

const JOB_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Fixed output filenames the runners write into a job's out dir, by download kind. */
export const OUTPUT_FILES = {
  xlsm: "report.xlsm", // Phase 1 report
  cf: "Carry_Forward_Updated.xlsx", // Phase 1 updated carry-forward
  p2workbook: "phase2.xlsm", // Phase 2 updated workbook
  p2gstr2b: "gstr2b_updated.xlsx", // Phase 2 stamped GSTR-2B
} as const;

export type DownloadKind = keyof typeof OUTPUT_FILES;

/** Create a fresh job directory under the OS temp dir. */
export async function createJob(): Promise<ReconJob> {
  await sweepStaleJobs();
  const id = randomUUID();
  const dir = path.join(JOBS_ROOT, id);
  const inDir = path.join(dir, "in");
  const outDir = path.join(dir, "out");
  await mkdir(inDir, { recursive: true });
  await mkdir(outDir, { recursive: true });
  return { id, dir, inDir, outDir, resultJson: path.join(dir, "result.json") };
}

/**
 * Resolve a download path for a finished job. Returns null if the job id is
 * malformed (guards against path traversal) or the file is missing.
 */
export async function resolveJobFile(
  jobId: string,
  kind: DownloadKind,
): Promise<string | null> {
  if (!JOB_ID_RE.test(jobId)) return null;
  const name = OUTPUT_FILES[kind];
  if (!name) return null;
  const outDir = path.join(JOBS_ROOT, jobId, "out");
  const p = path.join(outDir, name);
  // Ensure the resolved path stays inside the job's out dir.
  if (!p.startsWith(outDir + path.sep)) return null;
  try {
    const s = await stat(p);
    if (s.isFile()) return p;
  } catch {
    // not present
  }
  return null;
}

/**
 * Run the reconciliation for a prepared job. Input files must already be
 * written into `job.inDir` with their original filenames so the engine's
 * keyword-based file detection works.
 */
export async function runRecon(
  job: ReconJob,
  files: Partial<Record<ReconFileRole, string>>,
  opts: ReconRunOptions = {},
): Promise<ReconResult> {
  const outXlsm = path.join(job.outDir, "report.xlsm");
  const cfOut = path.join(job.outDir, "Carry_Forward_Updated.xlsx");

  const args = [
    RUNNER,
    "--input-dir", job.inDir,
    "--out", outXlsm,
    "--cf-out", cfOut,
    "--result-json", job.resultJson,
    "--util-label", opts.utilLabel?.trim() || "Utilized",
  ];
  if (opts.period?.trim()) args.push("--period", opts.period.trim());
  if (files.cf) args.push("--carry-forward", files.cf);
  if (files.outward) args.push("--output-summary", files.outward);

  const { code, stderr } = await execPython(args);

  // Prefer the structured result file; fall back to stderr for hard crashes.
  let payload: ReconResult | ReconError | null = null;
  try {
    payload = JSON.parse(await readFile(job.resultJson, "utf-8"));
  } catch {
    payload = null;
  }

  if (payload && payload.ok === false) {
    throw new ReconRunError(payload.error || "Reconciliation failed.");
  }
  if (!payload || payload.ok !== true) {
    const detail = stderr.trim().split("\n").slice(-5).join("\n");
    throw new ReconRunError(
      detail
        ? `Reconciliation failed (exit ${code}). ${detail}`
        : `Reconciliation failed (exit ${code}).`,
    );
  }
  return payload;
}

/** Summary returned by the Phase 2 driver's `run_phase2`. */
export interface Phase2Summary {
  books_input: number;
  gstr2b_eligible: number;
  books_matched: number;
  gstr2b_matched: number;
  tiers: Record<string, number>;
  itc_recovered: number;
  itc_month_label?: string;
}

export interface Phase2Result {
  ok: true;
  /** Absolute path to the updated Phase 2 workbook. */
  workbook: string;
  /** Absolute path to the stamped GSTR-2B file. */
  gstr2b: string;
  summary: Phase2Summary;
}

/**
 * Run the Phase 2 second-pass reconciliation. `phase1` and `gstr2b` must be
 * paths to files already written into `job.inDir`.
 */
export async function runPhase2(
  job: ReconJob,
  phase1: string,
  gstr2b: string,
  period: string,
): Promise<Phase2Result> {
  if (!period.trim()) {
    throw new ReconRunError("A return period (e.g. May'26) is required for Phase 2.");
  }
  const outWorkbook = path.join(job.outDir, OUTPUT_FILES.p2workbook);
  const outGstr2b = path.join(job.outDir, OUTPUT_FILES.p2gstr2b);

  const args = [
    PHASE2_RUNNER,
    "--phase1-workbook", phase1,
    "--gstr2b", gstr2b,
    "--period", period.trim(),
    "--out-workbook", outWorkbook,
    "--out-gstr2b", outGstr2b,
    "--result-json", job.resultJson,
  ];

  const { code, stderr } = await execPython(args);

  let payload: Phase2Result | ReconError | null = null;
  try {
    payload = JSON.parse(await readFile(job.resultJson, "utf-8"));
  } catch {
    payload = null;
  }

  if (payload && payload.ok === false) {
    throw new ReconRunError(payload.error || "Phase 2 reconciliation failed.");
  }
  if (!payload || payload.ok !== true) {
    const detail = stderr.trim().split("\n").slice(-5).join("\n");
    throw new ReconRunError(
      detail
        ? `Phase 2 failed (exit ${code}). ${detail}`
        : `Phase 2 failed (exit ${code}).`,
    );
  }
  return payload;
}

/** Error type so the API route can map engine failures to a 422 response. */
export class ReconRunError extends Error {}

function execPython(
  args: string[],
): Promise<{ code: number | null; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON_BIN, args, {
      cwd: REPO_ROOT,
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("error", (err) =>
      reject(
        new ReconRunError(
          `Could not start Python ("${PYTHON_BIN}"): ${err.message}. ` +
            `Set RECON_PYTHON to a valid interpreter with the recon deps installed.`,
        ),
      ),
    );
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

/** Best-effort cleanup of job dirs older than the TTL. */
async function sweepStaleJobs(): Promise<void> {
  let entries: string[];
  try {
    entries = await readdir(JOBS_ROOT);
  } catch {
    return; // root doesn't exist yet
  }
  const now = Date.now();
  await Promise.all(
    entries.map(async (name) => {
      const dir = path.join(JOBS_ROOT, name);
      try {
        const s = await stat(dir);
        if (now - s.mtimeMs > JOB_TTL_MS) {
          await rm(dir, { recursive: true, force: true });
        }
      } catch {
        // ignore
      }
    }),
  );
}
