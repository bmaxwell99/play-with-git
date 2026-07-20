"""Summarize the LES sales history mined by fetch_les_sales.py.

Filters to arm's-length residential sales, then reports yearly volume, median
price, and median $/sqft (condos/walk-ups only — co-op deeds carry no sqft).

Writes reports/03-les-sales-summary.md and two figures.

Usage: python src/analyze_les_sales.py [--input data/raw/les_sales_dof.csv]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

C_PRICE = "#2a78d6"
C_VOLUME = "#1baf7a"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

# DOF building-class categories that are residential sales of interest
RESIDENTIAL_PREFIXES = (
    "01",  # one family
    "02",  # two family
    "03",  # three family
    "07",  # rentals - walkup
    "08",  # rentals - elevator
    "09",  # coops - walkup
    "10",  # coops - elevator
    "12",  # condos - walkup
    "13",  # condos - elevator
    "15",  # condo coops
    "17",  # condo coops / condops
)
MIN_ARMS_LENGTH_PRICE = 10_000  # drop $0/$1 family transfers and estate deeds


def style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def single_series_plot(x, y, color, title, ylabel, out, kind="line") -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    if kind == "bar":
        ax.bar(x, y, color=color, width=0.7)
    else:
        ax.plot(x, y, color=color, linewidth=2)
    ax.set_ylabel(ylabel, color=INK_2, fontsize=9)
    ax.set_title(title, color=INK, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "les_sales_dof.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    df = pd.read_csv(args.input, parse_dates=["sale_date"])
    df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce")
    df["category"] = df["building_class_category"].astype(str).str.strip()

    res = df[
        df["category"].str.startswith(RESIDENTIAL_PREFIXES)
        & (df["sale_price"] >= MIN_ARMS_LENGTH_PRICE)
    ].copy()
    res["year"] = res["sale_date"].dt.year
    res["is_coop"] = res["category"].str.startswith(("09", "10"))
    res["is_condo"] = res["category"].str.startswith(("12", "13", "15", "17"))

    yearly = res.groupby("year").agg(
        sales=("sale_price", "size"),
        median_price=("sale_price", "median"),
        condo_share=("is_condo", "mean"),
        coop_share=("is_coop", "mean"),
    )
    ppsf = res[res.get("gross_square_feet", pd.Series(dtype=float)).gt(100)]
    if not ppsf.empty:
        yearly["median_ppsf"] = (ppsf["sale_price"] / ppsf["gross_square_feet"]).groupby(ppsf["year"]).median()

    fig_dir = args.out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    single_series_plot(
        yearly.index, yearly["median_price"] / 1000, C_PRICE,
        "LES residential sales: median price", "Median sale price ($k)",
        fig_dir / "les_median_price.png",
    )
    single_series_plot(
        yearly.index, yearly["sales"], C_VOLUME,
        "LES residential sales: volume", "Recorded arm's-length sales / yr",
        fig_dir / "les_sales_volume.png", kind="bar",
    )

    pct = lambda s: (s * 100).round(1)
    yearly["condo_share"] = pct(yearly["condo_share"])
    yearly["coop_share"] = pct(yearly["coop_share"])
    lines = [
        "# Lower East Side sales history (DOF public records)",
        "",
        f"{len(res):,} arm's-length residential sales "
        f"({res['sale_date'].min():%Y-%m} to {res['sale_date'].max():%Y-%m}); "
        f"raw file has {len(df):,} recorded transfers before filtering.",
        "",
        yearly.round(0).to_markdown(),
        "",
        "![median price](figures/les_median_price.png)",
        "![volume](figures/les_sales_volume.png)",
    ]
    out_md = args.out_dir / "03-les-sales-summary.md"
    out_md.write_text("\n".join(lines) + "\n")
    print(f"wrote {out_md} and {fig_dir}/les_*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
