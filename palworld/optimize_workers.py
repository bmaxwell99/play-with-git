#!/usr/bin/env python3
"""Analyze pals.json (from parse_pals.py) to optimize base workers.

Three subcommands:

  rank      Best pals for one work type, sorted by suitability level,
            then craft speed, then lowest food drain.
                python3 optimize_workers.py pals.json rank Handcraft --top 15

  coverage  The single best pal for every work type at a glance.
                python3 optimize_workers.py pals.json coverage

  team      Greedy roster builder: pick N pals to staff a set of jobs.
            Each pal is assigned the job where it's most needed; totals
            per job are reported so you can spot gaps.
                python3 optimize_workers.py pals.json team --size 15 \
                    --works Handcraft Mining Transport Kindling

Suitability levels are whatever the game data says (1.0 raised the cap
to 10); this script makes no assumptions about the scale.

Stdlib only; no dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> tuple[list[dict], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["pals"], data["work_types"]


def resolve_work(name: str, work_types: list[str]) -> str:
    """Case-insensitive, substring-tolerant work-type lookup.

    Lets you type 'mining' or 'handcraft' without knowing the exact
    internal name (e.g. 'EmitFlame' is kindling — try 'flame').
    """
    exact = [w for w in work_types if w.lower() == name.lower()]
    if exact:
        return exact[0]
    partial = [w for w in work_types if name.lower() in w.lower()]
    if len(partial) == 1:
        return partial[0]
    options = ", ".join(work_types)
    raise SystemExit(f"error: work type {name!r} is {'ambiguous' if partial else 'unknown'}; available: {options}")


def sort_key(pal: dict, work: str):
    """Higher level first, then faster crafting, then cheaper to feed."""
    return (
        -pal["work"].get(work, 0),
        -(pal.get("craft_speed") or 0),
        pal.get("food_amount") or 99,
        pal["name"],
    )


def fmt_row(cols, widths):
    return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))


def print_table(header, rows):
    widths = [max(len(str(header[i])), *(len(str(r[i])) for r in rows)) if rows else len(str(header[i]))
              for i in range(len(header))]
    print(fmt_row(header, widths))
    print(fmt_row(["-" * w for w in widths], widths))
    for row in rows:
        print(fmt_row(row, widths))


def cmd_rank(pals, work_types, args):
    work = resolve_work(args.work, work_types)
    candidates = [p for p in pals if p["work"].get(work, 0) > 0]
    if args.night:
        candidates = [p for p in candidates if p.get("nocturnal")]
    candidates.sort(key=lambda p: sort_key(p, work))
    rows = [
        (p["name"], p["work"][work], p.get("craft_speed", ""), p.get("food_amount", ""),
         "night" if p.get("nocturnal") else "day", p.get("rarity", ""))
        for p in candidates[: args.top]
    ]
    print(f"Top {len(rows)} for {work}:")
    print_table(("pal", "lvl", "craft", "food", "shift", "rarity"), rows)


def cmd_coverage(pals, work_types, args):
    rows = []
    for work in work_types:
        ranked = sorted((p for p in pals if p["work"].get(work, 0) > 0), key=lambda p: sort_key(p, work))
        if ranked:
            best = ranked[0]
            runners = ", ".join(p["name"] for p in ranked[1:4])
            rows.append((work, best["name"], best["work"][work], runners))
        else:
            rows.append((work, "(none)", 0, ""))
    print_table(("work", "best pal", "lvl", "runners-up"), rows)


def cmd_team(pals, work_types, args):
    works = [resolve_work(w, work_types) for w in args.works] if args.works else list(work_types)
    size = args.size

    # Greedy assignment: repeatedly give the currently most-understaffed
    # job (lowest total assigned level) the best remaining pal for it.
    # A pal only works one station at a time, so each pal counts toward
    # exactly one job even if it covers several.
    totals = {w: 0 for w in works}
    assigned: list[tuple[dict, str]] = []
    remaining = [p for p in pals if any(p["work"].get(w, 0) > 0 for w in works)]

    while len(assigned) < size and remaining:
        needy = min(totals, key=lambda w: totals[w])
        candidates = [p for p in remaining if p["work"].get(needy, 0) > 0]
        if not candidates:
            # Nothing can do the neediest job; stop considering it.
            del totals[needy]
            if not totals:
                break
            continue
        best = min(candidates, key=lambda p: sort_key(p, needy))
        assigned.append((best, needy))
        totals[needy] += best["work"][needy]
        remaining.remove(best)

    print(f"Suggested {len(assigned)}-pal roster for: {', '.join(works)}\n")
    rows = [
        (p["name"], job, p["work"][job],
         "/".join(f"{w}:{lvl}" for w, lvl in sorted(p["work"].items()) if lvl > 0 and w != job) or "-",
         p.get("food_amount", ""), "night" if p.get("nocturnal") else "day")
        for p, job in assigned
    ]
    print_table(("pal", "assigned job", "lvl", "also covers", "food", "shift"), rows)
    print()
    print_table(("work", "total assigned lvl"), sorted(totals.items(), key=lambda kv: kv[0]))
    uncovered = [w for w in works if w not in totals or totals[w] == 0]
    if uncovered:
        print(f"\nWARNING: no coverage for: {', '.join(uncovered)}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pals_json", type=Path, help="pals.json produced by parse_pals.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_rank = sub.add_parser("rank", help="best pals for one work type")
    p_rank.add_argument("work", help="work type (case-insensitive, partial ok)")
    p_rank.add_argument("--top", type=int, default=15)
    p_rank.add_argument("--night", action="store_true", help="nocturnal pals only")

    sub.add_parser("coverage", help="best pal per work type")

    p_team = sub.add_parser("team", help="build a base roster")
    p_team.add_argument("--size", type=int, default=15, help="number of base slots (default 15)")
    p_team.add_argument("--works", nargs="+", help="work types to staff (default: all)")

    args = parser.parse_args()
    pals, work_types = load(args.pals_json)
    {"rank": cmd_rank, "coverage": cmd_coverage, "team": cmd_team}[args.command](pals, work_types, args)


if __name__ == "__main__":
    main()
