"""Build interactive Folium map of v4 listings.

Markers are rendered ONCE into a single MarkerCluster. A custom floating
panel handles AND-style filtering across year / price / property-type
dimensions via JavaScript.
"""
from __future__ import annotations

import csv
import html as html_lib
import json
import math
from pathlib import Path

import folium
from folium.plugins import MarkerCluster
from branca.element import Element, Template, MacroElement

from config import (
    OUTPUT_DIR, DATA_DIR, COUNTY_FIPS,
    CORRIDOR_LAT_MIN, CORRIDOR_LAT_MAX, CORRIDOR_LNG_MIN, CORRIDOR_LNG_MAX,
)

CSV_PATH = OUTPUT_DIR / "filtered_listings_v4.csv"
GEOJSON  = DATA_DIR  / "tsahc_official_targeted.geojson"
HTML_OUT = OUTPUT_DIR / "listings_map.html"

ADDISON    = (32.96, -96.83)
LEWISVILLE = (33.04, -96.99)


# ---------- bucket / color helpers ----------
def price_color(price):
    if price is None:    return "#888888"
    if price < 300_000:    return "#e74c3c"
    if price < 500_000:    return "#e67e22"
    if price < 750_000:    return "#f1c40f"
    if price < 1_000_000:  return "#27ae60"
    return "#8e44ad"

def price_bucket(price):
    if price is None:    return "no price"
    if price < 300_000:    return "<$300k"
    if price < 500_000:    return "$300-500k"
    if price < 750_000:    return "$500-750k"
    if price < 1_000_000:  return "$750k-1M"
    return ">$1M"

def year_bucket(year):
    if year is None:    return "no year"
    if year >= 2020:    return "Built 2020+"
    if year >= 2010:    return "Built 2010-2019"
    if year >= 2000:    return "Built 2000-2009"
    return "Built <2000"

def type_bucket(pt):
    if not pt: return "Other"
    if "Single Family" in pt:                    return "SFR"
    if "Townhouse" in pt:                        return "Townhouse"
    if "Condo" in pt or "Co-op" in pt:           return "Condo"
    if "Multi-Family" in pt or "Multi Family" in pt: return "Multi-family"
    if "Vacant Land" in pt or pt == "Land":      return "Land"
    return "Other"

def radius_for(sqft):
    if not sqft or sqft <= 0: return 4.0
    return max(5.0, math.sqrt(sqft) / 8)

def _to_int(v):
    try: return int(float(v)) if v not in ("", None) else None
    except (TypeError, ValueError): return None

def _to_float(v):
    try: return float(v) if v not in ("", None) else None
    except (TypeError, ValueError): return None


def compute_tract_label(r):
    geoid = r.get("tract_geoid", "") or ""
    if not geoid: return ""
    raw = geoid[5:]
    if len(raw) < 6:
        return geoid
    pretty = f"{int(raw[:4])}.{raw[4:]}"
    return f"{r.get('city','')} {r.get('zip','')} (tract {pretty})"


