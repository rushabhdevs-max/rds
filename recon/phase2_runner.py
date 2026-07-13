"""
JSON wrapper around phase2_recon.run_phase2 for the Next.js web frontend.

Mirrors recon_runner.py: the Next.js API route writes the uploaded Phase 1
workbook and GSTR-2B register into a job directory and invokes this script as a
subprocess. The result (paths + summary) is written to `--result-json` rather
than stdout, because the engine prints progress text to stdout.

This is a thin adapter only; it does not modify any Phase 2 logic.
"""

import argparse
import json
import os
import sys
import traceback

# Ensure the sibling engine + phase2 modules are importable regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase2_recon import run_phase2  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="JSON wrapper for run_phase2")
    ap.add_argument("--phase1-workbook", required=True,
                    help="path to the Phase 1 output .xlsm")
    ap.add_argument("--gstr2b", required=True,
                    help="path to the GSTR-2B register .xlsx")
    ap.add_argument("--period", required=True,
                    help="return period e.g. May'26 (stamps ITC Taken Month)")
    ap.add_argument("--out-workbook", required=True,
                    help="output path for the updated Phase 2 workbook")
    ap.add_argument("--out-gstr2b", required=True,
                    help="output path for the updated GSTR-2B file")
    ap.add_argument("--result-json", required=True,
                    help="path to write the JSON result payload to")
    a = ap.parse_args()

    def write_result(payload: dict) -> None:
        with open(a.result_json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    try:
        summary = run_phase2(
            phase1_workbook=a.phase1_workbook,
            gstr2b_path=a.gstr2b,
            period=a.period,
            out_workbook=a.out_workbook,
            out_gstr2b=a.out_gstr2b,
        )
        write_result({
            "ok": True,
            "workbook": os.path.abspath(summary["out_workbook"]),
            "gstr2b": os.path.abspath(summary["out_gstr2b"]),
            "summary": summary,
        })
        return 0
    except Exception as exc:  # noqa: BLE001 — surface any engine error as JSON
        traceback.print_exc(file=sys.stderr)
        write_result({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
