# Starter prompt for a local Claude Code session

Copy everything in the fenced block below into a **new Claude Code chat
running on the desktop where Palworld is installed**. It's self-contained
— that session has none of our context, so the prompt carries the full
goal, the extraction path, and where the analysis scripts live.

---

```text
I have Palworld 1.0 installed on this machine and I want to data-mine the
pal stats straight from the game files so I can optimize my base workers.
The internet guides for 1.0 are stale, so I want ground truth from my own
install. You have local filesystem + shell access; please do the
extraction and analysis end to end and stop to ask me only if a GUI step
is unavoidable.

GOAL: produce a normalized pals.json/pals.csv of every pal and its
WorkSuitability_* levels, then rank pals per job and suggest a base roster.

The analysis tooling already exists in this GitHub repo/branch — clone it
first:
  git clone --branch claude/palworld-pal-data-mining-jvkii0 \
    https://github.com/bmaxwell99/play-with-git.git
  cd play-with-git/palworld
Read its README.md — it documents the whole pipeline and the two scripts
(parse_pals.py, optimize_workers.py, stdlib Python 3 only).

STEP 1 — Extract the DataTables to JSON. Try these in order; use the first
that works on this machine:

  (a) PalworldDataExtractor (CLI, preferred — you can run it unattended):
      https://github.com/PalworldDataTools/PalworldDataExtractor
      It reads the game's .pak and emits per-table data. Point it at:
        <Steam>\steamapps\common\Palworld\Pal\Content\Paks
      (default Steam path: C:\Program Files (x86)\Steam\steamapps\common\Palworld)
      If it needs a .usmap mappings file for 1.0, get one from
      https://github.com/elliotks/Palworld-FModel or dump a fresh one with
      UE4SS (https://docs.ue4ss.com/), then re-run. We specifically need
      the DT_PalMonsterParameter table (pal stats + work suitability) and,
      if available, DT_PalNameText (English names). Coerce its output into
      FModel's export shape if needed — see step 2 for what the parser
      expects.

  (b) A pak CLI (repak / UnrealPak) to unpack the .pak, then convert the
      DT_PalMonsterParameter.uasset to JSON with a .usmap-aware tool.

  (c) FModel GUI (last resort — you can't automate it). If it comes to
      this, tell me the exact click path and I'll export the JSON myself,
      then hand you the files. The repo README has the FModel steps.

STEP 2 — Normalize. parse_pals.py expects the FModel "Save Properties"
JSON shape: a top-level object (or list containing one) with a "Rows"
dict keyed by pal id, each row having WorkSuitability_* integer fields.
If your extractor emits a different shape, transform it to that first
(or just show me a sample of its output and adapt the parser — it's small
and readable). Then:
  python3 parse_pals.py <MonsterParameter>.json --names <NameText>.json --out-dir out/
Sanity-check against sample_data/ in the repo, which has a synthetic
fixture in the exact expected shape.

STEP 3 — Analyze and report back to me:
  python3 optimize_workers.py out/pals.json coverage
  python3 optimize_workers.py out/pals.json rank handcraft --top 15
  python3 optimize_workers.py out/pals.json team --size 15 \
      --works handcraft mining transport kindling watering
Show me the coverage table, the best pals for each major job, and a
suggested 15-slot base roster. Also confirm how many pals came through and
what work types were discovered (1.0 changed the suitability system, so
the work-type list is derived from the data, not hardcoded).

Important: verify before trusting. Spot-check 2-3 pals' extracted numbers
against what I see in-game and tell me if anything is off. Attach or paste
out/pals.csv so I have the full table.
```

---

## Notes for you (not part of the prompt)

- The prompt is deliberately extractor-agnostic with a fallback chain,
  because we don't yet know which CLI cleanly handles the 1.0 paks. If the
  local agent reports back what worked, tell me and I'll harden
  `parse_pals.py` for that exact output shape.
- If the local agent's extractor emits a non-FModel JSON shape, the
  fastest path is to have it paste one sample row here so I can add a
  small adapter rather than guessing.
- Everything the local agent needs is on the pushed branch
  `claude/palworld-pal-data-mining-jvkii0`, so it only needs repo access,
  not our chat.
