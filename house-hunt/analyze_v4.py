"""Per-section summary of filtered_listings_v4.csv. Run with section number 1-7."""
from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from config import OUTPUT_DIR

SRC = OUTPUT_DIR / "filtered_listings_v4.csv"
ROWS = list(csv.DictReader(SRC.open(encoding="utf-8")))


def _to_int(v):
    try:
        return int(float(v)) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _med(values):
    vals = [v for v in values if v is not None]
    return int(statistics.median(vals)) if vals else None


def _ppsf(r):
    """Compute price-per-sqft on the fly since v4 CSV doesn't carry it."""
    p = _to_int(r.get("price"))
    s = _to_int(r.get("sqft"))
    if p and s and s > 0:
        return int(p / s)
    return None


def _ascii(s):
    return (s or "").encode("ascii", "ignore").decode("ascii")


# ----- Section 1: by city -----
def section_1():
    by_city = defaultdict(list)
    for r in ROWS:
        by_city[r.get("city", "?")].append(r)
    print(f"{'city':22s} {'count':>5s}  {'price_median':>13s}  {'$/sqft_median':>14s}")
    print("-" * 60)
    for city, items in sorted(by_city.items(), key=lambda x: -len(x[1])):
        prices = [_to_int(r["price"]) for r in items]
        ppsf   = [_ppsf(r) for r in items]
        pm = _med(prices); sm = _med(ppsf)
        pm_s = f"${pm:,}" if pm is not None else "-"
        sm_s = f"${sm}/sqft" if sm is not None else "-"
        print(f"{_ascii(city):22s} {len(items):>5d}  {pm_s:>13s}  {sm_s:>14s}")


# ----- Section 2: by property_type -----
def section_2():
    by_pt = defaultdict(list)
    for r in ROWS:
        by_pt[r.get("property_type") or "?"].append(r)
    print(f"{'property_type':32s} {'count':>5s}  {'price_median':>13s}")
    print("-" * 60)
    for pt, items in sorted(by_pt.items(), key=lambda x: -len(x[1])):
        prices = [_to_int(r["price"]) for r in items]
        pm = _med(prices)
        pm_s = f"${pm:,}" if pm is not None else "-"
        print(f"{_ascii(pt):32s} {len(items):>5d}  {pm_s:>13s}")


# ----- Section 3: by year_built decade -----
def section_3():
    by_decade = defaultdict(list)
    for r in ROWS:
        yr = _to_int(r.get("year_built"))
        if yr is None or yr < 1900:
            decade = "(no year)"
        else:
            decade = f"{(yr // 10) * 10}s"
        by_decade[decade].append(r)
    print(f"{'decade':12s} {'count':>5s}  {'price_median':>13s}")
    print("-" * 40)
    for decade in sorted(by_decade.keys()):
        items = by_decade[decade]
        prices = [_to_int(r["price"]) for r in items]
        pm = _med(prices)
        pm_s = f"${pm:,}" if pm is not None else "-"
        print(f"{decade:12s} {len(items):>5d}  {pm_s:>13s}")


# ----- Section 4: top 15 tracts by listing count -----
def section_4():
    by_tract = defaultdict(list)
    for r in ROWS:
        by_tract[r["tract_geoid"]].append(r)
    sorted_tracts = sorted(by_tract.items(), key=lambda x: -len(x[1]))[:15]
    print(f"{'tract_geoid':14s} {'tract_label':36s} {'city':18s} {'cnt':>3s}  "
          f"{'price_min':>9s} {'price_max':>10s}  {'$/sqft_med':>10s}")
    print("-" * 110)
    for geoid, items in sorted_tracts:
        prices = sorted([_to_int(r["price"]) for r in items if _to_int(r["price"]) is not None])
        ppsf = [_ppsf(r) for r in items]
        sm = _med(ppsf)
        # tract_label not in v4 CSV directly - reconstruct
        cz = Counter(r["zip"] for r in items if r.get("zip"))
        cc = Counter(r["city"] for r in items if r.get("city"))
        zipc = cz.most_common(1)[0][0] if cz else "?"
        city = cc.most_common(1)[0][0] if cc else "?"
        raw = geoid[5:]
        pretty = f"{int(raw[:4])}.{raw[4:]}"
        label = f"{city} {zipc} (tract {pretty})"
        pmin = f"${prices[0]:,}" if prices else "-"
        pmax = f"${prices[-1]:,}" if prices else "-"
        sm_s = f"${sm}" if sm is not None else "-"
        print(f"{geoid:14s} {_ascii(label)[:36]:36s} {_ascii(city)[:18]:18s} {len(items):>3d}  "
              f"{pmin:>9s} {pmax:>10s}  {sm_s:>10s}")


