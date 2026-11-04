"""Render the statements as a self-contained interactive HTML report."""
import json
from pathlib import Path

from . import config, pnl

TEMPLATE = Path(__file__).with_name("report_template.html")


def report_lines(spec=None):
    """Ordered display lines, with an 'Other / not allocated' line after the
    children of every node that has both a reported item and children."""
    spec = spec or config.PNL
    children = pnl.children_of(spec)
    nodes = {n[0]: n for n in spec}
    out = []

    def walk(line, depth):
        _, parent, label, item, sign = nodes[line]
        kids = children.get(line, [])
        out.append({"id": line, "parent": parent, "label": label, "item": item,
                    "sign": sign, "depth": depth, "hasKids": bool(kids) or None})
        for k in kids:
            walk(k, depth + 1)
        if item and kids:
            out.append({"id": line + pnl.OTHER_SUFFIX, "parent": line,
                        "label": config.OTHER_LABELS.get(line, "Other / not allocated"), "item": None, "sign": 1,
                        "depth": depth + 1, "other": True})

    for root in children[None]:
        walk(root, 0)
    return out


def _round(obj):
    if isinstance(obj, float):
        return round(obj, 2)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def render(con, path):
    statements = {"pnl": {"title": "P&L", "lines": report_lines(),
                          "units": {u: pnl.build(con, u) for u in config.UNITS}}}
    cofog = {u: pnl.build_cofog(con, u) for u in config.UNITS}
    if all(cofog.values()):
        statements["cofog"] = {"title": "Expenditure by function",
                               "lines": report_lines(pnl.cofog_spec(con)), "units": cofog}
    runs = [dict(zip(("source", "loaded_at", "source_updated"), r)) for r in con.execute(
        "SELECT source_id, MAX(started_at), MAX(source_updated) FROM etl_run GROUP BY source_id")]
    data = _round({
        "statements": statements,
        "transfers": {u: pnl.transfers(con, u) for u in config.UNITS},
        "transferTypes": [{"code": c, "label": l} for c, l in config.TRANSFER_TYPES],
        "sectors": [{"code": c, "label": l, "kind": k}
                    for c, l, k, _ in sorted(config.SECTORS, key=lambda s: s[3])],
        "unitLabels": {u: config.UNIT_LABELS.get(u, u) for u in config.UNITS},
        "meta": {"geo": config.GEO, "runs": runs},
    })
    html = TEMPLATE.read_text().replace("/*__DATA__*/null",
                                        json.dumps(data, separators=(",", ":")))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(html, encoding="utf-8")
    return data
