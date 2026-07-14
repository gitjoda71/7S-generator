"""Coordinate parsing — several input formats -> WGS84 lat/lon. Zero dependencies.

`parse_point(text)` accepts, in order of detection:

  * MGRS            "33VXF6665179308", "33VXF 66651 79308", "33V XF 66651 79308"
                    (any even digit count 0–10; returns the cell centre)
  * DMS/DM          "59°15'41\"N 17°42'49\"E", "N59 15.69 E17 42.82", "59 15 41 N, 17 42 49 O"
                    (Swedish O/Ö accepted for east)
  * SWEREF 99 TM    "6577564, 674032"  (northing, easting — recognised by magnitude)
  * decimal degrees "59.2615, 17.7135" (comma, space, or both as separator)

The inverse UTM math round-trips against the forward in mgrs.py to within ~1 m.
Also hosts the polygon helpers used when a corpus is generated inside a drawn
area instead of a radius."""
import math
import re

from .mgrs import _A, _E2, _EP2, _K0, _BANDS, _COL_ORIGIN, _ROW_ORIGIN, _latlon_to_utm

_E1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))


# --- inverse UTM (Snyder) ----------------------------------------------------
def _utm_to_latlon(zone, easting, northing, northern=True):
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    m = y / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))
    phi1 = (mu
            + (3 * _E1 / 2 - 27 * _E1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * _E1 ** 2 / 16 - 55 * _E1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * _E1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * _E1 ** 4 / 512) * math.sin(8 * mu))
    sin1, cos1, tan1 = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    c1 = _EP2 * cos1 ** 2
    t1 = tan1 ** 2
    n1 = _A / math.sqrt(1 - _E2 * sin1 ** 2)
    r1 = _A * (1 - _E2) / (1 - _E2 * sin1 ** 2) ** 1.5
    d = x / (n1 * _K0)
    lat = phi1 - (n1 * tan1 / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * _EP2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * _EP2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    lon = lon0 + (d
                  - (1 + 2 * t1 + c1) * d ** 3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * _EP2 + 24 * t1 ** 2)
                  * d ** 5 / 120) / cos1
    return math.degrees(lat), math.degrees(lon)


# --- MGRS -> lat/lon ----------------------------------------------------------
def _letter_steps(origin, target, stop):
    """How many _advance-steps from `origin` to `target` (skipping I/O, wrapping
    after `stop`). Inverse of mgrs._advance."""
    cur, steps = ord(origin), 0
    while chr(cur) != target:
        cur += 1
        if cur == ord("I"):
            cur += 1
        if cur == ord("O"):
            cur += 1
        if cur > ord(stop):
            cur = ord("A")
        steps += 1
        if steps > 26:
            raise ValueError(f"ogiltig MGRS-bokstav {target!r}")
    return steps

_MGRS_RE = re.compile(r"(\d{1,2})([C-HJ-NP-X])([A-HJ-NP-Z])([A-HJ-NP-V])(\d*)")


def mgrs_to_latlon(text):
    """MGRS grid reference -> (lat, lon) at the centre of the referenced cell."""
    compact = re.sub(r"\s+", "", str(text).upper())
    m = _MGRS_RE.fullmatch(compact)
    if not m or len(m.group(5)) % 2:
        raise ValueError(f"ogiltig MGRS-referens: {text!r}")
    zone, band, col, row, digits = (int(m.group(1)), m.group(2), m.group(3),
                                    m.group(4), m.group(5))
    if not 1 <= zone <= 60:
        raise ValueError(f"ogiltig MGRS-zon: {zone}")
    s = zone % 6 or 6
    e100k = (_letter_steps(_COL_ORIGIN[s - 1], col, "Z") + 1) * 100000
    n_base = _letter_steps(_ROW_ORIGIN[s - 1], row, "V") * 100000

    half = len(digits) // 2
    scale = 10 ** (5 - half)
    e_in = int(digits[:half]) * scale if half else 0
    n_in = int(digits[half:]) * scale if half else 0
    easting = e100k + e_in + scale / 2 if half else e100k + 50000
    n_mod = n_base + n_in + (scale / 2 if half else 50000)

    # resolve the 2 000 000 m row-letter ambiguity from the latitude band:
    # pick the northing congruent to n_mod (mod 2 000 000) whose *cell* reaches
    # the band's southern edge. n_mod is the cell CENTRE, so allow half a cell
    # of slack (50 km for a grid-only ref, less for finer digits) plus a little
    # for the flat-earth band_min approximation — otherwise a coarse cell just
    # north of a band floor is wrongly bumped a full 2 000 000 m (~18°) north.
    band_lat = -80 + _BANDS.index(band) * 8
    lon0 = (zone - 1) * 6 - 180 + 3
    band_min = _latlon_to_utm(band_lat, lon0)[2]
    cell_half = 50000 if not half else scale / 2
    northern = _BANDS.index(band) >= _BANDS.index("N")
    northing = n_mod
    while northing < band_min - cell_half - 5000:
        northing += 2000000
    lat, lon = _utm_to_latlon(zone, easting, northing, northern=northern)
    return round(lat, 6), round(lon, 6)


