#!/usr/bin/env python3
"""
Airpay Reconciliation — Streamlit UI
Mirrors recon_engine (2).py logic exactly; adds file-upload, bank dropdown,
type-assignment panel, Stage-3 placeholders, and in-browser download.
"""

import io
import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ======================================================================
# CONFIG
# ======================================================================
CONFIG = {
    "txn": {
        "id": "Merchant Txn Id",
        "amount": "Amount",
        "status": "Transaction Status",
        "bank_name": "Bank Name",
        "datetime": "Added On",
        "context": ["Name", "Merchant Id", "Bank Name"],
    },
    "ma": {
        "id": "Merchant Txn Id",
        "amount": "Txn Amount",
        "status": "Txn Status",
        "datetime": "Txn Date/Time",
        "context": ["Merchant Name", "Bank"],
    },
    "ledger": {
        "id": "Merchant Txn Id",
        "amount": "Amount",
        "credit_amount": "Creditamount",
        "mode": "Mode",
        "mode_credit_value": "Credit",
        "datetime": "Added On",
    },
}

STATUS_SUCCESS = {"success"}
STATUS_FAILED = {"failed", "fail"}
STATUS_INCOMPLETE = {"incomplete"}
AMOUNT_TOLERANCE  = 0.01   # Stage 1 & 2: per-transaction match
STAGE3_TOLERANCE  = 2.00   # Stage 3: cycle totals — allows for formula rounding accumulation

NONFIN_KW = [
    "ministatement", "balanceenquiry", "balanceinquiry",
    "balance", "enquiry", "inquiry", "query",
]

MODES = {
    "AEPS": {
        "financialKw": ["withdrawal", "cashwithdrawal"],
        "otherModeKw": ["aadhaarpay", "aadharpay", "sales"],
    },
    "Aadhaar Pay": {
        "financialKw": ["aadhaarpay", "aadharpay", "sales"],
        "otherModeKw": ["withdrawal", "cashwithdrawal"],
    },
}

ICICI_SYNONYMS = {
    "amount":   ["credit", "amount", "transaction amount", "txn amount",
                 "settlement amount", "net amount",
                 "withdrawal", "withdrawal amt", "deposit", "deposit amt",
                 "debit", "amt", "withdrawal amt (inr)", "deposit amt (inr)"],
    "datetime": ["transaction posted date", "transaction posted datetime",
                 "value date", "valuedate", "date", "transaction date",
                 "txn date", "posted date", "datetime", "posting date"],
}

ICICI_HEADER_KEYWORDS = [
    "tran. id", "value date", "transaction remarks", "s.n.",
    "withdrawal amt", "deposit amt", "balance", "cheque",
    "transaction date", "transaction posted date",
]

BANK_SYNONYMS = {
    "id":       ["client transaction id", "bcrefid", "curn", "merchant txn id",
                 "merchant transaction id", "reference id", "transaction id",
                 "txn id", "order id"],
    "amount":   ["transaction amount", "transactionamount", "txn amount", "amount"],
    "status":   ["transaction status", "transactionstatus", "txn status", "status"],
    "type":     ["transaction mode", "transaction type", "transactiontype",
                 "txn type", "payment type", "mode"],
    "datetime": ["transactiondatetime", "transaction datetime", "txn datetime",
                 "transaction date time", "datetime"],
    "date":     ["transaction date", "txn date", "date"],
    "time":     ["transaction time", "txn time", "time"],
}

CONFIG_PATH = Path("recon_config.json")

BANK_DEFAULTS = {
    "NSDL":     {"cycleCount": 1, "cycles": [{"startDate": "", "startHHMM": "23:00", "endDate": "", "endHHMM": "23:00"}]},
    "Fino bank":{"cycleCount": 1, "cycles": [{"startDate": "", "startHHMM": "16:30", "endDate": "", "endHHMM": "16:30"}]},
    "CREDOPAY": {"cycleCount": 1, "cycles": [{"startDate": "", "startHHMM": "17:30", "endDate": "", "endHHMM": "17:30"}]},
}


# ======================================================================
# Loading helpers
# ======================================================================
def load_uploaded(f):
    name = f.name.lower()
    is_icici = "icici" in name
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        if is_icici:
            raw = pd.read_excel(f, header=None, dtype=str)
            header_row = detect_icici_header_row(raw)
            if header_row > 0:
                raw.columns = raw.iloc[header_row].fillna("").astype(str).tolist()
                raw = raw.drop(range(header_row + 1)).reset_index(drop=True)
            else:
                raw = raw.reset_index(drop=True)
            return raw
        return pd.read_excel(f, dtype=str)
    if is_icici:
        raw = pd.read_csv(f, header=None, dtype=str)
        header_row = detect_icici_header_row(raw)
        if header_row > 0:
            raw.columns = raw.iloc[header_row].fillna("").astype(str).tolist()
            raw = raw.drop(range(header_row + 1)).reset_index(drop=True)
        else:
            raw = raw.reset_index(drop=True)
        return raw
    return pd.read_csv(f, dtype=str)


def load_settlement_report(f):
    """Load a settlement report; concatenate all sheets if multi-tab Excel."""
    name = f.name.lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        xl = pd.ExcelFile(f)
        if len(xl.sheet_names) > 1:
            dfs = [pd.read_excel(xl, sheet_name=sh, dtype=str)
                   for sh in xl.sheet_names]
            return pd.concat(dfs, ignore_index=True)
        return pd.read_excel(f, dtype=str)
    return pd.read_csv(f, dtype=str)


def load_config(path=None):
    p = Path(path or CONFIG_PATH)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg, path=None):
    p = Path(path or CONFIG_PATH)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ======================================================================
# Normalization helpers
# ======================================================================
def norm_id(s):
    return s.astype(str).str.strip()


def norm_amount(s):
    return pd.to_numeric(s, errors="coerce").round(2)