# ----- Section 5: top 30 by dist_to_addison_mi (closest first) -----
def _print_listing_row(r):
    addr = _ascii(r["address"])[:32]
    city = _ascii(r["city"])[:14]
    price = _to_int(r["price"])
    p_s = f"${price:,}" if price else "-"
    pt = _ascii(r["property_type"] or "")[:14]
    yr = r.get("year_built", "") or "-"
    sq = r.get("sqft", "") or "-"
    ppsf_v = _ppsf(r)
    ppsf = str(ppsf_v) if ppsf_v else "-"
    hoa = r.get("hoa_month", "") or "-"
    dom = r.get("days_on_market", "") or "-"
    da = r.get("dist_to_addison_mi", "") or "-"
    dl = r.get("dist_to_lewisville_mi", "") or "-"
    print(f"{addr:32s} {city:14s} {p_s:>9s} {pt:14s} {yr:>4s} {sq:>5s} ${ppsf:>3s} ${hoa:>4s} {dom:>3s} {da:>5s}/{dl:<5s} {r['redfin_url']}")


def section_5():
    rows = sorted(
        [r for r in ROWS if _to_float(r.get("dist_to_addison_mi"))],
        key=lambda r: _to_float(r["dist_to_addison_mi"]),
    )[:30]
    print(f"{'address':32s} {'city':14s} {'price':>9s} {'type':14s} "
          f"{'yr':>4s} {'sqft':>5s} ${'ps':>3s} ${'HOA':>4s} {'DOM':>3s} {'dAdd/dLew':>11s} url")
    print("-" * 200)
    for r in rows:
        _print_listing_row(r)


def section_6():
    rows = sorted(
        [r for r in ROWS if _to_float(r.get("dist_to_lewisville_mi"))],
        key=lambda r: _to_float(r["dist_to_lewisville_mi"]),
    )[:30]
    print(f"{'address':32s} {'city':14s} {'price':>9s} {'type':14s} "
          f"{'yr':>4s} {'sqft':>5s} ${'ps':>3s} ${'HOA':>4s} {'DOM':>3s} {'dAdd/dLew':>11s} url")
    print("-" * 200)
    for r in rows:
        _print_listing_row(r)


def section_7(offset: int = 0, limit: int = 60):
    """Price < $400k AND year_built >= 2010, paginated."""
    matches = []
    for r in ROWS:
        p = _to_int(r.get("price"))
        y = _to_int(r.get("year_built"))
        if p is None or y is None:
            continue
        if p < 400000 and y >= 2010:
            matches.append(r)
    matches.sort(key=lambda r: (_to_int(r["price"]) or 0, _to_float(r.get("dist_to_addison_mi")) or 99))
    total = len(matches)
    chunk = matches[offset:offset + limit]
    print(f"# total matches (price<$400k, year>=2010): {total}")
    print(f"# showing rows {offset+1}-{offset+len(chunk)}")
    print(f"{'address':32s} {'city':14s} {'price':>9s} {'type':14s} "
          f"{'yr':>4s} {'sqft':>5s} ${'ps':>3s} ${'HOA':>4s} {'DOM':>3s} {'dAdd/dLew':>11s} url")
    print("-" * 200)
    for r in chunk:
        _print_listing_row(r)


def _tract_label_map(rows: list[dict]) -> dict[str, str]:
    """Build {tract_geoid -> 'City Zip (tract X.YY)'} from row scope."""
    by_t: dict[str, list[dict]] = {}
    for r in rows:
        by_t.setdefault(r["tract_geoid"], []).append(r)
    out = {}
    for geoid, items in by_t.items():
        cz = Counter(r["zip"] for r in items if r.get("zip"))
        cc = Counter(r["city"] for r in items if r.get("city"))
        zipc = cz.most_common(1)[0][0] if cz else "?"
        city = cc.most_common(1)[0][0] if cc else "?"
        raw = geoid[5:]
        out[geoid] = f"{city} {zipc} (tract {int(raw[:4])}.{raw[4:]})"
    return out


