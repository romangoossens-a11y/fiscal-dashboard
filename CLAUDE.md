# Fiscal Sustainability Dashboard — Claude Context

## Project
G10 Fiscal Sustainability Dashboard for Antigravity Macro Research.

**Live URL:** https://romangoossens-a11y.github.io/fiscal-dashboard/fiscal_dashboard.html
**GitHub repo:** https://github.com/romangoossens-a11y/fiscal-dashboard
**Local URL:** http://localhost:8743/fiscal_dashboard.html (run `python -m http.server 8743` in this folder)

## Tech Stack
- Single HTML file: `fiscal_dashboard.html` — Tailwind CSS, Alpine.js, Chart.js (all via CDN)
- Data: `data/fiscal_data.js` (loaded via script tag, works file://) + `data/fiscal_data.json` (fetched via http://)
- Python pipeline: `scripts/fetch_data.py` — FRED API + IMF DataMapper
- Hosting: GitHub Pages; auto data refresh every Monday via GitHub Actions

## Key Technical Notes
- **Chart instance** stored as closure variable `let _chart = null` inside `dashboard()` — NOT as Alpine reactive data. Alpine's proxy doesn't reliably persist assignments from outside event handlers (root cause of chart not updating bug).
- **`computeDebtPath`** returns raw floats (no `.toFixed()` rounding). Display rounding handled by tooltip/end-label `.toFixed(1)` and y-axis tick `(+v).toFixed(1) + '%'`.
- Sliders use `@input="sliderR = +$event.target.value; updateChart()"` — explicit value read before updateChart to avoid x-model timing issues.
- `waitForChart()` polls until Alpine data + Chart.js + canvas are all ready before rendering.
- `window.FISCAL_DATA` set by `data/fiscal_data.js`; `init()` prefers this over fetch().

## Data Pipeline
```powershell
# Refresh live data (PowerShell)
$env:FRED_API_KEY="your_key_here"
cd 'path\to\Fiscal sustainability dashboard'
python scripts/fetch_data.py
```
- FRED: 10Y yields — USA `DGS10` (daily), others `IRLTLT01XXM156N` (monthly)
- IMF primary balance indicator: `GGXONLB_G01_GDP_PT` (changed from old `GGXONLB_NGDP`)
- `PROJECTION_YEAR = date.today().year` — auto-set to current year at run time

## Fiscal Framework (Nominal Terms)
- `g = real_growth + inflation` (nominal growth)
- `pb* = (r/100 - g/100) × debt` (debt-stabilising primary balance)
- `fiscal_gap = pb - pb*` (positive = sustainable)
- `d_t = d_{t-1} × (1 + r/100) / (1 + g/100) - pb` (debt dynamics for chart)

## Code Conventions
- Font weights: `font-semibold` (600), `font-bold` (700), `font-medium` (500) — not `font-600` etc.
- All Tailwind classes; no custom CSS except minor inline styles
- Alpine.js `x-data="dashboard()"` on main container; all state in `dashboard()` closure
