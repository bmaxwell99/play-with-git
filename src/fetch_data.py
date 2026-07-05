"""Download raw source data for the Manhattan vs. national appreciation analysis.

Requires outbound HTTPS access to files.zillowstatic.com and fred.stlouisfed.org.
Writes CSVs into data/raw/.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

ZILLOW_BASE = "https://files.zillowstatic.com/research/public_csvs/zhvi"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

DOWNLOADS = {
    # Zillow ZHVI, Condo/Co-op home type, mid tier, smoothed + seasonally adjusted
    "zhvi_condo_county.csv": f"{ZILLOW_BASE}/County_zhvi_uc_condo_tier_0.33_0.67_sm_sa_month.csv",
    "zhvi_condo_metro.csv": f"{ZILLOW_BASE}/Metro_zhvi_uc_condo_tier_0.33_0.67_sm_sa_month.csv",
    # Case-Shiller: NY metro condo, US national, NY metro all-homes (Jan 2000 = 100)
    "case_shiller.csv": f"{FRED_CSV}?id=NYXRCSA,CSUSHPINSA,NYXRSA",
}

# FRED and some CDNs reject the default urllib user agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) housing-analysis/0.1"}


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    print(f"  wrote {dest} ({dest.stat().st_size:,} bytes)")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for name, url in DOWNLOADS.items():
        print(f"fetching {name} ...")
        try:
            fetch(url, RAW_DIR / name)
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures.append(name)
            print(f"  FAILED: {exc}", file=sys.stderr)
    if failures:
        print(f"\n{len(failures)} download(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nall downloads complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
