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

## Caveats

- **Redfin's GIS endpoint is undocumented.** The scraper uses browser-style headers and respects a 1.5s sleep between requests, but it is not an official API. Don't run it in tight loops; expect occasional breakage if Redfin changes their endpoint.
- **TSAHC eligibility is more than just a polygon.** Being inside a Targeted Area is necessary but not sufficient — income limits, purchase-price limits, and program-specific rules apply. Always confirm with a TSAHC-approved lender before relying on eligibility.
- **CSV schema** is documented in `corridor_pipeline_v4.py` (the `fields` list at the bottom of `main()`).
