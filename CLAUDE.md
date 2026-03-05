# Fiscal Sustainability Dashboard

## Purpose
Interactive web dashboard analysing G10 fiscal sustainability. Hosted on GitHub Pages, shareable via URL. Data auto-updates weekly via GitHub Actions pulling from FRED + IMF public APIs. Based on the framework from `2025_11_17_Macro_Report_G10_Fiscal_Sustainability.tex`.

## Tech Stack
- Frontend: Single `index.html` — Tailwind CSS v3 (CDN), Alpine.js (CDN), Chart.js (CDN)
- Icons: Lucide via CDN
- Font: Inter (Google Fonts)
- Data: `data/fiscal_data.json` — fetched on page load (no backend)
- Python: `scripts/fetch_data.py` — data pipeline (FRED + IMF DataMapper APIs)
- Hosting: GitHub Pages; GitHub Actions for scheduled data refresh (every Monday)

## Project Structure
```
Fiscal sustainability dashboard/
├── index.html               # Dashboard (table + chart) — main deliverable
├── data/
│   └── fiscal_data.json    # Auto-generated; do not edit manually
├── scripts/
│   └── fetch_data.py       # Run to refresh data: python scripts/fetch_data.py
├── requirements.txt         # requests, pandas, fredapi
├── .github/
│   └── workflows/
│       └── update_data.yml # Weekly GitHub Actions trigger
└── .claude/rules/           # Project-specific Claude rules
```

## Countries Covered (9)
Spain, Switzerland, Italy, Japan, Canada, United Kingdom, Germany, United States, France
(G10 scope from the 2025 Macro Report; ordered most → least sustainable by Fiscal Gap)

## Core Math — Nominal Terms Throughout
```
Debt dynamics:        d_t = d_{t-1} × (1 + r/100) / (1 + g/100) − pb
Stabilising balance:  pb* = (r − g) / 100 × d_{t-1}        [result in % GDP]
Fiscal Gap:           gap = pb − pb*                         [+ = sustainable]
```
- `r`  = nominal 10Y government bond yield (%)
- `g`  = nominal GDP growth ≈ real GDP growth + CPI inflation (%)
- `d`  = gross government debt as % of GDP (prior year)
- `pb` = general government primary balance as % of GDP (+ = surplus, − = deficit)

See `.claude/rules/fiscal_calculations.md` for full detail and sign conventions.

## Data Sources
| Variable | Source | Series/Indicator |
|---|---|---|
| 10Y nominal yields | FRED API | See `.claude/rules/data_pipeline.md` |
| Gross debt/GDP | IMF Fiscal Monitor | `GGXWDG_NGDP` |
| Primary balance | IMF Fiscal Monitor | `GGXONLB_NGDP` |
| Real GDP growth | IMF WEO | `NGDP_RPCH` |
| CPI inflation | IMF WEO | `PCPIPCH` |

IMF vintage: October 2025 (biannual: April + October). Yields: daily from FRED (latest obs).

## Updating Data
```bash
export FRED_API_KEY=your_key_here
python scripts/fetch_data.py
# Commit data/fiscal_data.json
```
GitHub Actions runs this automatically every Monday 8am UTC using `secrets.FRED_API_KEY`.

## Key Design Rules
- Table sorted most → least sustainable by Fiscal Gap (descending)
- Two row groups: "Sustainable (Gap ≥ 0)" / "Unsustainable (Gap < 0)"
- All values nominal — clearly labelled in the UI
- r and g cells are inline-editable; changes recalculate pb*, gap, and chart client-side
- Chart: single debt trajectory for selected country, 10-year horizon
- Chart sliders adjust r and g for what-if analysis (independent of table baseline)
- Primary balance in chart is fixed at country's current value (displayed as a label)

## Current Implementation Status (March 2026)

**Built and working:**
- `fiscal_dashboard.html` — fully functional; double-click to open, no server needed
- `data/fiscal_data.js` — inline data (enables `file://` opening without fetch)
- `data/fiscal_data.json` — same data for `http://` serving
- `scripts/fetch_data.py` — FRED + IMF pipeline, writes both data files
- `.github/workflows/update_data.yml` — auto weekly data refresh via GitHub Actions
- All `.claude/rules/` files written

**Seeded data vintage:** IMF WEO Oct 2025 / FRED Nov 2025 (values from 2025 Macro Report)
**Live data:** Not yet fetched — needs FRED API key (free at fred.stlouisfed.org)

**Immediate next steps:**
1. `set FRED_API_KEY=<key>` then `python scripts/fetch_data.py` to pull live data
2. Push folder to GitHub repo → enable Pages → add `FRED_API_KEY` secret → share URL

## Reference
Original analysis: `2025_11_17_Macro_Report_G10_Fiscal_Sustainability.tex`
