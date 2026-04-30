"""Redfin gis-csv search by polygon. Reuses session warmup from fetch_redfin.

See the NOTICE at the top of fetch_redfin.py before running. Same caveats
apply: this hits an undocumented endpoint, you own the decision to use it,
keep request rates moderate.
"""
from __future__ import annotations

import json
import random
import time
from typing import Optional

import requests

from config import REDFIN_RETRIES
from fetch_redfin import (
    GIS_CSV_URL,
    NAVIGATE_HEADERS,
    API_HEADERS,
    HOMEPAGE_URL,
    parse_gis_csv,
)
from geometry import ring_to_polystring, simplify_ring


def make_session() -> requests.Session:
    """Same warmup as fetch_redfin.make_session, kept local to avoid import cycle."""
    s = requests.Session()
    s.headers.update({k: v for k, v in API_HEADERS.items() if k != "Accept"})
    try:
        s.get(HOMEPAGE_URL, headers=NAVIGATE_HEADERS, timeout=15)
        time.sleep(0.6)
    except Exception as e:
        print(f"[redfin-poly] warmup failed: {e} (continuing)")
    return s


def _request_with_retry(session: requests.Session, params: dict,
                        timeout: int = 30) -> Optional[requests.Response]:
    last_status = None
    for attempt in range(1, REDFIN_RETRIES + 1):
        try:
            r = session.get(GIS_CSV_URL, params=params, headers=API_HEADERS, timeout=timeout)
            last_status = r.status_code
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429) or r.status_code >= 500:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"      [redfin-poly] HTTP {r.status_code} (try {attempt}/{REDFIN_RETRIES}) -> sleep {wait:.1f}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"      [redfin-poly] {type(e).__name__}: {e} (try {attempt}/{REDFIN_RETRIES}) -> sleep {wait:.1f}s")
            time.sleep(wait)
    print(f"      [redfin-poly] giving up (last status={last_status})")
    return None


def fetch_listings_in_polygon(
    session: requests.Session,
    rings: list[list[list[float]]],
    market: str = "dallas",
    target_vertices: int = 40,
) -> list[dict]:
    """Query Redfin gis-csv with poly= parameter built from outer ring."""
    if not rings:
        return []
    outer = simplify_ring(rings[0], target=target_vertices)
    poly_str = ring_to_polystring(outer)

    params = {
        "al": "1",
        "market": market,
        "num_homes": "350",
        "ord": "redfin-recommended-asc",
        "poly": poly_str,
        "sf": "1,2,3,5,6,7",
        "status": "9",
        "uipt": "1,3",
        "v": "8",
    }
    r = _request_with_retry(session, params)
    if r is None:
        return []
    return parse_gis_csv(r.text)
