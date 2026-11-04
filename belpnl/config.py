"""Static configuration: data source, government subsectors and the P&L hierarchy."""

EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Eurostat datasets (ESA 2010, annual).  key -> (dataset id, extra filters, fact table)
DATASETS = {
    "main":  ("gov_10a_main", {}, "fact_gov_finance"),             # revenue, expenditure, balance
    "cofog": ("gov_10a_exp", {"na_item": ["TE"]}, "fact_gov_cofog"), # expenditure by function
}
DATASET = DATASETS["main"][0]
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
    ("REV",        None,       "Total revenue",                                   "TR",            1),
    ("REV_TAX",    "REV",      "Taxes",                                           None,            1),
    ("D2REC",      "REV_TAX",  "Taxes on production and imports",                 "D2REC",         1),
    ("D21REC",     "D2REC",    "Taxes on products",                               "D21REC",        1),
    ("D211REC",    "D21REC",   "VAT",                                             "D211REC",       1),
    ("D29REC",     "D2REC",    "Other taxes on production",                       "D29REC",        1),
    ("D5REC",      "REV_TAX",  "Current taxes on income, wealth, etc.",           "D5REC",         1),
    ("D51REC",     "D5REC",    "Taxes on income",                                 "D51REC",        1),
    ("D51A_C1REC", "D51REC",   "Personal income tax",                             "D51A_C1REC",    1),
    ("D51B_C2REC", "D51REC",   "Corporate income tax",                            "D51B_C2REC",    1),
    ("D59REC",     "D5REC",    "Other current taxes",                             "D59REC",        1),
    ("D91REC",     "REV_TAX",  "Capital taxes (inheritance, gifts...)",           "D91REC",        1),
    ("D61REC",     "REV",      "Net social contributions",                        "D61REC",        1),
    ("D611REC",    "D61REC",   "Employers' actual contributions",                 "D611REC",       1),
    ("D613REC",    "D61REC",   "Households' actual contributions",                "D613REC",       1),
    ("P1REC",      "REV",      "Sales and other output",                          "P11_P12_P131",  1),
    ("P11",        "P1REC",    "Market output",                                   "P11",           1),
    ("P12",        "P1REC",    "Output for own final use",                        "P12",           1),
    ("P131",       "P1REC",    "Payments for non-market output (fees)",           "P131",          1),
    ("D4REC",      "REV",      "Property income received",                        "D4REC",         1),
    ("D41REC",     "D4REC",    "Interest",                                        "D41REC",        1),
    ("D42REC",     "D4REC",    "Dividends (distributed income of corporations)",  "D42REC",        1),
    ("D45REC",     "D4REC",    "Rent",                                            "D45REC",        1),
    ("D39REC",     "REV",      "Subsidies received",                              "D39REC",        1),
    ("D7REC",      "REV",      "Other current transfers received",                "D7REC",         1),
    ("D73REC",     "D7REC",    "From other levels of government",                 "D73REC",        1),
    ("D7REC_S212", "D7REC",    "From EU institutions",                            "D7REC_S212",    1),
    ("D92_D99REC", "REV",      "Capital transfers received",                      "D92_D99REC",    1),
    ("D92REC",     "D92_D99REC", "Investment grants",                             "D92REC",        1),
    ("D99REC",     "D92_D99REC", "Other capital transfers",                       "D99REC",        1),

    ("EXP",        None,       "Total expenditure",                               "TE",            1),
    ("EXP_OPS",    "EXP",      "Operating expenditure",                           None,            1),
    ("D1PAY",      "EXP_OPS",  "Compensation of employees",                       "D1PAY",         1),
    ("D11PAY",     "D1PAY",    "Wages and salaries",                              "D11PAY",        1),
    ("D12PAY",     "D1PAY",    "Employers' social contributions",                 "D12PAY",        1),
    ("P2",         "EXP_OPS",  "Intermediate consumption",                        "P2",            1),
    ("D29_D5PAY",  "EXP_OPS",  "Taxes paid",                                      None,            1),
    ("D29PAY",     "D29_D5PAY", "Other taxes on production",                      "D29PAY",        1),
    ("D5PAY",      "D29_D5PAY", "Current taxes on income, wealth",                "D5PAY",         1),
    ("EXP_SOC",    "EXP",      "Social benefits",                                 None,            1),
    ("D62PAY",     "EXP_SOC",  "Cash benefits (other than in kind)",              "D62PAY",        1),
    ("D62_GF1002", "D62PAY",   "Old age (pensions)",                              "D62PAY_GF1002", 1),
    ("D62_GF1003", "D62PAY",   "Survivors",                                       "D62PAY_GF1003", 1),
    ("D62_GF1005", "D62PAY",   "Unemployment",                                    "D62PAY_GF1005", 1),
    ("D632PAY",    "EXP_SOC",  "Social transfers in kind (market production)",    "D632PAY",       1),
    ("D8",         "EXP_SOC",  "Adjustment for change in pension entitlements",   "D8",            1),
    ("D3PAY",      "EXP",      "Subsidies",                                       "D3PAY",         1),
    ("D31PAY",     "D3PAY",    "Subsidies on products",                           "D31PAY",        1),
    ("D39PAY",     "D3PAY",    "Other subsidies on production",                   "D39PAY",        1),
    ("D4PAY",      "EXP",      "Property income paid",                            "D4PAY",         1),
    ("D41PAY",     "D4PAY",    "Interest",                                        "D41PAY",        1),
    ("D7PAY",      "EXP",      "Other current transfers paid",                    "D7PAY",         1),
    ("D73PAY",     "D7PAY",    "To other levels of government",                   "D73PAY",        1),
    ("D76PAY",     "D7PAY",    "EU own resources (VAT- and GNI-based)",           "D76PAY",        1),
    ("D74PAY",     "D7PAY",    "International cooperation",                       "D74PAY",        1),
    ("D75PAY",     "D7PAY",    "Miscellaneous current transfers",                 "D75PAY",        1),
    ("D71PAY",     "D7PAY",    "Net non-life insurance premiums",                 "D71PAY",        1),
    ("EXP_CAP",    "EXP",      "Capital expenditure",                             None,            1),
    ("P5",         "EXP_CAP",  "Gross capital formation",                         "P5",            1),
    ("P51G",       "P5",       "Gross fixed capital formation (investment)",      "P51G",          1),
    ("NP",         "EXP_CAP",  "Net acquisitions of non-produced assets (land...)", "NP",          1),
    ("D9PAY",      "EXP_CAP",  "Capital transfers paid",                          "D9PAY",         1),
    ("D92PAY",     "D9PAY",    "Investment grants",                               "D92PAY",        1),
    ("D99PAY",     "D9PAY",    "Other capital transfers",                         "D99PAY",        1),

    ("RES",        None,       "Net lending (+) / net borrowing (-)",             None,            1),
    ("RES_REV",    "RES",      "Total revenue",                                   "TR",            1),
    ("RES_EXP",    "RES",      "Total expenditure",                               "TE",           -1),
    ("PRIM",       None,       "Primary balance (excl. interest)",                None,            1),
    ("PRIM_RES",   "PRIM",     "Net lending / borrowing",                         "B9",            1),
    ("PRIM_INT",   "PRIM",     "Interest",                                        "D41PAY",        1),
]

# Reported aggregate used to check the computed result line.
CHECKS = [("RES", "B9")]

# Flows between government levels: not reported for consolidated S13, where they
# are zero by construction.
INTRA_GOV_ITEMS = {"D73REC", "D73PAY"}

# Who-pays-whom matrix: Eurostat reports, for each paying subsector,
# "<type>PAY_<receiving subsector>".
TRANSFER_TYPES = [
    ("D7", "Current transfers"),
    ("D9", "Capital transfers"),
    ("D4", "Property income (interest...)"),
]

