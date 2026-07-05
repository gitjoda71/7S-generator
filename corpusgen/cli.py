"""7S-generator — bygg en syntetisk 7S-rapportkorpus och lägg på hot/brus.

  generate        normalkorpus för ett område av intresse (AOI)
  add-hostiles    injicera en cell (spaning/sabotage/infiltration/terrorism)
  add-protesters  injicera en grupp (demonstranter/miljöaktivister/fredsaktivister)
  feed            mata ut en korpus till en målmapp över tid
"""
import argparse
import re
import sys
from datetime import datetime

from .content import AREAS, HOSTILES, PROTESTERS
from .corpus import Corpus
from . import generate


class _Fmt(argparse.ArgumentDefaultsHelpFormatter,
           argparse.RawDescriptionHelpFormatter):
    """Show defaults on every option *and* keep epilog/example text raw."""


class _AoiAction(argparse.Action):
    """Parse --aoi as LAT,LON into a (lat, lon) tuple, tolerantly: a comma, a space,
    or both may separate the two numbers, so `59.66,18.92`, `59.66, 18.92` (a space
    after the comma splits it into two shell tokens), and `59.66 18.92` all work."""
    def __call__(self, parser, namespace, values, option_string=None):
        text = " ".join(values)
        parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
        if len(parts) != 2:
            raise argparse.ArgumentError(self, f"förväntade LAT,LON (två tal), fick {text!r}")
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            raise argparse.ArgumentError(self, f"LAT och LON måste vara tal, fick {text!r}")
        # Range-check: a latitude > 90 (a common typo, e.g. 599.6 for 59.96)
        # silently produced arctic MGRS grids (band X) before this guard.
        if not -90 <= lat <= 90:
            raise argparse.ArgumentError(self, f"LAT måste vara mellan -90 och 90, fick {lat} (glömt decimalpunkt?)")
        if not -180 <= lon <= 180:
            raise argparse.ArgumentError(self, f"LON måste vara mellan -180 och 180, fick {lon}")
        setattr(namespace, self.dest, (lat, lon))


def _callsigns(s):
    cs = [c.strip().upper() for c in s.split(",") if c.strip()]
    if not cs:
        raise argparse.ArgumentTypeError("minst en anropssignal krävs")
    return cs


def _date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def cmd_generate(a):
    if a.to:
        days = (a.to - getattr(a, "from")).days + 1
    else:
        days = a.days
    if days <= 0:
        sys.exit("fel: tomt datumintervall")
    c = generate.build_normal(
        out=a.out, lat=a.aoi[0], lon=a.aoi[1], radius=a.radius, area=a.area,
        start=getattr(a, "from"), days=days, callsigns=a.callsigns, seed=a.seed,
        reports=a.reports, obj_name=a.name, images=a.images, obsidian=a.obsidian,
    )
    print(f"[{a.area}] skrev {len(c.ground_truth)} rapporter till {c.path} "
          f"({days} dagar, årstid {c.meta['season']}, {len(c.meta['locations'])} platser)")
    if a.images:
        n = sum(1 for r in c.ground_truth if r.get("plate"))
        print(f"renderade skyltfoton för {n} skyltrapport(er)")
    print(f"facit: {c.counts()}")


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
    print(f"injicerade {n} {a.type}-fiende(r) i {c.path}")
    print(f"facit: {c.counts()}")


