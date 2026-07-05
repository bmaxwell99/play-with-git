# play-with-git
This repo is for testing, playing, bashing and complaining.  Have fun!

---

# Project: Manhattan Condos & Co-ops vs. the National Housing Market

**Question:** Have Manhattan condos and co-ops appreciated faster or slower than
the national housing market?

**Answer so far:** see [`reports/01-preliminary-findings.md`](reports/01-preliminary-findings.md).
Short version: Manhattan outperformed the nation from 2000 to the mid-2010s, then
sharply underperformed — prices have been roughly flat since 2017 while national
prices rose ~60%, leaving Manhattan behind the national market over the full
2000–2026 window.

## Project layout

```
├── src/
│   ├── fetch_data.py    # downloads raw source data (Zillow, FRED)
│   └── analyze.py       # builds comparison tables + charts from raw data
├── data/
│   └── raw/             # downloaded source CSVs (not committed until fetched)
├── reports/
│   ├── 01-preliminary-findings.md   # narrative answer with cited anchors
│   ├── figures/         # charts emitted by analyze.py
│   └── summary.md       # tables emitted by analyze.py
└── README.md
```

## Data sources

| Series | Source | What it measures |
|---|---|---|
| ZHVI Condo/Co-op, New York County NY | Zillow Research | Typical Manhattan condo/co-op value, monthly, smoothed & seasonally adjusted |
| ZHVI Condo/Co-op, United States | Zillow Research | Same measure, national |
| `NYXRCSA` | S&P Cotality Case-Shiller via FRED | NY-metro condo repeat-sales index (Jan 2000 = 100) |
| `CSUSHPINSA` | S&P Cotality Case-Shiller via FRED | US national repeat-sales index (Jan 2000 = 100) |
| `NYXRSA` | S&P Cotality Case-Shiller via FRED | NY-metro all-homes repeat-sales index |

Zillow's ZHVI condo cut is the only free series that isolates *Manhattan*
(New York County) condos/co-ops. Case-Shiller's condo index covers the NY metro
area (heavily NYC-weighted) but is the gold-standard repeat-sales methodology and
runs back to 1995.

## How to run

```bash
pip install pandas matplotlib
python src/fetch_data.py     # needs network access to files.zillowstatic.com and fred.stlouisfed.org
python src/analyze.py        # writes reports/figures/*.png and reports/summary.md
```

> **Note for Claude Code on the web:** this session's environment network policy
> blocks `files.zillowstatic.com` and `fred.stlouisfed.org`. To let the agent pull
> live data, allow those domains in the environment's network settings and re-run
> `src/fetch_data.py`. Until then, `reports/01-preliminary-findings.md` gives the
> answer from cited published anchor values.
