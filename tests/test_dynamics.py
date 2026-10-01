from datetime import date

import pytest

from pipeline import dynamics


def snap(r, rg, inf, pb, debt):
    return {"r": r, "real_growth": rg, "inflation": inf, "pb": pb, "debt": debt}


def gap(x):
    return x["pb"] - (x["r"] - x["real_growth"] - x["inflation"]) * x["debt"] / 100


def test_decomposition_sums_exactly():
    then, now = snap(1.6, 0.1, 2.0, -1.4, 226.8), snap(2.94, 0.7, 2.3, -1.74, 204.4)
    parts = dynamics.decompose(then, now)
    total = parts["rates"] + parts["real_growth"] + parts["inflation"] + parts["fiscal"]
    assert total == pytest.approx(parts["net"], abs=1e-12)
    assert parts["net"] == pytest.approx(gap(now) - gap(then), abs=1e-12)


def test_rates_only_move():
    then, now = snap(4.0, 1.5, 2.5, -1.0, 100.0), snap(4.5, 1.5, 2.5, -1.0, 100.0)
    parts = dynamics.decompose(then, now)
    assert parts["rates"] == pytest.approx(-0.5)
    assert parts["real_growth"] == parts["inflation"] == parts["fiscal"] == 0


def test_months_before_clamps_day():
    assert dynamics.months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert dynamics.months_before(date(2026, 9, 30), 12) == date(2025, 9, 30)


def entry(d):
    return {"date": d, "kind": "reconstructed", "countries": {}}


def test_comparisons_pick_nearest_entry():
    hist = {"entries": [entry(x) for x in ("2025-08-31", "2025-09-30", "2026-03-31",
                                           "2026-04-30", "2026-08-31", "2026-09-30")]}
    arch = {"vintages": {"Apr2026": {"release_date": "2026-04-14"}}}
    out = dynamics.comparisons(hist, date(2026, 9, 30), arch, "Apr2026")
    assert out["1M"]["date"] == "2026-08-31"
    assert out["6M"]["date"] == "2026-03-31"
    assert out["1Y"]["date"] == "2025-09-30"
    assert out["IMF"]["date"] == "2026-03-31"  # last snapshot before the release


@pytest.mark.parametrize("pb, slope, expected", [
    (0.5, -2.0, "improving"), (0.5, 0.0, "improving"), (0.0, -2.0, "improving"),
    (-0.5, 2.0, "deteriorating"), (-0.5, 0.5, "deteriorating"),
    (0.5, 2.0, "mixed"), (0.1, 0.5, "unchanged"), (None, None, "unchanged"),
])
def test_verdict(pb, slope, expected):
    assert dynamics.verdict(pb, slope) == expected


def test_revisions_compare_same_year_and_slope():
    arch = {"vintages": {
        "Oct2025": {"release_date": "2025-10-14", "data": {"JPN": {
            "pb": {"2026": -1.4}, "debt": {"2025": 230.0, "2026": 226.8, "2030": 220.0}}}},
        "Apr2026": {"release_date": "2026-04-14", "data": {"JPN": {
            "pb": {"2026": -1.74}, "debt": {"2025": 207.0, "2026": 204.4, "2030": 200.0}}}},
    }}
    rev = dynamics.revisions(arch, "Apr2026", 2026)
    jpn = rev["countries"]["JPN"]
    assert rev["previous"] == "Oct2025" and (rev["slope_from"], rev["slope_to"]) == (2025, 2030)
    assert jpn["pb_change"] == pytest.approx(-0.34)
    # The level fell 22.4 pp but the slope barely moved: a rebase, not better dynamics.
    assert jpn["debt_level_change"] == pytest.approx(-22.4)
    assert jpn["debt_slope_change"] == pytest.approx(-7.0 - -10.0)
    # Weaker primary balance and a flatter debt decline.
    assert jpn["verdict"] == "deteriorating"


def test_no_comparison_when_history_is_too_far():
    hist = {"entries": [entry("2026-01-31")]}
    assert dynamics.comparisons(hist, date(2026, 9, 30), {"vintages": {}}, None) == {}
