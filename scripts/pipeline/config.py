"""Static configuration: countries, series codes, thresholds and file paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "fiscal_data.json"
OUTPUT_JS_FILE = DATA_DIR / "fiscal_data.js"
HISTORY_FILE = DATA_DIR / "history.json"
VINTAGES_FILE = DATA_DIR / "imf_vintages.json"
OVERRIDES_FILE = DATA_DIR / "overrides.json"

SCHEMA_VERSION = 3

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
    "AUS": "Australia",
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
    "AUS": "IRLTLT01AUM156N",
}

# IMF WEO indicator codes, keyed by the field name used in the output.
# The SDMX API and the WEO files share these codes. DataMapper uses a
# different code for the primary balance.
# Fields used in the fiscal gap. The GDP deflator is derived, not fetched:
# deflator growth = (1 + nominal GDP growth) / (1 + real growth) - 1, so
# nominal growth g matches IMF nominal GDP exactly. See imf.derive().
IMF_FIELDS = ("real_growth", "deflator", "pb", "debt")
SDMX_INDICATORS = {
    "real_growth": "NGDP_RPCH",   # real GDP growth, %
    "ngdp": "NGDP",               # nominal GDP, national currency
    "pb": "GGXONLB_NGDP",         # general government primary balance, % GDP
    "debt": "GGXWDG_NGDP",        # general government gross debt, % GDP
}
# Archived alongside, but not part of the fiscal gap. They explain why the
# IMF debt path differs from the simple projection: the overall balance gives
# net interest (primary minus overall), nominal GDP gives nominal growth on
# the GDP deflator.
AUX_INDICATORS = {
    "overall_balance": "GGXCNL_NGDP",  # general government net lending, % GDP
}
# DataMapper has no nominal GDP in national currency, so a DataMapper
# fallback cannot give the deflator. The archived release fills it in.
DATAMAPPER_INDICATORS = {"real_growth": "NGDP_RPCH", "pb": "GGXONLB_G01_GDP_PT", "debt": "GGXWDG_NGDP"}

# Year of each IMF field relative to the forecast year t. Debt dynamics run
# from the end of last year: d_t = d_(t-1) x (1 + r) / (1 + g) - pb_t, so the
# stabilising balance uses debt at the end of t-1.
IMF_YEAR_OFFSET = {"real_growth": 0, "deflator": 0, "pb": 0, "debt": -1}


def field_year(field, forecast_year):
    return forecast_year + IMF_YEAR_OFFSET[field]

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
    "deflator": (-10.0, 30.0),
    "pb": (-20.0, 20.0),
    "debt": (0.0, 400.0),
}

# Moves large enough to deserve a look. The value is still published.
LARGE_YIELD_MOVE = 1.0          # pp, between consecutive published months
LARGE_IMF_REVISION = {          # pp, same target year across two releases
    "real_growth": 2.0,
    "deflator": 2.0,
    "pb": 2.0,
    "debt": 5.0,
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
