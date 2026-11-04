"""Build the hierarchical P&L (with consolidation bridge) from the database."""
from . import config
from .db import facts

ELIM = "ELIM"      # pseudo-column: eliminations = consolidated - sum of subsectors
SUBTOTAL = "SUM"   # pseudo-column: sum of subsectors
OTHER_SUFFIX = "__OTHER"
TOLERANCE = 0.5    # EUR million / pp; differences below are rounding


def _tree():
    children = {}
    for line, parent, *_ in config.PNL:
        children.setdefault(parent, []).append(line)
    return children


def compute(fact_map, sector, year):
    """Return {line_id: value} for one sector-year, including 'Other' residual lines."""
    nodes = {n[0]: n for n in config.PNL}
    children = _tree()
    out = {}

    def reported(item):
        v = fact_map.get((sector, item, year))
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
            if kids and val is not None and any_kid and abs(val - kid_sum) > 1e-9:
                out[line + OTHER_SUFFIX] = val - kid_sum
        else:
            val = kid_sum if any_kid else None
        out[line] = val
        return val

    for root in children[None]:
        visit(root)
    return out


def build(con, unit):
    """Assemble everything the report needs for one unit."""
    fm = facts(con, unit)
    years = sorted({y for (_, _, y) in fm})
    sectors = [s[0] for s in sorted(config.SECTORS, key=lambda s: s[3])]
    subs = [s[0] for s in config.SECTORS if s[2] == "sub"]
    cons = next(s[0] for s in config.SECTORS if s[2] == "cons")

    values = {}            # values[sector][year][line]
    for s in sectors:
        values[s] = {y: compute(fm, s, y) for y in years}
    # consolidation bridge columns
    values[SUBTOTAL], values[ELIM] = {}, {}
    for y in years:
        lines = set().union(*(values[s][y].keys() for s in sectors))
        values[SUBTOTAL][y], values[ELIM][y] = {}, {}
        for ln in lines:
            sv = [values[s][y].get(ln) for s in subs]
            ssum = sum(v for v in sv if v is not None) if any(v is not None for v in sv) else None
            values[SUBTOTAL][y][ln] = ssum
            c = values[cons][y].get(ln)
            values[ELIM][y][ln] = (c - ssum) if (c is not None and ssum is not None) else None

    flags = {}             # provisional / estimated markers on reported items
    for (s, i, y), (_, f) in fm.items():
        if f:
            flags.setdefault(s, {}).setdefault(str(y), {})[i] = f

    checks = []
    for s in sectors:
        for y in years:
            for line, item in config.CHECKS:
                rep = fm.get((s, item, y), (None,))[0]
                calc = values[s][y].get(line)
                if rep is not None and calc is not None and abs(rep - calc) > TOLERANCE:
                    checks.append({"sector": s, "year": y, "line": line,
                                   "reported": rep, "computed": calc})

    used_items = {n[3] for n in config.PNL if n[3]}
    present = {i for (_, i, _) in fm}
    missing = sorted(used_items - present)
    return {"years": years, "values": values, "flags": flags,
            "checks": checks, "missing_items": missing}
