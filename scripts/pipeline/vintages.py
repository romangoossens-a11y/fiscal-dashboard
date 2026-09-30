"""Archive of IMF WEO releases, and detection of new ones.

The IMF APIs serve only the latest release and do not say which one it is.
Each run therefore compares what the SDMX API returns with the latest release
in the archive. Identical data means the same release. Different data means
a new release, labelled by the IMF calendar: April releases cover April to
September, October releases cover October to March.

Archive layout (data/imf_vintages.json):
    {"vintages": {"Apr2026": {"release_date": "2026-04-14",
                              "source": "...",
                              "data": {iso: {field: {"2026": value}}}}}}
"""

import json
from datetime import date

from .config import VINTAGE_YEARS_AFTER, VINTAGE_YEARS_BEFORE, VINTAGES_FILE

MONTH_NAMES = {"Apr": "April", "Oct": "October"}
TOLERANCE = 0.0005


def load(path=VINTAGES_FILE):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"vintages": {}}


def save(archive, path=VINTAGES_FILE):
    archive["vintages"] = dict(sorted(archive["vintages"].items(),
                                      key=lambda kv: kv[1]["release_date"]))
    path.write_text(json.dumps(archive, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def vintage_year(label):
    return int(label[3:])


def human(label):
    """'Apr2026' -> 'April 2026'."""
    return f"{MONTH_NAMES.get(label[:3], label[:3])} {label[3:]}"


def window(data, year):
    """Keep only the years stored per release."""
    lo, hi = year - VINTAGE_YEARS_BEFORE, year + VINTAGE_YEARS_AFTER
    return {iso: {f: {y: v for y, v in ys.items() if lo <= int(y) <= hi}
                  for f, ys in fields.items()}
            for iso, fields in data.items()}


def ordered(archive):
    return sorted(archive["vintages"], key=lambda k: archive["vintages"][k]["release_date"])


def latest(archive):
    labels = ordered(archive)
    return labels[-1] if labels else None


def in_force(archive, on_date):
    """Label of the release that was current on a given date, or None."""
    current = None
    for label in ordered(archive):
        if archive["vintages"][label]["release_date"] <= on_date.isoformat():
            current = label
    return current


def previous(archive, label):
    labels = ordered(archive)
    i = labels.index(label)
    return labels[i - 1] if i > 0 else None


def label_for(run_date):
    """Release a newly seen dataset belongs to, by the IMF calendar."""
    if run_date.month >= 10:
        return f"Oct{run_date.year}"
    if run_date.month >= 4:
        return f"Apr{run_date.year}"
    return f"Oct{run_date.year - 1}"


def same_data(new, old):
    """True if every value present in both agrees, and at least one is shared."""
    shared = 0
    for iso, fields in old.items():
        for field, years in fields.items():
            for year, value in years.items():
                other = new.get(iso, {}).get(field, {}).get(year)
                if other is None:
                    continue
                shared += 1
                if abs(other - value) > TOLERANCE:
                    return False
    return shared > 0


def register(archive, data, run_date: date, source):
    """Match live SDMX data to a release, adding it to the archive if new.

    Returns (label, status) where status is 'unchanged', 'new' or 'revised'.
    'revised' means the data changed inside a release window, which the IMF
    occasionally does for corrections.
    """
    last = latest(archive)
    if last and same_data(data, archive["vintages"][last]["data"]):
        return last, "unchanged"
    label = label_for(run_date)
    entry = {
        "release_date": run_date.isoformat(),
        "source": source,
        "data": window(data, vintage_year(label)),
    }
    if label in archive["vintages"]:
        entry["release_date"] = archive["vintages"][label]["release_date"]
        entry["revised_on"] = run_date.isoformat()
        archive["vintages"][label] = entry
        return label, "revised"
    archive["vintages"][label] = entry
    return label, "new"


def value(archive, label, iso, field, year):
    if not label:
        return None
    return (archive["vintages"].get(label, {}).get("data", {})
            .get(iso, {}).get(field, {}).get(str(year)))
