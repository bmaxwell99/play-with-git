# Preliminary findings: Manhattan condos/co-ops vs. the national market

*Written 2026-07-05. Status: **preliminary** — this session's network policy blocks
bulk downloads from Zillow and FRED, so this write-up is built from published
anchor values found via web search plus well-documented market history. Exact
monthly series and charts come from `src/fetch_data.py` + `src/analyze.py` once
those domains are allowed.*

## TL;DR

**It depends entirely on the window — but over the full modern era (2000–2026),
Manhattan condos and co-ops have appreciated *slower* than the national market,
and the gap opened almost entirely after 2017.**

- **2000 → mid-2010s: Manhattan outperformed.** It roughly doubled the national
  pace during the 2000s boom and fell far less during the 2008–2012 bust.
- **2017 → 2026: Manhattan sharply underperformed.** Manhattan prices are
  roughly *flat* versus their 2017 peak, while the national index rose ~70%.
- **Net of the two eras**, Manhattan's ~26-year appreciation (~2.6×, ≈3.8%/yr)
  trails the national repeat-sales index (~3.3×, ≈4.7%/yr).
- **In real (inflation-adjusted) terms**, Manhattan condo/co-op prices today are
  down roughly a quarter from 2017 and only modestly above their 2000 level,
  while national prices are meaningfully up in real terms.

## Anchor data points (cited)

