"""Extract government finance data from the Eurostat dissemination API (JSON-stat 2.0)."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

from . import config


def build_url(dataset=config.DATASET, geo=config.GEO, sectors=None, units=None,
              since=config.SINCE_YEAR, filters=None):
    sectors = sectors or [s[0] for s in config.SECTORS]
    units = units or config.UNITS
    params = [("format", "JSON"), ("lang", "EN"), ("geo", geo),
              ("sinceTimePeriod", str(since))]
    params += [("sector", s) for s in sectors]
    params += [("unit", u) for u in units]
    for dim, codes in (filters or {}).items():
        params += [(dim, c) for c in codes]
    return f"{config.EUROSTAT_API}/{dataset}?{urllib.parse.urlencode(params)}"


def fetch(url, raw_dir=None, timeout=120):
    """Download a JSON-stat document; keep a raw copy for audit when raw_dir is given."""
    req = urllib.request.Request(url, headers={"User-Agent": "belpnl/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    doc = json.loads(body)
    if raw_dir:
        Path(raw_dir).mkdir(parents=True, exist_ok=True)
        stamp = doc.get("updated", "unknown").replace(":", "").replace("-", "")[:15]
        name = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
        (Path(raw_dir) / f"{name}_{config.GEO}_{stamp}.json").write_bytes(body)
    return doc


def load_file(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_jsonstat(doc):
    """Flatten a JSON-stat 2.0 dataset into records.

    Returns (records, labels) where records is a list of dicts keyed by
    dimension id plus 'value' and 'flag', and labels maps
    dimension -> {code: label}.
    """
    ids, sizes, dims = doc["id"], doc["size"], doc["dimension"]
    codes_by_pos = []
    labels = {}
    for d in ids:
        cat = dims[d]["category"]
        index = cat.get("index")
        if isinstance(index, list):
            order = index
        elif isinstance(index, dict):
            order = [c for c, _ in sorted(index.items(), key=lambda kv: kv[1])]
        else:  # single category without index
            order = list(cat["label"].keys())
        codes_by_pos.append(order)
        labels[d] = dict(cat.get("label", {c: c for c in order}))

    values, status = doc.get("value", {}), doc.get("status", {}) or {}
    if isinstance(values, list):
        values = {i: v for i, v in enumerate(values) if v is not None}
    if isinstance(status, list):
        status = {i: s for i, s in enumerate(status) if s}

    # strides for row-major flat index
    strides, acc = [], 1
    for s in reversed(sizes):
        strides.insert(0, acc)
        acc *= s

    def decode(flat):
        out = {}
        for d, stride, size, order in zip(ids, strides, sizes, codes_by_pos):
            out[d] = order[(flat // stride) % size]
        return out

    keys = set(int(k) for k in values) | set(int(k) for k in status)
    records = []
    for flat in sorted(keys):
        rec = decode(flat)
        rec["value"] = values.get(str(flat), values.get(flat))
        rec["flag"] = status.get(str(flat), status.get(flat))
        records.append(rec)
    return records, labels
