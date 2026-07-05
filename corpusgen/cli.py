"""7S-generator CLI — build a synthetic 7S report corpus and layer threats/noise.

  generate        normal-activity corpus for an area of interest
  add-hostiles    inject a recon/sabotage/infiltration/terrorism cell
  add-protesters  inject a demonstrators/environmentalists/peace group (noise)
  feed            drip a corpus into a destination folder over time
"""
import argparse
import sys
from datetime import datetime

from .content import AREAS, HOSTILES, PROTESTERS
from .corpus import Corpus
from . import generate


class _Fmt(argparse.ArgumentDefaultsHelpFormatter,
           argparse.RawDescriptionHelpFormatter):
    """Show defaults on every option *and* keep epilog/example text raw."""


def _aoi(s):
    lat, lon = (float(x) for x in s.split(","))
    return lat, lon


def _callsigns(s):
    cs = [c.strip().upper() for c in s.split(",") if c.strip()]
    if not cs:
        raise argparse.ArgumentTypeError("need at least one callsign")
    return cs


def _date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def cmd_generate(a):
    if a.to:
        days = (a.to - getattr(a, "from")).days + 1
    else:
        days = a.days
    if days <= 0:
        sys.exit("error: empty date range")
    c = generate.build_normal(
        out=a.out, lat=a.aoi[0], lon=a.aoi[1], radius=a.radius, area=a.area,
        start=getattr(a, "from"), days=days, callsigns=a.callsigns, seed=a.seed,
        reports=a.reports, obj_name=a.name, images=a.images,
    )
    print(f"[{a.area}] wrote {len(c.ground_truth)} reports to {c.path} "
          f"({days} days, season {c.meta['season']}, {len(c.meta['locations'])} locations)")
    if a.images:
        n = sum(1 for r in c.ground_truth if r.get("plate"))
        print(f"rendered corroborating plate photos for {n} plate report(s)")
    print(f"ground truth: {c.counts()}")


def cmd_feed(a):
    from . import feed
    once = None
    for k in ("send", "auto", "reset", "status"):
        v = getattr(a, k)
        if v is not False and v is not None:
            once = (k, v if not isinstance(v, bool) else None)
    feed.run(a.corpus, a.dest, once)


def cmd_add_hostiles(a):
    c = Corpus.load(a.corpus)
    n = generate.add_hostiles(c, a.type, a.count, a.seed)
    print(f"injected {n} {a.type} hostile(s) into {c.path}")
    print(f"ground truth: {c.counts()}")


