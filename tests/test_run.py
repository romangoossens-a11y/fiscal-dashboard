"""The whole run with fake sources: nothing ever stops it."""

from datetime import date

import pytest

from pipeline.config import COUNTRIES, YIELD_SERIES
from pipeline.run import build
from pipeline.validate import CARRIED_FORWARD, LAGGING

RUN = date(2026, 9, 30)
IMF = {iso: {"real_growth": {"2026": 1.5}, "deflator": {"2026": 2.5},
             "pb": {"2026": -1.0}, "debt": {"2025": 100.0, "2026": 103.0}} for iso in COUNTRIES}
SERIES_TO_ISO = {s: iso for iso, s in YIELD_SERIES.items()}
N = len(COUNTRIES)


def archive():
    return {"vintages": {"Apr2026": {"release_date": "2026-04-14", "source": "t",
                                     "data": {iso: {f: dict(v) for f, v in fields.items()}
                                              for iso, fields in IMF.items()}}}}


def good_yield(series):
    return [("2026-07", 3.8), ("2026-08", 4.0)], "FRED API"


def fail(*_):
    raise ConnectionError("timeout")


def run(fetch_yield=good_yield, fetch_sdmx=lambda: IMF, fetch_dm=fail, previous=None, arch=None):
    return build(RUN, fetch_yield, fetch_sdmx, fetch_dm, previous, arch or archive())


def by_iso(out):
    return {c["iso3"]: c for c in out["countries"]}


def test_happy_path():
    out = run()
    assert len(out["countries"]) == N and out["data_status"] == []
    assert out["imf"]["vintage"] == "Apr2026" and out["imf"]["release_status"] == "unchanged"
    assert out["data_vintage"] == "IMF WEO April 2026 | 10Y yields: monthly averages, Aug 2026"
    c = by_iso(out)["USA"]
    assert c["r"] == 4.0 and c["r_month"] == "2026-08" and c["flags"] == []
    # g = 1.015 x 1.025 - 1 = 4.04%, above r = 4%, so pb* is slightly negative
    assert c["fiscal_gap"] == pytest.approx(-1 - (4 - 4.0375) / 1.040375, abs=0.01)
    assert c["debt"] == 100.0 and out["debt_year"] == 2025  # end of last year


def test_failed_yield_is_carried_forward_and_flagged():
    previous = run()
    previous["last_updated"] = "2026-09-23"

    def flaky(series):
        if SERIES_TO_ISO[series] == "JPN":
            raise ConnectionError("timeout")
        return good_yield(series)

    out = run(fetch_yield=flaky, previous=previous)
    jpn = by_iso(out)["JPN"]
    assert len(out["countries"]) == N
    assert jpn["r"] == 4.0
    kinds = [f["kind"] for f in jpn["flags"]]
    assert CARRIED_FORWARD in kinds
    carried = next(f for f in jpn["flags"] if f["kind"] == CARRIED_FORWARD)
    assert carried["since"] == "2026-09-23"
    assert any(s.startswith("Japan r:") for s in out["data_status"])

    # A second failed week keeps the original date.
    out["last_updated"] = "2026-09-30"
    again = run(fetch_yield=flaky, previous=out)
    carried = next(f for f in by_iso(again)["JPN"]["flags"] if f["kind"] == CARRIED_FORWARD)
    assert carried["since"] == "2026-09-23"


def test_out_of_range_yield_is_rejected():
    previous = run()
    out = run(fetch_yield=lambda s: ([("2026-08", 99.0)], "FRED API"), previous=previous)
    assert all(c["r"] == 4.0 for c in out["countries"])
    assert all(any(f["kind"] == CARRIED_FORWARD for f in c["flags"]) for c in out["countries"])


def test_lagging_month_is_flagged():
    def lagging(series):
        if SERIES_TO_ISO[series] == "ESP":
            return [("2026-07", 3.5)], "FRED API"
        return good_yield(series)

    esp = by_iso(run(fetch_yield=lagging))["ESP"]
    assert [f["kind"] for f in esp["flags"]] == [LAGGING]


def test_imf_falls_back_to_datamapper_then_archive():
    out = run(fetch_sdmx=fail, fetch_dm=lambda: IMF)
    assert out["imf"]["source"] == "IMF DataMapper (fallback)"
    assert out["imf"]["vintage"] == "Apr2026" and len(out["countries"]) == N
    assert any("DataMapper" in s for s in out["data_status"])

    out = run(fetch_sdmx=fail, fetch_dm=fail)
    assert out["imf"]["source"] == "IMF release archive (fallback)"
    assert len(out["countries"]) == N


def test_missing_imf_field_comes_from_archive():
    partial = {iso: dict(fields) for iso, fields in IMF.items()}
    partial["FRA"] = {k: v for k, v in IMF["FRA"].items() if k != "pb"}
    fra = by_iso(run(fetch_sdmx=lambda: partial))["FRA"]
    assert fra["pb"] == -1.0
    assert any(f["field"] == "pb" and f["kind"] == CARRIED_FORWARD for f in fra["flags"])


def test_new_release_is_archived():
    changed = {iso: dict(fields, debt={"2025": 101.0, "2026": 104.0}) for iso, fields in IMF.items()}
    arch = archive()
    out = build(date(2026, 10, 15), good_yield, lambda: changed, fail, None, arch)
    assert out["imf"]["vintage"] == "Oct2026" and out["imf"]["release_status"] == "new"
    assert "Oct2026" in arch["vintages"]


def test_first_run_with_no_data_skips_rather_than_crashes():
    out = run(fetch_yield=fail, fetch_sdmx=fail)
    assert out["countries"] == [] and len(out["skipped"]) == N
