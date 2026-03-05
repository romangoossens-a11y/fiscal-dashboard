# Fiscal Sustainability Dashboard — Implementation Plan

## Context
Interactive G10 fiscal sustainability dashboard for team sharing via GitHub Pages. Replicates and extends the analysis from the 2025 Macro Report. Data auto-updates from free public APIs (FRED for 10Y yields, IMF for fiscal variables). Two components: (1) colour-coded sortable fiscal table, (2) interactive 10-year debt trajectory chart.

---

## Architecture

**Hosting**: GitHub Pages (free, shareable URL)
**Data refresh**: GitHub Actions weekly Python script → commits updated `data/fiscal_data.json`
**Frontend**: Single `index.html` — Tailwind CSS v3, Alpine.js, Chart.js (all via CDN)
**No backend**: all API calls happen server-side in the Python script

---

## Files

```
Fiscal sustainability dashboard/
├── CLAUDE.md
├── PLAN.md
├── index.html                        # Main dashboard
├── data/fiscal_data.json            # Pre-computed data (auto-generated)
├── scripts/fetch_data.py            # Data fetcher + calculator
├── requirements.txt                 # requests, pandas, fredapi
├── .github/workflows/update_data.yml
└── .claude/rules/
    ├── technical_stack.md           # (existing)
    ├── fidelity_standards.md        # (existing)
    ├── iterative_workflow.md        # (existing)
    ├── data_pipeline.md             # NEW
    ├── chart_design.md              # NEW
    └── fiscal_calculations.md      # NEW
```

---

## Mathematical Framework (Nominal Terms)

```
Debt dynamics:        d_t = d_{t-1} × (1+r/100) / (1+g/100) − pb
Stabilising balance:  pb* = (r − g) / 100 × d_{t-1}
Fiscal Gap:           gap = pb − pb*    [+ = sustainable, − = unsustainable]
```

---

## Data Sources & Series Codes

### FRED API (free key required)
| Country     | Series ID            |
|-------------|---------------------|
| USA         | `DGS10`             |
| Japan       | `IRLTLT01JPM156N`   |
| Germany     | `IRLTLT01DEM156N`   |
| France      | `IRLTLT01FRM156N`   |
| UK          | `IRLTLT01GBM156N`   |
| Canada      | `IRLTLT01CAM156N`   |
| Italy       | `IRLTLT01ITM156N`   |
| Spain       | `IRLTLT01ESM156N`   |
| Switzerland | `IRLTLT01CHM156N`   |

### IMF DataMapper API (no key)
Base: `https://www.imf.org/external/datamapper/api/v1/{INDICATOR}/{ISO3}`

| Variable        | Indicator       |
|-----------------|----------------|
| Gross Debt/GDP  | `GGXWDG_NGDP`  |
| Primary Balance | `GGXONLB_NGDP` |
| Real GDP Growth | `NGDP_RPCH`    |
| CPI Inflation   | `PCPIPCH`      |

`g = NGDP_RPCH + PCPIPCH`. Projection year: 2026.
ISO3 codes: USA, JPN, DEU, FRA, GBR, CAN, ITA, ESP, CHE

---

## Python Script (`scripts/fetch_data.py`)

1. Fetch FRED latest 10Y yield for each country → `r`
2. Fetch IMF DataMapper for debt, primary balance, real growth, inflation
3. Compute `g = real_growth + inflation`
4. Compute `r_g = r − g`, `pb_star = (r−g)/100 × d`, `gap = pb − pb_star`
5. Sort by `fiscal_gap` descending
6. Write `data/fiscal_data.json`

---

## Frontend (`index.html`)

**Table**: Country | Debt | r | g | r-g | pb | pb* | Fiscal Gap
- r-g < 0 → green text; r-g > 0 → red text
- Fiscal Gap > 0 → green; < 0 → red
- Section headers: "Sustainable (Gap ≥ 0)" / "Unsustainable (Gap < 0)"
- r and g cells inline-editable → recalculate pb*, gap, chart client-side

**Chart**: Country dropdown → 10-year debt trajectory
- Sliders: r (0–15%) and g (0–10%)
- Single line: green if declining, red if rising; area fill
- Final debt % labelled at end of line

---

## GitHub Actions

Weekly schedule (Monday 8am UTC) + manual trigger.
FRED key stored as `secrets.FRED_API_KEY`.

---

## Setup (One-Time)
1. Create GitHub repo, push this folder
2. Add `FRED_API_KEY` as repo secret
3. Enable GitHub Pages (main branch, root `/`)
4. Run `python scripts/fetch_data.py` locally once to seed data
5. Share `https://username.github.io/repo-name`

---

## Verification
1. `python scripts/fetch_data.py` → JSON values match report table
2. Open `index.html` → correct colour coding, correct ordering
3. Edit r for USA (4.17 → 5.00) → Fiscal Gap shifts by ~−0.5pp
4. Select Japan in chart → starting debt ≈ 230%
5. Move r slider up → debt trajectory steepens
