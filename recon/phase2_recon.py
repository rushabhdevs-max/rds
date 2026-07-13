"""
Phase 2 GST Reconciliation
==========================

Second-pass reconciliation. Takes the Phase 1 output workbook (specifically the
"Unmatched - Books only" tab) and matches those leftover books rows against a
GSTR-2B register, considering only rows where 'ITC Taken Month' is blank.

Any match moves the books row from Unmatched to Matched/Review in a NEW
workbook (Phase 1 workbook is untouched). Every matched GSTR-2B row gets its
'ITC Taken Month' stamped with 'Mmm-YY' in a NEW copy of the GSTR-2B file
(surgical XML edit; byte-identical elsewhere).

Design notes
------------
- Reuses the Phase 1 Recon engine (5-tier cascade, same tolerances).
- Reads the 14-column "Unmatched - Books only" tab produced by Phase 1.
- Debit-note detection is skipped in Phase 2 (voucher_type is not preserved on
  the Phase 1 output tab; all rows flow through the matcher untagged). Sign
  display is not applied on Matched/Review destinations so this is harmless.
- Same 5 tiers, same tolerances (±1/±0.5% for tiers 1-3, ±2/±1% for 4/4b).
- GSTR-2B rows filtered to: ITC Taken Month is blank. No filter on Month
  column (register spans multiple periods; we take any unclaimed row).
- All 14 tabs from Phase 1 workbook carried through into Phase 2 output.
"""

from __future__ import annotations
import os
import re
import shutil
import argparse
import zipfile
import io
import datetime as dt
from typing import Optional, Tuple

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# We reuse Phase 1's Recon engine + helpers verbatim.
from gst_recon_agent import (
    Recon,
    norm_inv,
    _clean_gstin,
    _clean_compact,
    to_num,
    values_match,
)


# --------------------------------------------------------------------------
# Helpers copied verbatim from gst_recon_agent.build_report (they are nested
# inside the function and can't be imported directly). Keeping them in lock-
# step with the Phase 1 source is important — if _reshape_matched or
# _attach_tax_rate change in gst_recon_agent.py, they need to be updated
# here too.
# --------------------------------------------------------------------------

def _tax_rate(taxable, cgst, sgst, igst):
    """((IGST/Taxable)*100) when IGST > 0; else ((CGST+SGST)/Taxable*100).
    Returns "" when taxable is 0/blank to avoid divide-by-zero."""
    try:
        tx = float(taxable or 0); c = float(cgst or 0); s = float(sgst or 0); i = float(igst or 0)
    except (TypeError, ValueError):
        return ""
    if tx <= 0:
        return ""
    if i > 0:
        return round(i / tx * 100, 2)
    if (c + s) > 0:
        return round((c + s) / tx * 100, 2)
    return ""


def _attach_tax_rate(df, tax_col, c_col, s_col, i_col):
    """Add a 'Tax Rate %' column at the end of df, computed per row."""
    if df is None or len(df) == 0:
        df = df.copy() if df is not None else pd.DataFrame()
        df["Tax Rate %"] = []
        return df
    df = df.copy()
    df["Tax Rate %"] = [
        _tax_rate(r.get(tax_col), r.get(c_col), r.get(s_col), r.get(i_col))
        for _, r in df.iterrows()
    ]
    return df


