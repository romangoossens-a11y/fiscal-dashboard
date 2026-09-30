"""Monthly 10Y yields from FRED.

The FRED API needs a key. The public CSV endpoint behind the FRED charts does
not, so it serves as the fallback, and as the only source when running
locally without a key.
"""

import csv
import io

from . import http
from .config import FRED_API, FRED_CSV


def parse_api(payload):
    """Return [(month, value)] from a FRED API observations response."""
    out = []
    for obs in payload.get("observations", []):
        value = obs.get("value")
        if value in (None, "", "."):
            continue
        out.append((obs["date"][:7], float(value)))
    return sorted(out)


def parse_csv(text):
    """Return [(month, value)] from a fredgraph.csv download."""
    rows = list(csv.reader(io.StringIO(text)))
    out = []
    for row in rows[1:]:
        if len(row) < 2 or row[1] in ("", "."):
            continue
        out.append((row[0][:7], float(row[1])))
    return sorted(out)


def fetch_monthly(series_id, api_key=None):
    """Return (observations, source label) for one monthly FRED series.

    Tries the API first when a key is available, then the CSV endpoint.
    Raises if both fail or both return nothing.
    """
    errors = []
    if api_key:
        try:
            resp = http.get(FRED_API, params={
                "series_id": series_id, "api_key": api_key,
                "file_type": "json", "observation_start": "2015-01-01",
            })
            obs = parse_api(resp.json())
            if obs:
                return obs, "FRED API"
            errors.append("API returned no observations")
        except Exception as exc:  # noqa: BLE001, any failure means try the fallback
            errors.append(f"API: {type(exc).__name__}")
    try:
        resp = http.get(FRED_CSV, params={"id": series_id})
        obs = parse_csv(resp.text)
        if obs:
            # "FRED CSV" alone means the API was tried and failed.
            return obs, "FRED CSV" if api_key else "FRED CSV (no API key)"
        errors.append("CSV returned no observations")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CSV: {type(exc).__name__}")
    raise RuntimeError(f"{series_id}: " + "; ".join(errors))


def value_for_month(obs, month):
    """Value for a given 'YYYY-MM', or None."""
    for m, v in obs:
        if m == month:
            return v
    return None
