"""One pipeline run: fetch, validate, carry forward, compute, assemble.

The sources are passed in as functions so tests can run the whole thing
offline. build() never raises on a data problem. A value that cannot be
refreshed is carried forward from the previous output and flagged.
"""

from collections import Counter
from datetime import date

from . import compute, validate, vintages
from .config import (COUNTRY_NAMES, IMF_FIELDS, SCHEMA_VERSION, VALID_RANGES, YIELD_SERIES,
                     field_year)
from .validate import CARRIED_FORWARD, flag, month_label


def _reason(exc):
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}"[:160] if text else type(exc).__name__


def _carry_flag(field, reason, prev_country, published_on):
    """Flag for a carried forward value, keeping the original 'since' date."""
    since = published_on
    for f in prev_country.get("flags", []):
        if f.get("field") == field and f.get("kind") == CARRIED_FORWARD and f.get("since"):
            since = f["since"]
    out = flag(field, CARRIED_FORWARD,
               f"Not refreshed ({reason}). Showing the value published on {since}")
    out["since"] = since
    return out


def fetch_yields(run_date, fetch_yield, previous, published_on, status):
    """Latest monthly 10Y yield per country, with flags."""
    out, csv_fallback = {}, []
    for iso, series in YIELD_SERIES.items():
        prev = previous.get(iso, {})
        flags = []
        try:
            obs, source = fetch_yield(series)
            month, r = obs[-1]
            if not validate.in_range("r", r):
                raise ValueError(f"value {r} outside {VALID_RANGES['r']}")
            if source == "FRED CSV":
                csv_fallback.append(iso)
            source = f"{source} {series}"
        except Exception as exc:  # noqa: BLE001, any failure is carried forward
            if prev.get("r") is None:
                status.append(f"{COUNTRY_NAMES[iso]}: no 10Y yield available ({_reason(exc)})")
                out[iso] = None
                continue
            r, month = prev["r"], prev.get("r_month")
            source = prev.get("r_source", "previous run")
            flags.append(_carry_flag("r", _reason(exc), prev, published_on))
        if month:
            lag = validate.yield_lag_flag(month, run_date)
            if lag:
                flags.append(lag)
            move = validate.yield_move_flag(r, month, prev.get("r"), prev.get("r_month"))
            if move:
                flags.append(move)
        out[iso] = {"r": r, "r_month": month, "r_source": source, "flags": flags}
    if csv_fallback:
        status.append("FRED API unavailable, public CSV used for " + ", ".join(csv_fallback))
    return out


def fetch_imf(run_date, fetch_sdmx, fetch_datamapper, archive, status):
    """Return (data, source, release label, release status)."""
    try:
        data = fetch_sdmx()
        label, vstatus = vintages.register(archive, data, run_date, "IMF SDMX API, WEO dataflow")
        if vstatus == "new":
            status.append(f"New IMF release detected and archived: WEO {vintages.human(label)}")
        elif vstatus == "revised":
            status.append(f"IMF data changed within the WEO {vintages.human(label)} release window, archive updated")
        return data, "IMF SDMX API", label, vstatus
    except Exception as exc:  # noqa: BLE001
        sdmx_error = _reason(exc)
    label = vintages.latest(archive)
    try:
        data = fetch_datamapper()
        status.append(f"IMF SDMX API unavailable ({sdmx_error}). Used DataMapper, "
                      f"release assumed to be WEO {vintages.human(label) if label else 'unknown'}")
        return data, "IMF DataMapper (fallback)", label, "unverified"
    except Exception as exc:  # noqa: BLE001
        status.append(f"IMF sources unavailable (SDMX {sdmx_error}, DataMapper {_reason(exc)}). "
                      f"Using the archived WEO {vintages.human(label) if label else ''} release")
        return {}, "IMF release archive (fallback)", label, "archive"