def _reshape_matched(df):
    """Reshape a matched-records DataFrame to the 32-column layout used by
    Phase 1's Matched (Exact) / Review (Fuzzy+Agg) tabs."""
    if df.empty:
        return pd.DataFrame(columns=[
            "date","book_supplier","ims_supplier","book_gstin","ims_gstin",
            "gstin_match","book_ref_no","ims_inv_no","ims_status",
            "Books_taxable_value","Books_igst","Books_cgst","Books_sgst",
            "IMS_taxable_value","IMS_igst","IMS_cgst","IMS_sgst",
            "Diff_igst","Diff_cgst","Diff_sgst",
            "book_total_tax","ims_total_tax","tax_diff","Tax Rate %",
            "note","book_entry_count","ims_invoice_count",
            "match_source","tier","confidence","source_file","Move to Matched?",
        ])
    out = pd.DataFrame()
    out["date"]              = df.get("date", "")
    out["book_supplier"]     = df.get("book_supplier", "")
    out["ims_supplier"]      = df.get("ims_supplier", "")
    out["book_gstin"]        = df.get("book_gstin", "")
    out["ims_gstin"]         = df.get("ims_gstin", "")
    out["gstin_match"]       = df.get("gstin_match", "")
    out["book_ref_no"]       = df.get("book_ref_no", "")
    out["ims_inv_no"]        = df.get("ims_inv_no", "")
    out["ims_status"]        = df.get("ims_status", "")
    out["Books_taxable_value"] = df.get("taxable_value", 0)
    out["Books_igst"]          = df.get("book_igst", df.get("igst", 0))
    out["Books_cgst"]          = df.get("book_cgst", df.get("cgst", 0))
    out["Books_sgst"]          = df.get("book_sgst", df.get("sgst", 0))
    out["IMS_taxable_value"] = df.get("ims_taxable", 0)
    out["IMS_igst"]          = df.get("ims_igst", 0)
    out["IMS_cgst"]          = df.get("ims_cgst", 0)
    out["IMS_sgst"]          = df.get("ims_sgst", 0)
    out["Diff_igst"] = out["Books_igst"].astype(float) - out["IMS_igst"].astype(float)
    out["Diff_cgst"] = out["Books_cgst"].astype(float) - out["IMS_cgst"].astype(float)
    out["Diff_sgst"] = out["Books_sgst"].astype(float) - out["IMS_sgst"].astype(float)
    out["book_total_tax"]    = df.get("book_total_tax", 0)
    out["ims_total_tax"]     = df.get("ims_total_tax", 0)
    out["tax_diff"]          = df.get("tax_diff", 0)
    out["Tax Rate %"]        = df.get("Tax Rate %", "")
    out["note"]              = df.get("note", "")
    out["book_entry_count"]  = df.get("book_entry_count", 0)
    out["ims_invoice_count"] = df.get("ims_invoice_count", 0)
    out["match_source"]      = df.get("match_source", "Engine")
    out["tier"]              = df.get("tier", "")
    out["confidence"]        = df.get("confidence", "")
    out["source_file"]       = df.get("source_file", "")
    out["Move to Matched?"]  = ""
    return out


# ============================================================================
# GSTR-2B loader
# ============================================================================

# Column names in the GSTR-2B register (header row = row 5 in Excel,
# 0-indexed row 4). Verified against the uploaded sample file.
GSTR2B_HEADER_ROW = 4  # 0-indexed for pandas
GSTR2B_ITC_COL = "ITC Taken Month"
GSTR2B_HEAD_COL = "Head"
GSTR2B_MONTH_COL = "Month"

# All 6 heads eligible for matching (per user decision).
ELIGIBLE_HEADS = frozenset({"B2B", "B2BA", "CN", "DN", "CNA", "IMPG"})

# Which heads represent credit-note-like reductions of ITC. For sign handling
# on the IMS-like side we mirror Phase 1's B2B-CN treatment: values kept
# positive in the matcher, sign only matters at display time.
CN_LIKE_HEADS = frozenset({"CN", "CNA"})


