"""Stdlib tests for the local GUI server:  python3 -m unittest discover -s tests"""
import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

from corpusgen import generate
from corpusgen.gui import server as gui


class TestGuiApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = gui.GuiState()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), gui.make_handler(cls.state))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.corpus = str(Path(cls._tmp.name) / "korpus")
        generate.build_normal(out=cls.corpus, lat=60.345, lon=17.422, radius=3.0,
                              area="airport", start=datetime(2026, 6, 15), days=5,
                              callsigns=["AQ", "BQ"], seed=1, reports=20, obj_name="fältet")
        cls.dest = Path(cls._tmp.name) / "inkorg"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._tmp.cleanup()

    def _req(self, method, path, body=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if host:
            headers["Host"] = host                   # overrides the auto Host header
        payload = json.dumps(body) if body is not None else None
        conn.request(method, path, payload, headers)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        try:
            return r.status, json.loads(data)
        except ValueError:
            return r.status, data

    def test_serves_app_html(self):
        status, data = self._req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"7S-generator", data)

    def test_rejects_foreign_host(self):
        status, data = self._req("GET", "/api/state", host="ond.example.com")
        self.assertEqual(status, 403)

    def test_unknown_paths_are_404(self):
        self.assertEqual(self._req("GET", "/api/finnsinte")[0], 404)
        self.assertEqual(self._req("POST", "/api/finnsinte", {})[0], 404)
        self.assertEqual(self._req("GET", "/../corpusgen/cli.py")[0], 404)

    def test_use_rejects_bad_paths(self):
        self.assertEqual(self._req("POST", "/api/use", {"path": ""})[0], 400)
        status, data = self._req("POST", "/api/use", {"path": self._tmp.name})
        self.assertEqual(status, 400)                # dir exists but no meta.json
        self.assertIn("meta.json", data["error"])

    def test_oversized_body_is_rejected(self):
        big = {"path": "x" * (gui.MAX_BODY + 10)}
        self.assertEqual(self._req("POST", "/api/use", big)[0], 413)

    def test_use_state_send_reset_flow(self):
        status, st = self._req("POST", "/api/use", {"path": f'  "{self.corpus}"  '})
        self.assertEqual(status, 200)                # forgiving: quotes/whitespace ok
        self.assertEqual(st["reports"], 20)
        self.assertEqual(st["counts"], {"civil": 20})

        status, fs = self._req("POST", "/api/feed/send", {"dest": str(self.dest), "n": 3})
        self.assertEqual(status, 200)
        self.assertEqual((fs["delivered"], fs["total"]), (3, 20))
        self.assertEqual(len(list(self.dest.glob("*.md"))), 3)
        self.assertTrue(any("skickade 3" in line for line in fs["log"]))

        status, fs = self._req("GET", "/api/feed/status")
        self.assertEqual((status, fs["delivered"], fs["running"]), (200, 3, False))
        self.assertIsNotNone(fs["next"])

        status, fs = self._req("POST", "/api/feed/reset", {})
        self.assertEqual((status, fs["delivered"]), (200, 0))
        self.assertEqual(list(self.dest.glob("*.md")), [])

        dest2 = Path(self._tmp.name) / "inkorg2"    # ändrad målmapp => ny feeder, inte den gamla
        status, fs = self._req("POST", "/api/feed/send", {"dest": str(dest2), "n": 2})
        self.assertEqual(status, 200)
        self.assertEqual(len(list(dest2.glob("*.md"))), 2)
        self.assertEqual(list(self.dest.glob("*.md")), [])

    def test_feed_control_without_feed_is_409(self):
        fresh = gui.GuiState()                       # isolerad state, ingen feeder
        with self.assertRaises(gui.ApiError) as cm:
            fresh.feed_control("pause")
        self.assertEqual(cm.exception.status, 409)

    def test_minutes_is_forgiving(self):
        self.assertEqual(gui._minutes("7,5"), 7.5)   # svensk decimal
        self.assertEqual(gui._minutes(" 15 "), 15.0)
        for bad in ("abc", 0, -1, 999999):
            with self.assertRaises(gui.ApiError):
                gui._minutes(bad)

    def test_cli_wiring(self):
        from corpusgen.cli import build_parser
        a = build_parser().parse_args(["gui", "--port", "7710", "--no-browser"])
        self.assertEqual((a.port, a.no_browser), (7710, True))

    def test_parse_endpoint(self):
        status, r = self._req("POST", "/api/parse", {"text": "33V XF 66651 79308"})
        self.assertEqual(status, 200)
        self.assertEqual(r["kind"], "mgrs")
        self.assertTrue(59.2 < r["lat"] < 59.4)
        self.assertEqual(self._req("POST", "/api/parse", {"text": "strunt"})[0], 400)

    def test_preview_locations_radius_and_polygon(self):
        base = {"aoi": "60.345, 17.422", "area": "airport", "callsigns": "AQ,BQ", "seed": "1"}
        status, r = self._req("POST", "/api/preview-locations", dict(base, radius="3"))
        self.assertEqual(status, 200)
        self.assertEqual(len(r["locations"]), 8)             # 2 callsigns × 4
        self.assertIsNone(r["polygon"])
        for loc in r["locations"]:
            self.assertIn(loc["sector"], (0, 1))

        poly = [[60.30, 17.37], [60.30, 17.47], [60.40, 17.47], [60.40, 17.37]]
        status, r = self._req("POST", "/api/preview-locations", dict(base, polygon=poly))
        self.assertEqual(status, 200)
        self.assertEqual(r["polygon"], poly)
        from corpusgen.coords import point_in_polygon
        for loc in r["locations"]:
            self.assertTrue(point_in_polygon(loc["lat"], loc["lon"], poly))

    def test_generate_with_polygon(self):
        poly = [[60.30, 17.37], [60.30, 17.47], [60.40, 17.47], [60.40, 17.37]]
        out = str(Path(self._tmp.name) / "polykorpus")
        body = {"aoi": "60.345,17.422", "area": "airport", "from": "2026-06-15",
                "days": "5", "reports": "30", "seed": "3", "out": out, "polygon": poly}
        status, j = self._req("POST", "/api/generate", body)
        self.assertEqual(status, 200)
        job = self._poll_job(j["job"])
        self.assertEqual(job["status"], "done", job)
        meta = json.loads((Path(out) / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["polygon"], poly)

    def test_generate_rejects_bad_polygon(self):
        body = {"aoi": "60.3,17.4", "from": "2026-06-15", "out": "x",
                "polygon": [[60.3, 17.4], [60.4, 17.5]]}   # only 2 vertices
        self.assertEqual(self._req("POST", "/api/generate", body)[0], 400)

    def test_capabilities(self):
        status, cap = self._req("GET", "/api/capabilities")
        self.assertEqual(status, 200)
        self.assertIsInstance(cap["images"], bool)

    def _poll_job(self, jid, tries=100):
        import time
        for _ in range(tries):
            status, j = self._req("GET", f"/api/jobs/{jid}")
            self.assertEqual(status, 200)
            if j["status"] != "running":
                return j
            time.sleep(0.1)
        self.fail("jobbet blev aldrig klart")

    def test_preview_is_exact_prefix_of_real_run(self):
        body = {"aoi": "60.345, 17.422", "area": "airport", "from": "2026-06-15",
                "days": "5", "callsigns": "AQ,BQ", "seed": "1"}
        status, pv = self._req("POST", "/api/preview", body)
        self.assertEqual(status, 200)
        self.assertEqual(len(pv["reports"]), 3)
        self.assertGreater(pv["estimate"], 3)       # 22/dag × 5 dagar × årstid
        with tempfile.TemporaryDirectory() as d:    # samma parametrar, skarp körning
            c = generate.build_normal(out=d, lat=60.345, lon=17.422, radius=3.0,
                                      area="airport", start=datetime(2026, 6, 15), days=5,
                                      callsigns=["AQ", "BQ"], seed=1, reports=3)
            for got, row in zip(pv["reports"], c.ground_truth):
                self.assertEqual(got["file"], row["file"])
                real = (Path(d) / row["file"]).read_text(encoding="utf-8")
                self.assertEqual(got["text"], real)

    def test_generate_job_and_overwrite_guard(self):
        out = str(Path(self._tmp.name) / "nykorpus")
        body = {"aoi": "60.3, 17.4", "area": "rural", "from": "2026-06-15",
                "days": "3", "reports": "15", "seed": "7", "out": out}
        status, j = self._req("POST", "/api/generate", body)
        self.assertEqual(status, 200)
        job = self._poll_job(j["job"])
        self.assertEqual(job["status"], "done", job)
        self.assertEqual(job["result"]["reports"], 15)
        self.assertEqual(job["result"]["counts"], {"civil": 15})
        status, st = self._req("GET", "/api/state")
        self.assertEqual(st["active_corpus"], out)  # nya korpusen blev aktiv

        status, err = self._req("POST", "/api/generate", body)
        self.assertEqual(status, 409)               # utmappen är nu en korpus
        self.assertIn("bekräfta för att fortsätta", err["error"])
        status, j = self._req("POST", "/api/generate", dict(body, overwrite=True))
        self.assertEqual(status, 200)
        self.assertEqual(self._poll_job(j["job"])["status"], "done")

        target_file = Path(self._tmp.name) / "enfil.txt"
        target_file.write_text("x", encoding="utf-8")
        status, err = self._req("POST", "/api/generate", dict(body, out=str(target_file)))
        self.assertEqual(status, 400)               # utmapp som är en fil: 400, inte 500
        self.assertIn("fil", err["error"])

    def test_generate_validates_input(self):
        ok = {"aoi": "60.3,17.4", "from": "2026-06-15", "out": "x"}
        for broken in ({"aoi": "999,17"}, {"aoi": ""}, {"from": "15/6"},
                       {"days": "0"}, {"area": "mars"}, {"out": ""}):
            status, err = self._req("POST", "/api/generate", dict(ok, **broken))
            self.assertEqual(status, 400, (broken, err))
            self.assertTrue(err["error"], broken)


if __name__ == "__main__":
    unittest.main()
