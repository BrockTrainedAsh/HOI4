---
description: Dry-run a supported_version bump for all enabled mods
argument-hint: [target-version e.g. 1.19.*]
allowed-tools: Bash(python3:*)
model: haiku
---
!`python3 tools/mod_version_bump.py --hoi4-dir "$HOME/Documents/Paradox Interactive/Hearts of Iron IV" --to "${ARGUMENTS:-1.19.*}" --dry-run`

Report what would change. Tell the user to re-run without --dry-run to apply
(backups are written automatically).
