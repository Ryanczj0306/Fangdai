"""Pipeline v4 -- bbox + TSAHC polygons, NO year filter, ALL property types.

Output: filtered_listings_v4.csv -- everything actively for sale inside a
TSAHC-Targeted polygon within the commute bbox, sorted by average distance
to Addison + Lewisville (closer = higher).
"""
from __future__ import annotations

import csv
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from config import (
    COUNTY_FIPS, OUTPUT_DIR, REDFIN_SLEEP, DATA_DIR,
    CORRIDOR_LAT_MIN, CORRIDOR_LAT_MAX, CORRIDOR_LNG_MIN, CORRIDOR_LNG_MAX,
)
from geometry import point_in_polygon
from redfin_poly import make_session, _request_with_retry
from fetch_redfin import GIS_CSV_URL, parse_gis_csv

ADDISON     = (32.96, -96.83)
LEWISVILLE  = (33.04, -96.99)
OUT_CSV     = OUTPUT_DIR / "filtered_listings_v4.csv"
GEOJSON     = DATA_DIR / "tsahc_official_targeted.geojson"
TRACT_CITY  = json.loads((DATA_DIR / "tract_city.json").read_text())
PREFIX_TO_COUNTY = {v: k for k, v in COUNTY_FIPS.items()}


def haversine_mi(lat1, lng1, lat2, lng2):
    R = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def ring_centroid(ring):
    n = len(ring)
    return sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n


def pretty_tract(geoid):
    raw = geoid[5:]
    return f"{int(raw[:4])}.{raw[4:]}"


def fetch_listings_in_polygon_all_types(session, rings):
    """Like redfin_poly.fetch_listings_in_polygon but with ALL property types
    and no year filter."""
    if not rings:
        return []
    from geometry import simplify_ring, ring_to_polystring
    outer = simplify_ring(rings[0], target=40)
    poly_str = ring_to_polystring(outer)
    params = {
        "al": "1",
        "market": "dallas",
        "num_homes": "350",
        "ord": "redfin-recommended-asc",
        "poly": poly_str,
        "sf": "1,2,3,5,6,7",
        "status": "9",                       # active for sale
        "uipt": "1,2,3,4,5,6,7,8",          # ALL property types
        "v": "8",
    }
    r = _request_with_retry(session, params)
    if r is None:
        return []
    return parse_gis_csv(r.text)


