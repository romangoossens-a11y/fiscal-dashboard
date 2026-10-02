# Fiscal Dashboard Maintenance Guide

This file is the entry point for Codex and other coding agents. Read `CLAUDE.md` in full before changing the dashboard. It contains the architecture, fiscal formulas, data lineage, generated text rules and chart implementation notes. Use `README.md` for the user facing overview and `PLAN.md` for the decision history.

## Required workflow

1. Work on a short lived review branch for material changes.
2. Preserve the existing Tailwind, Alpine and Chart.js implementation. Do not introduce a new framework without explicit approval.
3. Keep all dates, IMF releases, country counts and economic conclusions generated from the data. Do not hardcode current observations in `index.html`.
4. Edit responsive styles in `assets/src/input.css`. Run `npm run build` after changing HTML classes, JavaScript, styles or vendor dependencies. Commit the generated `assets/app.css` and stamped asset links in `index.html`.
5. Run `.venv\Scripts\python.exe -m pytest -q` on Windows, or `python -m pytest -q` in CI.
6. Start a local server and obtain visual approval before merging a redesign. Do not merge, push or deploy until the user explicitly asks.
7. Branch protection and pull requests are optional for this single maintainer repository. Local tests and visual review are therefore mandatory before a direct merge to `main`.

## Data and availability rules

* `scripts/fetch_data.py` is the pipeline entry point.
* The US yield is FRED `GS10`. Other yields are OECD long term interest rate series republished by FRED.
* IMF WEO data comes from the SDMX API, then DataMapper, then the local archive.
* A source failure must retain and flag the last good value. It must not replace a live value with a blank or silently stop publishing.
* The scheduled refresh runs on Monday and Thursday at 08:17 UTC. IMF values normally change only in April and October.
* `data/fiscal_data.json` and `data/fiscal_data.js` must remain equivalent. History and IMF vintages must remain append only except during an intentional rebuild.

## Front end guardrails

* Scenario edits must flow through the overview, tables, Country Ranking, What Moved the Fiscal Gap, debt trajectory and Fiscal Data by Country.
* The Country Ranking, drivers and Fiscal Data by Country charts use the same height formula and bar thickness.
* Positive values use the shared green and negative values use the shared rose in country bar charts.
* Fiscal momentum supports one month, six months and one year. Its explanations must use the same decomposition as the detailed drivers chart.
* The decision table and full mechanics table are two views of the same data. Every metric remains sortable in both directions.
* Mobile behaviour must be checked for narrow Android and iOS widths. Preserve safe area padding and touch sized controls.
* Keep the cadence aware freshness message discreet. It should warn on a delayed scheduled refresh, lagging market data or carried values. Unchanged IMF data between its normal releases is not stale.

## Troubleshooting order

1. Check the browser console and the visible load or freshness message.
2. Run the full test suite.
3. Run `npm run build` and confirm `git diff --exit-code -- assets/ index.html` is clean.
4. Check `.github/workflows/update_data.yml` and the latest GitHub Actions run for refresh failures.
5. Review `data_status`, country `flags`, `data/history.json` and `data/imf_vintages.json` before changing fallback logic.
6. When changing formulas or decomposition, update the Python and JavaScript implementations together and add a regression test.

Whenever behaviour, sources, workflow or presentation changes, update `CLAUDE.md`, `README.md`, `PLAN.md` and this file where relevant.
