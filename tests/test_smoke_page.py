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
