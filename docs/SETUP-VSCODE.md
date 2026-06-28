# Continuing in VS Code

Everything below is run on your Windows machine. The repo lives at:

```
%USERPROFILE%\Documents\My Cheat Tables\HOI4-Memory-Toolkit
```

## 1. One-time: initialize git

The sandbox couldn't init git (filesystem limits), so do it once natively:

```powershell
cd "$env:USERPROFILE\Documents\My Cheat Tables\HOI4-Memory-Toolkit"
powershell -ExecutionPolicy Bypass -File .\init-repo.ps1
```

This cleans up the incomplete `.git`, initializes on branch `main`, and makes the
first commit.

## 2. Open it in VS Code

```powershell
code "$env:USERPROFILE\Documents\My Cheat Tables\HOI4-Memory-Toolkit\HOI4-Memory-Toolkit.code-workspace"
```

If `code` isn't recognized, open VS Code once, press `Ctrl+Shift+P`, run
"Shell Command: Install 'code' command in PATH", then retry. Or just use
File → Open Workspace from File… and pick the `.code-workspace`.

## 3. Install the recommended extensions

VS Code will pop up "This workspace has extension recommendations" — click Install
All. Or from PowerShell:

```powershell
code --install-extension anthropic.claude-code
code --install-extension ms-python.python
code --install-extension sumneko.lua
code --install-extension charliermarsh.ruff
```

## 4. Bring Claude into VS Code

After the Claude Code extension installs, reload VS Code. Then either:

- Open the Command Palette (`Ctrl+Shift+P`) and run a **Claude Code** command, or
- Open the integrated terminal (`` Ctrl+` ``) and run `claude` (if the Claude Code
  CLI is installed).

The agent reads `CLAUDE.md` at the repo root for project context and rules, so it
will understand the three tracks and the stdlib-only / safe-by-default conventions
without re-explaining.

## 5. Run the tools (PowerShell, from the repo root)

```powershell
$HOI4 = "$env:USERPROFILE\Documents\Paradox Interactive\Hearts of Iron IV"

# Watch / parse the game's error log (one-shot)
python tools\hoi4_log_watch.py --hoi4-dir $HOI4

# Live tail while playing (Ctrl-C to stop)
python tools\hoi4_log_watch.py --hoi4-dir $HOI4 --follow

# Find mod override conflicts (resolves your F:\ workshop paths natively)
python tools\mod_conflict_scan.py --hoi4-dir $HOI4

# Mod version flags (already applied once; dry-run shows current state)
python tools\mod_version_bump.py --hoi4-dir $HOI4 --to "1.19.*" --dry-run
```

Requirements: Python 3.9+ (`python --version`). No `pip install` needed — the
tools are standard-library only.

## 6. Cheat Engine Lua tools

These run inside Cheat Engine, not VS Code (edit them in VS Code, run them in CE).
In CE: Table → Lua Engine, then:

```lua
TOOLKIT_DIR = [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
dofile(TOOLKIT_DIR..[[\lua\healthcheck.lua]])
```

## 7. Publish to GitHub (optional, for the community)

```powershell
# create an EMPTY repo at https://github.com/new named HOI4-Memory-Toolkit, then:
git remote add origin https://github.com/<your-user>/HOI4-Memory-Toolkit.git
git push -u origin main
```

## Known issue flagged by the toolkit (2026-06-28)

`UTTNH_2.0` overrides `common/units/` with a pre-1.19 set and breaks the new
`category_regimental_support_battalions` referenced by vanilla `fire_support.txt`
and the land doctrines. Until an updated UTTNH ships, expect ~78 unit/doctrine
errors; disabling UTTNH clears them. Re-run `hoi4_log_watch.py` after any change.