def cmd_add_protesters(a):
    c = Corpus.load(a.corpus)
    n = generate.add_protesters(c, a.type, a.count, a.seed)
    print(f"injected a {a.type} group of {n} into {c.path}")
    print(f"ground truth: {c.counts()}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="7s-generator", description=__doc__, formatter_class=_Fmt,
        epilog="Run with no command (just `7s-generator`) to open an interactive shell.\n\n"
               "Typical flow:\n"
               "  1. generate       build a normal-activity corpus\n"
               "  2. add-hostiles   layer a threat cell on top       (optional)\n"
               "  3. add-protesters layer benign noise on top        (optional)\n"
               "  4. feed           drip the corpus into a folder     (optional)\n\n"
               "Run `7s-generator <command> -h` for a command's options and an example.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser(
        "generate", help="normal-activity corpus", formatter_class=_Fmt,
        description="Generate a corpus of normal civilian reports around an area of "
                    "interest over a time window. Deterministic: same --seed => same corpus.",
        epilog="Example:\n"
               "  7s-generator generate \\\n"
               "    --aoi 60.345,17.422 --radius 3 --area airport \\\n"
               "    --from 2026-06-15 --days 14 \\\n"
               "    --callsigns AQ,BQ,CQ,DQ --name \"Tierp flygfalt\" \\\n"
               "    --out ./corpus_tierp")
    g.add_argument("--aoi", type=_aoi, required=True, metavar="LAT,LON",
                   help="area-of-interest centre, decimal degrees (e.g. 60.345,17.422)")
    g.add_argument("--radius", type=float, default=3.0, metavar="KM",
                   help="location scatter radius from the AOI, km (>0, typ. 1-20)")
    g.add_argument("--area", choices=sorted(AREAS), default="rural",
                   help="area type (sets vocabulary and base report frequency)")
    g.add_argument("--from", type=_date, required=True, metavar="YYYY-MM-DD", help="start date")
    g.add_argument("--to", type=_date, metavar="YYYY-MM-DD",
                   help="end date, inclusive (overrides --days if given)")
    g.add_argument("--days", type=int, default=14, metavar="N",
                   help="window length in days when --to omitted (>=1)")
    g.add_argument("--callsigns", type=_callsigns, default=["AQ", "BQ", "CQ", "DQ"],
                   metavar="AQ,BQ,…", help="platoon callsigns, comma-separated (one sector each, >=1)")
    g.add_argument("--name", default="objektet", help="AOI name, used in threat prose")
    g.add_argument("--reports", type=int, metavar="N",
                   help="override the auto report count (default: frequency x days x season)")
    g.add_argument("--images", action="store_true",
                   help="attach corroborating plate photos to plate reports (needs Pillow)")
    g.add_argument("--seed", type=int, default=2026, metavar="N",
                   help="RNG seed (same seed => same corpus)")
    g.add_argument("--out", required=True, metavar="DIR", help="output corpus directory")
    g.set_defaults(func=cmd_generate)

    h = sub.add_parser(
        "add-hostiles", help="inject a hostile cell", formatter_class=_Fmt,
        description="Layer a hostile cell onto an existing corpus, near the AOI, "
                    "time-biased, each hostile recurring 1-4x. Detectable only as a pattern.",
        epilog="Example:\n  7s-generator add-hostiles --corpus ./corpus_tierp --type recon")
    h.add_argument("--corpus", required=True, metavar="DIR", help="existing corpus directory")
    h.add_argument("--type", choices=sorted(HOSTILES), required=True, help="threat cell behaviour")
    h.add_argument("--count", type=int, metavar="N",
                   help="number of distinct hostiles (default: random 2-10)")
    h.add_argument("--seed", type=int, default=7, metavar="N", help="RNG seed")
    h.set_defaults(func=cmd_add_hostiles)

    r = sub.add_parser(
        "add-protesters", help="inject challenging civilians (noise)", formatter_class=_Fmt,
        description="Layer a benign but clustered group (gathering at one location on one "
                    "day) onto a corpus, to stress a detector's precision.",
        epilog="Example:\n  7s-generator add-protesters --corpus ./corpus_tierp --type miljoaktivister")
    r.add_argument("--corpus", required=True, metavar="DIR", help="existing corpus directory")
    r.add_argument("--type", choices=sorted(PROTESTERS), required=True, help="group kind")
    r.add_argument("--count", type=int, metavar="N",
                   help="group size (default: the profile's range)")
    r.add_argument("--seed", type=int, default=11, metavar="N", help="RNG seed")
    r.set_defaults(func=cmd_add_protesters)

    f = sub.add_parser(
        "feed", help="drip a corpus into a destination folder", formatter_class=_Fmt,
        description="Deliver a corpus's reports from the source folder into a destination "
                    "folder in chronological order, mimicking a central app trickling "
                    "messages out over time. Referenced image attachments are copied too, "
                    "so embeds resolve. Interactive REPL by default; the flags below are "
                    "one-shot for scripts/CI.",
        epilog="Examples:\n"
               "  7s-generator feed --corpus ./corpus_tierp --dest ./inbox            # REPL\n"
               "  7s-generator feed --corpus ./corpus_tierp --dest ./inbox --send 5   # one-shot\n"
               "  7s-generator feed --corpus ./corpus_tierp --dest ./inbox --auto 5   # ~5-min replay")
    f.add_argument("--corpus", required=True, metavar="DIR", help="source corpus directory")
    f.add_argument("--dest", required=True, metavar="DIR",
                   help="destination folder to drip reports into (any directory)")
    f.add_argument("--send", type=int, metavar="N", help="one-shot: deliver the next N and exit")
    f.add_argument("--auto", type=float, metavar="MINS", help="one-shot: replay over ~MINS and exit")
    f.add_argument("--reset", action="store_true", help="one-shot: clear delivered reports and exit")
    f.add_argument("--status", action="store_true", help="one-shot: print progress and exit")
    f.set_defaults(func=cmd_feed)
    return p


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in ("shell", "repl"):
        from . import shell
        shell.run()
        return
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
