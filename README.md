# Belpnl: consolidated P&L of the Belgian government

This project turns Belgian government finance statistics (ESA 2010) into a
consolidated profit-and-loss statement:

* **Extract**: downloads two Eurostat datasets for Belgium, in EUR million and
  % of GDP, from 1995 onwards:
  * `gov_10a_main`: revenue, expenditure and main aggregates. It also gives
    the transfers between levels of government by counterparty.
  * `gov_10a_exp`: expenditure by function (COFOG), 10 divisions and about 70
    groups.

  Both cover these sectors:

  | Code  | Level |
  |-------|-------|
  | S1311 | Federal government (central government) |
  | S1312 | Communities and Regions (state government) |
  | S1313 | Local government |
  | S1314 | Social security funds |
  | S13   | General government, consolidated |

* **Store**: loads the data into a SQLite star schema (`belpnl/schema.sql`).
* **Visualise**: generates a self-contained HTML report
  (`belpnl/report_template.html`) with three tabs:
  * **P&L**: an expandable hierarchy of up to four levels.
  * **Expenditure by function**: COFOG divisions, expandable into groups.
  * **Transfers between governments**: a who-pays-whom matrix.

  The P&L and function tabs can show all levels of government for one year
  (with a consolidation bridge) or one level over time.

The report is available in **English, French, Dutch and German**. Use the
EN / FR / NL / DE switch at the top of the page, or open it with `?lang=fr`.
The page remembers your choice and otherwise follows the browser language.
All labels are stored in the `dim_label` table. The French and German
spending-function (COFOG) names are Eurostat's official labels, downloaded
during extraction. Eurostat has no Dutch, so the Dutch names, like the other
translations, are in `belpnl/i18n.py`.

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
| `dim_label` | translated labels (en, fr, nl, de) for P&L lines, sectors, units, flow types and COFOG |
| `etl_run` | load log: timestamp, origin URL or file, source `updated` stamp, row count |
| `fact_gov_cofog` | expenditure by function: sector × COFOG code × item × unit × year |
| `dim_cofog` | COFOG hierarchy (total → division → group) |
| `v_consolidation` | per item and year: Σ subsectors, consolidated S13, eliminations |
| `v_intergov_transfers` | payer × receiver × flow type (D7 current, D9 capital, D4 property income) |

## P&L hierarchy and consolidation

The hierarchy is defined in `belpnl/config.py`:

```
Total revenue (TR)
  Taxes
    Production & imports (D2): VAT, excise and other product taxes, other taxes on production
    Income & wealth (D5): personal income tax, corporate income tax, other
    Capital taxes (D91)
  Net social contributions (D61): employers, households, imputed
  Sales (P11, P12, P131) · Property income (interest, dividends, rent) · Subsidies received
  Other current transfers: from other levels of government (D73), from EU, other
  Capital transfers received: investment grants, other
Total expenditure (TE)
  Operating: compensation of employees (wages, employer contributions), intermediate consumption, taxes paid
  Social benefits: cash (old age, survivors, unemployment, other), in kind, pension-entitlement adjustment
  Subsidies · Property income paid (interest)
  Other current transfers: to other levels of government (D73), EU own resources, cooperation, other
  Capital: gross capital formation (GFCF), non-produced assets, capital transfers (investment grants, other)
Net lending / borrowing = TR − TE   (checked against reported B9)
Primary balance = B9 + interest
```

* Each subsector is already consolidated internally by Eurostat.
* **Consolidation eliminations** = S13 − Σ subsectors. This is the
  intergovernmental flows, mainly federal and social-security transfers to
  Communities, Regions and local authorities. They show up on the lines "from /
  to other levels of government" (D73) and cancel out in the balance.
* Total expenditure in the function dataset (COFOG) is compared with TE from the
  main dataset. Eurostat publishes the two separately, so recent years can differ
  by less than 0.7%.
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
* Function × economic type (e.g. compensation of employees within education)
  by adding more `na_item` codes to the COFOG extract.
* `gov_10a_taxag` for a finer breakdown of tax revenue.
