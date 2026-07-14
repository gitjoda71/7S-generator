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


class TestPolygonGeneration(unittest.TestCase):
    def test_places_land_inside_polygon(self):
        from corpusgen.coords import point_in_polygon
        # a square around the AOI (~±0.05° ≈ 5 km)
        poly = [[60.30, 17.37], [60.30, 17.47], [60.40, 17.47], [60.40, 17.37]]
        with tempfile.TemporaryDirectory() as d:
            c = generate.build_normal(out=d, lat=60.345, lon=17.422, radius=3.0,
                                      area="airport", start=datetime(2026, 6, 15),
                                      days=7, callsigns=CS, seed=1, reports=60,
                                      polygon=poly)
            self.assertEqual(c.meta["polygon"], poly)
            for loc in c.meta["locations"]:
                self.assertTrue(point_in_polygon(loc["lat"], loc["lon"], poly),
                                f"{loc['name']} @ {loc['lat']},{loc['lon']} utanför polygonen")

    def test_thin_polygon_never_places_on_outside_vertex(self):
        from corpusgen.coords import point_in_polygon
        # a ~11 m wide, ~20 km diagonal strip: bbox rejection almost never lands
        # inside, so the sampler must fall back to a guaranteed-interior point,
        # never to polygon[0] (a vertex that reads as OUTSIDE)
        thin = [[60.30, 17.40], [60.3001, 17.40], [60.40, 17.60], [60.4001, 17.60]]
        with tempfile.TemporaryDirectory() as d:
            c = generate.build_normal(out=d, lat=60.35, lon=17.50, radius=3, area="rural",
                                      start=datetime(2026, 6, 15), days=5, callsigns=CS,
                                      seed=2026, reports=20, polygon=thin)
            v0 = thin[0]
            on_vertex = sum(1 for l in c.meta["locations"]
                            if abs(l["lat"] - v0[0]) < 1e-9 and abs(l["lon"] - v0[1]) < 1e-9)
            self.assertEqual(on_vertex, 0, "platser staplade på ett hörn utanför polygonen")

    def test_polygon_is_deterministic(self):
        poly = [[60.30, 17.37], [60.30, 17.47], [60.40, 17.47], [60.40, 17.37]]
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a = generate.build_normal(out=d1, lat=60.345, lon=17.422, radius=3, area="airport",
                                      start=datetime(2026, 6, 15), days=7, callsigns=CS,
                                      seed=1, reports=40, polygon=poly)
            b = generate.build_normal(out=d2, lat=60.345, lon=17.422, radius=3, area="airport",
                                      start=datetime(2026, 6, 15), days=7, callsigns=CS,
                                      seed=1, reports=40, polygon=poly)
            self.assertEqual([r["id"] for r in a.ground_truth],
                             [r["id"] for r in b.ground_truth])
            self.assertEqual([l["lat"] for l in a.meta["locations"]],
                             [l["lat"] for l in b.meta["locations"]])


class TestCliAoi(unittest.TestCase):
    def _parse(self, *aoi_tokens):
        from corpusgen.cli import build_parser
        args = build_parser().parse_args(
            ["generate", "--aoi", *aoi_tokens, "--from", "2026-06-15", "--out", "/tmp/x"])
        return args.aoi

    def test_aoi_accepts_common_forms(self):
        self.assertEqual(self._parse("59.664,18.925"), (59.664, 18.925))      # canonical
        self.assertEqual(self._parse("59.664,", "18.925"), (59.664, 18.925))  # space after comma
        self.assertEqual(self._parse("59.664", "18.925"), (59.664, 18.925))   # space separator
        self.assertEqual(self._parse("59.664, 18.925"), (59.664, 18.925))     # quoted, spaced

    def test_aoi_accepts_mgrs(self):
        lat, lon = self._parse("33V", "XF", "66651", "79308")   # MGRS, shell-split
        self.assertTrue(59.2 < lat < 59.4 and 17.8 < lon < 18.0, (lat, lon))

    def test_aoi_rejects_bad_input(self):
        with self.assertRaises(SystemExit):      # argparse exits on a bad value
            self._parse("59.664")                # only one number
        with self.assertRaises(SystemExit):
            self._parse("abc,def")               # non-numeric


if __name__ == "__main__":
    unittest.main()
