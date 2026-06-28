#!/usr/bin/env python3
"""
hoi4_log_watch.py - watch and parse HOI4's error/game logs, and collect crashes.

HOI4 writes its problems to logs before they become crashes. This reads the logs,
buckets each error line by likely cause (missing file, parse error, broken
reference, texture, localization, save/checksum), and prints counts plus a few
examples per bucket. Use it one-shot after a patch, or --follow while you play.

Examples:
    python tools/hoi4_log_watch.py
    python tools/hoi4_log_watch.py --follow
    python tools/hoi4_log_watch.py --collect-crashes ./crash-collected
    python tools/hoi4_log_watch.py --hoi4-dir "D:/Docs/Paradox Interactive/Hearts of Iron IV"
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

# Order matters: first matching category wins.
CATEGORIES = [
    ("missing_file",   ("could not find", "not found", "unable to open",
                        "does not exist", "missing", "failed to load")),
    ("parse_error",    ("unexpected token", "unexpected", "syntax error",
                        "expected", "could not parse", "parse error")),
    ("broken_ref",     ("invalid", "unknown", "undefined", "no such",
                        "references", "duplicate")),
    ("texture_gfx",    ("texture", ".dds", ".tga", "sprite", "spritetype",
                        "gfx", "mesh", "shader")),
    ("localization",   ("localization", "localisation", "loc key", "text key")),
    ("save_checksum",  ("checksum", "savegame", "save game", "out of sync",
                        "corrupt")),
]


def default_hoi4_dir() -> Path:
    return Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV"


def categorize(line: str) -> str:
    low = line.lower()
    for name, needles in CATEGORIES:
        if any(n in low for n in needles):
            return name
    return "other"


def looks_like_error(line: str) -> bool:
    low = line.lower()
    return ("error" in low or "warning" in low or "fail" in low
            or "could not" in low or "unable" in low or "missing" in low)


def scan_once(log_path: Path, max_examples: int = 4):
    if not log_path.is_file():
        print(f"  (no {log_path.name})")
        return
    buckets = {}
    total = 0
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        print(f"  could not read {log_path.name}: {e}")
        return
    for ln in lines:
        ln = ln.strip()
        if not ln or not looks_like_error(ln):
            continue
        total += 1
        cat = categorize(ln)
        b = buckets.setdefault(cat, {"count": 0, "examples": []})
        b["count"] += 1
        if len(b["examples"]) < max_examples:
            b["examples"].append(ln[:200])

    print(f"  {log_path.name}: {total} error/warning line(s)")
    for cat, b in sorted(buckets.items(), key=lambda kv: -kv[1]["count"]):
        print(f"    [{cat}] x{b['count']}")
        for ex in b["examples"]:
            print(f"        {ex}")


def follow(log_path: Path, poll: float = 1.0):
    print(f"following {log_path} (Ctrl-C to stop)...")
    last_size = log_path.stat().st_size if log_path.is_file() else 0
    try:
        while True:
            if log_path.is_file():
                size = log_path.stat().st_size
                if size < last_size:           # rotated/truncated
                    last_size = 0
                if size > last_size:
                    with log_path.open("r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        for ln in f:
                            ln = ln.strip()
                            if ln and looks_like_error(ln):
                                print(f"[{categorize(ln)}] {ln[:200]}")
                    last_size = size
            time.sleep(poll)
    except KeyboardInterrupt:
        print("\nstopped.")


def collect_crashes(hoi4_dir: Path, dest: Path):
    src = hoi4_dir / "crashes"
    if not src.is_dir():
        print(f"no crashes folder at {src}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            if not target.exists():
                shutil.copytree(item, target)
                n += 1
        else:
            shutil.copy2(item, target)
            n += 1
    print(f"collected {n} crash item(s) into {dest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hoi4-dir", default=str(default_hoi4_dir()))
    ap.add_argument("--follow", action="store_true",
                    help="live-tail error.log instead of a one-shot summary")
    ap.add_argument("--collect-crashes", metavar="DEST",
                    help="copy crash dumps into DEST and exit")
    args = ap.parse_args()

    hoi4_dir = Path(args.hoi4_dir).expanduser()
    logs = hoi4_dir / "logs"

    if args.collect_crashes:
        collect_crashes(hoi4_dir, Path(args.collect_crashes).expanduser())
        return

    if args.follow:
        follow(logs / "error.log")
        return

    if not logs.is_dir():
        sys.exit(f"No logs folder at {logs} (check --hoi4-dir).")

    print(f"HOI4 log scan: {logs}\n")
    for name in ("error.log", "game.log", "text.log", "setup.log"):
        scan_once(logs / name)
        print()
    print("Cross-reference 'missing_file' / 'broken_ref' hits against")
    print("tools/mod_conflict_scan.py to pin the offending mod.")


if __name__ == "__main__":
    main()
