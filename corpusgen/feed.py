"""Feeder — drip a corpus from one folder into a destination folder over time,
mimicking a central app trickling messages out. Copies the .md reports in
chronological order plus any referenced attachments (so image embeds resolve).

Auto-feed can run in a background thread (`start_auto`) so a prompt stays live and
the feed can be paused/resumed/stopped on demand; `auto()` is the blocking wrapper
used by the one-shot CLI."""
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

_FM_TIME = re.compile(r"^tidpunkt:\s*(.+)$", re.MULTILINE)
_EMBED = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")  # Obsidian wikilink image embed


def _load(src):
    items = []
    for p in sorted(src.glob("*.md")):
        m = _FM_TIME.search(p.read_text(encoding="utf-8"))
        if m:
            items.append((datetime.fromisoformat(m.group(1).strip().strip('"')), p))
    items.sort(key=lambda x: x[0])
    return items


class Feeder:
    def __init__(self, src, dest):
        self.src = Path(src)
        self.dest = Path(dest)
        self.dest.mkdir(parents=True, exist_ok=True)
        self.reports = _load(self.src)
        if not self.reports:
            sys.exit(f"No reports found in {self.src}")
        self.idx = 0
        present = {p.name for p in self.dest.glob("*.md")}
        while self.idx < len(self.reports) and self.reports[self.idx][1].name in present:
            self.idx += 1
        # background auto-feed control
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread = None

    def _copy(self, p):
        shutil.copy2(p, self.dest / p.name)
        text = p.read_text(encoding="utf-8")
        for rel in _EMBED.findall(text):
            img = self.src / rel
            if img.exists():
                out = self.dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(img, out)

    def send(self, n=1):
        sent = 0
        with self._lock:
            while sent < n and self.idx < len(self.reports):
                ts, p = self.reports[self.idx]
                self._copy(p)
                print(f"  + {p.name}   [{ts:%a %Y-%m-%d %H:%M}]")
                self.idx += 1
                sent += 1
            done = self.idx >= len(self.reports)
        if done:
            print("  (all reports delivered)")
        return sent

    # --- background auto-feed ------------------------------------------------
    def start_auto(self, minutes=15.0):
        """Begin delivering the remaining reports over ~`minutes` in a background
        thread. Returns 'started', 'running' (one already going), or 'done'."""
        if self.is_running():
            return "running"
        with self._lock:
            remaining = len(self.reports) - self.idx
        if remaining <= 0:
            return "done"
        self._stop.clear()
        self._paused.clear()
        self._thread = threading.Thread(target=self._auto_loop, args=(minutes,), daemon=True)
        self._thread.start()
        return "started"

    def _interruptible_wait(self, seconds):
        """Wait `seconds` of *running* time in small slices; time spent paused does
        not count. Returns False if stopped mid-wait, True when the wait completes."""
        remaining = seconds
        while remaining > 0:
            if self._stop.is_set():
                return False
            if self._paused.is_set():
                time.sleep(0.1)
                continue
            dt = min(0.1, remaining)
            time.sleep(dt)
            remaining -= dt
        return not self._stop.is_set()

    def _auto_loop(self, minutes):
        with self._lock:
            remaining = self.reports[self.idx:]
        if not remaining:
            print("\n  (all reports already delivered)")
            return
        t0, t1 = remaining[0][0], self.reports[-1][0]
        span = (t1 - t0).total_seconds() or 1.0
        factor = span / (minutes * 60.0)
        print(f"\n  Feeding {len(remaining)} reports over ~{minutes:g} min "
              f"(≈{factor:.0f}× real time).")
        prev = t0
        for ts, p in remaining:
            wait = min(max(0.0, (ts - prev).total_seconds() / factor), minutes * 60.0)
            if not self._interruptible_wait(wait):
                print("\n  (feed stopped)")
                return
            with self._lock:
                self._copy(p)
                self.idx += 1
            print(f"\n  + {p.name}   [{ts:%a %H:%M}]")
            prev = ts
        print("\n  (feed complete)")

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    def stop(self):
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self):
        return self._paused.is_set()

    def progress(self):
        with self._lock:
            return self.idx, len(self.reports)

    def auto(self, minutes=15.0):
        """Blocking auto-feed for the one-shot CLI: start in the background and wait,
        so Ctrl-C stops it cleanly."""
        state = self.start_auto(minutes)
        if state == "done":
            print("  (all reports already delivered)")
            return
        print("  Ctrl-C to stop.")
        try:
            while self.is_running():
                self._thread.join(timeout=0.2)
        except KeyboardInterrupt:
            self.stop()
            print("\n  stopped.")

    # --- status / reset ------------------------------------------------------
    def status(self):
        with self._lock:
            done, total = self.idx, len(self.reports)
            nxt = self.reports[self.idx] if done < total else None
        state = "running" if self.is_running() else "idle"
        if self.is_running() and self.is_paused():
            state = "paused"
        print(f"  Delivered {done}/{total}  ({state}).")
        if nxt:
            ts, p = nxt
            print(f"  Next: {p.name} [{ts:%a %Y-%m-%d %H:%M}]")
        print(f"  Span: {self.reports[0][0]:%Y-%m-%d %H:%M} -> {self.reports[-1][0]:%Y-%m-%d %H:%M}")

    def reset(self):
        if self.is_running():
            print("  ? a feed is running — 'stop' it first.")
            return
        with self._lock:
            r = sum(1 for p in self.dest.glob("*.md") for _ in [p.unlink()])
            self.idx = 0
        print(f"  Removed {r} reports. Reset to start.")


def run(src, dest, once=None):
    """Interactive REPL, or a single one-shot action (`once` = ('send', n) etc.)."""
    f = Feeder(src, dest)
    if once:
        cmd, arg = once
        {"send": lambda: f.send(arg or 1), "auto": lambda: f.auto(arg or 15.0),
         "reset": f.reset, "status": f.status}[cmd]()
        return
    print(f"Loaded {len(f.reports)} reports -> {f.dest}")
    f.status()
    print("Commands: send [n] | auto [mins] | pause | resume | stop | status | reset | quit")
    while True:
        try:
            raw = input("feed> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        parts = raw.split()
        cmd = parts[0].lower()
        if cmd in ("quit", "exit", "q"):
            f.stop()
            break
        elif cmd == "send":
            if f.is_running():
                print("  ? a feed is running — 'pause' or 'stop' it first.")
            else:
                f.send(int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1)
        elif cmd == "auto":
            mins = float(parts[1]) if len(parts) > 1 else 15.0
            state = f.start_auto(mins)
            if state == "running":
                print("  ? a feed is already running — 'stop' it first.")
            elif state == "done":
                print("  (all reports already delivered)")
            else:
                print("  feeding in background — 'pause' to hold, 'stop' to end.")
        elif cmd == "pause":
            f.pause() if f.is_running() else print("  (no feed running)")
        elif cmd == "resume":
            f.resume() if f.is_running() else print("  (no feed running)")
        elif cmd == "stop":
            f.stop()
            print("  stopped.")
        elif cmd == "status":
            f.status()
        elif cmd == "reset":
            f.reset()
        else:
            print("  ? send [n] | auto [mins] | pause | resume | stop | status | reset | quit")
