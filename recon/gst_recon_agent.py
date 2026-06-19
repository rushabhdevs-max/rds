# ============================================================
# FIXED VERSION - 2026-05-29
# Status column = tab name (not "1-EXACT")
# CF rows in master have real tax/date values
# Books-only taxable populated
# _join filters NaN
# If you see "1-EXACT" in Status column, you are running the WRONG file.
# ============================================================
"""
GST IMS (GSTR-2B) <-> Books ITC Reconciliation Agent
=====================================================

Reconciles inward-supply invoices visible in the Invoice Management System
(IMS / GSTR-2B) against purchase entries recorded in the books, for the purpose
of claiming Input Tax Credit (ITC).

Usage (auto-mode):
    python gst_recon_agent.py
Reads from ./inputs/ folder, writes to ./output/ folder.

Usage (manual):
    python gst_recon_agent.py --input-dir <dir> --out <path.xlsm> [--period "Apr'26"]

Expected naming convention (place all files in inputs/ folder):
    ims_<GSTIN>_<DDMMYYYY>_<v>.xlsx     e.g.  ims_27AAKCA4619A1ZZ_14052026_1.xlsx
    cgst_<Period>_<Entity>.xls          e.g.  cgst_Apr26_APS1.xls
    sgst_<Period>_<Entity>.xls          e.g.  sgst_Apr26_APS1.xls
    igst_<Period>_<Entity>.xls          e.g.  igst_Apr26_APS1.xls
    cf_Last_Updated_<Period>_<Entity>.xlsx           e.g.  cf_Apr26.xlsx  (optional)

The period (e.g. Apr'26) is auto-detected from the CGST / SGST / IGST
or IMS filename. The carry-forward file (cf_*) is also auto-detected.
"""

from __future__ import annotations
import argparse, glob, os, re, shutil, subprocess, tempfile, zipfile
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from rapidfuzz import fuzz

# ----------------------------- configuration ------------------------------- #

VALUE_ABS_TOL = 1.0      # rupees; tax-head difference treated as a match
VALUE_REL_TOL = 0.005    # 0.5% relative tolerance for larger amounts
FUZZY_THRESHOLD = 82     # rapidfuzz score (0-100) on normalised invoice numbers
AGG_ABS_TOL = 2.0        # tolerance when summing aggregated invoices
AGG_REL_TOL = 0.01

# ---------- auto-detection patterns (file names) ---------- #

PERIOD_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*'?\s*(\d{2})",
    re.IGNORECASE)
"""Matches period labels like Apr26, Apr'26, apr26 in filenames."""

FILE_TYPE_RE = re.compile(
    r"(?:^|[_\s])(?P<type>ims|cgst|sgst|igst|cf)(?:[_\s]|$)",
    re.IGNORECASE)
"""Matches file-type keywords in basename (word boundaries via underscore/space)."""

# --------------------------- helper functions ------------------------------ #

