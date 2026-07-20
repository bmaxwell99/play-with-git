"""Pull Lower East Side property sales from NYC Dept. of Finance public records.

Source: NYC Open Data (Socrata) mirrors of the DOF citywide sales files, which
carry an explicit NEIGHBORHOOD field ("LOWER EAST SIDE"). Coverage back to 2003
via the annualized dataset; the rolling dataset carries the trailing ~12 months.

Requires HTTPS access to data.cityofnewyork.us. An app token is optional but
raises rate limits: set SOCRATA_APP_TOKEN.

Writes data/raw/les_sales_dof.csv (one row per recorded sale).

Usage: python src/fetch_les_sales.py [--neighborhoods "LOWER EAST SIDE" ...]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

SOCRATA_HOST = "https://data.cityofnewyork.us"

# DOF sales mirrors on NYC Open Data. Field names are identical across the two;
# together they span 2003 -> trailing month.
DATASETS = {
    "annualized": "w2pb-icbu",  # NYC Citywide Annualized Calendar Sales Update
    "rolling": "usep-8jbt",     # NYC Citywide Rolling Calendar Sales
}

PAGE_SIZE = 50_000


def soql_fetch(dataset_id: str, where: str) -> pd.DataFrame:
    """Fetch all rows matching a SoQL where-clause, paging as needed."""
    headers = {"Accept": "application/json"}
    if token := os.environ.get("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = token
    frames, offset = [], 0
    while True:
        params = urllib.parse.urlencode(
            {"$where": where, "$limit": PAGE_SIZE, "$offset": offset, "$order": ":id"}
        )
        url = f"{SOCRATA_HOST}/resource/{dataset_id}.json?{params}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=300) as resp:
            rows = json.load(io.TextIOWrapper(resp, encoding="utf-8"))
        if not rows:
            break
        frames.append(pd.DataFrame(rows))
        print(f"  {dataset_id}: {offset + len(rows):,} rows")
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_where(neighborhoods: list[str]) -> str:
    hoods = ", ".join(f"'{n.upper()}'" for n in neighborhoods)
    # borough is '1' in some vintages, 'MANHATTAN' in others
    return f"(borough in ('1', 'MANHATTAN')) AND upper(neighborhood) in ({hoods})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--neighborhoods",
        nargs="+",
        default=["LOWER EAST SIDE", "ALPHABET CITY"],
        help="DOF neighborhood names to include (DOF splits Alphabet City out of the LES)",
    )
    args = parser.parse_args()

    where = build_where(args.neighborhoods)
    frames = []
    for name, dataset_id in DATASETS.items():
        print(f"fetching {name} ({dataset_id}) where {where}")
        frames.append(soql_fetch(dataset_id, where))
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        print("no rows returned — check connectivity and dataset ids")
        return 1

    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    for col in ("sale_price", "gross_square_feet", "land_square_feet",
                "residential_units", "total_units", "year_built"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # the rolling file overlaps the tail of the annualized file
    dedupe_keys = [k for k in ("block", "lot", "address", "apartment_number", "sale_date", "sale_price")
                   if k in df.columns]
    df = df.drop_duplicates(subset=dedupe_keys).sort_values("sale_date")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / "les_sales_dof.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out}: {len(df):,} sales, "
          f"{df['sale_date'].min():%Y-%m} to {df['sale_date'].max():%Y-%m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
