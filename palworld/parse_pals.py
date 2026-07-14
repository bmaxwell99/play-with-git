#!/usr/bin/env python3
"""Normalize an FModel export of Palworld's pal DataTable into pals.json / pals.csv.

Input is the JSON produced by FModel when you export
``Pal/Content/Pal/DataTable/Character/DT_PalMonsterParameter.uasset``
(right click -> Save Properties / .json). Optionally pass the exported
name-text table (``DT_PalNameText``) to resolve English display names.

The 1.0 update changed the work-suitability system (levels now go to 10,
new work types, work auras), so this script discovers every
``WorkSuitability_*`` column dynamically instead of hardcoding a list —
whatever the game data actually contains is what you get out.

Usage:
    python3 parse_pals.py DT_PalMonsterParameter.json \
        --names DT_PalNameText.json --out-dir out/

Outputs ``out/pals.json`` (full normalized records) and ``out/pals.csv``
(flat table, one column per discovered work type).

Stdlib only; no dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Row-name prefixes for non-catchable encounter variants of pals. These
# duplicate the base pal's entry with inflated stats and would pollute
# worker rankings. Skipped unless --include-all is passed.
NON_WORKER_PREFIXES = ("BOSS_", "GYM_", "RAID_", "SUMMON_", "PREDATOR_", "Quest_")

WORK_PREFIX = "WorkSuitability_"

# Non-work fields we carry through when present, keyed by output name.
# Each maps to candidate source field names (game data has inconsistent
# casing between fields, and 1.0 may have renamed some).
FIELD_ALIASES = {
    "tribe": ("Tribe",),
    "genus": ("GenusCategory",),
    "rarity": ("Rarity",),
    "nocturnal": ("Nocturnal", "IsNocturnal"),
    "craft_speed": ("CraftSpeed",),
    "food_amount": ("FoodAmount",),
    "max_full_stomach": ("MaxFullStomach",),
    "hp": ("Hp", "HP", "HP2"),
    "melee_attack": ("MeleeAttack",),
    "shot_attack": ("ShotAttack",),
    "defense": ("Defense",),
    "support": ("Support",),
    "stamina": ("stamina", "Stamina"),
    "walk_speed": ("walkSpeed", "WalkSpeed"),
    "run_speed": ("runSpeed", "RunSpeed"),
    "transport_speed": ("transportSpeed", "TransportSpeed"),
    "combi_rank": ("CombiRank",),
    "male_probability": ("maleProbability", "MaleProbability"),
    "price": ("Price",),
    "zukan_index": ("ZukanIndex",),
    "zukan_suffix": ("ZukanIndexSuffix",),
    "size": ("Size",),
    "element1": ("ElementType1",),
    "element2": ("ElementType2",),
    "passive_skills": ("PassiveSkill", "PassiveSkills", "InnatePassiveSkills"),
}


def load_rows(path: Path) -> dict:
    """Return the Rows dict from an FModel export.

    FModel wraps exports in a list of objects; the DataTable one has a
    "Rows" key. Also accepts a bare {"Rows": {...}} or a bare rows dict.
    """
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    candidates = data if isinstance(data, list) else [data]
    for obj in candidates:
        if isinstance(obj, dict) and isinstance(obj.get("Rows"), dict):
            return obj["Rows"]
    if isinstance(data, dict) and data and all(isinstance(v, dict) for v in data.values()):
        return data  # already a bare rows dict
    raise SystemExit(f"error: {path} does not look like an FModel DataTable export (no Rows found)")


def strip_enum(value):
    """'EPalWorkSuitability::EmitFlame' -> 'EmitFlame'; pass through non-strings."""
    if isinstance(value, str) and "::" in value:
        return value.rsplit("::", 1)[-1]
    return value


def extract_text(value):
    """Pull a display string out of an exported FText structure.

    FModel export shapes vary by version, so walk the structure and take
    the first non-empty string under a known text key.
    """
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("LocalizedString", "SourceString", "CultureInvariantString", "Text", "TextData"):
            if key in value:
                found = extract_text(value[key])
                if found:
                    return found
        for sub in value.values():
            found = extract_text(sub)
            if found:
                return found
    if isinstance(value, list):
        for sub in value:
            found = extract_text(sub)
            if found:
                return found
    return None


def load_names(path: Path) -> dict:
    """Map pal id -> display name from an exported DT_PalNameText table.

    Rows are keyed like ``PAL_NAME_SheepBall``; matching is done
    case-insensitively on the part after the last known prefix.
    """
    names = {}
    for key, row in load_rows(path).items():
        pal_id = key
        for prefix in ("PAL_NAME_", "PAL_FIRST_SPAWN_DESC_"):
            if key.upper().startswith(prefix):
                pal_id = key[len(prefix):]
                break
        text = extract_text(row)
        if text:
            names.setdefault(pal_id.lower(), text)
    return names


def is_truthy(value) -> bool:
    return value is True or value == 1 or (isinstance(value, str) and value.lower() == "true")


def normalize(rows: dict, names: dict, include_all: bool) -> tuple[list[dict], list[str]]:
    """Return (pal records, sorted list of discovered work types)."""
    work_types: set[str] = set()
    pals = []
    skipped_non_pal = skipped_variant = 0

    for row_id, row in rows.items():
        if not isinstance(row, dict):
            continue
        if not include_all:
            if "IsPal" in row and not is_truthy(row["IsPal"]):
                skipped_non_pal += 1
                continue
            if row_id.startswith(NON_WORKER_PREFIXES):
                skipped_variant += 1
                continue

        work = {}
        for field, value in row.items():
            if field.startswith(WORK_PREFIX) and isinstance(value, (int, float)):
                work_type = field[len(WORK_PREFIX):]
                work[work_type] = int(value)
                work_types.add(work_type)

        record = {"id": row_id, "name": names.get(row_id.lower(), row_id)}
        for out_field, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                if alias in row:
                    record[out_field] = strip_enum(row[alias])
                    break
        if "nocturnal" in record:
            record["nocturnal"] = is_truthy(record["nocturnal"])
        record["work"] = work

        # Surface any 1.0 aura/suitability-adjacent fields we don't know
        # about yet rather than silently dropping them.
        extras = {
            f: strip_enum(v)
            for f, v in row.items()
            if "aura" in f.lower() or ("worksuitability" in f.lower() and not f.startswith(WORK_PREFIX))
        }
        if extras:
            record["extras"] = extras

        pals.append(record)

    if skipped_non_pal or skipped_variant:
        print(
            f"skipped {skipped_non_pal} non-pal rows (humans/NPCs) and "
            f"{skipped_variant} boss/raid variants (use --include-all to keep them)",
            file=sys.stderr,
        )
    return pals, sorted(work_types)


def write_outputs(pals: list[dict], work_types: list[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "pals.json"
    json_path.write_text(
        json.dumps({"work_types": work_types, "pals": pals}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    scalar_fields = [
        "rarity", "nocturnal", "craft_speed", "food_amount", "transport_speed",
        "hp", "melee_attack", "shot_attack", "defense", "support",
        "element1", "element2", "combi_rank",
    ]
    csv_path = out_dir / "pals.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "name"] + scalar_fields + work_types)
        for pal in sorted(pals, key=lambda p: str(p.get("name", ""))):
            writer.writerow(
                [pal["id"], pal["name"]]
                + [pal.get(f, "") for f in scalar_fields]
                + [pal["work"].get(w, 0) for w in work_types]
            )

    print(f"wrote {json_path} and {csv_path}: {len(pals)} pals, work types: {', '.join(work_types)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("monster_parameter", type=Path,
                        help="FModel JSON export of DT_PalMonsterParameter")
    parser.add_argument("--names", type=Path,
                        help="FModel JSON export of DT_PalNameText (for display names)")
    parser.add_argument("--out-dir", type=Path, default=Path("out"),
                        help="output directory (default: out/)")
    parser.add_argument("--include-all", action="store_true",
                        help="keep boss/raid variants and non-pal rows")
    args = parser.parse_args()

    rows = load_rows(args.monster_parameter)
    names = load_names(args.names) if args.names else {}
    pals, work_types = normalize(rows, names, args.include_all)
    if not pals:
        raise SystemExit("error: no pal rows survived filtering — try --include-all to inspect the raw rows")
    write_outputs(pals, work_types, args.out_dir)


if __name__ == "__main__":
    main()