def build_popup_html(r):
    addr  = html_lib.escape(f"{r['address']}, {r['city']}, TX {r['zip']}")
    price = _to_int(r.get("price"))
    sqft  = _to_int(r.get("sqft"))
    ppsf  = (price // sqft) if (price and sqft) else None
    yr    = r.get("year_built") or "—"
    beds  = r.get("beds") or "—"
    baths = r.get("baths") or "—"
    pt    = html_lib.escape(r.get("property_type") or "—")
    hoa   = r.get("hoa_month") or ""
    dom   = r.get("days_on_market") or "—"
    label = compute_tract_label(r)
    da    = r.get("dist_to_addison_mi") or "—"
    dl    = r.get("dist_to_lewisville_mi") or "—"
    lat   = _to_float(r.get("latitude"))
    lng   = _to_float(r.get("longitude"))

    redfin_url = html_lib.escape(r.get("redfin_url") or "#", quote=True)
    gmaps = (f"https://maps.google.com/?q={lat},{lng}" if lat and lng else "#")
    sview = (f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}"
             if lat and lng else "#")

    price_s = f"${price:,}" if price else "—"
    ppsf_s  = f"${ppsf}/sqft" if ppsf else ""
    sqft_s  = f"{sqft:,}" if sqft else "—"
    hoa_s   = f"${hoa}/mo" if hoa else "—"

    return (
      f'<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:13px;width:300px;">'
      f'<div style="font-weight:bold;font-size:14px;margin-bottom:6px;">{addr}</div>'
      f'<div style="color:#c0392b;font-weight:bold;font-size:16px;">{price_s} '
      f'<span style="color:#888;font-size:12px;font-weight:normal;">{ppsf_s}</span></div>'
      f'<div style="margin:6px 0;"><span style="background:#eef;padding:2px 6px;border-radius:3px;font-size:11px;">{pt}</span></div>'
      f'<table style="font-size:12px;border-collapse:collapse;">'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">Beds/Baths:</td><td>{beds} / {baths}</td></tr>'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">Sqft:</td><td>{sqft_s}</td></tr>'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">Year built:</td><td>{yr}</td></tr>'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">HOA:</td><td>{hoa_s}</td></tr>'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">DOM:</td><td>{dom} days</td></tr>'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">Tract:</td><td style="font-size:11px;">{html_lib.escape(label)}</td></tr>'
      f'<tr><td style="padding:1px 8px 1px 0;color:#666;">Distance:</td><td>Addison {da}mi · Lewisville {dl}mi</td></tr>'
      f'</table>'
      f'<div style="margin-top:8px;display:flex;gap:4px;flex-wrap:wrap;">'
      f'<a href="{redfin_url}" target="_blank" style="display:inline-block;padding:4px 8px;background:#a02021;color:#fff;text-decoration:none;border-radius:3px;font-size:11px;">Redfin</a>'
      f'<a href="{html_lib.escape(gmaps, quote=True)}" target="_blank" style="display:inline-block;padding:4px 8px;background:#4285f4;color:#fff;text-decoration:none;border-radius:3px;font-size:11px;">Google Maps</a>'
      f'<a href="{html_lib.escape(sview, quote=True)}" target="_blank" style="display:inline-block;padding:4px 8px;background:#34a853;color:#fff;text-decoration:none;border-radius:3px;font-size:11px;">Street View</a>'
      f'</div></div>'
    )


# ---------- legend ----------
LEGEND_HTML = """
{% macro html(this, kwargs) %}
<div style="position: fixed; bottom: 28px; left: 14px; z-index:9999;
            background: rgba(255,255,255,0.95); padding: 10px 14px; border: 1px solid #999;
            border-radius: 6px; font-family: -apple-system, Helvetica, Arial, sans-serif;
            font-size: 12px; line-height: 1.55; box-shadow: 0 2px 6px rgba(0,0,0,0.15);">
  <div style="font-weight: bold; margin-bottom: 5px; font-size: 13px;">Price legend</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#e74c3c;border-radius:50%;margin-right:6px;"></span>&lt; $300k</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#e67e22;border-radius:50%;margin-right:6px;"></span>$300k - $500k</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#f1c40f;border-radius:50%;margin-right:6px;"></span>$500k - $750k</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#27ae60;border-radius:50%;margin-right:6px;"></span>$750k - $1M</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#8e44ad;border-radius:50%;margin-right:6px;"></span>&gt; $1M</div>
  <div style="margin-top:5px;color:#666;font-size:11px;">Marker size scales with sqft</div>
</div>
{% endmacro %}
"""

TITLE_HTML = """
{% macro html(this, kwargs) %}
<div style="position: fixed; top: 12px; left: 50%; transform: translateX(-50%); z-index: 9999;
            background: rgba(255,255,255,0.95); padding: 7px 18px; border: 2px solid #2c6e9e;
            border-radius: 6px; font-family: -apple-system, Helvetica, Arial, sans-serif;
            font-size: 14px; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.15);">
  Dallas Commute Corridor — TSAHC Targeted Listings (702 active)
</div>
{% endmacro %}
"""