def main():
    print("=" * 76)
    print("CORRIDOR PIPELINE v4  --  no year/type filter, just TSAHC + bbox + active")
    print(f"Bbox: lat [{CORRIDOR_LAT_MIN}, {CORRIDOR_LAT_MAX}]  "
          f"lng [{CORRIDOR_LNG_MIN}, {CORRIDOR_LNG_MAX}]")
    print("=" * 76)

    # 1. Load + filter polygons
    gj = json.loads(GEOJSON.read_text())
    feats = gj["features"]
    prefixes = tuple(COUNTY_FIPS.values())
    in_4cty = [f for f in feats if f["properties"]["FIPS"].startswith(prefixes)]
    in_corr = []
    for f in in_4cty:
        rings = f["geometry"]["coordinates"]
        if not rings:
            continue
        c_lng, c_lat = ring_centroid(rings[0])
        if (CORRIDOR_LAT_MIN <= c_lat <= CORRIDOR_LAT_MAX
                and CORRIDOR_LNG_MIN <= c_lng <= CORRIDOR_LNG_MAX):
            in_corr.append(f)
    print(f"\n[1/3] Loaded {len(feats)} TSAHC polygons -> {len(in_4cty)} in 4 counties -> {len(in_corr)} in corridor")

    # 2. Redfin polygon search per tract -- no year/type filter
    print(f"\n[2/3] Redfin polygon search ({len(in_corr)} tracts; ~{len(in_corr) * REDFIN_SLEEP:.0f}s)")
    session = make_session()
    all_listings = []
    seen_urls = set()
    per_tract_counts = {}
    for i, feat in enumerate(sorted(in_corr, key=lambda x: x["properties"]["FIPS"]), 1):
        fips = feat["properties"]["FIPS"]
        county = PREFIX_TO_COUNTY.get(fips[:5], "?")
        rings = feat["geometry"]["coordinates"]
        try:
            raw = fetch_listings_in_polygon_all_types(session, rings)
        except Exception as e:
            print(f"  [{i:3d}/{len(in_corr)}] {fips}  ERROR {e}")
            raw = []
        verified = []
        for lst in raw:
            lat, lng = lst.get("latitude"), lst.get("longitude")
            if lat is None or lng is None:
                continue
            if not point_in_polygon(lat, lng, rings):
                continue
            lst["tract_geoid"] = fips
            lst["county_name"] = county
            lst["tract_city"] = TRACT_CITY.get(fips, "?")
            verified.append(lst)
        per_tract_counts[fips] = len(verified)
        if (i % 10 == 0) or (i == len(in_corr)) or len(verified) > 0:
            print(f"  [{i:3d}/{len(in_corr)}] {fips} ({county:7s})  active={len(verified):3d}")
        for lst in verified:
            url = lst.get("redfin_url") or ""
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_listings.append(lst)
        time.sleep(REDFIN_SLEEP)

    # 3. Compute derived columns
    by_tract = defaultdict(list)
    for l in all_listings:
        by_tract[l["tract_geoid"]].append(l)

    # tract_label for each tract: most-common city + zip + tract num
    tract_label_map = {}
    for geoid, items in by_tract.items():
        cz = Counter(l.get("zip", "") for l in items if l.get("zip"))
        cc = Counter(l.get("city", "") for l in items if l.get("city"))
        zipc = cz.most_common(1)[0][0] if cz else "?"
        city = cc.most_common(1)[0][0] if cc else (TRACT_CITY.get(geoid, "?"))
        tract_label_map[geoid] = f"{city} {zipc} (tract {pretty_tract(geoid)})"

    for l in all_listings:
        try:
            lat = float(l["latitude"]); lng = float(l["longitude"])
            l["dist_to_addison_mi"]    = round(haversine_mi(lat, lng, *ADDISON), 2)
            l["dist_to_lewisville_mi"] = round(haversine_mi(lat, lng, *LEWISVILLE), 2)
            l["avg_distance"]          = round(
                (l["dist_to_addison_mi"] + l["dist_to_lewisville_mi"]) / 2, 2)
        except (TypeError, ValueError):
            l["dist_to_addison_mi"] = ""
            l["dist_to_lewisville_mi"] = ""
            l["avg_distance"] = 99
        l["same_tract_count"] = len(by_tract[l["tract_geoid"]])
        l["tract_label"] = tract_label_map[l["tract_geoid"]]
        if l.get("latitude") is not None and l.get("longitude") is not None:
            l["google_maps_url"] = f"https://maps.google.com/?q={l['latitude']},{l['longitude']}"
        else:
            l["google_maps_url"] = ""

    # No sort (user explicitly asked for no sort)

    # 4. Write CSV (compact column set per user's request)
    fields = [
        "address", "city", "zip", "price", "beds", "baths", "sqft",
        "year_built", "lot_size", "property_type", "hoa_month",
        "days_on_market", "tract_geoid", "county_name",
        "dist_to_addison_mi", "dist_to_lewisville_mi",
        "latitude", "longitude", "redfin_url",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_listings)
    print(f"\n[3/3] Written {OUT_CSV} ({len(all_listings)} rows)")

    # 5. Stats
    print("\n" + "=" * 76)
    print("STATS")
    print("=" * 76)
    print(f"Total active listings: {len(all_listings)}")

    print("\nBy property_type:")
    for pt, n in Counter(l.get("property_type") or "?" for l in all_listings).most_common():
        print(f"  {pt:30s}: {n}")

    print("\nBy city (Redfin's CITY field):")
    for city, n in Counter(l.get("city") or "?" for l in all_listings).most_common():
        print(f"  {city:25s}: {n}")

    print(f"\nTracts with active listings: {sum(1 for v in per_tract_counts.values() if v > 0)} / {len(in_corr)}")
    print("\nBy tract (sorted by listing count desc):")
    sorted_tracts = sorted(by_tract.items(), key=lambda x: -len(x[1]))
    for geoid, items in sorted_tracts:
        prices = sorted([int(l["price"]) for l in items if l.get("price")])
        avg_dist = round(sum(l["avg_distance"] for l in items) / len(items), 1)
        if prices:
            pmin, pmax = prices[0], prices[-1]
            print(f"  {geoid}  {tract_label_map[geoid][:40]:40s}  {len(items):>3d}  "
                  f"${pmin:>7,}-${pmax:>7,}  avg_dist={avg_dist}mi")
        else:
            print(f"  {geoid}  {tract_label_map[geoid][:40]:40s}  {len(items):>3d}  (no prices)")

    if all_listings:
        ppsfs = sorted(int(l["price_per_sqft"]) for l in all_listings if l.get("price_per_sqft"))
        med = ppsfs[len(ppsfs)//2] if ppsfs else 0
        print(f"\nPrice range: ${all_listings[0]['price']:,} - ${all_listings[-1]['price']:,}")
        print(f"$/sqft median (where available): ${med}")


if __name__ == "__main__":
    main()
