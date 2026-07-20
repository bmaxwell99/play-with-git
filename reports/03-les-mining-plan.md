# Data-mining op: Lower East Side sales history from public records

Goal: assemble the recorded-sale history of the Lower East Side from primary
public records, before layering on commercial sources (Zillow etc.).

## Source stack (all NYC public records)

**Stage 1 — DOF citywide sales (2003 → present).** The NYC Department of
Finance publishes every recorded property sale with price, date, address, and a
`NEIGHBORHOOD` field that includes `LOWER EAST SIDE` (DOF splits out
`ALPHABET CITY`; we pull both and can slice later). Mined via the NYC Open Data
Socrata API — SQL-like queries, paging, no scraping:

- `w2pb-icbu` — NYC Citywide Annualized Calendar Sales Update (2003+)
- `usep-8jbt` — NYC Citywide Rolling Calendar Sales (trailing ~12 months)
- Script: `src/fetch_les_sales.py` → `data/raw/les_sales_dof.csv`

**Stage 2 — ACRIS deeds (1966 → present).** The City Register's ACRIS system
holds every recorded deed in Manhattan back to 1966. No neighborhood field, so
the op defines the LES geographically:

1. PLUTO (`64uk-42ks`): Manhattan lots in Community District 103 + zips
   10002/10009 → the set of LES tax blocks
2. ACRIS Real Property Legals (`8h5j-fqxa`): documents touching those blocks
3. ACRIS Real Property Master (`bnx9-e6tj`): deed-family docs with amounts/dates
4. Join → one row per deed per lot, cached per stage for resumability
- Script: `src/fetch_acris_deeds.py` → `data/raw/les_deeds_acris.csv`

**Analysis.** `src/analyze_les_sales.py` filters to arm's-length residential
sales (residential building classes, price ≥ $10k to drop family/estate
transfers), then reports yearly volume, median price, condo/co-op mix, and
median $/sqft where sqft exists. Smoke-tested against synthetic fixtures.

## Known data caveats

- DOF/ACRIS prices are deed consideration: **$0/nominal transfers**
  (inheritances, LLC reshuffles) must be filtered; bulk/portfolio deals can
  distort averages — medians preferred.
- **Co-op sales carry no square footage** (they're share transfers; DOF gross
  sqft is the building's), so $/sqft is condo-only. Pre-1980s the LES is
  overwhelmingly rental/HDFC, so early ACRIS deed volume is thin on apartments.
- ACRIS pre-~1990 records are digitized index entries; amounts are present but
  unit-level detail is weaker.
- Neighborhood boundaries: DOF's `LOWER EAST SIDE` ≠ CD3 ≠ zip 10002. The op
  keeps the definition explicit and adjustable in both stages.

## Status / blockers

Environment network policy currently blocks `data.cityofnewyork.us` (and
`nyc.gov`). Allowlist it and run:

```bash
python src/fetch_les_sales.py && python src/analyze_les_sales.py   # stage 1
python src/fetch_acris_deeds.py                                    # stage 2 (long)
```

Optional: set `SOCRATA_APP_TOKEN` (free from NYC Open Data) for higher rate
limits — stage 2 pulls a few hundred thousand rows.
