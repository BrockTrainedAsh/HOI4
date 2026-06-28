#!/usr/bin/env python3
"""
mod_version_bump.py - clear the launcher's "made for an older version" (warning
triangle) by rewriting `supported_version` in HOI4 mod descriptors.

The Paradox launcher flags a mod whenever its descriptor's supported_version
doesn't cover the running game version. Often the mod still works fine and the
tag is just stale. This rewrites the tag (with a backup) so the flags clear.

It edits the descriptor *.mod files in the HOI4 user 'mod' folder (the ones the
launcher reads). It does NOT touch read-only Steam Workshop content.

Examples:
    python tools/mod_version_bump.py --to "1.19.*" --dry-run
    python tools/mod_version_bump.py --to "1.19.*"
    python tools/mod_version_bump.py --hoi4-dir "D:/Docs/Paradox Interactive/Hearts of Iron IV" --to "1.19.*"

Always run with --dry-run first to see what would change.
"""
import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SUPPORTED_RE = re.compile(r'(supported_version\s*=\s*")([^"]*)(")')


def default_hoi4_dir() -> Path:
    return Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV"


def find_descriptors(hoi4_dir: Path):
    mod_dir = hoi4_dir / "mod"
    if not mod_dir.is_dir():
        return []
    # The launcher reads the *.mod files directly in the mod/ folder.
    return sorted(mod_dir.glob("*.mod"))


def process(path: Path, target: str, dry_run: bool, make_backup: bool):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return ("error", f"could not read: {e}", None)

    m = SUPPORTED_RE.search(text)
    name_m = re.search(r'name\s*=\s*"([^"]*)"', text)
    name = name_m.group(1) if name_m else path.stem

    if not m:
        # Some descriptors omit the tag entirely; add one after name= if present.
        if name_m:
            insert_at = name_m.end()
            new_text = text[:insert_at] + f'\nsupported_version="{target}"' + text[insert_at:]
            old_val = "(none)"
        else:
            return ("skip", f"{name}: no supported_version and no name= to anchor", None)
    else:
        old_val = m.group(2)
        if old_val == target:
            return ("ok", f"{name}: already {target}", None)
        new_text = text[:m.start()] + m.group(1) + target + m.group(3) + text[m.end():]

    if dry_run:
        return ("would", f"{name}: {old_val} -> {target}", None)

    if make_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_suffix(path.suffix + f".{stamp}.bak")
        shutil.copy2(path, backup)

    path.write_text(new_text, encoding="utf-8")
    return ("changed", f"{name}: {old_val} -> {target}", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hoi4-dir", default=str(default_hoi4_dir()),
                    help="HOI4 user-data folder (contains the 'mod' folder)")
    ap.add_argument("--to", required=True,
                    help='target supported_version, e.g. "1.19.*"')
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would change without writing")
    ap.add_argument("--no-backup", action="store_true",
                    help="do not write .bak backups (not recommended)")
    args = ap.parse_args()

    hoi4_dir = Path(args.hoi4_dir).expanduser()
    descriptors = find_descriptors(hoi4_dir)
    if not descriptors:
        sys.exit(f"No *.mod descriptors found in {hoi4_dir / 'mod'} "
                 f"(check --hoi4-dir).")

    print(f"{'DRY RUN: ' if args.dry_run else ''}target supported_version = {args.to}")
    print(f"scanning {len(descriptors)} descriptor(s) in {hoi4_dir / 'mod'}\n")

    counts = {}
    for d in descriptors:
        status, msg, _ = process(d, args.to, args.dry_run, not args.no_backup)
        counts[status] = counts.get(status, 0) + 1
        prefix = {"changed": "[fixed]", "would": "[would]", "ok": "[ ok  ]",
                  "skip": "[skip ]", "error": "[ERR  ]"}.get(status, "[ ?   ]")
        print(f"  {prefix} {msg}")

    print("\nsummary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if args.dry_run:
        print("re-run without --dry-run to apply.")


if __name__ == "__main__":
    main()
