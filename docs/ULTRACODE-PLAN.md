# Ultracode run plan

A single orchestrated pass that runs the whole toolkit from your Claude Code
terminal. Two ways to launch it:

1. **Slash command** (preferred): open Claude Code at the repo root and type
   `/run-all`. Optionally pass your HOI4 folder: `/run-all C:\Users\Brock\Documents\Paradox Interactive\Hearts of Iron IV`.
2. **Paste prompt**: paste the block below into the session.

The orchestration dispatches the project subagents (log-watcher, error-fixer,
signature-finder), runs independent steps in parallel, fixes the confirmed mod
conflict, prepares the Cheat Engine steps, and commits.

## What it does, phase by phase

- **Phase 0 — Verify**: python works; subagents and slash commands are loaded.
- **Phase 1 — Diagnostics (parallel)**: log-watcher parses the error log; a worker
  runs the conflict scan and a version-bump dry-run.
- **Phase 2 — Fix**: error-fixer tackles the top issue (UTTNH_2.0 →
  `category_regimental_support_battalions`), backs up, patches or recommends
  disabling, then re-checks the logs.
- **Phase 3 — Memory (prepare only)**: signature-finder emits the exact CE Lua
  Engine steps (CE can't run headless).
- **Phase 4 — Commit**: stage, commit, push.

## Guardrails

Backups before edits; no deletes or force-push without asking; Ironman/achievements
not broken silently; mirror repos out of scope until specs are provided.

## Paste-able prompt

```text
Ultracode: run the full HOI4 toolkit maintenance pass autonomously. Read CLAUDE.md
and PLAN.md first. Run independent steps in PARALLEL via the project subagents and
keep a running summary.

Paths: HOI4 user dir = $HOME/Documents/Paradox Interactive/Hearts of Iron IV;
Workshop = F:/SteamLibrary/steamapps/workshop/content/394360;
Vanilla = F:/SteamLibrary/steamapps/common/Hearts of Iron IV.

Phase 0 (sequential): confirm python runs and tools/ scripts exist; confirm the
log-watcher, error-fixer, signature-finder subagents and the slash commands load.

Phase 1 (parallel): dispatch log-watcher to run tools/hoi4_log_watch.py and
categorize; in parallel run tools/mod_conflict_scan.py and
tools/mod_version_bump.py --to 1.19.* --dry-run. Gather findings.

Phase 2 (after 1): dispatch error-fixer on UTTNH_2.0 ->
category_regimental_support_battalions: find the mod's common/units override under
the workshop path, diff vs vanilla, and either add the missing 1.19 category (with a
*.bak backup) or recommend disabling UTTNH. Re-run the log watcher to confirm fewer
errors.

Phase 3 (prepare only): dispatch signature-finder to output the exact Cheat Engine
Lua Engine steps for lua/healthcheck.lua and anchor relocation. Do NOT run CE.

Phase 4: git add -A; commit with a clear summary; git push.

Guardrails: back up before editing; never delete or force-push without asking; don't
silently break Ironman/achievements; mirror repos are out of scope. End with a concise
report of what changed, what's confirmed fixed, and what still needs me.
```
