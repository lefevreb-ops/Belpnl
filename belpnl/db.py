"""SQLite storage: schema creation, dimension seeding and fact loading."""
import datetime as dt
import sqlite3
from pathlib import Path

from . import config

SCHEMA = Path(__file__).with_name("schema.sql")
SOURCE_ID = f"eurostat:{config.DATASET}"


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text())
    seed(con)
    return con


def seed(con):
    con.execute(
        "INSERT OR IGNORE INTO dim_source VALUES (?,?,?,?,?)",
        (SOURCE_ID, "Eurostat", config.DATASET,
         "Government revenue, expenditure and main aggregates (ESA 2010), annual",
         f"{config.EUROSTAT_API}/{config.DATASET}"))
    for code, label, kind, order in config.SECTORS:
        con.execute(
            "INSERT INTO dim_sector (sector_code, label, kind, sort_order) VALUES (?,?,?,?) "
            "ON CONFLICT(sector_code) DO UPDATE SET label=excluded.label, kind=excluded.kind, "
            "sort_order=excluded.sort_order", (code, label, kind, order))
    for code, label in config.UNIT_LABELS.items():
        con.execute("INSERT OR IGNORE INTO dim_unit VALUES (?,?)", (code, label))
    con.execute("DELETE FROM dim_pnl_line")
    for order, (line, parent, label, item, sign) in enumerate(config.PNL):
        con.execute("INSERT INTO dim_pnl_line VALUES (?,?,?,?,?,?)",
                    (line, parent, label, item, sign, order))
    con.commit()


def load(con, records, labels, origin, source_updated=None):
    """Upsert parsed JSON-stat records. Returns number of fact rows written."""
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cur = con.execute(
        "INSERT INTO etl_run (source_id, started_at, source_updated, origin) VALUES (?,?,?,?)",
        (SOURCE_ID, started, source_updated, origin))
    run_id = cur.lastrowid

    for code, label in labels.get("na_item", {}).items():
        con.execute("INSERT INTO dim_item VALUES (?,?) ON CONFLICT(item_code) "
                    "DO UPDATE SET label=excluded.label", (code, label))
    for code, label in labels.get("sector", {}).items():
        con.execute("UPDATE dim_sector SET source_label=? WHERE sector_code=?", (label, code))
    for code, label in labels.get("unit", {}).items():
        con.execute("INSERT OR IGNORE INTO dim_unit VALUES (?,?)", (code, label))

    known_sectors = {s[0] for s in config.SECTORS}
    rows = [
        (SOURCE_ID, r["sector"], r["na_item"], r["unit"], int(r["time"]),
         r["value"], r["flag"], run_id)
        for r in records
        if r.get("sector") in known_sectors and (r.get("geo") in (None, config.GEO))
    ]
    con.executemany(
        "INSERT INTO fact_gov_finance VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(source_id, sector_code, item_code, unit_code, year) DO UPDATE SET "
        "value=excluded.value, flag=excluded.flag, run_id=excluded.run_id", rows)
    con.execute("UPDATE etl_run SET rows_loaded=? WHERE run_id=?", (len(rows), run_id))
    con.commit()
    return len(rows)


def facts(con, unit):
    """{(sector, item, year): (value, flag)} for one unit."""
    out = {}
    for s, i, y, v, f in con.execute(
            "SELECT sector_code, item_code, year, value, flag FROM fact_gov_finance "
            "WHERE source_id=? AND unit_code=?", (SOURCE_ID, unit)):
        out[(s, i, y)] = (v, f)
    return out
