"""HTTP server for the local GUI — stdlib only.

Security model (loopback tool, not a public service): bind 127.0.0.1 only;
Host and Origin headers are validated on every request (DNS-rebinding guard);
mutations go via POST only; request bodies are size-capped before reading; no
filesystem content is served — only the embedded app.html and JSON APIs.
"""
import json
import tempfile
import threading
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

from .. import generate
from ..content import AREAS, SEASONS
from ..corpus import Corpus
from ..feed import Feeder

MAX_BODY = 64 * 1024
ALLOWED_HOSTS = ("127.0.0.1", "localhost", "[::1]")
PREVIEW_REPORTS = 3


class ApiError(Exception):
    """A user-facing request error: (status, Swedish message)."""
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class GuiState:
    """Session state shared across requests — mirrors the shell's model:
    one active corpus, one Feeder (possibly auto-feeding in the background)."""

    def __init__(self):
        self.lock = threading.Lock()     # protects feed_log/jobs/_gen_active
        self.mutex = threading.Lock()    # serialises mutating API actions (tab races)
        self.current = None              # Path of the active corpus
        self.feeder = None
        self.feed_dest = None
        self.feed_log = deque(maxlen=200)
        self.jobs = {}                   # job id -> {"status": running|done|error, ...}
        self._job_seq = 0
        self._gen_active = set()         # out dirs with a generate job in flight

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
        with self.mutex:
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
        with self.mutex:
            f = self._new_feeder(body)
            minutes = _minutes(body.get("minutes", 15))
            result = f.start_auto(minutes)
            if result == "done":
                self.sink("(alla rapporter redan levererade)")
            else:
                self.sink(f"matar {self.current} -> {self.feed_dest} över ~{minutes:g} min")
            return self.feed_status()

    def feed_send(self, body):
        with self.mutex:
            if self.feeder and self.feeder.is_running():
                raise ApiError(409, "en matning pågår — pausa eller stoppa den först")
            raw = str(body.get("dest", "")).strip().strip('"').strip("'")
            dest_changed = bool(raw) and self.feed_dest != str(Path(raw).expanduser())
            src_changed = bool(self.feeder and self.current
                               and self.feeder.src != Path(self.current))
            f = self.feeder
            if f is None or dest_changed or src_changed:  # stale feeder: rebuild
                f = self._new_feeder(body)
            n = body.get("n", 1)
            try:
                n = max(1, int(n))
            except (TypeError, ValueError):
                raise ApiError(400, f"ogiltigt antal: {n!r}")
            sent = f.send(n)
            self.sink(f"skickade {sent} rapport(er) manuellt")
            return self.feed_status()

    # --- map helpers -----------------------------------------------------------
    def parse_coord(self, body):
        """Parse a single coordinate string (any supported format) for the map/form."""
        from ..coords import parse_point
        try:
            lat, lon, kind = parse_point(body.get("text", ""))
        except ValueError as e:
            raise ApiError(400, str(e))
        return {"lat": lat, "lon": lon, "kind": kind}

    def preview_locations(self, body):
        """Where the named locations would land for this AOI/radius/area/polygon —
        deterministic (same seed) and cheap (no reports written). Feeds the map."""
        import random as _random
        lat, lon = _parse_aoi(body.get("aoi", ""))
        area = str(body.get("area") or "rural").strip().lower()
        if area not in AREAS:
            raise ApiError(400, f"okänd områdestyp: {area}")
        radius = _number(body.get("radius"), "radie", 0.1, 100, default=3.0)
        callsigns = [c.strip().upper() for c in
                     str(body.get("callsigns") or "AQ,BQ,CQ,DQ").split(",") if c.strip()]
        if not callsigns:
            raise ApiError(400, "minst en anropssignal krävs")
        polygon = _parse_polygon(body.get("polygon"))
        seed = _number(body.get("seed"), "seed", -2**31, 2**31, cast=int, default=2026)
        locs = generate.build_locations(lat, lon, radius, area, callsigns,
                                        _random.Random(seed), polygon=polygon)
        return {"aoi": [lat, lon], "radius": radius, "polygon": polygon,
                "locations": [{"lat": l["lat"], "lon": l["lon"], "sector": l["sector"],
                               "callsign": l["callsign"], "name": l["name"]} for l in locs]}

    # --- generate --------------------------------------------------------------
    def preview(self, body):
        """First PREVIEW_REPORTS reports of the exact corpus `generate` would
        write: rng is consumed sequentially per report after a fixed setup, so
        a truncated run is a prefix of the full run (same seed)."""
        p = _gen_params(body, for_preview=True)
        est = p.pop("_estimate")
        season = p.pop("_season")
        with tempfile.TemporaryDirectory() as tmp:
            p.update(out=tmp, reports=min(PREVIEW_REPORTS, p["reports"] or PREVIEW_REPORTS),
                     images=False)
            c = generate.build_normal(**p)
            reports = [{"file": r["file"],
                        "text": (Path(tmp) / r["file"]).read_text(encoding="utf-8")}
                       for r in c.ground_truth]
        return {"estimate": est, "season": season, "locations": len(c.meta["locations"]),
                "reports": reports}

    def start_generate(self, body):
        with self.mutex:
            p = _gen_params(body)
            out = Path(p["out"])
            if out.is_file():
                raise ApiError(400, "utmappen är en fil — ange en mapp")
            if str(out) in self._gen_active:
                raise ApiError(409, "en generering pågår redan mot den mappen — vänta")
            if out.is_dir() and any(out.iterdir()) and not body.get("overwrite"):
                if (out / "meta.json").exists():
                    msg = ("utmappen är en befintlig korpus — dess rapporter raderas "
                           "och ersätts (bekräfta för att fortsätta)")
                else:
                    n_md = len(list(out.glob("*.md")))
                    msg = (f"utmappen är inte tom och inte en korpus — {n_md} .md-fil(er) "
                           "på toppnivån och ev. attachments/ RADERAS "
                           "(bekräfta för att fortsätta)")
                raise ApiError(409, msg)
            with self.lock:
                self._job_seq += 1
                jid = str(self._job_seq)
                self.jobs[jid] = {"status": "running"}
                self._gen_active.add(str(out))
            p.pop("_estimate"), p.pop("_season")
            threading.Thread(target=self._run_generate, args=(jid, p), daemon=True).start()
            return {"job": jid}

    def _run_generate(self, jid, params):
        try:
            c = generate.build_normal(**params)
            result = {"path": str(c.path), "reports": len(c.ground_truth),
                      "counts": c.counts(), "season": c.meta["season"],
                      "locations": len(c.meta["locations"]),
                      "plates": sum(1 for r in c.ground_truth if r.get("plate"))}
            with self.lock:
                self.jobs[jid] = {"status": "done", "result": result}
            self.current = Path(params["out"])       # new corpus becomes active
        except Exception as e:                       # noqa: BLE001 - job result carries it
            with self.lock:
                self.jobs[jid] = {"status": "error", "error": str(e)}
        finally:
            with self.lock:
                self._gen_active.discard(params["out"])
                for k in sorted(self.jobs, key=int):  # bounded job history
                    if len(self.jobs) <= 50:
                        break
                    if self.jobs[k]["status"] != "running":
                        del self.jobs[k]

    def job(self, jid):
        with self.lock:
            j = self.jobs.get(jid)
        if not j:
            raise ApiError(404, f"okänt jobb: {jid}")
        return j

    def feed_control(self, action):
        with self.mutex:
            return self._feed_control(action)

    def _feed_control(self, action):
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