def imf_values(iso, data, label, target, archive, prev, published_on):
    """The four IMF fields for one country, with carry forward and flags."""
    values, flags = {}, []
    for field in IMF_FIELDS:
        year = field_year(field, target)
        v = data.get(iso, {}).get(field, {}).get(str(year))
        if validate.in_range(field, v):
            values[field] = v
            continue
        archived = vintages.value(archive, label, iso, field, year)
        if validate.in_range(field, archived):
            values[field] = archived
            if data:
                flags.append(flag(field, CARRIED_FORWARD,
                                  f"{year} value missing from the live IMF source, "
                                  f"taken from the archived WEO {vintages.human(label)} release"))
        elif prev.get(field) is not None:
            values[field] = prev[field]
            flags.append(_carry_flag(field, f"no {year} IMF value", prev, published_on))
        else:
            values[field] = None
    prior = vintages.previous(archive, label) if label in archive["vintages"] else None
    if prior:
        for field in IMF_FIELDS:
            f = validate.revision_flag(field, values[field],
                                       vintages.value(archive, prior, iso, field,
                                                      field_year(field, target)),
                                       vintages.human(prior))
            if f:
                flags.append(f)
    return values, flags


def apply_override(iso, row, overrides, status):
    ov = overrides.get(iso)
    if not ov:
        return
    for field in ("r", "debt", "pb", "real_growth", "inflation"):
        if field in ov:
            row[field] = ov[field]
    if "g" in ov:
        row["real_growth"] = ov["g"] - (row["inflation"] or 0)
    status.append(f"{COUNTRY_NAMES[iso]}: manual override applied ({', '.join(sorted(ov))})")


def build(run_date: date, fetch_yield, fetch_sdmx, fetch_datamapper,
          previous_output, archive, overrides=None):
    """Assemble the output dictionary. Mutates the archive if a release is new."""
    overrides = overrides or {}
    status = []
    previous = {c["iso3"]: c for c in (previous_output or {}).get("countries", [])}
    published_on = (previous_output or {}).get("last_updated", "the previous run")
    target = run_date.year

    yields = fetch_yields(run_date, fetch_yield, previous, published_on, status)
    data, imf_source, label, vstatus = fetch_imf(run_date, fetch_sdmx, fetch_datamapper,
                                                 archive, status)

    countries, skipped = [], []
    for iso in COUNTRY_NAMES:
        prev = previous.get(iso, {})
        y = yields.get(iso)
        values, imf_flags = imf_values(iso, data, label, target, archive, prev, published_on)
        row = dict(values, r=y["r"] if y else None)
        apply_override(iso, row, overrides, status)
        if any(row[k] is None for k in ("r", *IMF_FIELDS)):
            skipped.append(iso)
            continue
        c = compute.compute_country(iso, row["debt"], row["r"], row["real_growth"],
                                    row["inflation"], row["pb"])
        c["r_month"] = y["r_month"]
        c["r_source"] = y["r_source"]
        c["flags"] = y["flags"] + imf_flags
        countries.append(c)

    countries.sort(key=lambda c: c["fiscal_gap"], reverse=True)

    for c in countries:
        for f in c["flags"]:
            if f["kind"] in (CARRIED_FORWARD, validate.LAGGING):
                status.append(f"{c['name']} {f['field']}: {f['message']}")

    months = Counter(c["r_month"] for c in countries if c["r_month"])
    latest_month = max(months) if months else None
    typical_month = months.most_common(1)[0][0] if months else None
    release = f"IMF WEO {vintages.human(label)}" if label else "IMF WEO"
    yields_text = (f"10Y yields: monthly averages, {month_label(typical_month)}"
                   if typical_month else "10Y yields: monthly averages")

    output = {
        "schema_version": SCHEMA_VERSION,
        "last_updated": run_date.isoformat(),
        "data_vintage": f"{release} | {yields_text}",
        "projection_year": target,
        "debt_year": field_year("debt", target),
        "imf": {
            "vintage": label,
            "vintage_label": vintages.human(label) if label else None,
            "release_status": vstatus,
            "source": imf_source,
            "target_year": target,
        },
        "yields": {
            "definition": "Monthly average 10Y government bond yield. US: FRED GS10. "
                          "Others: OECD long term interest rates via FRED.",
            "latest_month": latest_month,
            "typical_month": typical_month,
        },
        "data_status": status,
        "countries": countries,
    }
    if skipped:
        output["skipped"] = skipped
    return output