def _print_query_row(r, label_map):
    addr = _ascii(r["address"])[:28]
    city = _ascii(r["city"])[:9]
    zipc = (r.get("zip") or "")[:5]
    p = _to_int(r["price"])
    p_s = f"${p:,}" if p else "-"
    pt = _ascii(r["property_type"] or "")[:13]
    yr = r.get("year_built", "") or "-"
    sq = r.get("sqft", "") or "-"
    ppsf_v = _ppsf(r); ppsf = str(ppsf_v) if ppsf_v else "-"
    beds = r.get("beds", "") or "-"
    baths = r.get("baths", "") or "-"
    hoa = r.get("hoa_month", "") or "-"
    dom = r.get("days_on_market", "") or "-"
    lot = r.get("lot_size", "") or "-"
    da = r.get("dist_to_addison_mi", "") or "-"
    dl = r.get("dist_to_lewisville_mi", "") or "-"
    label = label_map.get(r["tract_geoid"], r["tract_geoid"])[:30]
    print(f"{addr:28s} {city:9s} {zipc:>5s} {p_s:>9s} {pt:13s} {yr:>4s} {sq:>5s} "
          f"${ppsf:>3s} {beds:>3s} {baths:>4s} ${hoa:>4s} {dom:>3s} {lot:>6s} "
          f"{da:>5s}/{dl:<5s} {label:30s} {r['redfin_url']}")


def _print_query_header():
    print(f"{'address':28s} {'city':9s} {'zip':>5s} {'price':>9s} {'type':13s} "
          f"{'yr':>4s} {'sqft':>5s} ${'ps':>3s} {'bd':>3s} {'ba':>4s} "
          f"${'HOA':>4s} {'DOM':>3s} {'lot':>6s} {'dAdd/dLew':>11s} "
          f"{'tract_label':30s} url")
    print("-" * 240)


def _print_summary(rows, label):
    if not rows:
        print(f"{label}: 0 matches")
        return
    prices = [_to_int(r["price"]) for r in rows]
    sqfts = [_to_int(r["sqft"]) for r in rows]
    ppsfs = [_ppsf(r) for r in rows]
    pm = _med(prices); sm = _med(sqfts); psm = _med(ppsfs)
    print(f"{label}: {len(rows)} matches | "
          f"Median price: ${pm:,} | Median sqft: {sm} | Median $/sqft: ${psm}")


_KEEP_TYPES = {"Single Family Residential", "Townhouse", "Condo/Co-op"}


def _passes_small_new(r, year_lo, year_hi=None):
    """Filter: year window + beds 1-3 + type in {SFR,TH,Condo} + price not null."""
    y = _to_int(r.get("year_built"))
    if y is None or y < year_lo:
        return False
    if year_hi is not None and y > year_hi:
        return False
    b = _to_int(r.get("beds"))
    if b is None or b < 1 or b > 3:
        return False
    if r.get("property_type") not in _KEEP_TYPES:
        return False
    if _to_int(r.get("price")) is None:
        return False
    return True


def _filter_a():
    """Query A: year >= 2020, beds 1-3, SFR/TH/Condo, price not null. Sort price ASC."""
    out = [r for r in ROWS if _passes_small_new(r, 2020)]
    out.sort(key=lambda r: _to_int(r["price"]) or 0)
    return out


def _filter_b():
    """Query B: year 2018-2019, beds 1-3, SFR/TH/Condo, price not null. Sort price ASC."""
    out = [r for r in ROWS if _passes_small_new(r, 2018, 2019)]
    out.sort(key=lambda r: _to_int(r["price"]) or 0)
    return out


import re as _re

_SKIP_STREET_TOKENS = {
    "N", "S", "E", "W", "NE", "NW", "SE", "SW",
    "NORTH", "SOUTH", "EAST", "WEST",
    "TBD",
}


