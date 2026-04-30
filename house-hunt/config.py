"""Project-wide constants and paths."""
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

TARGET_ZIPS = [
    "75067", "75056", "75007", "75006", "75234", "75244",
    "75254", "75038", "75039", "75019", "75229", "75230", "75240",
]

COUNTY_FIPS = {
    "Collin":  "48085",
    "Dallas":  "48113",
    "Denton":  "48121",
    "Tarrant": "48439",
}
TARGET_COUNTY_FIPS_PREFIXES = set(COUNTY_FIPS.values())

# User-supplied known Targeted FIPS — pipeline-plumbing fallback.
# Used when PDF parsing fails AND merged with PDF results when it succeeds
# (some entries may be from a later TSAHC update than the 2020 PDF).
HARDCODED_TRACTS: set[str] = {
    "48121021645",   # Denton  216.45
    "48121021739",   # Denton  217.39
    "48085031723",   # Collin  317.23
    "48113009610",   # Dallas   96.10
    "48113009804",   # Dallas   98.04   (also in 2020 PDF)
    "48113007204",   # Dallas   72.04
    "48113010001",   # Dallas  100.01
}

TSAHC_PDF_URL = (
    "https://www.tsahc.org/public/upload/files/general/"
    "2020_How_to_Determine_Targeted_Areas.pdf"
)

TSAHC_PDF_PATH       = DATA_DIR / "tsahc_targeted_areas.pdf"
TARGETED_TRACTS_JSON = DATA_DIR / "targeted_tracts.json"
RAW_LISTINGS_JSON    = DATA_DIR / "raw_listings.json"
GEOCODED_JSON        = DATA_DIR / "geocoded_listings.json"
GEOCODE_CACHE_JSON   = DATA_DIR / "geocode_cache.json"

FILTERED_CSV = OUTPUT_DIR / "filtered_listings.csv"
REPORT_HTML  = OUTPUT_DIR / "report.html"

MIN_YEAR_BUILT  = 2000

# Commute corridor (NW DFW: Prosper N -> Irving S, Denton W -> Plano E)
CORRIDOR_LAT_MIN = 32.70   # Irving/DFW south
CORRIDOR_LAT_MAX = 33.30   # Prosper north
CORRIDOR_LNG_MIN = -97.20  # west of Denton
CORRIDOR_LNG_MAX = -96.65  # Plano east
GEOCODE_SLEEP   = 0.5
REDFIN_SLEEP    = 1.5
REDFIN_RETRIES  = 3

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.redfin.com/",
    "Origin": "https://www.redfin.com",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
