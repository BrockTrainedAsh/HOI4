# Contributing / how the pieces fit

This repo is meant to be shared and forked. It has no build step and no
dependencies beyond Cheat Engine (for the Lua tools) and Python 3.9+ standard
library (for the mod/log tools).

## Layout

```
HOI4-Memory-Toolkit/
  README.md            overview
  PLAN.md              roadmap (4 tracks)
  LICENSE              MIT
  CLAUDE.md            project context for the Claude Code agent
  data/
    signatures.lua     baseline signature catalog (generated)
    signatures.json    same, portable
  lua/
    lib/aoblib.lua     shared CE Lua helpers
    healthcheck.lua    which signatures broke after a patch
    find_player_base.lua  guided value-scan to relocate the player struct
    aobgen.lua         mint unique patch-tolerant signatures
  tools/
    extract_baseline.py   regenerate the catalog from a known-good .CT
    mod_version_bump.py   clear launcher version flags
    mod_conflict_scan.py  find mod override conflicts
    hoi4_log_watch.py     watch/parse logs, collect crashes
  tables/              ready-to-load .CT deliverables (WASD, console helpers)
  docs/
    METHODOLOGY.md     memory relocation workflow
    MODS.md            mod maintenance + current playset notes
    DEBUGGING.md       logs & crashes
```

## Conventions

- **Lua**: pure Cheat Engine 7.x API, no external libs. Each script has a usage
  header and reads its data from `data/signatures.lua`. Keep machine-specific
  paths in the `TOOLKIT_DIR` variable at the top, never hard-coded mid-file.
- **Python**: standard library only (so anyone can run it without pip). Anything
  destructive defaults to a backup and supports `--dry-run`. Every tool supports
  `--help`.
- **Data is generated**: don't hand-edit `data/signatures.lua`; change the map in
  `tools/extract_baseline.py` and regenerate.

## Adding a new game version

1. Get a known-good table for the new version (or confirm new patterns yourself).
2. `python tools/extract_baseline.py "<that table>.CT" --game-version X.Y.Z`
3. Commit the new `data/signatures.*` alongside the old (history = what moved).
4. Note stable vs. drifting offsets in `docs/METHODOLOGY.md`.

## Pull requests

Keep changes scoped to one track where possible. Include the game version you
tested against. Don't commit copyrighted game files or full mod content — only
signatures, offsets, scripts, and docs.
