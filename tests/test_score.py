"""Stdlib tests for `score`:  python3 -m unittest discover -s tests"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from corpusgen import generate, score
from corpusgen.corpus import Corpus

CS = ["AQ", "BQ", "CQ", "DQ"]


def _corpus(d):
    """150 civila + en recon-cell (4 medlemmar) + en demonstration (8)."""
    generate.build_normal(out=d, lat=60.345, lon=17.422, radius=3.0, area="airport",
                          start=datetime(2026, 6, 15), days=14, callsigns=CS,
                          seed=1, reports=150, obj_name="fältet")
    c = Corpus.load(d)
    generate.add_hostiles(c, "recon", count=4, seed=3)
    generate.add_protesters(c, "demonstranter", count=8, seed=5)
    return Corpus.load(d)


class TestScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.corpus = _corpus(cls._tmp.name)
        cls.gt = cls.corpus.ground_truth
        cls.noncivil = [r for r in cls.gt if r["truth"] != "civil"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _dets(self, rows):
        return {score._norm_name(r["file"]): r["truth"] for r in rows}

    def test_perfect_detector(self):
        res = score.score(self.gt, self._dets(self.noncivil))
        for cls_name in ("icke-civil", "hostile", "protester"):
            c = res["classes"][cls_name]
            self.assertEqual((c["precision"], c["recall"], c["f1"]), (1.0, 1.0, 1.0), cls_name)
        cov = res["member_coverage"]
        self.assertEqual(cov["detected"], cov["total"])
        self.assertEqual(cov["total"], 4)                       # count=4 distinkta medlemmar
        for st in ("hostile:recon", "protester:demonstranter"):
            self.assertEqual(res["subtype_recall"][st]["detected"],
                             res["subtype_recall"][st]["total"], st)

    def test_empty_detections(self):
        res = score.score(self.gt, {})
        c = res["classes"]["icke-civil"]
        self.assertEqual(c["recall"], 0.0)
        self.assertIsNone(c["precision"])                       # inget flaggat
        self.assertIsNone(c["f1"])
        self.assertEqual(c["fn"], len(self.noncivil))
        self.assertEqual(res["member_coverage"]["detected"], 0)

    def test_flag_everything_has_base_rate_precision(self):
        dets = {score._norm_name(r["file"]): "hostile" for r in self.gt}
        res = score.score(self.gt, dets)
        c = res["classes"]["icke-civil"]
        self.assertEqual(c["recall"], 1.0)
        self.assertAlmostEqual(c["precision"], len(self.noncivil) / len(self.gt))

    def test_wrong_label_counts_for_overall_but_not_per_label(self):
        hostile = [r for r in self.gt if r["truth"] == "hostile"]
        dets = {score._norm_name(r["file"]): "protester" for r in hostile}  # fel label
        res = score.score(self.gt, dets)
        self.assertEqual(res["classes"]["icke-civil"]["recall"], 1.0 * len(hostile) / len(self.noncivil))
        self.assertEqual(res["classes"]["hostile"]["tp"], 0)    # label-strikt: miss
        self.assertEqual(res["classes"]["protester"]["fp"], len(hostile))
        self.assertEqual(res["member_coverage"]["detected"], 0)  # kräver rätt label

    def test_civil_label_is_not_a_flag(self):
        dets = {score._norm_name(r["file"]): "civil" for r in self.gt}
        res = score.score(self.gt, dets)
        self.assertEqual(res["classes"]["icke-civil"]["tp"], 0)
        self.assertEqual(res["classes"]["icke-civil"]["fp"], 0)

    def test_unknown_files_are_reported_and_excluded(self):
        dets = {"finnsinte.md": "hostile"}
        dets.update(self._dets(self.noncivil))
        res = score.score(self.gt, dets)
        self.assertEqual(res["detections"]["unknown_files"], ["finnsinte.md"])
        self.assertEqual(res["classes"]["icke-civil"]["fp"], 0)  # okänd fil ej FP


class TestDetectionsFile(unittest.TestCase):
    def _load(self, payload):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.json"
            p.write_text(json.dumps(payload), encoding="utf-8")
            return score.load_detections(p)

    def test_accepts_bare_filenames_and_wrapper(self):
        dets, dup = self._load({"detections": ["TNR170101.md", "sub/TNR180202.MD"]})
        self.assertEqual(dup, 0)
        self.assertEqual(dets, {"tnr170101.md": "hostile",     # bart namn = hostile
                                "tnr180202.md": "hostile"})    # basename, gemener

    def test_accepts_objects_and_counts_duplicates(self):
        dets, dup = self._load([{"file": "TNR170101.md", "label": "Hostile"},
                                {"file": "tnr170101.md", "label": "protester"}])
        self.assertEqual(dup, 1)
        self.assertEqual(dets["tnr170101.md"], "protester")    # sista vinner

    def test_rejects_malformed(self):
        with self.assertRaises(ValueError):
            self._load({"foo": 1})                             # varken lista eller wrapper
        with self.assertRaises(ValueError):
            self._load([{"label": "hostile"}])                 # saknar "file"
        with self.assertRaises(ValueError):
            self._load([{"file": "x.md", "label": "spion"}])   # okänd label
        with self.assertRaises(ValueError):
            score.load_detections(Path("finns") / "inte.json")


class TestRunGate(unittest.TestCase):
    def test_min_f1_gate(self):
        with tempfile.TemporaryDirectory() as d:
            c = _corpus(d)
            noncivil = [r for r in c.ground_truth if r["truth"] != "civil"]
            perfect = Path(d) / "perfect.json"
            perfect.write_text(json.dumps(
                [{"file": r["file"], "label": r["truth"]} for r in noncivil]), encoding="utf-8")
            empty = Path(d) / "empty.json"
            empty.write_text("[]", encoding="utf-8")
            sink = lambda s: None
            self.assertTrue(score.run(c, perfect, min_f1=0.99, out=sink))
            self.assertFalse(score.run(c, empty, min_f1=0.5, out=sink))
            self.assertTrue(score.run(c, empty, out=sink))     # ingen grind => True

    def test_cli_wiring(self):
        from corpusgen.cli import build_parser
        a = build_parser().parse_args(
            ["score", "--corpus", "k", "--detections", "d.json", "--min-f1", "0.8", "--json"])
        self.assertEqual((a.corpus, a.detections, a.min_f1, a.json), ("k", "d.json", 0.8, True))


if __name__ == "__main__":
    unittest.main()