def _street_keyword(addr: str) -> str:
    """First non-numeric, non-directional word in the address."""
    if not addr:
        return ""
    for tok in addr.split():
        if _re.match(r"^\d", tok):
            continue
        if tok.upper() in _SKIP_STREET_TOKENS:
            continue
        return tok.strip(".,#")
    return ""


def section_a(offset=0, limit=25, summary_only=False):
    rows = _filter_a()
    label = "Section A (year>=2020, beds 1-3, SFR/Townhouse/Condo, price not null)"
    if offset == 0 and not summary_only:
        _print_summary(rows, label)
    if summary_only:
        _print_summary(rows, label)
        return
    label_map = _tract_label_map(rows)
    chunk = rows[offset:offset + limit]
    print(f"# rows {offset+1}-{offset+len(chunk)} of {len(rows)}")
    _print_query_header()
    for r in chunk:
        _print_query_row(r, label_map)


def section_b(offset=0, limit=25, summary_only=False):
    rows = _filter_b()
    label = "Section B (year 2018-2019, beds 1-3, SFR/Townhouse/Condo, price not null)"
    if offset == 0 and not summary_only:
        _print_summary(rows, label)
    if summary_only:
        _print_summary(rows, label)
        return
    label_map = _tract_label_map(rows)
    chunk = rows[offset:offset + limit]
    print(f"# rows {offset+1}-{offset+len(chunk)} of {len(rows)}")
    _print_query_header()
    for r in chunk:
        _print_query_row(r, label_map)


def section_c(*_a, **_kw):
    """Cluster Query A results by (zip, street keyword); keep groups with >=2."""
    rows_a = _filter_a()
    clusters: dict[tuple, list[dict]] = {}
    for r in rows_a:
        sk = _street_keyword(r["address"])
        if not sk:
            continue
        key = (r.get("zip", "?"), sk)
        clusters.setdefault(key, []).append(r)

    multi = [(k, items) for k, items in clusters.items() if len(items) >= 2]
    multi.sort(key=lambda kv: -len(kv[1]))

    total_listings = sum(len(v) for _, v in multi)
    print(f"Section C (street clusters from Query A, group size >=2): "
          f"{len(multi)} clusters, {total_listings} listings")
    print(f"{'zip':>5s}  {'street':24s}  {'count':>5s}  {'price_min':>10s}  "
          f"{'price_max':>10s}  {'avg_year':>8s}")
    print("-" * 80)
    for (zip_, sk), items in multi:
        prices = sorted(_to_int(r["price"]) for r in items if _to_int(r["price"]) is not None)
        years = [_to_int(r["year_built"]) for r in items if _to_int(r["year_built"]) is not None]
        avg_y = round(sum(years) / len(years)) if years else "-"
        pmin = f"${prices[0]:,}" if prices else "-"
        pmax = f"${prices[-1]:,}" if prices else "-"
        print(f"{zip_:>5s}  {sk:24s}  {len(items):>5d}  {pmin:>10s}  {pmax:>10s}  {str(avg_y):>8s}")


SECTIONS = {
    "1": section_1, "2": section_2, "3": section_3, "4": section_4,
    "5": section_5, "6": section_6,
}


# ====================================================================
# Section S: composite-scored final filter
# ====================================================================
ZIP_SCORE = {
    # Tier 10: Trinity Groves / Bishop Arts edge
    "75212": 10, "75203": 10,
    # Tier 9
    "75208": 9, "75226": 9,
    # Tier 8: East Dallas / Lakewood
    "75204": 8, "75218": 8, "75223": 8,
    # Tier 7: Irving
    "75038": 7, "75039": 7, "75061": 7, "75062": 7,
    # Tier 6
    "75231": 6,
    "76011": 6, "76012": 6, "76013": 6,
    # Tier 5
    "75215": 5, "75210": 5,
    # Denton (any 762xx is Denton county per our pipeline)
    "76201": 5, "76205": 5, "76209": 5, "76208": 5,
    # Tier 3 (high-crime)
    "75216": 3, "75217": 3, "75232": 3, "75241": 3,
    # Default: 5
}


def _score_year(y):
    if y is None: return 0
    if y >= 2025: return 10
    if y == 2024: return 8
    if y == 2023: return 7
    if y == 2022: return 6
    if y == 2021: return 5
    if y == 2020: return 4
    if y >= 2018: return 3
    if y >= 2015: return 2
    return 0