def norm_inv(s) -> str:
    """Normalise an invoice / voucher-ref number for comparison."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = str(s).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)   # drop slashes, dashes, spaces
    s = s.lstrip("0")                  # leading zeros are noise
    return s


def to_num(x) -> float:
    v = pd.to_numeric(x, errors="coerce")
    return 0.0 if pd.isna(v) else float(v)


def values_match(a: float, b: float, abs_tol=VALUE_ABS_TOL, rel_tol=VALUE_REL_TOL) -> bool:
    a, b = abs(a), abs(b)
    if abs(a - b) <= abs_tol:
        return True
    denom = max(a, b, 1.0)
    return abs(a - b) / denom <= rel_tol


import datetime as _dt

def _period_index(p):
    """Map a "Mon'YY" return period to a sortable integer (year*12+month)."""
    try:
        mon, yr = str(p).replace("\u2019", "'").split("'")
        m = _dt.datetime.strptime(mon.strip()[:3], "%b").month
        return (2000 + int(yr.strip())) * 12 + m
    except Exception:
        return None

def classify_period(ret, book_period):
    """same-period / prior-period / future-period relative to the books month."""
    bi, ri = _period_index(book_period), _period_index(ret)
    if bi is None or ri is None:
        return "unknown"
    if ri == bi:
        return "same-period"
    return "prior-period" if ri < bi else "future-period"


# ------------------------------ data loading ------------------------------- #

def _clean_gstin(s) -> str:
    """Canonicalise a GSTIN cell for safe equality comparison.

    Real-world books exports sometimes carry the GSTIN with hidden artefacts:
      - '_x000D_' (Excel's XML escape for a carriage return \\r)
      - trailing/leading whitespace, embedded \\r / \\n / \\t
      - lowercase letters from copy-paste sources
    Excel renders these invisibly but Python's string equality does not, so
    comparing 'books GSTIN' to 'IMS GSTIN' falsely fails. Normalise here:
    strip the XML escape, drop ALL whitespace anywhere in the string, upper.
    A clean GSTIN is exactly 15 alphanumeric characters; we don't enforce
    that (some files have padding or trailing periods) -- we only canonise.
    """
    if s is None:
        return ""
    t = str(s).replace("_x000D_", "")  # Excel XML carriage-return escape
    # remove every whitespace char (spaces, \r, \n, \t, non-breaking space)
    t = "".join(t.split())
    return t.upper()


def _clean_compact(s) -> str:
    """Same hygiene as _clean_gstin but case-preserving.

    Used for structured ID fields like voucher_no and invoice numbers, where
    'INV-001\\r\\n' should equal 'INV-001' for matching purposes, but we
    do NOT want to uppercase since the original case may matter for display
    or for invoice-prefix detection (e.g. 'FIN001' vs 'Fin001'). Strips
    '_x000D_' and every whitespace character including embedded ones.
    """
    if s is None:
        return ""
    t = str(s).replace("_x000D_", "")
    t = "".join(t.split())
    return t


def _read_any_excel(path: str, **kw) -> pd.DataFrame:
    """Read .xls/.xlsx; some 'xls' files are really xlsx (PK zip)."""
    try:
        return pd.read_excel(path, engine="openpyxl", **kw)
    except Exception:
        return pd.read_excel(path, engine="xlrd", **kw)


def find_files(input_dir: str) -> dict:
    """Auto-detect IMS, CGST, SGST, IGST and CF files by regex on basename."""
    files = {k: None for k in ("ims", "cgst", "sgst", "igst", "cf")}
    for p in glob.glob(os.path.join(input_dir, "*")):
        base = os.path.basename(p).lower()
        if not base.endswith((".xls", ".xlsx", ".xlsm")):
            continue
        m = FILE_TYPE_RE.search(base)
        if m:
            key = m.group("type").lower()
            if key in files and files[key] is None:
                files[key] = p
    return files


def detect_period_from_files(files: dict) -> str:
    """Scan detected file names for a period string (e.g. Apr'26)."""
    for key in ("cgst", "sgst", "igst", "ims", "cf"):
        path = files.get(key)
        if not path:
            continue
        m = PERIOD_RE.search(os.path.basename(path))
        if m:
            mon = m.group(1).capitalize()[:3]
            yr = m.group(2)
            return f"{mon}'{yr}"
    return ""


def load_books(cgst_path, sgst_path, igst_path) -> pd.DataFrame:
    """Build one unified books ledger keyed by GSTIN + voucher ref."""
    frames = []

    STANDARD_RATES = [5, 12, 18, 28]

    def _detect_taxable(tax_amt, is_igst=False):
        """Detect taxable from tax amount using standard GST rates (5/12/18/28%)."""
        result = np.zeros(len(tax_amt), dtype=float)
        for i, t in enumerate(tax_amt):
            if t == 0:
                continue
            best = 0.0; best_diff = 1e9
            for r in STANDARD_RATES:
                rate = r / (100.0 if is_igst else 200.0)
                if rate == 0:
                    continue
                est = round(t / rate)
                diff = abs(t - est * rate) / t
                if diff < best_diff:
                    best_diff = diff; best = float(est)
            result[i] = best if best_diff < 0.05 else t
        return result

    # CGST/SGST file (identical structure; either holds both heads). Prefer CGST.
    cs_path = cgst_path or sgst_path
    if cs_path:
        df = _read_any_excel(cs_path, header=9).dropna(how="all")
        df = df[df["GSTIN/UIN"].notna()].copy()
        cgst_abs = df["CGST Input"].apply(to_num).abs()
        sgst_abs = df["SGST Input"].apply(to_num).abs()
        gross_abs = df["Gross Total"].apply(to_num).abs()
        tax_amt = np.maximum(cgst_abs.values, sgst_abs.values)
        taxable_vals = _detect_taxable(tax_amt)
        frames.append(pd.DataFrame({
            "gstin": df["GSTIN/UIN"].apply(_clean_gstin),
            "supplier": df["Particulars"].astype(str).str.strip(),
            "voucher_no": df["Voucher No."].apply(_clean_compact),
            "ref_no": df["Voucher Ref. No."].astype(str).str.strip(),
            "date": df["Date"].astype(str),
            "gross_total": gross_abs,
            "taxable": taxable_vals,
            "cgst": cgst_abs,
            "sgst": sgst_abs,
            "igst": 0.0,
        }))

    # IGST file (separate structure).
    if igst_path:
        df = _read_any_excel(igst_path, header=9).dropna(how="all")
        df = df[df["GSTIN/UIN"].notna()].copy()
        igst_abs = df["IGST Input"].apply(to_num).abs()
        gross_abs = df["Gross Total"].apply(to_num).abs()
        taxable_vals = _detect_taxable(igst_abs.values, is_igst=True)
        frames.append(pd.DataFrame({
            "gstin": df["GSTIN/UIN"].apply(_clean_gstin),
            "supplier": df["Particulars"].astype(str).str.strip(),
            "voucher_no": df["Voucher No."].apply(_clean_compact),
            "ref_no": df["Voucher Ref. No."].astype(str).str.strip(),
            "date": df["Date"].astype(str),
            "gross_total": gross_abs,
            "taxable": taxable_vals,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": igst_abs,
        }))

    books = pd.concat(frames, ignore_index=True)
    books["ref_no"] = books["ref_no"].replace({"nan": "", "None": ""})
    books["supplier"] = books["supplier"].replace({"nan": "", "None": ""})
    books["total_tax"] = books["cgst"] + books["sgst"] + books["igst"]
    books["ref_norm"] = books["ref_no"].apply(norm_inv)
    books = books[books["total_tax"] > 0].reset_index(drop=True)
    books.insert(0, "book_id", [f"B{i:04d}" for i in range(len(books))])
    return books


def load_ims(ims_path: str) -> pd.DataFrame:
    """Load the B2B sheet of the IMS workbook (the main ITC source)."""
    raw = pd.read_excel(ims_path, sheet_name="B2B", header=[4, 5])
    raw.columns = ["gstin", "name", "inv_no", "inv_type", "inv_date", "inv_val",
                   "status", "pos", "taxable", "igst", "cgst", "sgst", "cess",
                   "remarks", "source", "ret_period", "filing"]
    raw = raw[raw["gstin"].notna()].copy()
    for c in ("igst", "cgst", "sgst", "taxable", "inv_val"):
        raw[c] = raw[c].apply(to_num)
    raw["gstin"] = raw["gstin"].apply(_clean_gstin)
    raw["inv_no"] = raw["inv_no"].astype(str).str.strip()
    raw["total_tax"] = raw["igst"] + raw["cgst"] + raw["sgst"]
    raw["inv_norm"] = raw["inv_no"].apply(norm_inv)
    raw = raw.reset_index(drop=True)
    raw.insert(0, "ims_id", [f"I{i:04d}" for i in range(len(raw))])
    return raw


# ------------------------------- matching ---------------------------------- #

@dataclass
class Recon:
    books: pd.DataFrame
    ims: pd.DataFrame
    matches: list = field(default_factory=list)   # dicts
    book_used: set = field(default_factory=set)
    ims_used: set = field(default_factory=set)

    def _record(self, brows, irows, tier, score, note=""):
        if isinstance(brows, pd.Series):
            brows = [brows]
        if isinstance(irows, pd.Series):
            irows = [irows]
        b_tax = sum(r["total_tax"] for r in brows)
        i_tax = sum(r["total_tax"] for r in irows)

        def _join(vals, n=8):
            vals = [str(v) for v in vals if str(v) not in ("", "nan", "None", "NaN")]
            if len(vals) > n:
                return " | ".join(vals[:n]) + f"  (+{len(vals)-n} more)"
            return " | ".join(vals)

        ims_gstins = sorted({str(r["gstin"]) for r in irows})
        ims_names = sorted({str(r["name"]) for r in irows if str(r["name"]) not in ("", "nan", "None")})
        self.matches.append({
            "match_source": "Engine",
            "tier": tier, "confidence": score,
            "book_id": _join([r["book_id"] for r in brows]),
            "book_gstin": brows[0]["gstin"],
            "ims_gstin": _join(ims_gstins, 3),
            "gstin_match": "Y" if (len(ims_gstins) == 1 and ims_gstins[0] == str(brows[0]["gstin"])) else "CHECK",
            "book_supplier": _join([r["supplier"] for r in brows if str(r.get("supplier","")).strip() not in ("", "nan", "None")], 3) or "",
            "ims_supplier": _join(ims_names, 3) if ims_names else "",
            "book_ref_no": _join([r["ref_no"] for r in brows]),
            "book_voucher_no": _join([r["voucher_no"] for r in brows]),
            "book_cgst": sum(r["cgst"] for r in brows),
            "book_sgst": sum(r["sgst"] for r in brows),
            "book_igst": sum(r["igst"] for r in brows), "book_total_tax": b_tax,
            "ims_id": _join([r["ims_id"] for r in irows]),
            "ims_name": irows[0]["name"],
            "ims_inv_no": _join([r["inv_no"] for r in irows]),
            "ims_status": _join(sorted({str(r["status"]) for r in irows}), 4),
            "ims_cgst": sum(r["cgst"] for r in irows),
            "ims_sgst": sum(r["sgst"] for r in irows),
            "ims_igst": sum(r["igst"] for r in irows),
            "ims_total_tax": i_tax,
            "tax_diff": round(abs(b_tax) - abs(i_tax), 2),
            "book_entry_count": len(brows),
            "ims_invoice_count": len(irows),
            "taxable_value": sum(r.get("taxable", 0) for r in brows),
            "date": brows[0].get("date", ""),
            "cgst": sum(r["cgst"] for r in brows),
            "sgst": sum(r["sgst"] for r in brows),
            "igst": sum(r["igst"] for r in brows),
            "note": note,
        })
        for r in brows:
            self.book_used.add(r["book_id"])
        for r in irows:
            self.ims_used.add(r["ims_id"])

    def run(self):
        books = self.books
        ims = self.ims
        ims_by_g = {g: d for g, d in ims.groupby("gstin")}

        # ---- Tier 1: exact GSTIN + normalised invoice + value tolerance ----
        for _, b in books.iterrows():
            if b["book_id"] in self.book_used or not b["ref_norm"]:
                continue
            cand = ims_by_g.get(b["gstin"])
            if cand is None:
                continue
            hit = cand[(cand["inv_norm"] == b["ref_norm"]) &
                       (~cand["ims_id"].isin(self.ims_used))]
            for _, ir in hit.iterrows():
                if values_match(b["total_tax"], ir["total_tax"]):
                    self._record(b, ir, "1-EXACT", 100,
                                 "GSTIN + invoice no. + tax matched")
                    break

        # ---- Tier 2: fuzzy invoice number (clerical mismatches) ----
        for _, b in books.iterrows():
            if b["book_id"] in self.book_used or not b["ref_norm"]:
                continue
            cand = ims_by_g.get(b["gstin"])
            if cand is None:
                continue
            cand = cand[~cand["ims_id"].isin(self.ims_used)]
            best, best_s = None, 0
            for _, ir in cand.iterrows():
                if not ir["inv_norm"]:
                    continue
                s = fuzz.ratio(b["ref_norm"], ir["inv_norm"])
                if s > best_s:
                    best, best_s = ir, s
            if best is not None and best_s >= FUZZY_THRESHOLD and \
                    values_match(b["total_tax"], best["total_tax"]):
                self._record(b, best, "2-FUZZY", int(best_s),
                             f"Fuzzy invoice match (score {best_s}); tax matched")

        # ---- Tier 3: value match, invoice no. differs / missing ----
        for _, b in books.iterrows():
            if b["book_id"] in self.book_used:
                continue
            cand = ims_by_g.get(b["gstin"])
            if cand is None:
                continue
            cand = cand[~cand["ims_id"].isin(self.ims_used)]
            hit = cand[cand["total_tax"].apply(lambda v: values_match(b["total_tax"], v))]
            if len(hit) == 1:
                self._record(b, hit.iloc[0], "3-VALUE", 70,
                             "GSTIN + tax value matched (invoice no. differs)")

        # ---- Tier 4: aggregated GSTIN-bucket reconciliation ----
        # For the bank / payment-gateway case the books net many small invoices
        # into one (or a few) entries (often literally "Multiple Invoices-...").
        # After line matching, compare the *remaining* book vs IMS totals per
        # GSTIN. If they reconcile, mark the whole bucket matched (many-to-many)
        # and surface any residual difference for review.
        for g, bsub in books[~books["book_id"].isin(self.book_used)].groupby("gstin"):
            isub = ims_by_g.get(g)
            if isub is None:
                continue
            isub = isub[~isub["ims_id"].isin(self.ims_used)]
            if len(isub) == 0 or len(bsub) == 0:
                continue
            # require either a genuine many-side or an explicit aggregation marker
            many = len(isub) >= 2 or len(bsub) >= 2
            marker = bsub["ref_no"].str.contains(
                r"multiple|various|aggreg|consolidat", case=False, na=False).any()
            if not (many or marker):
                continue
            if values_match(bsub["total_tax"].sum(), isub["total_tax"].sum(),
                            AGG_ABS_TOL, AGG_REL_TOL):
                self._record([r for _, r in bsub.iterrows()],
                             [r for _, r in isub.iterrows()],
                             "4-AGGREGATED", 75,
                             f"GSTIN-bucket aggregation: {len(bsub)} book entr"
                             f"{'y' if len(bsub)==1 else 'ies'} = {len(isub)} "
                             f"IMS invoices (GSTIN + total value)")

        # ---- Tier 4b: prefix-group aggregation ----
        # When global Tier 4 doesn't reconcile, the books may still aggregate
        # IMS invoices by their invoice-number letter prefix. e.g. a supplier
        # issues 'INF...' and 'SRN...' series; books carries TWO entries for
        # that GSTIN, each aggregating one series. We discover prefix groups
        # in the remaining IMS rows, sum each, and match against single
        # unmatched books rows by value alone (books ref_no need not share
        # the prefix -- catches 'Multiple Invoices-Apr26' against an IPG bucket).
        def _prefix(inv_no):
            """Letters at the start of an invoice number, stop at first digit
            or non-letter. 'MAN1604268353621' -> 'MAN', 'abcd1234' -> 'ABCD',
            '0138261395985690' -> '' (numeric-only stays in its own '' bucket)."""
            s = str(inv_no)
            out = []
            for ch in s:
                if ch.isalpha():
                    out.append(ch)
                else:
                    break
            return "".join(out).upper()

        for g, bsub in books[~books["book_id"].isin(self.book_used)].groupby("gstin"):
            isub = ims_by_g.get(g)
            if isub is None:
                continue
            isub = isub[~isub["ims_id"].isin(self.ims_used)]
            if len(isub) == 0 or len(bsub) == 0:
                continue
            # Build prefix groups inside the unmatched IMS rows under this GSTIN.
            # Numeric-only invoice numbers ('1234567') are excluded entirely --
            # we cannot meaningfully cluster them as a "sequence", and grouping
            # them under a fake '' bucket would risk false matches.
            isub = isub.assign(_pfx=isub["inv_no"].apply(_prefix))
            isub = isub[isub["_pfx"] != ""]
            if len(isub) == 0:
                continue
            # Skip if there's only one prefix group -- global Tier 4 already
            # tried that combination above and failed (otherwise we wouldn't
            # be here). Need 2+ groups to make the prefix split meaningful.
            if isub["_pfx"].nunique() < 2:
                continue

            # For each prefix group, try to find a single unmatched books row
            # whose total_tax matches the group's sum within tolerance. First
            # match wins; both sides locked so a books row cannot be matched
            # by two different prefix groups in the same pass.
            for pfx, pgrp in isub.groupby("_pfx"):
                # re-filter on each iteration: rows used by an earlier prefix
                # group in this same loop should no longer be candidates
                cands = bsub[~bsub["book_id"].isin(self.book_used)]
                if len(cands) == 0:
                    break
                pgrp = pgrp[~pgrp["ims_id"].isin(self.ims_used)]
                if len(pgrp) == 0:
                    continue
                group_tax = pgrp["total_tax"].sum()
                for _, b in cands.iterrows():
                    if values_match(b["total_tax"], group_tax,
                                    AGG_ABS_TOL, AGG_REL_TOL):
                        self._record(b,
                                     [r for _, r in pgrp.iterrows()],
                                     "4-AGGREGATED", 72,
                                     f"Prefix-group aggregation: 1 book entry "
                                     f"= {len(pgrp)} IMS invoice"
                                     f"{'s' if len(pgrp)!=1 else ''} with "
                                     f"prefix {pfx!r} (GSTIN + group value)")
                        break

        return self

    # ------------------------------ outputs -------------------------------- #
    def matched_df(self):
        return pd.DataFrame(self.matches)

    def books_unmatched(self):
        return self.books[~self.books["book_id"].isin(self.book_used)].copy()

    def ims_unmatched(self):
        return self.ims[~self.ims["ims_id"].isin(self.ims_used)].copy()


# ----------------------- carry-forward matching ---------------------------- #

CF_HEADER_ROW = 1          # 0-indexed row holding column names
CF_UTIL_COL = "ITC Utilized month"
CF_GSTIN_COL = "GSTIN "    # note trailing space in source file
CF_INV_COL = "Invoice No. as per data"


def match_carry_forward(cross_ims: pd.DataFrame, cf_path: str, util_label: str):
    """
    Match cross-period IMS invoices against PENDING rows in the carry-forward
    file, using the same GSTIN + normalised-invoice (then value) logic.

    Returns (matches_df, updated_cf_df, matched_ims_ids, header_row_values).
    Only rows currently marked 'Pending' are eligible; matched CF rows get
    their 'ITC Utilized month' set to util_label. Nothing else is altered.
    """
    cf = pd.read_excel(cf_path, header=CF_HEADER_ROW)
    cf = cf[cf[CF_GSTIN_COL].notna()].reset_index(drop=True)

    cf["_gstin"] = cf[CF_GSTIN_COL].apply(_clean_gstin)
    cf["_inv_norm"] = cf[CF_INV_COL].apply(_clean_compact).apply(norm_inv)
    for c in ("SGST Input", "CGST Input", "IGST Input"):
        if c not in cf.columns:
            cf[c] = 0.0
    cf["_tot"] = cf[["SGST Input", "CGST Input", "IGST Input"]].apply(
        lambda r: sum(to_num(x) for x in r), axis=1).abs()
    cf["_pending"] = cf[CF_UTIL_COL].astype(str).str.strip().str.lower() == "pending"

    cross = cross_ims.copy()
    cross["_gstin"] = cross["gstin"].apply(_clean_gstin)
    cf_by_g = {g: d for g, d in cf[cf["_pending"]].groupby("_gstin")}

    matches, used_cf, matched_ims = [], set(), set()

    def _commit(irow, cf_idx, kind, score):
        used_cf.add(cf_idx)
        matched_ims.add(irow["ims_id"])
        c = cf.loc[cf_idx]
        matches.append({
            "match_type": kind, "confidence": score,
            "ims_id": irow["ims_id"], "gstin": irow["_gstin"],
            "ims_supplier": irow["name"], "ims_inv_no": irow["inv_no"],
            "ims_ret_period": irow["ret_period"], "ims_total_tax": irow["total_tax"],
            "cf_row": int(cf_idx) + CF_HEADER_ROW + 2,  # 1-based sheet row
            "cf_particulars": c.get("Particulars", ""),
            "cf_inv_no": c.get(CF_INV_COL, ""), "cf_total_tax": c["_tot"],
            "cf_prev_status": c[CF_UTIL_COL], "cf_new_status": util_label,
            "tax_diff": round(abs(irow["total_tax"]) - abs(c["_tot"]), 2),
            # IMS-side fields for the All Transactions / GSTR3B Working masters
            "m_taxable": to_num(irow.get("taxable", 0)),
            "m_cgst": to_num(irow.get("cgst", 0)),
            "m_sgst": to_num(irow.get("sgst", 0)),
            "m_igst": to_num(irow.get("igst", 0)),
            "m_date": str(irow.get("inv_date", "")),
        })

    # Tier 1: GSTIN + normalised invoice + value tolerance
    for _, ir in cross.iterrows():
        cand = cf_by_g.get(ir["_gstin"])
        if cand is None or not ir["inv_norm"]:
            continue
        hit = cand[(cand["_inv_norm"] == ir["inv_norm"]) & (~cand.index.isin(used_cf))]
        for idx, c in hit.iterrows():
            if values_match(ir["total_tax"], c["_tot"]):
                _commit(ir, idx, "1-EXACT", 100)
                break

    # Tier 2: fuzzy invoice + value
    for _, ir in cross.iterrows():
        if ir["ims_id"] in matched_ims:
            continue
        cand = cf_by_g.get(ir["_gstin"])
        if cand is None or not ir["inv_norm"]:
            continue
        cand = cand[~cand.index.isin(used_cf)]
        best, bidx, bs = None, None, 0
        for idx, c in cand.iterrows():
            if not c["_inv_norm"]:
                continue
            s = fuzz.ratio(ir["inv_norm"], c["_inv_norm"])
            if s > bs:
                best, bidx, bs = c, idx, s
        if best is not None and bs >= FUZZY_THRESHOLD and \
                values_match(ir["total_tax"], best["_tot"]):
            _commit(ir, bidx, "2-FUZZY", int(bs))

    # Tier 3: value-only (unique), GSTIN bucket
    for _, ir in cross.iterrows():
        if ir["ims_id"] in matched_ims:
            continue
        cand = cf_by_g.get(ir["_gstin"])
        if cand is None:
            continue
        cand = cand[~cand.index.isin(used_cf)]
        hv = cand[cand["_tot"].apply(lambda v: values_match(ir["total_tax"], v))]
        if len(hv) == 1:
            _commit(ir, hv.index[0], "3-VALUE", 70)

    # Apply status updates to the CF frame (only matched pending rows)
    updated = cf.copy()
    for idx in used_cf:
        updated.at[idx, CF_UTIL_COL] = util_label

    matches_df = pd.DataFrame(matches)
    helper_cols = [c for c in updated.columns if c.startswith("_")]
    updated = updated.drop(columns=helper_cols)
    return matches_df, updated, matched_ims


def write_updated_cf(original_path: str, updated_df: pd.DataFrame, out_path: str,
                     util_label: str, matched_sheet_rows: set):
    """
    Surgically update the carry-forward file: change ONLY the 'ITC Utilized
    month' cell of matched rows by repointing them to a newly-appended shared
    string. Every other byte of the original workbook is preserved exactly
    (no float re-serialisation, no format loss) — important for a tax file.
    """
    import zipfile, re, shutil
    if not matched_sheet_rows:
        shutil.copy(original_path, out_path)
        return out_path

    zin = zipfile.ZipFile(original_path, "r")
    sheet = zin.read("xl/worksheets/sheet1.xml").decode("utf-8")
    ss = zin.read("xl/sharedStrings.xml").decode("utf-8")

    # locate the column letter of 'ITC Utilized month' from the header row (row 2)
    hdr_cells = dict(re.findall(r'<c r="([A-Z]+)2"[^>]*t="s"[^>]*><v>(\d+)</v></c>', sheet))
    sis = re.findall(r"<si>(.*?)</si>", ss, re.S)
    def _txt(si): return "".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))
    strvals = [_txt(s) for s in sis]
    util_col = None
    for col_letter, idx in hdr_cells.items():
        if int(idx) < len(strvals) and strvals[int(idx)].strip() == CF_UTIL_COL:
            util_col = col_letter
            break
    if util_col is None:
        util_col = "V"  # known position in this file

    # append the new shared string and get its index
    new_idx = len(sis)
    ss2 = ss.replace("</sst>", f"<si><t xml:space=\"preserve\">{util_label}</t></si></sst>")
    ss2 = re.sub(r'(<sst[^>]*\bcount=")(\d+)(")',
                 lambda m: f"{m.group(1)}{int(m.group(2))+1}{m.group(3)}", ss2, count=1)
    ss2 = re.sub(r'(<sst[^>]*\buniqueCount=")(\d+)(")',
                 lambda m: f"{m.group(1)}{int(m.group(2))+1}{m.group(3)}", ss2, count=1)

    # repoint each matched cell (e.g. V917) to new shared-string index
    for sheet_row in matched_sheet_rows:
        ref = f"{util_col}{sheet_row}"
        pat = re.compile(rf'(<c r="{ref}"[^>]*t="s"[^>]*><v>)\d+(</v></c>)')
        if pat.search(sheet):
            sheet = pat.sub(rf"\g<1>{new_idx}\g<2>", sheet, count=1)
        else:
            # cell may be inline/other type; coerce to shared-string ref
            pat2 = re.compile(rf'<c r="{ref}"[^>]*>.*?</c>')
            sheet = pat2.sub(f'<c r="{ref}" t="s"><v>{new_idx}</v></c>', sheet, count=1)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            if item == "xl/worksheets/sheet1.xml":
                zout.writestr(item, sheet)
            elif item == "xl/sharedStrings.xml":
                zout.writestr(item, ss2)
            else:
                zout.writestr(item, zin.read(item))
    zin.close()
    return out_path



