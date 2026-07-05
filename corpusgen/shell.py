"""Interactive shell for 7S-generator.

`7s-generator` (or `python3 -m corpusgen`) with no arguments launches this REPL. It
wraps the same commands as the one-shot CLI — generate / add-hostiles / add-protesters
/ feed — with identical flags (parsed by the shared `cli.build_parser`), but adds:

  * a remembered *active corpus* so augment/feed commands don't retype --corpus,
  * a background, pausable auto-feed (feed --auto) that leaves the prompt live.

Command names and flags stay English so scripts/CI behave identically to the CLI."""
from pathlib import Path
import shlex

from .corpus import Corpus
from . import generate, feed
from .cli import build_parser

_AUGMENT = ("add-hostiles", "add-protesters")
_PARSED = ("generate", "add-hostiles", "add-protesters", "feed")

WELCOME = r"""
  7S-generator — interactive shell
  Build a synthetic 7S corpus, layer threats/noise, then drip it to a folder.
"""

HELP = """\
Commands (each takes the same flags as `7s-generator <cmd> -h`):
  generate --aoi LAT,LON --from YYYY-MM-DD --out DIR [--area .. --days .. --images .. --obsidian]
                      build a normal-activity corpus; becomes the active corpus
                      (--obsidian => exact app format; default => portable Markdown)
  add-hostiles --type TYPE [--corpus DIR] [--count N]
                      inject a hostile cell (recon/sabotage/infiltration/terrorism)
  add-protesters --type TYPE [--corpus DIR] [--count N]
                      inject a benign cluster (demonstranter/miljoaktivister/…)
  feed --dest DIR [--corpus DIR] [--auto MINS | --send N | --status | --reset]
                      drip reports to any folder; --auto runs in the background

Session:
  use DIR             set the active corpus (used when --corpus is omitted)
  status              show the active corpus and any running feed
  pause | resume | stop
                      control a background auto-feed (prompt stays live)
  help                show this text
  quit                leave (stops any running feed)

Omit --corpus on add-*/feed and the active corpus is used. Run `<cmd> -h` for details.
"""


