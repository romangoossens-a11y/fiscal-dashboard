"""
One-off backfill of the IMF release archive and the snapshot history.
=====================================================================
Run locally, not in CI, because the older WEO releases exist only as files
downloaded from imf.org through a browser (imf.org refuses scripts).

    python scripts/backfill.py --weo-dir PATH_TO_WEO_FILES

1. IMF archive. April 2019 to April 2025 are read from the weo{apr,oct}YYYYall.xls
   files in --weo-dir. October 2025 comes from its SDMX vintage dataflow and
   the current release from the SDMX "WEO" dataflow, the same source the weekly
   run uses, so the next run recognises it as unchanged.

2. History. One "reconstructed" entry per month end from --start to the last
   month end before today. Each uses the previous month's average yield, the
   IMF release in force on that date and that year's fundamentals, which is
   what the dashboard would have shown with a normal publication lag.
   Existing live entries are kept.
"""

import argparse
import csv
import io
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import compute, fred, history, imf, vintages  # noqa: E402
from pipeline.config import (COUNTRIES, SDMX_INDICATORS, WEO_RELEASE_DATES,  # noqa: E402
                             YIELD_SERIES, field_year)
from pipeline.validate import add_months  # noqa: E402

CODE_TO_FIELD = {code: field for field, code in SDMX_INDICATORS.items()}


def read_weo_tsv(path):
    """Parse one WEO .xls file (really tab separated text) into archive shape."""
    raw = path.read_bytes()
    encoding = "utf-16-le" if raw[:200].count(b"\x00") > 20 else "latin-1"
    text = raw.decode(encoding, errors="replace").lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    header = [h.strip() for h in rows[0]]
    iso_col = header.index("ISO")
    sub_col = header.index("WEO Subject Code")
    years = {i: h for i, h in enumerate(header) if re.fullmatch(r"\d{4}", h)}
    out = {}
    for row in rows[1:]:
        if len(row) <= max(iso_col, sub_col):
            continue
        iso, field = row[iso_col].strip(), CODE_TO_FIELD.get(row[sub_col].strip())
        if iso not in COUNTRIES or field is None:
            continue
        for i, year in years.items():
            if i >= len(row):
                continue
            cell = row[i].strip().replace(",", "")
            if cell in ("", "n/a", "--", "NA"):
                continue
            try:
                out.setdefault(iso, {}).setdefault(field, {})[year] = round(float(cell), 3)
            except ValueError:
                continue
    return out


def build_archive(weo_dir):
    archive = {"vintages": {}}
    for path in sorted(weo_dir.glob("weo*all.xls")):
        m = re.fullmatch(r"weo(apr|oct)(\d{4})all\.xls", path.name, re.I)
        if not m:
            continue
        label = m.group(1).capitalize() + m.group(2)
        data = read_weo_tsv(path)
        archive["vintages"][label] = {
            "release_date": WEO_RELEASE_DATES[label],
            "source": f"WEO database file {path.name}",
            "data": vintages.window(data, vintages.vintage_year(label)),
        }
        print(f"  {label}: {sum(len(f) for f in data.values())} series from {path.name}")

    flows = imf.list_vintage_flows()
    for flow in flows:
        m = re.fullmatch(r"WEO_(\d{4})_(APR|OCT)_VINTAGE", flow)
        label = m.group(2).capitalize() + m.group(1)
        if label in archive["vintages"]:
            continue
        data = imf.fetch_sdmx(flow)
        archive["vintages"][label] = {
            "release_date": WEO_RELEASE_DATES[label],
            "source": f"IMF SDMX API, {flow} dataflow",
            "data": vintages.window(data, vintages.vintage_year(label)),
        }
        print(f"  {label}: from SDMX {flow}")

    # The current release. Its label follows the latest archived one.
    current = imf.fetch_sdmx()
    last = vintages.latest(archive)
    nxt = f"Oct{vintages.vintage_year(last)}" if last.startswith("Apr") else f"Apr{vintages.vintage_year(last) + 1}"
    archive["vintages"][nxt] = {
        "release_date": WEO_RELEASE_DATES.get(nxt, date.today().isoformat()),
        "source": "IMF SDMX API, WEO dataflow",
        "data": vintages.window(current, vintages.vintage_year(nxt)),
    }
    print(f"  {nxt}: current SDMX WEO dataflow")
    return archive


def month_ends(start_month, end_date):
    """Last day of each month from start_month up to end_date."""
    y, m = (int(p) for p in start_month.split("-"))
    while True:
        first_next = date(y + (m == 12), m % 12 + 1, 1)
        last = first_next - timedelta(days=1)
        if last > end_date:
            return
        yield last
        y, m = first_next.year, first_next.month


def reconstruct(archive, hist, start_month, end_date):
    yields = {iso: dict(fred.fetch_monthly(series)[0]) for iso, series in YIELD_SERIES.items()}
    added = 0
    for d in month_ends(start_month, end_date):
        label = vintages.in_force(archive, d)
        if label is None:
            continue
        month = add_months(f"{d.year:04d}-{d.month:02d}", -1)
        countries, borrowed = [], set()
        for iso in COUNTRIES:
            vals = {}
            for f in SDMX_INDICATORS:
                # The April 2020 release carried no fiscal series, so a missing
                # field falls back to the most recent earlier release.
                year = field_year(f, d.year)
                src = label
                while src and vintages.value(archive, src, iso, f, year) is None:
                    src = vintages.previous(archive, src)
                vals[f] = vintages.value(archive, src, iso, f, year)
                if src and src != label:
                    borrowed.add((f, src))
            r = yields[iso].get(month)
            if r is None or any(v is None for v in vals.values()):
                continue
            c = compute.compute_country(iso, vals["debt"], r, vals["real_growth"],
                                        vals["inflation"], vals["pb"])
            c["r_month"] = month
            countries.append(c)
        if countries:
            if any(e["date"] == d.isoformat() and e["kind"] == "live" for e in hist["entries"]):
                continue
            entry = history.make_entry(d, "reconstructed", label, d.year, countries)
            if borrowed:
                entry["notes"] = [f"{f} from the {vintages.human(src)} release, missing in "
                                  f"{vintages.human(label)}" for f, src in sorted(borrowed)]
            history.upsert(hist, entry)
            added += 1
    return added


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--weo-dir", type=Path, help="needed unless --history-only")
    ap.add_argument("--start", default="2019-05", help="first month end, YYYY-MM")
    ap.add_argument("--history-only", action="store_true",
                    help="keep the existing IMF archive, rebuild only the history")
    ap.add_argument("--fresh-history", action="store_true",
                    help="discard existing history entries, live ones included")
    args = ap.parse_args()

    if args.history_only:
        archive = vintages.load()
    else:
        if not args.weo_dir:
            ap.error("--weo-dir is required unless --history-only")
        print("Building IMF release archive")
        archive = build_archive(args.weo_dir)
        vintages.save(archive)

    print("Reconstructing monthly history")
    hist = {"entries": []} if args.fresh_history else history.load()
    last_month_end = date.today().replace(day=1) - timedelta(days=1)
    n = reconstruct(archive, hist, args.start, last_month_end)
    history.save(hist)
    print(f"  {n} reconstructed entries, {len(hist['entries'])} in total")


if __name__ == "__main__":
    main()
