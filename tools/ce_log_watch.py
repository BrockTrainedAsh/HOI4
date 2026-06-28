#!/usr/bin/env python3
"""
ce_log_watch.py - read and interpret the Cheat Engine console-cheat log.

tables/HOI4 Console Cheats.CT writes a timestamped step-by-step log (HC.log) to
logs/ce-console.log. This reads that log and tells you WHERE the cheats are
failing, so you don't have to eyeball raw lines. Run it after using the table's
[ DIAGNOSTICS ] entry.

It answers the questions that matter:
  - Did the engine load?           (engine ready)
  - Did focus detection work?      (focused=true ever seen after Alt-Tab)
  - Did key DETECTION work?        (isKeyPressed(W)=true ever seen)
  - Did commands get sent?         (send: DONE lines)
  - What is the verdict?           (a plain-language diagnosis)

Examples:
    python3 tools/ce_log_watch.py
    python3 tools/ce_log_watch.py --follow
    python3 tools/ce_log_watch.py --file "D:/somewhere/ce-console.log"
"""
import argparse
import re
import sys
import time
from pathlib import Path


def default_logfile() -> Path:
    return Path(__file__).resolve().parent.parent / "logs" / "ce-console.log"


# (label, matcher) - order matters for the summary.
SIGNALS = [
    ("engine_ready",   re.compile(r"engine ready")),
    ("diag_run",       re.compile(r"=+ DIAGNOSTICS")),
    ("not_attached",   re.compile(r"not attached to a process")),
    ("focus_true",     re.compile(r"focused\s*=\s*true", re.I)),
    ("focus_false",    re.compile(r"focused\s*=\s*false", re.I)),
    ("pid_match_true", re.compile(r"MATCH:\s*true")),
    ("pid_match_false",re.compile(r"MATCH:\s*false")),
    ("wkey_true",      re.compile(r"isKeyPressed\(W\)\s*=\s*true")),
    ("queued",         re.compile(r"^\[.*\]\s*queued:")),
    ("send_open",      re.compile(r"send: opening console|\[DRAIN\] start")),
    ("send_done",      re.compile(r"send: DONE|\[DRAIN\] done")),
    ("errors",         re.compile(r"\[ERR\]")),
    ("capped",         re.compile(r"capped to in-game max")),
    ("cancelled",      re.compile(r"cancelled|is not a number")),
]


def scan(lines):
    counts = {label: 0 for label, _ in SIGNALS}
    for ln in lines:
        for label, rx in SIGNALS:
            if rx.search(ln):
                counts[label] += 1
    return counts


def verdict(c):
    out = []
    if c["engine_ready"] == 0:
        out.append("X engine never logged 'ready' - tick [ ACTIVATE FIRST ] (and reload the .CT).")
    if c["not_attached"]:
        out.append("X Cheat Engine is NOT attached to hoi4.exe - open the process in CE first.")
    if c["diag_run"] and c["focus_true"] == 0:
        out.append("X focus detection FAILED - HOI4 never read as the active window after Alt-Tab. "
                   "getForegroundWindow/getWindowProcessID may be returning wrong values on your CE.")
    if c["focus_true"] and c["send_done"] == 0 and c["queued"]:
        out.append("! reached focus but never sent - dispatcher may not be firing.")
    if c["send_done"] and c["wkey_true"] == 0 and c["diag_run"]:
        out.append("! commands were SENT and keys were injected, but isKeyPressed(W) never went true - "
                   "if nothing changed in-game, HOI4 is likely ignoring synthetic key input "
                   "(=> the keystroke approach can't work; use the memory/CE-relocation cheats instead).")
    if c["focus_true"] and c["send_done"]:
        out.append("OK focus + send path executed. If still nothing in-game: wrong console key (HC.GRAVE) "
                   "or the command/alias changed - check the test-1/test-2 answers you reported.")
    if not out:
        out.append("… not enough signal yet. Run the table's [ DIAGNOSTICS ] entry, Alt-Tab to HOI4, "
                   "press W a few times, then re-run this.")
    return out


SUMMARY_RE = re.compile(r"DIAGSUMMARY\s+(.*)$")
ERR_RE = re.compile(r"\[ERR\]\s+(.*)$")


def parse_summary(lines):
    """Parse the last 'DIAGSUMMARY key=val key=val ...' line into a dict, or None."""
    found = None
    for ln in lines:
        m = SUMMARY_RE.search(ln)
        if m:
            found = m.group(1)
    if not found:
        return None
    out = {}
    for tok in found.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def parse_errors(lines):
    return [m.group(1) for ln in lines for m in [ERR_RE.search(ln)] if m]


def structured_verdict(s, errors):
    """Verdict from the machine-readable DIAGSUMMARY (auto-detectable facts)."""
    out = []
    if s.get("attached") == "false":
        out.append("X CE is NOT attached to hoi4.exe - open the process in CE first.")
    for api in ("api_fgwin", "api_iskey", "api_inputquery", "api_timer"):
        if api in s and s[api] != "function":
            out.append(f"X CE API missing: {api}={s[api]} (expected 'function') - update Cheat Engine.")
    if s.get("focus_seen") == "false":
        out.append("X focus never detected after Alt-Tab - HC.focused() is misreading your CE; "
                   "the dispatcher will never fire.")
    if s.get("wkey_seen") == "false":
        out.append("! isKeyPressed(W) never went true - either W wasn't pressed during the watch, "
                   "or key DETECTION is broken (WASD would fail too).")
    if errors:
        out.append(f"X {len(errors)} caught error(s): " + "  ||  ".join(errors[-3:]))
    if not out:
        out.append(f"OK auto-checks pass (attached + focus + key-detect + APIs; hold={s.get('hold')}ms). "
                   "The remaining unknowns are USER-OBSERVED: did the map pan up, and did PP rise by 1? "
                   "If PP did NOT rise, the key hold is still too short - raise HC.HOLD (e.g. 100) and re-test.")
    return out


def summarize(path: Path):
    if not path.is_file():
        print(f"No log yet at {path}\n"
              f"  Load the .CT, tick [ ACTIVATE FIRST ], then [ DIAGNOSTICS ], Alt-Tab to HOI4.")
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    c = scan(lines)
    summary = parse_summary(lines)
    errors = parse_errors(lines)
    print(f"CE console log: {path}  ({len(lines)} lines)\n")
    if summary:
        print("  DIAGSUMMARY (machine-read):")
        for k, v in summary.items():
            print(f"    {k:16} {v}")
    if errors:
        print("\n  caught errors:")
        for e in errors[-6:]:
            print(f"    {e}")
    print("\n  last 10 lines:")
    for ln in lines[-10:]:
        print(f"    {ln}")
    print("\n  VERDICT:")
    vs = structured_verdict(summary, errors) if summary else verdict(c)
    for v in vs:
        print(f"    {v}")


def follow(path: Path):
    print(f"following {path} (Ctrl-C to stop)...")
    while not path.is_file():
        time.sleep(0.5)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.3)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=None, help="path to ce-console.log (default: ../logs/ce-console.log)")
    ap.add_argument("--follow", action="store_true", help="live-tail the log instead of summarizing")
    args = ap.parse_args()

    path = Path(args.file).expanduser() if args.file else default_logfile()
    try:
        if args.follow:
            follow(path)
        else:
            summarize(path)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
