"""Command line: python -m belpnl {extract,load,report,all}"""
import argparse
import sys

from . import config, db, extract, report

DEFAULT_DB = "data/belpnl.sqlite"
DEFAULT_RAW = "data/raw"
DEFAULT_OUT = "output/belgium_gov_pnl.html"


def main(argv=None):
    p = argparse.ArgumentParser(prog="belpnl", description=__doc__)
    p.add_argument("--db", default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="download from Eurostat and load into the database")
    e.add_argument("--raw-dir", default=DEFAULT_RAW)
    e.add_argument("--since", type=int, default=1995)

    l = sub.add_parser("load", help="load a previously downloaded Eurostat JSON-stat file")
    l.add_argument("file")

    r = sub.add_parser("report", help="render the HTML P&L report")
    r.add_argument("--out", default=DEFAULT_OUT)

    a = sub.add_parser("all", help="extract + report")
    a.add_argument("--raw-dir", default=DEFAULT_RAW)
    a.add_argument("--since", type=int, default=1995)
    a.add_argument("--out", default=DEFAULT_OUT)

    args = p.parse_args(argv)
    con = db.connect(args.db)

    if args.cmd in ("extract", "all"):
        for dataset, filters, _ in config.DATASETS.values():
            url = extract.build_url(dataset=dataset, since=args.since, filters=filters)
            print(f"Fetching {url}")
            try:
                doc = extract.fetch(url, raw_dir=args.raw_dir)
            except OSError as exc:
                print(f"Download failed: {exc}\nOpen the URL above in a browser, save the JSON, "
                      "then run: python -m belpnl load <file.json>", file=sys.stderr)
                return 1
            recs, labels = extract.parse_jsonstat(doc)
            n = db.load(con, recs, labels, origin=url, source_updated=doc.get("updated"),
                        dataset=dataset)
            print(f"Loaded {n} rows from {dataset} (source updated {doc.get('updated')})")
    if args.cmd == "load":
        doc = extract.load_file(args.file)
        recs, labels = extract.parse_jsonstat(doc)
        n = db.load(con, recs, labels, origin=args.file, source_updated=doc.get("updated"))
        print(f"Loaded {n} rows from {args.file}")
    if args.cmd in ("report", "all"):
        data = report.render(con, args.out)
        for name, st in data["statements"].items():
            for u, d in st["units"].items():
                if d["missing_items"]:
                    print(f"[{name}/{u}] items not found in source: {', '.join(d['missing_items'])}")
                if d["checks"]:
                    print(f"[{name}/{u}] {len(d['checks'])} reconciliation differences")
        print(f"Report written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
