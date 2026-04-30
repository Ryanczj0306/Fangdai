"""TSAHC's authoritative Targeted Tract list (sourced from their own JS calculator).

The eligibility tool at https://www.tsahc.org/eligibility loads
/public/data/calculator/fips.json and matches purely client-side. That JSON
is the ground truth for which tracts are TSAHC-Targeted.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from config import DATA_DIR

TSAHC_FIPS_JSON_URL = "https://www.tsahc.org/public/data/calculator/fips.json"
CACHE = DATA_DIR / "tsahc_fips_official.json"


def fetch_official(force_refresh: bool = False) -> list[dict]:
    if CACHE.exists() and not force_refresh:
        data = json.loads(CACHE.read_text())
        print(f"[tsahc] cache hit -> {len(data)} entries")
        return data
    print(f"[tsahc] cache miss -> fetching {TSAHC_FIPS_JSON_URL}")
    r = requests.get(TSAHC_FIPS_JSON_URL, timeout=20,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()
    CACHE.write_text(json.dumps(data, indent=2))
    print(f"[tsahc] saved {len(data)} entries -> {CACHE.name}")
    return data


def targeted_set(force_refresh: bool = False) -> set[str]:
    """Return set of 11-digit FIPS strings designated as TSAHC Targeted."""
    data = fetch_official(force_refresh)
    return {str(t["fips"]).zfill(11) for t in data
            if t.get("targeted_area") == "Y"}


def all_known_set(force_refresh: bool = False) -> set[str]:
    data = fetch_official(force_refresh)
    return {str(t["fips"]).zfill(11) for t in data}


if __name__ == "__main__":
    data = fetch_official(force_refresh=True)
    targeted = targeted_set()
    print(f"\nTotal TX tracts in TSAHC list: {len(data)}")
    print(f"Designated Targeted (Y): {len(targeted)}")
    by_county = {}
    for f in targeted:
        by_county.setdefault(f[:5], 0)
        by_county[f[:5]] += 1
    name = {"48085":"Collin","48113":"Dallas","48121":"Denton","48439":"Tarrant"}
    print("\nTargeted in our 4 commute counties:")
    for cf in ("48085","48113","48121","48439"):
        print(f"  {name[cf]:8s} ({cf}): {by_county.get(cf, 0)}")
