"""TIGER 2020 tract geometry: centroids + polygon rings, point-in-polygon test."""
from __future__ import annotations

import json
from typing import Iterable

import requests

from config import DATA_DIR

# Census 2020 boundaries (matches FFIEC 2023 / ACS 2023 reporting)
TIGER_2020_TRACTS_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/tigerWMS_Census2020/MapServer/6/query"
)

CACHE_GEOMETRY = DATA_DIR / "tract_geometry_2020.json"


def _chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def fetch_geometry(geoids: list[str], with_polygons: bool = True) -> dict[str, dict]:
    """Returns {GEOID: {lat, lng, rings (if with_polygons)}}"""
    out: dict[str, dict] = {}
    fields = "GEOID,INTPTLAT,INTPTLON"
    for chunk in _chunks(sorted(set(geoids)), 50):
        where = "GEOID IN (" + ",".join(f"'{g}'" for g in chunk) + ")"
        r = requests.post(TIGER_2020_TRACTS_URL, data={
            "where": where,
            "outFields": fields,
            "returnGeometry": "true" if with_polygons else "false",
            "outSR": "4326",
            "f": "json",
        }, timeout=60)
        r.raise_for_status()
        data = r.json()
        for feat in data.get("features", []):
            attrs = feat["attributes"]
            geoid = attrs["GEOID"]
            entry: dict = {
                "lat": float(attrs["INTPTLAT"]),
                "lng": float(attrs["INTPTLON"]),
            }
            if with_polygons:
                entry["rings"] = feat.get("geometry", {}).get("rings", [])
            out[geoid] = entry
    return out


def cache_geometry_for_eligible(eligible_geoids: list[str], force_refresh: bool = False) -> dict[str, dict]:
    if CACHE_GEOMETRY.exists() and not force_refresh:
        data = json.loads(CACHE_GEOMETRY.read_text())
        already = set(data.keys())
        new = [g for g in eligible_geoids if g not in already]
        if not new:
            print(f"[geometry] cache hit -> {len(data)} tracts (all requested in cache)")
            return data
        print(f"[geometry] cache partial -> have {len(already)}, fetching {len(new)} more")
        more = fetch_geometry(new, with_polygons=True)
        data.update(more)
        CACHE_GEOMETRY.write_text(json.dumps(data, indent=2))
        return data

    print(f"[geometry] cache miss -> fetching {len(eligible_geoids)} tracts")
    data = fetch_geometry(eligible_geoids, with_polygons=True)
    CACHE_GEOMETRY.write_text(json.dumps(data, indent=2))
    print(f"[geometry] cached {len(data)} tracts")
    return data


def filter_to_corridor(
    geometry: dict[str, dict],
    lat_min: float, lat_max: float,
    lng_min: float, lng_max: float,
) -> dict[str, dict]:
    return {
        g: v for g, v in geometry.items()
        if lat_min <= v["lat"] <= lat_max and lng_min <= v["lng"] <= lng_max
    }


def simplify_ring(ring: list[list[float]], target: int = 40) -> list[list[float]]:
    """Reduce a ring to ~target vertices by uniform-step subsampling.

    Crude (not Douglas-Peucker) but fine for tract polygons in a fetch query.
    """
    n = len(ring)
    if n <= target:
        return ring
    step = max(1, n // target)
    out = ring[::step]
    # ensure ring closes
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def ring_to_polystring(ring: list[list[float]]) -> str:
    """Redfin poly format: 'lng1 lat1,lng2 lat2,...'  (space-separated within point)."""
    return ",".join(f"{p[0]:.6f} {p[1]:.6f}" for p in ring)


def point_in_ring(px: float, py: float, ring: list[list[float]]) -> bool:
    """Ray casting on a single ring of [lng, lat] vertices.  px=lng, py=lat."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lng: float, rings: list[list[list[float]]]) -> bool:
    """A polygon may have outer ring + holes; for tract polygons we just check outer."""
    if not rings:
        return False
    return point_in_ring(lng, lat, rings[0])
