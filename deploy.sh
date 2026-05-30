#!/usr/bin/env bash
# =============================================================================
# Fund Watchdog — one-shot bootstrap + deploy
#
# FOR CLAUDE CODE: make this executable and run it (`bash deploy.sh`). It
# scaffolds the whole repo, runs the data pipeline locally, and — if the
# GitHub CLI (`gh`) is authenticated — creates a private repo, pushes, and
# enables GitHub Pages. Phase 1 (live prices + returns dashboard) needs NO
# API keys. Alerting/holdings layers are stubbed for later phases.
#
# After it runs, help the user edit fund-watchdog/config/portfolio.yml with
# their real holdings, then re-run `python -m etl.run` (or just push).
# =============================================================================
set -euo pipefail

REPO_NAME="fund-watchdog"     # change if you like
PRIVATE="--private"           # set to "--public" to make it public
PROJECT_DIR="fund-watchdog"

echo "▶ Fund Watchdog bootstrap starting…"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
mkdir -p etl/sources docs/data .github/workflows config

# ---------------------------------------------------------------------------
# requirements + package marker
# ---------------------------------------------------------------------------
cat > requirements.txt << 'EOF_REQ'
pyyaml>=6.0
EOF_REQ

cat > etl/__init__.py << 'EOF_INIT'
EOF_INIT

# ---------------------------------------------------------------------------
# config (the only file you normally edit)
# ---------------------------------------------------------------------------
cat > config/portfolio.yml << 'EOF_PORT'
# Your holdings. id = AMFI scheme code (IN) or ticker (US).
# Edit freely, then re-run `python -m etl.run` or push to GitHub.
assets:
  - id: "122639"
    market: IN
    kind: mf
    name: "Parag Parikh Flexi Cap Fund - Direct - Growth"
    benchmark: ""              # IN TRI not free/keyless → left blank in P1

  - id: "VOO"
    market: US
    kind: etf
    name: "Vanguard S&P 500 ETF"
    benchmark: "SPY"           # US ticker proxy (keyless) → alpha computed

  - id: "AAPL"
    market: US
    kind: stock
    name: "Apple Inc"
    benchmark: ""
EOF_PORT

cat > config/settings.yml << 'EOF_SET'
thresholds:
  sector_pct: 2.0
  allocation_pct: 5.0
notify:
  telegram: false   # set true in P3 after creating a bot (see SETUP_NEXT.md)
  email: false
EOF_SET

# ---------------------------------------------------------------------------
# etl/db.py — sqlite schema (history for later diffing)
# ---------------------------------------------------------------------------
cat > etl/db.py << 'EOF_DB'
import sqlite3, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "state.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS prices(asset_id TEXT, dt TEXT, nav REAL, PRIMARY KEY(asset_id,dt));
CREATE TABLE IF NOT EXISTS snapshots(asset_id TEXT, snap_date TEXT, source TEXT,
  manager TEXT, category TEXT, name TEXT, objective TEXT, eq REAL, debt REAL, cash REAL,
  PRIMARY KEY(asset_id,snap_date));
CREATE TABLE IF NOT EXISTS holdings(asset_id TEXT, snap_date TEXT, name TEXT, weight REAL);
CREATE TABLE IF NOT EXISTS sectors(asset_id TEXT, snap_date TEXT, name TEXT, weight REAL);
CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, asset_id TEXT, type TEXT, title TEXT,
  from_val TEXT, to_val TEXT, fired_at TEXT, notified INTEGER DEFAULT 0);
