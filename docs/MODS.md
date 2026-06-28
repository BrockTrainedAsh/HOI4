# Mod maintenance

Workshop mods are data overrides, not memory cheats, so keeping them working is a
file problem we can actually script. There are three failure modes after a patch:

1. **Version flag only** — the launcher shows ⚠ because the mod's
   `supported_version` lists an older patch. Very often the mod still works; the
   fix is bumping the tag. → `tools/mod_version_bump.py`.
2. **Override conflict** — two enabled mods replace the same vanilla file, or a
   mod replaces a file the patch restructured. This is the usual cause of broken
   saves / missing UI / crashes. → `tools/mod_conflict_scan.py`, plus the logs.
3. **Vanilla drift** — the mod overrides a file Paradox changed, so the mod's old
   copy reintroduces removed content. → `vanilla_diff.py` (planned).

## Where the files live (Windows defaults)

```
Descriptors / local mods:  %USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\mod\
Enabled playset + order:   ...\Hearts of Iron IV\dlc_load.json  (and launcher DB)
Workshop content:          <Steam>\steamapps\workshop\content\394360\<id>\
```

Point the tools at the user-data folder with `--hoi4-dir` (see `--help`).

## Current playset (from the launcher, INITIAL PLAYSET — Mods: 8)

| # | Mod | Ver | Notes |
|---|-----|-----|-------|
| 1 | Unlimited Dockyards "PER_LINE" | 1.0 | Cheat-style data mod. Small; usually just needs a version bump. |
| 2 | Improved vanilla technology icons | 1.2 | Pure GFX. Low risk across patches. |
| 3 | Expanded tank designer | 0.2 | Touches tank designer data — re-check on patches that change armor/equipment. |
| 4 | GEO World War 2 Models Mod | 0.1 | Large 3D models/GFX. Asset-only; low logic risk. |
| 5 | Majors Tank Blueprints | 4.0 | Blueprint/preset data. Re-check if equipment archetypes change. |
| 6 | Unlimited Factory Slot | 1.15.2 | Edits building/defines. **Higher risk** — defines move between patches. |
| 7 | WASD Move (1.15+) | 2 | Camera WASD via mod. Overlaps the CE WASD toggle (see note). |
| 8 | UTTNH_2.0 (tech tree) | 1 | Large tech-tree overhaul. **Highest risk** — overrides lots of vanilla. |

Priority for re-checking after a patch: **#8 UTTNH**, then **#6 Unlimited
Factory Slot**, then **#3 / #5** (designer/blueprint data). Asset-only mods
(#2, #4) and tiny cheat mods (#1, #7) are usually fine with a version bump.

## Note on WASD

You already run **WASD Move (1.15+)** as a Workshop mod *and* now have the
version-independent WASD toggle in the Cheat Engine table. They do the same job
by different means:

- The **mod** is cleaner in normal play but disables achievements/Ironman
  (any enabled mod does) and breaks if the patch changes camera input handling.
- The **CE toggle** works in Ironman and survives patches, but only while CE is
  attached.

Pick one per playstyle; no need to run both. For Ironman/achievement runs, prefer
the CE toggle and disable the mod.

## Typical workflow after a patch

```bash
# 1. Clear version flags (dry-run first!)
python tools/mod_version_bump.py --hoi4-dir "<...>" --to 1.19.* --dry-run
python tools/mod_version_bump.py --hoi4-dir "<...>" --to 1.19.*

# 2. Find override conflicts in the enabled set
python tools/mod_conflict_scan.py --hoi4-dir "<...>"

# 3. Launch, then watch the logs for what actually breaks
python tools/hoi4_log_watch.py --hoi4-dir "<...>" --follow
```
