# Fiscal Sustainability Dashboard

Interactive web dashboard analysing fiscal sustainability for 9 major economies.
Based on the framework from the Antigravity Macro Research November 2025 report.

**Live site:** https://romangoossens-a11y.github.io/fiscal-dashboard/

---

## What It Shows

1. **Fiscal Dashboard Table**: debt, 10Y yield (r), nominal growth (g), r − g, primary balance (pb), stabilising balance (pb*), fiscal gap, its change over 1M, 6M, 1Y or since the last IMF release, and the breakeven yield with headroom in bp. Click any highlighted value to edit, or shift all yields at once.
2. **What Moved the Fiscal Gap**: the change in each country's gap split into market rates, real growth, inflation and fiscal stance, with a dot for the net change.
3. **How the IMF Changed Its View**: current year primary balance and projected debt change, previous IMF release versus the latest, with a verdict.
4. **Debt Trajectory Simulation**: 10 year debt path for a selected country, with r and g sliders.

## Framework

All variables are in **nominal terms**.

| Formula | Description |
|---|---|
| `pb* = (r − g) / 100 × d` | Debt-stabilising primary balance |
| `Fiscal Gap = pb − pb*` | Positive = sustainable, negative = needs consolidation |
| `Breakeven r = g + 100 × pb / d` | 10Y yield at which the debt ratio is stable. Gap = (breakeven − r) × d / 100 |
| `d_t = d_{t−1} × (1+r/100) / (1+g/100) − pb` | Debt dynamics (chart) |

## Data Sources

| Variable | Source | Indicator | Frequency |
|---|---|---|---|
| 10Y nominal yields | FRED | `GS10` (US), OECD `IRLTLT01XXM156N` (others) | Monthly average |
| Gross debt / GDP | IMF WEO via SDMX API | `GGXWDG_NGDP` | April and October releases |
| Primary balance | IMF WEO via SDMX API | `GGXONLB_NGDP` | April and October releases |
| Real GDP growth | IMF WEO via SDMX API | `NGDP_RPCH` | April and October releases |
| CPI inflation | IMF WEO via SDMX API | `PCPIPCH` | April and October releases |

Data refreshes every Monday via GitHub Actions. If a source fails, the last good value is carried forward and flagged on the page. Every IMF release is archived in `data/imf_vintages.json` and every run in `data/history.json`.

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

Spain · Switzerland · Italy · Japan · Canada · United Kingdom · Germany · United States · France

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
