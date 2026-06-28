# HOI4 Memory & Mod Maintenance Toolkit

A community-oriented toolkit for keeping Hearts of Iron IV cheats and mods alive
across game patches. It grew out of the reality that the long-running Recifense
Cheat Engine table stopped being maintained at game version 1.16.9, while HOI4
keeps shipping updates (1.19 as of mid-2026). Every patch shifts code in
`hoi4.exe`, breaking the byte-pattern signatures that memory cheats rely on, and
flags Workshop mods as "incompatible."

This repo doesn't pretend to fully automate reverse engineering — that part is
inherently manual and happens against your live game. What it does is make the
repeatable parts repeatable, and give you a documented, scriptable workflow so a
post-patch fix takes minutes of guided work instead of hours of guessing.

## What's inside

Three tracks, one repo:

1. **Memory signatures** (`lua/`, `data/`) — Cheat Engine Lua scripts that tell
   you which cheat signatures broke after a patch, help you relocate them, and
   generate fresh patch-tolerant signatures. Baseline catalog extracted from the
   1.11.10 Recifense table.

2. **Mod maintenance** (`tools/mod_*.py`, `docs/MODS.md`) — bump Workshop mods'
   `supported_version` so the launcher stops flagging them, and scan an enabled
   playset for the file-override conflicts that cause most "it broke after the
   update" reports.

3. **Watchers & debugging** (`tools/hoi4_log_watch.py`, `docs/DEBUGGING.md`) —
   tail and parse HOI4's own error/game logs, group errors by cause, and collect
   crash dumps so conflicts and missing-file regressions surface immediately.

## Quick start

```text
After a game patch:
  1. lua/healthcheck.lua   -> see which cheats broke
  2. lua/find_player_base.lua + CE GUI -> relocate the anchor struct
  3. lua/aobgen.lua        -> mint new signatures for the broken scans
  4. tools/mod_version_bump.py -> clear the launcher's version warnings
  5. tools/mod_conflict_scan.py + tools/hoi4_log_watch.py -> hunt conflicts
```

Each Lua script has a usage header. Each Python tool supports `--help`.

## Requirements

- Cheat Engine 7.4+ (for the Lua memory tools)
- Python 3.9+ (for the mod / log tools; standard library only, no pip installs)

## Status

Early scaffold (v0.1). See `PLAN.md` for the roadmap and `CONTRIBUTING.md` for
how the pieces fit together. MIT licensed — built to be shared and forked.

## Disclaimer

For single-player / local use with your own legally-owned copy of the game.
Memory editing and modding single-player games is the intent here; don't use any
of this to interfere with other players or online services.
