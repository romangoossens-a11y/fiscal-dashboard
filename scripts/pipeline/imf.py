"""IMF WEO data: the SDMX API first, DataMapper as fallback.

Both return the same shape, {iso: {field: {"YYYY": value}}}, with years as
strings so the structure round trips through JSON unchanged.

The SDMX API at api.imf.org needs no key. It serves the current release as
the "WEO" dataflow and, from October 2025 onwards, each superseded release as
its own "WEO_<year>_<MON>_VINTAGE" dataflow. It does not state which release
the current dataflow is, so vintages.py works that out.
"""

from . import http
from .config import (AUX_INDICATORS, COUNTRIES, DATAMAPPER_BASE, DATAMAPPER_INDICATORS,
                     SDMX_AGENCY, SDMX_BASE, SDMX_CURRENT_FLOW, SDMX_INDICATORS)


def parse_sdmx(payload, indicator_to_field):
    """Turn one SDMX JSON data response into {iso: {field: {year: value}}}.

    Observations are stored against integer positions, so the dimension value
    lists are indexed back to recover country, indicator and year.
    """
    out = {}
    structures = payload["data"]["structures"][0]
    dims = structures["dimensions"]
    order = [d["id"] for d in dims["series"]]
    values = {d["id"]: [v["id"] for v in d["values"]] for d in dims["series"]}
    years = [v["value"] for v in dims["observation"][0]["values"]]
    for dataset in payload["data"]["dataSets"]:
        for key, series in dataset.get("series", {}).items():
            pos = [int(p) for p in key.split(":")]
            labels = {dim: values[dim][pos[i]] for i, dim in enumerate(order)}
            field = indicator_to_field.get(labels.get("INDICATOR"))
            iso = labels.get("COUNTRY")
            if field is None or iso is None:
                continue
            for idx, obs in series.get("observations", {}).items():
                if obs is None or obs[0] in (None, ""):
                    continue
                year = str(years[int(idx)])[:4]
                out.setdefault(iso, {}).setdefault(field, {})[year] = round(float(obs[0]), 3)
    return out


def fetch_sdmx(dataflow=SDMX_CURRENT_FLOW, countries=COUNTRIES):
    """Fetch all four fields for one WEO dataflow. One call per indicator,
    because the API handles a single indicator filter more reliably."""
    out = {}
    for field, code in {**SDMX_INDICATORS, **AUX_INDICATORS}.items():
        url = f"{SDMX_BASE}/data/dataflow/{SDMX_AGENCY}/{dataflow}/+/*"
        resp = http.get(url, params={"c[COUNTRY]": ",".join(countries),
                                     "c[INDICATOR]": code}, timeout=120)
        part = parse_sdmx(resp.json(), {code: field})
        for iso, fields in part.items():
            out.setdefault(iso, {}).update(fields)
    if not out:
        raise RuntimeError(f"SDMX {dataflow} returned no data")
    return out


def list_vintage_flows():
    """Ids of the archived WEO release dataflows, for example WEO_2025_OCT_VINTAGE."""
    resp = http.get(f"{SDMX_BASE}/structure/dataflow/{SDMX_AGENCY}", timeout=90)
    return sorted(f["id"] for f in resp.json()["data"]["dataflows"]
                  if f["id"].startswith("WEO_") and f["id"].endswith("_VINTAGE"))


def parse_datamapper(payload, code, field, out):
    for iso, years in payload.get("values", {}).get(code, {}).items():
        for year, value in years.items():
            if value is not None:
                out.setdefault(iso, {}).setdefault(field, {})[str(year)] = round(float(value), 3)


def fetch_datamapper(countries=COUNTRIES):
    """Fetch all four fields from DataMapper. Values there are rounded to one
    decimal, so they are never used to detect a new release."""
    out = {}
    for field, code in DATAMAPPER_INDICATORS.items():
        resp = http.get(f"{DATAMAPPER_BASE}/{code}/{'/'.join(countries)}", timeout=60)
        parse_datamapper(resp.json(), code, field, out)
    if not out:
        raise RuntimeError("DataMapper returned no data")
    return out
