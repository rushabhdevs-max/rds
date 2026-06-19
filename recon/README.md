# GST Reconciliation — web frontend

A Next.js frontend (route `/recon`) for the GST IMS ↔ Books ITC reconciliation
engine. It replaces the standalone Streamlit `app.py`: same `run_recon` driver,
same outputs, served from this repo instead of a separate Python process you
launch by hand.

The engine itself is **unchanged** Python (`gst_recon_agent.py`). The web layer
shells out to it; it does not re-implement any matching, carry-forward, or
GSTR-3B logic in TypeScript.

## Pieces

| File | Role |
|---|---|
| `recon/gst_recon_agent.py` | The reconciliation engine (verbatim, do not edit). |
| `recon/AutoMoveMatched.bas` | Excel macros shipped alongside the output. |
| `recon/recon_runner.py` | Thin JSON wrapper around `run_recon`. Writes its result to a `--result-json` file so engine/LibreOffice stdout never corrupts the payload. |
| `recon/requirements.txt` | Python deps for the engine. |
| `src/lib/recon.ts` | Server-only bridge: spawns the runner, manages per-job temp dirs, resolves downloads. |
| `src/app/api/recon/route.ts` | `POST` — multipart upload → run → summary + download URLs. |
| `src/app/api/recon/download/route.ts` | `GET` — streams `report.xlsm` / updated carry-forward. |
| `src/app/recon/page.tsx` + `src/components/ReconForm.tsx` | The upload form, results scorecard, download buttons. |

## One-click launch (`run.bat`)

On Windows, double-click **`run.bat`** in the repo root. It replaces the old
Streamlit launcher: on the first run it installs Node + Python dependencies and
builds the app, then on every run it starts the server and opens the browser at
`http://localhost:3000/recon`. Press `Ctrl+C` in the console window to stop it.

`run.bat` picks the Windows Python command (`python`) automatically and passes
it to the server via `RECON_PYTHON`, so the engine subprocess uses the right
interpreter. LibreOffice must still be installed separately (see below).

To run it by hand instead:

```bash
pip install -r recon/requirements.txt   # once
npm install                             # once
npm run dev                             # then open http://localhost:3000/recon
```

## Prerequisites (server host)

The API route runs the engine as a subprocess, so the host needs:

1. **Python 3** with the engine deps:
   ```bash
   pip install -r recon/requirements.txt
   ```
2. **LibreOffice** on `PATH` (`libreoffice` / `soffice`) — the engine converts
   the working `.xlsx` to the final macro-enabled `.xlsm` headlessly.

If Python lives somewhere non-standard, set `RECON_PYTHON` to the interpreter
path (e.g. a virtualenv's `python`). It defaults to `python3`.

## Flow

1. The user attaches files on `/recon`. IMS, CGST and IGST are required; SGST,
   Carry-Forward and Outward-Revenue-Summary are optional. The period is
   auto-detected from filenames (editable).
2. `POST /api/recon` writes the uploads into a fresh temp job dir under the OS
   temp dir, preserving original filenames so the engine's keyword-based file
   detection still works.
3. `recon_runner.py` runs `run_recon` and writes `result.json`.
4. The route returns the summary plus `/api/recon/download?job=<id>&kind=xlsm|cf`
   URLs. Job dirs are swept after 1 hour.

Engine-level failures (bad input, missing LibreOffice, unmatched period) come
back as HTTP 422 carrying the engine's own message; the UI shows it inline.

## Notes

- Job ids are UUIDs and validated on download (no path traversal).
- This is a wrapper, not a rewrite — see the project conventions about never
  removing engine logic.