def _score_ppsf(ppsf):
    if ppsf is None: return 0
    if ppsf < 150:  return 10
    if ppsf < 180:  return 9
    if ppsf < 220:  return 8
    if ppsf < 260:  return 6
    if ppsf < 300:  return 4
    return 2


def _score_zip(zipc):
    return ZIP_SCORE.get((zipc or "").strip(), 5)


def _score_sqft(s):
    if s is None: return 0
    if 1500 <= s <= 2200: return 10
    if 2200 < s <= 2800:  return 9
    if 1200 <= s < 1500:  return 8
    if 2800 < s <= 3500:  return 7
    if s < 1200:          return 6
    return 5


def _score_dom(d):
    if d is None: return 5
    if d < 14:    return 10
    if d < 30:    return 9
    if d < 60:    return 8
    if d < 90:    return 6
    if d < 180:   return 4
    return 2


def _score_listing(r):
    y    = _to_int(r.get("year_built"))
    ppsf = _ppsf(r)
    s    = _to_int(r.get("sqft"))
    d    = _to_int(r.get("days_on_market"))
    sy = _score_year(y)
    sp = _score_ppsf(ppsf)
    sz = _score_zip(r.get("zip"))
    sf = _score_sqft(s)
    sd = _score_dom(d)
    return sy + sp + sz + sf + sd, (sy, sp, sz, sf, sd)


def _filter_s():
    """year>=2015, beds 1-4, price<=500k, type in {SFR,TH,Condo}, score-ranked."""
    keep = {"Single Family Residential", "Townhouse", "Condo/Co-op"}
    out = []
    for r in ROWS:
        y = _to_int(r.get("year_built"))
        if y is None or y < 2015:
            continue
        b = _to_int(r.get("beds"))
        if b is None or b < 1 or b > 4:
            continue
        p = _to_int(r.get("price"))
        if p is None or p > 500_000:
            continue
        if r.get("property_type") not in keep:
            continue
        score, parts = _score_listing(r)
        r2 = dict(r)
        r2["_score"] = score
        r2["_score_parts"] = parts
        out.append(r2)
    out.sort(key=lambda r: (-r["_score"], _to_int(r["price"]) or 0))
    return out


def _print_score_header():
    print(f"{'#':>3s} | {'sc':>2s} | {'address':35s} | {'city':10s} | {'zip':>5s} | "
          f"{'price':>9s} | {'yr':>4s} | {'sqft':>5s} | {'$/sf':>4s} | "
          f"{'bd':>2s} | {'ba':>3s} | {'type':25s} | {'dom':>3s} | "
          f"{'dAdd':>5s} | {'dLew':>5s} | url")
    print("-" * 240)


def _print_score_row(idx, r):
    addr = _ascii(r["address"])
    city = _ascii(r["city"])
    zipc = r.get("zip") or ""
    p = _to_int(r.get("price"))
    p_s = f"${p:,}" if p else "-"
    yr = r.get("year_built", "") or "-"
    sq = r.get("sqft", "") or "-"
    ppsf_v = _ppsf(r); ppsf = str(ppsf_v) if ppsf_v else "-"
    bd = r.get("beds", "") or "-"
    ba = r.get("baths", "") or "-"
    pt = _ascii(r.get("property_type") or "")
    dom = r.get("days_on_market", "") or "-"
    da = r.get("dist_to_addison_mi", "") or "-"
    dl = r.get("dist_to_lewisville_mi", "") or "-"
    print(f"{idx:>3d} | {r['_score']:>2d} | {addr:35s} | {city:10s} | {zipc:>5s} | "
          f"{p_s:>9s} | {yr:>4s} | {sq:>5s} | {ppsf:>4s} | "
          f"{bd:>2s} | {ba:>3s} | {pt:25s} | {dom:>3s} | "
          f"{da:>5s} | {dl:>5s} | {r['redfin_url']}")


def section_s(offset=0, limit=25, summary_only=False):
    rows = _filter_s()
    total = len(rows)
    if summary_only:
        print(f"Section S: {total} matches (year>=2015, beds 1-4, price<=$500k, SFR/TH/Condo)")
        return
    chunk = rows[offset:offset + limit]
    print(f"Section: rank {offset+1} to {offset+len(chunk)} | Showing {len(chunk)} / Total {total}")
    _print_score_header()
    for i, r in enumerate(chunk, start=offset + 1):
        _print_score_row(i, r)


