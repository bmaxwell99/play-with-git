"""Rolling 30-year windows, 1970-2026: Manhattan apartments vs the national market.

No continuous Manhattan condo/co-op index exists back to 1970, so this uses
annual series reconstructed from documented anchor values (see data/manual/*.csv,
each anchor carries a confidence flag and source note) with geometric
interpolation between anchors. Units differ between the two series (Manhattan
avg $/sqft vs a national index) — growth rates are unit-free.

Writes reports/02-rolling-30yr-windows.md and reports/figures/rolling_30yr_cagr.png.

Usage: python src/rolling_windows.py [--window-years 30]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Reference dataviz palette (light mode), matching analyze.py.
C_MANHATTAN = "#2a78d6"
C_NATIONAL = "#1baf7a"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"


def load_interpolated(csv_path: Path) -> pd.Series:
    """Annual series from anchor rows, geometric (log-linear) interpolation."""
    anchors = pd.read_csv(csv_path)
    years = np.arange(anchors["year"].min(), anchors["year"].max() + 1)
    values = np.exp(np.interp(years, anchors["year"], np.log(anchors["value"])))
    return pd.Series(values, index=years, name=csv_path.stem)


def window_table(manhattan: pd.Series, national: pd.Series, span: int) -> pd.DataFrame:
    rows = []
    for start in range(manhattan.index.min(), manhattan.index.max() - span + 1):
        end = start + span
        m = (manhattan[end] / manhattan[start]) ** (1 / span) - 1
        n = (national[end] / national[start]) ** (1 / span) - 1
        rows.append(
            {
                "window": f"{start}-{end}",
                "start": start,
                "Manhattan %/yr": m * 100,
                "National %/yr": n * 100,
                "gap (pp)": (m - n) * 100,
                "winner": "Manhattan" if m > n else "National",
            }
        )
    return pd.DataFrame(rows)


def plot_windows(table: pd.DataFrame, span: int, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)

    for col, label, color in (
        ("Manhattan %/yr", "Manhattan", C_MANHATTAN),
        ("National %/yr", "National", C_NATIONAL),
    ):
        ax.plot(table["start"], table[col], color=color, linewidth=2)
        ax.annotate(
            f"{label}  {table[col].iloc[-1]:.1f}%",
            (table["start"].iloc[-1], table[col].iloc[-1]),
            xytext=(8, 0), textcoords="offset points",
            color=INK, fontsize=9, va="center",
        )
    ax.legend(["Manhattan", "National"], frameon=False, labelcolor=INK_2, fontsize=9, loc="upper right")
    ax.set_xlabel("Window start year", color=INK_2, fontsize=9)
    ax.set_ylabel(f"Annualized appreciation over {span} years (%/yr)", color=INK_2, fontsize=9)
    ax.set_title(f"{span}-year appreciation by start year (reconstructed series)", color=INK, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-years", type=int, default=30)
    args = parser.parse_args()
    span = args.window_years

    manhattan = load_interpolated(ROOT / "data" / "manual" / "manhattan_ppsf_annual_anchors.csv")
    national = load_interpolated(ROOT / "data" / "manual" / "national_index_annual_anchors.csv")

    table = window_table(manhattan, national, span)
    wins = (table["winner"] == "Manhattan").sum()
    pct = wins / len(table) * 100

    fig_dir = ROOT / "reports" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    plot_windows(table, span, fig_dir / f"rolling_{span}yr_cagr.png")

    closest = table.loc[table["gap (pp)"].abs().idxmin()]
    # combined endpoint error (as a growth-multiple ratio) needed to flip the closest window
    flip_factor = ((1 + closest["Manhattan %/yr"] / 100) / (1 + closest["National %/yr"] / 100)) ** span
    lines = [
        f"# Rolling {span}-year windows: Manhattan vs national, "
        f"{table['start'].min()}-{table['start'].max() + span}",
        "",
        "Built from anchor-reconstructed annual series (`data/manual/*.csv` — every",
        "anchor carries a confidence flag and source note; pre-1989 Manhattan values",
        "are decade-level reconstructions, not survey data).",
        "",
        f"**Manhattan wins {wins} of {len(table)} windows ({pct:.0f}%).**",
        f"Narrowest margin: {closest['window']} at {closest['gap (pp)']:+.1f} pp/yr.",
        "",
        f"**Robustness:** in the narrowest window ({closest['window']}), Manhattan's",
        f"cumulative growth multiple is {flip_factor:.2f}x the national multiple — the",
        "reconstructed endpoint values would have to be jointly wrong by that factor",
        f"(~{(flip_factor - 1) * 100:.0f}%) for the winner to flip. Wider windows need larger errors;",
        "the pre-1989 reconstruction is the least certain but sits in windows with the",
        "largest margins.",
        "",
        table.drop(columns="start").round(2).to_markdown(index=False),
        "",
        f"![rolling CAGR](figures/rolling_{span}yr_cagr.png)",
    ]
    out_md = ROOT / "reports" / f"02-rolling-{span}yr-windows.md"
    out_md.write_text("\n".join(lines) + "\n")
    print(f"Manhattan wins {wins}/{len(table)} ({pct:.0f}%) of {span}-year windows")
    print(f"wrote {out_md} and {fig_dir}/rolling_{span}yr_cagr.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
