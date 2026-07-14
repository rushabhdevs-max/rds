# Airpay Reconciliation — Streamlit app

Self-contained two-stage + settlement reconciliation UI (`app_1.py`).

## Run it

**Windows:** double-click **`run.bat`**. On first launch it installs the Python
dependencies, then it opens your browser at `http://localhost:8501`.

**Any OS (manual):**

```bash
pip install -r requirements.txt
streamlit run app_1.py
```

Then open `http://localhost:8501`.

## Requirements

- Python 3
- `streamlit`, `pandas`, `numpy`, `openpyxl`, `xlrd` (installed from
  `requirements.txt`; `xlrd` is only needed for legacy `.xls` uploads)

## Notes

- The app writes `recon_config.json` in this folder to remember per-bank
  settlement-cycle settings; it is created on demand and git-ignored.
- This is a standalone Streamlit tool, separate from the GST recon frontend
  under `../recon` and the Next.js app at the repo root.
