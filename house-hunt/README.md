# house-hunt — Dallas DFW + TSAHC targeted-area listing tool

A scripted Redfin scraper + interactive map for finding active for-sale listings inside [TSAHC](https://www.tsahc.org/) Targeted Areas in the Dallas / Fort Worth commute corridor.

**Scope:** This is **Texas-only** and currently scoped to a NW DFW corridor (Irving / Dallas / Plano / Frisco / Lewisville / Denton). It is offered as-is — the listing source and corridor bounds are hard-coded to the original author's house-hunt scenario.

## What it does

1. **`tsahc_official.py`** — pulls the official TSAHC ArcGIS webmap and writes the targeted census-tract polygons to `data/tsahc_official_targeted.geojson`.
2. **`corridor_pipeline_v4.py`** — for each polygon inside the commute bbox (defined in `config.py`), queries the Redfin GIS endpoint for active listings, dedupes, computes haversine distances to two reference cities (Addison & Lewisville), and writes `output/filtered_listings_v4.csv`.
3. **`build_map.py`** — renders `output/listings_map.html`: a Folium map with the TSAHC polygon overlay, a clustered marker layer (one per listing, color-coded by price, sized by sqft), and a JS filter panel that AND-filters by year-built / price band / property type.
4. **`analyze_v4.py`** — terminal sections summarizing the v4 CSV (by city, type, decade, top tracts, distance, composite-score ranking).

## Quick start

```bash
pip install -r requirements.txt

# (optional) refresh the TSAHC polygon data
python tsahc_official.py

# (optional) refresh listings — hits Redfin, takes ~3 minutes
python corridor_pipeline_v4.py

# always available: regenerate the interactive map from the committed sample CSV
python build_map.py
# -> open output/listings_map.html in a browser

# explore the CSV
python analyze_v4.py 1          # by city
python analyze_v4.py S          # composite-scored top picks
python analyze_v4.py stats      # summary stats
```

## What's committed vs what's regenerated

Committed sample data lets you run `build_map.py` without scraping anything:

- `data/tsahc_official_targeted.geojson` — official TSAHC polygons
- `data/tract_city.json` — tract → city label
- `output/filtered_listings_v4.csv` — sample listings snapshot
- `output/listings_map.html` — pre-built map

Larger / volatile caches are gitignored and regenerated on demand:

- `data/raw_listings.json`, `data/geocoded_listings.json`, `data/geocode_cache.json`
- `data/tract_centroids.json`, `data/tract_geometry_2020.json`, `data/tsahc_arcgis_webmap.json`

## Customizing for your area

`config.py` is the only knob you usually need to touch:

- `COUNTY_FIPS` — counties you want included
- `CORRIDOR_LAT_MIN/MAX`, `CORRIDOR_LNG_MIN/MAX` — bbox of your commute corridor
- `TARGET_ZIPS` — used by the v1 main.py flow only
- `MIN_YEAR_BUILT` — used by older flows only

Reference cities for distance columns are hard-coded in `corridor_pipeline_v4.py` (`ADDISON`, `LEWISVILLE`) and `build_map.py` — change those if you're not commuting between Addison and Lewisville.

## Sample data freshness

The committed `output/filtered_listings_v4.csv` and `output/listings_map.html` are a **snapshot from 2026-04-30** of public Redfin for-sale listings inside the corridor. Listings turn over constantly, so by the time you read this most rows will be off-market. The snapshot exists so `build_map.py` and `analyze_v4.py` are runnable out of the box; for live data, re-run `corridor_pipeline_v4.py` (and read the next section first).

## Acceptable use & TOS notice

`corridor_pipeline_v4.py`, `fetch_redfin.py`, and `redfin_poly.py` talk to Redfin's `gis-csv` endpoint, which is undocumented and not part of any public API. This project is **not affiliated with or endorsed by Redfin**. The scraping code is provided for **personal and educational research** only.

If you choose to run it:

- Read [Redfin's Terms of Service](https://www.redfin.com/about/terms-of-use) and `https://www.redfin.com/robots.txt` first. Confirm that personal-research scraping is acceptable in your jurisdiction.
- Keep `REDFIN_SLEEP` at the default (1.5s/request) or higher. Do not parallelize the requests. The pipeline prints a 3-second warning on startup so you have a chance to abort.
- The endpoint can change at any time. The scraper may stop working without notice.
- You are responsible for what you do with the output. Don't redistribute scraped listings as a service or repackage them commercially.

If any of that doesn't sit right with you, just don't run the scraper — `build_map.py` and `analyze_v4.py` work fine off the committed snapshot.

## Other caveats

- **TSAHC eligibility is more than just a polygon.** Being inside a Targeted Area is necessary but not sufficient — income limits, purchase-price limits, and program-specific rules apply. Always confirm with a TSAHC-approved lender before relying on eligibility.
- **CSV schema** is documented in `corridor_pipeline_v4.py` (the `fields` list at the bottom of `main()`).