def build_filter_panel_html(year_counts, price_counts, type_counts):
    def cb(group, value, count):
        safe = html_lib.escape(value, quote=True)
        return (f'<label style="display:block;padding:1px 0;font-size:12px;">'
                f'<input type="checkbox" data-filter="{group}" value="{safe}" checked '
                f'style="margin-right:5px;vertical-align:middle;"> '
                f'{html_lib.escape(value)} <span style="color:#888;">({count})</span></label>')

    year_order  = ["Built 2020+", "Built 2010-2019", "Built 2000-2009", "Built <2000", "no year"]
    price_order = ["<$300k", "$300-500k", "$500-750k", "$750k-1M", ">$1M", "no price"]
    type_order  = ["SFR", "Townhouse", "Condo", "Multi-family", "Land", "Other"]

    year_html  = "".join(cb("year", y,  year_counts.get(y, 0))  for y in year_order  if year_counts.get(y, 0))
    price_html = "".join(cb("price", p, price_counts.get(p, 0)) for p in price_order if price_counts.get(p, 0))
    type_html  = "".join(cb("type", t,  type_counts.get(t, 0))  for t in type_order  if type_counts.get(t, 0))

    return f"""
<div id="filter-panel" style="position: fixed; top: 60px; right: 12px; z-index: 9999;
     width: 220px; background: rgba(255,255,255,0.96); padding: 10px 12px;
     border: 1px solid #999; border-radius: 6px;
     font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 12px;
     box-shadow: 0 2px 8px rgba(0,0,0,0.15); max-height: 80vh; overflow-y: auto;">
  <div style="font-weight:bold;font-size:13px;margin-bottom:4px;">
    Showing <span id="visible-count" style="color:#27ae60;">702</span> / <span id="total-count">702</span>
  </div>
  <div style="font-size:11px;color:#888;margin-bottom:6px;">AND filter across all 3 dimensions</div>
  <hr style="margin:6px 0;border:none;border-top:1px solid #ddd;">
  <div style="font-weight:bold;margin:4px 0 2px;">Year built</div>
  {year_html}
  <hr style="margin:6px 0;border:none;border-top:1px solid #ddd;">
  <div style="font-weight:bold;margin:4px 0 2px;">Price</div>
  {price_html}
  <hr style="margin:6px 0;border:none;border-top:1px solid #ddd;">
  <div style="font-weight:bold;margin:4px 0 2px;">Property type</div>
  {type_html}
  <hr style="margin:6px 0;border:none;border-top:1px solid #ddd;">
  <div style="display:flex;gap:6px;">
    <button id="filter-reset" style="flex:1;padding:5px;background:#27ae60;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:11px;">Reset</button>
    <button id="filter-clear" style="flex:1;padding:5px;background:#e74c3c;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:11px;">Clear all</button>
  </div>
</div>
"""