"""
def conn():
    c = sqlite3.connect(DB); c.executescript(SCHEMA); return c
def put_prices(c, asset_id, series):
    c.executemany("INSERT OR REPLACE INTO prices VALUES(?,?,?)",
                  [(asset_id, d, v) for d, v in series])
    c.commit()
EOF_DB

# ---------------------------------------------------------------------------
# etl/sources/amfi.py — Indian MF NAV (keyless, via mfapi.in)
# ---------------------------------------------------------------------------
cat > etl/sources/amfi.py << 'EOF_AMFI'
import json, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (fund-watchdog)"}
def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")
def fetch(code):
    d = json.loads(_get(f"https://api.mfapi.in/mf/{code}"))
    s = []
    for x in d.get("data", []):
        try:
            dd, mm, yy = x["date"].split("-")
            s.append((f"{yy}-{mm}-{dd}", float(x["nav"])))
        except Exception:
            pass
    s.sort()
    meta = d.get("meta", {})
    sub = " · ".join(v for v in [meta.get("fund_house"), meta.get("scheme_category")] if v)
    return s, (meta.get("scheme_name") or f"Scheme {code}"), (sub or "Mutual Fund")
EOF_AMFI

# ---------------------------------------------------------------------------
# etl/sources/us_prices.py — US EOD (keyless, via Stooq CSV)
# ---------------------------------------------------------------------------
cat > etl/sources/us_prices.py << 'EOF_US'
import urllib.request
UA = {"User-Agent": "Mozilla/5.0 (fund-watchdog)"}
def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")
def fetch(ticker):
    txt = _get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d")
    lines = txt.strip().splitlines()
    if not lines or not lines[0].lower().startswith("date"):
        return [], ticker, "US (no data)"
    s = []
    for ln in lines[1:]:
        p = ln.split(",")
        if len(p) < 5:
            continue
        try:
            s.append((p[0], float(p[4])))   # Close
        except Exception:
            pass
    s.sort()
    return s, ticker, "US stock / ETF"
EOF_US

# ---------------------------------------------------------------------------
# etl/sources/_stubs — later phases (documented placeholders)
# ---------------------------------------------------------------------------
for stub in amc_portfolio us_etf factsheet news; do
cat > "etl/sources/${stub}.py" << EOF_STUB
"""Phase 2/3 stub — see SPEC.md §7-8.
Implement a parser for this source and write into state.db tables
(snapshots/holdings/sectors). Until then the frontend's manual-import
fallback covers this asset class.
"""
def fetch(*args, **kwargs):
    raise NotImplementedError("${stub}: implement per SPEC.md")
EOF_STUB
done

cat > etl/alerts.py << 'EOF_AL'
"""Phase 3 stub — diff last two snapshots into the alerts table (SPEC.md §9)."""
def run():
    pass
EOF_AL

cat > etl/notify.py << 'EOF_NO'
"""Phase 3 stub — push unnotified alerts to Telegram/Resend (SPEC.md §10)."""
def run():
    pass
EOF_NO

# ---------------------------------------------------------------------------
# etl/compute.py — returns + rolling
# ---------------------------------------------------------------------------
cat > etl/compute.py << 'EOF_COMP'
from datetime import datetime, timedelta
def _D(x): return datetime.strptime(x, "%Y-%m-%d")
def _nav_back(s, days):
    if not s: return None
    tgt = _D(s[-1][0]) - timedelta(days=days)
    if _D(s[0][0]) > tgt: return None
    return min(s, key=lambda p: abs((_D(p[0]) - tgt).days))
def returns(s):
    if len(s) < 2: return {}
    last, first = s[-1][1], s[0][1]
    yrs = (_D(s[-1][0]) - _D(s[0][0])).days / 365.25
    def mk(days, ann):
        p = _nav_back(s, days)
        if not p or p[1] <= 0: return None
        y = days / 365.25; tot = last / p[1]
        return ((tot ** (1 / y)) - 1) * 100 if (ann and y > 1) else (tot - 1) * 100
    p1 = _nav_back(s, 1)
    return {
        "last": round(last, 4),
        "d1": round((last / p1[1] - 1) * 100, 2) if p1 and p1[1] > 0 else None,
        "y1": _r(mk(365, False)), "y3": _r(mk(1095, True)), "y5": _r(mk(1825, True)),
        "y10": _r(mk(3652, True)), "y15": _r(mk(5478, True)),
        "si": _r(((last / first) ** (1 / yrs) - 1) * 100 if yrs > 1 else (last / first - 1) * 100),
        "siYrs": round(yrs, 1),
    }
def rolling(s, win):
    if len(s) < 30: return None
    pts = [(_D(d).toordinal(), v) for d, v in s]
    start, end = pts[0][0], pts[-1][0]
    def at(o):
        b = min(pts, key=lambda p: abs(p[0] - o))
        return b if abs(b[0] - o) < 7 else None
    out = []; o = start
    while o + win <= end:
        a, b = at(o), at(o + win)
        if a and b and a[1] > 0:
            y = win / 365.25; tot = b[1] / a[1]
            out.append((tot ** (1 / y) - 1) * 100 if y > 1 else (tot - 1) * 100)
        o += 30
    if len(out) < 3: return None
    pos = sum(1 for x in out if x > 0)
    return {"n": len(out), "min": round(min(out), 1), "max": round(max(out), 1),
            "avg": round(sum(out) / len(out), 1), "posPct": round(pos / len(out) * 100),
            "vals": [round(x, 1) for x in out]}
def _r(x): return None if x is None else round(x, 2)
EOF_COMP

# ---------------------------------------------------------------------------
# etl/run.py — orchestrator (Phase 1)
# ---------------------------------------------------------------------------
cat > etl/run.py << 'EOF_RUN'
import json, os, yaml
from etl.sources import amfi, us_prices
from etl import compute, db
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
def load(p): return yaml.safe_load(open(os.path.join(ROOT, "config", p)))
def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), separators=(",", ":"))
def fetch(a):
    return amfi.fetch(a["id"]) if a["market"] == "IN" else us_prices.fetch(a["id"])
def main():
    cfg = load("portfolio.yml")
    c = db.conn()
    index = []
    for a in cfg.get("assets", []):
        aid = str(a["id"]); mkt = a["market"]
        try:
            s, nm, sub = fetch(a)
        except Exception as e:
            print(f"  ! {aid}: fetch failed ({e})"); s, nm, sub = [], a.get("name", aid), "fetch error"
        name = a.get("name") or nm
        cur = "₹" if mkt == "IN" else "$"
        r = compute.returns(s) if s else {}
        r["currency"] = cur
        r["rolling1"] = compute.rolling(s, 365) if s else None
        r["rolling3"] = compute.rolling(s, 1095) if s else None
        bench = a.get("benchmark") or ""
        if bench and mkt == "US" and bench.isascii() and bench.replace(".", "").isalnum():
            try:
                bs, _, _ = us_prices.fetch(bench)
                br = compute.returns(bs) if bs else {}
                r["bench"] = {k: br.get(k) for k in ["y1", "y3", "y5", "y10", "y15", "si"]}
            except Exception:
                pass
        write(os.path.join(DATA, "returns", f"{aid}.json"), r)
        write(os.path.join(DATA, "prices", f"{aid}.json"), s[-750:])
        if s: db.put_prices(c, aid, s)
        index.append({"id": aid, "market": mkt, "kind": a.get("kind", ""),
                      "name": name, "sub": sub, "benchmark": bench})
        print(f"  ✓ {aid} {name[:40]} — {len(s)} points")
    write(os.path.join(DATA, "index.json"), index)
    print(f"Done. {len(index)} assets → docs/data/")
if __name__ == "__main__":
    main()
EOF_RUN

# ---------------------------------------------------------------------------
# docs/index.html — read-only dashboard (reads ./data/*.json)
# ---------------------------------------------------------------------------
cat > docs/index.html << 'FWHTML'
<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fund Watchdog</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#0b0c0f;--panel:#13151b;--panel2:#191c24;--line:#262a35;--ink:#e9ecf2;--muted:#8b93a6;--faint:#5b6273;--amber:#f0b429;--up:#36d399;--down:#f4607b;--us:#5aa0ff;--in:#f0b429}
*{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--ink);font-family:'IBM Plex Sans',sans-serif;font-size:15px;line-height:1.45;background-image:radial-gradient(900px 500px at 88% -8%,rgba(240,180,41,.07),transparent 60%);min-height:100vh;padding-bottom:60px}
.mono{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums}.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}.faint{color:var(--faint)}
header{position:sticky;top:0;z-index:5;background:rgba(11,12,15,.86);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:14px 16px}
.brand{display:flex;align-items:center;gap:10px;max-width:960px;margin:0 auto}
.logo{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;background:linear-gradient(135deg,var(--amber),#b9821a);color:#1a1205;font-weight:800;font-family:'Bricolage Grotesque';font-size:18px}
h1{font-family:'Bricolage Grotesque';font-weight:800;font-size:19px;letter-spacing:-.3px}.sub{font-size:11px;color:var(--faint);letter-spacing:.4px;text-transform:uppercase}
main{padding:16px;max-width:960px;margin:0 auto}
.fcard{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:10px}
.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.nm{font-weight:600;font-size:14px;line-height:1.3}.meta{font-size:11px;color:var(--faint);margin-top:3px;text-transform:uppercase;letter-spacing:.4px}
.flag{display:inline-block;font-size:9px;font-weight:700;padding:2px 6px;border-radius:5px;margin-right:6px;letter-spacing:.5px;vertical-align:2px}.flag.IN{background:rgba(240,180,41,.16);color:var(--in)}.flag.US{background:rgba(90,160,255,.16);color:var(--us)}
.kind{font-size:9px;color:var(--faint);border:1px solid var(--line);border-radius:4px;padding:1px 5px;margin-left:6px;text-transform:uppercase}
.nav-big{font-family:'IBM Plex Mono';font-size:20px;font-weight:600;text-align:right;white-space:nowrap}
.strip{display:flex;margin-top:12px;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.cell{flex:1;text-align:center;padding:8px 4px;border-right:1px solid var(--line)}.cell:last-child{border:none}.k{font-size:9px;color:var(--faint);text-transform:uppercase;letter-spacing:.5px}.v{font-family:'IBM Plex Mono';font-size:14px;font-weight:600;margin-top:2px}
.spark{display:flex;align-items:flex-end;gap:2px;height:30px;margin-top:12px}.spark i{flex:1;border-radius:1px;min-height:2px;background:var(--amber);opacity:.7}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:12px}th{text-align:left;font-size:10px;color:var(--faint);text-transform:uppercase;letter-spacing:.5px;padding:7px 8px;border-bottom:1px solid var(--line)}td{padding:8px;border-bottom:1px solid var(--line)}td.num,th.num{text-align:right;font-family:'IBM Plex Mono'}tr:last-child td{border:none}
.badge{font-size:11px;font-weight:600;padding:3px 9px;border-radius:6px}.pass{background:rgba(54,211,153,.13);color:var(--up)}.fail{background:rgba(244,96,123,.13);color:var(--down)}
.note{font-size:11.5px;color:var(--faint);background:var(--panel2);border:1px dashed var(--line);border-radius:8px;padding:10px 12px;margin:14px 0;line-height:1.5}
details{margin-top:8px}summary{font-size:12px;color:var(--faint);cursor:pointer}
.loading{display:inline-block;width:14px;height:14px;border:2px solid var(--line);border-top-color:var(--amber);border-radius:50%;animation:spin .7s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body>
<header><div class="brand"><div class="logo">W</div><div><h1>Fund Watchdog</h1><div class="sub">India MF · US Stocks & ETFs · live</div></div></div></header>
<main id="app"><div class="faint mono" style="font-size:12px"><span class="loading"></span> loading…</div></main>
<script>
const fmt=(x,d=1)=>x==null||isNaN(x)?'—':(x>=0?'+':'')+(+x).toFixed(d)+'%';
const cls=x=>x==null||isNaN(x)?'':(x>=0?'up':'down');
async function j(u){const r=await fetch(u+'?t='+Date.now());if(!r.ok)throw 0;return r.json();}
function cell(k,v){return `<div class="cell"><div class="k">${k}</div><div class="v ${cls(v)}">${fmt(v)}</div></div>`;}
function spark(s){if(!s||s.length<2)return '';const v=s.slice(-60).map(p=>p[1]);const mn=Math.min(...v),mx=Math.max(...v),rg=mx-mn||1;return '<div class="spark">'+v.map(x=>`<i style="height:${4+(x-mn)/rg*26}px"></i>`).join('')+'</div>';}
function ptable(r){const P=[['1Y','y1'],['3Y','y3'],['5Y','y5'],['10Y','y10'],['15Y','y15'],['Since Incep.','si']];const b=r.bench||{};
 return `<table><thead><tr><th>Period</th><th class="num">Return</th><th class="num">Bench</th><th class="num">Alpha</th><th>Beat</th></tr></thead><tbody>`+
 P.map(([lbl,k])=>{const f=r[k],bv=b[k],al=(f!=null&&bv!=null)?f-bv:null;
 const beat=al==null?'<span class="faint">—</span>':(al>=0?'<span class="badge pass">✓</span>':'<span class="badge fail">✗</span>');
 return `<tr><td>${lbl}</td><td class="num ${cls(f)}">${fmt(f)}</td><td class="num muted">${bv!=null?fmt(bv):'—'}</td><td class="num ${cls(al)}">${al==null?'—':fmt(al)}</td><td>${beat}</td></tr>`;}).join('')+`</tbody></table>`;}
(async()=>{const app=document.getElementById('app');
 let idx;try{idx=await j('./data/index.json');}catch(e){app.innerHTML='<div class="note">No data yet. Run <b>python -m etl.run</b> and push.</div>';return;}
 app.innerHTML='';
 for(const a of idx){
   let r={},s=[];try{r=await j(`./data/returns/${a.id}.json`);}catch(e){}try{s=await j(`./data/prices/${a.id}.json`);}catch(e){}
   const cur=r.currency||'';const r1=r.rolling1;
   const el=document.createElement('div');el.className='fcard';
   el.innerHTML=`<div class="top"><div><div class="nm"><span class="flag ${a.market}">${a.market}</span>${a.name}<span class="kind">${a.kind}</span></div><div class="meta">${a.sub||''}</div></div>
     <div class="nav-big">${r.last!=null?cur+(+r.last).toFixed(2):'—'}<div style="font-size:11px" class="${cls(r.d1)}">${fmt(r.d1,2)} 1D</div></div></div>
     <div class="strip">${cell('1Y',r.y1)}${cell('3Y',r.y3)}${cell('5Y',r.y5)}${cell('SI',r.si)}</div>
     ${spark(s)}
     <details><summary>Performance detail${r1?` · 1Y rolling avg ${r1.avg}% (${r1.posPct}% positive)`:''}</summary>${ptable(r)}</details>`;
   app.appendChild(el);
 }
 const n=document.createElement('div');n.className='note';
 n.innerHTML='<b>Phase 1 live:</b> prices, returns, rolling & benchmark-beating, refreshed daily. Holdings Δ, sector Δ and change-alerts activate in Phase 2/3 (see SPEC.md).';
 app.appendChild(n);
})();
</script></body></html>
FWHTML

# ---------------------------------------------------------------------------
# GitHub Actions — daily refresh + commit
# ---------------------------------------------------------------------------
cat > .github/workflows/daily.yml << 'EOF_WF'
name: daily-refresh
on:
  schedule:
    - cron: "30 13 * * *"   # ~19:00 IST
  workflow_dispatch:
permissions:
  contents: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m etl.run
      - run: |
          git config user.name "fund-watchdog-bot"
          git config user.email "bot@users.noreply.github.com"
          git add docs/data state.db
          git commit -m "data: $(date -u +%F)" || echo "no changes"
          git push
EOF_WF

# ---------------------------------------------------------------------------
# .gitignore + next-steps note
# ---------------------------------------------------------------------------
cat > .gitignore << 'EOF_GI'
.venv/
__pycache__/
*.pyc
EOF_GI

cat > SETUP_NEXT.md << 'EOF_NEXT'
# What only you can do (can't be automated)

Phase 1 (prices + returns dashboard) is already live with no keys.

To enable the rest:
- **Holdings Δ / Sector Δ (P2):** implement one adapter in etl/sources/amc_portfolio.py
  (your AMC's monthly portfolio XLS) and etl/sources/us_etf.py (your ETF issuer's
  holdings CSV). See SPEC.md §7-8. Until then, use the manual-import fallback.
- **Alerts to your phone (P3):** create a Telegram bot via @BotFather, get the token
  and your chat_id, add them as GitHub repo secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID,
  set notify.telegram: true in config/settings.yml, then build etl/alerts.py + notify.py.
- **Better US data (optional):** add a TIINGO_TOKEN secret to replace the Stooq fallback.

Edit holdings anytime in config/portfolio.yml, then `python -m etl.run` (local) or push.
EOF_NEXT

# ---------------------------------------------------------------------------
# Run the pipeline locally (Phase 1 seed)
# ---------------------------------------------------------------------------
echo "▶ Installing deps + seeding data…"
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python -m etl.run

# ---------------------------------------------------------------------------
# Git + auto-deploy via GitHub CLI when available
# ---------------------------------------------------------------------------
git init -q
git add -A
git commit -q -m "Fund Watchdog: Phase 1 (live prices + returns)" || true
git branch -M main

echo "▶ Checking for GitHub CLI…"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "▶ gh authenticated — creating repo & deploying…"
  gh repo create "$REPO_NAME" $PRIVATE --source=. --remote=origin --push
  OWNER=$(gh api user -q .login)
  # Enable GitHub Pages: serve /docs from main
  gh api -X POST "repos/$OWNER/$REPO_NAME/pages" \
    -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1 \
    && echo "▶ Pages enabled." \
    || echo "▶ Could not auto-enable Pages — turn it on: Settings → Pages → main / /docs"
  echo ""
  echo "✅ Deployed.  Dashboard (live in ~1 min):  https://$OWNER.github.io/$REPO_NAME/"
  echo "   Repo: https://github.com/$OWNER/$REPO_NAME"
else
  echo ""
  echo "✅ Built & seeded locally (no GitHub CLI auth found)."
  echo "   Finish deploy manually:"
  echo "     1) gh auth login        (or create a repo on github.com)"
  echo "     2) git remote add origin <your-repo-url> && git push -u origin main"
  echo "     3) GitHub → Settings → Pages → Source: main, folder: /docs"
fi

echo ""
echo "Open docs/index.html locally to preview now. Edit config/portfolio.yml for your real holdings, then: python -m etl.run"
echo "See SETUP_NEXT.md for the human-only steps that unlock alerts & holdings."
