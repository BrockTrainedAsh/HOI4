#!/usr/bin/env python3
"""
extract_baseline.py  -  Build the baseline signature catalog for the toolkit.

Parses a Recifense-style Cheat Engine table (.CT) and pulls out every
AOBScanModule(symbol, $process, pattern) entry, pairing each symbol with a
human-readable feature description. Emits:

    data/signatures.lua   - canonical catalog consumed by the CE Lua scripts
    data/signatures.json  - same data, portable for tooling / diffing

This is a *build-time* helper. The live memory-finding tools are Lua (see lua/).
You only re-run this when you want to regenerate the baseline from a known-good
table for a new game version.

Usage:
    python tools/extract_baseline.py "../Hearts of Iron IV.CT"
    python tools/extract_baseline.py path/to/table.CT --game-version 1.11.10
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# Human-readable purpose for each scan symbol used by the Recifense table.
# (symbol -> (feature, notes))  Keep this in sync as the table evolves.
FEATURES = {
    "MOHP": ("Human player base + Political Power / Stability / War Support / Command Power / XP",
             "Anchor scan. Resolves the player struct (pPlayer). Many cheats hang off this."),
    "MOCP": ("Construction progress (Construction in 1 day)", "Fires when the day changes."),
    "MOPP": ("Production progress (equipment/aircraft)", "Fires when the day changes."),
    "MPP1": ("Production progress (ships)", "Fires when the day changes."),
    "MPP2": ("Refitting progress (Refit in 1 day)", "Fires when the day changes."),
    "MORP": ("Research progress (Research in 1 day)", "Fires when the day changes."),
    "MOFP": ("National Focus progress (Finish focus in 1 day)", "Fires when the day changes."),
    "MOSF": ("Army/Fleet selected (pArmyFleet)", "Anchor scan for the selected unit."),
    "MOAM": ("Army/Fleet movement in 1 hour", "Movement timer."),
    "MAM1": ("Army/Fleet movement in 1 hour (during battle)", "Movement timer, combat path."),
    "MOPS": ("Fill up player squadrons", "Runs continuously."),
    "GDMD": ("God Mode (army, in battle)", "HP + Organization."),
    "GMDS": ("God Mode (ships, strength)", "Strength + manpower."),
    "GDS2": ("God Mode (ships, organization)", "Organization."),
    "MOSR": ("Province/region selected (pRegion)", "Anchor scan for the selected region."),
    "MOMR": ("Minimum natural resources (250)", "Per-hour."),
    "MOMM": ("Minimum manpower per state (7000)", "Runs continuously."),
    "MOAC": ("Agency construction in 1 day (La Resistance)", "DLC feature."),
    "MOAU": ("Agency upgrade in 1 day (La Resistance)", "DLC feature."),
    "MOOR": ("Operative recruitment in 1 day (La Resistance)", "DLC feature."),
    "MODP": ("Cipher decrypting in 1 day (La Resistance)", "DLC feature."),
    "MONP": ("Network creation progress (La Resistance)", "DLC feature."),
    "MOOP": ("Intel operation progress (La Resistance)", "DLC feature."),
    "MOPH": ("Operation phase in 3 days (La Resistance)", "DLC feature; select the Agency once."),
    "MUDP": ("Unit deployment in 1 day", "Deployment progress."),
    "MORW": ("Railway construction in 1 day", "Per-turn."),
}

# Struct offsets worth remembering for re-anchoring (extracted by hand from the
# 1.11.10 script body). These tend to survive minor patches even when the code
# signature moves, so they are gold for relocating a whole family of cheats.
KNOWN_OFFSETS = {
    "player.political_power": "[[pPlayer+0xEA0]+0xC8]  (int, x1000)",
    "player.stability":       "[pPlayer+0xFA8]  (int, x1000, 'National Unity')",
    "player.war_support":     "[pPlayer+0xFAC]  (int, x1000)",
    "player.command_power":   "[pPlayer+0x1C4]  (int, x1000)",
    "player.army_xp":         "[pPlayer+0x1E0]  (int, x32768)",
    "player.navy_xp":         "[pPlayer+0x1F8]  (int, x32768)",
    "player.air_xp":          "[pPlayer+0x210]  (int, x32768)",
    "player.id":              "[pPlayer+0x18] & 0x00FFFFFF",
    "player.field_EA0":       "pPlayer+0xEA0 -> sub-object holding PP at +0xC8",
}

SCAN_RE = re.compile(
    r"AOBScanModule\(\s*(\w+)\s*,\s*\$process\s*,\s*([0-9A-Fa-f?\s]+?)\)",
    re.DOTALL,
)


def parse_table(ct_path: Path):
    text = ct_path.read_text(encoding="utf-8", errors="replace")
    entries = []
    seen = set()
    for m in SCAN_RE.finditer(text):
        sym = m.group(1)
        pattern = " ".join(m.group(2).split()).upper()
        if sym in seen:
            continue
        seen.add(sym)
        feature, notes = FEATURES.get(sym, ("(unknown - add to FEATURES map)", ""))
        entries.append({
            "symbol": sym,
            "feature": feature,
            "notes": notes,
            "pattern": pattern,
            "byte_len": len([b for b in pattern.split()]),
            "wildcards": pattern.count("?") // 2 if "?" in pattern else 0,
            "is_anchor": sym in ("MOHP", "MOSF", "MOSR"),
        })
    return entries


def lua_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_lua(entries, offsets, out_path: Path, game_version: str):
    lines = []
    lines.append("-- AUTO-GENERATED by tools/extract_baseline.py -- do not edit by hand.")
    lines.append(f"-- Baseline game version: {game_version}")
    lines.append(f"-- Generated: {date.today().isoformat()}")
    lines.append("-- Returns a table consumed by lua/healthcheck.lua and friends.")
    lines.append("local M = {}")
    lines.append(f'M.gameVersion = "{lua_escape(game_version)}"')
    lines.append("M.signatures = {")
    for e in entries:
        lines.append("  {")
        lines.append(f'    symbol   = "{lua_escape(e["symbol"])}",')
        lines.append(f'    feature  = "{lua_escape(e["feature"])}",')
        lines.append(f'    notes    = "{lua_escape(e["notes"])}",')
        lines.append(f'    pattern  = "{lua_escape(e["pattern"])}",')
        lines.append(f'    isAnchor = {str(e["is_anchor"]).lower()},')
        lines.append("  },")
    lines.append("}")
    lines.append("M.knownOffsets = {")
    for k, v in offsets.items():
        lines.append(f'  ["{lua_escape(k)}"] = "{lua_escape(v)}",')
    lines.append("}")
    lines.append("return M")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Extract baseline AOB catalog from a .CT")
    ap.add_argument("ct", help="path to the source .CT table")
    ap.add_argument("--game-version", default="1.11.10",
                    help="game version the baseline corresponds to")
    ap.add_argument("--outdir", default=None,
                    help="output data dir (default: ../data relative to this script)")
    args = ap.parse_args()

    ct_path = Path(args.ct).expanduser().resolve()
    if not ct_path.exists():
        sys.exit(f"ERROR: table not found: {ct_path}")

    outdir = Path(args.outdir).resolve() if args.outdir else (Path(__file__).resolve().parent.parent / "data")
    outdir.mkdir(parents=True, exist_ok=True)

    entries = parse_table(ct_path)
    if not entries:
        sys.exit("ERROR: no AOBScanModule entries found - is this a Recifense-style table?")

    write_lua(entries, KNOWN_OFFSETS, outdir / "signatures.lua", args.game_version)
    (outdir / "signatures.json").write_text(
        json.dumps({"gameVersion": args.game_version,
                    "generated": date.today().isoformat(),
                    "signatures": entries,
                    "knownOffsets": KNOWN_OFFSETS}, indent=2),
        encoding="utf-8")

    print(f"Parsed {len(entries)} signatures from {ct_path.name}")
    print(f"  -> {outdir / 'signatures.lua'}")
    print(f"  -> {outdir / 'signatures.json'}")
    anchors = [e['symbol'] for e in entries if e['is_anchor']]
    print(f"  anchors: {', '.join(anchors)}")


if __name__ == "__main__":
    main()
