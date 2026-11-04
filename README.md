# Belpnl: consolidated P&L of the Belgian government

This project turns Belgian government finance statistics (ESA 2010) into a
consolidated profit-and-loss statement:

* **Extract**: downloads Eurostat `gov_10a_main` (government revenue,
  expenditure and main aggregates) for Belgium in EUR million and % of GDP,
  from 1995 onwards. It covers these sectors:

  | Code  | Level |
  |-------|-------|
  | S1311 | Federal government (central government) |
  | S1312 | Communities and Regions (state government) |
  | S1313 | Local government |
  | S1314 | Social security funds |
  | S13   | General government, consolidated |

* **Store**: loads the data into a SQLite star schema (`belpnl/schema.sql`).
* **Visualise**: generates a self-contained HTML report with an expandable
  P&L hierarchy (`belpnl/report_template.html`).

The project uses only the Python standard library (3.10+).

## Usage

```bash
python -m belpnl all          # download, load into data/belpnl.sqlite, write output/belgium_gov_pnl.html
python -m belpnl extract      # download + load only
python -m belpnl report       # regenerate the HTML from the database

# Offline / blocked network: save the Eurostat JSON from a browser, then
python -m belpnl load data/raw/gov_10a_main.json
python -m belpnl report
```

Each download is archived in `data/raw/` for audit. Loads are idempotent
upserts, and each load is logged in `etl_run`.

## Database

| Table | Content |
|-------|---------|
| `fact_gov_finance` | value per source × sector × ESA item × unit × year, plus the Eurostat flag (p = provisional, e = estimated, …) |
| `dim_sector`, `dim_item`, `dim_unit`, `dim_source` | dimensions; item labels come from the source |
| `dim_pnl_line` | the P&L hierarchy (parent/child, mapped ESA item, sign) |
| `etl_run` | load log: timestamp, origin URL or file, source `updated` stamp, row count |
| `v_consolidation` | per item and year: Σ subsectors, consolidated S13, eliminations |

## P&L hierarchy and consolidation

The hierarchy is defined in `belpnl/config.py`:

```
Total revenue (TR)
  Taxes: production & imports (D2), income & wealth (D5), capital (D91)
  Net social contributions (D61) · Sales (P11+P12+P131) · Property income (D4) · Other current transfers (D7)
  Other / not allocated (balancing line)
Total expenditure (TE)
  Operating: compensation of employees (D1), intermediate consumption (P2)
  Social benefits (D62, D632) · Subsidies (D3) · Interest (D41) · Other current transfers (D7)
  Capital: gross fixed capital formation (P51G), capital transfers (D9)
  Other / not allocated (balancing line)
Net lending / borrowing = TR − TE   (checked against reported B9)
Primary balance = B9 + interest
```

* Each subsector is already consolidated internally by Eurostat.
* **Consolidation eliminations** = S13 − Σ subsectors. This is the
  intergovernmental flows, mainly federal and social-security transfers to
  Communities, Regions and local authorities. These flows cancel out in the
  balance.
* Wherever a total is reported, an "Other / not allocated" line reconciles
  the listed components with it, so the hierarchy always adds up. Missing
  items are listed in the report footnotes.

## Tests

```bash
python -m unittest -v
```

The tests use a small **synthetic** JSON-stat document to check parsing,
loading, the hierarchy arithmetic, the consolidation bridge and report
rendering. Its values are not real data.

## Possible extensions

* NBB.Stat (National Bank of Belgium) for the split of Communities and Regions
  into individual entities (Flemish, Walloon, Brussels, French and German-speaking
  Communities).
* `gov_10a_exp` (COFOG) for expenditure by function.
