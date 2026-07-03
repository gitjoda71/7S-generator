"""Placing named locations around an area of interest (AOI).

Locations are scattered uniformly within a radius of the AOI and assigned to a
sector/callsign by bearing, so each platoon "owns" a wedge of the area."""
import math

_KM_PER_DEG_LAT = 110.574


def _km_offset(lat, dnorth_km, deast_km):
    dlat = dnorth_km / _KM_PER_DEG_LAT
    dlon = deast_km / (111.320 * math.cos(math.radians(lat)))
    return dlat, dlon


def random_point(lat, lon, radius_km, rng):
    """A uniform random point within `radius_km` of (lat, lon).
    Returns (lat, lon, bearing_deg) — bearing measured clockwise from north."""
    r = radius_km * math.sqrt(rng.random())          # uniform over the disk area
    theta = rng.uniform(0, 2 * math.pi)              # 0 = east, math convention
    dn = r * math.sin(theta)                          # north component (km)
    de = r * math.cos(theta)                          # east component (km)
    dlat, dlon = _km_offset(lat, dn, de)
    bearing = (90 - math.degrees(theta)) % 360        # clockwise from north
    return round(lat + dlat, 5), round(lon + dlon, 5), bearing


def sector_index(bearing_deg, n_sectors):
    """Map a bearing (deg from north) to one of n equal wedges, starting at north."""
    width = 360 / n_sectors
    return int((bearing_deg % 360) // width)


def offset_point(lat, lon, bearing_deg, dist_km):
    """A point `dist_km` from (lat, lon) along `bearing_deg` (clockwise from north)."""
    br = math.radians(bearing_deg)
    dlat, dlon = _km_offset(lat, dist_km * math.cos(br), dist_km * math.sin(br))
    return round(lat + dlat, 5), round(lon + dlon, 5)


def dist_km(lat1, lon1, lat2, lon2):
    dn = (lat2 - lat1) * _KM_PER_DEG_LAT
    de = (lon2 - lon1) * 111.320 * math.cos(math.radians(lat1))
    return math.hypot(dn, de)
