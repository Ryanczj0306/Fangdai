"""Fetch active Redfin listings for a list of ZIP codes.

NOTICE — please read before running:
  This module talks to Redfin's `gis-csv` endpoint, which is undocumented and
  not part of any public API. Running it is YOUR responsibility, not the
  author's. By executing this code you agree that you have:
    - reviewed Redfin's Terms of Service and robots.txt
    - decided that personal/research use of this scraper is acceptable in your
      jurisdiction
    - configured a moderate request rate (defaults to REDFIN_SLEEP=1.5s
      between requests in config.py — do not lower without good reason)
  This code is provided as-is, for educational and personal-research use. It
  is not affiliated with or endorsed by Redfin.

Strategy (the autocomplete endpoint is CloudFront-blocked, so we go around it):
  1. Warm up a Session by GET https://www.redfin.com/                  (sets cookies)
  2. GET https://www.redfin.com/zipcode/<zip>                          (sets more cookies, returns HTML)
     -> regex out `region_id=(\\d+)` from the embedded data
  3. GET https://www.redfin.com/stingray/api/gis-csv?region_id=...      (returns CSV of listings)

Robust handling: requests.Session with browser headers + warmup, exponential
backoff for 403/429/5xx, individual ZIP failures don't kill the run.
"""
from __future__ import annotations

import csv
import io
import json
import random
import re
import time
from typing import Optional

import requests

from config import (
    BROWSER_HEADERS,
    RAW_LISTINGS_JSON,
    REDFIN_RETRIES,
    REDFIN_SLEEP,
    TARGET_ZIPS,
)

GIS_CSV_URL = "https://www.redfin.com/stingray/api/gis-csv"
ZIP_PAGE_URL_TEMPLATE = "https://www.redfin.com/zipcode/{zip}"
HOMEPAGE_URL = "https://www.redfin.com/"