# --------------------------- report generation ----------------------------- #

_FY_QUARTER = {4: "Q1", 5: "Q1", 6: "Q1", 7: "Q2", 8: "Q2", 9: "Q2",
               10: "Q3", 11: "Q3", 12: "Q3", 1: "Q4", 2: "Q4", 3: "Q4"}
_QUARTER_FILL = {"Q1": "FFC7CE", "Q2": "FFD9A8", "Q3": "FFF2A8", "Q4": "C6EFCE"}

def _quarter_of(dateval):
    """Indian fiscal quarter from an invoice date. Returns 'Q1'..'Q4' or ''."""
    try:
        d = pd.to_datetime(dateval, errors="coerce", dayfirst=True)
        if pd.isna(d):
            return ""
        return _FY_QUARTER.get(int(d.month), "")
    except Exception:
        return ""


# =================== VBA macro embedding =================================== #

MACRO_BAS = r'''Attribute VB_Name = "AutoMoveMatched"
' ===================================================================
' GST Reconciliation - Manual Match Mover
' Moves rows ticked TRUE in "Move to Matched?" from any unmatched tab
' into "Matched (Exact)", mapping each field into the correct column,
' tagging match_source = "Manual", then DELETING the row from source.
' One-time setup per file: Alt+F11 > File > Import File > this .bas.
' Run: press Alt+F8 > MoveCheckedRows > Run  (or add a button).
' ===================================================================
Option Explicit

Private Function ColIndex(ws As Worksheet, header As String) As Long
    Dim c As Long
    ColIndex = 0
    For c = 1 To 80
        If Trim(CStr(ws.Cells(1, c).Value)) = header Then ColIndex = c: Exit Function
        If Len(Trim(CStr(ws.Cells(1, c).Value))) = 0 And c > 40 Then Exit For
    Next c
End Function

Private Sub PutVal(mt As Worksheet, nr As Long, header As String, v As Variant)
    Dim c As Long: c = ColIndex(mt, header)
    If c > 0 Then mt.Cells(nr, c).Value = v
End Sub

Public Sub MoveCheckedRows()
    Dim ws As Worksheet, mt As Worksheet
    Dim chkC As Long, lastRow As Long, nr As Long, r As Long
    Dim moved As Long: moved = 0
    Dim toMove As Long: toMove = 0
    Dim isBooks As Boolean
    Set mt = ThisWorkbook.Sheets("Matched (Exact)")

    ' --- count first, then confirm (first line of defence) ---
    For Each ws In ThisWorkbook.Worksheets
        If ws.Name Like "Unmatched*" Or ws.Name Like "Cross-period*" Then
            chkC = ColIndex(ws, "Move to Matched?")
            If chkC > 0 Then
                lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
                For r = 2 To lastRow
                    If UCase(Trim(CStr(ws.Cells(r, chkC).Value))) = "TRUE" Then toMove = toMove + 1
                Next r
            End If
        End If
    Next ws
    If toMove = 0 Then
        MsgBox "No rows are ticked TRUE. Nothing to move.", vbInformation, "GST Recon"
        Exit Sub
    End If
    If MsgBox("Move " & toMove & " row(s) to 'Matched (Exact)'?" & vbCrLf & vbCrLf & _
              "This cannot be undone with Ctrl+Z, but you can reverse it later " & _
              "with MoveBackToUnmatched.", vbQuestion + vbYesNo, "Confirm move") <> vbYes Then
        Exit Sub
    End If

    Application.ScreenUpdating = False
    Application.EnableEvents = False

    For Each ws In ThisWorkbook.Worksheets
        If ws.Name Like "Unmatched*" Or ws.Name Like "Cross-period*" Then
            chkC = ColIndex(ws, "Move to Matched?")
            If chkC > 0 Then
                ' Books tab has 'book_id'; IMS tabs have 'ims_id'
                isBooks = (ColIndex(ws, "book_id") > 0)
                lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
                For r = lastRow To 2 Step -1
                    If UCase(Trim(CStr(ws.Cells(r, chkC).Value))) = "TRUE" Then
                        nr = mt.Cells(mt.Rows.Count, 1).End(xlUp).Row + 1
                        ' common
                        PutVal mt, nr, "match_source", "Manual"
                        PutVal mt, nr, "source_file", IIf(isBooks, "Books", "IMS")
                        PutVal mt, nr, "tier", "MANUAL"
                        PutVal mt, nr, "confidence", 100
                        PutVal mt, nr, "gstin_match", "Y"
                        ' unified fields the master tab links to (taxable/per-head/date)
                        PutVal mt, nr, "taxable_value", ws.Cells(r, ColIndex(ws, "taxable")).Value
                        PutVal mt, nr, "cgst", ws.Cells(r, ColIndex(ws, "cgst")).Value
                        PutVal mt, nr, "sgst", ws.Cells(r, ColIndex(ws, "sgst")).Value
                        PutVal mt, nr, "igst", ws.Cells(r, ColIndex(ws, "igst")).Value
                        If isBooks Then
                            PutVal mt, nr, "date", ws.Cells(r, ColIndex(ws, "date")).Value
                            PutVal mt, nr, "book_gstin", ws.Cells(r, ColIndex(ws, "gstin")).Value
                            PutVal mt, nr, "book_supplier", ws.Cells(r, ColIndex(ws, "supplier")).Value
                            PutVal mt, nr, "book_ref_no", ws.Cells(r, ColIndex(ws, "ref_no")).Value
                            PutVal mt, nr, "book_total_tax", ws.Cells(r, ColIndex(ws, "total_tax")).Value
                            PutVal mt, nr, "book_entry_count", 1
                        Else
                            PutVal mt, nr, "date", ws.Cells(r, ColIndex(ws, "inv_date")).Value
                            PutVal mt, nr, "book_gstin", ws.Cells(r, ColIndex(ws, "gstin")).Value
                            PutVal mt, nr, "ims_gstin", ws.Cells(r, ColIndex(ws, "gstin")).Value
                            PutVal mt, nr, "book_supplier", ws.Cells(r, ColIndex(ws, "name")).Value
                            PutVal mt, nr, "ims_supplier", ws.Cells(r, ColIndex(ws, "name")).Value
                            PutVal mt, nr, "book_ref_no", ws.Cells(r, ColIndex(ws, "inv_no")).Value
                            PutVal mt, nr, "ims_inv_no", ws.Cells(r, ColIndex(ws, "inv_no")).Value
                            PutVal mt, nr, "ims_status", ws.Cells(r, ColIndex(ws, "status")).Value
                            PutVal mt, nr, "ims_total_tax", ws.Cells(r, ColIndex(ws, "total_tax")).Value
                            PutVal mt, nr, "book_total_tax", ws.Cells(r, ColIndex(ws, "total_tax")).Value
                            PutVal mt, nr, "ims_invoice_count", 1
                        End If
                        ' store a machine-parseable origin tag so reversal is automatic
                        PutVal mt, nr, "note", "Manual confirmed | origin=[" & ws.Name & "]"
                        ws.Rows(r).Delete
                        moved = moved + 1
                    End If
                Next r
            End If
        End If
    Next ws

    Application.EnableEvents = True
    Application.ScreenUpdating = True
    RebuildMaster
    MsgBox moved & " row(s) moved to 'Matched (Exact)' as Manual matches.", vbInformation, "GST Recon"
End Sub

' ===================================================================
' Reverse a mistaken manual move. Select any cell(s) on the rows you
' want to send back in 'Matched (Exact)', then run this. Only rows with
' match_source = "Manual" are reversible; each is auto-routed back to its
' origin tab (read from the note's origin=[...] tag). Engine matches are
' protected and will be skipped.
' ===================================================================
Public Sub MoveBackToUnmatched()
    Dim mt As Worksheet: Set mt = ThisWorkbook.Sheets("Matched (Exact)")
    If ActiveSheet.Name <> mt.Name Then
        MsgBox "Go to the 'Matched (Exact)' tab, select the row(s) to reverse, then run this.", _
               vbExclamation, "GST Recon": Exit Sub
    End If

    Dim srcC As Long: srcC = ColIndex(mt, "match_source")
    Dim noteC As Long: noteC = ColIndex(mt, "note")
    Dim sel As Range, rowsHit As Object
    Set rowsHit = CreateObject("Scripting.Dictionary")
    For Each sel In Selection.Cells
        If sel.Row > 1 Then rowsHit(sel.Row) = True
    Next sel
    If rowsHit.Count = 0 Then
        MsgBox "Select at least one data row to reverse.", vbExclamation, "GST Recon": Exit Sub
    End If

    ' collect target rows, validate they are Manual
    Dim rowsArr() As Long, n As Long: n = 0
    ReDim rowsArr(1 To rowsHit.Count)
    Dim k As Variant, skipped As Long: skipped = 0
    For Each k In rowsHit.Keys
        If Trim(CStr(mt.Cells(CLng(k), srcC).Value)) = "Manual" Then
            n = n + 1: rowsArr(n) = CLng(k)
        Else
            skipped = skipped + 1
        End If
    Next k
    If n = 0 Then
        MsgBox "None of the selected rows are Manual matches. Engine matches are protected.", _
               vbExclamation, "GST Recon": Exit Sub
    End If
    If MsgBox("Send " & n & " row(s) back to their origin unmatched tab?" & _
              IIf(skipped > 0, vbCrLf & skipped & " engine match(es) will be skipped.", ""), _
              vbQuestion + vbYesNo, "Confirm reverse") <> vbYes Then Exit Sub

    ' sort descending so deletes don't shift pending rows
    Dim i As Long, j As Long, t As Long
    For i = 1 To n - 1
        For j = i + 1 To n
            If rowsArr(j) > rowsArr(i) Then t = rowsArr(i): rowsArr(i) = rowsArr(j): rowsArr(j) = t
        Next j
    Next i

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Dim done As Long: done = 0
    For i = 1 To n
        Dim rr As Long: rr = rowsArr(i)
        Dim note As String: note = CStr(mt.Cells(rr, noteC).Value)
        Dim origin As String: origin = ""
        Dim p1 As Long, p2 As Long
        p1 = InStr(note, "origin=[")
        If p1 > 0 Then
            p2 = InStr(p1, note, "]")
            If p2 > p1 Then origin = Mid(note, p1 + 8, p2 - (p1 + 8))
        End If
        If origin = "" Then
            MsgBox "Row " & rr & " has no origin tag; skipping. Move it back manually.", vbExclamation
        ElseIf Not WorksheetExists(origin) Then
            MsgBox "Origin tab '" & origin & "' not found for row " & rr & "; skipping.", vbExclamation
        Else
            Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(origin)
            Dim chkC As Long: chkC = ColIndex(ws, "Move to Matched?")
            Dim isBooks As Boolean: isBooks = (ColIndex(ws, "book_id") > 0)
            ' find next free row using the GSTIN column (always populated), not col 1,
            ' because the id column (book_id/ims_id) is not written on reverse
            Dim gcol As Long: gcol = ColIndex(ws, "gstin")
            Dim nr As Long: nr = ws.Cells(ws.Rows.Count, gcol).End(xlUp).Row + 1
            If nr < 2 Then nr = 2
            ' put a marker in the id column (col 1) so row-counts that scan col 1 see it
            If isBooks Then
                ws.Cells(nr, ColIndex(ws, "book_id")).Value = "MANUAL"
            Else
                ws.Cells(nr, ColIndex(ws, "ims_id")).Value = "MANUAL"
            End If
            If isBooks Then
                ws.Cells(nr, ColIndex(ws, "gstin")).Value = mt.Cells(rr, ColIndex(mt, "book_gstin")).Value
                ws.Cells(nr, ColIndex(ws, "supplier")).Value = mt.Cells(rr, ColIndex(mt, "book_supplier")).Value
                ws.Cells(nr, ColIndex(ws, "ref_no")).Value = mt.Cells(rr, ColIndex(mt, "book_ref_no")).Value
                ws.Cells(nr, ColIndex(ws, "total_tax")).Value = mt.Cells(rr, ColIndex(mt, "book_total_tax")).Value
                ws.Cells(nr, ColIndex(ws, "date")).Value = mt.Cells(rr, ColIndex(mt, "date")).Value
            Else
                ws.Cells(nr, ColIndex(ws, "gstin")).Value = mt.Cells(rr, ColIndex(mt, "ims_gstin")).Value
                ws.Cells(nr, ColIndex(ws, "name")).Value = mt.Cells(rr, ColIndex(mt, "ims_supplier")).Value
                ws.Cells(nr, ColIndex(ws, "inv_no")).Value = mt.Cells(rr, ColIndex(mt, "ims_inv_no")).Value
                ws.Cells(nr, ColIndex(ws, "status")).Value = mt.Cells(rr, ColIndex(mt, "ims_status")).Value
                ws.Cells(nr, ColIndex(ws, "total_tax")).Value = mt.Cells(rr, ColIndex(mt, "ims_total_tax")).Value
                ws.Cells(nr, ColIndex(ws, "inv_date")).Value = mt.Cells(rr, ColIndex(mt, "date")).Value
            End If
            ' carry taxable + per-head back so the master link resolves
            ws.Cells(nr, ColIndex(ws, "taxable")).Value = mt.Cells(rr, ColIndex(mt, "taxable_value")).Value
            ws.Cells(nr, ColIndex(ws, "cgst")).Value = mt.Cells(rr, ColIndex(mt, "cgst")).Value
            ws.Cells(nr, ColIndex(ws, "sgst")).Value = mt.Cells(rr, ColIndex(mt, "sgst")).Value
            ws.Cells(nr, ColIndex(ws, "igst")).Value = mt.Cells(rr, ColIndex(mt, "igst")).Value
            ' tag this restored row as a manual entry; source_file matches the tab type
            If ColIndex(ws, "match_source") > 0 Then ws.Cells(nr, ColIndex(ws, "match_source")).Value = "Manual"
            If ColIndex(ws, "source_file") > 0 Then ws.Cells(nr, ColIndex(ws, "source_file")).Value = IIf(isBooks, "Books", "IMS")
            If chkC > 0 Then ws.Cells(nr, chkC).Value = "FALSE"
            mt.Rows(rr).Delete
            done = done + 1
        End If
    Next i

    Application.EnableEvents = True
    Application.ScreenUpdating = True
    RebuildMaster
    MsgBox done & " row(s) sent back to their origin tab(s).", vbInformation, "GST Recon"
End Sub

Private Function WorksheetExists(nm As String) As Boolean
    Dim w As Worksheet
    On Error Resume Next
    Set w = ThisWorkbook.Sheets(nm)
    WorksheetExists = Not w Is Nothing
    On Error GoTo 0
End Function

' ===================================================================
' Rebuild both consolidated tabs (live-linked) after any move/reverse.
' 'All Transactions' includes all 6 source tabs; 'GSTR3B Working'
' includes only the matched-side tabs (GSTR-3B filing set).
' ===================================================================
Private Function HdrCol(ws As Worksheet, header As String) As Long
    Dim c As Long
    HdrCol = 0
    For c = 1 To 90
        If Trim(CStr(ws.Cells(1, c).Value)) = header Then HdrCol = c: Exit Function
    Next c
End Function

Public Sub RebuildMaster()
    RebuildOneMaster "All Transactions", True
    RebuildOneMaster "GSTR3B Working", False
End Sub

' includeAll = True  -> all six source tabs (full ledger)
' includeAll = False -> only the three matched-side tabs (GSTR3B working set)
Private Sub RebuildOneMaster(masterName As String, includeAll As Boolean)
    If Not WorksheetExists(masterName) Then Exit Sub
    Dim mw As Worksheet: Set mw = ThisWorkbook.Sheets(masterName)

    Application.ScreenUpdating = False
    Application.EnableEvents = False

    ' clear existing data rows (keep title row1 + header row3); 11 cols now
    Dim lastr As Long: lastr = mw.Cells(mw.Rows.Count, 9).End(xlUp).Row
    If lastr >= 4 Then mw.Range("A4:K" & lastr).Clear

    ' source tabs included
    Dim n As Long, names() As String
    If includeAll Then
        n = 6
        ReDim names(1 To 6)
        names(1) = "Matched (Exact)": names(2) = "Review (Fuzzy+Agg)"
        names(3) = "Carry-Forward Matches": names(4) = "Unmatched - Books only"
        names(5) = "Unmatched IMS (same period)": names(6) = "Cross-period IMS (timing)"
    Else
        n = 3
        ReDim names(1 To 3)
        names(1) = "Matched (Exact)": names(2) = "Review (Fuzzy+Agg)"
        names(3) = "Carry-Forward Matches"
    End If

    Dim outR As Long: outR = 4
    Dim k As Long
    For k = 1 To n
        If WorksheetExists(names(k)) Then
            Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(names(k))
            Dim supC$, gstC$, invC$, taxC$, cgC$, sgC$, igC$, dtC$
            Select Case names(k)
                Case "Matched (Exact)", "Review (Fuzzy+Agg)"
                    supC = "book_supplier": gstC = "book_gstin": invC = "book_ref_no"
                    taxC = "taxable_value": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "date"
                Case "Carry-Forward Matches"
                    supC = "ims_supplier": gstC = "gstin": invC = "ims_inv_no"
                    taxC = "taxable_value": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "date"
                Case "Unmatched - Books only"
                    supC = "supplier": gstC = "gstin": invC = "ref_no"
                    taxC = "taxable": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "date"
                Case Else  ' IMS unmatched / cross-period
                    supC = "name": gstC = "gstin": invC = "inv_no"
                    taxC = "taxable": cgC = "cgst": sgC = "sgst": igC = "igst": dtC = "inv_date"
            End Select

            Dim cS&, cG&, cI&, cT&, cC&, cSg&, cIg&, cD&, cMS&, cSF&
            cS = HdrCol(ws, supC): cG = HdrCol(ws, gstC): cI = HdrCol(ws, invC)
            cT = HdrCol(ws, taxC): cC = HdrCol(ws, cgC): cSg = HdrCol(ws, sgC)
            cIg = HdrCol(ws, igC): cD = HdrCol(ws, dtC)
            cMS = HdrCol(ws, "match_source"): cSF = HdrCol(ws, "source_file")

            ' count by GSTIN col (always populated); manually-restored rows safe
            Dim lr As Long: lr = ws.Cells(ws.Rows.Count, cG).End(xlUp).Row
            Dim r As Long
            For r = 2 To lr
                If Len(Trim(CStr(ws.Cells(r, cG).Value))) > 0 Then
                    Dim q$: q = "'" & Replace(names(k), "'", "''") & "'!"
                    If cS > 0 Then mw.Cells(outR, 1).Formula = "=" & q & ws.Cells(r, cS).Address(False, False)
                    If cG > 0 Then mw.Cells(outR, 2).Formula = "=" & q & ws.Cells(r, cG).Address(False, False)
                    If cI > 0 Then mw.Cells(outR, 3).Formula = "=" & q & ws.Cells(r, cI).Address(False, False)
                    If cT > 0 Then mw.Cells(outR, 4).Formula = "=" & q & ws.Cells(r, cT).Address(False, False)
                    If cC > 0 Then mw.Cells(outR, 5).Formula = "=" & q & ws.Cells(r, cC).Address(False, False)
                    If cSg > 0 Then mw.Cells(outR, 6).Formula = "=" & q & ws.Cells(r, cSg).Address(False, False)
                    If cIg > 0 Then mw.Cells(outR, 7).Formula = "=" & q & ws.Cells(r, cIg).Address(False, False)
                    If cD > 0 Then mw.Cells(outR, 8).Formula = "=" & q & ws.Cells(r, cD).Address(False, False)
                    mw.Cells(outR, 9).Value = names(k)
                    ' Origin (col 10) -> live link to match_source if available
                    If cMS > 0 Then
                        mw.Cells(outR, 10).Formula = "=" & q & ws.Cells(r, cMS).Address(False, False)
                    Else
                        mw.Cells(outR, 10).Value = "Engine"
                    End If
                    ' Source File (col 11) -> live link to source_file if available
                    If cSF > 0 Then
                        mw.Cells(outR, 11).Formula = "=" & q & ws.Cells(r, cSF).Address(False, False)
                    Else
                        ' fall back to a constant inferred from the tab type
                        Select Case names(k)
                            Case "Matched (Exact)", "Review (Fuzzy+Agg)", "Unmatched - Books only"
                                mw.Cells(outR, 11).Value = "Books"
                            Case Else
                                mw.Cells(outR, 11).Value = "IMS"
                        End Select
                    End If
                    outR = outR + 1
                End If
            Next r
        End If
    Next k

    Application.EnableEvents = True
    Application.ScreenUpdating = True
End Sub
'''


