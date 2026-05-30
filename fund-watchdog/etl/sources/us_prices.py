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
