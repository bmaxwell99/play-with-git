"""Stage-2 miner: LES deed history back to 1966 from ACRIS public records.

ACRIS document records have no neighborhood field, so the op runs in stages:

  1. PLUTO (64uk-42ks): pull Manhattan lots in Community District 103 / LES zips
     to build the set of tax blocks that define the Lower East Side.
  2. ACRIS Real Property Legals (8h5j-fqxa): document ids touching those blocks.
  3. ACRIS Real Property Master (bnx9-e6tj): deed-family documents (DEED, DEEDO,
     DEED.COR) with doc_amount, doc_date, recorded_datetime.
  4. Join 2+3 on document_id -> one row per deed per lot.

Each stage caches to data/raw/acris/ so a rate-limited run can resume.
Requires HTTPS access to data.cityofnewyork.us (SOCRATA_APP_TOKEN recommended;
the legals table is ~20M rows so the block filter matters).

Usage: python src/fetch_acris_deeds.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fetch_les_sales import soql_fetch

CACHE = Path(__file__).resolve().parent.parent / "data" / "raw" / "acris"

PLUTO = "64uk-42ks"
LEGALS = "8h5j-fqxa"
MASTER = "bnx9-e6tj"

# LES/Alphabet City definition: Manhattan CD 3 minus Chinatown/EV is contested;
# start broad (CD 103 + the two core zips) and let analysis slice later.
PLUTO_WHERE = "borough = 'MN' AND (cd = '103' OR zipcode in ('10002', '10009'))"

DEED_TYPES = "('DEED', 'DEEDO', 'DEED, LE', 'DEED, RC', 'DEED, TS')"


def cached(name: str, fetch) -> pd.DataFrame:
    path = CACHE / f"{name}.csv"
    if path.exists():
        print(f"using cached {path}")
        return pd.read_csv(path)
    df = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"wrote {path}: {len(df):,} rows")
    return df


def main() -> int:
    pluto = cached("pluto_les_lots", lambda: soql_fetch(PLUTO, PLUTO_WHERE))
    blocks = sorted({int(b) for b in pd.to_numeric(pluto["block"], errors="coerce").dropna()})
    print(f"LES footprint: {len(pluto):,} lots across {len(blocks)} tax blocks")

    block_list = ", ".join(str(b) for b in blocks)
    legals = cached(
        "acris_legals_les",
        lambda: soql_fetch(LEGALS, f"borough = '1' AND block in ({block_list})"),
    )
    doc_ids = legals["document_id"].dropna().unique()
    print(f"{len(doc_ids):,} documents touch LES blocks")

    def fetch_master() -> pd.DataFrame:
        frames = []
        chunk = 500  # keep the in() clause under Socrata's URL limits
        for i in range(0, len(doc_ids), chunk):
            ids = ", ".join(f"'{d}'" for d in doc_ids[i : i + chunk])
            frames.append(
                soql_fetch(MASTER, f"doc_type in {DEED_TYPES} AND document_id in ({ids})")
            )
        return pd.concat([f for f in frames if not f.empty], ignore_index=True)

    master = cached("acris_master_les_deeds", fetch_master)

    deeds = master.merge(
        legals[["document_id", "block", "lot", "street_number", "street_name", "unit"]],
        on="document_id",
        how="left",
    )
    deeds["doc_amount"] = pd.to_numeric(deeds.get("doc_amount"), errors="coerce")
    deeds["doc_date"] = pd.to_datetime(deeds.get("doc_date"), errors="coerce")
    out = CACHE.parent / "les_deeds_acris.csv"
    deeds.to_csv(out, index=False)
    print(f"wrote {out}: {len(deeds):,} deed-lot rows, "
          f"{deeds['doc_date'].min():%Y} to {deeds['doc_date'].max():%Y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
