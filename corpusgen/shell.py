"""Interactive shell for 7S-generator.

`7s-generator` (or `python3 -m corpusgen`) with no arguments launches this REPL. It
wraps the same commands as the one-shot CLI — generate / add-hostiles / add-protesters
/ feed — with identical flags (parsed by the shared `cli.build_parser`), but adds:

  * a remembered *active corpus* so augment/feed commands don't retype --corpus,
  * a background, pausable auto-feed (feed --auto) that leaves the prompt live.

Command names and flags stay English so scripts/CI behave identically to the CLI;
the on-screen text is Swedish."""
from pathlib import Path
import shlex

from .corpus import Corpus
from . import generate, feed
from .cli import build_parser

_AUGMENT = ("add-hostiles", "add-protesters")
_PARSED = ("generate", "add-hostiles", "add-protesters", "feed", "score")

# Short banner shown at startup — keep it light for someone who uses this rarely.
WELCOME = """
  7S-generator — bygg och mata ut syntetiska 7S-rapporter.

  Kom igång:
    generate --aoi 60.3,17.4 --area airport --from 2026-06-15 --out ./korpus
    add-hostiles --type recon             lägg till en hotcell
    add-protesters --type demonstranter   lägg till brus
    feed --dest ./inkorg --auto 10        mata ut rapporter (i bakgrunden)

  Skriv 'hjälp' för alla kommandon, 'avsluta' för att gå ur.
"""

