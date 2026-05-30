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
