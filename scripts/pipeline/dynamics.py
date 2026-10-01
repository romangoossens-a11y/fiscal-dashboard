"""Comparison snapshots and IMF revisions for the dashboard.

comparisons: the history entries the page compares today's table with, for
    1M, 6M, 1Y and "since the last IMF release". The page splits each change
    in the fiscal gap into rates, real growth, inflation and fiscal stance,
    using decompose() below (mirrored in assets/app.js).

revisions: how the IMF changed its view between its two latest releases, for
    the same calendar year. The primary balance is compared as a level. Debt
    is compared on its projected change (slope) from last year to four years
    ahead, so statistical rebases of the level do not read as better or worse
    dynamics.
"""

from datetime import date

from . import vintages
from .config import COUNTRIES

PERIODS = (("1M", 1), ("6M", 6), ("1Y", 12))

# Thresholds for the verdict chip. Smaller revisions count as unchanged.
PB_THRESHOLD = 0.2      # pp of GDP
SLOPE_THRESHOLD = 1.0   # pp of GDP over the slope horizon
SLOPE_YEARS_AHEAD = 4


def months_before(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) - n
    y, m = idx // 12, idx % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def nearest(entries, target: date, max_days=20):
    """Entry closest to target, the earlier one on a tie. None if all are far."""
    best, best_gap = None, None
    for e in entries:
        gap = abs((date.fromisoformat(e["date"]) - target).days)
        if gap <= max_days and (best is None or gap < best_gap):
            best, best_gap = e, gap
    return best


def latest_before(entries, cutoff: date):
    best = None
    for e in entries:
        if e["date"] < cutoff.isoformat() and (best is None or e["date"] > best["date"]):
            best = e
    return best


def comparisons(history, run_date: date, archive, current_label):
    """Reference snapshots keyed by period. Entries for run_date are excluded."""
    entries = [e for e in history["entries"] if e["date"] < run_date.isoformat()]
    out = {}
    for key, n in PERIODS:
        ref = nearest(entries, months_before(run_date, n))
        if ref:
            out[key] = ref
    release = archive["vintages"].get(current_label or "", {}).get("release_date")
    if release:
        ref = latest_before(entries, date.fromisoformat(release))
        if ref:
            out["IMF"] = ref
    return out


def decompose(then, now):
    """Split the change in fiscal gap into four contributions that sum exactly.

    gap = pb - (r - g) x debt / 100, with g = real growth + inflation.
    Midpoint weights make the split exact:
      rates       = -mean(debt) x change in r / 100
      real growth =  mean(debt) x change in real growth / 100
      inflation   =  mean(debt) x change in inflation / 100
      fiscal      =  change in pb - mean(r - g) x change in debt / 100
    """
    def gap(x):
        return x["pb"] - (x["r"] - x["real_growth"] - x["inflation"]) * x["debt"] / 100

    d = (then["debt"] + now["debt"]) / 2
    rg = ((then["r"] - then["real_growth"] - then["inflation"])
          + (now["r"] - now["real_growth"] - now["inflation"])) / 2
    parts = {
        "rates": -d * (now["r"] - then["r"]) / 100,
        "real_growth": d * (now["real_growth"] - then["real_growth"]) / 100,
        "inflation": d * (now["inflation"] - then["inflation"]) / 100,
        "fiscal": (now["pb"] - then["pb"]) - rg * (now["debt"] - then["debt"]) / 100,
    }
    parts["net"] = gap(now) - gap(then)
    return parts


def verdict(pb_change, slope_change):
    better = (pb_change is not None and pb_change > PB_THRESHOLD,
              slope_change is not None and slope_change < -SLOPE_THRESHOLD)
    worse = (pb_change is not None and pb_change < -PB_THRESHOLD,
             slope_change is not None and slope_change > SLOPE_THRESHOLD)
    if any(better) and any(worse):
        return "mixed"
    if any(better):
        return "improving"
    if any(worse):
        return "deteriorating"
    return "unchanged"


def revisions(archive, label, target_year):
    """IMF view of target_year in the current release versus the previous one."""
    if not label or label not in archive["vintages"]:
        return None
    prior = vintages.previous(archive, label)
    if not prior:
        return None
    base, end = target_year - 1, target_year + SLOPE_YEARS_AHEAD

    def v(lab, iso, field, year):
        return vintages.value(archive, lab, iso, field, year)

    def diff(a, b):
        return None if a is None or b is None else round(a - b, 3)

    countries = {}
    for iso in COUNTRIES:
        pb_old, pb_new = v(prior, iso, "pb", target_year), v(label, iso, "pb", target_year)
        slope_old = diff(v(prior, iso, "debt", end), v(prior, iso, "debt", base))
        slope_new = diff(v(label, iso, "debt", end), v(label, iso, "debt", base))
        pb_change, slope_change = diff(pb_new, pb_old), diff(slope_new, slope_old)
        countries[iso] = {
            "pb_old": pb_old, "pb_new": pb_new, "pb_change": pb_change,
            "debt_slope_old": slope_old, "debt_slope_new": slope_new,
            "debt_slope_change": slope_change,
            "debt_level_change": diff(v(label, iso, "debt", target_year),
                                      v(prior, iso, "debt", target_year)),
            "verdict": verdict(pb_change, slope_change),
        }
    return {
        "current": label,
        "current_label": vintages.human(label),
        "previous": prior,
        "previous_label": vintages.human(prior),
        "target_year": target_year,
        "slope_from": base,
        "slope_to": end,
        "thresholds": {"pb": PB_THRESHOLD, "debt_slope": SLOPE_THRESHOLD},
        "countries": countries,
    }


def attach(output, history, archive, run_date: date):
    label = output["imf"]["vintage"]
    output["comparisons"] = comparisons(history, run_date, archive, label)
    output["revisions"] = revisions(archive, label, output["projection_year"])
    return output