def _nid(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return str(v).strip()


def _namt(v):
    if v is None or v == "":
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    try:
        n = float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None
    if np.isnan(n):
        return None
    return round(n, 2)


def classify_status(raw):
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return ("Failed", "Missing status", False)
    r = str(raw).strip().lower()
    if r == "":
        return ("Failed", "Missing status", False)
    if r in STATUS_SUCCESS:
        return ("Success", "", True)
    if r in STATUS_INCOMPLETE:
        return ("Failed", "Incomplete", True)
    if r in STATUS_FAILED:
        return ("Failed", "", True)
    return ("Failed", f"Unrecognized status: {raw}", False)


def amounts_equal(a, b):
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return False
    return abs(float(a) - float(b)) <= AMOUNT_TOLERANCE


def get_context(df, id_series, cols, prefix):
    present = [c for c in cols if c in df.columns]
    out = pd.DataFrame({"_id": id_series})
    for c in present:
        out[f"{prefix}{c}"] = df[c].values
    return out.drop_duplicates("_id").set_index("_id")


def ctx_first(df, id_col, cols, prefix):
    present = [c for c in cols if c in df.columns]
    m = {}
    for r in df.to_dict("records"):
        i = _nid(r.get(id_col))
        if i not in m:
            m[i] = {f"{prefix}{c}": r.get(c) for c in present}
    return present, m


# ======================================================================
# Fuzzy bank-header resolver
# ======================================================================
def norm_header(s):
    return re.sub(r"[^a-z0-9]", "", str("" if s is None else s).lower())


def resolve_field(headers, synonyms):
    nh = [(h, norm_header(h)) for h in headers]
    for syn in synonyms:
        ns = norm_header(syn)
        for h, n in nh:
            if n == ns:
                return h
    for syn in synonyms:
        ns = norm_header(syn)
        if len(ns) < 4:
            continue
        for h, n in nh:
            if ns in n:
                return h
    return None


def resolve_bank_columns(headers):
    c = {
        "id":       resolve_field(headers, BANK_SYNONYMS["id"]),
        "amount":   resolve_field(headers, BANK_SYNONYMS["amount"]),
        "status":   resolve_field(headers, BANK_SYNONYMS["status"]),
        "type":     resolve_field(headers, BANK_SYNONYMS["type"]),
        "datetime": resolve_field(headers, BANK_SYNONYMS["datetime"]),
        "date": None, "time": None,
    }
    if not c["datetime"]:
        c["date"] = resolve_field(headers, BANK_SYNONYMS["date"])
        c["time"] = resolve_field(headers, BANK_SYNONYMS["time"])
    missing = [k for k in ("id", "amount", "status", "type") if not c[k]]
    if not c["datetime"] and not (c["date"] and c["time"]):
        missing.append("datetime")
    c["missing"] = missing
    return c


# Settlement reports have different column naming than bank statements, so we use
# a dedicated synonym list. Key differences:
#   - datetime: prefer explicit "datetime" compound names first; avoid matching
#     settlement/nodal date columns (same for all rows) as the transaction datetime.
#   - status: includes "response code" (Credopay) and similar result codes.
SETTLEMENT_SYNONYMS = {
    "amount":   BANK_SYNONYMS["amount"],
    "status":   BANK_SYNONYMS["status"] + ["response code", "result code", "transaction status code"],
    # Only match explicitly compound datetime column names here.
    # "transaction datetime" / "txn datetime" are intentionally omitted because
    # the substring check would cause "Transaction Date" and "Txn Date" to
    # match them — those split-date columns are caught by "date"/"time" below.
    "datetime": [
        "transactiondatetime", "datetime", "posted date", "posting date",
    ],
    "date": [
        "transaction date", "txn date", "value date", "valuedate", "date",
    ],
    "time":     BANK_SYNONYMS["time"],
}


def resolve_settlement_columns(headers):
    """Fuzzy-detect amount, status, and datetime columns in a settlement report."""
    c = {
        "amount":   resolve_field(headers, SETTLEMENT_SYNONYMS["amount"]),
        "status":   resolve_field(headers, SETTLEMENT_SYNONYMS["status"]),
        "datetime": resolve_field(headers, SETTLEMENT_SYNONYMS["datetime"]),
        "date": None, "time": None,
    }
    if not c["datetime"]:
        c["date"] = resolve_field(headers, SETTLEMENT_SYNONYMS["date"])
        c["time"] = resolve_field(headers, SETTLEMENT_SYNONYMS["time"])
    missing = []
    if not c["amount"]:
        missing.append("amount")
    # date alone is OK — time may be embedded in the date column (e.g. Credopay "Txn Date")
    if not c["datetime"] and not c["date"]:
        missing.append("datetime")
    c["missing"] = missing
    return c


# ======================================================================
# Date/time standardization  ->  DD-MM-YYYY HH:MM:SS
# ======================================================================
def _pad2(n):
    n = str(n)
    return n if len(n) >= 2 else "0" + n


def _parse_dmy(s):
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})",
                 str("" if s is None else s).strip())
    if not m:
        return None
    y = int(m.group(3))
    if y < 100:
        y += 2000
    return [y, int(m.group(2)), int(m.group(1))]


def _parse_hms(s):
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?",
                  str("" if s is None else s).strip())
    if not m:
        return None
    return [int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else 0]


def standardize_dt(date_str=None, time_str=None, single_str=None):
    ymd = hms = None
    if single_str is not None and str(single_str).strip() != "":
        parts = str(single_str).strip().split()
        ymd = _parse_dmy(parts[0])
        hms = _parse_hms(" ".join(parts[1:])) if len(parts) > 1 else [0, 0, 0]
    else:
        ymd = _parse_dmy(date_str)
        hms = (_parse_hms(time_str)
               if (time_str is not None and str(time_str).strip() != "")
               else [0, 0, 0])
    if not ymd:
        raw = str(single_str) if single_str is not None else f"{date_str or ''} {time_str or ''}"
        return (raw.strip(), "")
    if not hms:
        hms = [0, 0, 0]
    disp = (f"{_pad2(ymd[2])}-{_pad2(ymd[1])}-{ymd[0]} "
            f"{_pad2(hms[0])}:{_pad2(hms[1])}:{_pad2(hms[2])}")
    iso  = (f"{ymd[0]}-{_pad2(ymd[1])}-{_pad2(ymd[2])}T"
            f"{_pad2(hms[0])}:{_pad2(hms[1])}:{_pad2(hms[2])}")
    return (disp, iso)


# ======================================================================
# Bank status (codes + words)
# ======================================================================
def classify_bank_status(raw):
    r = str("" if raw is None else raw).strip().lower()
    if r in {"success", "successful", "00", "000", "0"}:
        return "Success"
    return "Failed"


def bank_status_code(raw):
    s = str("" if raw is None else raw).strip()
    return s if re.search(r"\d", s) else ""


# ======================================================================
# Mode / type classification
# ======================================================================
def compact_type(t):
    return re.sub(r"[^a-z0-9]", "", str("" if t is None else t).lower())


def default_category(type_val, mode):
    c = compact_type(type_val)
    md = MODES.get(mode, MODES["AEPS"])
    for kw in NONFIN_KW:
        if kw in c:
            return "nonfinancial"
    for kw in md["financialKw"]:
        if kw in c:
            return "financial"
    for kw in md["otherModeKw"]:
        if kw in c:
            return "ignored"
    return "flagged"


def get_bank_types(df, type_col):
    seen, out = set(), []
    if type_col not in df.columns:
        return out
    for v in df[type_col].tolist():
        t = str("" if v is None else v).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    out.sort()
    return out


def build_type_assignment(types, mode, saved=None):
    saved = saved or {}
    fin = set(saved.get("financial", []))
    non = set(saved.get("nonFinancial", []))
    ign = set(saved.get("ignored", []))
    a = {"financial": [], "nonFinancial": [], "ignored": [], "flagged": []}
    for t in types:
        if t in fin:
            a["financial"].append(t)
        elif t in non:
            a["nonFinancial"].append(t)
        elif t in ign:
            a["ignored"].append(t)
        else:
            c = default_category(t, mode)
            a[{"financial": "financial", "nonfinancial": "nonFinancial",
               "ignored": "ignored", "flagged": "flagged"}[c]].append(t)
    return a


