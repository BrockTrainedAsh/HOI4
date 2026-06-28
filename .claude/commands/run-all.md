---
description: Ultracode — full HOI4 toolkit diagnostics + fix pass, orchestrated across subagents
argument-hint: [optional HOI4 user folder]
model: opus
---
# Ultracode: full HOI4 toolkit run

Orchestrate the complete maintenance pass autonomously. Run independent steps in
PARALLEL by dispatching the project subagents; keep a running summary. Read CLAUDE.md
and PLAN.md first for goals and conventions.

Paths:
- Repo: this folder.
- HOI4 user dir: ${ARGUMENTS:-$HOME/Documents/Paradox Interactive/Hearts of Iron IV}
- Workshop: F:/SteamLibrary/steamapps/workshop/content/394360
- Vanilla:  F:/SteamLibrary/steamapps/common/Hearts of Iron IV

## Phase 0 - Verify environment (sequential)
- Confirm `python --version` works and the tools/ scripts exist.
- Confirm the subagents (log-watcher, error-fixer, signature-finder) and the slash
  commands (/watch-logs, /scan-conflicts, /bump-versions, /healthcheck) are available.

## Phase 1 - Diagnostics (PARALLEL)
Dispatch concurrently:
- log-watcher subagent: run tools/hoi4_log_watch.py against the HOI4 dir; categorize.
- a worker to run tools/mod_conflict_scan.py and
  tools/mod_version_bump.py --to 1.19.* --dry-run.
Collect all findings before Phase 2.

## Phase 2 - Fix (after Phase 1)
Dispatch the error-fixer subagent on the top confirmed issue
(UTTNH_2.0 -> category_regimental_support_battalions): locate the mod's
common/units override under the workshop path, diff against vanilla, and either
add the missing 1.19 category (writing a *.bak backup first) or recommend disabling
UTTNH if no safe fix exists. Re-run the log watcher to confirm the error count dropped.

## Phase 3 - Memory track (prepare only)
Dispatch the signature-finder subagent to output the exact Cheat Engine Lua Engine
steps for lua/healthcheck.lua and anchor relocation. Do NOT attempt to run CE.

## Phase 4 - Commit
git add -A; commit with a clear message summarizing the pass; git push.

## Guardrails
Back up any file before editing. Never delete files or force-push without asking.
Do not silently break Ironman/achievements. Mirror repos are out of scope (awaiting
specs). End with a concise report: what changed, what is confirmed fixed, and what
still needs me.
