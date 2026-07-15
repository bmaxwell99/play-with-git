# Palworld 1.0 pal data mining

Palworld 1.0 (July 10, 2026) overhauled the work suitability system —
levels now go 1–10 instead of 1–4, there are new work types and "work
aura" passives, and 72 new pals — so pre-1.0 wikis and tier lists are
wrong. Rather than trusting stale docs, this toolkit extracts pal data
straight from your own game install (the ground truth) and analyzes it
for **base worker optimization**.

The pipeline has two halves:

1. **Extract** the DataTables from the game's `.pak` files as JSON,
   using [FModel](https://fmodel.app/) on the machine where Palworld is
   installed (one-time, ~10 minutes).
2. **Analyze** those JSON exports with the scripts here (pure Python 3,
   no dependencies).

## Step 1: Extract the DataTables with FModel

Palworld is an Unreal Engine 5 game; all pal stats live in DataTable
assets inside `Palworld/Pal/Content/Paks/`.

1. Download [FModel](https://fmodel.app/) (Windows; the game files are
   what matters, so do this where Palworld is installed).
2. Add a game directory pointing at your install's
   `Pal/Content/Paks` folder (Steam default:
   `C:\Program Files (x86)\Steam\steamapps\common\Palworld\Pal\Content\Paks`).
3. Set **UE Version** to `GAME_UE5_1`. (If 1.0 bumped the engine and
   archives fail to parse, try the newer `GAME_UE5_x` presets.)
4. Palworld uses unversioned assets, so FModel needs a **mappings file**
   (`.usmap`): in Settings → General enable *Local Mapping File* and
   point it at a Palworld `.usmap`. Community-maintained mappings are at
   [elliotks/Palworld-FModel](https://github.com/elliotks/Palworld-FModel);
   if that hasn't updated for 1.0 yet, you can dump a fresh one yourself
   with the [UE4SS](https://docs.ue4ss.com/) `DumpUsmap` feature, or see
   [pwmodding.wiki's FModel guide](https://pwmodding.wiki/docs/developers/useful-tools/fmodel).
5. In the archive browser, navigate to each table below, right-click →
   **Save Properties (.json)**:

   | Table | Path in FModel | Contains |
   |---|---|---|
   | `DT_PalMonsterParameter` | `Pal/Content/Pal/DataTable/Character/` | every pal's stats + `WorkSuitability_*` levels (required) |
   | `DT_PalNameText` | `Pal/Content/L10N/en/Pal/DataTable/Text/` | English display names (optional but nice) |
   | `DT_PassiveSkill_Main` | `Pal/Content/Pal/DataTable/PassiveSkill/` | passive skills incl. 1.0 work auras (optional, for reference) |

   Exact paths may have shifted in 1.0 — if a path is missing, use
   FModel's search box for the table name; DataTables are also easy to
   spot under `Pal/Content/Pal/DataTable/`.

Copy the exported `.json` files somewhere the scripts can see them.

## Step 2: Normalize the export

```sh
python3 parse_pals.py DT_PalMonsterParameter.json \
    --names DT_PalNameText.json --out-dir out/
```

This writes:

- `out/pals.json` — full normalized records (feeds the optimizer)
- `out/pals.csv` — flat spreadsheet, one column per work type, if you'd
  rather pivot in Excel/Sheets

Notes on how it parses:

- **Work types are discovered dynamically** from `WorkSuitability_*`
  fields — nothing is hardcoded, so 1.0's new work types (e.g. oil
  extraction era additions, whatever 1.0 added) appear automatically.
- Boss/raid/gym variant rows (`BOSS_*`, `RAID_*`, …) and non-pal rows
  (humans, NPCs) are skipped by default; `--include-all` keeps them.
- Any field that looks aura- or suitability-related but isn't a plain
  `WorkSuitability_*` level is preserved under `extras` in `pals.json`
  instead of being dropped — check there for 1.0's work-aura flags.

## Step 3: Optimize your base workers

Best pals for one job (level, then craft speed, then lowest food drain):

```sh
python3 optimize_workers.py out/pals.json rank handcraft --top 15
python3 optimize_workers.py out/pals.json rank mining --night   # night shift
```

Best pal for every job at a glance:

```sh
python3 optimize_workers.py out/pals.json coverage
```

Build a roster for your base slots — greedy assignment that repeatedly
staffs the currently most-understaffed job with the best remaining pal
for it, then shows per-job totals and coverage gaps:

```sh
python3 optimize_workers.py out/pals.json team --size 15 \
    --works handcraft mining transport kindling watering
```

Work-type names are case-insensitive and partial ("flame" matches
`EmitFlame`, which is kindling).

## Sample data

`sample_data/` contains a tiny **synthetic** fixture in FModel's export
shape — fake numbers, real structure — so you can smoke-test the
pipeline without game files:

```sh
python3 parse_pals.py sample_data/DT_PalMonsterParameter.sample.json \
    --names sample_data/DT_PalNameText.sample.json --out-dir /tmp/out
python3 optimize_workers.py /tmp/out/pals.json coverage
```

Do not use the sample numbers for actual game decisions.

## Step 4 (optional): Plot coordinates on a map

`plot_map.py` projects labelled points — base locations, spawn coords,
fast-travel statues, dig spots — onto a map and writes **one
self-contained HTML file** (image embedded, no server, no dependencies)
you can drop into Slack/Discord or open anywhere. Markers are coloured by
category with hover tooltips, categories toggle on/off in the legend, and
a live world-coordinate readout follows your mouse.

### Getting a base map image

You don't need to (and shouldn't redistribute) a wiki's map — the world
map texture is in *your* game files, same as the stats. In FModel, search
for the map texture (e.g. `T_WorldMap*` / `T_OpenWorldMap*` under
`Pal/Content/Pal/Texture/UI/Map/`), right-click → **Save Texture (.png)**.
For personal/base-planning use that's the real 1.0 map. If you'd rather
not bother, skip `--map` entirely and you get a clean coordinate grid,
which is still perfectly usable for relative layout.

### Calibrating the coordinate transform

Palworld's world coordinates don't map 1:1 to map pixels (and its map Y is
flipped), so instead of hardcoding constants that 1.0 may have changed,
you give **reference points** and the tool solves the transform:

1. Pick a spot you can identify on your map image and note its pixel
   position (most image viewers show x/y on hover), plus the world coord
   it corresponds to (from the datamine, or read off the in-game compass).
2. Do that for 2 points (enough for Palworld's axis-aligned map; the Y
   flip is handled automatically) or 3 points (if your map is rotated).

```sh
python3 plot_map.py points.csv --map worldmap.png --out base_map.html \
    --ref=112,-435,812,1440 --ref=380,140,1560,690 \
    --title "Our base & spawn map"
```

Use the `--ref=` (equals) form: Palworld coordinates are often negative,
and `--ref -230,...` would otherwise be mistaken for a command-line flag.

`points.csv` columns: `x,y,label[,category]`. `category` drives marker
colour and the legend toggles (e.g. `base`, `spawn`, `statue`, `mining`).
You can also feed a `pals.json`-style file if you add `x`/`y` fields.

No calibration handy? `--autofit` scales all points to fill the canvas —
great for a quick relative-layout view or grid mode:

```sh
python3 plot_map.py sample_data/points.sample.csv --out demo.html --autofit
```

### Viewing it on localhost

Add `--serve` to spin up a local web server (stdlib, no deps) and open
the map in your browser at `http://localhost:8000`:

```sh
python3 plot_map.py sample_data/points.sample.csv --out demo.html \
    --autofit --serve
# serving map at http://localhost:8000/demo.html  (Ctrl+C to stop)
```

Pass a port if 8000 is taken: `--serve 8127`. The server binds to
`127.0.0.1` (local only). Re-run the command to regenerate after editing
your points file, then refresh the browser.

(That sample command uses synthetic coordinates from `sample_data/` — fake
numbers, real format — so you can see the output before extracting
anything.)

## Ideas for later

- Parse `DT_PassiveSkill_Main` to rank work-speed passives (Artisan,
  Serious, …) and identify which pals carry 1.0 work auras innately.
- Factor breeding (`CombiRank`) into the roster builder to suggest
  attainable suitability upgrades (1.0 lets breeding raise suitability).
- Cross-check a couple of pals in-game against the extracted numbers to
  validate the export before trusting it wholesale.
