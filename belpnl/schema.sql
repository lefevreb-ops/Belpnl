-- Belgian general government finance database (ESA 2010)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_source (
    source_id    TEXT PRIMARY KEY,           -- e.g. 'eurostat:gov_10a_main'
    provider     TEXT NOT NULL,
    dataset      TEXT NOT NULL,
    description  TEXT,
    url          TEXT
);

CREATE TABLE IF NOT EXISTS dim_sector (
    sector_code  TEXT PRIMARY KEY,           -- ESA code: S13, S1311 ...
    label        TEXT NOT NULL,
    source_label TEXT,
    kind         TEXT NOT NULL CHECK (kind IN ('sub', 'cons')),
    sort_order   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_item (
    item_code    TEXT PRIMARY KEY,           -- ESA transaction code: TR, D2REC ...
    label        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_unit (
    unit_code    TEXT PRIMARY KEY,
    label        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_pnl_line (
    line_id      TEXT PRIMARY KEY,
    parent_id    TEXT REFERENCES dim_pnl_line(line_id),
    label        TEXT NOT NULL,
    item_code    TEXT,                       -- NULL = computed as sum of children
    sign         INTEGER NOT NULL DEFAULT 1,
    sort_order   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_run (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL REFERENCES dim_source(source_id),
    started_at   TEXT NOT NULL,
    source_updated TEXT,                     -- 'updated' stamp of the source dataset
    origin       TEXT,                       -- URL or file path
    rows_loaded  INTEGER
);

CREATE TABLE IF NOT EXISTS fact_gov_finance (
    source_id    TEXT NOT NULL REFERENCES dim_source(source_id),
    sector_code  TEXT NOT NULL REFERENCES dim_sector(sector_code),
    item_code    TEXT NOT NULL REFERENCES dim_item(item_code),
    unit_code    TEXT NOT NULL REFERENCES dim_unit(unit_code),
    year         INTEGER NOT NULL,
    value        REAL,
    flag         TEXT,                       -- Eurostat status flag (p = provisional, e = estimated ...)
    run_id       INTEGER REFERENCES etl_run(run_id),
    PRIMARY KEY (source_id, sector_code, item_code, unit_code, year)
);

-- Consolidation bridge: sum of subsectors, eliminations and consolidated S13.
CREATE VIEW IF NOT EXISTS v_consolidation AS
SELECT f.item_code, f.unit_code, f.year,
       SUM(CASE WHEN s.kind = 'sub' THEN f.value END)                         AS sum_subsectors,
       MAX(CASE WHEN s.kind = 'cons' THEN f.value END)                        AS consolidated,
       MAX(CASE WHEN s.kind = 'cons' THEN f.value END)
         - SUM(CASE WHEN s.kind = 'sub' THEN f.value END)                     AS eliminations
FROM fact_gov_finance f JOIN dim_sector s USING (sector_code)
GROUP BY f.item_code, f.unit_code, f.year;