def _parse_aoi(text):
    """AOI in any supported format (decimal / MGRS / DMS / SWEREF 99 TM),
    via corpusgen.coords. Returns (lat, lon)."""
    from ..coords import parse_point
    try:
        lat, lon, _ = parse_point(text)
    except ValueError as e:
        raise ApiError(400, f"AOI: {e}")
    return lat, lon


def _parse_polygon(raw):
    """Validate a polygon from the request: a list of [lat, lon] pairs (>=3),
    each range-checked. Returns None for an empty/absent polygon."""
    if not raw:
        return None
    if not isinstance(raw, list) or len(raw) < 3:
        raise ApiError(400, "polygon behöver minst 3 hörn")
    poly = []
    for pt in raw:
        try:
            lat, lon = float(pt[0]), float(pt[1])
        except (TypeError, ValueError, IndexError):
            raise ApiError(400, f"ogiltigt polygonhörn: {pt!r}")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ApiError(400, f"polygonhörn utanför giltigt intervall: {pt!r}")
        poly.append([lat, lon])
    return poly


def _number(v, name, lo, hi, cast=float, default=None):
    if v in (None, ""):
        if default is None:
            raise ApiError(400, f"ange {name}")
        return default
    try:
        n = cast(str(v).replace(",", ".").strip()) if cast is float else cast(str(v).strip())
    except (TypeError, ValueError):
        raise ApiError(400, f"ogiltigt värde för {name}: {v!r}")
    if not lo <= n <= hi:
        raise ApiError(400, f"{name} måste vara mellan {lo} och {hi}")
    return n


