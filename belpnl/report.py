"""Render the statements as a self-contained interactive HTML report."""
import json
from pathlib import Path

from . import config, db, i18n, pnl

TEMPLATE = Path(__file__).with_name("report_template.html")


def report_lines(spec=None, labels=None):
    """Ordered display lines, with an 'Other / not allocated' line after the
    children of every node that has both a reported item and children.
    labels: {line_id: {lang: label}}; English from the spec when missing."""
    spec = spec or config.PNL
    labels = labels or {}

    def names(line_id, en):
        return {lang: labels.get(line_id, {}).get(lang) or en for lang in i18n.LANGS}

    children = pnl.children_of(spec)
    nodes = {n[0]: n for n in spec}
    out = []

    def walk(line, depth):
        _, parent, label, item, sign = nodes[line]
        kids = children.get(line, [])
        out.append({"id": line, "parent": parent, "labels": names(line, label), "item": item,
                    "sign": sign, "depth": depth, "hasKids": bool(kids) or None})
        for k in kids:
            walk(k, depth + 1)
        if item and kids:
            out.append({"id": line + pnl.OTHER_SUFFIX, "parent": line,
                        "labels": names(line + pnl.OTHER_SUFFIX, i18n.OTHER[""][0]),
                        "item": None, "sign": 1,
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
    statements = {"pnl": {"lines": report_lines(labels=db.labels(con, "pnl_line")),
                          "units": {u: pnl.build(con, u) for u in config.UNITS}}}
    cofog = {u: pnl.build_cofog(con, u) for u in config.UNITS}
    if all(cofog.values()):
        statements["cofog"] = {"lines": report_lines(pnl.cofog_spec(con), db.labels(con, "cofog")),
                               "units": cofog}
    sl, ul, tl = db.labels(con, "sector"), db.labels(con, "unit"), db.labels(con, "transfer")
    runs = [dict(zip(("source", "loaded_at", "source_updated"), r)) for r in con.execute(
        "SELECT source_id, MAX(started_at), MAX(source_updated) FROM etl_run GROUP BY source_id")]
    data = _round({
        "statements": statements,
        "transfers": {u: pnl.transfers(con, u) for u in config.UNITS},
        "transferTypes": [{"code": c, "labels": tl.get(c, {"en": l})} for c, l in config.TRANSFER_TYPES],
        "sectors": [{"code": c, "labels": sl.get(c, {"en": l}), "kind": k}
                    for c, l, k, _ in sorted(config.SECTORS, key=lambda s: s[3])],
        "unitLabels": {u: ul.get(u, {"en": u}) for u in config.UNITS},
        "langs": i18n.LANGS,
        "numberLocales": i18n.NUMBER_LOCALES,
        "ui": i18n.ui(),
        "meta": {"geo": config.GEO, "runs": runs},
    })
    html = TEMPLATE.read_text().replace("/*__DATA__*/null",
                                        json.dumps(data, separators=(",", ":")))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(html, encoding="utf-8")
    return data
