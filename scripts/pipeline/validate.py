"""Checks applied before anything is published, and the flags they raise.

Nothing here stops the run. A rejected value is replaced by the last good one
and flagged, so the reader can see which country is lagging and why.
"""

from datetime import date

from .config import LARGE_IMF_REVISION, LARGE_YIELD_MOVE, VALID_RANGES, YIELD_EXPECTED_DAY

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Flag kinds, most serious first. The front end colours by kind.
CARRIED_FORWARD = "carried_forward"
FALLBACK_SOURCE = "fallback_source"
LAGGING = "lagging"
LARGE_MOVE = "large_move"
LARGE_REVISION = "large_revision"


def flag(field, kind, message):
    return {"field": field, "kind": kind, "message": message}


def in_range(field, value):
    if value is None:
        return False
    lo, hi = VALID_RANGES[field]
    return lo <= value <= hi


def month_label(month):
    """'2026-08' -> 'Aug 2026'."""
    y, m = month.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def add_months(month, n):
    y, m = (int(p) for p in month.split("-"))
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def expected_yield_month(run_date: date):
    """Latest monthly average that should normally be out by run_date."""
    this_month = f"{run_date.year:04d}-{run_date.month:02d}"
    lag = 1 if run_date.day >= YIELD_EXPECTED_DAY else 2
    return add_months(this_month, -lag)


def yield_lag_flag(month, run_date):
    expected = expected_yield_month(run_date)
    if month < expected:
        return flag("r", LAGGING,
                    f"Latest monthly yield is {month_label(month)}, "
                    f"{month_label(expected)} not yet published")
    return None


def yield_move_flag(new_r, new_month, prev_r, prev_month):
    if prev_r is None or prev_month is None or new_month == prev_month:
        return None
    if abs(new_r - prev_r) > LARGE_YIELD_MOVE:
        return flag("r", LARGE_MOVE,
                    f"10Y yield moved {new_r - prev_r:+.2f} pp from "
                    f"{month_label(prev_month)} to {month_label(new_month)}, check")
    return None


def debt_revision_note(level_change, history_change, year, history_year, old_label, new_label):
    """Plain explanation of a large debt revision between two IMF releases.

    If an already published year moved by a similar amount, the IMF revised
    its historical data (often a GDP benchmark revision), not its outlook.
    """
    text = (f"Debt for {year} revised {level_change:+.1f} pp between the {old_label} "
            f"and {new_label} IMF releases.")
    if history_change is not None and abs(history_change) >= 0.5 * abs(level_change) \
            and history_change * level_change > 0:
        return text + (f" {history_year} was revised by {history_change:+.1f} pp too, so this "
                       f"reflects revised historical data, not a change in outlook.")
    return text + f" Past years barely moved, so this reflects a change in the IMF outlook."


def revision_flag(field, new, old, old_label, new_label=None, history=None):
    """Flag a large revision. history = (history_year, change) for debt."""
    if new is None or old is None:
        return None
    if abs(new - old) <= LARGE_IMF_REVISION[field]:
        return None
    if field == "debt" and history and new_label:
        return flag(field, LARGE_REVISION, debt_revision_note(
            new - old, history[1], history[2], history[0], old_label, new_label))
    return flag(field, LARGE_REVISION, f"Revised {new - old:+.1f} pp from the {old_label} IMF release")
