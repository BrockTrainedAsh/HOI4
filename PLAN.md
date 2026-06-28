# Roadmap & Plan

This is the working plan for the toolkit. It covers three tracks that share one
goal: keep HOI4 cheats and mods working as the game updates, and make problems
visible fast.

## Guiding constraints (read first)

- **Reverse engineering can't be fully automated.** Finding where a value lives
  in `hoi4.exe` after a patch requires scanning the live process and reading
  disassembly. The toolkit accelerates and documents this; it does not replace
  the human step.
- **Mods are data, not code.** Workshop mods are text/asset overrides. Keeping
  them working is a *file* problem (version tags, override conflicts, vanilla
  drift) — very tractable and scriptable, unlike memory cheats.
- **The game already tells us when it's unhappy.** HOI4 writes error and game
  logs and crash dumps. Watching them turns "it crashed" into an actionable line
  number and file path.

## Track 1 — Memory signatures (Cheat Engine)

Goal: when a patch breaks the cheat table, regenerate it in minutes.

Done (v0.1):
- `data/signatures.lua` / `.json` — baseline catalog of all 26 scan signatures
  + known struct offsets, extracted from the 1.11.10 Recifense table.
- `lua/healthcheck.lua` — reports broken / ambiguous / resolved signatures.
- `lua/find_player_base.lua` — guided value-scan to relocate the player struct.
- `lua/aobgen.lua` — generate unique, patch-tolerant signatures from an address.
- `docs/METHODOLOGY.md` — the end-to-end manual+scripted workflow.

Next:
- [ ] Capture new 1.19 signatures for the anchor scans (MOHP/MOSF/MOSR) and the
      high-value cheats (PP, research, focus, manpower, god mode).
- [ ] `lua/build_table.lua` — emit a ready-to-load `.CT` from `signatures.lua`
      once new patterns are confirmed, so rebuilding is one click.
- [ ] Pointer-map doc: stable struct offsets vs. ones that drift between patches.
- [ ] Per-version signature history in `data/` so we can diff what moved.

## Track 2 — Mod maintenance

Goal: stop the launcher from flagging mods, and catch the conflicts that break
saves after an update.

Done (v0.1):
- `tools/mod_version_bump.py` — rewrite `supported_version` in mod descriptors
  (with backups) so the ⚠ "made for an older version" flags clear.
- `tools/mod_conflict_scan.py` — find vanilla files overridden by more than one
  enabled mod (the classic conflict source), report load-order-sensitive wins.
- `docs/MODS.md` — per-mod notes for the current playset + workflow.

Next:
- [ ] `tools/vanilla_diff.py` — diff a mod's overridden files against the current
      vanilla files to see what drifted in the patch (needs game install path).
- [ ] Playset importer: read the launcher's `dlc_load.json` / playset DB so the
      conflict scan reflects exactly what's enabled, in order.
- [ ] Track which mods are pure-data (safe across patches) vs. ones touching
      defines/GUI that need re-checking every update.

## Track 3 — Watchers & debugging

Goal: surface crashes, errors, and conflicts the moment they happen.

Done (v0.1):
- `tools/hoi4_log_watch.py` — one-shot scan or live `--follow` of the HOI4 logs;
  groups errors by category (missing file, parse error, broken reference, etc.),
  and collects crash dumps into one folder for review.
- `docs/DEBUGGING.md` — where the logs live and how to read them.

Next:
- [ ] Error-signature catalog: map common log lines to likely causes / mods.
- [ ] `--watch-table` mode: warn if a CE cheat writes to an address that the
      health check later finds relocated (stale-pointer guard).
- [ ] Optional desktop notification on new crash/error during a session.

## Track 4 — Packaging for the community

- [ ] GitHub repo with this layout; Issues for per-version signature requests.
- [ ] A "post-patch checklist" release doc.
- [ ] Versioned releases pinned to game versions (e.g. `hoi4-toolkit-1.19`).
- [ ] Keep the Cheat Engine `.CT` deliverables (WASD camera, console helpers) in
      `tables/` so non-technical users get a ready file without running scripts.

## Open questions for the maintainer (Brock)

- Which folder holds your HOI4 user data + Workshop mods? The mod and log tools
  need read access to it (see each tool's `--help` for the default Windows path).
- Do you want the rebuilt cheats shipped as a standalone `.CT`, or merged into
  Fuwa's console-extension table as the base?