def _to_xlsm(xlsx_path: str) -> str:
    """Repackage .xlsx as .xlsm by patching the content-type."""
    xlsm_path = os.path.splitext(xlsx_path)[0] + ".xlsm"
    shutil.copy(xlsx_path, xlsm_path)
    tmp = xlsm_path + ".tmp"
    with zipfile.ZipFile(xlsm_path, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item == "[Content_Types].xml":
                data = data.replace(
                    b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                    b"application/vnd.ms-excel.sheet.macroEnabled.main+xml")
            zout.writestr(item, data)
    os.replace(tmp, xlsm_path)
    return xlsm_path


def _embed_via_excel(xlsm_path: str, bas_path: str) -> bool:
    """Use PowerShell + Excel COM to import a .bas macro into the .xlsm.

    Temporarily enables 'Trust access to VBA project object model' via
    registry if needed, then restores the original value.
    """
    ps_script = f'''
$regPath = "HKCU:\\Software\\Microsoft\\Office\\16.0\\Excel\\Security"
$regName = "AccessVBOM"
$orig = $null
if (Test-Path $regPath) {{
    $orig = Get-ItemProperty -Path $regPath -Name $regName -ErrorAction SilentlyContinue
    $orig = if ($orig) {{ $orig.$regName }} else {{ $null }}
}}
if ($orig -ne 1) {{
    Set-ItemProperty -Path $regPath -Name $regName -Value 1 -Type DWord -Force
}}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {{
    $wb = $excel.Workbooks.Open("{xlsm_path}")
    $vbp = $wb.VBProject
    if ($vbp -eq $null) {{ throw "VBProject is null - VBA trust may still be blocked" }}
    $vbp.VBComponents.Import("{bas_path}")
    $wb.Save()
    Write-Output "EMBED_SUCCESS"
}} catch {{
    Write-Output "FAIL:$($_.Exception.Message)"
}} finally {{
    if ($wb) {{ $wb.Close($false) }}
    $excel.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
    if ($orig -ne 1) {{
        if ($orig -ne $null) {{ Set-ItemProperty -Path $regPath -Name $regName -Value $orig -Type DWord -Force }}
        else {{ Remove-ItemProperty -Path $regPath -Name $regName -ErrorAction SilentlyContinue }}
    }}
}}
'''
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=120)
        out = r.stdout.strip()
        if "EMBED_SUCCESS" in out:
            return True
        print(f"  [warning] Excel COM import failed: {out}")
        return False
    except Exception as e:
        print(f"  [warning] Could not launch PowerShell: {e}")
        return False


