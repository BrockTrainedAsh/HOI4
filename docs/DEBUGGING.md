# Debugging — watchers, logs, and crashes

HOI4 is fairly chatty about its own problems. Most "it broke after the update"
and mod-conflict issues show up in the logs before they show up as a crash.

## Where to look (Windows defaults)

```
Logs:     %USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\logs\
Crashes:  %USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\crashes\
```

Key log files:

- `error.log` — the important one. Missing files, broken references, parse
  errors. After a patch or a mod change, this is the first stop.
- `game.log` — general lifecycle; useful for "where did it get to before dying."
- `setup.log` / `system.log` — startup and environment.
- `text.log` — localization key problems (missing/duplicate keys).

## The watcher

`tools/hoi4_log_watch.py` reads these and turns raw lines into grouped causes.

```bash
# One-shot summary of the latest error.log
python tools/hoi4_log_watch.py --hoi4-dir "<...>"

# Live tail while you play / load a save (Ctrl-C to stop)
python tools/hoi4_log_watch.py --hoi4-dir "<...>" --follow

# Pull any crash dumps into one folder for review / sharing
python tools/hoi4_log_watch.py --hoi4-dir "<...>" --collect-crashes ./crash-collected
```

It buckets lines into categories — missing file, parse/token error, broken
reference, texture/GFX, localization, save/checksum — and prints counts plus a
few representative examples per bucket. That maps directly onto mod problems:

- **missing file / broken reference** → a mod points at a vanilla file the patch
  renamed or removed (vanilla drift), or a mod was partially updated.
- **parse / unexpected token** → a mod's syntax no longer matches the new schema
  for that file (defines/equipment changes are common culprits).
- **texture / GFX** → an asset mod referencing a sprite that moved.

## Turning a log line into a fix

1. Run the watcher; note the category and the file/path in the message.
2. Cross-reference `tools/mod_conflict_scan.py` output: is that file overridden by
   one of your mods? If two mods touch it, you found the conflict.
3. If it's vanilla drift (mod overrides a file the patch changed), the mod needs
   its copy reconciled with the new vanilla version (`vanilla_diff.py`, planned).
4. Re-launch, re-watch, confirm the line is gone.

## Crashes

Crash dumps (`.dmp`) land in the `crashes\` folder, each in a timestamped
subfolder with a `meta.yml`. `--collect-crashes` copies them somewhere central so
you can keep a history and attach them to bug reports. Full symbolized analysis of
a `.dmp` needs Paradox's symbols (not public), so the practical signal is: which
mods were enabled, what the last `error.log` lines were, and whether disabling the
highest-risk mod (per `docs/MODS.md`) stops it.
