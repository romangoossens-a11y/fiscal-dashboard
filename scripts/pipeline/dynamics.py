"""Comparison snapshots and IMF revisions for the dashboard.

comparisons: the history entries the page compares today's table with, for
    1M, 6M, 1Y and "since the last IMF release". The page splits each change
    in the fiscal gap into rates, real growth, GDP deflator and fiscal stance,
    using decompose() below (mirrored in assets/app.js).

revisions: how the IMF changed its view between its two latest releases, for
    the same calendar year. The primary balance is compared as a level. Debt
    is compared on its projected change (slope) from last year to four years
    ahead, so statistical rebases of the level do not read as better or worse
    dynamics.
"""

from datetime import date

from itertools import combinations
from math import factorial

from . import vintages
from .compute import fiscal_gap
from .config import COUNTRIES, LARGE_IMF_REVISION
from .validate import debt_revision_note

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


# Players in the decomposition and the inputs each one moves.
DRIVERS = {
    "rates": ("r",),
    "real_growth": ("real_growth",),
    "deflator": ("deflator",),
    "fiscal": ("pb", "debt"),
}


def decompose(then, now):
    """Split the change in fiscal gap into four contributions that sum exactly.

    The gap is pb - (r - g) / (1 + g) x debt / 100, which is not linear in its
    inputs, so each driver gets its Shapley value: the average effect of
    switching its inputs from then to now, over every order in which the
    other drivers could be switched. Mirrored in assets/app.js.
    """
    keys = list(DRIVERS)
    n = len(keys)

    def gap_with(moved):
        x = dict(then)
        for k in moved:
            for field in DRIVERS[k]:
                x[field] = now[field]
        return fiscal_gap(x["r"], x["real_growth"], x["deflator"], x["pb"], x["debt"])

    parts = {}
    for k in keys:
        others = [o for o in keys if o != k]
        total = 0.0
        for size in range(n):
            weight = factorial(size) * factorial(n - size - 1) / factorial(n)
            for subset in combinations(others, size):
                total += weight * (gap_with(subset + (k,)) - gap_with(subset))
        parts[k] = total
    parts["net"] = gap_with(tuple(keys)) - gap_with(())
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
            "debt_level_change": diff(v(label, iso, "debt", base), v(prior, iso, "debt", base)),
            "debt_level_note": debt_level_note(archive, label, prior, iso, base),
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


def imf_debt_paths(archive, label, from_year):
    """The IMF's own debt projection per country, for the trajectory chart."""
    out = {}
    for iso in COUNTRIES:
        years = (archive["vintages"].get(label or "", {}).get("data", {})
                 .get(iso, {}).get("debt", {}))
        path = {y: v for y, v in sorted(years.items()) if int(y) >= from_year}
        if path:
            out[iso] = path
    return out


def imf_bridge(archive, label, forecast_year):
    """Inputs to explain the gap between the simple projection and the IMF
    debt path in the forecast year: IMF debt, net interest and nominal GDP
    growth. The page combines them with the current r and g."""
    out = {}

    def v(iso, field, year):
        return vintages.value(archive, label, iso, field, year)

    for iso in COUNTRIES:
        debt = v(iso, "debt", forecast_year)
        pb, overall = v(iso, "pb", forecast_year), v(iso, "overall_balance", forecast_year)
        gdp, gdp_prev = v(iso, "ngdp", forecast_year), v(iso, "ngdp", forecast_year - 1)
        if None in (debt, pb, overall, gdp, gdp_prev) or not gdp_prev:
            continue
        out[iso] = {
            "year": forecast_year,
            "imf_debt": debt,
            "net_interest": round(pb - overall, 3),
            "nominal_growth": round((gdp / gdp_prev - 1) * 100, 3),
        }
    return out


def debt_level_note(archive, label, prior, iso, year):
    old, new = vintages.value(archive, prior, iso, "debt", year), vintages.value(archive, label, iso, "debt", year)
    if old is None or new is None or abs(new - old) < LARGE_IMF_REVISION["debt"]:
        return None
    old_h, new_h = (vintages.value(archive, prior, iso, "debt", year - 1),
                    vintages.value(archive, label, iso, "debt", year - 1))
    hist = None if old_h is None or new_h is None else new_h - old_h
    return debt_revision_note(new - old, hist, year, year - 1,
                              vintages.human(prior), vintages.human(label))


def effective_rate(net_interest, nominal_growth, debt_prev):
    """Average interest rate on the debt stock, % per year.

    Net interest paid in year t (% of GDP_t) divided by debt at the end of
    t-1 (% of GDP_(t-1)), rescaled by nominal growth so both sit on the same
    GDP: i = interest_t x (1 + g) / d_(t-1).
    """
    if None in (net_interest, nominal_growth, debt_prev) or not debt_prev:
        return None
    return round(net_interest * (1 + nominal_growth / 100) / debt_prev * 100, 3)


def attach(output, history, archive, run_date: date):
    label = output["imf"]["vintage"]
    output["comparisons"] = comparisons(history, run_date, archive, label)
    output["revisions"] = revisions(archive, label, output["projection_year"])
    output["imf_debt_paths"] = imf_debt_paths(archive, label, output["debt_year"])
    output["imf_bridge"] = imf_bridge(archive, label, output["projection_year"])
    for c in output["countries"]:
        b = output["imf_bridge"].get(c["iso3"], {})
        c["r_eff"] = effective_rate(b.get("net_interest"), b.get("nominal_growth"), c.get("debt"))
    return output
