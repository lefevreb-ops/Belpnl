"""End-to-end tests on a SYNTHETIC JSON-stat document (not real Belgian data)."""
import tempfile
import unittest
from pathlib import Path

from belpnl import config, db, extract, i18n, pnl, report

SECTORS = ["S1311", "S1312", "S1313", "S1314", "S13"]
ITEMS = ["TR", "TE", "B9", "D2REC", "D5REC", "D41PAY", "D73PAY", "D7PAY_S1312"]
# synthetic values per sector for year 2000 (unit MIO_EUR)
VALS = {
    "S1311": {"TR": 100, "TE": 110, "B9": -10, "D2REC": 40, "D5REC": 50, "D41PAY": 8, "D73PAY": 30, "D7PAY_S1312": 30},
    "S1312": {"TR": 60, "TE": 58, "B9": 2, "D2REC": 5, "D5REC": 10, "D41PAY": 1},
    "S1313": {"TR": 20, "TE": 21, "B9": -1, "D2REC": 3, "D5REC": 7, "D41PAY": 1},
    "S1314": {"TR": 80, "TE": 79, "B9": 1, "D2REC": 0, "D5REC": 2, "D41PAY": 0},
    # consolidated: 30 of federal transfers eliminated on both sides
    "S13": {"TR": 230, "TE": 238, "B9": -8, "D2REC": 48, "D5REC": 69, "D41PAY": 10},
}


def synthetic_doc():
    dims = {"freq": ["A"], "unit": ["MIO_EUR"], "sector": SECTORS, "na_item": ITEMS,
            "geo": ["BE"], "time": ["2000"]}
    return _doc(dims, lambda c: VALS[c["sector"]].get(c["na_item"]),
                lambda c: "p" if (c["sector"], c["na_item"]) == ("S13", "TR") else None)


COFOG = {  # synthetic expenditure by function, per sector: TOTAL, GF01, GF0101, GF0108, GF10
    "S1311": [110, 80, 50, 30, 30], "S1312": [58, 58, 58, 0, 0], "S1313": [21, 21, 21, 0, 0],
    "S1314": [79, 0, 0, 0, 79], "S13": [238, 129, 129, 0, 109],
}
COFOG_CODES = ["TOTAL", "GF01", "GF0101", "GF0108", "GF10"]


def synthetic_cofog_doc():
    dims = {"freq": ["A"], "unit": ["MIO_EUR"], "sector": SECTORS, "cofog99": COFOG_CODES,
            "na_item": ["TE"], "geo": ["BE"], "time": ["2000"]}
    return _doc(dims, lambda c: COFOG[c["sector"]][COFOG_CODES.index(c["cofog99"])])


