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
