# Fiscal Sustainability Dashboard — Claude Context

## Project
G10 Fiscal Sustainability Dashboard for Antigravity Macro Research.

**Live URL:** https://romangoossens-a11y.github.io/fiscal-dashboard/
**GitHub repo:** https://github.com/romangoossens-a11y/fiscal-dashboard
**Local URL:** http://localhost:8743/index.html (run `python -m http.server 8743` in this folder)

## Tech Stack
- `index.html` (markup), `assets/app.js` (Alpine component), `assets/app.css` (compiled Tailwind)
- Nothing loads from third party hosts. Alpine 3.17.4, Chart.js 4.4.9 and the Inter font are self hosted in `assets/vendor` and `assets/fonts`, pinned in `package.json`
- After changing classes in `index.html` or `assets/app.js`, or the CSS source `assets/src/input.css`, run `npm install` once, then `npm run build`, and commit `assets/`. CI fails if they are out of date
- Data: `data/fiscal_data.js` (loaded via script tag, works file://) + `data/fiscal_data.json` (fetched via http://)
- Python pipeline: `scripts/fetch_data.py` (FRED monthly yields, IMF SDMX API)
- Hosting: GitHub Pages; auto data refresh every Monday via GitHub Actions

## Key Technical Notes
- **Chart instance** stored as closure variable `let _chart = null` inside `dashboard()` — NOT as Alpine reactive data. Alpine's proxy doesn't reliably persist assignments from outside event handlers (root cause of chart not updating bug).
- **`computeDebtPath`** returns raw floats (no `.toFixed()` rounding). Display rounding handled by tooltip/end-label `.toFixed(1)` and y-axis tick `(+v).toFixed(1) + '%'`.
- Sliders use `@input="sliderR = +$event.target.value; updateChart()"` — explicit value read before updateChart to avoid x-model timing issues.
- Scripts load `defer` in order: Chart.js, data, `app.js`, Alpine last. `init()` runs automatically (Alpine 3 calls it, so there is no `x-init`) and draws the chart with `$nextTick`.
- The table renders from one row template: `groups` getter, one `<tbody>` per group.
- Load failure shows a banner (`loadError`). The date badge turns amber after 10 days without a refresh (`isStale`).
- `window.FISCAL_DATA` set by `data/fiscal_data.js`; `init()` prefers this over fetch().

## Data Pipeline
```powershell
# Refresh live data (FRED_API_KEY optional, the public FRED CSV is the fallback)
python scripts/fetch_data.py
python -m pytest -q
# Page smoke test needs: pip install playwright==1.55.0 && python -m playwright install chromium
```
- Code in `scripts/pipeline/`: `fred.py`, `imf.py` (sources), `vintages.py` (IMF release archive and detection), `validate.py` (ranges, lag, flags), `compute.py`, `history.py`, `run.py` (orchestration, sources injected so tests run offline)
- Yields: **monthly averages** for all 9. US `GS10`, others OECD `IRLTLT01XXM156N`. Each value carries `r_month`
- IMF: SDMX API `api.imf.org` (`WEO` dataflow) first, DataMapper fallback, archive last. Indicators `NGDP_RPCH`, `PCPIPCH`, `GGXONLB_NGDP`, `GGXWDG_NGDP`. Target year is the run's calendar year
- **Never stops on a data problem.** A value that cannot be refreshed is carried forward and flagged (`flags` per country, `data_status` list). The front end shows an amber dot and a data status panel
- New IMF releases are detected by comparing with the latest archived release, labelled Apr (Apr to Sep) or Oct (Oct to Mar)
- `data/history.json`: one entry per run (`live`) plus monthly `reconstructed` entries from May 2019
- `data/imf_vintages.json`: every WEO release from April 2019, years t-3 to t+6
- `scripts/backfill.py`: one-off rebuild of both files from local WEO files (imf.org blocks scripts)
- See `PLAN.md` for decisions and the roadmap

## Fiscal Framework (Nominal Terms)
- `g = real_growth + inflation` (nominal growth)
- `pb* = (r/100 - g/100) × debt` (debt-stabilising primary balance)
- `fiscal_gap = pb - pb*` (positive = sustainable)
- `d_t = d_{t-1} × (1 + r/100) / (1 + g/100) - pb` (debt dynamics for chart)

## Code Conventions
- Font weights: `font-semibold` (600), `font-bold` (700), `font-medium` (500) — not `font-600` etc.
- All Tailwind classes; no custom CSS except minor inline styles
- Alpine.js `x-data="dashboard()"` on main container; all state in `dashboard()` closure
