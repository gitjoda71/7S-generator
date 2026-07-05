"""Generation logic — pure functions over the content tables.

`build_normal` creates a corpus of benign activity for an area; `add_hostiles` and
`add_protesters` inject a threat / noise layer into an existing corpus. All three
are seedable and deterministic."""
import random as _random
import uuid as _uuid
from datetime import datetime, timedelta

from . import geo
from .content import AREAS, SEASONS, HOSTILES, PROTESTERS, CARS, DOGS, COLOURS
from .corpus import Corpus
from .mgrs import latlon_to_mgrs
from .render import tnr_from, iso


def _uid(rng):
    return str(_uuid.UUID(int=rng.getrandbits(128), version=4))


def season_of(month):
    for name, s in SEASONS.items():
        if month in s["months"]:
            return name
    return "sommar"


def build_locations(lat, lon, radius, area, callsigns, rng, per=4):
    """`per` named locations per callsign, each in that callsign's bearing wedge."""
    places = AREAS[area]["places"][:]
    rng.shuffle(places)
    n = len(callsigns)
    width = 360 / n
    locs, pi = [], 0
    for i, cs in enumerate(callsigns):
        for _ in range(per):
            bearing = rng.uniform(i * width, (i + 1) * width)
            dist = radius * (rng.random() ** 0.5)
            plat, plon = geo.offset_point(lat, lon, bearing, dist)
            name = places[pi % len(places)]
            pi += 1
            locs.append({"callsign": cs, "sector": i, "name": name,
                         "lat": plat, "lon": plon, "mgrs": latlon_to_mgrs(plat, plon, sep=" ")})
    return locs


def _attachment_dir(rec):
    """Per-message attachment folder, matching the source app's shape:
    <signaltime>_<DDHHMM>-<sender>."""
    ts = datetime.fromisoformat(rec.get("signal_tidpunkt") or rec["tidpunkt"])
    sender = rec.get("sender") or rec["uuid"]
    return f"{ts:%Y%m%d%H%M%S}_{ts:%d%H%M}-{sender}"


def _civ_time(start, days, rng, day_band):
    lo, hi = day_band
    hour = min(hi, max(lo, int(rng.gauss((lo + hi) / 2, (hi - lo) / 5))))
    return start + timedelta(days=rng.randrange(days), hours=hour, minutes=rng.randrange(60))


def _threat_time(start, days, rng, night_bias):
    if rng.random() < night_bias:
        hour = rng.choice([22, 22, 23, 0, 1, 4, 5, 5, 6, 21])
    else:
        hour = rng.randrange(6, 22)
    return start + timedelta(days=rng.randrange(days), hours=hour, minutes=rng.randrange(60))


def _new_record(dt, loc, rng, platoon_uuid):
    if rng.random() < 0.9:  # Signal is the default channel
        sig = dt + timedelta(minutes=rng.randint(1, 3), seconds=rng.randint(0, 59))
        tnr, sigt, sender = tnr_from(sig), iso(sig), platoon_uuid[loc["callsign"]]
    else:
        tnr, sigt, sender = tnr_from(dt), None, None
    grid_only = rng.random() < 0.5
    return {
        "uuid": _uid(rng), "tnr": tnr, "tidpunkt": iso(dt), "signal_tidpunkt": sigt,
        "sender": sender, "callsign": loc["callsign"], "stund": tnr_from(dt),
        "stalle": loc["mgrs"] if grid_only else f'{loc["mgrs"]}, {loc["name"]}',
        "plats": loc["mgrs"] if grid_only else loc["name"],
        "lat": None if grid_only else loc["lat"], "lon": None if grid_only else loc["lon"],
        "sector": loc["sector"], "name": loc["name"], "plate": None,
    }


