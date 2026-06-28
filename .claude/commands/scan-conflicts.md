---
description: Scan the enabled HOI4 playset for mod file-override conflicts
argument-hint: [hoi4-user-folder]
allowed-tools: Bash(python3:*), Read
model: sonnet
---
!`python3 tools/mod_conflict_scan.py --hoi4-dir "${ARGUMENTS:-$HOME/Documents/Paradox Interactive/Hearts of Iron IV}"`

Explain which mods overlap and which wins under load order. Cross-reference with the
latest log watcher output to point at the real culprit.