# ======================================================================
# Stage 1 : Txn <-> MA <-> Point ledger
# ======================================================================
def build_stage1(txn, ma, ledger):
    cT, cM, cL = CONFIG["txn"], CONFIG["ma"], CONFIG["ledger"]

    t = pd.DataFrame({"_id": norm_id(txn[cT["id"]])})
    t["txn_amount"] = norm_amount(txn[cT["amount"]])
    t["txn_raw"]    = txn[cT["status"]].fillna("").astype(str).str.strip()
    sc = txn[cT["status"]].map(classify_status)
    t["txn_status"] = sc.map(lambda x: x[0])
    if cT["datetime"] in txn.columns:
        t["txn_datetime"] = txn[cT["datetime"]].values
    t = t.drop_duplicates("_id")

    m = pd.DataFrame({"_id": norm_id(ma[cM["id"]])})
    m["ma_amount"] = norm_amount(ma[cM["amount"]])
    m["ma_raw"]    = ma[cM["status"]].fillna("").astype(str).str.strip()
    sc = ma[cM["status"]].map(classify_status)
    m["ma_status"] = sc.map(lambda x: x[0])
    m = m.drop_duplicates("_id")

    lf = ledger.copy()
    lf["_id"] = norm_id(lf[cL["id"]])
    credit = lf[lf[cL["mode"]].astype(str).str.strip().str.lower()
                == cL["mode_credit_value"].lower()].copy()
    credit["ledger_amount"] = norm_amount(
        credit[cL["credit_amount"]].where(
            pd.to_numeric(credit[cL["credit_amount"]], errors="coerce").notna(),
            credit[cL["amount"]],
        )
    )
    lg = (credit.groupby("_id")
               .agg(ledger_amount=("ledger_amount", "first"),
                    ledger_rows=("ledger_amount", "size"))
               .reset_index())

    tctx = get_context(txn, norm_id(txn[cT["id"]]), cT["context"], "Txn ")
    mctx = get_context(ma,  norm_id(ma[cM["id"]]),  cM["context"], "MA ")

    wide = t.merge(m, on="_id", how="outer").merge(lg, on="_id", how="outer")
    wide["in_txn"]    = wide["txn_amount"].notna() | wide["txn_status"].notna()
    wide["in_ma"]     = wide["ma_amount"].notna()  | wide["ma_status"].notna()
    wide["in_ledger"] = wide["ledger_amount"].notna()

    def disp(present, raw):
        if not present:
            return "NA"
        raw = ("" if raw is None else str(raw)).strip()
        return raw if raw else "(blank)"

    results_m, results_e = [], []
    for d in wide.to_dict("records"):
        reasons = []
        in_txn, in_ma, in_ledger = d["in_txn"], d["in_ma"], d["in_ledger"]

        if in_txn and in_ma:
            both_success = d["txn_status"] == "Success" and d["ma_status"] == "Success"
            both_failed  = d["txn_status"] == "Failed"  and d["ma_status"] == "Failed"
            if not both_success and not both_failed:
                reasons.append("MA/Txn status mismatch")
            if not amounts_equal(d["txn_amount"], d["ma_amount"]):
                reasons.append("MA/Txn amount mismatch")
            if both_success:
                if not in_ledger:
                    reasons.append("Success but no point-ledger credit")
                else:
                    if not amounts_equal(d["txn_amount"], d["ledger_amount"]):
                        reasons.append("Ledger amount mismatch")
                    if (d.get("ledger_rows") or 0) > 1:
                        reasons.append("Duplicate ledger credit rows")
            elif both_failed:
                if in_ledger:
                    reasons.append("Failed but credited in point ledger")
        elif in_txn and not in_ma:
            reasons.append("Missing in MA report")
        elif in_ma and not in_txn:
            reasons.append("Missing in transaction report")
        elif in_ledger:
            reasons.append("Credit in point ledger with no transaction record")

        row = {
            "Merchant Txn Id":    d["_id"],
            "Txn Report Status":  disp(in_txn,    d.get("txn_raw")),
            "MA Report Status":   disp(in_ma,     d.get("ma_raw")),
            "Point Ledger Status": "Credited" if in_ledger else "NA",
            "Txn Amount":         d["txn_amount"],
            "MA Amount":          d["ma_amount"],
            "Ledger Amount":      d["ledger_amount"],
        }
        if reasons:
            row["Exception Reason"] = "; ".join(reasons)
        row["Txn Date/Time"] = d.get("txn_datetime", "")
        (results_e if reasons else results_m).append(row)

    def finalize(rows):
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.join(tctx, on="Merchant Txn Id").join(mctx, on="Merchant Txn Id")
        return df.reset_index(drop=True)

    return finalize(results_m), finalize(results_e), None


# ======================================================================
# Stage 2 : Txn (filtered to bank) <-> Bank statement (mode-aware)
# ======================================================================
def build_stage2(txn, bank, selected_bank, bank_cols, financial_types, nonfinancial_types):
    cT = CONFIG["txn"]
    bn = "" if selected_bank is None else str(selected_bank).strip()
    txn_f = txn[txn[cT["bank_name"]].astype(str).str.strip() == bn] if bn else txn

    id_col  = bank_cols["id"]
    amt_col = bank_cols["amount"]
    st_col  = bank_cols["status"]
    ty_col  = bank_cols["type"]
    dt_col  = bank_cols["datetime"]
    date_col = bank_cols["date"]
    time_col = bank_cols["time"]

    fin_set = {str(t).strip().lower() for t in (financial_types  or [])}
    non_set = {str(t).strip().lower() for t in (nonfinancial_types or [])}

    fin = {}
    nonfin_rows = []
    ignored_count = 0
    fin_rows = 0

    for r in bank.to_dict("records"):
        type_val = str("" if r.get(ty_col) is None else r.get(ty_col)).strip()
        tl = type_val.lower()
        if tl in fin_set:
            cat = "financial"
        elif tl in non_set:
            cat = "nonfinancial"
        else:
            cat = "ignored"

        if cat == "nonfinancial":
            nonfin_rows.append(r)
            continue
        if cat == "ignored":
            ignored_count += 1
            continue
        fin_rows += 1
        rid = _nid(r.get(id_col))
        disp, iso = standardize_dt(
            r.get(date_col) if date_col else None,
            r.get(time_col) if time_col else None,
            r.get(dt_col)   if dt_col   else None,
        )
        if rid not in fin:
            fin[rid] = {
                "amount": _namt(r.get(amt_col)),
                "status": classify_bank_status(r.get(st_col)),
                "code":   bank_status_code(r.get(st_col)),
                "dt": disp, "iso": iso, "rows": 1,
            }
        else:
            fin[rid]["rows"] += 1

    rec = {}

    def slot(rid):
        if rid not in rec:
            rec[rid] = {"id": rid, "in_txn": False, "in_bank": False,
                        "txn_amount": None, "txn_status": None,
                        "bank_amount": None, "bank_status": None, "bank_code": "",
                        "bank_dt": "", "bank_rows": 0, "txn_datetime": ""}
        return rec[rid]

    has_dt = cT["datetime"] in txn_f.columns
    for r in txn_f.to_dict("records"):
        s = slot(_nid(r.get(cT["id"])))
        s["in_txn"]       = True
        s["txn_amount"]   = _namt(r.get(cT["amount"]))
        s["txn_status"]   = classify_status(r.get(cT["status"]))[0]
        s["txn_datetime"] = r.get(cT["datetime"], "") if has_dt else ""

    for rid, f in fin.items():
        s = slot(rid)
        s["in_bank"]      = True
        s["bank_amount"]  = f["amount"]
        s["bank_status"]  = f["status"]
        s["bank_code"]    = f["code"]
        s["bank_dt"]      = f["dt"]
        s["bank_rows"]    = f["rows"]

    present_ctx, tctx = ctx_first(txn_f, cT["id"], cT["context"], "Txn ")

    matched, unmatched = [], []
    for rid, d in rec.items():
        reasons = []
        if d["in_txn"] and d["in_bank"]:
            if d["txn_status"] != d["bank_status"]:
                reasons.append("Bank/Txn status mismatch")
            if not amounts_equal(d["txn_amount"], d["bank_amount"]):
                reasons.append("Bank/Txn amount mismatch")
            if d["bank_rows"] > 1:
                reasons.append("Duplicate bank withdrawal rows")
        elif d["in_txn"] and not d["in_bank"]:
            reasons.append("In transaction report, missing in bank statement")
        elif d["in_bank"] and not d["in_txn"]:
            reasons.append("Bank withdrawal not in transaction report")

        row = {
            "Merchant Txn Id":   rid,
            "Txn Status":        d["txn_status"] or "",
            "Bank Status Code":  d["bank_code"]  or "",
            "Bank Status":       d["bank_status"] or "",
            "In Txn Report":     "Y" if d["in_txn"]  else "N",
            "In Bank Statement": "Y" if d["in_bank"] else "N",
            "Txn Amount":        d["txn_amount"],
            "Bank Amount":       d["bank_amount"],
        }
        if reasons:
            row["Exception Reason"] = "; ".join(reasons)
        row["Txn Date/Time"]  = d["txn_datetime"]
        row["Bank Date/Time"] = d["bank_dt"] or ""
        tc = tctx.get(rid, {})
        for c in present_ctx:
            row[f"Txn {c}"] = tc.get(f"Txn {c}")
        (unmatched if reasons else matched).append(row)

    meta = {
        "financialRows":  fin_rows,
        "financialIds":   len(fin),
        "ignored":        ignored_count,
        "nonfinancial":   len(nonfin_rows),
        "bankCols":       bank_cols,
    }
    return (pd.DataFrame(matched), pd.DataFrame(unmatched),
            pd.DataFrame(nonfin_rows) if nonfin_rows else pd.DataFrame(),
            meta)


# ======================================================================
# Stage 3 helpers
# ======================================================================
def detect_icici_header_row(df, max_scan=35):
    """Scan first max_scan rows of a headerless df for recognizable ICICI column header
    keywords. Returns the row index of the header row, or 0 if not found."""
    keywords_norm = [norm_header(k) for k in ICICI_HEADER_KEYWORDS]
    max_row = min(len(df), max_scan)
    best_row = 0
    best_count = 0
    for i in range(max_row):
        row_vals = [norm_header(str(v)) for v in df.iloc[i].tolist()]
        matches = sum(1 for kw in keywords_norm for rv in row_vals if kw in rv and rv != "nan")
        if matches > best_count:
            best_count = matches
            best_row = i
    return best_row if best_count >= 2 else 0


