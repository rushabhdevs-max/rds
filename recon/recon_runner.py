"""
JSON wrapper around gst_recon_agent.run_recon for the Next.js web frontend.

The Next.js API route (`src/app/api/recon/route.ts`) writes the uploaded input
files into a directory and invokes this script as a subprocess. The script runs
the reconciliation and prints a single JSON object to stdout describing the
result, so the Node side never has to parse human-readable log output.

Contract
--------
The result JSON is written to the path given by `--result-json` (NOT stdout),
because the engine and its LibreOffice subprocess both write progress text to
stdout, which would otherwise corrupt the payload.

On success the file contains:
    {"ok": true,
     "xlsm": "<abs path to report .xlsm>",
     "cf":   "<abs path to updated carry-forward .xlsx>" | null,
     "summary": {book_total, book_matched, ims_total, ims_matched, tiers: {...}}}

On failure the file contains:
    {"ok": false, "error": "<message>"}
and the process exits non-zero.

This is a thin adapter only. It deliberately does NOT modify any engine logic
(see the "never remove logic" / "do not touch" conventions in the project
README); it simply calls the public `run_recon` entry point.
"""

import argparse
import json
import os
import sys
import traceback

# Ensure the engine module (sibling file) is importable regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gst_recon_agent import run_recon  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="JSON wrapper for run_recon")
    ap.add_argument("--input-dir", required=True,
                    help="directory containing the uploaded input files")
    ap.add_argument("--out", required=True,
                    help="output path for the generated .xlsm report")
    ap.add_argument("--period", default="",
                    help="return period e.g. May'26 (auto-detected if empty)")
    ap.add_argument("--carry-forward", default=None,
                    help="path to the carry-forward .xlsx (optional)")
    ap.add_argument("--cf-out", default=None,
                    help="path for the updated carry-forward .xlsx (optional)")
    ap.add_argument("--util-label", default="Utilized",
                    help="status label written to matched carry-forward rows")
    ap.add_argument("--output-summary", default=None,
                    help="path to the outward-revenue summary .xlsx (optional)")
    ap.add_argument("--result-json", required=True,
                    help="path to write the JSON result payload to")
    a = ap.parse_args()

    def write_result(payload: dict) -> None:
        with open(a.result_json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    try:
        xlsm_path, cf_path, summary = run_recon(
            input_dir=a.input_dir,
            out_path=a.out,
            period=a.period,
            carry_forward=a.carry_forward,
            cf_out=a.cf_out,
            util_label=a.util_label,
            outward_summary_path=a.output_summary,
        )
        write_result({
            "ok": True,
            "xlsm": os.path.abspath(xlsm_path) if xlsm_path else None,
            "cf": os.path.abspath(cf_path) if cf_path else None,
            "summary": summary,
        })
        return 0
    except Exception as exc:  # noqa: BLE001 — surface any engine error as JSON
        traceback.print_exc(file=sys.stderr)
        write_result({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
