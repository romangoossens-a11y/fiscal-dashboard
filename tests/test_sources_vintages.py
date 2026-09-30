from datetime import date

from pipeline import fred, imf, vintages


def test_parse_fred_csv_skips_missing():
    text = "observation_date,GS10\n2026-06-01,4.40\n2026-07-01,.\n2026-08-01,4.68\n"
    assert fred.parse_csv(text) == [("2026-06", 4.40), ("2026-08", 4.68)]


def test_parse_fred_api():
    payload = {"observations": [{"date": "2026-08-01", "value": "4.68"},
                                {"date": "2026-07-01", "value": "."}]}
    assert fred.parse_api(payload) == [("2026-08", 4.68)]


def test_parse_sdmx():
    payload = {"data": {
        "structures": [{"dimensions": {
            "series": [{"id": "COUNTRY", "values": [{"id": "USA"}, {"id": "JPN"}]},
                       {"id": "INDICATOR", "values": [{"id": "GGXWDG_NGDP"}]},
                       {"id": "FREQUENCY", "values": [{"id": "A"}]}],
            "observation": [{"id": "TIME_PERIOD",
                             "values": [{"value": "2025"}, {"value": "2026"}]}]}}],
        "dataSets": [{"series": {
            "0:0:0": {"observations": {"0": ["124.1"], "1": ["125.781"]}},
            "1:0:0": {"observations": {"1": ["204.4"], "0": None}}}}]}}
    out = imf.parse_sdmx(payload, {"GGXWDG_NGDP": "debt"})
    assert out == {"USA": {"debt": {"2025": 124.1, "2026": 125.781}},
                   "JPN": {"debt": {"2026": 204.4}}}


def test_parse_datamapper():
    out = {}
    imf.parse_datamapper({"values": {"GGXONLB_G01_GDP_PT": {"USA": {"2026": -3.7, "2027": None}}}},
                         "GGXONLB_G01_GDP_PT", "pb", out)
    assert out == {"USA": {"pb": {"2026": -3.7}}}


def test_label_for_follows_imf_calendar():
    assert vintages.label_for(date(2026, 4, 14)) == "Apr2026"
    assert vintages.label_for(date(2026, 9, 30)) == "Apr2026"
    assert vintages.label_for(date(2026, 10, 14)) == "Oct2026"
    assert vintages.label_for(date(2027, 2, 1)) == "Oct2026"


def _archive():
    return {"vintages": {
        "Oct2025": {"release_date": "2025-10-14", "source": "t",
                    "data": {"USA": {"debt": {"2026": 128.7}}}},
        "Apr2026": {"release_date": "2026-04-14", "source": "t",
                    "data": {"USA": {"debt": {"2026": 125.781}}}},
    }}


def test_register_unchanged_new_revised():
    a = _archive()
    assert vintages.register(a, {"USA": {"debt": {"2026": 125.781, "2031": 140.0}}},
                             date(2026, 9, 30), "t") == ("Apr2026", "unchanged")
    label, status = vintages.register(a, {"USA": {"debt": {"2026": 124.0}}}, date(2026, 10, 15), "t")
    assert (label, status) == ("Oct2026", "new")
    assert a["vintages"]["Oct2026"]["release_date"] == "2026-10-15"
    label, status = vintages.register(a, {"USA": {"debt": {"2026": 123.5}}}, date(2026, 11, 2), "t")
    assert (label, status) == ("Oct2026", "revised")
    assert a["vintages"]["Oct2026"]["release_date"] == "2026-10-15"


def test_in_force_and_previous():
    a = _archive()
    assert vintages.in_force(a, date(2026, 3, 31)) == "Oct2025"
    assert vintages.in_force(a, date(2026, 4, 14)) == "Apr2026"
    assert vintages.in_force(a, date(2025, 1, 1)) is None
    assert vintages.previous(a, "Apr2026") == "Oct2025"
    assert vintages.human("Apr2026") == "April 2026"


def test_window_keeps_release_horizon():
    data = {"USA": {"debt": {str(y): 1.0 for y in range(2015, 2035)}}}
    kept = vintages.window(data, 2026)["USA"]["debt"]
    assert min(kept) == "2023" and max(kept) == "2032"
