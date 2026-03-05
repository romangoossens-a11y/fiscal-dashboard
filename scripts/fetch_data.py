"""
Fiscal Sustainability Dashboard — Data Fetcher
==============================================
Fetches 10Y nominal yields from FRED and fiscal/macro variables from IMF DataMapper.
Computes pb*, fiscal gap, sorts countries, writes data/fiscal_data.json.

Requirements:
    pip install requests pandas fredapi

Usage:
    export FRED_API_KEY=your_key_here      # Linux/Mac
    set FRED_API_KEY=your_key_here         # Windows
    python scripts/fetch_data.py
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests

try:
    from fredapi import Fred
except ImportError:
    print("ERROR: fredapi not installed. Run: pip install fredapi")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECTION_YEAR = date.today().year
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "fiscal_data.json"
OUTPUT_JS_FILE = Path(__file__).parent.parent / "data" / "fiscal_data.js"
OVERRIDES_FILE = Path(__file__).parent.parent / "data" / "overrides.json"

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

# FRED series IDs for 10Y nominal government bond yields
FRED_SERIES = {
    "USA": "DGS10",
    "JPN": "IRLTLT01JPM156N",
    "DEU": "IRLTLT01DEM156N",
    "FRA": "IRLTLT01FRM156N",
    "GBR": "IRLTLT01GBM156N",
    "CAN": "IRLTLT01CAM156N",
    "ITA": "IRLTLT01ITM156N",
    "ESP": "IRLTLT01ESM156N",
    "CHE": "IRLTLT01CHM156N",
}

IMF_INDICATORS = {
    "debt": "GGXWDG_NGDP",       # Gross govt debt % GDP
    "pb": "GGXONLB_G01_GDP_PT",   # Primary balance % GDP (+ = surplus)
    "real_growth": "NGDP_RPCH",  # Real GDP growth %
    "inflation": "PCPIPCH",      # CPI inflation %
}

IMF_BASE_URL = "https://www.imf.org/external/datamapper/api/v1"
IMF_COUNTRY_STR = "/".join(COUNTRY_NAMES.keys())

# ---------------------------------------------------------------------------
# FRED Fetching
# ---------------------------------------------------------------------------

def fetch_fred_yields(api_key: str) -> dict:
    """Fetch latest 10Y nominal yield for each country from FRED."""
    fred = Fred(api_key=api_key)
    yields = {}
    for iso3, series_id in FRED_SERIES.items():
        try:
            series = fred.get_series(series_id)
            latest = float(series.dropna().iloc[-1])
            yields[iso3] = round(latest, 2)
            print(f"  FRED {iso3}: {latest:.2f}% ({series_id})")
        except Exception as e:
            print(f"  WARNING: Could not fetch FRED {series_id} for {iso3}: {e}")
            yields[iso3] = None
    return yields


# ---------------------------------------------------------------------------
# IMF DataMapper Fetching
# ---------------------------------------------------------------------------

def fetch_imf_indicator(indicator: str) -> dict:
    """Fetch an IMF DataMapper indicator for all countries. Returns {iso3: value}."""
    url = f"{IMF_BASE_URL}/{indicator}/{IMF_COUNTRY_STR}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  WARNING: Could not fetch IMF {indicator}: {e}")
        return {}

    values = data.get("values", {}).get(indicator, {})
    # Print available years for first country to aid debugging
    first_iso = next(iter(COUNTRY_NAMES))
    available = sorted(k for k, v in values.get(first_iso, {}).items() if v is not None)
    print(f"    Available years for {indicator} ({first_iso}): {available[-6:] if available else 'none'}")

    result = {}
    years_to_try = [str(PROJECTION_YEAR - i) for i in range(6)]  # try up to 6 years back
    for iso3 in COUNTRY_NAMES:
        country_data = values.get(iso3, {})
        for year in years_to_try:
            if year in country_data and country_data[year] is not None:
                result[iso3] = round(float(country_data[year]), 2)
                break
        if iso3 not in result:
            print(f"  WARNING: No IMF {indicator} data for {iso3}")
            result[iso3] = None
    return result


def fetch_imf_data() -> dict:
    """Fetch all IMF indicators. Returns dict of {indicator_name: {iso3: value}}."""
    imf_data = {}
    for key, indicator in IMF_INDICATORS.items():
        print(f"  Fetching IMF {indicator} ({key})...")
        imf_data[key] = fetch_imf_indicator(indicator)
    return imf_data


# ---------------------------------------------------------------------------
# Load Manual Overrides
# ---------------------------------------------------------------------------

def load_overrides() -> dict:
    """Load optional overrides from data/overrides.json."""
    if OVERRIDES_FILE.exists():
        with open(OVERRIDES_FILE) as f:
            overrides = json.load(f)
        print(f"  Loaded overrides for: {list(overrides.keys())}")
        return overrides
    return {}


# ---------------------------------------------------------------------------
# Compute Derived Variables
# ---------------------------------------------------------------------------

def compute_fiscal_metrics(iso3: str, debt, r, real_growth, inflation, pb) -> dict:
    """Compute g, r_g, pb_star, fiscal_gap for one country."""
    g = round(real_growth + inflation, 2)          # Nominal growth (approx)
    r_g = round(r - g, 2)                           # Interest-growth differential
    # Stabilising primary balance: pb* = (r - g) / 100 * debt
    pb_star = round((r / 100 - g / 100) * debt, 2)
    fiscal_gap = round(pb - pb_star, 2)
    return {
        "name": COUNTRY_NAMES[iso3],
        "iso3": iso3,
        "debt": round(debt, 1),
        "r": round(r, 2),
        "g": round(g, 2),
        "r_g": round(r_g, 2),
        "pb": round(pb, 2),
        "pb_star": round(pb_star, 2),
        "fiscal_gap": round(fiscal_gap, 2),
        "sustainable": fiscal_gap >= 0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    fred_api_key = os.environ.get("FRED_API_KEY")
    if not fred_api_key:
        print("ERROR: FRED_API_KEY environment variable not set.")
        print("Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html")
        sys.exit(1)

    print("=== Fetching FRED 10Y Yields ===")
    yields = fetch_fred_yields(fred_api_key)

    print("\n=== Fetching IMF DataMapper Data ===")
    imf = fetch_imf_data()

    print("\n=== Loading Overrides ===")
    overrides = load_overrides()

    print("\n=== Computing Fiscal Metrics ===")
    countries = []
    skipped = []

    for iso3 in COUNTRY_NAMES:
        debt = imf["debt"].get(iso3)
        r = yields.get(iso3)
        real_growth = imf["real_growth"].get(iso3)
        inflation = imf["inflation"].get(iso3)
        pb = imf["pb"].get(iso3)

        # Apply overrides
        if iso3 in overrides:
            ov = overrides[iso3]
            if "r" in ov:
                r = ov["r"]
                print(f"  Override: {iso3} r → {r}")
            if "g" in ov:
                # Override g directly → back-compute real_growth
                real_growth = ov["g"] - (inflation or 0)
            if "debt" in ov:
                debt = ov["debt"]
            if "pb" in ov:
                pb = ov["pb"]

        if any(v is None for v in [debt, r, real_growth, inflation, pb]):
            print(f"  SKIPPING {iso3}: missing data (debt={debt}, r={r}, growth={real_growth}, infl={inflation}, pb={pb})")
            skipped.append(iso3)
            continue

        metrics = compute_fiscal_metrics(iso3, debt, r, real_growth, inflation, pb)
        countries.append(metrics)
        print(f"  {metrics['name']:16s} | debt={metrics['debt']:6.1f}% | r={metrics['r']:5.2f}% | g={metrics['g']:5.2f}% | gap={metrics['fiscal_gap']:+.2f}%")

    # Sort by fiscal_gap descending (most sustainable first)
    countries.sort(key=lambda c: c["fiscal_gap"], reverse=True)

    # Build output
    fred_vintage = datetime.now().strftime("%Y-%m-%d")
    output = {
        "last_updated": str(date.today()),
        "data_vintage": f"IMF WEO Oct 2025 | FRED {fred_vintage}",
        "projection_year": PROJECTION_YEAR,
        "countries": countries,
    }

    if skipped:
        output["skipped"] = skipped
        print(f"\nWARNING: Skipped countries due to missing data: {skipped}")

    # Write JSON (used by http:// hosted version)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    # Write JS (used when opening file:// directly in browser — no fetch needed)
    js_content = (
        "// Auto-generated by scripts/fetch_data.py — do not edit manually.\n"
        "window.FISCAL_DATA = "
        + json.dumps(output, separators=(",", ":"))
        + ";\n"
    )
    with open(OUTPUT_JS_FILE, "w") as f:
        f.write(js_content)

    print(f"\n=== Done ===")
    print(f"Written {len(countries)} countries to {OUTPUT_FILE} and {OUTPUT_JS_FILE}")
    print(f"Sorted order: {' → '.join(c['name'] for c in countries)}")


if __name__ == "__main__":
    main()