def cmd_add_protesters(a):
    c = Corpus.load(a.corpus)
    n = generate.add_protesters(c, a.type, a.count, a.seed)
    print(f"injicerade en {a.type}-grupp på {n} i {c.path}")
    print(f"facit: {c.counts()}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="7s-generator", description=__doc__, formatter_class=_Fmt,
        epilog="Kör utan kommando (bara `7s-generator`) för att öppna ett interaktivt skal.\n\n"
               "Typiskt arbetsflöde:\n"
               "  1. generate       bygg en normalkorpus\n"
               "  2. add-hostiles   lägg på en hotcell             (valfritt)\n"
               "  3. add-protesters lägg på godartat brus          (valfritt)\n"
               "  4. feed           mata ut korpusen till en mapp  (valfritt)\n\n"
               "Kör `7s-generator <kommando> -h` för ett kommandos flaggor och ett exempel.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser(
        "generate", help="normalkorpus (normal aktivitet)", formatter_class=_Fmt,
        description="Generera en korpus av normala civila rapporter runt ett område av "
                    "intresse (AOI) över ett tidsfönster. Deterministiskt: samma --seed => "
                    "samma korpus.",
        epilog="Exempel:\n"
               "  7s-generator generate \\\n"
               "    --aoi 60.345,17.422 --radius 3 --area airport \\\n"
               "    --from 2026-06-15 --days 14 \\\n"
               "    --callsigns AQ,BQ,CQ,DQ --name \"Tierp flygfält\" \\\n"
               "    --out ./korpus_tierp")
    g.add_argument("--aoi", nargs="+", action=_AoiAction, required=True, metavar="LAT,LON",
                   help="områdets mittpunkt (AOI), decimalgrader, latitud först "
                        "(t.ex. 60.345,17.422; mellanslag efter kommatecknet går bra)")
    g.add_argument("--radius", type=float, default=3.0, metavar="KM",
                   help="spridningsradie för platser från AOI, km (>0, vanl. 1–20)")
    g.add_argument("--area", choices=sorted(AREAS), default="rural",
                   help="områdestyp (styr ordförråd och basfrekvens för rapporter)")
    g.add_argument("--from", type=_date, required=True, metavar="ÅÅÅÅ-MM-DD", help="startdatum")
    g.add_argument("--to", type=_date, metavar="ÅÅÅÅ-MM-DD",
                   help="slutdatum, inklusive (åsidosätter --days om angivet)")
    g.add_argument("--days", type=int, default=14, metavar="N",
                   help="fönsterlängd i dagar när --to utelämnas (>=1)")
    g.add_argument("--callsigns", type=_callsigns, default=["AQ", "BQ", "CQ", "DQ"],
                   metavar="AQ,BQ,…", help="plutonens anropssignaler, kommaseparerade (en sektor var, >=1)")
    g.add_argument("--name", default="objektet", help="AOI-namn, används i hottexten")
    g.add_argument("--reports", type=int, metavar="N",
                   help="åsidosätt automatiskt rapportantal (standard: frekvens × dagar × årstid)")
    g.add_argument("--images", action="store_true",
                   help="bifoga bekräftande skyltfoton till skyltrapporter (kräver Pillow)")
    g.add_argument("--obsidian", action="store_true",
                   help="Obsidian-kompatibel utdata: bildinbäddningar som `## Bilagor` + "
                        "`![[wikilänk]]` i per-meddelande-mappar, identiskt med källappen "
                        "(standard: portabel standard-Markdown `![](attachments/…)`). "
                        "Påverkar bara rapporter med foto (--images).")
    g.add_argument("--seed", type=int, default=2026, metavar="N",
                   help="slumpfrö (samma frö => samma korpus)")
    g.add_argument("--out", required=True, metavar="MAPP", help="utmatningskatalog för korpusen")
    g.set_defaults(func=cmd_generate)

    h = sub.add_parser(
        "add-hostiles", help="injicera en hotcell", formatter_class=_Fmt,
        description="Lägg på en hotcell på en befintlig korpus, nära AOI, tidsviktad, där "
                    "varje fiende återkommer 1–4×. Upptäckbar endast som ett mönster.",
        epilog="Exempel:\n  7s-generator add-hostiles --corpus ./korpus_tierp --type recon")
    h.add_argument("--corpus", required=True, metavar="MAPP", help="befintlig korpuskatalog")
    h.add_argument("--type", choices=sorted(HOSTILES), required=True, help="hotcellens beteende")
    h.add_argument("--count", type=int, metavar="N",
                   help="antal DISTINKTA fiender/personer (standard: slumpvis 2–10). Varje "
                        "fiende återkommer flera gånger (1–4× beroende på typ), så antalet "
                        "rapporter blir count × återkomster — alltså mer än count.")
    h.add_argument("--seed", type=int, default=7, metavar="N", help="slumpfrö")
    h.set_defaults(func=cmd_add_hostiles)

    r = sub.add_parser(
        "add-protesters", help="injicera utmanande civila (brus)", formatter_class=_Fmt,
        description="Lägg på en godartad men klustrad grupp (samlas på en plats under en dag) "
                    "på en korpus, för att pröva en detektors precision.",
        epilog="Exempel:\n  7s-generator add-protesters --corpus ./korpus_tierp --type miljöaktivister")
    r.add_argument("--corpus", required=True, metavar="MAPP", help="befintlig korpuskatalog")
    r.add_argument("--type", choices=sorted(PROTESTERS), required=True, help="grupptyp")
    r.add_argument("--count", type=int, metavar="N",
                   help="gruppstorlek = antal rapporter i klustret (standard: profilens "
                        "intervall). Här blir antalet protestrapporter exakt count — alla "
                        "samma grupp, en plats, en dag.")
    r.add_argument("--seed", type=int, default=11, metavar="N", help="slumpfrö")
    r.set_defaults(func=cmd_add_protesters)

    f = sub.add_parser(
        "feed", help="mata ut en korpus till en målmapp", formatter_class=_Fmt,
        description="Leverera en korpus rapporter från källmappen till en målmapp i "
                    "kronologisk ordning, som en central app som droppar ut meddelanden över "
                    "tid. Refererade bildbilagor kopieras också så att inbäddningar fungerar. "
                    "Interaktivt skal som standard; flaggorna nedan är engångsåtgärder för "
                    "skript/CI.",
        epilog="Exempel:\n"
               "  7s-generator feed --corpus ./korpus_tierp --dest ./inkorg            # skal\n"
               "  7s-generator feed --corpus ./korpus_tierp --dest ./inkorg --send 5   # engång\n"
               "  7s-generator feed --corpus ./korpus_tierp --dest ./inkorg --auto 5   # ~5-min uppspelning")
    f.add_argument("--corpus", required=True, metavar="MAPP", help="källkatalog för korpusen")
    f.add_argument("--dest", required=True, metavar="MAPP",
                   help="målmapp att droppa rapporter till (valfri katalog)")
    f.add_argument("--send", type=int, metavar="N", help="engång: leverera nästa N och avsluta")
    f.add_argument("--auto", type=float, metavar="MIN", help="engång: spela upp över ~MIN och avsluta")
    f.add_argument("--reset", action="store_true", help="engång: rensa levererade rapporter och avsluta")
    f.add_argument("--status", action="store_true", help="engång: skriv ut status och avsluta")
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