# --- SWEREF 99 TM -> lat/lon ---------------------------------------------------
def sweref99tm_to_latlon(northing, easting):
    """SWEREF 99 TM (EPSG:3006): Transverse Mercator with central meridian 15°E,
    k0 0.9996, false easting 500 000 — projection-wise identical to UTM zone 33
    (GRS80 vs WGS84 differs by <1 mm)."""
    return _utm_to_latlon(33, easting, northing, northern=True)


# --- DMS / DM -------------------------------------------------------------------
_DMS_COMP = re.compile(
    r"([NS]|[EW]|O)\s*((?:\d+(?:\.\d+)?\s*){1,3})|((?:\d+(?:\.\d+)?\s*){1,3})([NS]|[EW]|O)")


def _parse_dms(text):
    s = str(text).upper().replace("Ö", "O")
    for ch in "°º'’′\"”″":
        s = s.replace(ch, " ")
    s = re.sub(r"(\d),(\d)", r"\1.\2", s).replace(",", " ")   # decimal comma vs separator
    comps = []
    for m in _DMS_COMP.finditer(s):
        letter = m.group(1) or m.group(4)
        nums = (m.group(2) or m.group(3)).split()
        val = float(nums[0])
        if len(nums) > 1:
            val += float(nums[1]) / 60
        if len(nums) > 2:
            val += float(nums[2]) / 3600
        comps.append((letter, val))
    if len(comps) != 2:
        raise ValueError(f"kunde inte tolka DMS-koordinat: {text!r}")
    lat = lon = None
    for letter, val in comps:
        if letter in "NS":
            lat = val if letter == "N" else -val
        else:                                      # E, W, or Swedish O (öst)
            lon = val if letter in "EO" else -val
    if lat is None or lon is None:
        raise ValueError(f"DMS-koordinaten saknar lat- eller lon-del: {text!r}")
    return lat, lon


# --- the umbrella parser ----------------------------------------------------------
def _check_range(lat, lon, original):
    if not -90 <= lat <= 90:
        raise ValueError(f"LAT måste vara mellan -90 och 90, fick {lat} (glömt decimalpunkt?)")
    if not -180 <= lon <= 180:
        raise ValueError(f"LON måste vara mellan -180 och 180, fick {lon}")
    return lat, lon


def parse_point(text):
    """Parse a point in any supported format. Returns (lat, lon, kind) where
    kind is one of latlon / mgrs / dms / sweref99tm. Raises ValueError with a
    Swedish message on anything unparseable."""
    t = str(text).strip()
    if not t:
        raise ValueError("tom koordinat")

    compact = re.sub(r"\s+", "", t.upper())
    if _MGRS_RE.fullmatch(compact):
        lat, lon = mgrs_to_latlon(compact)
        return (*_check_range(lat, lon, t), "mgrs")

    if re.search(r"[°º'′\"″]|[NSEW]|\bO\b|Ö", t, re.I) and re.search(r"\d", t):
        lat, lon = _parse_dms(t)
        return (*_check_range(lat, lon, t), "dms")

    parts = [p for p in re.split(r"[,;\s]+", t) if p]
    if len(parts) != 2:
        raise ValueError(f"förväntade LAT,LON (två tal) eller MGRS/DMS/SWEREF, fick {t!r}")
    try:
        a, b = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"LAT och LON måste vara tal, fick {t!r}")
    if 5900000 <= a <= 7800000 and 100000 <= b <= 1100000:   # N, E i Sverige-spannet
        lat, lon = sweref99tm_to_latlon(a, b)
        return (*_check_range(lat, lon, t), "sweref99tm")
    return (*_check_range(a, b, t), "latlon")


# --- polygon helpers ---------------------------------------------------------------
def point_in_polygon(lat, lon, polygon):
    """Ray casting: is (lat, lon) inside the polygon [[lat, lon], …]?"""
    inside = False
    n = len(polygon)
    for i in range(n):
        y1, x1 = polygon[i]
        y2, x2 = polygon[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) / (y2 - y1) * (x2 - x1)
            if lon < x_cross:
                inside = not inside
    return inside


def polygon_bounds(polygon):
    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]
    return min(lats), max(lats), min(lons), max(lons)
