"""SQLite storage: schema creation, dimension seeding and fact loading."""
import datetime as dt
import sqlite3
from pathlib import Path

from . import config

SCHEMA = Path(__file__).with_name("schema.sql")
DESCRIPTIONS = {
    "gov_10a_main": "Government revenue, expenditure and main aggregates (ESA 2010), annual",
    "gov_10a_exp": "General government expenditure by function (COFOG), annual",
}


def source_id(dataset):
    return f"eurostat:{dataset}"


SOURCE_ID = source_id(config.DATASET)


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text())
    seed(con)
    return con


def seed(con):
    for dataset, _, _ in config.DATASETS.values():
        con.execute("INSERT OR IGNORE INTO dim_source VALUES (?,?,?,?,?)",
                    (source_id(dataset), "Eurostat", dataset, DESCRIPTIONS.get(dataset),
                     f"{config.EUROSTAT_API}/{dataset}"))
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


def _cofog_parent(code):
    if code == "TOTAL":
        return None, 0
    if len(code) == 4:          # GF01
        return "TOTAL", 1
    return code[:4], 2          # GF0101


def load(con, records, labels, origin, source_updated=None, dataset=None):
    """Upsert parsed JSON-stat records. Returns number of fact rows written."""
    dataset = dataset or (config.DATASETS["cofog"][0] if "cofog99" in labels else config.DATASET)
    src = source_id(dataset)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cur = con.execute(
        "INSERT INTO etl_run (source_id, started_at, source_updated, origin) VALUES (?,?,?,?)",
        (src, started, source_updated, origin))
    run_id = cur.lastrowid

    for code, label in labels.get("na_item", {}).items():
        con.execute("INSERT INTO dim_item VALUES (?,?) ON CONFLICT(item_code) "
                    "DO UPDATE SET label=excluded.label", (code, label))
    for code, label in labels.get("sector", {}).items():
        con.execute("UPDATE dim_sector SET source_label=? WHERE sector_code=?", (label, code))
    for code, label in labels.get("unit", {}).items():
        con.execute("INSERT OR IGNORE INTO dim_unit VALUES (?,?)", (code, label))
    for code, label in labels.get("cofog99", {}).items():
        parent, level = _cofog_parent(code)
        con.execute("INSERT INTO dim_cofog VALUES (?,?,?,?) ON CONFLICT(cofog_code) "
                    "DO UPDATE SET label=excluded.label", (code, label, parent, level))

    known = {s[0] for s in config.SECTORS}
    keep = [r for r in records
            if r.get("sector") in known and r.get("geo") in (None, config.GEO)]
    if "cofog99" in labels:
        rows = [(src, r["sector"], r["cofog99"], r["na_item"], r["unit"], int(r["time"]),
                 r["value"], r["flag"], run_id) for r in keep]
        con.executemany(
            "INSERT INTO fact_gov_cofog VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_id, sector_code, cofog_code, item_code, unit_code, year) "
            "DO UPDATE SET value=excluded.value, flag=excluded.flag, run_id=excluded.run_id", rows)
    else:
        rows = [(src, r["sector"], r["na_item"], r["unit"], int(r["time"]),
                 r["value"], r["flag"], run_id) for r in keep]
        con.executemany(
            "INSERT INTO fact_gov_finance VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_id, sector_code, item_code, unit_code, year) DO UPDATE SET "
            "value=excluded.value, flag=excluded.flag, run_id=excluded.run_id", rows)
    con.execute("UPDATE etl_run SET rows_loaded=? WHERE run_id=?", (len(rows), run_id))
    con.commit()
    return len(rows)


def facts(con, unit):
    """{(sector, item, year): (value, flag)} for one unit (main dataset)."""
    return {(s, i, y): (v, f) for s, i, y, v, f in con.execute(
        "SELECT sector_code, item_code, year, value, flag FROM fact_gov_finance "
        "WHERE source_id=? AND unit_code=?", (SOURCE_ID, unit))}


def cofog_facts(con, unit, item="TE"):
    """{(sector, cofog, year): (value, flag)} for one unit."""
    return {(s, c, y): (v, f) for s, c, y, v, f in con.execute(
        "SELECT sector_code, cofog_code, year, value, flag FROM fact_gov_cofog "
        "WHERE unit_code=? AND item_code=?", (unit, item))}


def cofog_tree(con):
    """[(code, parent, label)] in display order."""
    return list(con.execute(
        "SELECT cofog_code, parent_code, label FROM dim_cofog "
        "ORDER BY CASE WHEN cofog_code='TOTAL' THEN '' ELSE cofog_code END"))
