"""Static configuration: countries, series codes, thresholds and file paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "fiscal_data.json"
OUTPUT_JS_FILE = DATA_DIR / "fiscal_data.js"
HISTORY_FILE = DATA_DIR / "history.json"
VINTAGES_FILE = DATA_DIR / "imf_vintages.json"
OVERRIDES_FILE = DATA_DIR / "overrides.json"

SCHEMA_VERSION = 2

COUNTRY_NAMES = {
    "ESP": "Spain",
    "CHE": "Switzerland",
    "ITA": "Italy",
    "JPN": "Japan",
    "CAN": "Canada",
    "GBR": "United Kingdom",
    "DEU": "Germany",
    "USA": "United States",
    "FRA": "France",
}
COUNTRIES = list(COUNTRY_NAMES)

# Monthly average 10Y government bond yields on FRED. GS10 is the monthly
# average of the daily US constant maturity yield. The others are the OECD
# long term interest rate series, which FRED republishes with a lag of one
# to two months.
YIELD_SERIES = {
    "USA": "GS10",
    "JPN": "IRLTLT01JPM156N",
    "DEU": "IRLTLT01DEM156N",
    "FRA": "IRLTLT01FRM156N",
    "GBR": "IRLTLT01GBM156N",
    "CAN": "IRLTLT01CAM156N",
    "ITA": "IRLTLT01ITM156N",
    "ESP": "IRLTLT01ESM156N",
    "CHE": "IRLTLT01CHM156N",
}

# IMF WEO indicator codes, keyed by the field name used in the output.
# The SDMX API and the WEO files share these codes. DataMapper uses a
# different code for the primary balance.
IMF_FIELDS = ("real_growth", "inflation", "pb", "debt")
SDMX_INDICATORS = {
    "real_growth": "NGDP_RPCH",   # real GDP growth, %
    "inflation": "PCPIPCH",       # CPI inflation, period average, %
    "pb": "GGXONLB_NGDP",         # general government primary balance, % GDP
    "debt": "GGXWDG_NGDP",        # general government gross debt, % GDP
}
DATAMAPPER_INDICATORS = dict(SDMX_INDICATORS, pb="GGXONLB_G01_GDP_PT")

SDMX_BASE = "https://api.imf.org/external/sdmx/3.0"
SDMX_AGENCY = "IMF.RES"
SDMX_CURRENT_FLOW = "WEO"
DATAMAPPER_BASE = "https://www.imf.org/external/datamapper/api/v1"
FRED_API = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Plausible ranges. A value outside them is rejected and the last good value
# is carried forward instead.
VALID_RANGES = {
    "r": (-1.5, 20.0),
    "real_growth": (-15.0, 15.0),
    "inflation": (-5.0, 30.0),
    "pb": (-20.0, 20.0),
    "debt": (0.0, 400.0),
}

# Moves large enough to deserve a look. The value is still published.
LARGE_YIELD_MOVE = 1.0          # pp, between consecutive published months
LARGE_IMF_REVISION = {          # pp, same target year across two releases
    "real_growth": 2.0,
    "inflation": 2.0,
    "pb": 2.0,
    "debt": 10.0,
}

# A yield month is expected to be the previous calendar month from this day
# of the month onwards, and the month before that until then.
YIELD_EXPECTED_DAY = 20

# Years kept per IMF release in the archive, relative to the release year.
VINTAGE_YEARS_BEFORE = 3
VINTAGE_YEARS_AFTER = 6

# Publication dates of past WEO releases. Used to know which release was in
# force on a given date when reconstructing history. Live releases are dated
# by the run that first detects them.
WEO_RELEASE_DATES = {
    "Apr2019": "2019-04-09",
    "Oct2019": "2019-10-15",
    "Apr2020": "2020-04-14",
    "Oct2020": "2020-10-13",
    "Apr2021": "2021-04-06",
    "Oct2021": "2021-10-12",
    "Apr2022": "2022-04-19",
    "Oct2022": "2022-10-11",
    "Apr2023": "2023-04-11",
    "Oct2023": "2023-10-10",
    "Apr2024": "2024-04-16",
    "Oct2024": "2024-10-22",
    "Apr2025": "2025-04-22",
    "Oct2025": "2025-10-14",
    "Apr2026": "2026-04-14",
}