def _has_pillow():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _gen_params(body, for_preview=False):
    """Validate a generate/preview request into build_normal kwargs (plus the
    bookkeeping keys _estimate/_season, popped by the callers)."""
    lat, lon = _parse_aoi(body.get("aoi", ""))
    area = str(body.get("area") or "rural").strip().lower()
    if area not in AREAS:
        raise ApiError(400, f"okänd områdestyp: {area} (giltiga: {', '.join(sorted(AREAS))})")
    raw_from = str(body.get("from", "")).strip()
    try:
        start = datetime.strptime(raw_from, "%Y-%m-%d")
    except ValueError:
        raise ApiError(400, f"ogiltigt startdatum (ÅÅÅÅ-MM-DD): {raw_from!r}")
    days = _number(body.get("days"), "dagar", 1, 365, cast=int, default=14)
    callsigns = [c.strip().upper() for c in str(body.get("callsigns") or "AQ,BQ,CQ,DQ").split(",")
                 if c.strip()]
    if not callsigns:
        raise ApiError(400, "minst en anropssignal krävs")
    reports = body.get("reports")
    reports = None if reports in (None, "") else _number(reports, "antal rapporter", 1, 100000, cast=int)
    images = bool(body.get("images"))
    if images and not for_preview and not _has_pillow():
        raise ApiError(400, "skyltfoton kräver Pillow — installera images-tillägget")
    out = str(body.get("out", "")).strip().strip('"').strip("'")
    if not out and not for_preview:
        raise ApiError(400, "ange en utmapp")
    polygon = _parse_polygon(body.get("polygon"))
    season = generate.season_of(start.month)
    estimate = reports if reports is not None else round(
        AREAS[area]["reports_per_day"] * days * SEASONS[season]["civ_mult"])
    return {
        "out": str(Path(out).expanduser()) if out else "",
        "lat": lat, "lon": lon,
        "radius": _number(body.get("radius"), "radie", 0.1, 100, default=3.0),
        "area": area, "start": start, "days": days, "callsigns": callsigns,
        "seed": _number(body.get("seed"), "seed", -2**31, 2**31, cast=int, default=2026),
        "reports": reports, "obj_name": str(body.get("name") or "objektet").strip() or "objektet",
        "images": images, "obsidian": bool(body.get("obsidian")), "polygon": polygon,
        "_estimate": estimate, "_season": season,
    }


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
            # img-src also allows the OSM tile host: the *browser* fetches tiles
            # only when the user opts into the background map — the Python server
            # itself never makes a network request, so the tool stays air-gapped.
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'; "
                             "img-src 'self' data: https://tile.openstreetmap.org; "
                             "base-uri 'none'; form-action 'none'")
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
            elif path == "/api/capabilities":
                self._send(200, {"images": _has_pillow()})
            elif path.startswith("/api/jobs/"):
                try:
                    self._send(200, state.job(path.rsplit("/", 1)[-1]))
                except ApiError as e:
                    self._fail(e.status, str(e))
            else:
                self._fail(404, "finns inte")

        def do_POST(self):
            if not self._guard():
                return
            path = urlsplit(self.path).path
            routes = {"/api/use": state.use,
                      "/api/generate": state.start_generate,
                      "/api/preview": state.preview,
                      "/api/preview-locations": state.preview_locations,
                      "/api/parse": state.parse_coord,
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
