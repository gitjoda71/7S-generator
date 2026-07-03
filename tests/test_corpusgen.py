"""Stdlib tests:  python3 -m unittest discover -s tests"""
import os
import tempfile
import unittest
from datetime import datetime

from corpusgen import generate
from corpusgen.corpus import Corpus
from corpusgen.mgrs import latlon_to_mgrs

CS = ["AQ", "BQ", "CQ", "DQ"]


def _build(out, days=7, reports=120, seed=1):
    return generate.build_normal(out=out, lat=60.345, lon=17.422, radius=3.0, area="airport",
                                 start=datetime(2026, 6, 15), days=days, callsigns=CS,
                                 seed=seed, reports=reports, obj_name="fältet")


class TestMgrs(unittest.TestCase):
    def test_forward_matches_known_vallinge_grid(self):
        self.assertEqual(latlon_to_mgrs(59.2615, 17.7135), "33VXF5468572319")
        self.assertTrue(latlon_to_mgrs(60.345, 17.422).startswith("33V"))


class TestGenerate(unittest.TestCase):
    def test_normal_corpus_is_valid_7s(self):
        with tempfile.TemporaryDirectory() as d:
            c = _build(d)
            self.assertEqual(len(c.ground_truth), 120)
            self.assertTrue(all(r["truth"] == "civil" for r in c.ground_truth))
            self.assertEqual(len(c.meta["locations"]), 16)   # 4 callsigns × 4
            for r in c.ground_truth[:25]:
                with open(os.path.join(d, r["file"]), encoding="utf-8") as fh:
                    txt = fh.read()
                self.assertIn("typ: 7S-rapport", txt)
                self.assertIn("**Händelse:**", txt)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a, b = _build(d1), _build(d2)
            self.assertEqual([r["id"] for r in a.ground_truth],
                             [r["id"] for r in b.ground_truth])

    def test_area_frequency_scales(self):
        with tempfile.TemporaryDirectory() as urb, tempfile.TemporaryDirectory() as forest:
            u = generate.build_normal(out=urb, lat=59.0, lon=18.0, radius=3, area="urban",
                                      start=datetime(2026, 7, 1), days=10, callsigns=CS, seed=1)
            f = generate.build_normal(out=forest, lat=59.0, lon=18.0, radius=3, area="forest",
                                      start=datetime(2026, 7, 1), days=10, callsigns=CS, seed=1)
            self.assertGreater(len(u.ground_truth), 3 * len(f.ground_truth))


class TestAugment(unittest.TestCase):
    def test_hostiles(self):
        with tempfile.TemporaryDirectory() as d:
            _build(d, days=14, reports=200)
            n = generate.add_hostiles(Corpus.load(d), "recon", count=None, seed=3)
            self.assertTrue(2 <= n <= 10, n)
            gt = Corpus.load(d).ground_truth
            hostiles = [r for r in gt if r["truth"] == "hostile"]
            self.assertGreaterEqual(len(hostiles), n)                    # each appears ≥1×
            self.assertTrue(all(r["subtype"] == "recon" for r in hostiles))
            self.assertEqual(len({r["member"] for r in hostiles}), n)    # n distinct members

    def test_protesters_cluster(self):
        with tempfile.TemporaryDirectory() as d:
            _build(d, days=14, reports=200)
            m = generate.add_protesters(Corpus.load(d), "demonstranter", count=8, seed=5)
            self.assertEqual(m, 8)
            prot = [r for r in Corpus.load(d).ground_truth if r["truth"] == "protester"]
            self.assertEqual(len(prot), 8)
            self.assertEqual(len({r["member"] for r in prot}), 1)        # one group


if __name__ == "__main__":
    unittest.main()
