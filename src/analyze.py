"""Compare Manhattan condo/co-op appreciation against the national market.

Reads the CSVs downloaded by fetch_data.py from data/raw/ and writes:
  - reports/figures/rebased_index.png   (both series rebased to 100 at first common month)
  - reports/figures/cagr_windows.png    (annualized appreciation by start window)
  - reports/figures/case_shiller.png    (NY condo vs US national repeat-sales, if fetched)
  - reports/summary.md                  (tables of the numbers behind the charts)

Usage: python src/analyze.py [--data-dir DIR] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Reference dataviz palette (light mode): slot 1 blue, slot 2 aqua, chrome inks.
C_MANHATTAN = "#2a78d6"
C_NATIONAL = "#1baf7a"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

WINDOW_STARTS = ["2000", "2006", "2012", "2017", "2020"]


def load_zhvi_series(csv_path: Path, region: str, region_col: str = "RegionName") -> pd.Series:
    """Extract one region's ZHVI as a monthly Series indexed by date."""
    df = pd.read_csv(csv_path)
    row = df[df[region_col] == region]
    if len(row) != 1:
        raise ValueError(f"expected exactly one row for {region!r} in {csv_path.name}, got {len(row)}")
    date_cols = [c for c in df.columns if c[:2] in ("19", "20")]
    s = row[date_cols].iloc[0]
    s.index = pd.to_datetime(date_cols)
    return s.astype(float).dropna().rename(region)


def cagr(series: pd.Series, start: str) -> float | None:
    """Annualized growth from the first observation >= start to the last observation."""
    window = series[series.index >= start]
    if len(window) < 24:
        return None
    years = (window.index[-1] - window.index[0]).days / 365.25
    return (window.iloc[-1] / window.iloc[0]) ** (1 / years) - 1


def style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def plot_rebased(manhattan: pd.Series, national: pd.Series, out: Path) -> pd.DataFrame:
    df = pd.concat([manhattan, national], axis=1).dropna()
    rebased = df / df.iloc[0] * 100

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    for col, color in ((manhattan.name, C_MANHATTAN), (national.name, C_NATIONAL)):
        ax.plot(rebased.index, rebased[col], color=color, linewidth=2)
        ax.annotate(
            f"{col}  {rebased[col].iloc[-1]:.0f}",
            (rebased.index[-1], rebased[col].iloc[-1]),
            xytext=(8, 0), textcoords="offset points",
            color=INK, fontsize=9, va="center",
        )
    ax.legend(rebased.columns, frameon=False, labelcolor=INK_2, fontsize=9, loc="upper left")
    ax.set_title(
        f"Condo/co-op values, rebased to 100 in {rebased.index[0]:%b %Y}",
        color=INK, fontsize=12, loc="left",
    )
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return rebased


def plot_cagr_bars(manhattan: pd.Series, national: pd.Series, out: Path) -> pd.DataFrame:
    rows = []
    for start in WINDOW_STARTS:
        m, n = cagr(manhattan, start), cagr(national, start)
        if m is not None and n is not None:
            rows.append({"window": f"{start}→now", "Manhattan": m * 100, "National": n * 100})
    table = pd.DataFrame(rows).set_index("window")

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    x = range(len(table))
    width = 0.36
    handles = []
    for offset, (col, color) in enumerate(
        (("Manhattan", C_MANHATTAN), ("National", C_NATIONAL))
    ):
        pos = [i + (offset - 0.5) * (width + 0.03) for i in x]
        bars = ax.bar(pos, table[col], width=width, color=color, label=col)
        ax.bar_label(bars, fmt="%.1f%%", color=INK, fontsize=8, padding=2)
        handles.append(bars)
    ax.axhline(0, color=BASELINE, linewidth=1)
    ax.set_xticks(list(x), table.index)
    ax.legend(handles=handles, frameon=False, labelcolor=INK_2, fontsize=9)
    ax.set_ylabel("Annualized appreciation (%/yr)", color=INK_2, fontsize=9)
    ax.set_title("Annualized appreciation by start year", color=INK, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return table


def plot_case_shiller(cs_path: Path, out: Path) -> pd.DataFrame | None:
    if not cs_path.exists():
        return None
    df = pd.read_csv(cs_path, na_values=".")
    date_col = df.columns[0]  # FRED uses DATE (older) or observation_date
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    if not {"NYXRCSA", "CSUSHPINSA"}.issubset(df.columns):
        return None
    df = df[["NYXRCSA", "CSUSHPINSA"]].dropna()

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    for col, label, color in (
        ("NYXRCSA", "NY metro condos", C_MANHATTAN),
        ("CSUSHPINSA", "US national", C_NATIONAL),
    ):
        ax.plot(df.index, df[col], color=color, linewidth=2)
        ax.annotate(
            f"{label}  {df[col].iloc[-1]:.0f}",
            (df.index[-1], df[col].iloc[-1]),
            xytext=(8, 0), textcoords="offset points",
            color=INK, fontsize=9, va="center",
        )
    ax.legend(["NY metro condos", "US national"], frameon=False, labelcolor=INK_2, fontsize=9, loc="upper left")
    ax.set_title("Case-Shiller repeat-sales indices (Jan 2000 = 100)", color=INK, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    fig_dir = args.out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    manhattan = load_zhvi_series(args.data_dir / "zhvi_condo_county.csv", "New York County").rename("Manhattan")
    national = load_zhvi_series(args.data_dir / "zhvi_condo_metro.csv", "United States").rename("National")

    rebased = plot_rebased(manhattan, national, fig_dir / "rebased_index.png")
    cagr_table = plot_cagr_bars(manhattan, national, fig_dir / "cagr_windows.png")
    cs = plot_case_shiller(args.data_dir / "case_shiller.csv", fig_dir / "case_shiller.png")

    def annual(df: pd.DataFrame) -> pd.DataFrame:
        out = df.resample("YE").last().round(1)
        out.index = out.index.year.rename("year")
        return out

    lines = [
        "# Manhattan vs. national appreciation — summary tables",
        "",
        f"Data through **{rebased.index[-1]:%B %Y}** (Zillow ZHVI condo/co-op, mid-tier, smoothed & SA).",
        "",
        "## Cumulative growth (rebased, first common month = 100)",
        "",
        annual(rebased).to_markdown(),
        "",
        "## Annualized appreciation by window (%/yr)",
        "",
        cagr_table.round(2).to_markdown(),
    ]
    if cs is not None:
        lines += [
            "",
            "## Case-Shiller cross-check (Jan 2000 = 100)",
            "",
            annual(cs).to_markdown(),
        ]
    (args.out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out_dir / 'summary.md'} and {fig_dir}/*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