def embed_macro(xlsx_path: str, macro_source: str = MACRO_BAS,
                xlsm_path: str = None) -> str:
    """Convert .xlsx to .xlsm and embed VBA macro.

    Args:
        xlsx_path: Path to the openpyxl-saved .xlsx (will be removed on success).
        macro_source: VBA source code string.
        xlsm_path: Desired final .xlsm path (default: derived from xlsx_path).

    Returns the path to the final .xlsm.
    """
    if not xlsm_path:
        xlsm_path = os.path.splitext(xlsx_path)[0] + ".xlsm"

    # Convert .xlsx -> .xlsm via zipfile content-type patching
    shutil.copy(xlsx_path, xlsm_path)
    tmp = xlsm_path + ".tmp"
    with zipfile.ZipFile(xlsm_path, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item == "[Content_Types].xml":
                data = data.replace(
                    b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                    b"application/vnd.ms-excel.sheet.macroEnabled.main+xml")
            zout.writestr(item, data)
    os.replace(tmp, xlsm_path)

    bas_dir = os.path.dirname(xlsm_path) or "."
    bas_path = os.path.join(bas_dir, "AutoMoveMatched.bas")

    with open(bas_path, "w") as f:
        f.write(macro_source)

    ok = _embed_via_excel(xlsm_path, bas_path)
    if ok:
        os.remove(bas_path)
        print(f"Macro embedded in: {xlsm_path}")
    else:
        print(f"  [info] Macro file: {bas_path} (import via Alt+F11 -> Import File)")
    os.remove(xlsx_path)
    return xlsm_path


GSTR3B_TEMPLATE_B64 = (
    "UEsDBBQABgAIAAAAIQCYiRhLogEAABoHAAATAAgCW0NvbnRlbnRfVHlwZXNdLnhtbCCiBAIooAAC"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACs"
    "lcFOwzAMhu9IvEOVK1ozOCCE1nHY4IQACXgAk3hrtDSJ4jC2t8cNDE1oWzXopVGb+P/+uLEzulk1"
    "tlhiJONdJc7LoSjQKa+Nm1fi9eVucCUKSuA0WO+wEmskcTM+PRm9rANSwdGOKlGnFK6lJFVjA1T6"
    "gI5nZj42kPg1zmUAtYA5yovh8FIq7xK6NEithhiPpjiDd5uK2xV//nIS0ZIoJl8LW1YlIARrFCR2"
    "KpdO/6IMvgklR+Y1VJtAZ2xDyJ2EJc8cBfCzmVGovXpv2HzJ8dMIH5yoPYAWvR/wbeyRcx+NxuIJ"
    "YnqAhvcpV1Z++Lh4835RHhbZkYZfLilEBE01YmpsmceyAeM2iTnAz4tJ5uG8ZyPt/rJwhw/kExEd"
    "2HvjFiS33/p2tK39Z1MXPafpCFOJSw9lfv4/NVmmIwuU1hap7wOaRbvINUTUzyly7fVuYFu7w4fy"
    "TdsJqO+juNHtwoNVk5prued/oDa6h/jcBp+iD8S9POLxBjbNuo0eBBbCmAz+tOtdXemHyPfAv3fc"
    "FpbTqHewZb7Zxp8AAAD//wMAUEsDBBQABgAIAAAAIQC1VTAj9AAAAEwCAAALAAgCX3JlbHMvLnJl"
    "bHMgogQCKKAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAArJJNT8MwDIbvSPyHyPfV3ZAQQkt3QUi7IVR+gEncD7WNoyQb3b8nHBBUGoMDR3+9"
    "fvzK2908jerIIfbiNKyLEhQ7I7Z3rYaX+nF1ByomcpZGcazhxBF21fXV9plHSnkodr2PKqu4qKFL"
    "yd8jRtPxRLEQzy5XGgkTpRyGFj2ZgVrGTVneYviuAdVCU+2thrC3N6Dqk8+bf9eWpukNP4g5TOzS"
    "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"
    "AAAhAHMtshBHAwAAzgwAACIAAAAAAAAAAAAAAAAAEUgAAHhsL2V4dGVybmFsTGlua3MvZXh0ZXJu"
    "YWxMaW5rMS54bWxQSwECLQAUAAYACAAAACEAziWfXQIDAABWCQAAIgAAAAAAAAAAAAAAAACYSwAA"
    "eGwvZXh0ZXJuYWxMaW5rcy9leHRlcm5hbExpbmsyLnhtbFBLAQItABQABgAIAAAAIQDc5AdO9AEA"
    "AI0EAAAQAAAAAAAAAAAAAAAAANpOAAB4bC9jb21tZW50czEueG1sUEsBAi0AFAAGAAgAAAAhAILn"
    "d9h7AQAAfgUAABAAAAAAAAAAAAAAAAAA/FAAAHhsL2NhbGNDaGFpbi54bWxQSwECLQAUAAYACAAA"
    "ACEAS5iObEsBAABnAgAAEQAAAAAAAAAAAAAAAAClUgAAZG9jUHJvcHMvY29yZS54bWxQSwECLQAU"
    "AAYACAAAACEAYUkJEIkBAAARAwAAEAAAAAAAAAAAAAAAAAAnVQAAZG9jUHJvcHMvYXBwLnhtbFBL"
    "AQItABQABgAIAAAAIQClM0AjQwEAAPUCAAAtAAAAAAAAAAAAAAAAAOZXAAB4bC9leHRlcm5hbExp"
    "bmtzL19yZWxzL2V4dGVybmFsTGluazEueG1sLnJlbHNQSwECLQAUAAYACAAAACEA4J7nPhwBAABe"
    "AgAALQAAAAAAAAAAAAAAAAB0WQAAeGwvZXh0ZXJuYWxMaW5rcy9fcmVscy9leHRlcm5hbExpbmsy"
    "LnhtbC5yZWxzUEsFBgAAAAASABIA7AQAANtaAAAAAA=="
)


def _add_gstr3b_summary_tab(wb, period, gstr3b_data_rows, outward_summary_path=None):
    """Insert the GSTR-3B form summary as the FIRST tab of `wb`.

    The template is loaded from an embedded blob (no external file needed at
    runtime). It already carries all internal formulas (SUM, ROUND, %, cross-
    row references); we only populate two pieces of data:

      Row 15 (Section 3.1(a) Outward taxable supplies)
        Taxable -> D15, IGST -> G15, CGST -> J15, SGST -> M15
        Sourced from the user-provided outward-revenue xlsx via a hidden
        "Outward Source" tab embedded into THIS workbook (so the link is
        internal and survives moving the file around).

      Row 43 (Section 4 ITC > (5) All other ITC)
        IGST -> D43, CGST -> H43, SGST -> L43
        SUM formulas over the GSTR3B Working tab in this workbook.

    Period parameter (e.g. "Mar'26") is used to set Year (Q5), Month (Q6) and
    update the "as on Mar-26" label in row 59. All broken external workbook
    references in the template are replaced with 0 so dependent formulas
    still compute cleanly.
    """
    import base64, io, datetime as _dt
    from openpyxl import load_workbook as _lwb
    from openpyxl.styles import Font
    from copy import copy as _copy

    # --- 1. load embedded template into a separate workbook ---
    tpl_bytes = base64.b64decode(GSTR3B_TEMPLATE_B64)
    tpl_wb = _lwb(io.BytesIO(tpl_bytes))
    tpl_ws = tpl_wb[tpl_wb.sheetnames[0]]

    # --- 2. resolve period -> year, month-date, "Mon-YY" label ---
    MON = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
           "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    year_val, month_dt, mon_yy_label = 2026, _dt.datetime(2026,3,1), "Mar-26"
    if period:
        # accept "Mar'26", "Mar-26", "Mar 26", "Mar2026", etc.
        m = re.match(r"\s*([A-Za-z]{3})[\s'\-]?(\d{2,4})", period)
        if m:
            mon3, yr = m.group(1).title()[:3], m.group(2)
            if mon3 in MON:
                y = int(yr) + (2000 if len(yr) == 2 else 0)
                year_val = y
                month_dt = _dt.datetime(y, MON[mon3], 1)
                mon_yy_label = f"{mon3}-{str(y)[-2:]}"

    # --- 3. create new first sheet in target workbook ---
    ws_name = "Summary GSTR-3B"
    if ws_name in wb.sheetnames:
        del wb[ws_name]
    ws = wb.create_sheet(ws_name, index=0)
    ws.sheet_view.showGridLines = False

    # --- 4. copy every cell from template (value/formula + style) ---
    # Strip broken external references; cells that have them get a 0.
    EXTREF_PAT = re.compile(r"^=.*\[\d+\].*!")
    for row in tpl_ws.iter_rows():
        for cell in row:
            if cell.value is None and not cell.has_style:
                continue
            new = ws.cell(row=cell.row, column=cell.column)
            v = cell.value
            if isinstance(v, str) and EXTREF_PAT.match(v):
                v = 0  # remove broken external workbook link
            new.value = v
            if cell.has_style:
                new.font = _copy(cell.font)
                new.fill = _copy(cell.fill)
                new.border = _copy(cell.border)
                new.alignment = _copy(cell.alignment)
                new.number_format = cell.number_format
                new.protection = _copy(cell.protection)
    # copy column widths and merged ranges
    for col, dim in tpl_ws.column_dimensions.items():
        ws.column_dimensions[col].width = dim.width
    for rng in tpl_ws.merged_cells.ranges:
        ws.merge_cells(str(rng))
    for rd, dim in tpl_ws.row_dimensions.items():
        if dim.height:
            ws.row_dimensions[rd].height = dim.height

    # --- 5. write period-derived fields ---
    ws.cell(row=5, column=17, value=year_val)   # Q5 Year
    ws.cell(row=6, column=17, value=month_dt)   # Q6 Month
    ws.cell(row=6, column=17).number_format = "mmm-yy"
    ws.cell(row=59, column=4, value=f"ITC Available in Credit Ledger as on {mon_yy_label}")

    # --- 6. embed outward-supplies SUMMARY into a hidden helper tab ---
    if outward_summary_path and os.path.exists(outward_summary_path):
        try:
            src_wb = _lwb(outward_summary_path, data_only=True)
            src_ws = src_wb[src_wb.sheetnames[0]]  # 'SUMMARY' in the example
            helper = wb.create_sheet("Outward Source")
            helper.sheet_state = "hidden"
            for r in range(1, src_ws.max_row + 1):
                for c in range(1, src_ws.max_column + 1):
                    helper.cell(row=r, column=c, value=src_ws.cell(r, c).value)
            # Section 3.1(a) outward taxable supplies - row 15
            # Source row in Outward Source = TOTAL row (24 in the sample); we
            # locate it dynamically by matching "TOTAL" in column A.
            total_r = None
            for r in range(1, helper.max_row + 1):
                v = helper.cell(r, 1).value
                if isinstance(v, str) and v.strip().upper() == "TOTAL":
                    total_r = r
                    break
            if total_r:
                # Column mapping in the outward summary file:
                #   col B = Total Taxable, E = IGST Output, F = CGST Output, G = SGST Output
                ws.cell(row=15, column=4,  value=f"='Outward Source'!B{total_r}")  # Taxable
                ws.cell(row=15, column=7,  value=f"='Outward Source'!E{total_r}")  # IGST
                ws.cell(row=15, column=10, value=f"='Outward Source'!F{total_r}")  # CGST
                ws.cell(row=15, column=13, value=f"='Outward Source'!G{total_r}")  # SGST
        except Exception as e:
            print(f"  [warning] Could not embed outward summary: {e}")

    # --- 7. ITC inputs from GSTR3B Working tab (row 43) ---
    # GSTR3B Working columns: D=Taxable, E=CGST, F=SGST, G=IGST. Header row=1.
    # We don't know the last data row at this point (sheet not yet built), so
    # use an open-ended range that will sum however many rows end up there.
    g3 = "'GSTR3B Working'"
    ws.cell(row=43, column=4,  value=f"=SUM({g3}!G2:G10000)")   # IGST
    ws.cell(row=43, column=8,  value=f"=SUM({g3}!E2:E10000)")   # CGST
    ws.cell(row=43, column=12, value=f"=SUM({g3}!F2:F10000)")   # SGST
    # Note: template has no taxable-value cell in row 43 (ITC table is by tax
    # head only, per GSTR-3B form structure). If you also want the taxable
    # base shown, it can be added in a new column.

    # ------------------------------------------------------------------
    # Section 6.1 - Payment of Tax: live ITC waterfall with per-head 1% cash floor
    # ------------------------------------------------------------------
    # Rules implemented (per user spec):
    #   - Each ITC pool first fully extinguishes its OWN liability.
    #   - Then cross-utilization in order:
    #       IGST liab : IGST -> CGST -> SGST
    #       CGST liab : CGST -> IGST
    #       SGST liab : SGST -> IGST
    #   - Mandatory 1% cash floor applies INDEPENDENTLY to EACH HEAD
    #     (IGST, CGST, SGST). At most 99% of each head's liability can be
    #     paid via ITC; the other >=1% must be in cash. This applies always
    #     -- even when natural cash is already > 1%, no adjustment needed;
    #     when natural cash < 1%, ITC application is scaled back so cash
    #     hits exactly 1% of that head's liability.
    #   - When scaling back a head's ITC, cross-applied ITC is reduced
    #     first (to preserve own-type ITC), then own-type ITC if needed.
    #   - RCM rows (65, 68, 71) intentionally left untouched per spec.
    #
    # Working values live on hidden helper row 77 with labels in col C.
    # Direct cells (F/H/J in rows 64/67/70) reference these helpers.
    # ------------------------------------------------------------------
    ws.row_dimensions[77].hidden = True
    helper_labels = [
        (3,  "WATERFALL HELPERS"),
        (4,  "T (total liab)"),
        (5,  "(unused)"),
        (6,  "o_i (IGST own offset)"),
        (7,  "o_c (CGST own offset)"),
        (8,  "o_s (SGST own offset)"),
        (9,  "c_to_i (CGST->IGST)"),
        (10, "s_to_i (SGST->IGST)"),
        (11, "i_to_c (IGST->CGST)"),
        (12, "i_to_s (IGST->SGST)"),
        (13, "max ITC IGST head (99%)"),
        (14, "max ITC CGST head (99%)"),
        (15, "max ITC SGST head (99%)"),
        (16, "trim_i (excess to remove)"),
        (17, "trim_c"),
        (18, "trim_s"),
    ]
    for c, lbl in helper_labels:
        ws.cell(row=76, column=c, value=lbl).font = Font(name="Arial", italic=True,
                                                          size=8, color="888888")

    # Helper formulas at row 77 (hidden)
    H = {
        "D": "=D64+D67+D70",                                       # T
        # natural waterfall (no 1% rule):
        "F": "=MIN(D64,D47)",                                      # o_i
        "G": "=MIN(D67,H47)",                                      # o_c
        "H": "=MIN(D70,L47)",                                      # o_s
        "I": "=MIN(D64-F77, H47-G77)",                             # c_to_i
        "J": "=MIN(D64-F77-I77, L47-H77)",                         # s_to_i
        "K": "=MIN(D67-G77, D47-F77)",                             # i_to_c
        "L": "=MIN(D70-H77, D47-F77-K77)",                         # i_to_s
        # per-head 99% caps
        "M": "=0.99*D64",                                          # max ITC against IGST liab
        "N": "=0.99*D67",                                          # max ITC against CGST liab
        "O": "=0.99*D70",                                          # max ITC against SGST liab
        # excess ITC to trim per head (= natural ITC total - 99% cap, floored at 0)
        "P": "=MAX(0, (F77+I77+J77) - M77)",                       # trim_i
        "Q": "=MAX(0, (G77+K77) - N77)",                           # trim_c (no SGST on CGST)
        "R": "=MAX(0, (H77+L77) - O77)",                           # trim_s (no CGST on SGST)
    }
    for col_letter, formula in H.items():
        col = ord(col_letter) - 64
        ws.cell(row=77, column=col, value=formula).font = Font(name="Arial",
                                                                size=8, color="888888")

    # ---- Row 64: IGST liability ----
    # Trim order: s_to_i first (J64), then c_to_i (H64), then o_i (F64).
    # red_j = MIN(s_to_i, trim_i)
    # red_h = MIN(c_to_i, trim_i - red_j)
    # red_f = trim_i - red_j - red_h
    ws.cell(row=64, column=6,
            value="=F77-MAX(0, P77-MIN(J77,P77)-MIN(I77, P77-MIN(J77,P77)))")   # F64
    ws.cell(row=64, column=8,
            value="=I77-MIN(I77, P77-MIN(J77,P77))")                            # H64
    ws.cell(row=64, column=10,
            value="=J77-MIN(J77,P77)")                                          # J64

    # ---- Row 67: CGST liability ----
    # Trim order: i_to_c (F67) first, then o_c (H67).
    # red_f67 = MIN(i_to_c, trim_c)
    # red_h67 = trim_c - red_f67
    ws.cell(row=67, column=6,
            value="=K77-MIN(K77, Q77)")                                         # F67
    ws.cell(row=67, column=8,
            value="=G77-MAX(0, Q77-MIN(K77,Q77))")                              # H67
    ws.cell(row=67, column=10, value=0)                                         # J67

    # ---- Row 70: SGST liability ----
    # Trim order: i_to_s (F70) first, then o_s (J70).
    # red_f70 = MIN(i_to_s, trim_s)
    # red_j70 = trim_s - red_f70
    ws.cell(row=70, column=6,
            value="=L77-MIN(L77, R77)")                                         # F70
    ws.cell(row=70, column=8,  value=0)                                         # H70
    ws.cell(row=70, column=10,
            value="=H77-MAX(0, R77-MIN(L77,R77))")                              # J70




def build_report(recon: Recon, xlsm_path: str, period: str = "",
                 cf_matches: pd.DataFrame = None, cf_matched_ims: set = None,
                 outward_summary_path: str = None):
    """Build the report workbook, save as macro-enabled .xlsm."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    # Save openpyxl content to a temp .xlsx first, then convert to final .xlsm
    xlsm_path = os.path.abspath(xlsm_path)
    xlsx_temp = os.path.splitext(xlsm_path)[0] + "_tmp.xlsx"

    cf_matched_ims = cf_matched_ims or set()
    matched = recon.matched_df()
    b_un = recon.books_unmatched()
    i_un = recon.ims_unmatched().copy()
    i_un["period_class"] = i_un["ret_period"].apply(lambda p: classify_period(p, period))
    # full IMS classified (for same-period KPI)
    ims_all = recon.ims.copy()
    ims_all["period_class"] = ims_all["ret_period"].apply(lambda p: classify_period(p, period))
    ims_all["matched"] = ims_all["ims_id"].isin(recon.ims_used)
    same = ims_all[ims_all["period_class"] == "same-period"]
    same_m = int(same["matched"].sum())
    same_itc = float(same["total_tax"].sum())
    same_itc_m = float(same[same["matched"]]["total_tax"].sum())
    # CF-matched cross-period IMS rows are promoted to the Matched tab, so drop
    # them from the unmatched cross-period pool here.
    cf_promoted = i_un[i_un["ims_id"].isin(cf_matched_ims)].copy()
    i_un = i_un[~i_un["ims_id"].isin(cf_matched_ims)].copy()
    cross_un = i_un[i_un["period_class"] != "same-period"]
    same_un = i_un[i_un["period_class"] == "same-period"]

    HEAD = PatternFill("solid", fgColor="1F4E78")
    SUB  = PatternFill("solid", fgColor="D9E1F2")
    GOOD = PatternFill("solid", fgColor="C6EFCE")
    WARN = PatternFill("solid", fgColor="FFEB9C")
    BAD  = PatternFill("solid", fgColor="FFC7CE")
    WHITEB = Font(name="Arial", bold=True, color="FFFFFF")
    BOLD = Font(name="Arial", bold=True)
    NORM = Font(name="Arial")
    thin = Side(style="thin", color="BFBFBF")
    BORD = Border(left=thin, right=thin, top=thin, bottom=thin)
    MONEY = '#,##0.00;(#,##0.00);"-"'

    wb = Workbook()

    def style_header(ws, row, ncols):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = WHITEB; cell.fill = HEAD
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BORD

    def write_table(ws, df, start_row, money_cols=(), flag_col=None,
                    check_col=None, quarter_col=None):
        from openpyxl.worksheet.datavalidation import DataValidation
        for j, col in enumerate(df.columns, 1):
            ws.cell(row=start_row, column=j, value=col)
        style_header(ws, start_row, len(df.columns))
        cols_list = list(df.columns)
        flag_idx = cols_list.index(flag_col) if (flag_col and flag_col in cols_list) else None
        q_idx = cols_list.index(quarter_col) if (quarter_col and quarter_col in cols_list) else None
        last_row = start_row + len(df)
        for i, (_, r) in enumerate(df.iterrows(), start=start_row + 1):
            row_flag = (flag_idx is not None and str(r[flag_col]) == "CHECK")
            qfill = None
            if q_idx is not None:
                qfill = _QUARTER_FILL.get(str(r[quarter_col]))
            for j, col in enumerate(df.columns, 1):
                v = r[col]
                if isinstance(v, (np.integer,)): v = int(v)
                elif isinstance(v, (np.floating,)): v = float(v)
                cell = ws.cell(row=i, column=j, value=v)
                cell.font = NORM; cell.border = BORD
                if col in money_cols:
                    cell.number_format = MONEY
                if col == check_col:
                    cell.value = "FALSE"
                    cell.alignment = Alignment(horizontal="center")
                if row_flag:
                    cell.fill = BAD
                elif qfill:
                    cell.fill = PatternFill("solid", fgColor=qfill)
        # checkbox dropdown (TRUE/FALSE) on the check column
        if check_col and check_col in cols_list and len(df):
            cidx = cols_list.index(check_col) + 1
            letter = get_column_letter(cidx)
            dv = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
            dv.add(f"{letter}{start_row+1}:{letter}{last_row}")
            ws.add_data_validation(dv)
        # widths
        for j, col in enumerate(df.columns, 1):
            w = max(len(str(col)), *(len(str(r[col])) for _, r in df.iterrows())) if len(df) else len(str(col))
            ws.column_dimensions[get_column_letter(j)].width = min(max(w + 2, 10), 42)
        ws.freeze_panes = ws.cell(row=start_row + 1, column=1)

    # ---------------------- Sheet 1: Summary dashboard --------------------- #
    ws = wb.active; ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    ws["A1"] = "GST IMS (GSTR-2B) \u2194 Books ITC Reconciliation"
    ws["A1"].font = Font(name="Arial", bold=True, size=15, color="1F4E78")
    ws["A2"] = f"Period: {period or 'N/A'}    |    Recipient GSTIN per IMS file"
    ws["A2"].font = Font(name="Arial", italic=True, size=10, color="595959")

    def itc(df, side):
        if df.empty: return 0.0
        cols = ["book_cgst","book_sgst","book_igst"] if side=="book" else ["ims_cgst","ims_sgst","ims_igst"]
        return float(df[cols].sum().sum())

    n_books = len(recon.books); n_ims = len(recon.ims)
    book_itc_total = float(recon.books["total_tax"].sum())
    ims_itc_total  = float(recon.ims["total_tax"].sum())
    matched_book_itc = itc(matched, "book")
    matched_ims_itc  = itc(matched, "ims")

    rows = [
        ("RECONCILIATION OVERVIEW", "Volume (count)", "Value \u2013 ITC (\u20b9)"),
        ("Books purchase entries (total)", n_books, book_itc_total),
        ("IMS / 2B invoices (B2B, total)", n_ims, ims_itc_total),
        ("", "", ""),
        ("SAME-PERIOD RECON (books month vs 2B-filed same month)", "", ""),
        (f"IMS invoices filed in {period or 'book month'}", len(same), same_itc),
        ("  \u2514 matched", same_m, same_itc_m),
        ("  \u2514 true same-period gap", len(same) - same_m, same_itc - same_itc_m),
        ("", "", ""),
        ("Matched \u2013 book entries", len(recon.book_used), matched_book_itc),
        ("Matched \u2013 IMS invoices (all periods)", len(recon.ims_used), matched_ims_itc),
        ("Unmatched \u2013 Books only (not in 2B)", len(b_un), float(b_un["total_tax"].sum()) if len(b_un) else 0.0),
        ("Unmatched \u2013 IMS same-period (true gap)", len(same_un), float(same_un["total_tax"].sum()) if len(same_un) else 0.0),
        ("Unmatched \u2013 IMS cross-period (timing/carry-fwd)", len(cross_un), float(cross_un["total_tax"].sum()) if len(cross_un) else 0.0),
    ]
    r0 = 4
    for k,(a,b,c) in enumerate(rows):
        ra = r0 + k
        ws.cell(row=ra, column=1, value=a)
        ws.cell(row=ra, column=2, value=b)
        ws.cell(row=ra, column=3, value=c)
        if k == 0:
            for cc in range(1,4):
                cell=ws.cell(row=ra,column=cc); cell.font=WHITEB; cell.fill=HEAD
                cell.alignment=Alignment(horizontal="center")
        else:
            is_subhead = a.isupper() and b == "" and c == ""
            al = a.lower()
            ws.cell(row=ra,column=1).font = BOLD if (a and not al.startswith("  ")) else NORM
            ws.cell(row=ra,column=2).font = NORM
            ws.cell(row=ra,column=3).font = NORM
            ws.cell(row=ra,column=3).number_format = MONEY
            if is_subhead:
                for cc in range(1,4):
                    cell=ws.cell(row=ra,column=cc); cell.fill=SUB; cell.font=BOLD
            elif "matched" in al or al.endswith("matched"):
                for cc in range(1,4): ws.cell(row=ra,column=cc).fill=GOOD
            elif "true same-period gap" in al:
                for cc in range(1,4): ws.cell(row=ra,column=cc).fill=BAD
            elif "cross-period" in al:
                for cc in range(1,4): ws.cell(row=ra,column=cc).fill=SUB
            elif "unmatched" in al:
                for cc in range(1,4): ws.cell(row=ra,column=cc).fill=WARN

    # match breakdown by tier
    tb = r0 + len(rows) + 2
    ws.cell(row=tb, column=1, value="MATCHED BREAKDOWN BY TIER")
    for cc in range(1,4):
        cell=ws.cell(row=tb,column=cc); cell.font=WHITEB; cell.fill=HEAD
        cell.alignment=Alignment(horizontal="center")
    ws.cell(row=tb,column=2,value="Book entries"); ws.cell(row=tb,column=3,value="ITC value (\u20b9)")
    if not matched.empty:
        g = matched.groupby("tier").agg(n=("book_id","nunique"), v=("book_total_tax","sum")).reset_index()
        for k,(_,gr) in enumerate(g.iterrows(),1):
            ws.cell(row=tb+k,column=1,value=gr["tier"]).font=NORM
            ws.cell(row=tb+k,column=2,value=int(gr["n"])).font=NORM
            cell=ws.cell(row=tb+k,column=3,value=float(gr["v"])); cell.number_format=MONEY; cell.font=NORM

    ws.column_dimensions["A"].width=46; ws.column_dimensions["B"].width=18; ws.column_dimensions["C"].width=22

    # ---------------------- Tax Rate helper ------------------------------- #
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

    # ---------------------- Sheet 2: Matched (exact) ----------------------- #
    money = ("taxable_value","cgst","sgst","igst",
             "book_cgst","book_sgst","book_igst","book_total_tax",
             "ims_cgst","ims_sgst","ims_igst","ims_total_tax","tax_diff")
    cols = ["match_source","tier","confidence","gstin_match",
            "taxable_value","date","cgst","sgst","igst",
            "book_gstin","ims_gstin","book_supplier","ims_supplier",
            "book_ref_no","ims_inv_no","ims_status",
            "book_total_tax","ims_total_tax","tax_diff",
            "book_entry_count","ims_invoice_count","note","Tax Rate %"]
    exact = matched[matched["tier"]=="1-EXACT"] if not matched.empty else matched
    exact = _attach_tax_rate(exact, "taxable_value", "cgst", "sgst", "igst")
    ws2 = wb.create_sheet("Matched (Exact)")
    write_table(ws2, (exact[cols] if not exact.empty else pd.DataFrame(columns=cols)), 1,
                money_cols=("taxable_value","cgst","sgst","igst",
                           "book_total_tax","ims_total_tax","tax_diff"), flag_col="gstin_match")

    # ---------------------- Sheet 3: Review (fuzzy+agg) -------------------- #
    review = matched[matched["tier"]!="1-EXACT"] if not matched.empty else matched
    review = _attach_tax_rate(review, "taxable_value", "cgst", "sgst", "igst")
    ws3 = wb.create_sheet("Review (Fuzzy+Agg)")
    write_table(ws3, (review[cols] if not review.empty else pd.DataFrame(columns=cols)), 1,
                money_cols=("taxable_value","cgst","sgst","igst",
                           "book_total_tax","ims_total_tax","tax_diff"), flag_col="gstin_match")

    # ------------- Sheet: Carry-Forward Matches (cross-period IMS) ---------- #
    cfcols = ["match_type","confidence","gstin","ims_supplier","ims_inv_no",
              "ims_ret_period","ims_total_tax","cf_row","cf_particulars",
              "cf_inv_no","cf_total_tax","tax_diff","cf_prev_status","cf_new_status","Tax Rate %"]
    ws_cf = wb.create_sheet("Carry-Forward Matches")
    cfm = cf_matches if (cf_matches is not None and not cf_matches.empty) else pd.DataFrame(columns=cfcols)
    cfm = _attach_tax_rate(cfm, "m_taxable", "m_cgst", "m_sgst", "m_igst")
    write_table(ws_cf, cfm[cfcols] if not cfm.empty else cfm, 1,
                money_cols=("ims_total_tax","cf_total_tax","tax_diff"))

    # ---------------------- Sheet 4: Books-only unmatched ------------------ #
    bcols = ["book_id","gstin","supplier","ref_no","voucher_no","date","gross_total","taxable","cgst","sgst","igst","total_tax","Tax Rate %"]
    b_out = (b_un[bcols[:-1]].copy() if len(b_un) else pd.DataFrame(columns=bcols[:-1]))
    b_out = _attach_tax_rate(b_out, "taxable", "cgst", "sgst", "igst")
    b_out["Move to Matched?"] = ""
    ws4 = wb.create_sheet("Unmatched - Books only")
    write_table(ws4, b_out, 1, money_cols=("gross_total","taxable","cgst","sgst","igst","total_tax"),
                check_col="Move to Matched?")

    # ------------ Sheet 5/6: IMS unmatched split by period class --------- #
    icols = ["ims_id","gstin","name","inv_no","inv_date","taxable","status","cgst","sgst","igst","total_tax","filing","ret_period","period_class","Tax Rate %"]
    sm = same_un.sort_values("total_tax", ascending=False) if len(same_un) else same_un
    s_out = (sm[icols[:-1]].copy() if len(sm) else pd.DataFrame(columns=icols[:-1]))
    s_out = _attach_tax_rate(s_out, "taxable", "cgst", "sgst", "igst")
    s_out["Move to Matched?"] = ""
    ws5 = wb.create_sheet("Unmatched IMS (same period)")
    write_table(ws5, s_out, 1, money_cols=("taxable","cgst","sgst","igst","total_tax"),
                check_col="Move to Matched?")

    # Cross-period: add Quarter column (from invoice date) + checkbox
    cp = cross_un.sort_values(["period_class","total_tax"], ascending=[True, False]) if len(cross_un) else cross_un
    cp_out = (cp[icols[:-1]].copy() if len(cp) else pd.DataFrame(columns=icols[:-1]))
    cp_out = _attach_tax_rate(cp_out, "taxable", "cgst", "sgst", "igst")
    cp_out["Quarter"] = cp_out["inv_date"].apply(_quarter_of) if len(cp_out) else []
    cp_out["Move to Matched?"] = ""
    ws6 = wb.create_sheet("Cross-period IMS (timing)")
    write_table(ws6, cp_out, 1, money_cols=("taxable","cgst","sgst","igst","total_tax"),
                check_col="Move to Matched?", quarter_col="Quarter")

    # ---------------------- Sheet 7: All Transactions ------------------------- #
    def _tier_to_tab(tier):
        # 1-EXACT -> Matched (Exact); everything else (fuzzy/value/aggregated) -> Review
        return "Matched (Exact)" if str(tier) == "1-EXACT" else "Review (Fuzzy+Agg)"

    all_rows = []
    # 1. Matched (Exact) + Review (Fuzzy+Agg)
    for _, r in matched.iterrows():
        all_rows.append({
            "Particulars / Supplier": r["book_supplier"],
            "GSTIN": r["book_gstin"],
            "Voucher / Invoice No": r["book_ref_no"],
            "Taxable Value": r.get("taxable_value", ""),
            "CGST": r.get("cgst", r["book_cgst"]),
            "SGST": r.get("sgst", r["book_sgst"]),
            "IGST": r.get("igst", r["book_igst"]),
            "Date": r.get("date", ""),
            "Status": _tier_to_tab(r["tier"]),
            "Origin": r["match_source"],
            "Source File": "Books",
        })
    # 2. Carry-Forward Matches
    if cfm is not None and not cfm.empty:
        for _, r in cfm.iterrows():
            all_rows.append({
                "Particulars / Supplier": r.get("ims_supplier", ""),
                "GSTIN": r.get("gstin", ""),
                "Voucher / Invoice No": r.get("ims_inv_no", ""),
                "Taxable Value": r.get("taxable_value", r.get("m_taxable", "")),
                "CGST": r.get("cgst", r.get("m_cgst", "")),
                "SGST": r.get("sgst", r.get("m_sgst", "")),
                "IGST": r.get("igst", r.get("m_igst", "")),
                "Date": r.get("date", r.get("m_date", "")),
                "Status": "Carry-Forward Matches",
                "Origin": "Engine",
                "Source File": "IMS",
            })
    # 3. Unmatched - Books only
    for _, r in b_un.iterrows():
        all_rows.append({
            "Particulars / Supplier": r["supplier"],
            "GSTIN": r["gstin"],
            "Voucher / Invoice No": r["ref_no"],
            "Taxable Value": r.get("taxable", ""),
            "CGST": r["cgst"],
            "SGST": r["sgst"],
            "IGST": r["igst"],
            "Date": r["date"],
            "Status": "Unmatched - Books only",
            "Origin": "Engine",
            "Source File": "Books",
        })
    # 4. Unmatched IMS (same period)
    for _, r in same_un.iterrows():
        all_rows.append({
            "Particulars / Supplier": r["name"],
            "GSTIN": r["gstin"],
            "Voucher / Invoice No": r["inv_no"],
            "Taxable Value": r.get("taxable", ""),
            "CGST": r["cgst"],
            "SGST": r["sgst"],
            "IGST": r["igst"],
            "Date": r["inv_date"],
            "Status": "Unmatched IMS (same period)",
            "Origin": "Engine",
            "Source File": "IMS",
        })
    # 5. Cross-period IMS (timing)
    for _, r in cross_un.iterrows():
        all_rows.append({
            "Particulars / Supplier": r["name"],
            "GSTIN": r["gstin"],
            "Voucher / Invoice No": r["inv_no"],
            "Taxable Value": r.get("taxable", ""),
            "CGST": r["cgst"],
            "SGST": r["sgst"],
            "IGST": r["igst"],
            "Date": r["inv_date"],
            "Status": "Cross-period IMS (timing)",
            "Origin": "Engine",
            "Source File": "IMS",
        })
    all_cols = ["Particulars / Supplier", "GSTIN", "Voucher / Invoice No",
                "Taxable Value", "CGST", "SGST", "IGST", "Date", "Status",
                "Origin", "Source File", "Tax Rate %"]
    # populate Tax Rate % on each master row from its own values
    for row in all_rows:
        row["Tax Rate %"] = _tax_rate(row.get("Taxable Value"), row.get("CGST"),
                                       row.get("SGST"), row.get("IGST"))
    all_df = pd.DataFrame(all_rows, columns=all_cols)
    ws7 = wb.create_sheet("All Transactions")
    write_table(ws7, all_df, 1, money_cols=("Taxable Value", "CGST", "SGST", "IGST"))

    # ---------------------- Sheet 8: GSTR3B Working --------------------------- #
    gstr3b_rows = []
    # 1. Matched (Exact) + Review (Fuzzy+Agg)
    for _, r in matched.iterrows():
        gstr3b_rows.append({
            "Particulars / Supplier": r["book_supplier"],
            "GSTIN": r["book_gstin"],
            "Voucher / Invoice No": r["book_ref_no"],
            "Taxable Value": r.get("taxable_value", ""),
            "CGST": r.get("cgst", r["book_cgst"]),
            "SGST": r.get("sgst", r["book_sgst"]),
            "IGST": r.get("igst", r["book_igst"]),
            "Date": r.get("date", ""),
            "Status": _tier_to_tab(r["tier"]),
            "Origin": r["match_source"],
            "Source File": "Books",
        })
    # 2. Carry-Forward Matches
    if cfm is not None and not cfm.empty:
        for _, r in cfm.iterrows():
            gstr3b_rows.append({
                "Particulars / Supplier": r.get("ims_supplier", ""),
                "GSTIN": r.get("gstin", ""),
                "Voucher / Invoice No": r.get("ims_inv_no", ""),
                "Taxable Value": r.get("taxable_value", r.get("m_taxable", "")),
                "CGST": r.get("cgst", r.get("m_cgst", "")),
                "SGST": r.get("sgst", r.get("m_sgst", "")),
                "IGST": r.get("igst", r.get("m_igst", "")),
                "Date": r.get("date", r.get("m_date", "")),
                "Status": "Carry-Forward Matches",
                "Origin": "Engine",
                "Source File": "IMS",
            })
    gstr3b_cols = all_cols  # includes Tax Rate %
    for row in gstr3b_rows:
        row["Tax Rate %"] = _tax_rate(row.get("Taxable Value"), row.get("CGST"),
                                       row.get("SGST"), row.get("IGST"))
    gstr3b_df = pd.DataFrame(gstr3b_rows, columns=gstr3b_cols)
    ws8 = wb.create_sheet("GSTR3B Working")
    write_table(ws8, gstr3b_df, 1, money_cols=("Taxable Value", "CGST", "SGST", "IGST"))

    # --- GSTR-3B summary as the FIRST tab (inserted at index 0) ---
    _add_gstr3b_summary_tab(wb, period, gstr3b_data_rows=len(gstr3b_df),
                            outward_summary_path=outward_summary_path)

    wb.save(xlsx_temp)
    xlsm_path = embed_macro(xlsx_temp, xlsm_path=xlsm_path)
    return xlsm_path


def run_recon(input_dir, out_path, period="", carry_forward=None,
              cf_out=None, util_label="Utilized in April 2026",
              outward_summary_path=None):
    """Core reconciliation logic — callable from CLI or Streamlit.

    Args:
        input_dir: Directory containing input files (auto-detected by name).
        out_path: Desired output path for the .xlsm report.
        period: Return period like "Apr'26" (auto-detected from filenames if empty).
        carry_forward: Path to carry-forward file, or None to auto-detect.
        cf_out: Where to write the updated carry-forward (default: alongside out_path).
        util_label: Status label for matched CF rows.

    Returns:
        (xlsm_path, cf_updated_path_or_None)
    """
    f = find_files(input_dir)
    missing = [k for k in ("ims", "cgst", "igst") if not f[k]]
    if missing:
        raise FileNotFoundError(f"Missing required files: {missing}")

    period = period or detect_period_from_files(f)
    if not period:
        raise ValueError(
            "Could not auto-detect period from filenames. "
            "Pass --period \"Mon'YY\" or rename files.")

    cf_path = carry_forward or f.get("cf")
    out_dir = os.path.dirname(out_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    books = load_books(f["cgst"], f["sgst"], f["igst"])
    ims = load_ims(f["ims"])

    recon = Recon(books, ims).run()

    cf_matches, cf_matched_ims = None, set()
    cf_updated_path = None
    if cf_path:
        i_un = recon.ims_unmatched().copy()
        i_un["pc"] = i_un["ret_period"].apply(lambda p: classify_period(p, period))
        cross = i_un[i_un["pc"] != "same-period"].copy()
        cf_matches, cf_updated, cf_matched_ims = match_carry_forward(
            cross, cf_path, util_label)
        cf_updated_path = cf_out or os.path.join(out_dir, "Carry_Forward_Updated.xlsx")
        rows = set(cf_matches["cf_row"].tolist()) if not cf_matches.empty else set()
        write_updated_cf(cf_path, cf_updated, cf_updated_path, util_label, rows)

    xlsm_path = build_report(recon, out_path, period, cf_matches, cf_matched_ims,
                             outward_summary_path=outward_summary_path)

    m = recon.matched_df()
    summary = {
        "book_total": len(books),
        "book_matched": len(recon.book_used),
        "ims_total": len(ims),
        "ims_matched": len(recon.ims_used),
        "tiers": m.groupby("tier")["book_id"].nunique().to_dict() if not m.empty else {},
    }
    return xlsm_path, cf_updated_path, summary


def main():
    ap = argparse.ArgumentParser(description="GST IMS <-> Books ITC reconciliation")
    ap.add_argument("--input-dir", default="inputs",
                    help="folder containing input files (default: ./inputs/)")
    ap.add_argument("--out", default="",
                    help="output .xlsm path (default: ./output/recon_<period>.xlsm)")
    ap.add_argument("--period", default="",
                    help="return period e.g. Apr'26 (auto-detected from filenames if omitted)")
    ap.add_argument("--carry-forward", default=None,
                    help="path to Carry-Forward file (auto-detected from inputs/ if omitted)")
    ap.add_argument("--cf-out", default=None,
                    help="path for updated Carry-Forward file (default: output/Carry_Forward_Updated.xlsx)")
    ap.add_argument("--util-label", default="Utilized in April 2026")
    ap.add_argument("--output-summary", default=None,
                    help="path to the outward-revenue summary xlsx (used to populate "
                         "Section 3.1(a) outward taxable supplies in the GSTR-3B tab)")
    a = ap.parse_args()

    # resolve defaults
    f = find_files(a.input_dir)
    period = a.period or detect_period_from_files(f)
    if not a.out:
        out = os.path.join("output", f"recon_{period.replace(chr(39), '')}.xlsm")
    else:
        out = a.out

    print("Files:", {k: os.path.basename(v) if v else None for k, v in f.items()})
    print(f"Period: {period}")

    xlsm_path, cf_path, summary = run_recon(
        input_dir=a.input_dir,
        out_path=out,
        period=period,
        carry_forward=a.carry_forward,
        cf_out=a.cf_out,
        util_label=a.util_label,
        outward_summary_path=a.output_summary,
    )

    if cf_path:
        print(f"Updated carry-forward written to {cf_path}")
    print(f"Matched book entries : {summary['book_matched']}/{summary['book_total']}")
    print(f"Matched IMS invoices : {summary['ims_matched']}/{summary['ims_total']}")
    if summary["tiers"]:
        print("By tier:", summary["tiers"])
    print("Report written to", xlsm_path)


if __name__ == "__main__":
    main()
