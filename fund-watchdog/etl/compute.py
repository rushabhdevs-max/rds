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