def section_stats():
    """Final summary stats for Section S."""
    from collections import Counter
    rows = _filter_s()
    total = len(rows)
    print(f"Total matches: {total}")
    print()

    # ZIP top 8
    zip_counts = Counter((r.get("zip") or "?") for r in rows)
    print(f"By ZIP (top 8):")
    for z, n in zip_counts.most_common(8):
        print(f"  {z:>5s} : {n}")
    print()

    # Year
    print(f"By year_built:")
    yr_counts = Counter(int(r["year_built"]) for r in rows if _to_int(r.get("year_built")))
    for y in sorted(yr_counts):
        print(f"  {y} : {yr_counts[y]}")
    print()

    # Property type
    print(f"By property_type:")
    for pt, n in Counter(r.get("property_type") for r in rows).most_common():
        print(f"  {pt:30s} : {n}")
    print()

    # Price bands
    print(f"By price band ($50k):")
    bands = Counter()
    for r in rows:
        p = _to_int(r.get("price"))
        if p is None:
            continue
        lo = (p // 50_000) * 50_000
        bands[lo] += 1
    for lo in sorted(bands):
        hi = lo + 50_000
        print(f"  ${lo//1000}k-${hi//1000}k : {bands[lo]}")
    print()

    # Medians
    prices = sorted(_to_int(r["price"]) for r in rows if _to_int(r.get("price")))
    sqfts  = sorted(_to_int(r["sqft"]) for r in rows if _to_int(r.get("sqft")))
    ppsfs  = sorted(p for p in (_ppsf(r) for r in rows) if p)
    years  = sorted(_to_int(r["year_built"]) for r in rows if _to_int(r.get("year_built")))
    doms   = sorted(_to_int(r["days_on_market"]) for r in rows if _to_int(r.get("days_on_market")) is not None)

    def m(L): return L[len(L) // 2] if L else "-"
    print("Medians:")
    print(f"  price       : ${m(prices):,}" if prices else "  price       : -")
    print(f"  sqft        : {m(sqfts):,}"   if sqfts  else "  sqft        : -")
    print(f"  $/sqft      : ${m(ppsfs)}"    if ppsfs  else "  $/sqft      : -")
    print(f"  year_built  : {m(years)}"     if years  else "  year_built  : -")
    print(f"  days_on_mkt : {m(doms)}"      if doms   else "  days_on_mkt : -")


if __name__ == "__main__":
    sec = sys.argv[1] if len(sys.argv) > 1 else "1"
    parts = sec.split(":")
    head = parts[0]
    if head == "7":
        offset = int(parts[1]) if len(parts) > 1 else 0
        limit  = int(parts[2]) if len(parts) > 2 else 60
        section_7(offset, limit)
    elif head in ("A", "a"):
        summary = (len(parts) > 1 and parts[1] == "summary")
        offset = int(parts[1]) if (len(parts) > 1 and not summary) else 0
        limit  = int(parts[2]) if len(parts) > 2 else 25
        section_a(offset, limit, summary_only=summary)
    elif head in ("B", "b"):
        summary = (len(parts) > 1 and parts[1] == "summary")
        offset = int(parts[1]) if (len(parts) > 1 and not summary) else 0
        limit  = int(parts[2]) if len(parts) > 2 else 25
        section_b(offset, limit, summary_only=summary)
    elif head in ("C", "c"):
        summary = (len(parts) > 1 and parts[1] == "summary")
        offset = int(parts[1]) if (len(parts) > 1 and not summary) else 0
        limit  = int(parts[2]) if len(parts) > 2 else 25
        section_c(offset, limit, summary_only=summary)
    elif head in ("S", "s"):
        summary = (len(parts) > 1 and parts[1] == "summary")
        offset = int(parts[1]) if (len(parts) > 1 and not summary) else 0
        limit  = int(parts[2]) if len(parts) > 2 else 25
        section_s(offset, limit, summary_only=summary)
    elif head == "stats":
        section_stats()
    else:
        SECTIONS[sec]()
