---
description: Run the HOI4 log watcher and summarize problems + likely mod
argument-hint: [hoi4-user-folder]
allowed-tools: Bash(python3:*), Read, Grep
model: sonnet
---
Run the watcher (defaults to the standard HOI4 user folder if no argument given):

!`python3 tools/hoi4_log_watch.py --hoi4-dir "${ARGUMENTS:-$HOME/Documents/Paradox Interactive/Hearts of Iron IV}"`

Then summarize the categories, and for the biggest clusters name the most likely
offending mod. If a fix is needed, recommend delegating to the error-fixer agent.
