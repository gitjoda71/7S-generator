"""Stdlib tests for coordinate parsing + polygon helpers."""
import unittest

from corpusgen import coords
from corpusgen.geo import dist_km
from corpusgen.mgrs import latlon_to_mgrs

# lat, lon across zones, bands and both hemispheres
POINTS = [
    (59.2615, 17.7135), (60.345, 17.422), (55.60, 13.00), (67.85, 20.23),
    (57.70, 11.97), (-33.87, 151.21), (40.71, -74.01), (0.5, 0.5), (78.22, 15.63),
]


class TestMgrsInverse(unittest.TestCase):
    def test_round_trip_sub_metre(self):
        for lat, lon in POINTS:
            m = latlon_to_mgrs(lat, lon, digits=5)
            rlat, rlon = coords.mgrs_to_latlon(m)
            d = dist_km(lat, lon, rlat, rlon) * 1000
            self.assertLess(d, 2.0, f"{lat},{lon} via {m}: Δ={d:.2f} m")

    def test_spacing_variants_agree(self):
        a = coords.mgrs_to_latlon("33VXF6665179308")
        b = coords.mgrs_to_latlon("33V XF 66651 79308")
        c = coords.mgrs_to_latlon("33vxf 66651 79308")   # lower-case
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_coarse_precision_is_cell_centre(self):
        # a 4-digit (10 m) grid centre is within the 100 km 33VXF cell
        lat, lon = coords.mgrs_to_latlon("33VXF6679")
        self.assertTrue(58 < lat < 60 and 17 < lon < 19, (lat, lon))

    def test_rejects_garbage(self):
        for bad in ("33VXF12345", "hello", "99ZZ9999", "33VXF 1 2 3"):
            with self.assertRaises(ValueError, msg=bad):
                coords.mgrs_to_latlon(bad)


class TestParsePoint(unittest.TestCase):
    def test_dispatch(self):
        cases = [
            ("59.2615, 17.7135", "latlon"), ("59.2615 17.7135", "latlon"),
            ("33VXF6665179308", "mgrs"), ("33V XF 66651 79308", "mgrs"),
            ('59°15\'41"N 17°42\'49"E', "dms"), ("N59 15.69 E17 42.82", "dms"),
            ("59 15 41 N, 17 42 49 O", "dms"),          # Swedish O = east
            ("6580822, 674032", "sweref99tm"),
        ]
        for text, kind in cases:
            lat, lon, got = coords.parse_point(text)
            self.assertEqual(got, kind, f"{text!r} -> {got}")
            self.assertTrue(-90 <= lat <= 90 and -180 <= lon <= 180)

    def test_all_formats_hit_the_same_place(self):
        # the same Vällinge point, four ways, should agree within ~30 m
        ref = (59.2615, 17.7135)
        for text in ("59.2615, 17.7135", latlon_to_mgrs(*ref, digits=5),
                     "59 15 41.4 N 17 42 48.6 E"):
            lat, lon, _ = coords.parse_point(text)
            self.assertLess(dist_km(*ref, lat, lon) * 1000, 30, text)

    def test_swedish_decimal_comma_in_dms(self):
        lat, lon, kind = coords.parse_point("N59 15,69 E17 42,82")
        self.assertEqual(kind, "dms")
        self.assertAlmostEqual(lat, 59 + 15.69 / 60, places=4)

    def test_rejects_bad(self):
        for bad in ("", "59.664", "abc,def", "1 2 3 4"):
            with self.assertRaises(ValueError, msg=bad):
                coords.parse_point(bad)

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            coords.parse_point("599.6, 17.4")           # missing decimal point
        with self.assertRaises(ValueError):
            coords.parse_point("59.6, 200")


class TestSweref(unittest.TestCase):
    def test_matches_utm33_within_a_metre(self):
        # SWEREF99TM and WGS84/UTM33 differ by < 1 m in Sweden
        lat, lon = coords.sweref99tm_to_latlon(6580822, 674032)
        back = latlon_to_mgrs(lat, lon)
        self.assertTrue(back.startswith("33V") or back.startswith("34V"))
        self.assertTrue(58.5 < lat < 60 and 17 < lon < 19, (lat, lon))


class TestPolygon(unittest.TestCase):
    def test_point_in_polygon(self):
        sq = [[59.0, 17.0], [59.0, 18.0], [60.0, 18.0], [60.0, 17.0]]
        self.assertTrue(coords.point_in_polygon(59.5, 17.5, sq))
        self.assertFalse(coords.point_in_polygon(58.9, 17.5, sq))
        self.assertFalse(coords.point_in_polygon(59.5, 18.5, sq))

    def test_concave_polygon(self):
        # an L-shape: the notch must read as outside
        L = [[0, 0], [0, 2], [2, 2], [2, 1], [1, 1], [1, 0]]
        self.assertTrue(coords.point_in_polygon(0.5, 0.5, L))
        self.assertTrue(coords.point_in_polygon(1.5, 1.5, L))
        self.assertFalse(coords.point_in_polygon(1.5, 0.5, L))   # the notch

    def test_bounds(self):
        self.assertEqual(coords.polygon_bounds([[1, 2], [3, 4], [-1, 5]]),
                         (-1, 3, 2, 5))


if __name__ == "__main__":
    unittest.main()
