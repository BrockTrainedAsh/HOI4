#!/usr/bin/env python3
"""
mod_conflict_scan.py - find file-override conflicts between enabled HOI4 mods.

Most "my save broke after the patch / after adding a mod" problems come from two
mods replacing the same vanilla file, or a mod replacing a file the patch
restructured. This walks each enabled mod's content folder and reports every
relative game path that more than one mod provides, plus which mod "wins" given
the load order (in HOI4 the mod loaded later overrides earlier ones).

Source of truth for what's enabled + order: dlc_load.json in the HOI4 user dir.
Each enabled entry points at a *.mod descriptor whose `path=`/`archive=` gives the
content folder (local or Steam Workshop).

Examples:
    python tools/mod_conflict_scan.py
    python tools/mod_conflict_scan.py --hoi4-dir "D:/Docs/Paradox Interactive/Hearts of Iron IV"
    python tools/mod_conflict_scan.py --all          # scan every installed mod, not just enabled
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Vanilla content roots a mod can override (anything outside these is ignored,
# e.g. descriptor.mod, thumbnail.png, .git).
CONTENT_DIRS = {
    "common", "events", "history", "gfx", "interface", "localisation",
    "localization", "map", "music", "sound", "tutorial", "portraits",
    "gui", "dlc", "decisions", "ai_focuses",
}


def default_hoi4_dir() -> Path:
    return Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV"


def parse_descriptor(mod_file: Path):
    """Return (name, content_path) from a *.mod descriptor, or (name, None)."""
    try:
        text = mod_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (mod_file.stem, None)
    name_m = re.search(r'name\s*=\s*"([^"]*)"', text)
    name = name_m.group(1) if name_m else mod_file.stem
    # Prefer an unpacked path=; fall back to archive= (zip) which we can't walk.
    path_m = re.search(r'path\s*=\s*"([^"]*)"', text)
    if path_m:
        return (name, Path(path_m.group(1)))
    arch_m = re.search(r'archive\s*=\s*"([^"]*)"', text)
    if arch_m:
        return (name, Path(arch_m.group(1)))  # zip; flagged later
    return (name, None)


def enabled_mod_files(hoi4_dir: Path):
    """Return ordered list of *.mod descriptor Paths from dlc_load.json."""
    dlc_load = hoi4_dir / "dlc_load.json"
    if not dlc_load.is_file():
        return None
    try:
        data = json.loads(dlc_load.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    out = []
    for rel in data.get("enabled_mods", []):
        out.append(hoi4_dir / rel)        # e.g. "mod/ugc_123.mod"
    return out


def all_mod_files(hoi4_dir: Path):
    mod_dir = hoi4_dir / "mod"
    return sorted(mod_dir.glob("*.mod")) if mod_dir.is_dir() else []


def collect_files(content_path: Path):
    """Relative game paths a mod provides (under known content dirs)."""
    files = set()
    if content_path is None or not content_path.is_dir():
        return files
    for root_dir in CONTENT_DIRS:
        base = content_path / root_dir
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if f.is_file():
                files.add(f.relative_to(content_path).as_posix())
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hoi4-dir", default=str(default_hoi4_dir()))
    ap.add_argument("--all", action="store_true",
                    help="scan every installed mod instead of only the enabled playset")
    args = ap.parse_args()

    hoi4_dir = Path(args.hoi4_dir).expanduser()

    if args.all:
        mod_files = all_mod_files(hoi4_dir)
        order_note = "(all installed mods; load order not applied)"
    else:
        mod_files = enabled_mod_files(hoi4_dir)
        order_note = "(enabled playset, in load order; later wins)"
        if mod_files is None:
            sys.exit(f"Could not read {hoi4_dir/'dlc_load.json'}. "
                     f"Use --all or check --hoi4-dir.")
    if not mod_files:
        sys.exit("No mods found to scan.")

    # name -> (order_index, set_of_files)
    mods = []
    zip_mods = []
    for idx, mf in enumerate(mod_files):
        name, content = parse_descriptor(mf)
        if content is not None and content.suffix.lower() == ".zip":
            zip_mods.append(name)
            files = set()
        else:
            files = collect_files(content)
        mods.append((name, files))

    print(f"Conflict scan {order_note}")
    print(f"mods scanned: {len(mods)}\n")
    if zip_mods:
        print("note: these mods are packed as .zip and were not walked "
              "(unpack to scan): " + ", ".join(zip_mods) + "\n")

    # Invert: file -> [mod indices providing it]
    providers = {}
    for i, (name, files) in enumerate(mods):
        for f in files:
            providers.setdefault(f, []).append(i)

    conflicts = {f: idxs for f, idxs in providers.items() if len(idxs) > 1}
    if not conflicts:
        print("No file-override conflicts found among the scanned mods.")
        return

    # Group conflicts by the set of mods involved for readable output.
    by_group = {}
    for f, idxs in conflicts.items():
        key = tuple(idxs)
        by_group.setdefault(key, []).append(f)

    print(f"Found {len(conflicts)} conflicting file(s) "
          f"across {len(by_group)} mod-pair group(s):\n")
    for key, files in sorted(by_group.items(), key=lambda kv: -len(kv[1])):
        names = [mods[i][0] for i in key]
        winner = mods[key[-1]][0] if not args.all else "(load order unknown)"
        print(f"* {len(files)} file(s) overridden by: {' + '.join(names)}")
        print(f"    winner under load order: {winner}")
        for f in sorted(files)[:12]:
            print(f"      {f}")
        if len(files) > 12:
            print(f"      ... and {len(files) - 12} more")
        print()

    print("Tip: conflicts aren't always bad (intentional patches/compat mods),")
    print("but after a game update they are the first place to look. Cross-check")
    print("the winners against error.log via tools/hoi4_log_watch.py.")


if __name__ == "__main__":
    main()
