"""HTTP server for the local GUI — stdlib only.

Security model (loopback tool, not a public service): bind 127.0.0.1 only;
Host and Origin headers are validated on every request (DNS-rebinding guard);
mutations go via POST only; request bodies are size-capped before reading; no
filesystem content is served — only the embedded app.html and JSON APIs.
"""
import json
import threading
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

from ..corpus import Corpus
from ..feed import Feeder

MAX_BODY = 64 * 1024
ALLOWED_HOSTS = ("127.0.0.1", "localhost", "[::1]")


class ApiError(Exception):
    """A user-facing request error: (status, Swedish message)."""
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class GuiState:
    """Session state shared across requests — mirrors the shell's model:
    one active corpus, one Feeder (possibly auto-feeding in the background)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current = None          # Path of the active corpus
        self.feeder = None
        self.feed_dest = None
        self.feed_log = deque(maxlen=200)

    def sink(self, msg):
        """Feeder background messages -> timestamped GUI log lines."""
        msg = " ".join(str(msg).split())
        if msg:
            with self.lock:
                self.feed_log.append(f"{datetime.now():%H:%M:%S}  {msg}")

    # --- api actions ---------------------------------------------------------
    def use(self, body):
        raw = str(body.get("path", "")).strip().strip('"').strip("'")
        if not raw:
            raise ApiError(400, "ange en korpusmapp")
        p = Path(raw).expanduser()
        if not p.is_dir():
            raise ApiError(400, f"hittades inte: {p}")
        if not (p / "meta.json").exists():
            raise ApiError(400, f"{p} saknar meta.json — inte en korpusmapp?")
        self.current = p
        return self.state()

    def state(self):
        st = {"active_corpus": str(self.current) if self.current else None,
              "counts": None, "reports": None}
        if self.current:
            try:
                c = Corpus.load(self.current)
                st["counts"] = c.counts()
                st["reports"] = len(c.ground_truth)
            except Exception as e:                   # noqa: BLE001 - surface, don't crash
                st["error"] = f"kunde inte läsa korpusen: {e}"
        st["feed"] = self.feed_status()
        return st

    def feed_status(self):
        f = self.feeder
        if not f:
            return {"exists": False, "dest": self.feed_dest}
        done, total = f.progress()
        nxt = None
        if done < total:
            ts, p = f.reports[done]
            nxt = {"file": p.name, "ts": ts.strftime("%Y-%m-%d %H:%M")}
        with self.lock:
            log = list(self.feed_log)
        return {"exists": True, "dest": self.feed_dest,
                "running": f.is_running(), "paused": f.is_paused(),
                "delivered": done, "total": total, "next": nxt, "log": log}

    def _require_feeder(self):
        if not self.feeder:
            raise ApiError(409, "ingen matning är uppsatt — starta en först")
        return self.feeder

    def _new_feeder(self, body):
        if self.feeder and self.feeder.is_running():
            raise ApiError(409, "en matning pågår redan — stoppa den först")
        if not self.current:
            raise ApiError(400, "ingen aktiv korpus — välj en i Korpus-fliken")
        raw = str(body.get("dest", "")).strip().strip('"').strip("'")
        if not raw and self.feed_dest:
            raw = self.feed_dest                 # forgiving: reuse the last dest
        if not raw:
            raise ApiError(400, "ange en målmapp")
        dest = Path(raw).expanduser()
        try:
            f = Feeder(str(self.current), str(dest), sink=self.sink)
        except SystemExit as e:                      # Feeder aborts if no reports found
            raise ApiError(400, str(e))
        self.feeder, self.feed_dest = f, str(dest)
        return f

    def feed_start(self, body):
        f = self._new_feeder(body)
        minutes = _minutes(body.get("minutes", 15))
        result = f.start_auto(minutes)
        if result == "done":
            self.sink("(alla rapporter redan levererade)")
        else:
            self.sink(f"matar {self.current} -> {self.feed_dest} över ~{minutes:g} min")
        return self.feed_status()

    def feed_send(self, body):
        if self.feeder and self.feeder.is_running():
            raise ApiError(409, "en matning pågår — pausa eller stoppa den först")
        f = self.feeder if self.feeder else self._new_feeder(body)
        n = body.get("n", 1)
        try:
            n = max(1, int(n))
        except (TypeError, ValueError):
            raise ApiError(400, f"ogiltigt antal: {n!r}")
        before = f.progress()[0]
        f.send(n)
        sent = f.progress()[0] - before
        self.sink(f"skickade {sent} rapport(er) manuellt")
        return self.feed_status()

    def feed_control(self, action):
        f = self._require_feeder()
        if action == "reset":
            if f.is_running():
                raise ApiError(409, "en matning pågår — stoppa den först")
            f.reset()
            self.sink("återställd — målmappen tömd på rapporter")
        elif action in ("pause", "resume", "stop"):
            if not f.is_running():
                raise ApiError(409, "ingen matning pågår")
            getattr(f, action)()
            self.sink({"pause": "pausad", "resume": "återupptagen", "stop": "stoppad"}[action])
        else:
            raise ApiError(404, f"okänd åtgärd: {action}")
        return self.feed_status()


def _minutes(v):
    """Forgiving minutes input: 15, '15', '7,5' (Swedish decimal comma)."""
    try:
        m = float(str(v).replace(",", ".").strip())
    except ValueError:
        raise ApiError(400, f"ogiltigt antal minuter: {v!r}")
    if not 0 < m <= 24 * 60:
        raise ApiError(400, "minuter måste vara mellan 0 och 1440")
    return m


def _app_html():
    return resources.files(__package__).joinpath("app.html").read_bytes()


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        server_version, sys_version = "7s-gui", ""   # leak no stack/version details

        # --- plumbing --------------------------------------------------------
        def log_message(self, fmt, *args):           # quiet: no per-request spam
            pass

        def _send(self, status, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else \
                json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'; "
                             "img-src 'self' data:; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def _fail(self, status, message):
            self._send(status, {"error": message})

        def _guard(self):
            """Host allowlist on every request; same-origin check on POST."""
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].lower()
            if host not in ALLOWED_HOSTS:
                self._fail(403, "otillåten Host")
                return False
            origin = self.headers.get("Origin")
            if self.command == "POST" and origin:
                o = urlsplit(origin)
                if (o.hostname or "").lower() not in ("127.0.0.1", "localhost", "::1"):
                    self._fail(403, "otillåten Origin")
                    return False
            return True

        def _body(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "ogiltig Content-Length")
            if length > MAX_BODY:
                raise ApiError(413, "för stor request-body")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                raise ApiError(400, "request-body är inte giltig JSON")
            if not isinstance(body, dict):
                raise ApiError(400, "request-body ska vara ett JSON-objekt")
            return body

        # --- routing ---------------------------------------------------------
        def do_GET(self):
            if not self._guard():
                return
            path = urlsplit(self.path).path
            if path in ("/", "/index.html"):
                self._send(200, _app_html(), ctype="text/html; charset=utf-8")
            elif path == "/api/state":
                self._send(200, state.state())
            elif path == "/api/feed/status":
                self._send(200, state.feed_status())
            else:
                self._fail(404, "finns inte")

        def do_POST(self):
            if not self._guard():
                return
            path = urlsplit(self.path).path
            routes = {"/api/use": state.use,
                      "/api/feed/start": state.feed_start,
                      "/api/feed/send": state.feed_send}
            try:
                if path in routes:
                    self._send(200, routes[path](self._body()))
                elif path.startswith("/api/feed/"):
                    self._body()                     # drain + validate size
                    self._send(200, state.feed_control(path.rsplit("/", 1)[-1]))
                else:
                    self._fail(404, "finns inte")
            except ApiError as e:
                self._fail(e.status, str(e))
            except Exception as e:                   # noqa: BLE001 - surface, don't crash
                self._fail(500, f"internt fel: {e}")

    return Handler


def run(port=7700, open_browser=True):
    state = GuiState()
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    except OSError as e:
        raise SystemExit(f"kunde inte lyssna på port {port} ({e}) — prova --port")
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"7S-generator GUI: {url}   (Ctrl-C stoppar)")
    if open_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstoppad.")
    finally:
        if state.feeder and state.feeder.is_running():
            state.feeder.stop()
        httpd.server_close()