# JS template -- placeholders __LISTINGS__ and __CLUSTER__ are substituted
JS_TEMPLATE = """
//<![CDATA[
window.__LISTINGS_DATA = __LISTINGS__;
window.__cluster_var_name = "__CLUSTER__";

window.addEventListener('load', function() {
  setTimeout(window.__initFilterMap, 80);
});

window.__initFilterMap = function() {
  var cluster = window[window.__cluster_var_name];
  if (!cluster) {
    // try local scope (folium variable) via eval
    try { cluster = eval(window.__cluster_var_name); } catch(e) {}
  }
  if (!cluster) {
    setTimeout(window.__initFilterMap, 100);
    return;
  }
  var data = window.__LISTINGS_DATA;
  var markers = [];
  for (var i = 0; i < data.length; i++) {
    var l = data[i];
    var m = L.circleMarker([l.lat, l.lng], {
      radius: l.r,
      color: l.c,
      weight: 1.2,
      fillColor: l.c,
      fillOpacity: 0.78,
    });
    m.bindPopup(l.p, {maxWidth: 320});
    if (l.t) m.bindTooltip(l.t);
    m._meta = { y: l.yb, pr: l.pb, tp: l.tb };
    markers.push(m);
  }
  cluster.addLayers(markers);
  window.__allMarkers = markers;
  window.__cluster = cluster;
  window.__totalMarkers = markers.length;

  var totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = markers.length;

  // Wire up filter UI
  var panel = document.getElementById('filter-panel');
  if (!panel) return;
  panel.querySelectorAll('input[type=checkbox][data-filter]').forEach(function(cb) {
    cb.addEventListener('change', window.__applyFilters);
  });
  document.getElementById('filter-reset').addEventListener('click', function() {
    panel.querySelectorAll('input[type=checkbox][data-filter]').forEach(function(cb) { cb.checked = true; });
    window.__applyFilters();
  });
  document.getElementById('filter-clear').addEventListener('click', function() {
    panel.querySelectorAll('input[type=checkbox][data-filter]').forEach(function(cb) { cb.checked = false; });
    window.__applyFilters();
  });
};

window.__applyFilters = function() {
  function checkedSet(group) {
    var s = {};
    document.querySelectorAll('input[data-filter="' + group + '"]:checked').forEach(function(cb) {
      s[cb.value] = true;
    });
    return s;
  }
  var ys = checkedSet('year');
  var ps = checkedSet('price');
  var ts = checkedSet('type');

  var keep = [];
  var all = window.__allMarkers;
  for (var i = 0; i < all.length; i++) {
    var m = all[i];
    if (ys[m._meta.y] && ps[m._meta.pr] && ts[m._meta.tp]) {
      keep.push(m);
    }
  }
  window.__cluster.clearLayers();
  if (keep.length) window.__cluster.addLayers(keep);
  var visibleEl = document.getElementById('visible-count');
  if (visibleEl) visibleEl.textContent = keep.length;
};
//]]>
"""