def resolve_icici_columns(headers):
    """Fuzzy-detect amount + datetime columns in ICICI statement.
    If both withdrawal and deposit amount columns are found, they are merged
    into a virtual 'ICICI_Merged_Amount' column at reconciliation time.
    Bank-identifier is always the LAST column — no detection needed."""

    def _res(syns):
        nh = [(h, norm_header(h)) for h in headers]
        for syn in syns:
            ns = norm_header(syn)
            for h, n in nh:
                if n == ns:
                    return h
        for syn in syns:
            ns = norm_header(syn)
            if len(ns) < 4:
                continue
            for h, n in nh:
                if ns in n:
                    return h
        return None

    def _res_all(syns):
        nh = [(h, norm_header(h)) for h in headers]
        results = []
        for syn in syns:
            ns = norm_header(syn)
            for h, n in nh:
                if n == ns:
                    if h not in results:
                        results.append(h)
        for syn in syns:
            ns = norm_header(syn)
            if len(ns) < 4:
                continue
            for h, n in nh:
                if ns in n:
                    if h not in results:
                        results.append(h)
        return results

    amt_cols = _res_all(ICICI_SYNONYMS["amount"])
    dt_col   = _res(ICICI_SYNONYMS["datetime"])
    missing  = []
    if not amt_cols:
        missing.append("amount")

    result = {
        "amount": amt_cols[0] if amt_cols else None,
        "datetime": dt_col,
        "bank_id": headers[-1],
        "missing": missing,
        "_amount_sources": amt_cols if len(amt_cols) > 1 else [],
    }

    return result


def compute_cycles(start_dt, end_dt, n):
    """Divide [start_dt, end_dt) into n equal, gap-free cycles."""
    if n < 1:
        return []
    total_secs = (end_dt - start_dt).total_seconds()
    dur = total_secs / n
    return [(start_dt + timedelta(seconds=i * dur),
             start_dt + timedelta(seconds=(i + 1) * dur))
            for i in range(n)]


def compute_cycles_from_config(cycle_config):
    """Convert a per-cycle config [{startDate, startHHMM, endDate, endHHMM}, ...] into
    a list of (datetime, datetime) tuples.  Empty / incomplete cycles are skipped."""
    cycles = []
    for c in cycle_config.get("cycles", []):
        sd_str = (c.get("startDate") or "").strip()
        ed_str = (c.get("endDate")   or "").strip()
        sh_str = (c.get("startHHMM") or "").strip()
        eh_str = (c.get("endHHMM")   or "").strip()
        if not sd_str or not ed_str or not sh_str or not eh_str:
            continue
        try:
            sd = date.fromisoformat(sd_str)
            ed = date.fromisoformat(ed_str)
            sh, sm = map(int, sh_str.split(":"))
            eh, em = map(int, eh_str.split(":"))
        except (ValueError, TypeError):
            continue
        start_dt = datetime(sd.year, sd.month, sd.day, sh, sm)
        end_dt   = datetime(ed.year, ed.month, ed.day, eh, em)
        cycles.append((start_dt, end_dt))
    return cycles


def get_cycle_config(mode, bank_name):
    """Load per-cycle settlement config for a bank, with defaults for known banks."""
    cfg = load_config()
    bank_config = cfg.get(mode, {}).get(bank_name, {})
    saved = bank_config.get("settlementCycles", {})
    defaults = BANK_DEFAULTS.get(bank_name, {
        "cycleCount": 1,
        "cycles": [{"date": "", "startHHMM": "00:00", "endHHMM": "24:00"}],
    })
    if not saved:
        return dict(defaults)
    return {
        "cycleCount": saved.get("cycleCount", defaults["cycleCount"]),
        "cycles": list(saved.get("cycles", defaults["cycles"])),
    }


def save_cycle_config(mode, bank_name, cycle_cfg):
    """Persist per-cycle settlement config for a bank to recon_config.json."""
    cfg = load_config()
    cfg.setdefault(mode, {})
    cfg[mode].setdefault(bank_name, {})
    cfg[mode][bank_name]["settlementCycles"] = cycle_cfg
    save_config(cfg)


