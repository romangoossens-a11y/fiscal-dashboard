"""Snapshot history, so the dashboard can show change over 1M, 6M and 1Y.

Each entry stores the inputs and the resulting fiscal gap per country:
    {"date": "2026-09-30", "kind": "live" | "reconstructed",
     "imf_vintage": "Apr2026", "target_year": 2026,
     "countries": {iso: {"r", "r_month", "real_growth", "deflator",
                         "pb", "debt", "fiscal_gap"}}}

Debt is at the end of the year before target_year, like the live table.

"live" entries are written by the weekly run. "reconstructed" entries were
rebuilt by scripts/backfill.py from FRED and archived IMF releases, one per
month end, using the previous month's average yield.
"""

import json

from .config import HISTORY_FILE

KEYS = ("r", "r_month", "real_growth", "deflator", "pb", "debt", "fiscal_gap")


def load(path=HISTORY_FILE):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"entries": []}


def save(history, path=HISTORY_FILE):
    history["entries"].sort(key=lambda e: e["date"])
    # One entry per line keeps weekly diffs readable.
    lines = [json.dumps(e, separators=(",", ":")) for e in history["entries"]]
    body = ",\n  ".join(lines)
    path.write_text('{"entries": [\n  ' + body + "\n]}\n", encoding="utf-8")


def make_entry(run_date, kind, imf_vintage, target_year, countries):
    return {
        "date": run_date.isoformat(),
        "kind": kind,
        "imf_vintage": imf_vintage,
        "target_year": target_year,
        "debt_year": target_year - 1,
        "countries": {c["iso3"]: {k: c.get(k) for k in KEYS} for c in countries},
    }


def upsert(history, entry):
    """Add an entry, replacing any existing one for the same date."""
    history["entries"] = [e for e in history["entries"] if e["date"] != entry["date"]]
    history["entries"].append(entry)
