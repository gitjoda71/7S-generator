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


if __name__ == "__main__":
    unittest.main()