# --- normal activity --------------------------------------------------------
def build_normal(out, lat, lon, radius, area, start, days, callsigns, seed,
                 reports=None, obj_name="objektet", images=False):
    rng = _random.Random(seed)
    prof = AREAS[area]
    season = season_of(start.month)
    smeta = SEASONS[season]
    locs = build_locations(lat, lon, radius, area, callsigns, rng)
    platoon_uuid = {cs: _uid(rng) for cs in callsigns}

    if reports is None:
        reports = round(prof["reports_per_day"] * days * smeta["civ_mult"])

    corpus = Corpus.create(out, {
        "aoi": [lat, lon], "aoi_name": obj_name, "radius_km": radius, "area": area,
        "from": start.strftime("%Y-%m-%d"), "days": days, "callsigns": callsigns,
        "season": season, "seed": seed, "locations": locs, "platoon_uuid": platoon_uuid,
    })
    render_plate = None
    if images:
        from .images import render_plate  # lazy: only needs Pillow with --images

    for _ in range(reports):
        loc = rng.choice(locs)
        rec = _new_record(_civ_time(start, days, rng, smeta["day"]), loc, rng, platoon_uuid)
        template = rng.choice(prof["civil"])
        if prof["vehicles"] and "{car}" in template and rng.random() < 0.5:
            rec["plate"] = _plate(rng)
            car = rng.choice(CARS) + f", reg {rec['plate']}"
        else:
            car = rng.choice(CARS)
        rec["handelse"] = template.format(car=car, dog=rng.choice(DOGS), colour=rng.choice(COLOURS))
        if rng.random() < 0.12:  # occasional benign appearance (season-appropriate)
            rec["symbol"] = f"{rng.choice(smeta['upper'])}, {rng.choice(smeta['accessory'])}"
        if images and rec["plate"]:  # a corroborating photo of the typed plate
            folder = _attachment_dir(rec)
            img_name = f"plate_{rec['uuid'][:8]}.jpg"
            d = corpus.path / folder
            d.mkdir(parents=True, exist_ok=True)
            render_plate(rec["plate"], d / img_name)
            rec["image"] = f"{folder}/{img_name}"
        corpus.add(rec, "civil")

    corpus.save()
    return corpus


_LETTERS = "ABCDEFGHJKLMNPRSTUWXYZ"
def _plate(rng):
    a = "".join(rng.choice(_LETTERS) for _ in range(3))
    if rng.random() < 0.5:
        return a + "".join(rng.choice("0123456789") for _ in range(3))
    return a + "".join(rng.choice("0123456789") for _ in range(2)) + rng.choice(_LETTERS)


# --- hostiles ---------------------------------------------------------------
def add_hostiles(corpus, htype, count, seed):
    rng = _random.Random(seed)
    prof = HOSTILES[htype]
    m = corpus.meta
    lat, lon = m["aoi"]
    start = datetime.strptime(m["from"], "%Y-%m-%d")
    days, obj = m["days"], m.get("aoi_name", "objektet")
    locs = m["locations"]
    platoon_uuid = m["platoon_uuid"]

    # near-AOI weighting
    ranked = sorted(locs, key=lambda l: geo.dist_km(lat, lon, l["lat"], l["lon"]))
    near = ranked[: max(1, len(ranked) * 3 // 5)]

    if count is None:
        count = rng.randint(2, 10)
    marks = prof["marks"][:]
    rng.shuffle(marks)

    for i in range(count):
        member = f"H{i + 1}"
        mark = marks[i % len(marks)]
        for _ in range(rng.randint(*prof["appearances"])):
            loc = rng.choice(near if rng.random() < prof["near_bias"] else locs)
            rec = _new_record(_threat_time(start, days, rng, prof["night_bias"]), loc, rng, platoon_uuid)
            rec["handelse"] = rng.choice(prof["behaviour"]).format(obj=obj)
            rec["symbol"] = mark
            corpus.add(rec, "hostile", subtype=htype, member=member)

    corpus.save()
    return count


# --- protesters (challenging civilians) -------------------------------------
def add_protesters(corpus, ptype, count, seed):
    rng = _random.Random(seed)
    prof = PROTESTERS[ptype]
    m = corpus.meta
    start = datetime.strptime(m["from"], "%Y-%m-%d")
    obj = m.get("aoi_name", "objektet")
    locs = m["locations"]
    platoon_uuid = m["platoon_uuid"]

    size = count if count is not None else rng.randint(*prof["size"])
    loc = rng.choice(locs)                       # a protest gathers at one place…
    day0 = rng.randrange(m["days"])
    hour0 = rng.randrange(9, 18)                 # …in daylight
    behaviour = rng.choice(prof["behaviour"]).format(obj=obj)

    for _ in range(size):
        dt = start + timedelta(days=day0, hours=hour0, minutes=rng.randrange(0, 90))
        rec = _new_record(dt, loc, rng, platoon_uuid)
        rec["handelse"] = behaviour
        rec["symbol"] = rng.choice(prof["marks"])
        corpus.add(rec, "protester", subtype=ptype, member="protest-1")

    corpus.save()
    return size