class Shell:
    def __init__(self):
        self.parser = build_parser()
        self.current = None      # active corpus dir (Path)
        self.feeder = None       # last feed.Feeder (may be running in background)

    # --- parsing -------------------------------------------------------------
    def _parse(self, tokens):
        """Parse via the shared CLI parser; return args, or None on error/-h
        (argparse raises SystemExit, which would otherwise kill the shell)."""
        try:
            return self.parser.parse_args(tokens)
        except SystemExit:
            return None

    # --- command handlers ----------------------------------------------------
    def _do_generate(self, a):
        frm = getattr(a, "from")
        days = (a.to - frm).days + 1 if a.to else a.days
        if days <= 0:
            print("  ? empty date range")
            return
        try:
            c = generate.build_normal(
                out=a.out, lat=a.aoi[0], lon=a.aoi[1], radius=a.radius, area=a.area,
                start=frm, days=days, callsigns=a.callsigns, seed=a.seed,
                reports=a.reports, obj_name=a.name, images=a.images, obsidian=a.obsidian)
        except Exception as e:                       # noqa: BLE001 - surface, don't crash
            print(f"  ? generate failed: {e}")
            return
        self.current = Path(a.out)
        print(f"  [{a.area}] wrote {len(c.ground_truth)} reports to {c.path} "
              f"({days} days, season {c.meta['season']}, {len(c.meta['locations'])} locations)")
        if a.images:
            n = sum(1 for r in c.ground_truth if r.get("plate"))
            print(f"  rendered plate photos for {n} report(s)")
        print(f"  active corpus: {self.current}   ground truth: {c.counts()}")

    def _do_augment(self, cmd, a):
        try:
            c = Corpus.load(a.corpus)
        except FileNotFoundError as e:
            print(f"  ? {e}")
            return
        if cmd == "add-hostiles":
            n = generate.add_hostiles(c, a.type, a.count, a.seed)
            print(f"  injected {n} {a.type} hostile(s) into {c.path}")
        else:
            n = generate.add_protesters(c, a.type, a.count, a.seed)
            print(f"  injected a {a.type} group of {n} into {c.path}")
        print(f"  ground truth: {c.counts()}")

    def _do_feed(self, a):
        if self.feeder and self.feeder.is_running():
            print("  ? a feed is already running — 'pause'/'resume'/'stop' it first.")
            return
        try:
            f = feed.Feeder(a.corpus, a.dest)
        except SystemExit as e:                      # Feeder aborts if no reports found
            print(f"  ? {e}")
            return
        self.feeder = f
        if a.status:
            f.status()
        elif a.reset:
            f.reset()
        elif a.send is not None:
            f.send(a.send)
        else:                                        # default action: background auto-feed
            mins = a.auto if a.auto is not None else 15.0
            if f.start_auto(mins) == "done":
                print("  (all reports already delivered)")
            else:
                print(f"  feeding {a.corpus} -> {a.dest} in background (~{mins:.0f} min).")
                print("  prompt is live — type 'pause', 'resume', 'stop', or 'status'.")

    # --- session commands ----------------------------------------------------
    def _use(self, tokens):
        if len(tokens) < 2:
            print("  ? use <dir>")
            return
        d = Path(tokens[1])
        if not d.exists():
            print(f"  ? not found: {d}")
            return
        self.current = d
        print(f"  active corpus: {d}")

    def _status(self):
        if self.current:
            try:
                print(f"  active corpus: {self.current}   {Corpus.load(self.current).counts()}")
            except Exception:                        # noqa: BLE001
                print(f"  active corpus: {self.current}")
        else:
            print("  no active corpus (run 'generate' or 'use <dir>')")
        if self.feeder:
            self.feeder.status()

    def _feed_control(self, cmd):
        if not (self.feeder and self.feeder.is_running()):
            print("  (no feed running)")
            return
        if cmd == "pause":
            self.feeder.pause()
            print("  paused.")
        elif cmd == "resume":
            self.feeder.resume()
            print("  resumed.")
        elif cmd == "stop":
            self.feeder.stop()
            print("  stopped.")

    # --- dispatch / loop -----------------------------------------------------
    def dispatch(self, line):
        """Run one shell line. Returns False to quit, True to keep going."""
        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"  ? {e}")
            return True
        if not tokens:
            return True
        cmd = tokens[0].lower()

        if cmd in ("quit", "exit", "q"):
            return False
        if cmd == "help":
            print(HELP)
            return True
        if cmd == "use":
            self._use(tokens)
            return True
        if cmd == "status":
            self._status()
            return True
        if cmd in ("pause", "resume", "stop"):
            self._feed_control(cmd)
            return True

        if cmd in _PARSED:
            # default omitted --corpus to the active corpus for augment/feed
            if cmd in _AUGMENT + ("feed",) and "--corpus" not in tokens:
                if self.current:
                    tokens += ["--corpus", str(self.current)]
                else:
                    print("  ? no active corpus — run 'generate', 'use <dir>', or pass --corpus")
                    return True
            args = self._parse(tokens)
            if args is None:
                return True
            if cmd == "generate":
                self._do_generate(args)
            elif cmd in _AUGMENT:
                self._do_augment(cmd, args)
            else:
                self._do_feed(args)
            return True

        print(f"  ? unknown command: {cmd}   (type 'help')")
        return True

    def run(self):
        print(WELCOME)
        print(HELP)
        while True:
            try:
                line = input("7S> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print("\n(interrupt — type 'quit' to leave; a background feed keeps running)")
                continue
            if not self.dispatch(line):
                break
        if self.feeder and self.feeder.is_running():
            self.feeder.stop()


def run():
    Shell().run()
