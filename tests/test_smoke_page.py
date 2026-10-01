"""Headless browser smoke test of index.html.

Serves the repository over a local HTTP server and checks that the page
renders all countries with no console errors and no third party requests.
Skipped when Playwright or its Chromium build is not installed.
"""

import functools
import http.server
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


def open_page(browser, url, route=None):
    page = browser.new_page()
    problems, external = [], []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}")
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("request", lambda r: external.append(r.url)
            if not r.url.startswith(url) and not r.url.startswith("data:") else None)
    if route:
        route(page)
    page.goto(url + "/index.html")
    page.wait_for_load_state("networkidle")
    return page, problems, external


def test_page_renders_all_countries(browser, base_url):
    page, problems, external = open_page(browser, base_url)
    rows = page.locator("#fiscal-table tbody tr:not(.section-divider)")
    assert rows.count() == 9
    assert page.evaluate("typeof Chart !== 'undefined' && !!Chart.getChart('debtChart')")
    assert "IMF WEO" in page.locator("#fiscal-table").locator("xpath=ancestor::div[contains(@class,'glass-card')]").inner_text()
    assert problems == []
    assert external == []
    page.close()


def test_row_click_selects_country(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    page.locator("#fiscal-table tbody tr", has_text="Japan").click()
    page.wait_for_timeout(300)
    assert page.evaluate("window._dashboardReady.selectedCountry.iso3") == "JPN"
    assert page.locator("select").input_value() == "JPN"
    assert problems == []
    page.close()


def test_load_failure_shows_banner(browser, base_url):
    def break_data(page):
        page.route("**/data/fiscal_data.js", lambda r: r.fulfill(status=404, body=""))
        page.route("**/data/fiscal_data.json", lambda r: r.fulfill(status=500, body=""))

    page, _, _ = open_page(browser, base_url, route=break_data)
    banner = page.get_by_text("Data could not be loaded")
    assert banner.is_visible()
    page.close()


def test_change_column_and_drivers_chart(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    result = page.evaluate("""() => {
        const d = window._dashboardReady, out = {};
        for (const p of d.periods.map(p => p.key)) {
            d.setPeriod(p);
            out[p] = Math.max(...d.allCountries.map(c => {
                const ch = d.change(c);
                return Math.abs(ch.rates + ch.real_growth + ch.inflation + ch.fiscal - ch.net);
            }));
        }
        return { errors: out, bars: Chart.getChart('driversChart').data.labels.length };
    }""")
    assert set(result["errors"]) >= {"1M", "6M", "1Y"}
    assert all(err < 1e-9 for err in result["errors"].values())
    assert result["bars"] == 9
    assert problems == []
    page.close()


def test_yield_shift_moves_gap_by_debt_sensitivity(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    moved = page.evaluate("""() => {
        const d = window._dashboardReady;
        d.setYieldShift(0);  // baseline recomputed from the displayed inputs
        const before = Object.fromEntries(d.allCountries.map(c => [c.iso3, [c.fiscal_gap, c.debt]]));
        d.setYieldShift(10);
        return d.allCountries.map(c => c.fiscal_gap - before[c.iso3][0] + before[c.iso3][1] / 1000);
    }""")
    # +10 bp moves each gap by -debt / 1000, up to 2 dp rounding
    assert all(abs(x) < 0.011 for x in moved), moved
    assert problems == []
    page.close()


def test_revisions_table(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    rows = page.locator("#revisions-table tbody tr")
    assert rows.count() == 9
    verdicts = set(page.locator("#revisions-table tbody tr td:last-child").all_inner_texts())
    assert verdicts <= {"Improving", "Deteriorating", "Mixed", "Unchanged"}
    assert problems == []
    page.close()


# ── Degraded data: the page must stay readable whatever is missing ─────────

BAD_TEXT = ("undefined", "NaN", "null", "[object")


def serve_payload(payload):
    import json

    def route(page):
        body = "window.FISCAL_DATA = " + json.dumps(payload) + ";"
        page.route("**/data/fiscal_data.js*", lambda r: r.fulfill(
            status=200, body=body, content_type="application/javascript"))
    return route


def real_payload():
    import json
    return json.loads((ROOT / "data" / "fiscal_data.json").read_text(encoding="utf-8"))


def visible_text(page):
    return page.locator("body").inner_text()


@pytest.mark.parametrize("strip", [
    ("comparisons", "revisions", "imf", "yields", "debt_year", "imf_debt_paths", "projection_year"),
    ("comparisons",),
    ("revisions",),
    ("imf",),
])
def test_page_survives_missing_blocks(browser, base_url, strip):
    payload = {k: v for k, v in real_payload().items() if k not in strip}
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    assert page.locator("#fiscal-table tbody tr:not(.section-divider)").count() == 9
    text = visible_text(page)
    assert not any(bad in text for bad in BAD_TEXT), [b for b in BAD_TEXT if b in text]
    assert page.locator("#key-messages li").count() >= 1
    assert problems == []
    page.close()


def test_page_survives_old_schema_countries(browser, base_url):
    # Version 1 files had no real growth, inflation or yield month.
    payload = real_payload()
    for c in payload["countries"]:
        for k in ("real_growth", "inflation", "r_month", "flags"):
            c.pop(k, None)
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    assert page.locator("#fiscal-table tbody tr:not(.section-divider)").count() == 9
    text = visible_text(page)
    assert not any(bad in text for bad in BAD_TEXT)
    assert problems == []
    page.close()


def test_labels_follow_the_data(browser, base_url):
    # Every year, month and release name on the page comes from the data.
    payload = real_payload()
    payload.update(projection_year=2031, debt_year=2030)
    payload["imf"]["vintage_label"] = "October 2030"
    payload["yields"]["typical_month"] = "2031-02"
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    text = visible_text(page)
    for expected in ("October 2030", "end 2030", "Feb 2031"):
        assert expected in text
    assert problems == []
    page.close()
