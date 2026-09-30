from datetime import date

import pytest

from pipeline import validate
from pipeline.compute import compute_country


def test_fiscal_gap_formula():
    c = compute_country("ITA", debt=138.4, r=3.99, real_growth=0.6, inflation=2.5, pb=0.79)
    assert c["g"] == pytest.approx(3.1)
    assert c["pb_star"] == pytest.approx(round((3.99 - 3.1) / 100 * 138.4, 2))
    assert c["fiscal_gap"] == pytest.approx(round(0.79 - (3.99 - 3.1) / 100 * 138.4, 2))
    assert c["sustainable"] is False
    assert c["real_growth"] == 0.6 and c["inflation"] == 2.5


def test_gap_is_headroom_times_debt():
    # Fiscal gap = (breakeven yield - r) x debt / 100, breakeven = g + 100 pb / debt
    c = compute_country("USA", debt=125.8, r=4.68, real_growth=2.32, inflation=3.23, pb=-3.67)
    breakeven = 2.32 + 3.23 + 100 * -3.67 / 125.8
    assert c["fiscal_gap"] == pytest.approx((breakeven - 4.68) * 125.8 / 100, abs=0.01)


@pytest.mark.parametrize("run, expected", [
    (date(2026, 9, 30), "2026-08"),
    (date(2026, 9, 10), "2026-07"),
    (date(2026, 1, 25), "2025-12"),
    (date(2026, 2, 5), "2025-12"),
])
def test_expected_yield_month(run, expected):
    assert validate.expected_yield_month(run) == expected


def test_lag_flag_only_when_behind():
    assert validate.yield_lag_flag("2026-08", date(2026, 9, 30)) is None
    f = validate.yield_lag_flag("2026-07", date(2026, 9, 30))
    assert f["kind"] == validate.LAGGING and "Jul 2026" in f["message"] and "Aug 2026" in f["message"]


def test_move_flag():
    assert validate.yield_move_flag(4.0, "2026-08", 3.5, "2026-07") is None
    assert validate.yield_move_flag(5.2, "2026-08", 3.5, "2026-07")["kind"] == validate.LARGE_MOVE
    assert validate.yield_move_flag(5.2, "2026-08", 3.5, "2026-08") is None


def test_ranges_and_revision():
    assert validate.in_range("r", 4.0)
    assert not validate.in_range("r", 45.0)
    assert not validate.in_range("debt", None)
    assert validate.revision_flag("debt", 204.4, 226.8, "October 2025")["kind"] == validate.LARGE_REVISION
    assert validate.revision_flag("pb", -1.7, -1.4, "October 2025") is None


def test_add_months():
    assert validate.add_months("2026-01", -1) == "2025-12"
    assert validate.add_months("2025-12", 2) == "2026-02"
