"""Render the P&L hierarchy as a self-contained interactive HTML report."""
import json
from pathlib import Path

from . import config, pnl

TEMPLATE = Path(__file__).with_name("report_template.html")


def report_lines():
    """Ordered display lines, with an 'Other / not allocated' line after the
    children of every node that has both a reported item and children."""
    children = {}
    for line, parent, *_ in config.PNL:
        children.setdefault(parent, []).append(line)
    nodes = {n[0]: n for n in config.PNL}
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
                        "label": "Other / not allocated", "item": None, "sign": 1,
                        "depth": depth + 1, "other": True})

    for root in children[None]:
        walk(root, 0)
    return out


def render(con, path):
    units = {u: pnl.build(con, u) for u in config.UNITS}
    run = con.execute("SELECT started_at, source_updated, origin FROM etl_run "
                      "ORDER BY run_id DESC LIMIT 1").fetchone()
    data = {
        "lines": report_lines(),
        "sectors": [{"code": c, "label": l, "kind": k}
                    for c, l, k, _ in sorted(config.SECTORS, key=lambda s: s[3])],
        "units": {u: {"label": config.UNIT_LABELS.get(u, u), **units[u]} for u in units},
        "meta": {"dataset": config.DATASET, "geo": config.GEO,
                 "loaded_at": run[0] if run else None,
                 "source_updated": run[1] if run else None,
                 "origin": run[2] if run else None},
    }
    html = TEMPLATE.read_text().replace("/*__DATA__*/null",
                                        json.dumps(data, separators=(",", ":")))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(html, encoding="utf-8")
    return data