def load_gstr2b(path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load the GSTR-2B register into an IMS-shaped DataFrame.

    Returns
    -------
    eligible : pd.DataFrame
        Rows where ITC Taken Month is blank AND Head is one of the 6
        eligible categories. Columns normalised to match the schema the
        Phase 1 Recon engine expects (gstin, inv_no, taxable, igst, cgst,
        sgst, cess, total_tax, status, ret_period, source_sheet, inv_norm,
        ims_id, plus '_gstr2b_row' pointing back to the source row number
        for the write-back step).
    original : pd.DataFrame
        The full raw DataFrame (all rows, all columns) — used later to write
        back only the rows we matched without disturbing anything else.
    """
    df = pd.read_excel(path, header=GSTR2B_HEADER_ROW)
    df = df.reset_index(drop=True)
    # Track the source row number (1-indexed Excel row where the row lives,
    # accounting for the header being on row 5 = header_row + 2 for 0-indexed
    # data row 0 becomes Excel row 6).
    df["_gstr2b_row"] = df.index + GSTR2B_HEADER_ROW + 2

    # --- Filter to eligible rows ---
    # A row is eligible if:
    #   * ITC Taken Month is blank (NaN or empty-string), AND
    #   * Head is one of the 6 categories we accept.
    itc = df[GSTR2B_ITC_COL].astype(str).str.strip()
    itc_blank = df[GSTR2B_ITC_COL].isna() | (itc == "") | (itc.str.lower() == "nan")
    head_ok = df[GSTR2B_HEAD_COL].astype(str).str.strip().isin(ELIGIBLE_HEADS)
    eligible_raw = df[itc_blank & head_ok].copy()

    if len(eligible_raw) == 0:
        # empty eligible pool — return an empty frame with the right shape
        empty = pd.DataFrame(columns=[
            "ims_id", "gstin", "name", "inv_no", "inv_type", "inv_date",
            "inv_val", "taxable", "igst", "cgst", "sgst", "cess", "status",
            "pos", "remarks", "source", "ret_period", "filing", "source_sheet",
            "total_tax", "inv_norm", "_gstr2b_row",
        ])
        return empty, df

    # --- Normalise columns to the Recon engine's expected schema ---
    out = pd.DataFrame()
    out["gstin"] = eligible_raw["GSTIN of supplier"].apply(_clean_gstin)
    out["name"] = eligible_raw["Trade/Legal name"].astype(str).str.strip()
    out["inv_no"] = eligible_raw["Invoice number"].astype(str).str.strip()
    out["inv_type"] = eligible_raw["Invoice type"].astype(str).str.strip()
    out["inv_date"] = eligible_raw["Invoice Date"].astype(str)
    out["inv_val"] = eligible_raw["Invoice Value(\u20b9)"].apply(to_num)
    out["taxable"] = eligible_raw["Taxable Value (\u20b9)"].apply(to_num)
    out["igst"] = eligible_raw["Integrated Tax(\u20b9)"].apply(to_num)
    out["cgst"] = eligible_raw["Central Tax(\u20b9)"].apply(to_num)
    out["sgst"] = eligible_raw["State/UT Tax(\u20b9)"].apply(to_num)
    out["cess"] = eligible_raw["Cess(\u20b9)"].apply(to_num) if "Cess(\u20b9)" in eligible_raw.columns else 0.0
    out["status"] = ""  # GSTR-2B has no ims_status equivalent
    out["pos"] = eligible_raw["Place of supply"].astype(str).str.strip() if "Place of supply" in eligible_raw.columns else ""
    out["remarks"] = eligible_raw["Remarks"].astype(str).str.strip() if "Remarks" in eligible_raw.columns else ""
    out["source"] = "GSTR-2B"
    out["ret_period"] = eligible_raw["GSTR-1/IFF/GSTR-5 Period"].astype(str).str.strip() if "GSTR-1/IFF/GSTR-5 Period" in eligible_raw.columns else ""
    out["filing"] = eligible_raw["GSTR-1/IFF/GSTR-5 Filing Date"].astype(str).str.strip() if "GSTR-1/IFF/GSTR-5 Filing Date" in eligible_raw.columns else ""
    # Head is stored as source_sheet so the Recon engine can see it (mirrors
    # Phase 1's B2B/B2B-CN tagging).
    out["source_sheet"] = eligible_raw[GSTR2B_HEAD_COL].astype(str).str.strip()

    out["total_tax"] = out["igst"].abs() + out["cgst"].abs() + out["sgst"].abs()
    out["inv_norm"] = out["inv_no"].apply(norm_inv)
    out["_gstr2b_row"] = eligible_raw["_gstr2b_row"].values
    out = out.reset_index(drop=True)
    out.insert(0, "ims_id", [f"G{i:05d}" for i in range(len(out))])

    return out, df


# ============================================================================
# Phase 1 workbook - books-side reader
# ============================================================================

def load_unmatched_books(phase1_xlsm_path: str) -> pd.DataFrame:
    """Read the 'Unmatched - Books only' tab from a Phase 1 output workbook,
    reshape into a books DataFrame that the Recon engine can consume.

    Rows returned carry a Phase-2-specific book_id prefix ('P2B0000', ...)
    so they cannot collide with the original Phase 1 book_id space. The
    ref_norm column is re-derived here (Phase 1 does not persist it to the
    output tab). voucher_type is set to empty string (Phase 1 does not
    preserve it either); this means debit-note detection is a no-op in
    Phase 2 (all rows flow through the matcher without a sign flip).
    """
    wb = load_workbook(phase1_xlsm_path, data_only=True)
    if "Unmatched - Books only" not in wb.sheetnames:
        raise ValueError(
            f"Phase 1 workbook is missing the 'Unmatched - Books only' tab. "
            f"Sheets found: {wb.sheetnames}"
        )
    ws = wb["Unmatched - Books only"]

    # Read into a pandas DataFrame the low-tech way (openpyxl values)
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    rows = []
    for r in range(2, ws.max_row + 1):
        row = {h: ws.cell(r, c).value for c, h in enumerate(headers, start=1) if h}
        # Skip empty rows (all None)
        if all(v is None or v == "" for v in row.values()):
            continue
        rows.append(row)
    if not rows:
        # Empty tab — no leftover books to match
        return pd.DataFrame(columns=[
            "book_id", "gstin", "supplier", "voucher_no", "ref_no", "date",
            "gross_total", "taxable", "cgst", "sgst", "igst", "total_tax",
            "ref_norm", "voucher_type", "source_sheet",
        ])

    df = pd.DataFrame(rows)

    # --- Ensure every column the Recon engine needs is present ---
    # Coerce numeric fields (they came through openpyxl as int/float/None).
    for c in ("gross_total", "taxable", "cgst", "sgst", "igst", "total_tax"):
        if c in df.columns:
            df[c] = df[c].apply(to_num)
        else:
            df[c] = 0.0

    # Coerce string identity fields
    for c in ("gstin", "supplier", "voucher_no", "ref_no", "date"):
        if c in df.columns:
            df[c] = df[c].astype(str).replace({"None": "", "nan": ""}).str.strip()
        else:
            df[c] = ""

    # Drop audit noise (present in Phase 1 output but useless for matching)
    for c in ("Tax Rate %", "Move to Matched?"):
        if c in df.columns:
            df = df.drop(columns=[c])

    # Re-derive fields the Recon engine expects
    df["ref_norm"] = df["ref_no"].apply(norm_inv)
    df["voucher_type"] = ""  # not preserved on the Phase 1 output; harmless empty
    df["source_sheet"] = "BOOKS"

    # Reprefix book_id so Phase 2 IDs don't collide with any subsequent
    # Phase 1 rerun that would produce book_id 'B0000', 'B0001', ...
    df = df.reset_index(drop=True)
    df["book_id"] = [f"P2B{i:04d}" for i in range(len(df))]

    # Return columns in a sensible order
    ordered = ["book_id", "gstin", "supplier", "voucher_no", "ref_no", "date",
               "gross_total", "taxable", "cgst", "sgst", "igst", "total_tax",
               "ref_norm", "voucher_type", "source_sheet"]
    return df[[c for c in ordered if c in df.columns]]


# ============================================================================
# ITC Taken Month writer (surgical XML edit on GSTR-2B file)
# ============================================================================

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _format_itc_month(period: str) -> str:
    """Convert a period like "May'26" -> "May-26".

    Accepts several input shapes: Mon'YY, Mon-YY, Mon YY, MonYYYY.
    Emits three-letter title-case month + '-' + two-digit year.
    """
    p = str(period).strip().replace("\u2019", "'")
    # Try Mon'YY / Mon-YY / Mon YY
    m = re.match(r"^([A-Za-z]{3,})['\-\s]?(\d{2,4})$", p)
    if not m:
        raise ValueError(f"Cannot parse period {period!r} as a Mon-YY value.")
    mon = m.group(1)[:3].title()
    if mon not in MONTH_ABBR:
        raise ValueError(f"Unknown month prefix in period {period!r}: {mon!r}")
    yr = m.group(2)
    yr = yr[-2:] if len(yr) == 4 else yr
    return f"{mon}-{yr}"


def write_updated_gstr2b(
    src_path: str,
    out_path: str,
    matched_source_rows: set,
    itc_month_label: str,
) -> None:
    """Copy src_path -> out_path, then stamp itc_month_label into the
    'ITC Taken Month' column of every row whose source Excel row number is
    in matched_source_rows. Uses openpyxl to preserve every other cell,
    formula, style, and structure.
    """
    if os.path.abspath(src_path) == os.path.abspath(out_path):
        raise ValueError("write_updated_gstr2b: src and out paths must differ.")
    shutil.copy2(src_path, out_path)

    if not matched_source_rows:
        # No matches to stamp; the copy is already the correct output.
        return

    wb = load_workbook(out_path)
    # First (and only) sheet is the GSTR-2B register
    ws = wb[wb.sheetnames[0]]

    # Locate the 'ITC Taken Month' column (header row = row 5 in Excel).
    header_row = GSTR2B_HEADER_ROW + 1  # 1-indexed
    itc_col = None
    for c in range(1, ws.max_column + 1):
        if str(ws.cell(header_row, c).value or "").strip() == GSTR2B_ITC_COL:
            itc_col = c
            break
    if itc_col is None:
        raise ValueError(
            f"Could not locate {GSTR2B_ITC_COL!r} column in the GSTR-2B "
            f"header row {header_row}."
        )

    for src_row in matched_source_rows:
        ws.cell(src_row, itc_col, itc_month_label)

    wb.save(out_path)


# ============================================================================
# Workbook update (Phase 2 output construction)
# ============================================================================

MATCHED_TAB = "Matched (Exact)"
REVIEW_TAB = "Review (Fuzzy+Agg)"
UNMATCHED_BOOKS_TAB = "Unmatched - Books only"
GSTR3B_WORKING_TAB = "GSTR3B Working"
ALL_TX_TAB = "All Transactions"
SUMMARY_TAB = "Summary"


def _append_rows(ws, rows: list, header_row: int = 1) -> None:
    """Append a list of dict rows to worksheet, using the header row to map
    dict keys -> column indices. Rows lacking a key get None in that cell.
    Extra keys (not in the header) are silently ignored."""
    if not rows:
        return
    headers = [ws.cell(header_row, c).value for c in range(1, ws.max_column + 1)]
    hdr_to_col = {h: c for c, h in enumerate(headers, start=1) if h}
    start_row = ws.max_row + 1
    for i, r in enumerate(rows):
        for k, v in r.items():
            c = hdr_to_col.get(k)
            if c is not None:
                ws.cell(start_row + i, c, v)


def _remove_rows_from_tab(ws, book_ids_to_remove: set, header_row: int = 1) -> int:
    """Remove rows from a worksheet where the 'book_id' column value is in
    book_ids_to_remove. Uses openpyxl's delete_rows (single-row-at-a-time,
    scanning bottom-up to keep indices stable). Returns count removed.
    """
    if not book_ids_to_remove:
        return 0
    headers = [ws.cell(header_row, c).value for c in range(1, ws.max_column + 1)]
    if "book_id" not in headers:
        return 0
    bid_col = headers.index("book_id") + 1

    # Collect rows to remove (bottom-up so deletions don't shift pending ones)
    to_delete = []
    for r in range(ws.max_row, header_row, -1):
        v = ws.cell(r, bid_col).value
        if v in book_ids_to_remove:
            to_delete.append(r)
    for r in to_delete:
        ws.delete_rows(r, 1)
    return len(to_delete)


def _build_gstr3b_working_rows(matched_records: pd.DataFrame) -> list:
    """Reshape matched records into the GSTR3B Working tab schema.

    GSTR3B Working column order (from Phase 1's build_report):
        Particulars / Supplier | GSTIN | Voucher / Invoice No |
        Taxable Value | CGST | SGST | IGST | Date | Status |
        Origin | Source File | Tax Rate %
    """
    rows = []
    for _, m in matched_records.iterrows():
        # Books side is authoritative for the ITC amount (GSTR3B §4(5) is a
        # books-side sum).
        taxable = float(m.get("taxable_value", 0) or 0)
        cgst = float(m.get("book_cgst", m.get("cgst", 0) or 0))
        sgst = float(m.get("book_sgst", m.get("sgst", 0) or 0))
        igst = float(m.get("book_igst", m.get("igst", 0) or 0))
        tax = igst + cgst + sgst
        rate = round(tax / taxable * 100, 2) if taxable else None
        rows.append({
            "Particulars / Supplier": m.get("book_supplier", ""),
            "GSTIN": m.get("book_gstin", ""),
            "Voucher / Invoice No": m.get("book_ref_no", ""),
            "Taxable Value": taxable,
            "CGST": cgst,
            "SGST": sgst,
            "IGST": igst,
            "Date": m.get("date", ""),
            "Status": "Matched (Exact)" if m.get("tier") == "1-EXACT" else "Review (Fuzzy+Agg)",
            "Origin": "Phase2",
            "Source File": "Books",
            "Tax Rate %": rate,
        })
    return rows


def _build_all_transactions_rows(matched_records: pd.DataFrame) -> list:
    """Reshape matched records for the All Transactions master tab.

    All Transactions column order (from Phase 1's build_report):
        match_source | tier | confidence | gstin_match | taxable |
        date | cgst | sgst | igst | book_gstin | ims_gstin |
        book_supplier | ims_supplier | book_ref_no | ims_inv_no |
        ims_status | book_total_tax | ims_total_tax | tax_diff |
        book_entry_count | ims_invoice_count | note | Status |
        Source File | Tax Rate %
    """
    rows = []
    for _, m in matched_records.iterrows():
        taxable = float(m.get("taxable_value", 0) or 0)
        cgst = float(m.get("book_cgst", m.get("cgst", 0) or 0))
        sgst = float(m.get("book_sgst", m.get("sgst", 0) or 0))
        igst = float(m.get("book_igst", m.get("igst", 0) or 0))
        rate = round((igst + cgst + sgst) / taxable * 100, 2) if taxable else None
        rows.append({
            "match_source": "Phase2",
            "tier": m.get("tier", ""),
            "confidence": m.get("confidence", ""),
            "gstin_match": "Y",
            "taxable_value": taxable,
            "date": m.get("date", ""),
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "book_gstin": m.get("book_gstin", ""),
            "ims_gstin": m.get("ims_gstin", ""),
            "book_supplier": m.get("book_supplier", ""),
            "ims_supplier": m.get("ims_supplier", ""),
            "book_ref_no": m.get("book_ref_no", ""),
            "ims_inv_no": m.get("ims_inv_no", ""),
            "ims_status": m.get("ims_status", ""),
            "book_total_tax": m.get("book_total_tax", ""),
            "ims_total_tax": m.get("ims_total_tax", ""),
            "tax_diff": m.get("tax_diff", ""),
            "book_entry_count": m.get("book_entry_count", 1),
            "ims_invoice_count": m.get("ims_invoice_count", 1),
            "note": m.get("note", ""),
            "Status": "Matched (Exact)" if m.get("tier") == "1-EXACT" else "Review (Fuzzy+Agg)",
            "Source File": "Books",
            "Tax Rate %": rate,
        })
    return rows


def apply_phase2_matches_to_workbook(
    workbook_path: str,
    matches_df: pd.DataFrame,
    matched_book_ids: set,
) -> None:
    """Open the workbook, append Phase 2 matches to Matched/Review tabs,
    remove matched rows from Unmatched - Books only, append into GSTR3B
    Working and All Transactions. Save back in place.

    Note: matched_book_ids uses the ORIGINAL book_id values from the
    Phase 1 workbook (e.g. 'B0000'), NOT the P2B-prefixed IDs we assigned
    during Phase 2 processing. The Recon engine sees P2B-prefixed IDs;
    caller must translate back before calling this function.
    """
    wb = load_workbook(workbook_path, keep_vba=True)

    # --- 1. Append to Matched / Review tabs ---
    matched = matches_df[matches_df["tier"] == "1-EXACT"] if not matches_df.empty else matches_df
    review = matches_df[matches_df["tier"] != "1-EXACT"] if not matches_df.empty else matches_df

    for tab_name, df_subset in ((MATCHED_TAB, matched), (REVIEW_TAB, review)):
        if tab_name not in wb.sheetnames or df_subset.empty:
            continue
        ws = wb[tab_name]
        # Tag phase before reshape
        df_tagged = df_subset.copy()
        df_tagged["match_source"] = "Phase2"
        df_tagged["source_file"] = "GSTR-2B"
        reshaped = _reshape_matched(_attach_tax_rate(
            df_tagged, "taxable_value", "cgst", "sgst", "igst"
        ))
        rows_as_dicts = reshaped.to_dict(orient="records")
        _append_rows(ws, rows_as_dicts, header_row=1)

    # --- 2. Remove matched book_ids from Unmatched - Books only ---
    if UNMATCHED_BOOKS_TAB in wb.sheetnames:
        n = _remove_rows_from_tab(wb[UNMATCHED_BOOKS_TAB], matched_book_ids)
        # (n is discarded, but useful for logging)

    # --- 3. Append to GSTR3B Working ---
    if GSTR3B_WORKING_TAB in wb.sheetnames and not matches_df.empty:
        _append_rows(wb[GSTR3B_WORKING_TAB],
                     _build_gstr3b_working_rows(matches_df), header_row=1)

    # --- 4. Append to All Transactions ---
    if ALL_TX_TAB in wb.sheetnames and not matches_df.empty:
        _append_rows(wb[ALL_TX_TAB],
                     _build_all_transactions_rows(matches_df), header_row=1)

    # --- 5. Refresh Summary KPI counts ---
    # Summary tab has a hidden state and only ships text/count cells; we
    # regenerate the affected count cells if they exist. Because the tab
    # was built with a specific layout in Phase 1, and the numbers are
    # already stale after Phase 2 matches, we prepend a small "Phase 2
    # additions" block near the top for finance visibility, without
    # rewriting the whole tab.
    if SUMMARY_TAB in wb.sheetnames and not matches_df.empty:
        ws_sum = wb[SUMMARY_TAB]
        # Add a compact Phase 2 note at the last free row
        last = ws_sum.max_row + 2
        ws_sum.cell(last, 1, "Phase 2 additions").font = Font(bold=True, color="1F4E78")
        ws_sum.cell(last + 1, 1, "Book entries matched via Phase 2")
        ws_sum.cell(last + 1, 2, int(matches_df["book_entry_count"].sum())
                    if "book_entry_count" in matches_df.columns else len(matched_book_ids))
        ws_sum.cell(last + 2, 1, "GSTR-2B invoices matched via Phase 2")
        ws_sum.cell(last + 2, 2, int(matches_df["ims_invoice_count"].sum())
                    if "ims_invoice_count" in matches_df.columns else 0)
        ws_sum.cell(last + 3, 1, "ITC recovered via Phase 2 (\u20b9)")
        ws_sum.cell(last + 3, 2, float(matches_df["book_total_tax"].astype(float).sum())
                    if "book_total_tax" in matches_df.columns else 0.0)

    wb.save(workbook_path)


# ============================================================================
# Driver
# ============================================================================

def run_phase2(
    phase1_workbook: str,
    gstr2b_path: str,
    period: str,
    out_workbook: Optional[str] = None,
    out_gstr2b: Optional[str] = None,
) -> dict:
    """Run Phase 2 reconciliation.

    Parameters
    ----------
    phase1_workbook : str
        Path to a Phase 1 output .xlsm.
    gstr2b_path : str
        Path to the consolidated GSTR-2B .xlsx register.
    period : str
        Reconciliation period (Mon'YY). Used only to stamp the
        ITC Taken Month cell and derive the default output filenames.
    out_workbook : str, optional
        Output path for the updated workbook. Defaults to the input
        workbook name with '_phase2' inserted before .xlsm.
    out_gstr2b : str, optional
        Output path for the updated GSTR-2B file. Defaults to the input
        GSTR-2B name with '_phase2_updated' inserted before .xlsx.

    Returns
    -------
    dict
        Summary counts: {
            'books_input': int,
            'gstr2b_eligible': int,
            'books_matched': int,
            'gstr2b_matched': int,
            'tiers': {tier_name: count, ...},
            'itc_recovered': float,
            'out_workbook': str,
            'out_gstr2b': str,
        }
    """
    # ---- Default output paths ----
    if out_workbook is None:
        base, ext = os.path.splitext(phase1_workbook)
        out_workbook = f"{base}_phase2{ext}"
    if out_gstr2b is None:
        base, ext = os.path.splitext(gstr2b_path)
        out_gstr2b = f"{base}_phase2_updated{ext}"

    # ---- Load ----
    books = load_unmatched_books(phase1_workbook)
    gstr2b_eligible, _gstr2b_raw = load_gstr2b(gstr2b_path)

    # If either side is empty, short-circuit with a summary that still
    # copies files through so downstream code sees consistent artifacts.
    if len(books) == 0 or len(gstr2b_eligible) == 0:
        # Copy Phase 1 workbook to out path (no changes), and copy GSTR-2B
        # verbatim.
        shutil.copy2(phase1_workbook, out_workbook)
        shutil.copy2(gstr2b_path, out_gstr2b)
        return {
            "books_input": len(books),
            "gstr2b_eligible": len(gstr2b_eligible),
            "books_matched": 0,
            "gstr2b_matched": 0,
            "tiers": {},
            "itc_recovered": 0.0,
            "out_workbook": out_workbook,
            "out_gstr2b": out_gstr2b,
        }

    # ---- Match using Phase 1's Recon engine ----
    recon = Recon(books, gstr2b_eligible).run()
    matches_df = recon.matched_df()

    # ---- Translate P2B-prefixed book_ids back to original B-prefixed IDs ----
    # The Phase 1 workbook's Unmatched - Books only tab uses 'B0000',
    # 'B0001', etc. We renamed to 'P2B0000' etc. inside Phase 2 to avoid
    # collision inside the Recon engine. To edit the workbook, we need
    # the ORIGINAL ID. Build the reverse map from the loaded books frame.
    # Original IDs live in the same relative order as the P2B IDs.
    # We reconstruct by re-reading the Unmatched tab and lining up by index.
    p2b_to_orig = {}
    _wb = load_workbook(phase1_workbook, data_only=True)
    _ws = _wb["Unmatched - Books only"]
    _hdrs = [_ws.cell(1, c).value for c in range(1, _ws.max_column + 1)]
    _bid_col = _hdrs.index("book_id") + 1
    _orig_ids = [_ws.cell(r, _bid_col).value for r in range(2, _ws.max_row + 1)
                 if _ws.cell(r, _bid_col).value not in (None, "")]
    for i, oid in enumerate(_orig_ids):
        p2b_to_orig[f"P2B{i:04d}"] = oid

    # Which ORIGINAL book_ids got matched? We look at the matched book_ids
    # in the recon output (which are the P2B-prefixed ones) and translate.
    matched_p2b_ids = set(recon.book_used)
    matched_orig_ids = {p2b_to_orig[p] for p in matched_p2b_ids if p in p2b_to_orig}

    # Which GSTR-2B source rows got matched? Recon.ims_used contains ims_ids
    # like 'G00042'. We need to map back to _gstr2b_row to write ITC Taken.
    gstr2b_by_id = gstr2b_eligible.set_index("ims_id")
    matched_source_rows = set()
    for iid in recon.ims_used:
        if iid in gstr2b_by_id.index:
            matched_source_rows.add(int(gstr2b_by_id.at[iid, "_gstr2b_row"]))

    # ---- Write Output 1: updated workbook ----
    shutil.copy2(phase1_workbook, out_workbook)
    apply_phase2_matches_to_workbook(out_workbook, matches_df, matched_orig_ids)

    # ---- Write Output 2: updated GSTR-2B ----
    itc_label = _format_itc_month(period)
    write_updated_gstr2b(gstr2b_path, out_gstr2b, matched_source_rows, itc_label)

    # ---- Summary ----
    tier_counts = matches_df.groupby("tier")["book_id"].nunique().to_dict() \
        if not matches_df.empty else {}
    itc_recovered = float(matches_df["book_total_tax"].astype(float).sum()) \
        if not matches_df.empty else 0.0

    return {
        "books_input": len(books),
        "gstr2b_eligible": len(gstr2b_eligible),
        "books_matched": len(matched_orig_ids),
        "gstr2b_matched": len(matched_source_rows),
        "tiers": tier_counts,
        "itc_recovered": itc_recovered,
        "itc_month_label": itc_label,
        "out_workbook": out_workbook,
        "out_gstr2b": out_gstr2b,
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="GST Reconciliation Phase 2")
    ap.add_argument("--phase1-workbook", required=True,
                    help="Phase 1 output .xlsm")
    ap.add_argument("--gstr2b", required=True,
                    help="GSTR-2B register .xlsx")
    ap.add_argument("--period", required=True,
                    help="Reconciliation period, e.g. May'26 (used to stamp ITC Taken Month as 'May-26')")
    ap.add_argument("--out-workbook", default=None,
                    help="Output workbook path (default: input name + '_phase2.xlsm')")
    ap.add_argument("--out-gstr2b", default=None,
                    help="Output GSTR-2B path (default: input name + '_phase2_updated.xlsx')")
    a = ap.parse_args()

    print(f"Phase 1 workbook : {a.phase1_workbook}")
    print(f"GSTR-2B register : {a.gstr2b}")
    print(f"Period           : {a.period}")

    result = run_phase2(
        phase1_workbook=a.phase1_workbook,
        gstr2b_path=a.gstr2b,
        period=a.period,
        out_workbook=a.out_workbook,
        out_gstr2b=a.out_gstr2b,
    )

    print()
    print(f"Books read from Unmatched tab : {result['books_input']}")
    print(f"GSTR-2B eligible rows         : {result['gstr2b_eligible']}")
    print(f"Books matched in Phase 2      : {result['books_matched']}")
    print(f"GSTR-2B rows stamped          : {result['gstr2b_matched']}")
    if result["tiers"]:
        print(f"By tier                       : {result['tiers']}")
    print(f"ITC recovered                 : \u20b9{result['itc_recovered']:,.2f}")
    print(f"Stamp label                   : {result.get('itc_month_label', '')}")
    print()
    print(f"Updated workbook -> {result['out_workbook']}")
    print(f"Updated GSTR-2B  -> {result['out_gstr2b']}")


if __name__ == "__main__":
    main()