def _parse_dt_flex(val):
    """Parse any datetime representation to a Python datetime; None on failure."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    s = str(val).strip()
    if not s or s.lower() in {"nat", "nan", "none", ""}:
        return None
    try:
        ts = pd.to_datetime(s, dayfirst=True, errors="raise")
        return ts.to_pydatetime()
    except Exception:
        pass
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def build_stage3(settlement_df, settlement_cols,
                 icici_df, icici_cols,
                 selected_bank, cycles, s2u, is_gross=False):
    """
    Cycle-level settlement reconciliation.
    settlement_df   : settlement report for this bank (all sheets merged)
    settlement_cols : detected columns (status, datetime/date+time, amount)
    icici_df        : full ICICI bank statement
    icici_cols      : detected ICICI columns
    cycles          : list of (start_dt, end_dt) datetime pairs
    s2u             : Stage 2 Unmatched DataFrame
    Returns (stage3_df, s2u_updated)
    """
    # ── 1. Settlement report: filter to successful, parse dt + amt ──
    st_col   = settlement_cols.get("status")
    dt_col   = settlement_cols.get("datetime")
    date_col = settlement_cols.get("date")
    time_col = settlement_cols.get("time")
    amt_col  = settlement_cols.get("amount")

    settle = settlement_df.copy()
    if st_col and st_col in settle.columns:
        settle = settle[settle[st_col].apply(
            lambda v: classify_bank_status(v) == "Success")].copy()

    def _settle_dt(row):
        if dt_col and dt_col in row:
            return _parse_dt_flex(row.get(dt_col))
        ds = str(row.get(date_col, "") or "")
        ts = str(row.get(time_col, "") or "")
        return _parse_dt_flex(f"{ds} {ts}".strip())

    settle["_dt"] = settle.apply(_settle_dt, axis=1)

    if is_gross and amt_col:
        def _calc_net(a_val):
            a = _namt(a_val) or 0.0
            b = min(0.005 * a, 15.0)   # Airpay commission: 0.5% of A or ₹15, whichever lower
            c = 0.10 * b               # Bank charges: 10% of B
            d = b - c                  # Net commission: B − C
            e = 0.02 * d               # TDS: 2% of D
            return round(a + d - e, 2) # Settlement amount: A + D − E
        settle["_amt"] = settle[amt_col].apply(_calc_net)
    else:
        settle["_amt"] = settle[amt_col].apply(_namt) if amt_col else 0.0

    # ── 2. ICICI: merge dual amount cols if detected, filter to this bank ──
    icici_amt_col = icici_cols["amount"]
    icici_dt_col  = icici_cols.get("datetime")
    icici_id_col  = icici_cols["bank_id"]

    _amt_sources = icici_cols.get("_amount_sources", [])
    if len(_amt_sources) > 1:
        MERGED = "ICICI_Merged_Amount"
        icici_df[MERGED] = icici_df[_amt_sources[0]].apply(_namt)
        for src in _amt_sources[1:]:
            icici_df[MERGED] = icici_df[MERGED].fillna(icici_df[src].apply(_namt))
        icici_amt_col = MERGED

    # Match selected_bank against ICICI label column.
    # Bidirectional: bank words checked against label AND label words checked
    # against bank name — handles mismatches like "Fino bank" vs "Fino settlement".
    _SKIP = {"bank", "ltd", "limited", "pvt", "private", "co", "finance",
             "settlement", "payment", "payments", "technologies"}
    bank_norm = re.sub(r"[^a-z0-9]", "", selected_bank.lower())
    bank_words = [w for w in re.sub(r"[^a-z0-9 ]", "", selected_bank.lower()).split()
                  if w not in _SKIP and len(w) >= 3]

    def _icici_match(val):
        s = str(val)
        if not s or s.lower() in {"nan", "none", ""}:
            return False
        label_norm  = re.sub(r"[^a-z0-9]", "", s.lower())
        label_words = [w for w in re.sub(r"[^a-z0-9 ]", "", s.lower()).split()
                       if w not in _SKIP and len(w) >= 3]
        # bank word appears in ICICI label
        if any(w in label_norm for w in bank_words):
            return True
        # ICICI label word appears in bank name
        if any(w in bank_norm for w in label_words):
            return True
        return False

    if icici_id_col and icici_id_col in icici_df.columns:
        icici_bank = icici_df[icici_df[icici_id_col].apply(_icici_match)].copy()
    else:
        icici_bank = pd.DataFrame(columns=icici_df.columns)
    if icici_bank.empty:
        icici_bank = pd.DataFrame(columns=icici_df.columns)

    if icici_dt_col and icici_dt_col in icici_bank.columns:
        icici_bank["_dt"] = icici_bank[icici_dt_col].apply(_parse_dt_flex)
        icici_bank = icici_bank.sort_values("_dt").reset_index(drop=True)
    else:
        icici_bank = icici_bank.reset_index(drop=True)

    # ── 3. Per-cycle: sum settlement amounts, map ICICI CHRONOLOGICALLY ──
    # Cycles run in order; this bank's ICICI settlement entries are ordered by
    # S.N. (verified: S.N. order == chronological order for every bank).
    # Cycle i binds to the i-th entry, one-to-one, each entry consumed once.
    #
    # Nearest-time matching is deliberately NOT used: a settlement can post hours
    # after its own cutoff (NSDL cycle 4 closes 17:30 but posts 21:32), so a
    # closest-in-time rule can pull an entry into the wrong cycle.
    _sn_col = None
    for _c in icici_bank.columns:
        if norm_header(_c) in ("sn", "sno", "srno", "serialno", "slno"):
            _sn_col = _c
            break

    if not icici_bank.empty:
        if _sn_col:
            icici_bank["_sn"] = pd.to_numeric(icici_bank[_sn_col], errors="coerce")
            icici_bank = icici_bank.sort_values("_sn").reset_index(drop=True)
        elif "_dt" in icici_bank.columns:
            icici_bank = icici_bank.sort_values("_dt").reset_index(drop=True)

    def _icici_at(i):
        """i-th ICICI entry for this bank, in S.N. (chronological) order."""
        if icici_bank.empty or i >= len(icici_bank):
            return None, "", ""
        irow = icici_bank.loc[i]
        amt  = _namt(irow.get(icici_amt_col))
        dts  = ""
        if icici_dt_col and icici_dt_col in irow.index:
            dts = str(irow.get(icici_dt_col, ""))
        sn = ""
        if _sn_col:
            sv = irow.get("_sn")
            sn = "" if pd.isna(sv) else int(sv)
        return amt, dts, sn

    cycle_rows = []
    for i, (c_start, c_end) in enumerate(cycles):
        # Settlement sum for this cycle
        mask_s = settle["_dt"].apply(
            lambda d: d is not None and c_start <= d < c_end)
        cycle_settle  = settle[mask_s]
        settle_total  = round(float(cycle_settle["_amt"].fillna(0).sum()), 2)
        settle_count  = len(cycle_settle)

        icici_amount, icici_dt_str, icici_sn = _icici_at(i)

        diff   = None
        status = "No ICICI entry"
        if icici_amount is not None:
            diff   = round(settle_total - icici_amount, 2)
            status = "Matched" if abs(diff) <= STAGE3_TOLERANCE else "Mismatch"
        elif settle_count > 0:
            status = "Post period (settles next cycle)"

        cycle_rows.append({
            "Cycle":                 i + 1,
            "Cycle Start":           c_start.strftime("%d-%m-%Y %H:%M"),
            "Cycle End":             c_end.strftime("%d-%m-%Y %H:%M"),
            "Settlement Txn Count":  settle_count,
            "Settlement Total":      settle_total,
            "ICICI S.N.":            icici_sn,
            "ICICI Amount":          icici_amount,
            "ICICI Date":            icici_dt_str,
            "Difference":            diff,
            "Status":                status,
        })

    # ICICI settlement entries with no corresponding cycle -> surfaced, not silently dropped
    for j in range(len(cycles), len(icici_bank)):
        icici_amount, icici_dt_str, icici_sn = _icici_at(j)
        cycle_rows.append({
            "Cycle":                 j + 1,
            "Cycle Start":           "",
            "Cycle End":             "",
            "Settlement Txn Count":  0,
            "Settlement Total":      None,
            "ICICI S.N.":            icici_sn,
            "ICICI Amount":          icici_amount,
            "ICICI Date":            icici_dt_str,
            "Difference":            None,
            "Status":                "Settlement with no matching cycle",
        })

    stage3_df = pd.DataFrame(cycle_rows)

    # ── 4. Update Stage 2 Unmatched exception reasons ──
    s2u_updated = s2u.copy()
    if not s2u_updated.empty and cycles:
        first_start = cycles[0][0]
        last_end    = cycles[-1][1]
        if "Txn Date/Time" in s2u_updated.columns:
            s2u_updated["_txn_dt"] = s2u_updated["Txn Date/Time"].apply(_parse_dt_flex)
        if "Bank Date/Time" in s2u_updated.columns:
            s2u_updated["_bank_dt"] = s2u_updated["Bank Date/Time"].apply(_parse_dt_flex)

        def _upd(row):
            reason = str(row.get("Exception Reason", "") or "")
            rl = reason.lower()
            if "missing in bank statement" in rl:
                dt = row.get("_txn_dt")
                if dt is not None and dt >= last_end:
                    return "Post period transaction"
            elif "bank withdrawal not in transaction report" in rl:
                dt = row.get("_bank_dt")
                if dt is not None and dt < first_start:
                    return "Prior period transaction"
            return reason

        s2u_updated["Exception Reason"] = s2u_updated.apply(_upd, axis=1)
        s2u_updated = s2u_updated.drop(
            columns=[c for c in ("_txn_dt", "_bank_dt") if c in s2u_updated.columns])

    return stage3_df, s2u_updated


# ======================================================================
# Summary
# ======================================================================
def status_counts(df, col):
    if col not in df.columns:
        return {"Success": 0, "Failed": 0, "Incomplete (within Failed)": 0}
    sc   = df[col].map(classify_status)
    canon = sc.map(lambda x: x[0])
    inc   = sc.map(lambda x: x[1] == "Incomplete").sum()
    out   = {"Success": 0, "Failed": 0}
    out.update(canon.value_counts().to_dict())
    out["Incomplete (within Failed)"] = int(inc)
    return out


def reason_breakdown(unmatched):
    if unmatched is None or unmatched.empty or "Exception Reason" not in unmatched.columns:
        return {}
    exploded = (unmatched["Exception Reason"].fillna("")
                .str.split(";").explode().str.strip())
    return exploded[exploded != ""].value_counts().to_dict()


def build_summary(txn, ma, ledger, bank, s1m, s1e, s2m, s2u, nonfin, meta,
                  files, selected_bank, mode):
    cT, cM  = CONFIG["txn"], CONFIG["ma"]
    bn       = selected_bank or ""
    bank_cols = meta.get("bankCols", {})
    txn_bank  = (txn[txn[cT["bank_name"]].astype(str).str.strip() == bn]
                 if bn else txn)

    rows = []

    def R(a, b=""):
        rows.append((a, b))

    R("AIRPAY RECONCILIATION SUMMARY")
    R("Generated",              datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    R("Reconciliation mode",    mode or "AEPS")
    R("Stage 2 bank filter",    bn or "(all banks)")
    R("")
    R("SOURCE FILES")
    for k, v in files.items():
        R(f"  {k}", v)
    R("")
    R("SOURCE RECORD COUNTS")
    R("  Transaction report rows", len(txn))
    R("  MA report rows",          len(ma))
    R("  Point ledger rows",       len(ledger))
    R("  Bank statement rows",     len(bank))
    R("")
    R("STATUS MIX (transaction report)", str(status_counts(txn, cT["status"])))
    R("STATUS MIX (MA report)",          str(status_counts(ma,  cM["status"])))
    detected = {
        "id":     bank_cols.get("id"),
        "amount": bank_cols.get("amount"),
        "status": bank_cols.get("status"),
        "type":   bank_cols.get("type"),
        "datetime": bank_cols.get("datetime")
                    or f"{bank_cols.get('date') or ''} + {bank_cols.get('time') or ''}",
    }
    R("BANK COLUMNS DETECTED", str(detected))
    R("")
    R("STAGE 1  —  Txn <-> MA <-> Point ledger")
    R("  Transactions evaluated",       len(s1m) + len(s1e))
    R("  Matched (clean)",              len(s1m))
    R("  Exceptions (manual review)",   len(s1e))
    for reason, n in reason_breakdown(s1e).items():
        R(f"    - {reason}", n)
    R("")
    R("STAGE 2  —  %s  ·  Txn (Bank Name = %s)  <->  Bank statement"
      % (mode or "AEPS", bn or "all banks"))
    R("  Transaction rows for this bank",              len(txn_bank))
    R("  Bank financial rows (this mode)",             meta.get("financialRows", 0))
    R("  Bank rows ignored (other mode)",              meta.get("ignored", 0))
    R("  Keys evaluated",                              len(s2m) + len(s2u))
    R("  Matched",                                     len(s2m))
    R("  Unmatched / flagged",                         len(s2u))
    for reason, n in reason_breakdown(s2u).items():
        R(f"    - {reason}", n)
    if not s2u.empty and "Exception Reason" in s2u.columns:
        miss = s2u[s2u["Exception Reason"].fillna("").str.contains(
            "missing in bank statement", na=False)]
        if not miss.empty:
            R("      (missing-in-bank, by txn status)",
              str(miss["Txn Status"].value_counts().to_dict()))
    R("  Bank non-financial rows", len(nonfin))
    type_col = bank_cols.get("type")
    if type_col and not nonfin.empty and type_col in nonfin.columns:
        for tt, n in nonfin[type_col].value_counts().items():
            R(f"    - {tt}", int(n))

    return pd.DataFrame(rows, columns=["Metric", "Value"])


# ======================================================================
# Excel writer  (writes to a BytesIO buffer for Streamlit download)
# ======================================================================
def write_workbook(buf, sheets, summary_df):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl import load_workbook

    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        summary_df.to_excel(xl, sheet_name="Summary", index=False, header=False)
        for name, df in sheets.items():
            (df if not df.empty else pd.DataFrame({"(none)": []})).to_excel(
                xl, sheet_name=name, index=False
            )

    buf.seek(0)
    wb = load_workbook(buf)

    head_fill  = PatternFill("solid", fgColor="1F3864")
    head_font  = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    base_font  = Font(name="Arial", size=10)
    flag_fill  = PatternFill("solid", fgColor="FCE4D6")

    ws = wb["Summary"]
    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 60
    for row in ws.iter_rows():
        for c in row:
            c.font      = base_font
            c.alignment = Alignment(vertical="center", wrap_text=False)
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value or ""
        if a and not a.startswith("  ") and a == a.upper():
            ws.cell(r, 1).font = Font(name="Arial", bold=True, size=10, color="1F3864")

    for name, df in sheets.items():
        ws = wb[name]
        if ws.max_row < 1:
            continue
        for c in ws[1]:
            c.fill, c.font = head_fill, head_font
            c.alignment = Alignment(horizontal="center", vertical="center")
        ws.freeze_panes = "A2"
        ncols = ws.max_column
        ws.auto_filter.ref = f"A1:{get_column_letter(ncols)}{ws.max_row}"
        for ci in range(1, ncols + 1):
            col    = get_column_letter(ci)
            header = str(ws.cell(1, ci).value or "")
            ws.column_dimensions[col].width = min(max(len(header) + 2, 12), 40)
        headers = [str(c.value) for c in ws[1]]
        if "Exception Reason" in headers:
            idx = headers.index("Exception Reason") + 1
            for r in range(2, ws.max_row + 1):
                if ws.cell(r, idx).value:
                    ws.cell(r, idx).fill = flag_fill
                    ws.cell(r, idx).font = Font(name="Arial", size=10, color="9C2500")
        for r in range(2, ws.max_row + 1):
            for ci in range(1, ncols + 1):
                cell = ws.cell(r, ci)
                if not cell.font or cell.font.name != "Arial":
                    cell.font = base_font

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


# ======================================================================
# Streamlit UI
# ======================================================================
CAT_OPTIONS = ["Financial", "Non-Financial", "Ignored"]
CAT_DEFAULT = {"financial": "Financial", "nonFinancial": "Non-Financial", "ignored": "Ignored"}


def _cat_label(assign, t):
    if t in assign["financial"]:     return "Financial"
    if t in assign["nonFinancial"]:  return "Non-Financial"
    if t in assign["ignored"]:       return "Ignored"
    return "Ignored"


def main():
    st.set_page_config(
        page_title="Airpay Reconciliation",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # ── Minimal sidebar ──
    with st.sidebar:
        st.markdown("## Airpay Recon")
        st.caption("Two-stage + settlement reconciliation engine")

    # ── Title ──
    st.title("📊 Airpay Reconciliation Engine")
    st.caption(
        "**Stage 1** — Txn Report ↔ MA Report ↔ Point Ledger  |  "
        "**Stage 2** — Txn Report ↔ Bank Statement (per bank · per mode)  |  "
        "**Stage 3** — Cycle-level Bank Total ↔ ICICI Settlement"
    )

    # ── Step 1: Mode + Common Reports ──
    st.header("1 · Mode & Common Reports")

    mode = st.selectbox("Reconciliation Mode", list(MODES.keys()), key="mode")

    txn_file    = st.file_uploader("Transaction Report (.xlsx)", type=["xlsx", "xls"], key="f_txn")
    ma_file     = st.file_uploader("MA Report (.csv)",           type=["csv"],          key="f_ma")
    ledger_file = st.file_uploader("Point Ledger (.xlsx)",       type=["xlsx", "xls"], key="f_ledger")

    # ── Step 2: Select Bank ──
    txn = None
    selected_bank = ""

    if txn_file:
        try:
            txn_file.seek(0)
            txn = load_uploaded(txn_file)
            bn_col = CONFIG["txn"]["bank_name"]
            if bn_col in txn.columns:
                bank_names = sorted(txn[bn_col].astype(str).str.strip().unique())
                st.header("2 · Select Bank")
                selected_bank = st.selectbox(
                    "Bank Name (from transaction report)", bank_names, key="sel_bank"
                )
            else:
                st.error(f"Column '{bn_col}' not found in transaction report. "
                         f"Columns found: {list(txn.columns)}")
        except Exception as e:
            st.error(f"Could not read transaction report: {e}")
            txn = None

    # ── Step 3: Settlement Cycles (per bank, manual input) ──
    cycles = []
    cycle_parse_ok = False

    if selected_bank:
        st.header("3 · Settlement Cycles")
        cycle_config = get_cycle_config(mode, selected_bank)

        st.caption(f"Define settlement cycles for **{selected_bank}** ({mode})")

        def _parse_hhmm(s):
            try:
                h, m = map(int, str(s).strip().split(":"))
                return h, m
            except Exception:
                return None

        n_cycles = st.number_input(
            "Number of settlement cycles", min_value=1, max_value=24,
            value=cycle_config.get("cycleCount", 1), step=1, key="n_cycles",
        )

        nc = int(n_cycles)
        saved_cycles = cycle_config.get("cycles", [])
        default_entry = {
            "startDate": date.today().isoformat(), "startHHMM": "00:00",
            "endDate":   date.today().isoformat(), "endHHMM":   "24:00",
        }

        while len(saved_cycles) < nc:
            saved_cycles.append(default_entry.copy())
        saved_cycles = saved_cycles[:nc]

        new_cycles_data = []
        all_valid = True

        for i in range(nc):
            sc = saved_cycles[i] if i < len(saved_cycles) else default_entry.copy()
            try:
                def_sdate = date.fromisoformat(sc.get("startDate", "") or "")
            except (ValueError, TypeError):
                def_sdate = date.today()
            try:
                def_edate = date.fromisoformat(sc.get("endDate", "") or "")
            except (ValueError, TypeError):
                def_edate = date.today()

            st.markdown(f"**Cycle {i+1}**")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                cd_start = st.date_input("Start Date", value=def_sdate, key=f"cycle_sdate_{i}")
            with c2:
                st_hhmm = st.text_input("Start (HH:MM)", value=sc.get("startHHMM", "00:00"), key=f"cycle_start_{i}")
            with c3:
                cd_end = st.date_input("End Date", value=def_edate, key=f"cycle_edate_{i}")
            with c4:
                ed_hhmm = st.text_input("End (HH:MM)", value=sc.get("endHHMM", "24:00"), key=f"cycle_end_{i}")

            sh = _parse_hhmm(st_hhmm)
            eh = _parse_hhmm(ed_hhmm)
            cycle_ok = bool(sh and eh)

            if cycle_ok:
                start_dt = datetime(cd_start.year, cd_start.month, cd_start.day, sh[0], sh[1])
                end_dt   = datetime(cd_end.year,   cd_end.month,   cd_end.day,   eh[0], eh[1])
                st.caption(
                    f"  → {start_dt.strftime('%d-%m-%Y %H:%M')}  to  "
                    f"{end_dt.strftime('%d-%m-%Y %H:%M')}"
                )
            else:
                st.caption("  → (enter valid Start/End dates and HH:MM times)")
                all_valid = False

            new_cycles_data.append({
                "startDate": cd_start.isoformat(),
                "startHHMM": st_hhmm.strip(),
                "endDate":   cd_end.isoformat(),
                "endHHMM":   ed_hhmm.strip(),
            })

        if all_valid and nc > 0:
            cycles = compute_cycles_from_config({"cycles": new_cycles_data})
            cycle_parse_ok = True

            new_config = {"cycleCount": nc, "cycles": new_cycles_data}
            if new_config != cycle_config:
                save_cycle_config(mode, selected_bank, new_config)

    # ── Step 4: Bank Statement ──
    bank      = None
    bank_cols = None
    assign    = None

    if selected_bank:
        st.header("4 · Bank Statement")
        bank_file = st.file_uploader(
            f"Upload statement for **{selected_bank}** (.csv or .xlsx)",
            type=["csv", "xlsx", "xls"], key="f_bank",
        )

        if bank_file:
            try:
                bank_file.seek(0)
                bank      = load_uploaded(bank_file)
                bank_cols = resolve_bank_columns(list(bank.columns))

                if bank_cols["missing"]:
                    st.error(
                        f"Could not auto-detect column(s): **{bank_cols['missing']}**\n\n"
                        f"Bank statement headers found: `{list(bank.columns)}`\n\n"
                        "Add the correct synonym to `BANK_SYNONYMS` in the script, or rename the column."
                    )
                else:
                    dt_label = (bank_cols["datetime"]
                                or f"{bank_cols['date']} + {bank_cols['time']}")
                    st.success("All columns auto-detected ✓")
                    dc1, dc2, dc3, dc4, dc5 = st.columns(5)
                    dc1.metric("ID column",       bank_cols["id"])
                    dc2.metric("Amount column",   bank_cols["amount"])
                    dc3.metric("Status column",   bank_cols["status"])
                    dc4.metric("Type column",     bank_cols["type"])
                    dc5.metric("DateTime column", dt_label)

            except Exception as e:
                st.error(f"Could not read bank statement: {e}")
                bank = None

    # ── Step 5: Type Classification ──
    if bank is not None and bank_cols is not None and not bank_cols["missing"]:
        type_col = bank_cols.get("type")
        if type_col:
            bk     = selected_bank.strip() if selected_bank else "(all banks)"
            cfg    = load_config()
            saved  = (cfg.get(mode, {}) or {}).get(bk, {})
            types  = get_bank_types(bank, type_col)
            assign = build_type_assignment(types, mode, saved)

            st.header("5 · Transaction Type Classification")

            if assign["flagged"]:
                st.warning(
                    f"**{len(assign['flagged'])} unrecognized type(s)** found in the bank statement. "
                    "Classify each below before running."
                )

            all_types = (assign["financial"] + assign["nonFinancial"] +
                         assign["ignored"]   + assign["flagged"])

            if all_types:
                st.markdown("Adjust any category if needed — saved assignments are pre-filled.")
                user_assign = {"financial": set(assign["financial"]),
                               "nonFinancial": set(assign["nonFinancial"]),
                               "ignored": set(assign["ignored"])}

                rows_ui = []
                for t in all_types:
                    default_cat = _cat_label(assign, t)
                    badge = "🔴 Unrecognized" if t in assign["flagged"] else ""
                    rows_ui.append((t, default_cat, badge))

                hdr1, hdr2, hdr3 = st.columns([4, 2, 2])
                hdr1.markdown("**Transaction Type**")
                hdr2.markdown("**Category**")
                hdr3.markdown("")
                st.divider()

                final_assign = {"financial": [], "nonFinancial": [], "ignored": []}
                for (t, default_cat, badge) in rows_ui:
                    col_t, col_sel, col_badge = st.columns([4, 2, 2])
                    with col_t:
                        st.markdown(f"`{t}`")
                    with col_sel:
                        chosen = st.selectbox(
                            f"cat_{t}",
                            CAT_OPTIONS,
                            index=CAT_OPTIONS.index(default_cat),
                            label_visibility="collapsed",
                            key=f"type_{t}",
                        )
                    with col_badge:
                        if badge:
                            st.markdown(badge)

                    key_map = {"Financial": "financial",
                               "Non-Financial": "nonFinancial",
                               "Ignored": "ignored"}
                    final_assign[key_map[chosen]].append(t)

                assign = {**final_assign, "flagged": []}

    # ── Step 6: Settlement Report (Stage 3 — optional) ──
    settle_df   = None
    settle_cols = None
    settle_file = None
    is_gross    = False

    if selected_bank:
        st.header("6 · Settlement Report (Stage 3 — optional)")
        settle_file = st.file_uploader(
            f"Upload settlement report for **{selected_bank}** (.csv or .xlsx — multi-tab Excel auto-merged)",
            type=["csv", "xlsx", "xls"], key="f_settle",
        )

        if settle_file:
            try:
                settle_file.seek(0)
                settle_df   = load_settlement_report(settle_file)
                settle_cols = resolve_settlement_columns(list(settle_df.columns))

                if settle_cols["missing"]:
                    st.error(
                        f"Could not detect settlement column(s): **{settle_cols['missing']}**\n\n"
                        f"Headers found: `{list(settle_df.columns)}`"
                    )
                else:
                    dt_label = (settle_cols["datetime"]
                                or f"{settle_cols['date']} + {settle_cols['time']}")
                    st.success("Settlement report columns detected ✓")
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("Amount column",   settle_cols["amount"])
                    sc2.metric("Status column",   settle_cols.get("status") or "(not found — all rows used)")
                    sc3.metric("DateTime column", dt_label)
                    st.caption(f"{len(settle_df)} rows loaded (all sheets merged if multi-tab)")

                    is_gross = st.checkbox(
                        "Amount column is **GROSS** — calculate net settlement using Airpay formula"
                        "  ·  B = min(0.5%×A, ₹15)  ·  C = 10%×B  ·  D = B−C  ·  E = 2%×D  ·  **F = A+D−E**",
                        key="settle_is_gross",
                    )
            except Exception as e:
                st.error(f"Could not read settlement report: {e}")
                settle_df = None

    # ── Step 7: ICICI Statement (Stage 3 — optional) ──
    icici_df   = None
    icici_cols = None

    st.header("7 · ICICI Statement (Stage 3 — optional)")
    icici_file = st.file_uploader(
        "ICICI Statement (.csv or .xlsx)", type=["csv", "xlsx", "xls"], key="f_icici"
    )

    if icici_file:
        try:
            icici_file.seek(0)
            icici_df   = load_uploaded(icici_file)
            icici_cols = resolve_icici_columns(list(icici_df.columns))

            if icici_cols["missing"]:
                st.error(
                    f"Could not detect ICICI column(s): **{icici_cols['missing']}**\n\n"
                    f"Headers found: `{list(icici_df.columns)}`"
                )
            else:
                i1, i2, i3 = st.columns(3)
                amt_label = icici_cols["amount"]
                if icici_cols.get("_amount_sources"):
                    amt_label = f"{amt_label} (+ {', '.join(icici_cols['_amount_sources'][1:])})"
                i1.metric("Amount column",   amt_label)
                i2.metric("DateTime column", icici_cols.get("datetime") or "(not found — order used)")
                i3.metric("Bank ID column",  icici_cols["bank_id"])
                if not icici_cols.get("datetime"):
                    st.warning(
                        "No datetime column detected in ICICI statement — "
                        "ICICI entries will be matched to cycles by row order."
                    )
        except Exception as e:
            st.error(f"Could not read ICICI statement: {e}")
            icici_df = None

    # ── Step 7: Run ──
    st.header("8 · Run Reconciliation")

    stage3_ready = (settle_df is not None and settle_cols is not None and
                    not settle_cols.get("missing") and
                    icici_df is not None and icici_cols is not None and
                    not icici_cols.get("missing") and
                    cycle_parse_ok and len(cycles) > 0)

    all_ready = (txn is not None and ma_file is not None and
                 ledger_file is not None and bank is not None and
                 bank_cols is not None and not bank_cols.get("missing") and
                 assign is not None)

    if not all_ready:
        missing_items = []
        if txn is None:      missing_items.append("Transaction Report (Step 1)")
        if not ma_file:      missing_items.append("MA Report (Step 1)")
        if not ledger_file:  missing_items.append("Point Ledger (Step 1)")
        if not selected_bank: missing_items.append("Bank selection (Step 2)")
        elif bank is None:    missing_items.append(f"Bank Statement for {selected_bank} (Step 4)")
        elif bank_cols and bank_cols.get("missing"):
            missing_items.append("Bank column mapping (Step 4)")
        if missing_items:
            st.info(f"Waiting for: {' · '.join(missing_items)}")

    if all_ready and not stage3_ready:
        reasons = []
        if not (settle_df is not None and settle_cols is not None and not settle_cols.get("missing")):
            reasons.append("Settlement Report (Step 6)")
        if not (icici_df is not None and icici_cols is not None and not icici_cols.get("missing")):
            reasons.append("ICICI Statement (Step 7)")
        if not (cycle_parse_ok and len(cycles) > 0):
            reasons.append("Settlement cycle config (Step 3)")
        if reasons:
            st.info(f"Stage 3 will be skipped — missing: {' · '.join(reasons)}")

    run_btn = st.button("▶ Run Reconciliation", type="primary", disabled=not all_ready)

    # ── Results ──
    if run_btn:
        try:
            ma_file.seek(0);     ma     = load_uploaded(ma_file)
            ledger_file.seek(0); ledger = load_uploaded(ledger_file)
            txn_file.seek(0);    txn    = load_uploaded(txn_file)

            with st.spinner("Running Stage 1 — Txn ↔ MA ↔ Point Ledger …"):
                s1m, s1e, _ = build_stage1(txn, ma, ledger)

            with st.spinner(f"Running Stage 2 — {selected_bank} · {mode} …"):
                s2m, s2u, nonfin, meta = build_stage2(
                    txn, bank, selected_bank, bank_cols,
                    assign["financial"], assign["nonFinancial"],
                )

            stage3_df   = pd.DataFrame()
            s2u_display = s2u

            if stage3_ready:
                with st.spinner(
                    f"Running Stage 3 — {len(cycles)} cycle(s) · "
                    f"{selected_bank} ↔ ICICI …"
                ):
                    settle_file.seek(0)
                    settle_raw = load_settlement_report(settle_file)
                    stage3_df, s2u_display = build_stage3(
                        settle_raw, settle_cols,
                        icici_df, icici_cols,
                        selected_bank, cycles, s2u,
                        is_gross=is_gross,
                    )

            # Persist type assignments
            cfg_out = load_config()
            bk = selected_bank.strip() if selected_bank else "(all banks)"
            cfg_out.setdefault(mode, {})
            cfg_out[mode][bk] = {
                "financial":    assign["financial"],
                "nonFinancial": assign["nonFinancial"],
                "ignored":      assign["ignored"],
            }
            save_config(cfg_out)

            files_map = {
                "Transaction Report": txn_file.name,
                "MA Report":          ma_file.name,
                "Point Ledger":       ledger_file.name,
                "Bank Statement":     bank_file.name,
            }
            if settle_file:
                files_map["Settlement Report"] = settle_file.name
            if icici_file:
                files_map["ICICI Statement"] = icici_file.name

            summary = build_summary(txn, ma, ledger, bank,
                                    s1m, s1e, s2m, s2u_display, nonfin, meta,
                                    files_map, selected_bank, mode)

            # ── Metric cards ──
            st.header("Results")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Stage 1 Matched",    len(s1m))
            m2.metric("Stage 1 Exceptions", len(s1e))
            m3.metric("Stage 2 Matched",    len(s2m))
            m4.metric("Stage 2 Unmatched",  len(s2u_display))

            m5, m6, m7 = st.columns(3)
            m5.metric("Bank Financial rows",     meta.get("financialRows", 0))
            m6.metric("Bank Ignored rows",       meta.get("ignored", 0))
            m7.metric("Bank Non-financial rows", meta.get("nonfinancial", 0))

            if stage3_ready and not stage3_df.empty:
                st.subheader("Stage 3 — Settlement Cycle Summary")
                matched_cycles   = (stage3_df["Status"] == "Matched").sum()
                mismatch_cycles  = (stage3_df["Status"] == "Mismatch").sum()
                other_cycles     = len(stage3_df) - matched_cycles - mismatch_cycles
                net_var = pd.to_numeric(stage3_df["Difference"], errors="coerce").sum()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cycles Matched",   int(matched_cycles))
                c2.metric("Cycles Mismatch",  int(mismatch_cycles))
                c3.metric("Post/Unmatched",   int(other_cycles))
                c4.metric("Net Variance", f"{net_var:,.2f}")

                def _color_status(val):
                    if val == "Matched":   return "background-color:#d4edda; color:#155724"
                    if val == "Mismatch":  return "background-color:#f8d7da; color:#721c24"
                    return "background-color:#fff3cd; color:#856404"   # post-period / no-cycle

                st.dataframe(
                    stage3_df.style.map(_color_status, subset=["Status"]),
                    use_container_width=True, hide_index=True,
                )

            # ── Build workbook ──
            with st.spinner("Building output workbook …"):
                sheets = {
                    "Stage1_Matched":    s1m,
                    "Stage1_Exceptions": s1e,
                    "Stage2_Matched":    s2m,
                    "Stage2_Unmatched":  s2u_display,
                    "Bank_NonFinancial": nonfin,
                }
                if not stage3_df.empty:
                    sheets["Stage3_Settlement"] = stage3_df

                buf     = io.BytesIO()
                out_buf = write_workbook(buf, sheets, summary)

            stamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
            mode_safe = re.sub(r"[^A-Za-z0-9]+", "_", mode).strip("_")
            bank_safe = re.sub(r"[^A-Za-z0-9]+", "_", selected_bank).strip("_") or "bank"
            fname     = f"reconciliation_{bank_safe}_{mode_safe}_{stamp}.xlsx"

            st.download_button(
                label="⬇️ Download Output Workbook",
                data=out_buf,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            with st.expander("Full Summary"):
                st.dataframe(summary, use_container_width=True, hide_index=True)

            if not s1e.empty:
                with st.expander(f"Stage 1 Exceptions ({len(s1e)} rows)"):
                    st.dataframe(s1e, use_container_width=True, hide_index=True)

            if not s2u_display.empty:
                with st.expander(f"Stage 2 Unmatched ({len(s2u_display)} rows)"):
                    st.dataframe(s2u_display, use_container_width=True, hide_index=True)

        except Exception as e:
            import traceback
            st.error(f"Reconciliation failed: {e}")
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
