"""7S-generator CLI — build a synthetic 7S report corpus and layer threats/noise.

  generate        normal-activity corpus for an area of interest
  add-hostiles    inject a recon/sabotage/infiltration/terrorism cell
  add-protesters  inject a demonstrators/environmentalists/peace group (noise)
"""
import argparse
import sys
from datetime import datetime

from .content import AREAS, HOSTILES, PROTESTERS
from .corpus import Corpus
from . import generate


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
        reports=a.reports, obj_name=a.name,
    )
    print(f"[{a.area}] wrote {len(c.ground_truth)} reports to {c.path} "
          f"({days} days, season {c.meta['season']}, {len(c.meta['locations'])} locations)")
    print(f"ground truth: {c.counts()}")


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
    p = argparse.ArgumentParser(prog="7s-generator", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="normal-activity corpus")
    g.add_argument("--aoi", type=_aoi, required=True, metavar="LAT,LON", help="area of interest centre")
    g.add_argument("--radius", type=float, default=3.0, metavar="KM", help="location radius from the AOI")
    g.add_argument("--area", choices=sorted(AREAS), default="rural", help="area type")
    g.add_argument("--from", type=_date, required=True, metavar="YYYY-MM-DD", help="start date")
    g.add_argument("--to", type=_date, metavar="YYYY-MM-DD", help="end date (inclusive)")
    g.add_argument("--days", type=int, default=14, help="number of days (if --to omitted)")
    g.add_argument("--callsigns", type=_callsigns, default=["AQ", "BQ", "CQ", "DQ"],
                   metavar="AQ,BQ,…", help="platoon callsigns (one sector each)")
    g.add_argument("--name", default="objektet", help="AOI name, used in threat prose")
    g.add_argument("--reports", type=int, help="override the auto report count")
    g.add_argument("--seed", type=int, default=2026)
    g.add_argument("--out", required=True, metavar="DIR", help="output corpus directory")
    g.set_defaults(func=cmd_generate)

    h = sub.add_parser("add-hostiles", help="inject a hostile cell")
    h.add_argument("--corpus", required=True, metavar="DIR")
    h.add_argument("--type", choices=sorted(HOSTILES), required=True)
    h.add_argument("--count", type=int, help="number of hostiles (default: random 2–10)")
    h.add_argument("--seed", type=int, default=7)
    h.set_defaults(func=cmd_add_hostiles)

    r = sub.add_parser("add-protesters", help="inject challenging civilians (noise)")
    r.add_argument("--corpus", required=True, metavar="DIR")
    r.add_argument("--type", choices=sorted(PROTESTERS), required=True)
    r.add_argument("--count", type=int, help="group size (default: profile range)")
    r.add_argument("--seed", type=int, default=11)
    r.set_defaults(func=cmd_add_protesters)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
