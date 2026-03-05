# G10 Fiscal Sustainability Dashboard

Interactive web dashboard analysing fiscal sustainability for 9 major economies (G10 scope). Based on the framework from the November 2025 Macro Report.

## What This Is

A single-page dashboard with two components:

1. **Fiscal Dashboard Table** — shows Debt/GDP, 10Y nominal rate (r), nominal growth (g), r−g differential, primary balance (pb), stabilising balance (pb\*), and Fiscal Gap for each country. Colour-coded green/red. Click any r or g value to edit and see how it affects sustainability in real time.

2. **Debt Trajectory Chart** — 10-year debt path simulation for a selected country. Sliders for r and g let you run what-if scenarios instantly.

## How to Open

Simply double-click `fiscal_dashboard.html` to open in any browser. No server needed.

## Framework

All variables are in **nominal terms**.

| Formula | Description |
|---|---|
| `pb* = (r − g) / 100 × d` | Debt-stabilising primary balance |
| `Fiscal Gap = pb − pb*` | Positive = sustainable, negative = needs consolidation |
| `d_t = d_{t−1} × (1+r/100) / (1+g/100) − pb` | Debt dynamics (chart) |

## Data Sources

| Variable | Source | Update frequency |
|---|---|---|
| 10Y nominal yields | FRED API (St. Louis Fed) | Daily |
| Gross debt / GDP | IMF Fiscal Monitor (`GGXWDG_NGDP`) | Biannual (Apr / Oct) |
| Primary balance | IMF Fiscal Monitor (`GGXONLB_NGDP`) | Biannual |
| Real GDP growth | IMF WEO (`NGDP_RPCH`) | Biannual |
| CPI inflation | IMF WEO (`PCPIPCH`) | Biannual |

Current data vintage: **IMF WEO October 2025 / FRED November 2025**

## Refreshing the Data

```bash
# Windows
set FRED_API_KEY=your_key_here
python scripts/fetch_data.py

# Mac / Linux
export FRED_API_KEY=your_key_here
python scripts/fetch_data.py
```

Get a free FRED API key at: https://fred.stlouisfed.org/docs/api/api_key.html

The script updates both `data/fiscal_data.json` and `data/fiscal_data.js`.

## Project Structure

```
Fiscal sustainability dashboard/
├── fiscal_dashboard.html     ← open this in your browser
├── data/
│   ├── fiscal_data.json      ← data (JSON, for http:// hosting)
│   └── fiscal_data.js        ← same data as JS variable (for file:// opening)
├── scripts/
│   └── fetch_data.py         ← data pipeline (FRED + IMF → data files)
├── requirements.txt          ← pip install -r requirements.txt
├── screenshots/              ← test screenshots (dev use only)
├── CLAUDE.md                 ← project context for Claude AI sessions
└── .claude/rules/            ← Claude coding conventions for this project
```

## Countries Covered

Spain · Switzerland · Italy · Japan · Canada · United Kingdom · Germany · United States · France

## ✅ Done

- [x] Full dashboard HTML (`fiscal_dashboard.html`) — works as a local file
- [x] Colour-coded table with section grouping (sustainable / unsustainable)
- [x] Inline-editable r and g values in table (live recalculation)
- [x] 10-year debt trajectory chart with country dropdown
- [x] r and g sliders with live chart update
- [x] End-of-line debt label on chart
- [x] Seeded data from November 2025 Macro Report
- [x] Python data pipeline (`fetch_data.py`) — FRED + IMF APIs
- [x] Manual override mechanism (`data/overrides.json`)
- [x] GitHub Actions workflow for automatic weekly data refresh
- [x] CLAUDE.md and rules files for future AI sessions

## ⏳ To Do — Publishing on the Web

### Option A: GitHub Pages (Recommended — Free)

1. Create a GitHub repository (private or public)
2. Push this entire folder to the repo
3. Go to **Settings → Pages → Source: Deploy from branch → main / root**
4. Add your FRED API key: **Settings → Secrets → `FRED_API_KEY`**
5. The GitHub Actions workflow (`.github/workflows/update_data.yml`) will refresh data every Monday automatically
6. Share the URL: `https://your-username.github.io/repo-name/fiscal_dashboard.html`

### Option B: Any Static Web Host

Upload `fiscal_dashboard.html` + `data/` folder to any static host (Netlify, Vercel, AWS S3, etc.). The page works as a static site — no server-side code needed.

### Note on the HTML filename

The dashboard uses `fiscal_dashboard.html` (not `index.html`). If you want it to load at the root URL without the filename in the link, either rename it to `index.html` when publishing, or configure your host to use it as the default document.
