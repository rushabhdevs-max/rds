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