# Full reference shown on `hjälp`.
HELP = """\
Kommandon (samma flaggor som `7s-generator <kmd> -h`):
  generate --aoi LAT,LON --from ÅÅÅÅ-MM-DD --out MAPP [--area .. --days .. --images .. --obsidian]
                      bygg en normalkorpus; blir den aktiva korpusen
                      (--obsidian => exakt appformat; standard => portabel Markdown)
  add-hostiles --type TYP [--corpus MAPP] [--count N]
                      injicera en hotcell (recon/sabotage/infiltration/terrorism)
                      --count = antal personer; var och en ger flera rapporter (1–4×)
  add-protesters --type TYP [--corpus MAPP] [--count N]
                      injicera ett godartat kluster (demonstranter/miljöaktivister/…)
                      --count = antal rapporter i klustret
  feed --dest MAPP [--corpus MAPP] [--auto MIN | --send N | --status | --reset]
                      mata ut rapporter till valfri mapp; --auto kör i bakgrunden
  score --detections FIL [--corpus MAPP] [--json] [--min-f1 X]
                      poängsätt en detektors utpekningar mot korpusens facit

Session:
  use MAPP            sätt aktiv korpus (används när --corpus utelämnas)
  status             visa aktiv korpus och pågående matning
  pause | resume | stop
                     styr en bakgrundsmatning (prompten är kvar)
  hjälp              visa den här texten
  avsluta            gå ur (stoppar pågående matning)

Utelämna --corpus på add-*/feed så används den aktiva korpusen. Kör `<kmd> -h` för detaljer.
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
            print("  ? tomt datumintervall")
            return
        try:
            c = generate.build_normal(
                out=a.out, lat=a.aoi[0], lon=a.aoi[1], radius=a.radius, area=a.area,
                start=frm, days=days, callsigns=a.callsigns, seed=a.seed,
                reports=a.reports, obj_name=a.name, images=a.images, obsidian=a.obsidian)
        except Exception as e:                       # noqa: BLE001 - surface, don't crash
            print(f"  ? generering misslyckades: {e}")
            return
        self.current = Path(a.out)
        print(f"  [{a.area}] skrev {len(c.ground_truth)} rapporter till {c.path} "
              f"({days} dagar, årstid {c.meta['season']}, {len(c.meta['locations'])} platser)")
        if a.images:
            n = sum(1 for r in c.ground_truth if r.get("plate"))
            print(f"  renderade skyltfoton för {n} rapport(er)")
        print(f"  aktiv korpus: {self.current}   facit: {c.counts()}")

    def _do_augment(self, cmd, a):
        try:
            c = Corpus.load(a.corpus)
        except FileNotFoundError as e:
            print(f"  ? {e}")
            return
        if cmd == "add-hostiles":
            n = generate.add_hostiles(c, a.type, a.count, a.seed)
            print(f"  injicerade {n} {a.type}-fiende(r) i {c.path}")
        else:
            n = generate.add_protesters(c, a.type, a.count, a.seed)
            print(f"  injicerade en {a.type}-grupp på {n} i {c.path}")
        print(f"  facit: {c.counts()}")

    def _do_score(self, a):
        from . import score
        try:
            c = Corpus.load(a.corpus)
            score.run(c, a.detections, json_out=a.json, min_f1=a.min_f1,
                      out=lambda s: print("  " + s.replace("\n", "\n  ")))
        except Exception as e:                       # noqa: BLE001 - surface, don't kill the shell
            print(f"  ? {e}")

    @staticmethod
    def _bg_print(msg):
        """Background-feed messages: print, then redraw the prompt so the line
        the user is typing at 7S> isn't left visually swallowed."""
        print(msg)
        print("7S> ", end="", flush=True)

    def _do_feed(self, a):
        if self.feeder and self.feeder.is_running():
            print("  ? en matning pågår redan — 'pause'/'resume'/'stop' den först.")
            return
        try:
            f = feed.Feeder(a.corpus, a.dest, sink=self._bg_print)
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
                print("  (alla rapporter redan levererade)")
            else:
                print(f"  matar {a.corpus} -> {a.dest} i bakgrunden (~{mins:g} min).")
                print("  prompten är kvar — skriv 'pause', 'resume', 'stop' eller 'status'.")

    # --- session commands ----------------------------------------------------
    def _use(self, tokens):
        if len(tokens) < 2:
            print("  ? use <mapp>")
            return
        d = Path(tokens[1])
        if not d.exists():
            print(f"  ? hittades inte: {d}")
            return
        self.current = d
        print(f"  aktiv korpus: {d}")

    def _status(self):
        if self.current:
            try:
                print(f"  aktiv korpus: {self.current}   {Corpus.load(self.current).counts()}")
            except Exception:                        # noqa: BLE001
                print(f"  aktiv korpus: {self.current}")
        else:
            print("  ingen aktiv korpus (kör 'generate' eller 'use <mapp>')")
        if self.feeder:
            self.feeder.status()

    def _feed_control(self, cmd):
        if not (self.feeder and self.feeder.is_running()):
            print("  (ingen matning pågår)")
            return
        if cmd == "pause":
            self.feeder.pause()
            print("  pausad.")
        elif cmd == "resume":
            self.feeder.resume()
            print("  återupptagen.")
        elif cmd == "stop":
            self.feeder.stop()
            print("  stoppad.")

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

        if cmd in ("quit", "exit", "q", "avsluta"):
            return False
        if cmd in ("help", "hjälp", "hjalp", "?"):
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
            # default omitted --corpus to the active corpus for augment/feed/score
            # (recognise the --corpus=PATH form too, or we'd silently override it)
            has_corpus = any(t == "--corpus" or t.startswith("--corpus=") for t in tokens)
            if cmd in _AUGMENT + ("feed", "score") and not has_corpus:
                if self.current:
                    tokens += ["--corpus", str(self.current)]
                else:
                    print("  ? ingen aktiv korpus — kör 'generate', 'use <mapp>' eller ange --corpus")
                    return True
            args = self._parse(tokens)
            if args is None:
                return True
            if cmd == "generate":
                self._do_generate(args)
            elif cmd in _AUGMENT:
                self._do_augment(cmd, args)
            elif cmd == "score":
                self._do_score(args)
            else:
                self._do_feed(args)
            return True

        print(f"  ? okänt kommando: {cmd}   (skriv 'hjälp')")
        return True

    def run(self):
        print(WELCOME)
        while True:
            try:
                line = input("7S> ")
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print("\n(avbrott — skriv 'avsluta' för att gå ur; en bakgrundsmatning fortsätter)")
                continue
            if not self.dispatch(line):
                break
        if self.feeder and self.feeder.is_running():
            self.feeder.stop()


def run():
    Shell().run()
