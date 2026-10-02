# Fiscal Sustainability Dashboard — Claude Context

## Project
Fiscal Sustainability Dashboard for ten advanced economies, built for Antigravity Macro Research.

**Live URL:** https://romangoossens-a11y.github.io/fiscal-dashboard/
**GitHub repo:** https://github.com/romangoossens-a11y/fiscal-dashboard
**Local URL:** http://localhost:8743/index.html (run `python -m http.server 8743` in this folder)

## Tech Stack
- `index.html` (markup), `assets/app.js` (Alpine component), `assets/app.css` (compiled Tailwind)
- Nothing loads from third party hosts. Alpine 3.17.4, Chart.js 4.4.9 and the Inter font are self hosted in `assets/vendor` and `assets/fonts`, pinned in `package.json`
- After changing classes in `index.html` or `assets/app.js`, or the CSS source `assets/src/input.css`, run `npm install` once, then `npm run build`, and commit `assets/`. CI fails if they are out of date
- Data: `data/fiscal_data.js` (loaded via script tag, works file://) + `data/fiscal_data.json` (fetched via http://)
- Python pipeline: `scripts/fetch_data.py` (FRED monthly yields, IMF SDMX API)
- Hosting: GitHub Pages. Automatic data refresh runs every Monday and Thursday at 08:17 UTC through GitHub Actions. Monday is the normal update and Thursday is the recovery run

## Key Technical Notes
- **Chart instance** stored as closure variable `let _chart = null` inside `dashboard()` — NOT as Alpine reactive data. Alpine's proxy doesn't reliably persist assignments from outside event handlers (root cause of chart not updating bug).
- **`computeDebtPath`** returns raw floats (no `.toFixed()` rounding). Display rounding handled by tooltip/end-label `.toFixed(1)` and y-axis tick `(+v).toFixed(1) + '%'`.
- Sliders use `@input="sliderR = +$event.target.value; updateChart()"` — explicit value read before updateChart to avoid x-model timing issues.
- Scripts load `defer` in order: Chart.js, data, `app.js`, Alpine last. `init()` runs automatically (Alpine 3 calls it, so there is no `x-init`) and draws the chart with `$nextTick`.
- The table renders from one row template: `groups` getter, one `<tbody>` per group. `tableView` hides `.detail-col` fields for the default decision view. The full mechanics view uses the same table and therefore the same data and calculations
- Phones use generated country cards for the decision view and retain horizontal access to the full table. Safe area padding supports iOS and the controls use touch sized targets
- Load failure shows a banner (`loadError`). The page has one cadence aware freshness line. It turns amber through `hasFreshnessWarning` after ten days without a refresh, when market data lags, or when any value was carried forward. IMF data being unchanged between its April and October releases is not treated as stale
- `window.FISCAL_DATA` set by `data/fiscal_data.js`; `init()` prefers this over fetch().

## Data Pipeline
```powershell
# Refresh live data (FRED_API_KEY optional, the public FRED CSV is the fallback)
python scripts/fetch_data.py
python -m pytest -q
# Page smoke test needs: pip install playwright==1.55.0 && python -m playwright install chromium
```
- Code in `scripts/pipeline/`: `fred.py`, `imf.py` (sources), `vintages.py` (IMF release archive and detection), `validate.py` (ranges, lag, flags), `compute.py`, `history.py`, `run.py` (orchestration, sources injected so tests run offline)
- Yields: **monthly averages** for all ten countries. The US uses FRED `GS10`. The other nine use OECD long term interest rate series republished by FRED as `IRLTLT01XXM156N`. Each value carries `r_month`
- IMF: SDMX API `api.imf.org` (`WEO` dataflow) first, DataMapper fallback, archive last. Indicators `NGDP_RPCH`, `NGDP`, `GGXONLB_NGDP`, `GGXWDG_NGDP`, plus `GGXCNL_NGDP` for the bridge. GDP deflator growth is derived in `imf.derive()` from nominal GDP and real growth, so g equals IMF nominal GDP growth. CPI is not used. Target year is the run's calendar year
- **Never stops on a data problem.** A value that cannot be refreshed is carried forward and flagged (`flags` per country, `data_status` list). The front end shows an amber dot and a data status panel
- New IMF releases are detected by comparing with the latest archived release, labelled Apr (Apr to Sep) or Oct (Oct to Mar)
- `data/history.json`: one entry per run (`live`) plus monthly `reconstructed` entries from May 2019
- `data/imf_vintages.json`: every WEO release from April 2019, years t-3 to t+6
- `scripts/backfill.py`: one-off rebuild of both files from local WEO files (imf.org blocks scripts)
- `pipeline/dynamics.py` adds `comparisons` (history snapshots nearest to 1M, 6M, 1Y ago, plus the last one before the current IMF release) and `revisions` (current vs previous IMF release, same calendar year: pb level, debt slope from t-1 to t+4, verdict) to `fiscal_data.json`
- Breakeven yield = g + 100 x pb x (1 + g) / debt. A +10 bp yield move changes the gap by -debt / (1000 (1 + g))
- The change decomposition uses Shapley values over four drivers (rates, real growth, GDP deflator, fiscal = pb and debt), because the exact gap is not linear. Python `dynamics.decompose()` and JS `decompose()` must stay identical
- `imf_bridge` (IMF debt, net interest = primary minus overall balance, nominal GDP growth) feeds the trajectory footnote explaining simple vs IMF debt in the first year. Series come from `AUX_INDICATORS`
- Large debt revisions get a generated note (`validate.debt_revision_note`) saying whether the previous year moved too (revised history) or not (new outlook). It updates with every release
- **Debt is end of previous year** (`debt_year` = forecast year minus 1), as in d_t = d_(t-1) x (1 + r) / (1 + g) - pb_t. History uses the same definition. `config.field_year()` maps each IMF field to its year
- **No dates, release names, country counts or current country conclusions in the markup.** Every year, month, IMF release, executive indicator, momentum leader and explanation is built in `assets/app.js` from the data, with a neutral fallback when a field is missing. The key messages are generated sentences that drop out when their inputs are missing. Browser tests check the page with blocks removed, with an old schema, and with shifted years
- `npm run build` stamps asset links in `index.html` with a content hash (`?v=`), so a deploy cannot mix a new page with cached old scripts
- `r_eff` per country: IMF net interest (primary minus overall balance) x (1 + g) / debt at end of last year. Shown as "Gap at net interest rate" (the term "average rate" was dropped as unclear) next to the headline gap at the 10Y yield. It changes only with IMF releases, not with the yield shift. Gap at average rate is close to the IMF's projected fall in the debt ratio excluding other flows, a useful check
- Fiscal gap uses a single forecast year on purpose (decided 1 Oct 2026): averaging would hide sensitivity
- The executive overview is the first reading layer. `executiveCards` generates the four headline indicators, including the highest fiscal gap as the strongest fiscal position and the lowest fiscal gap as the weakest. `momentumLeaders` ranks `changeForPeriod()` over one month, six months or one year. `momentumExplanation()` uses the same Shapley contributions and driver phrases as the detailed drivers section. It identifies the largest contribution in the direction of the net move
- Fiscal momentum is a full width horizontal strip above the full width Country ranking chart. In the net interest view, `headlineMarker` draws a cyan tick for the 10Y fiscal gap and a faint connector to the net interest gap. Do not restore the previous hollow dot treatment
- Debt trajectory is visually ordered before IMF revisions because it explains the debt mechanism before the slower moving vintage comparison
- Country ranking chart (`updateComparison`): one measure at a time, fiscal gap, yield cushion or gap at net interest rate, ranked. It refreshes whenever the drivers chart does
- Adding a country: add it to `COUNTRY_NAMES` and `YIELD_SERIES` in `config.py`, then rerun `scripts/backfill.py --weo-dir ... --fresh-history` and `fetch_data.py`. The page (count in the header, chart heights) and the tests follow the data
- See `PLAN.md` for decisions and the roadmap

## Fiscal Framework (Nominal Terms)
- `g = (1 + real_growth)(1 + deflator) - 1` (nominal GDP growth)
- `pb* = (r - g) / (1 + g) × d_(t-1) / 100` (stabilising primary balance, exact form, debt at end of last year)
- `fiscal_gap = pb - pb*` (positive = sustainable)
- `d_t = d_{t-1} × (1 + r/100) / (1 + g/100) - pb` (debt dynamics for chart)

## Code Conventions
- Font weights: `font-semibold` (600), `font-bold` (700), `font-medium` (500) — not `font-600` etc.
- Tailwind classes are preferred. Responsive behaviour shared across several elements lives in `assets/src/input.css`, including decision table columns and mobile safe areas. Rebuild `assets/app.css` after any change
- Alpine.js `x-data="dashboard()"` on main container; all state in `dashboard()` closure
