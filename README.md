# G10 Fiscal Sustainability Dashboard

Interactive web dashboard analysing fiscal sustainability for 9 major economies.
Based on the framework from the Antigravity Macro Research November 2025 report.

**Live site:** https://romangoossens-a11y.github.io/fiscal-dashboard/

---

## What It Shows

1. **Fiscal Dashboard Table** — Debt/GDP, 10Y yield (r), nominal growth (g), r−g, primary balance (pb), stabilising balance (pb*), and Fiscal Gap for each country. Colour-coded. Click any r or g value to edit for scenario analysis.

2. **Debt Trajectory Chart** — 10-year debt path simulation for a selected country. Sliders for r and g for what-if scenarios.

## Framework

All variables are in **nominal terms**.

| Formula | Description |
|---|---|
| `pb* = (r − g) / 100 × d` | Debt-stabilising primary balance |
| `Fiscal Gap = pb − pb*` | Positive = sustainable, negative = needs consolidation |
| `d_t = d_{t−1} × (1+r/100) / (1+g/100) − pb` | Debt dynamics (chart) |

## Data Sources

| Variable | Source | Indicator | Frequency |
|---|---|---|---|
| 10Y nominal yields | FRED (St. Louis Fed) | Various (see `scripts/fetch_data.py`) | Daily (USA) / Monthly (others) |
| Gross debt / GDP | IMF DataMapper | `GGXWDG_NGDP` | Biannual (Apr / Oct) |
| Primary balance | IMF DataMapper | `GGXONLB_G01_GDP_PT` | Biannual |
| Real GDP growth | IMF WEO | `NGDP_RPCH` | Biannual |
| CPI inflation | IMF WEO | `PCPIPCH` | Biannual |

Data auto-refreshes every Monday via GitHub Actions.

## Countries

Spain · Switzerland · Italy · Japan · Canada · United Kingdom · Germany · United States · France

## Project Structure

```
fiscal-dashboard/
├── index.html                ← the dashboard
├── data/
│   ├── fiscal_data.json      ← auto-generated data (http:// hosting)
│   └── fiscal_data.js        ← same data as JS variable (file:// opening)
├── scripts/
│   └── fetch_data.py         ← data pipeline (FRED + IMF APIs)
├── requirements.txt
├── .github/workflows/
│   └── update_data.yml       ← weekly auto-refresh
└── CLAUDE.md                 ← AI session context
```