def _doc(dims, value_of, flag_of=lambda c: None):
    import itertools
    ids = list(dims)
    size = [len(dims[d]) for d in ids]
    value, status = {}, {}
    for flat, combo in enumerate(itertools.product(*(dims[d] for d in ids))):
        c = dict(zip(ids, combo))
        v = value_of(c)
        if v is not None:
            value[str(flat)] = v
            if flag_of(c):
                status[str(flat)] = flag_of(c)
    return {
        "version": "2.0", "class": "dataset", "updated": "2000-01-01T00:00:00Z",
        "id": ids, "size": size, "value": value, "status": status,
        "dimension": {d: {"category": {"index": {c: i for i, c in enumerate(dims[d])},
                                       "label": {c: c + " label" for c in dims[d]}}}
                      for d in ids},
    }


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = db.connect(Path(self.tmp.name) / "t.sqlite")
        recs, labels = extract.parse_jsonstat(synthetic_doc())
        self.recs = recs
        self.n = db.load(self.con, recs, labels, origin="synthetic", source_updated="2000-01-01")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_parse(self):
        self.assertEqual(self.n, sum(len(v) for v in VALS.values()))
        r = next(r for r in self.recs if r["sector"] == "S1312" and r["na_item"] == "TE")
        self.assertEqual((r["value"], r["time"], r["geo"]), (58, "2000", "BE"))
        flagged = [r for r in self.recs if r["flag"]]
        self.assertEqual([(r["sector"], r["na_item"], r["flag"]) for r in flagged], [("S13", "TR", "p")])

    def test_hierarchy_and_residuals(self):
        v = pnl.build(self.con, "MIO_EUR")["values"]
        fed = v["S1311"][2000]
        self.assertEqual(fed["REV_TAX"], 90)
        self.assertEqual(fed["REV__OTHER"], 10)          # TR 100 - taxes 90
        self.assertEqual(fed["D4PAY"], 8)                # not reported: sum of components
        self.assertEqual(fed["EXP__OTHER"], 72)          # TE 110 - interest 8 - transfers 30
        self.assertEqual(fed["RES"], -10)
        self.assertEqual(fed["PRIM"], -2)

    def test_consolidation_bridge(self):
        out = pnl.build(self.con, "MIO_EUR")
        v = out["values"]
        self.assertEqual(v["SUM"][2000]["REV"], 260)
        self.assertEqual(v["ELIM"][2000]["REV"], -30)
        self.assertEqual(v["ELIM"][2000]["EXP"], -30)
        self.assertEqual(v["ELIM"][2000]["RES"], 0)
        self.assertEqual(out["checks"], [])
        self.assertIn("D61REC", out["missing_items"])

    def test_view_and_reload_idempotent(self):
        row = self.con.execute("SELECT sum_subsectors, consolidated, eliminations FROM v_consolidation "
                               "WHERE item_code='TE' AND year=2000").fetchone()
        self.assertEqual(row, (268, 238, -30))
        recs, labels = extract.parse_jsonstat(synthetic_doc())
        db.load(self.con, recs, labels, origin="synthetic")
        cnt = self.con.execute("SELECT COUNT(*) FROM fact_gov_finance").fetchone()[0]
        self.assertEqual(cnt, self.n)

    def test_cofog_and_transfers(self):
        recs, labels = extract.parse_jsonstat(synthetic_cofog_doc())
        db.load(self.con, recs, labels, origin="synthetic-cofog")
        out = pnl.build_cofog(self.con, "MIO_EUR")
        v = out["values"]
        self.assertEqual(v["S1311"][2000]["GF01"], 80)
        self.assertEqual(v["ELIM"][2000]["GF0108"], -30)
        self.assertEqual(v["ELIM"][2000]["TOTAL"], -30)
        self.assertEqual(out["checks"], [])                 # COFOG total == TE
        self.assertNotIn("GF01__OTHER", v["S1311"][2000])  # groups add up
        self.assertEqual(pnl.transfers(self.con, "MIO_EUR"), {2000: {"D7": {"S1311": {"S1312": 30}}}})
        html_path = Path(self.tmp.name) / "c.html"
        data = report.render(self.con, html_path)
        self.assertIn("cofog", data["statements"])

    def test_intra_gov_zero_when_consolidated(self):
        v = pnl.build(self.con, "MIO_EUR")["values"]
        self.assertEqual(v["S13"][2000]["D73PAY"], 0.0)
        self.assertEqual(v["ELIM"][2000]["D73PAY"], -30)

    def test_report(self):
        out = Path(self.tmp.name) / "r.html"
        report.render(self.con, out)
        html = out.read_text()
        self.assertNotIn("/*__DATA__*/null", html)
        self.assertIn('"REV__OTHER"', html)

    def test_translations_complete(self):
        data = report.render(self.con, Path(self.tmp.name) / "l.html")
        for line in data["statements"]["pnl"]["lines"]:
            self.assertEqual(set(line["labels"]), set(i18n.LANGS), line["id"])
            if line["id"] in i18n.PNL:      # translated, not English fallback
                self.assertEqual(line["labels"]["fr"], i18n.PNL[line["id"]][0])
        for s in data["sectors"]:
            self.assertEqual(len(set(s["labels"].values())), 4, s["code"])
        for lang in i18n.LANGS:
            self.assertEqual(set(data["ui"][lang]), set(data["ui"]["en"]))
        self.assertEqual(set(i18n.PNL), {n[0] for n in config.PNL})
        self.assertIn("?format=JSON&lang=FR", extract.label_url("gov_10a_exp", "fr"))

    def test_url(self):
        url = extract.build_url()
        self.assertIn("gov_10a_main?", url)
        self.assertIn("sector=S1312", url)
        self.assertIn("unit=PC_GDP", url)


if __name__ == "__main__":
    unittest.main()
