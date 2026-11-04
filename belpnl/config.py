"""Static configuration: data source, government subsectors and the P&L hierarchy."""

EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Eurostat "Government revenue, expenditure and main aggregates" (ESA 2010, annual).
DATASET = "gov_10a_main"
GEO = "BE"
UNITS = ["MIO_EUR", "PC_GDP"]
SINCE_YEAR = 1995

# Consolidated general government (S13) and its Belgian subsectors.
# kind: 'sub' = subsector column, 'cons' = consolidated total.
SECTORS = [
    # code,   label,                          kind,   order
    ("S1311", "Federal government",           "sub",  1),
    ("S1312", "Communities and Regions",      "sub",  2),
    ("S1313", "Local government",             "sub",  3),
    ("S1314", "Social security funds",        "sub",  4),
    ("S13",   "General government (consolidated)", "cons", 9),
]

UNIT_LABELS = {"MIO_EUR": "EUR million", "PC_GDP": "% of GDP"}

# P&L hierarchy.  Each node:
#   id, parent, label, item (Eurostat na_item code or None), sign
# Rules applied when the P&L is built:
#   * a node with an `item` takes the reported value of that item;
#   * a node without `item` is the sum of its children (times their sign);
#   * when a node has an item AND children, an "Other / not allocated" line is
#     added so that children always reconcile with the reported parent.
# Expenditure is displayed as a positive amount; the result line is
# revenue - expenditure and is checked against the reported B9.
PNL = [
    ("REV",       None,      "Total revenue",                                   "TR",           1),
    ("REV_TAX",   "REV",     "Taxes",                                           None,           1),
    ("D2REC",     "REV_TAX", "Taxes on production and imports (VAT, excise...)", "D2REC",       1),
    ("D5REC",     "REV_TAX", "Current taxes on income, wealth, etc.",           "D5REC",        1),
    ("D91REC",    "REV_TAX", "Capital taxes",                                   "D91REC",       1),
    ("D61REC",    "REV",     "Net social contributions",                        "D61REC",       1),
    ("P1REC",     "REV",     "Sales and other output",                          "P11_P12_P131", 1),
    ("D4REC",     "REV",     "Property income received",                        "D4REC",        1),
    ("D7REC",     "REV",     "Other current transfers received",                "D7REC",        1),

    ("EXP",       None,      "Total expenditure",                               "TE",           1),
    ("EXP_OPS",   "EXP",     "Operating expenditure",                           None,           1),
    ("D1PAY",     "EXP_OPS", "Compensation of employees",                       "D1PAY",        1),
    ("P2",        "EXP_OPS", "Intermediate consumption",                        "P2",           1),
    ("EXP_SOC",   "EXP",     "Social benefits",                                 None,           1),
    ("D62PAY",    "EXP_SOC", "Social benefits other than in kind",              "D62PAY",       1),
    ("D632PAY",   "EXP_SOC", "Social transfers in kind (market production)",    "D632PAY",      1),
    ("D3PAY",     "EXP",     "Subsidies",                                       "D3PAY",        1),
    ("D41PAY",    "EXP",     "Interest",                                        "D41PAY",       1),
    ("D7PAY",     "EXP",     "Other current transfers paid",                    "D7PAY",        1),
    ("EXP_CAP",   "EXP",     "Capital expenditure",                             None,           1),
    ("P51G",      "EXP_CAP", "Gross fixed capital formation",                   "P51G",         1),
    ("D9PAY",     "EXP_CAP", "Capital transfers paid",                          "D9PAY",        1),

    ("RES",       None,      "Net lending (+) / net borrowing (-)",             None,           1),
    ("RES_REV",   "RES",     "Total revenue",                                   "TR",           1),
    ("RES_EXP",   "RES",     "Total expenditure",                               "TE",          -1),
    ("PRIM",      None,      "Primary balance (excl. interest)",                None,           1),
    ("PRIM_RES",  "PRIM",    "Net lending / borrowing",                         "B9",           1),
    ("PRIM_INT",  "PRIM",    "Interest",                                        "D41PAY",       1),
]

# Reported aggregate used to check the computed result line.
CHECKS = [("RES", "B9")]
