#!/usr/bin/env python3
"""
mod_version_bump.py - clear the launcher's "made for an older version" (warning
triangle) by rewriting the mods' supported game version.

There are TWO places HOI4 records a mod's supported version, and they must agree
for the triangle to clear:

  1. The descriptor *.mod files in the HOI4 user 'mod' folder (`supported_version`).
     The GAME reads these at launch. Bumping them stops the *game* from complaining.
  2. The Paradox launcher's own database, launcher-v2.sqlite (`mods.requiredVersion`).
     The LAUNCHER UI reads THIS, not the *.mod files, to draw the warning triangle.

By default this tool only rewrites the *.mod descriptors (#1). That makes the game
happy but, on the launcher-v2 client, the triangle persists because the launcher
trusts its cached DB (#2). Pass --sync-launcher-db to also update the DB so the
flags actually clear in the launcher.

IMPORTANT for --sync-launcher-db: the Paradox launcher must be COMPLETELY CLOSED
first. While it is open it holds the DB and will overwrite your change on exit (or
the write will fail with "database is locked"). A timestamped .bak of the DB is
written before any change. Steam Workshop content is never touched.

Examples:
    python tools/mod_version_bump.py --to "1.19.*" --dry-run
    python tools/mod_version_bump.py --to "1.19.*"
    python tools/mod_version_bump.py --to "1.19.*" --sync-launcher-db --dry-run
    python tools/mod_version_bump.py --to "1.19.*" --sync-launcher-db   # launcher closed!
    python tools/mod_version_bump.py --hoi4-dir "D:/Docs/Paradox Interactive/Hearts of Iron IV" --to "1.19.*"

Always run with --dry-run first to see what would change.
"""
import argparse
import re
import shutil
import sqlite3
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


def find_launcher_db(hoi4_dir: Path) -> Path:
    return hoi4_dir / "launcher-v2.sqlite"


def sync_launcher_db(db_path: Path, target: str, dry_run: bool, make_backup: bool):
    """Update mods.requiredVersion in launcher-v2.sqlite so the launcher's
    'made for an older version' triangle clears.

    Returns (report, error) where report is a list of (label, old, new) tuples
    and error is None or a human-readable string. The launcher must be closed for
    a non-dry-run write to stick.
    """
    if not db_path.is_file():
        return None, f"launcher DB not found at {db_path}"

    # Compute changes from a read-only connection (safe even if launcher is open).
    try:
        ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = ro.execute(
            "SELECT id, COALESCE(displayName, name, CAST(steamId AS TEXT), "
            "CAST(pdxId AS TEXT), 'mod') AS label, requiredVersion FROM mods"
        ).fetchall()
        ro.close()
    except sqlite3.Error as e:
        return None, f"could not read launcher DB: {e}"

    changes = [(rid, label, rv) for (rid, label, rv) in rows if (rv or "") != target]
    report = [(label, rv if rv is not None else "(none)", target)
              for (_rid, label, rv) in changes]

    if dry_run or not changes:
        return report, None

    if make_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(db_path, db_path.with_suffix(db_path.suffix + f".{stamp}.bak"))

    try:
        con = sqlite3.connect(str(db_path), timeout=2)
        with con:
            con.executemany("UPDATE mods SET requiredVersion=? WHERE id=?",
                            [(target, rid) for (rid, _l, _rv) in changes])
        con.close()
    except sqlite3.OperationalError as e:
        return report, (f"launcher DB is locked ({e}). Close the Paradox Launcher "
                        f"completely (check the system tray / Task Manager for "
                        f"'Paradox Launcher.exe'), then re-run.")
    return report, None


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
    ap.add_argument("--sync-launcher-db", action="store_true",
                    help="also update mods.requiredVersion in launcher-v2.sqlite "
                         "so the launcher triangle clears (launcher must be CLOSED)")
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

    print("\nsummary (*.mod descriptors): "
          + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    if args.sync_launcher_db:
        db_path = find_launcher_db(hoi4_dir)
        print(f"\n{'DRY RUN: ' if args.dry_run else ''}launcher DB: {db_path}")
        report, err = sync_launcher_db(db_path, args.to, args.dry_run,
                                       not args.no_backup)
        if report is None:
            print(f"  [ERR  ] {err}")
        elif not report:
            print("  [ ok  ] all mods already requiredVersion = " + args.to)
        else:
            verb = "would set" if args.dry_run else "set"
            for label, old, new in report:
                print(f"  [{'would' if args.dry_run else 'fixed'}] {label}: "
                      f"{old} -> {new}")
            print(f"  summary (launcher DB): {verb} {len(report)} mod(s) "
                  f"to {args.to}")
            if err:
                print(f"  [ERR  ] {err}")
            elif not args.dry_run:
                print("  Restart the Paradox Launcher to see the triangles clear.")
    else:
        print("\nNote: the launcher triangle is driven by launcher-v2.sqlite, not "
              "the *.mod files. Re-run with --sync-launcher-db (launcher closed) "
              "to clear it.")

    if args.dry_run:
        print("\nre-run without --dry-run to apply.")


if __name__ == "__main__":
    main()