| Anchor | Value | Source |
|---|---|---|
| Case-Shiller U.S. National (`CSUSHPINSA`, Jan 2000 = 100) | ≈ **329.9** (Mar 2026), +0.7% YoY | [FRED](https://fred.stlouisfed.org/series/CSUSHPINSA), [Advisor Perspectives](https://www.advisorperspectives.com/dshort/updates/2026/07/01/case-shiller-home-price-index-april-2026), [MacroRadar](https://www.macroradar.io/case-shiller-home-price-index) |
| Case-Shiller NY metro all homes (`NYXRSA`, Jan 2000 = 100) | ≈ **324.0** (Feb 2025), rising mid-single digits through 2025 | [Trading Economics](https://tradingeconomics.com/united-states/s-p-case-shiller-ny-new-york-home-price-index-fed-data.html), [FRED](https://fred.stlouisfed.org/series/NYXRSA) |
| Manhattan median sale price, condo + co-op, Q4 2025 | **$1,125,000**, +2.3% YoY | Elliman Report/Miller Samuel via [Brick Underground](https://www.brickunderground.com/sell/manhattan-co-op-condo-sales-market-report-nyc-fourth-quarter-2025), [Elliman Q4 2025 PDF](https://elliman.com/media/Manhattan_Q4_2025_63fbaed055.pdf) |
| Manhattan median, condos only, Q4 2025 | $1,661,000, −0.2% QoQ | same |
| Manhattan median, co-ops only, Q4 2025 | $825,000, +3.8% | same |
| Manhattan median, condo + co-op, Q1 2025 | $1,165,000 | [Brick Underground](https://www.brickunderground.com/sell/manhattan-co-op-condo-sales-market-report-nyc-first-quarter-2025) |
| Manhattan median sale price, 2000 | ≈ **$430K** (Miller Samuel decade series) | approximate, from Miller Samuel's [10-year trend reports](https://www.millersamuel.com/files/2011/10/MMR10.pdf); to be confirmed from raw data |

Values marked "approximate" and all pre-2025 Manhattan figures below are from
Miller Samuel / Case-Shiller / StreetEasy history as of the author's knowledge
cutoff and should be re-derived from the raw series before being quoted further.

## The story in four eras

**1. 2000–2008: Manhattan boom outruns the national boom.** The Manhattan
condo/co-op median roughly went from ~$430K to ~$950K–$1M by mid-2008 (~+120%),
while the national Case-Shiller index rose ~+60–85% to its 2006–07 peak. The
Case-Shiller NY-metro *condo* index (`NYXRCSA`) peaked well above the national
index on the common Jan-2000 = 100 base.

**2. 2008–2012: Manhattan falls less.** The national index dropped ~27%
peak-to-trough; NY-metro condos fell roughly half as much, and Manhattan medians
recovered faster (foreign capital, constrained supply, all-cash co-op buyers).

**3. 2012–2017: both rise; Manhattan luxury boom.** New-development condo wave,
records set through 2017 — Manhattan medians reached ~$1.15–1.2M. StreetEasy's
repeat-sales Manhattan index peaked in 2017–18.

**4. 2017–2026: the great divergence.** Manhattan stalled — 2019 mansion-tax
and SALT-deduction changes, condo oversupply, COVID exodus, then a
higher-rate era. The Q4 2025 median ($1.125M) is *below* the 2017–2018 and Q1 2025
levels in nominal terms. Meanwhile the national index went from ~190 (mid-2017)
to ~330 (2026), i.e. **+70–75%**, including the extraordinary 2020–2022 run
(+45%) that Manhattan mostly sat out. Only in 2024–2025 did NYC resume rising —
recently faster than the now-flat national market (+0.7% YoY nationally vs.
+2–5% for NYC/co-ops).

## Preliminary scorecard (to be replaced by computed table)

| Window | Manhattan condo/co-op | National (Case-Shiller) | Verdict |
|---|---|---|---|
| 2000 → 2026 | ~2.6× (≈3.8%/yr) | ~3.3× (≈4.7%/yr) | **Slower** |
| 2000 → 2008 peak | ~+120% | ~+60–85% | **Faster** |
| 2008 → 2012 trough | ~−10–15% | ~−27% | **Held up better** |
| 2012 → 2017 | ~+35–40% | ~+40% | comparable |
| 2017 → 2026 | ~0% | ~+70–75% | **Much slower** |
| 2020 → 2026 | ~+10–15% | ~+55% | **Much slower** |
| Real terms, 2017 → 2026 (CPI ≈ +33%) | ≈ −25% | ≈ +30% | **Much slower** |

## Addendum (2026-07-05): the last year, and the post-COVID window

**Last 12 months — Manhattan is now *outperforming*.** The Q2 2026 Elliman
report puts the Manhattan condo/co-op median at a **record $1,250,000, +4.2%
YoY** — the sixth straight quarter of annual gains, with listing inventory
falling, a record 57.9% of sales above $1M, and record cash share. The national
Case-Shiller index rose just **+0.8% YoY** (April 2026) and has declined
month-over-month recently. Case-Shiller's NY-metro all-homes index was **+3.8%
YoY**, second-strongest of the 20 metros (after Chicago, +6.5%). Roughly:
Manhattan +4%, nation +1%.

**Since COVID — Manhattan still far behind.** From the COVID-eve Q4 2019 median
of **$999,000** to Q2 2026's $1,250,000 is **~+25% over 6.5 years (≈3.5%/yr)** —
and less than that on a seasonally matched basis, since Q4 medians run below Q2
medians (vs. Q2 2019's ~$1.2M median, mid-2026 is only ~+3–5%). The national
Case-Shiller index rose from ~212 (Feb 2020, approximate) to ~330 — **~+55%
(≈7%/yr)**. Manhattan captured roughly half or less of the national post-COVID
boom; the deficit was built in 2020–2022 (nation +45%, Manhattan roughly flat)
and Manhattan has been closing the gap only since 2024.

| Window | Manhattan (median) | National (Case-Shiller) |
|---|---|---|
| Mid-2025 → mid-2026 | **+4.2%** (record $1.25M) | **+0.8%** |
| Q4 2019 → Q2 2026 | ~+25% (≈3.5%/yr); ~+3–5% seasonally matched vs Q2 2019 | ~+55% (≈7%/yr) |

## Why the divergence? (hypotheses to test)

1. **Tax policy:** 2017 SALT deduction cap raised the carrying cost of high-tax
   NYC ownership; 2019 NY mansion/transfer tax hit the >$1M segment — exactly
   Manhattan's median.
2. **Supply:** the 2014–2019 new-development condo pipeline delivered into a
   softening market; the nation as a whole was *under*-building.
3. **Demand shocks:** COVID out-migration and remote work hit dense, high-price
   urban cores hardest; the national boom was suburban/Sun-Belt.
4. **Rates cut both ways:** Manhattan's heavy cash/co-op segment is less
   rate-sensitive, which dampened both the 2020–22 boom and the 2022–24 chill.
5. **Co-op vs condo split:** co-ops (cheaper, primary-residence) have recently
   outperformed condos — worth separating in the computed analysis.

## Caveats

- Manhattan medians are **not quality-adjusted**; new-development mix can swing
  them. The computed analysis uses Zillow ZHVI (hedonic-adjusted, condo/co-op cut,
  New York County) and Case-Shiller repeat-sales as cross-checks.
- Case-Shiller `NYXRCSA` covers the NY *metro* condo market, not Manhattan alone.
- Appreciation ≠ total return: Manhattan carrying costs (common charges,
  maintenance, property taxes) and rents change the ownership economics
  materially.

## Next steps

1. Allow `files.zillowstatic.com` and `fred.stlouisfed.org` in the environment
   network policy; run `python src/fetch_data.py && python src/analyze.py`.
2. Replace the scorecard above with the computed tables/charts.
3. Extensions: condo-vs-co-op split, borough and neighborhood cuts, real
   (CPI-deflated) series, drawdown analysis, and a rent-vs-own overlay.
