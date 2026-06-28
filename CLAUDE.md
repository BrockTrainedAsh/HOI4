# CLAUDE.md — agent context for this repo

Context for an AI coding agent (e.g. Claude Code in VS Code) working in this
repository. Read this first.

## What this project is

A toolkit to keep Hearts of Iron IV cheats and mods working across game patches.
Three technical domains live here; keep them separated:

1. **Cheat Engine memory work** (`lua/`, `data/`) — Lua run *inside* Cheat Engine
   against the live `hoi4.exe`. You cannot run or test these from the agent
   sandbox; they require CE + the running game. Treat them as carefully-reviewed
   source, validate by reading, and rely on the maintainer to run them in CE.
2. **Mod maintenance** (`tools/mod_*.py`) — operate on HOI4 mod files on disk.
   Testable with sample data; safe-by-default (dry-run + backups).
3. **Log/crash watching** (`tools/hoi4_log_watch.py`) — read-only over the HOI4
   logs folder.

## Hard rules

- **Python = standard library only.** No pip dependencies. Anyone should run the
  tools with a bare Python 3.9+. If you think you need a package, don't — solve it
  with the stdlib or raise it in PLAN.md first.
- **Destructive ops default to safe.** Anything that writes to mod files must keep
  `--dry-run` and write `.bak` backups. Never delete game/mod files.
- **Never commit copyrighted content.** No vanilla game files, no full mod
  payloads. Only signatures, offsets, scripts, and docs. `.gitignore` enforces
  most of this — keep it current.
- **Data is generated.** `data/signatures.lua` comes from
  `tools/extract_baseline.py`. Edit the feature map in that script and regenerate;
  don't hand-edit the generated file.
- **Lua targets Cheat Engine 7.x**, not standalone Lua. Globals like `AOBScan`,
  `readBytes`, `createMemScan`, `process` are provided by CE (declared in
  `.vscode/settings.json` so the Lua LSP stops flagging them).

## Where things are

See `CONTRIBUTING.md` for the full tree. Start points:
- New game version broke cheats → `docs/METHODOLOGY.md`, `lua/healthcheck.lua`.
- Mod flagged / conflicting → `docs/MODS.md`, `tools/mod_*.py`.
- Crash / errors → `docs/DEBUGGING.md`, `tools/hoi4_log_watch.py`.

## Paths the tools need (not in the repo)

The mod/log tools read the HOI4 user-data folder (default
`~/Documents/Paradox Interactive/Hearts of Iron IV`). Pass `--hoi4-dir` to point
elsewhere. The agent sandbox will not have this folder mounted unless the
maintainer connects it.

## Definition of done for a change

- `--help` works and is accurate for any tool you touch.
- Destructive paths still default to dry-run + backup.
- No new third-party imports.
- Docs in `docs/` updated if behavior changed.
