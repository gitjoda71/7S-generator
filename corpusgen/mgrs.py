"""WGS84 lat/lon -> MGRS (forward), proj4 lettering (origin AJSAJS / AFAFAF, I/O
skipped, latitude bands C..X). Zero dependencies. Round-trips against the standard
inverse used by common MGRS libraries."""
import math

_A = 6378137.0
_F = 1 / 298.257223563
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_K0 = 0.9996
_COL_ORIGIN = "AJSAJS"
_ROW_ORIGIN = "AFAFAF"
_BANDS = "CDEFGHJKLMNPQRSTUVWX"  # 8-degree bands, -80..84 (I, O skipped)


def _latlon_to_utm(lat, lon):
    latr, lonr = math.radians(lat), math.radians(lon)
    zone = int((lon + 180) / 6) + 1
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    n = _A / math.sqrt(1 - _E2 * math.sin(latr) ** 2)
    t = math.tan(latr) ** 2
    c = _EP2 * math.cos(latr) ** 2
    a = (lonr - lon0) * math.cos(latr)
    m = _A * (
        (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256) * latr
        - (3 * _E2 / 8 + 3 * _E2 ** 2 / 32 + 45 * _E2 ** 3 / 1024) * math.sin(2 * latr)
        + (15 * _E2 ** 2 / 256 + 45 * _E2 ** 3 / 1024) * math.sin(4 * latr)
        - (35 * _E2 ** 3 / 3072) * math.sin(6 * latr)
    )
    easting = _K0 * n * (a + (1 - t + c) * a ** 3 / 6
                         + (5 - 18 * t + t ** 2 + 72 * c - 58 * _EP2) * a ** 5 / 120) + 500000.0
    northing = _K0 * (m + n * math.tan(latr) * (a ** 2 / 2
                      + (5 - t + 9 * c + 4 * c ** 2) * a ** 4 / 24
                      + (61 - 58 * t + t ** 2 + 600 * c - 330 * _EP2) * a ** 6 / 720))
    if lat < 0:
        northing += 10000000.0
    return zone, easting, northing


def _advance(origin, steps, stop):
    cur = ord(origin)
    for _ in range(steps):
        cur += 1
        if cur == ord("I"):
            cur += 1
        if cur == ord("O"):
            cur += 1
        if cur > ord(stop):
            cur = ord("A")
    return chr(cur)


def latlon_to_mgrs(lat, lon, digits=5, sep=""):
    """MGRS string. `sep=" "` renders the grid-reference spaced (e.g.
    "33VXF 66651 79308"); the default runs it together ("33VXF6665179308")."""
    zone, easting, northing = _latlon_to_utm(lat, lon)
    s = zone % 6 or 6
    band = _BANDS[min(int((lat + 80) // 8), len(_BANDS) - 1)]
    col = _advance(_COL_ORIGIN[s - 1], int(easting // 100000) - 1, "Z")
    row = _advance(_ROW_ORIGIN[s - 1], int((northing % 2000000) // 100000), "V")
    scale = 10 ** (5 - digits)
    e = int((easting % 100000) / scale)
    n = int((northing % 100000) / scale)
    return f"{zone}{band}{col}{row}{sep}{e:0{digits}d}{sep}{n:0{digits}d}"
