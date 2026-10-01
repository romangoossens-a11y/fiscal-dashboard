from datetime import date

import pytest

from pipeline import validate
from pipeline.compute import compute_country


def test_fiscal_gap_formula():
    # Exact form: pb* = (r - g) / (1 + g) x debt at the end of last year
    c = compute_country("ITA", debt=138.4, r=3.99, real_growth=0.6, deflator=2.5, pb=0.79)
    g = (1.006 * 1.025 - 1) * 100
    pb_star = (3.99 - g) / (1 + g / 100) * 138.4 / 100
    assert c["g"] == pytest.approx(round(g, 2))
    assert c["pb_star"] == pytest.approx(round(pb_star, 2))
    assert c["fiscal_gap"] == pytest.approx(round(0.79 - pb_star, 2))
    assert c["sustainable"] is False
    assert c["real_growth"] == 0.6 and c["deflator"] == 2.5


def test_gap_is_cushion_times_debt():
    # Breakeven = g + 100 pb (1 + g) / debt, and gap = (breakeven - r) x debt / (100 (1 + g))
    c = compute_country("USA", debt=123.9, r=4.68, real_growth=2.32, deflator=3.23, pb=-3.67)
    g = (1.0232 * 1.0323 - 1) * 100
    breakeven = g + 100 * -3.67 * (1 + g / 100) / 123.9
    assert c["fiscal_gap"] == pytest.approx((breakeven - 4.68) * 123.9 / (100 * (1 + g / 100)), abs=0.01)


def test_debt_revision_note_tells_history_from_outlook():
    from pipeline.validate import debt_revision_note
    japan = debt_revision_note(-23.0, -21.6, 2025, 2024, "October 2025", "April 2026")
    assert "revised historical data" in japan and "2024" in japan and "April 2026" in japan
    outlook = debt_revision_note(-6.0, -0.2, 2025, 2024, "October 2025", "April 2026")
    assert "change in the IMF outlook" in outlook


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


def test_deflator_is_derived_so_g_matches_nominal_gdp():
    from pipeline.compute import nominal_growth
    from pipeline.imf import derive
    data = derive({"USA": {"ngdp": {"2025": 30000.0, "2026": 31650.0}, "real_growth": {"2026": 2.32}}})
    deflator = data["USA"]["deflator"]["2026"]
    assert deflator == pytest.approx((1.055 / 1.0232 - 1) * 100, abs=1e-3)
    assert nominal_growth(2.32, deflator) == pytest.approx(5.5, abs=1e-3)
    assert "2025" not in data["USA"]["deflator"]  # needs the year before