NAVIGATE_HEADERS = {
    **BROWSER_HEADERS,
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
API_HEADERS = {**BROWSER_HEADERS, "Accept": "text/csv,*/*"}

REGION_ID_RE = re.compile(r"region_id=(\d+)")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    try:
        s.get(HOMEPAGE_URL, headers=NAVIGATE_HEADERS, timeout=15)
        time.sleep(0.6)
    except Exception as e:
        print(f"[redfin] warmup failed: {e} (continuing)")
    return s


def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _request_with_retry(session: requests.Session, url: str, params: Optional[dict] = None,
                        headers: Optional[dict] = None, timeout: int = 30) -> requests.Response:
    last_status = None
    for attempt in range(1, REDFIN_RETRIES + 1):
        try:
            r = session.get(url, params=params, headers=headers, timeout=timeout)
            last_status = r.status_code
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429) or r.status_code >= 500:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"    [redfin] HTTP {r.status_code} (try {attempt}/{REDFIN_RETRIES}) -> sleep {wait:.1f}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"    [redfin] {type(e).__name__}: {e} (try {attempt}/{REDFIN_RETRIES}) -> sleep {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(f"Redfin GET failed after {REDFIN_RETRIES} retries (last status={last_status}): {url}")


def parse_gis_csv(raw_text: str) -> list[dict]:
    """Find the CSV header line (containing ADDRESS+PRICE columns), parse from there."""
    if not raw_text or not raw_text.strip():
        return []
    lines = raw_text.splitlines()
    start: Optional[int] = None
    for i, ln in enumerate(lines):
        if "ADDRESS" in ln and "PRICE" in ln and "YEAR BUILT" in ln:
            start = i
            break
    if start is None:
        return []
    csv_text = "\n".join(lines[start:])
    reader = csv.DictReader(io.StringIO(csv_text))

    results: list[dict] = []
    for row in reader:
        url_col = next((k for k in row if isinstance(k, str) and k.startswith("URL")), None)
        raw_url = ((row.get(url_col) if url_col else "") or "").strip()
        full_url = ("https://www.redfin.com" + raw_url) if raw_url.startswith("/") else raw_url

        def _s(key: str) -> str:
            v = row.get(key)
            return (v or "").strip() if isinstance(v, str) else ""

        if not _s("ADDRESS") or not _s("ZIP OR POSTAL CODE"):
            continue  # skip preamble / disclaimer rows

        results.append({
            "address":     _s("ADDRESS"),
            "city":        _s("CITY"),
            "state":       _s("STATE OR PROVINCE"),
            "zip":         _s("ZIP OR POSTAL CODE"),
            "price":       _safe_int(row.get("PRICE")),
            "beds":        _safe_int(row.get("BEDS")),
            "baths":       _safe_float(row.get("BATHS")),
            "sqft":        _safe_int(row.get("SQUARE FEET")),
            "year_built":  _safe_int(row.get("YEAR BUILT")),
            "price_per_sqft": _safe_int(row.get("$/SQUARE FEET")),
            "redfin_url":  full_url,
            "latitude":    _safe_float(row.get("LATITUDE")),
            "longitude":   _safe_float(row.get("LONGITUDE")),
            "property_type": _s("PROPERTY TYPE"),
            "hoa_month":   _safe_int(row.get("HOA/MONTH")),
            "lot_size":    _safe_int(row.get("LOT SIZE")),
            "days_on_market": _safe_int(row.get("DAYS ON MARKET")),
        })
    return results


def get_region_id_from_zip_page(session: requests.Session, zip_code: str) -> Optional[str]:
    """Fetch /zipcode/<zip> HTML and regex out region_id."""
    url = ZIP_PAGE_URL_TEMPLATE.format(zip=zip_code)
    r = _request_with_retry(session, url, headers=NAVIGATE_HEADERS, timeout=20)
    m = REGION_ID_RE.search(r.text)
    if not m:
        # Fallback regex
        m = re.search(r'"regionId"\s*:\s*"?(\d+)', r.text) or re.search(r'"id":(\d+),"name":"' + re.escape(zip_code), r.text)
    return m.group(1) if m else None


def fetch_zip_listings(session: requests.Session, zip_code: str) -> list[dict]:
    region_id = get_region_id_from_zip_page(session, zip_code)
    if not region_id:
        print(f"  [{zip_code}] no region_id resolvable from zipcode page — skip")
        return []
    print(f"  [{zip_code}] region_id={region_id}")
    params = {
        "al": "1",
        "region_id": region_id,
        "region_type": "2",
        "sf": "1,2,3,5,6,7",
        "status": "9",
        "uipt": "1,3",
        "num_homes": "350",
        "v": "8",
    }
    r = _request_with_retry(session, GIS_CSV_URL, params=params, headers=API_HEADERS, timeout=30)
    listings = parse_gis_csv(r.text)
    for l in listings:
        l["source_zip"] = zip_code
    print(f"  [{zip_code}] -> {len(listings)} listings")
    return listings


def load_all_listings(zips: list[str] | None = None, force_refresh: bool = False) -> list[dict]:
    zips = zips or TARGET_ZIPS

    if RAW_LISTINGS_JSON.exists() and not force_refresh:
        data = json.loads(RAW_LISTINGS_JSON.read_text())
        print(f"[redfin] cache hit -> {len(data)} listings from {RAW_LISTINGS_JSON.name}")
        return data

    print(f"[redfin] cache miss -> fetching {len(zips)} ZIPs")
    session = make_session()
    all_listings: list[dict] = []
    seen_keys: set[str] = set()

    for zip_code in zips:
        try:
            listings = fetch_zip_listings(session, zip_code)
        except Exception as e:
            print(f"  [{zip_code}] FAILED: {e}")
            listings = []
        for lst in listings:
            key = lst.get("redfin_url") or f"{lst['address']}|{lst['zip']}"
            if key not in seen_keys:
                seen_keys.add(key)
                all_listings.append(lst)
        time.sleep(REDFIN_SLEEP + random.uniform(0, 0.5))

    RAW_LISTINGS_JSON.write_text(json.dumps(all_listings, indent=2))
    print(f"[redfin] cache saved -> {len(all_listings)} unique listings to {RAW_LISTINGS_JSON.name}")
    return all_listings


if __name__ == "__main__":
    import sys
    zips = sys.argv[1:] or ["75057"]
    listings = load_all_listings(zips=zips, force_refresh=True)
    if listings:
        print(f"\nFirst sample listing:")
        print(json.dumps(listings[0], indent=2))
        print(f"\nLast sample listing:")
        print(json.dumps(listings[-1], indent=2))
