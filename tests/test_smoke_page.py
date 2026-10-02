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
# Number of countries in the published data file
N = len(__import__("json").loads((ROOT / "data" / "fiscal_data.json").read_text(encoding="utf-8"))["countries"])


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
        except Exception as bundled_exc:  # noqa: BLE001
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception as system_exc:  # noqa: BLE001
                pytest.skip(f"Chromium not available: {bundled_exc}; system Chrome: {system_exc}")
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
    assert rows.count() == N
    status = page.locator("#freshness-status")
    assert status.is_visible()
    assert "Data checked" in status.inner_text()
    assert "Market yields" in status.inner_text()
    assert "IMF WEO" in status.inner_text()
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
                return Math.abs(ch.rates + ch.real_growth + ch.deflator + ch.fiscal - ch.net);
            }));
        }
        return { errors: out, bars: Chart.getChart('driversChart').data.labels.length };
    }""")
    assert set(result["errors"]) >= {"1M", "6M", "1Y"}
    assert all(err < 1e-9 for err in result["errors"].values())
    assert result["bars"] == N
    assert problems == []
    page.close()


def test_yield_shift_moves_gap_by_debt_sensitivity(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    moved = page.evaluate("""() => {
        const d = window._dashboardReady;
        d.setYieldShift(0);  // baseline recomputed from the displayed inputs
        const before = Object.fromEntries(d.allCountries.map(c => [c.iso3, [c.fiscal_gap, c.debt / (1 + c.g / 100)]]));
        d.setYieldShift(10);
        return d.allCountries.map(c => c.fiscal_gap - before[c.iso3][0] + before[c.iso3][1] / 1000);
    }""")
    # +10 bp moves each gap by -debt / (1 + g) / 1000, up to 2 dp rounding
    assert all(abs(x) < 0.011 for x in moved), moved
    assert problems == []
    page.close()


def test_revisions_table(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    rows = page.locator("#revisions-table tbody tr")
    assert rows.count() == N
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
    assert page.locator("#fiscal-table tbody tr:not(.section-divider)").count() == N
    text = visible_text(page)
    assert not any(bad in text for bad in BAD_TEXT), [b for b in BAD_TEXT if b in text]
    assert page.locator("#key-messages li").count() >= 1
    assert problems == []
    page.close()


def test_page_survives_old_schema_countries(browser, base_url):
    # Older files had no real growth, deflator or yield month.
    payload = real_payload()
    for c in payload["countries"]:
        for k in ("real_growth", "deflator", "inflation", "r_month", "flags"):
            c.pop(k, None)
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    assert page.locator("#fiscal-table tbody tr:not(.section-divider)").count() == N
    text = visible_text(page)
    assert not any(bad in text for bad in BAD_TEXT)
    assert problems == []
    page.close()


def test_freshness_notice_distinguishes_refresh_delay_and_carried_values(browser, base_url):
    payload = real_payload()
    payload["last_updated"] = "2000-01-01"
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    status = page.locator("#freshness-status")
    assert "Update delayed" in status.inner_text()
    assert "Market data may no longer reflect the latest yields" in status.inner_text()
    assert problems == []
    page.close()

    payload = real_payload()
    payload["countries"][0].setdefault("flags", []).append({
        "field": "r", "kind": "carried_forward", "message": "Test warning",
    })
    payload["data_status"] = ["Test warning"]
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    status = page.locator("#freshness-status")
    assert "carried forward" in status.inner_text()
    assert status.get_by_text("Data status").is_visible()
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


def test_trajectory_bridge_adds_up(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    result = page.evaluate("""() => {
        const d = window._dashboardReady;
        return d.allCountries.map(c => {
            d.selectCountryByIso(c.iso3);
            const b = d.bridge;
            return b ? Math.abs(b.interest + b.growth + b.other - b.total) : null;
        });
    }""")
    assert all(x is not None and x < 1e-9 for x in result)
    assert "Why the lines differ" in visible_text(page)
    assert problems == []
    page.close()


# ── Every control on the page, driven through the interface ───────────────

def table_state(page):
    return page.evaluate("""() => window._dashboardReady.allCountries.map(c =>
        [c.iso3, c.r, c.g, c.fiscal_gap].join(':')).sort().join('|')""")


def chart_state(page):
    return page.evaluate("""() => JSON.stringify([
        Chart.getChart('driversChart').data.datasets.map(d => d.data.map(v => +(+v).toFixed(4))),
        Chart.getChart('debtChart').data.datasets[0].data.map(v => +v.toFixed(4))])""")


def test_cell_edit_then_reset_restores_everything(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    published_table, published_charts = table_state(page), chart_state(page)
    message = page.locator("#key-messages li").first.inner_text()

    # Edit France's nominal growth in the table
    page.get_by_role("button", name="Full mechanics", exact=True).click()
    page.locator("#fiscal-table tbody tr", has_text="France").locator(".editable-cell").nth(2).click()
    box = page.locator("#fiscal-table input.table-input")
    box.fill("6.0")
    box.press("Enter")
    page.wait_for_timeout(300)
    assert table_state(page) != published_table
    assert chart_state(page) != published_charts

    # Reset from the drivers card
    page.locator("button", has_text="Reset to published data").first.click()
    page.wait_for_timeout(300)
    assert table_state(page) == published_table
    assert chart_state(page) == published_charts
    assert page.locator("#key-messages li").first.inner_text() == message
    assert problems == []
    page.close()


def test_yield_shift_then_reset(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    published = table_state(page)
    page.locator("#yield-shift").fill("50")
    page.wait_for_timeout(300)
    assert table_state(page) != published
    page.locator("button", has_text="Reset to published data").first.click()
    page.wait_for_timeout(300)
    assert table_state(page) == published
    assert page.locator("#yield-shift").input_value() == "0"
    assert problems == []
    page.close()


def test_period_toggles_stay_in_sync(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    groups = page.locator("[aria-label='Comparison period']")
    assert groups.count() == 2
    for label in ("6M", "1Y", "1M"):
        groups.nth(1).get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(200)
        for i in range(2):
            pressed = groups.nth(i).locator("button[aria-pressed='true']").inner_text()
            assert pressed == label
    assert problems == []
    page.close()


def test_theme_toggle_and_country_select(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    page.locator(".theme-toggle").click()
    page.locator(".theme-toggle").click()
    assert page.evaluate("!!Chart.getChart('driversChart') && !!Chart.getChart('debtChart')")
    before = chart_state(page)
    page.locator("select").select_option("JPN")
    page.wait_for_timeout(300)
    assert chart_state(page) != before
    assert "Japan" in page.locator("select").locator("option:checked").inner_text()
    assert problems == []
    page.close()


def test_drivers_toggle_stays_put(browser, base_url):
    # The toggle must not jump when the sentence beside it changes length,
    # or when a scenario adds the reset button. Measured within its card.
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(base_url + "/index.html")
    page.wait_for_load_state("networkidle")
    group = page.locator("[aria-label='Comparison period']").nth(1)
    where = """g => { const c = g.closest('.glass-card').getBoundingClientRect(), b = g.getBoundingClientRect();
                      return [Math.round(c.right - b.right), Math.round(b.top - c.top)]; }"""
    positions = set()
    for label in ("1M", "6M", "1Y", "Last IMF release", "1M"):
        group.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(150)
        positions.add(tuple(group.evaluate(where)))
    page.locator("#yield-shift").fill("25")
    page.wait_for_timeout(150)
    positions.add(tuple(group.evaluate(where)))
    assert len(positions) == 1, positions
    page.close()


def test_gap_at_net_interest_rate(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    result = page.evaluate("""() => {
        const d = window._dashboardReady;
        const before = d.allCountries.map(c => [c.iso3, d.gapEffective(c)]);
        d.setYieldShift(50);  // market move: headline gap changes, average rate does not
        const after = Object.fromEntries(d.allCountries.map(c => [c.iso3, d.gapEffective(c)]));
        return { missing: before.filter(([, v]) => v === null).length,
                 moved: before.filter(([iso, v]) => Math.abs(after[iso] - v) > 1e-9).length };
    }""")
    assert result == {"missing": 0, "moved": 0}
    assert "At the net interest rate governments pay on their debt" in page.locator("#key-messages").text_content()
    assert problems == []
    page.close()


def test_next_year_gap_hover(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    payload_year = real_payload()["projection_year"] + 1
    titles = page.locator("#fiscal-table tbody td[data-col='fiscal-gap']").evaluate_all("els => els.map(e => e.title)")
    assert len(titles) == N
    assert all(f"Next year ({payload_year})" in t for t in titles)
    assert not any(bad in " ".join(titles) for bad in BAD_TEXT)
    # The yield shift flows into next year's gap too
    moved = page.evaluate("""() => { const d = window._dashboardReady, c = d.allCountries[0];
        const before = d.nextYearGap(c).gap; d.setYieldShift(50); return d.nextYearGap(c).gap - before; }""")
    assert moved < 0
    assert problems == []
    page.close()


def test_comparison_chart_measures(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    group = page.locator("[aria-label='Comparison measure']")
    labels = group.locator("button").all_inner_texts()
    assert labels == ["Fiscal gap", "Yield cushion", "Gap at net interest rate"]
    for label in labels:
        group.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(200)
        state = page.evaluate("""() => {
            const d = window._dashboardReady, ch = Chart.getChart('compareChart'), m = d.currentMetric;
            const values = ch.data.datasets[0].data;
            const expected = d.allCountries.map(c => m.value(c)).sort((a, b) => b - a);
            return { n: values.length, sorted: values.every((v, i) => i === 0 || values[i - 1] >= v),
                     matches: values.every((v, i) => Math.abs(v - expected[i]) < 1e-9), sets: ch.data.datasets.length };
        }""")
        assert state["n"] == N and state["sorted"] and state["matches"], (label, state)
        assert state["sets"] == (2 if label == "Gap at net interest rate" else 1)
    # Scenario edits flow into the chart, reset restores it
    group.get_by_role("button", name="Fiscal gap", exact=True).click()
    page.wait_for_timeout(200)
    before = page.evaluate("Chart.getChart('compareChart').data.datasets[0].data.join()")
    page.locator("#yield-shift").fill("50")
    page.wait_for_timeout(200)
    assert page.evaluate("Chart.getChart('compareChart').data.datasets[0].data.join()") != before
    page.locator("button", has_text="Reset to published data").first.click()
    page.wait_for_timeout(200)
    assert page.evaluate("Chart.getChart('compareChart').data.datasets[0].data.join()") == before
    assert problems == []
    page.close()


def test_comparison_chart_without_net_interest_data(browser, base_url):
    payload = real_payload()
    for c in payload["countries"]:
        c.pop("r_eff", None)
    page, problems, _ = open_page(browser, base_url, route=serve_payload(payload))
    labels = page.locator("[aria-label='Comparison measure'] button").all_inner_texts()
    assert labels == ["Fiscal gap", "Yield cushion"]
    assert problems == []
    page.close()


def test_country_labels_are_not_clipped(browser, base_url):
    # The axis must be wide enough for the longest country name in Inter.
    page, problems, _ = open_page(browser, base_url)
    result = page.evaluate("""async () => {
        await document.fonts.ready;
        const out = {};
        for (const id of ['compareChart', 'driversChart']) {
            const ch = Chart.getChart(id), ctx = ch.ctx;
            ctx.save(); ctx.font = '12px Inter, sans-serif';
            const need = Math.max(...ch.data.labels.map(l => ctx.measureText(l).width));
            ctx.restore();
            out[id] = ch.scales.y.width - need;
        }
        return out;
    }""")
    assert all(room >= 0 for room in result.values()), result
    assert problems == []
    page.close()


def test_executive_momentum_is_generated_from_comparisons(browser, base_url):
    page, problems, _ = open_page(browser, base_url)
    strongest = page.evaluate("""() => {
        const d = window._dashboardReady;
        const expected = [...d.allCountries].sort((a, b) => b.fiscal_gap - a.fiscal_gap)[0];
        const card = d.executiveCards.find(c => c.label === 'Strongest fiscal position');
        return { value: card.value, expected: expected.name, note: card.note };
    }""")
    assert strongest["value"] == strongest["expected"]
    assert "pp fiscal gap" in strongest["note"]
    for label, key in (("1 month", "1M"), ("6 months", "6M"), ("1 year", "1Y")):
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(200)
        state = page.evaluate("""key => {
            const d = window._dashboardReady;
            const rows = d.allCountries.map(c => ({ name: c.name, change: d.changeForPeriod(c, key) }))
              .filter(r => r.change).sort((a, b) => b.change.net - a.change.net);
            return {
              selected: d.momentumPeriod,
              improved: d.momentumLeaders.improved.country.name,
              worsened: d.momentumLeaders.worsened.country.name,
              expectedImproved: rows[0].name,
              expectedWorsened: rows[rows.length - 1].name,
            };
        }""", key)
        assert state["selected"] == key
        assert state["improved"] == state["expectedImproved"]
        assert state["worsened"] == state["expectedWorsened"]
    assert problems == []
    page.close()


def test_mobile_decision_view_fits_phone(browser, base_url):
    page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    problems = []
    page.on("console", lambda m: problems.append(f"{m.type}: {m.text}")
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.goto(base_url + "/index.html")
    page.wait_for_load_state("networkidle")
    assert page.get_by_role("button", name="Decision view", exact=True).get_attribute("aria-pressed") == "true"
    assert page.locator("#countries .sm\\:hidden button").count() == N
    assert page.locator("#fiscal-table").is_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.locator(".theme-toggle").is_visible()
    assert problems == []
    page.close()
