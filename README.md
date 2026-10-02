# Fiscal Sustainability Dashboard

Interactive web dashboard analysing fiscal sustainability for ten advanced economies.
Based on the framework from the Antigravity Macro Research November 2025 report.

**Live site:** https://romangoossens-a11y.github.io/fiscal-dashboard/

---

## What It Shows

1. **Executive overview**: four decision indicators, the countries whose fiscal gaps improved and worsened most over one or six months, and a ranked country comparison. Every statement is generated from the current data.
2. **Fiscal position**: a concise decision view by default, with a full mechanics view for debt, growth, rates, stabilising balance and breakeven yield. The mobile layout uses country cards instead of forcing the wide table onto a small screen.
3. **What moved the fiscal gap**: the change in each country's gap split into the 10Y yield, real growth, GDP deflator and fiscal stance, with a dot for the net change.
4. **How the IMF changed its view**: current year primary balance and projected debt change, previous IMF release versus the latest, with a verdict.
5. **Debt trajectory simulation**: a ten year debt path for a selected country against the IMF forecast.

The page is responsive for desktop, Android and iOS. Click any highlighted value in the full mechanics table to edit it, or shift all yields at once. Scenario changes flow through the overview, ranking, table and charts.

## Framework

All variables are in **nominal terms**.

| Formula | Description |
|---|---|
| `pb* = (r − g) / (1 + g) × d / 100` | Primary balance that stabilises debt (d at the end of last year) |
| `Fiscal Gap = pb − pb*` | Positive = sustainable, negative = needs consolidation |
| `Breakeven r = g + 100 × pb × (1 + g) / d` | 10Y yield at which the debt ratio is stable |
| `d_t = d_{t−1} × (1+r/100) / (1+g/100) − pb` | Debt dynamics (chart) |

## Data Sources

| Variable | Source | Indicator | Frequency |
|---|---|---|---|
| 10Y nominal yields | FRED for the US, OECD series republished by FRED for all other countries | `GS10` (US), `IRLTLT01XXM156N` (others) | Monthly average |
| Gross debt / GDP | IMF WEO via SDMX API | `GGXWDG_NGDP` | April and October releases |
| Primary balance | IMF WEO via SDMX API | `GGXONLB_NGDP` | April and October releases |
| Real GDP growth | IMF WEO via SDMX API | `NGDP_RPCH` | April and October releases |
| Nominal GDP | IMF WEO via SDMX API | `NGDP` | April and October releases |
| GDP deflator growth | Derived: (1 + nominal GDP growth) / (1 + real growth) − 1 | | |

Data refreshes every Monday and Thursday at 08:17 UTC through GitHub Actions. Monday is the normal update and Thursday provides a quiet recovery run. If a source fails, the last good value is carried forward and flagged on the page. A single status line shows the latest check, the market yield month and the IMF release. It turns amber only when the refresh is more than ten days old, market data lags, or a value has been carried forward. IMF data is expected to change only with its April and October releases.

Every IMF release is archived in `data/imf_vintages.json` and every run in `data/history.json`.

## Development

```
pip install -r requirements-dev.txt
python -m pytest -q
python scripts/fetch_data.py

# Front end assets, after changing classes or CSS
npm install
npm run build
```

## Countries

Spain · Switzerland · Italy · Japan · Canada · United Kingdom · Germany · United States · France · Australia

## Project Structure

```
fiscal-dashboard/
├── index.html                ← the dashboard markup
├── assets/                   ← app.js, compiled app.css, self hosted vendor files and fonts
├── data/
│   ├── fiscal_data.json      ← auto-generated data (http:// hosting)
│   ├── fiscal_data.js        ← same data as JS variable (file:// opening)
│   ├── history.json          ← snapshot per run, monthly back to 2019
│   └── imf_vintages.json     ← every IMF WEO release since April 2019
├── scripts/
│   ├── fetch_data.py         ← data pipeline entry point
│   ├── backfill.py           ← one-off rebuild of history and IMF archive
│   └── pipeline/             ← sources, validation, compute, history
├── tests/                    ← offline tests (pytest)
├── requirements.txt
├── .github/workflows/
│   └── update_data.yml       ← weekly auto-refresh
└── CLAUDE.md                 ← AI session context
```
