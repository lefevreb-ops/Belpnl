"""Build hierarchical statements (with consolidation bridge) from the database."""
from . import config, db

ELIM = "ELIM"      # pseudo-column: eliminations = consolidated - sum of subsectors
SUBTOTAL = "SUM"   # pseudo-column: sum of subsectors
OTHER_SUFFIX = "__OTHER"
TOLERANCE = 0.5    # EUR million / pp; differences below are rounding

SUBS = [s[0] for s in config.SECTORS if s[2] == "sub"]
CONS = next(s[0] for s in config.SECTORS if s[2] == "cons")
SECTOR_ORDER = [s[0] for s in sorted(config.SECTORS, key=lambda s: s[3])]


def children_of(spec):
    children = {}
    for line, parent, *_ in spec:
        children.setdefault(parent, []).append(line)
    return children


def compute(fact_map, sector, year, spec=None):
    """Return {line_id: value} for one sector-year, including 'Other' residual lines.

    spec: list of (id, parent, label, item, sign); defaults to the P&L.
    fact_map: {(sector, item, year): (value, flag)}.
    """
    spec = spec or config.PNL
    nodes = {n[0]: n for n in spec}
    children = children_of(spec)
    out = {}

    def reported(item):
        v = fact_map.get((sector, item, year))
        if (v is None or v[0] is None) and sector == CONS and item in config.INTRA_GOV_ITEMS:
            return 0.0      # flows between levels vanish once consolidated
        return None if v is None or v[0] is None else v[0]

    def visit(line):
        _, _, _, item, _ = nodes[line]
        kids = children.get(line, [])
        kid_sum, any_kid = 0.0, False
        for k in kids:
            kv = visit(k)
            if kv is not None:
                kid_sum += kv * nodes[k][4]
                any_kid = True
        if item:
            val = reported(item)
            if val is None and any_kid:
                val = kid_sum          # parent not reported: fall back to its components
            if kids and val is not None and any_kid and abs(val - kid_sum) > 1e-9:
                out[line + OTHER_SUFFIX] = val - kid_sum
        else:
            val = kid_sum if any_kid else None
        out[line] = val
        return val

    for root in children[None]:
        visit(root)
    return out


def statement(fact_map, spec, checks=()):
    """Values for every sector, Σ subsectors and eliminations, plus flags and checks."""
    years = sorted({y for (_, _, y) in fact_map})
    values = {s: {y: compute(fact_map, s, y, spec) for y in years} for s in SECTOR_ORDER}
    values[SUBTOTAL], values[ELIM] = {}, {}
    for y in years:
        lines = set().union(*(values[s][y].keys() for s in SECTOR_ORDER))
        values[SUBTOTAL][y], values[ELIM][y] = {}, {}
        for ln in lines:
            sv = [values[s][y].get(ln) for s in SUBS]
            known = [v for v in sv if v is not None]
            ssum = sum(known) if known else None
            values[SUBTOTAL][y][ln] = ssum
            c = values[CONS][y].get(ln)
            values[ELIM][y][ln] = (c - ssum) if (c is not None and ssum is not None) else None

    flags = {}
    for (s, i, y), (_, f) in fact_map.items():
        if f:
            flags.setdefault(s, {}).setdefault(str(y), {})[i] = f

    issues = []
    for s in SECTOR_ORDER:
        for y in years:
            for line, item in checks:
                rep = fact_map.get((s, item, y), (None,))[0]
                calc = values[s][y].get(line)
                if rep is not None and calc is not None and abs(rep - calc) > TOLERANCE:
                    issues.append({"sector": s, "year": y, "line": line,
                                   "reported": rep, "computed": calc})

    used = {n[3] for n in spec if n[3]}
    present = {i for (_, i, _) in fact_map} | config.INTRA_GOV_ITEMS
    return {"years": years, "values": values, "flags": flags,
            "checks": issues, "missing_items": sorted(used - present)}


def build(con, unit):
    """P&L statement for one unit."""
    return statement(db.facts(con, unit), config.PNL, config.CHECKS)


def cofog_spec(con):
    return [(code, parent, label, code, 1) for code, parent, label in db.cofog_tree(con)]


def build_cofog(con, unit):
    """Expenditure by function (COFOG) for one unit."""
    spec = cofog_spec(con)
    if not spec:
        return None
    out = statement(db.cofog_facts(con, unit), spec)
    # cross-check: COFOG total must equal TE from the main dataset
    main = db.facts(con, unit)
    out["checks"] = [
        {"sector": s, "year": y, "line": "TOTAL", "reported": main[(s, "TE", y)][0],
         "computed": out["values"][s][y].get("TOTAL")}
        for s in SECTOR_ORDER for y in out["years"]
        if (s, "TE", y) in main and main[(s, "TE", y)][0] is not None
        and out["values"][s][y].get("TOTAL") is not None
        and abs(main[(s, "TE", y)][0] - out["values"][s][y]["TOTAL"]) > TOLERANCE
    ]
    return out


def transfers(con, unit):
    """{year: {type: {payer: {receiver: value}}}} from <type>PAY_<receiver> items."""
    out = {}
    for typ, payer, receiver, year, value in con.execute(
            "SELECT transfer_type, payer, receiver, year, value FROM v_intergov_transfers "
            "WHERE unit_code=? AND value IS NOT NULL", (unit,)):
        if payer == receiver:
            continue
        out.setdefault(year, {}).setdefault(typ, {}).setdefault(payer, {})[receiver] = value
    return out