def main():
    print(f"Loading {CSV_PATH.name}...")
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    print(f"  {len(rows)} listings")

    print(f"Loading {GEOJSON.name}...")
    gj = json.loads(GEOJSON.read_text())
    prefixes = tuple(COUNTY_FIPS.values())
    in_corridor = []
    for f in gj["features"]:
        if not f["properties"]["FIPS"].startswith(prefixes):
            continue
        rings = f["geometry"]["coordinates"]
        if not rings: continue
        ring = rings[0]
        c_lng = sum(p[0] for p in ring) / len(ring)
        c_lat = sum(p[1] for p in ring) / len(ring)
        if (CORRIDOR_LAT_MIN <= c_lat <= CORRIDOR_LAT_MAX
                and CORRIDOR_LNG_MIN <= c_lng <= CORRIDOR_LNG_MAX):
            in_corridor.append(f)
    print(f"  {len(in_corridor)} TSAHC polygons in corridor")

    center = ((CORRIDOR_LAT_MIN + CORRIDOR_LAT_MAX) / 2,
              (CORRIDOR_LNG_MIN + CORRIDOR_LNG_MAX) / 2)
    m = folium.Map(location=center, zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Positron",
        max_zoom=19, subdomains="abcd", control=True, overlay=False,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name="CartoDB Voyager",
        max_zoom=19, subdomains="abcd", control=True, overlay=False, show=False,
    ).add_to(m)

    # Polygon overlay
    polygon_fg = folium.FeatureGroup(name="TSAHC Targeted Areas", show=True)
    folium.GeoJson(
        {"type": "FeatureCollection", "features": in_corridor},
        style_function=lambda x: {"fillColor": "#27ae60", "color": "#1e7e34",
                                  "weight": 1, "fillOpacity": 0.20},
        tooltip=folium.GeoJsonTooltip(fields=["FIPS", "County1"],
                                      aliases=["FIPS:", "County:"]),
    ).add_to(polygon_fg)
    polygon_fg.add_to(m)

    # Reference markers
    ref_fg = folium.FeatureGroup(name="Commute references", show=True)
    folium.Marker(
        location=ADDISON,
        popup=folium.Popup("<b>Addison center</b><br>32.96, -96.83", max_width=200),
        tooltip="Addison",
        icon=folium.Icon(icon="home", color="blue", prefix="fa"),
    ).add_to(ref_fg)
    folium.Marker(
        location=LEWISVILLE,
        popup=folium.Popup("<b>Lewisville center</b><br>33.04, -96.99", max_width=200),
        tooltip="Lewisville",
        icon=folium.Icon(icon="home", color="green", prefix="fa"),
    ).add_to(ref_fg)
    ref_fg.add_to(m)

    # Empty MarkerCluster -- JS will populate
    cluster = MarkerCluster(name="Listings",
                            options={"disableClusteringAtZoom": 14,
                                     "maxClusterRadius": 40})
    cluster.add_to(m)
    cluster_name = cluster.get_name()

    # Build listings JSON + counts
    listings_data = []
    bounds = []
    year_counts: dict[str, int] = {}
    price_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    pt_raw_counts: dict[str, int] = {}
    skipped = 0

    for r in rows:
        lat = _to_float(r.get("latitude"))
        lng = _to_float(r.get("longitude"))
        if lat is None or lng is None:
            skipped += 1
            continue
        bounds.append((lat, lng))
        price = _to_int(r.get("price"))
        sqft  = _to_int(r.get("sqft"))
        year  = _to_int(r.get("year_built"))
        pt    = (r.get("property_type") or "").strip()

        yb = year_bucket(year)
        pb = price_bucket(price)
        tb = type_bucket(pt)
        year_counts[yb]  = year_counts.get(yb, 0) + 1
        price_counts[pb] = price_counts.get(pb, 0) + 1
        type_counts[tb]  = type_counts.get(tb, 0) + 1
        pt_raw_counts[pt or "Other"] = pt_raw_counts.get(pt or "Other", 0) + 1

        listings_data.append({
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "r": round(radius_for(sqft), 2),
            "c": price_color(price),
            "p": build_popup_html(r),
            "t": f"${price:,}" if price else "(no price)",
            "yb": yb,
            "pb": pb,
            "tb": tb,
        })

    print(f"  prepared {len(listings_data)} marker records (skipped {skipped})")
    print(f"  by year: {year_counts}")
    print(f"  by price: {price_counts}")
    print(f"  by type: {type_counts}")

    # Filter panel
    panel_html = build_filter_panel_html(year_counts, price_counts, type_counts)
    m.get_root().html.add_child(Element(panel_html))

    # JS to populate cluster + handle filters
    listings_json = json.dumps(listings_data, separators=(",", ":"))
    js_code = JS_TEMPLATE.replace("__LISTINGS__", listings_json) \
                         .replace("__CLUSTER__", cluster_name)
    m.get_root().script.add_child(Element(js_code))

    # LayerControl: only base tiles, polygon overlay, reference points
    folium.LayerControl(position="topleft", collapsed=False).add_to(m)

    # Title + legend
    title = MacroElement(); title._template = Template(TITLE_HTML)
    m.get_root().add_child(title)
    legend = MacroElement(); legend._template = Template(LEGEND_HTML)
    m.get_root().add_child(legend)

    # Fit bounds
    if bounds:
        sw = (min(p[0] for p in bounds), min(p[1] for p in bounds))
        ne = (max(p[0] for p in bounds), max(p[1] for p in bounds))
        m.fit_bounds([sw, ne])

    HTML_OUT.write_bytes(b"")
    m.save(str(HTML_OUT))

    size_kb = HTML_OUT.stat().st_size / 1024
    print(f"\nWritten -> {HTML_OUT}")
    print(f"Size:    {size_kb:,.0f} KB ({size_kb/1024:.2f} MB)")
    print(f"Markers: {len(listings_data)} (single render, AND-filter via JS panel)")


if __name__ == "__main__":
    main()
