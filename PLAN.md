# Improvement plan

Agreed with Roman on 30 September 2026. Infrastructure first, new features after.
Tick items off as they land.

## Decisions

| Topic | Decision |
|---|---|
| Yields | Monthly averages for all 9 countries. US uses `GS10`, the others the OECD series on FRED. Each value carries its own month. |
| Failure policy | Never stop the job. A value that cannot be refreshed is carried forward and flagged, naming the country, the field, since when and why. |
| Timeliness at the margin | Breakeven yield, headroom and sensitivity per 10 bp, plus a global yield shift control. No daily feeds and no Bloomberg. |
| 1Y comparison | The dashboard as it stood a year ago, including the roll to a new fundamentals year. Same year comparisons live in the IMF revisions table. |
| IMF revisions | Compare the same calendar year across consecutive releases. Debt is compared on its projected slope, not its level, so rebases (Japan, April 2026) do not read as better dynamics. |

## Phase 0. Housekeeping

- [x] Fresh clone outside OneDrive (`Documents\Claude\fiscal-dashboard`)
- [x] Work on branches with pull requests
- [x] Test workflow on every pull request

## Phase 1. Data pipeline

- [x] Split `fetch_data.py` into sources, compute, validate and write
- [x] Store real growth and inflation separately, not only their sum
- [x] Metadata on every value: yield month, IMF release and target year, schema version
- [x] IMF from the SDMX API (`api.imf.org`), DataMapper as fallback, archive as last resort
- [x] FRED API with the public CSV endpoint as fallback, retries on both
- [x] Validation: ranges, large moves, lagging months
- [x] Carry forward and flag, never stop
- [x] History store (`data/history.json`) backfilled monthly from 2019
- [x] IMF release archive (`data/imf_vintages.json`) backfilled from April 2019
- [x] Workflow hardening: pinned packages, timeout, concurrency, rebase before push
- [x] Tests for formulas, validation and parsers
- [x] Front end reads the vintage label from the data and shows the data status note

## Phase 2. Front end hardening

- [x] Self host pinned Alpine and Chart.js, precompiled Tailwind CSS
- [x] Load failure banner, per value stale badge, yield month shown
- [x] All labels from the JSON, chart start year from `projection_year`
- [x] Merge the duplicated table row markup, remove the `waitForChart` polling
- [x] Optional headless smoke test in CI

## Phase 3. Features

- [x] Change column with 1M, 6M, 1Y and since last IMF release toggle
- [x] Drivers chart: rates, real growth, inflation, fiscal stance, net dot
- [x] IMF revisions table: current year pb, debt slope revision, verdict chip
- [x] Breakeven yield, headroom and sensitivity per 10 bp, replacing "Debt 10Y"
- [x] Global yield shift control
- [x] Wording: FRED pulse dot, "Unsustainable", G10 title

## Phase 3b. Readability pass

- [x] Column groups by source (IMF forecast, Market, Debt arithmetic, Trend, Market threshold)
- [x] Plain labels, units and years in headers, values without units
- [x] Debt at end of the previous year
- [x] Neutral editable cells, pencil on hover
- [x] Main driver tag on the change column
- [x] Comparison caption in market terms, scenario label
- [x] Drivers labelled by source, generated takeaway
- [x] IMF table with separate columns and verdict reasons
- [x] IMF debt path on the trajectory chart
- [x] Generated key messages
- [x] All labels from the data, tested against missing and shifted data
- [x] Content hashed asset links
