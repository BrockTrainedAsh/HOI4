#!/usr/bin/env python3
"""
extract_baseline.py  -  Build the baseline signature catalog for the toolkit.

Parses a Recifense-style Cheat Engine table (.CT) and pulls out every
AOBScanModule(symbol, $process, pattern) entry, pairing each symbol with a
human-readable feature description. Emits:

    data/signatures.lua    - canonical catalog consumed by the CE Lua scripts
    data/signatures.json   - same data, portable for tooling / diffing
    data/wemod_targets.lua  - the WeMod feature wishlist + coverage map
    data/wemod_targets.json - same, portable

The WeMod target map (WEMOD_TARGETS below) is the toolkit's goal list: every
cheat from the WeMod/MrAntiFun HOI4 trainer (see docs/CHEAT-TARGETS.md), mapped
to the Recifense baseline symbol and/or in-game console command that implements
it. It is STATIC (no game files, no copying WeMod's code) so it can be emitted
without a .CT via --targets-only.

This is a *build-time* helper. The live memory-finding tools are Lua (see lua/).
You only re-run this when you want to regenerate the baseline from a known-good
table for a new game version.

Usage:
    python tools/extract_baseline.py "../Hearts of Iron IV.CT"
    python tools/extract_baseline.py path/to/table.CT --game-version 1.19.1
    python tools/extract_baseline.py --targets-only      # just the WeMod catalog
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

# --------------------------------------------------------------------------- #
# WeMod feature wishlist -> implementation route (docs/CHEAT-TARGETS.md).
#
# Each target says HOW we intend to deliver that cheat:
#   route    : "memory" | "console" | "memory+console" | "external"
#   baseline : Recifense scan symbol that implements it (matches FEATURES /
#              data/signatures), or "" if it hangs off pPlayer via an offset,
#              or None for a brand-new target with no baseline yet.
#   offset   : KNOWN_OFFSETS key when the cheat is just a pPlayer field write.
#   console  : best-known HOI4 console command (NAMES DRIFT between patches --
#              always verify in-game; "?" suffix = unverified for 1.19).
#   status   : "baseline" (signature exists, just relocate) |
#              "new"      (no baseline signature, find from scratch in CE) |
#              "console"  (ship as a console helper, no memory work needed) |
#              "external" (provided by another tool, e.g. Fuwa's Ironman enabler)
#
# We use WeMod's feature *list* as a checklist only. No WeMod code/signatures.
# --------------------------------------------------------------------------- #
def _t(feature, route, status, baseline=None, offset=None, console=None, notes=""):
    return {"feature": feature, "route": route, "status": status,
            "baseline": baseline, "offset": offset, "console": console, "notes": notes}

WEMOD_TARGETS = [
    # --- Player ---
    _t("Fast Research", "memory+console", "baseline", baseline="MORP",
       console="research_on_icon_click"),
    _t("Super Production (equipment + ships)", "memory", "baseline", baseline="MOPP",
       notes="ships share MPP1; no clean console command"),
    _t("Fast Construction", "memory+console", "baseline", baseline="MOCP",
       console="instantconstruction", notes="console toggle builds instantly incl. ships"),
    _t("Set Command Power", "memory+console", "baseline", baseline="MOHP",
       offset="player.command_power", console="add_command_power <n>"),
    _t("Unlimited Convoy", "console", "console", console="add_equipment <n> convoy"),
    _t("Fast National Focus", "memory+console", "baseline", baseline="MOFP",
       console="focus.autocomplete"),
    _t("Unlimited Resources", "memory", "baseline", baseline="MOMR"),
    _t("Unlimited Organization (standalone)", "memory", "new",
       notes="WeMod splits this out from God Mode; relates to GDMD org write"),
    _t("Unlimited Vehicles Fuel", "memory+console", "new", console="fuel?",
       notes="verify console command for 1.19"),
    _t("God Mode (army + ships)", "memory", "baseline", baseline="GDMD",
       notes="also GMDS (ship strength) + GDS2 (ship org)"),
    _t("Instant Movement", "memory", "baseline", baseline="MOAM",
       notes="also MAM1 during battle"),
    _t("Enable Ironman Console", "external", "external",
       notes="use Fuwa's Ironman-enabler extension table"),
    _t("Instant Agency Construction", "memory", "baseline", baseline="MOAC"),
    _t("Instant Agency Upgrade", "memory", "baseline", baseline="MOAU"),
    _t("Instant Agency Operatives", "memory", "baseline", baseline="MOOR"),
    _t("Instant Intel Network", "memory", "baseline", baseline="MONP"),
    _t("Instant Intel Ops Prepare", "memory", "baseline", baseline="MOOP"),
    _t("Instant Intel Op Execute", "memory", "baseline", baseline="MOPH"),
    _t("Instant Intel Decrypting", "memory", "baseline", baseline="MODP"),
    _t("Unlimited Breakthroughs", "memory", "new", notes="combat stat, no baseline"),
    _t("Instant Special Project / Prototype (radar, jets, etc.)", "memory", "new",
       notes="AAT facility research. complete_special_project is a script-only effect "
             "(no console command), so this is a CE memory cheat: scan the project's progress value."),
    # --- Stats (all three are pPlayer fields; Recifense sets them together) ---
    _t("Set Army Exp", "memory+console", "baseline", baseline="MOHP",
       offset="player.army_xp", console="xp <n>"),
    _t("Set Navy Exp", "memory+console", "baseline", baseline="MOHP",
       offset="player.navy_xp", console="xp <n>"),
    _t("Set Air Exp", "memory+console", "baseline", baseline="MOHP",
       offset="player.air_xp", console="xp <n>"),
    # --- Weapons ---
    _t("Unlimited Nukes", "console", "console", console="add_nukes <n>"),
    # --- Game ---
    _t("Unlimited ManPower", "memory+console", "baseline", baseline="MOMM",
       console="add_manpower <n>"),
    _t("Set Political Power", "memory+console", "baseline", baseline="MOHP",
       offset="player.political_power", console="add_political_power <n>"),
    _t("Unlimited Stability", "memory+console", "baseline", baseline="MOHP",
       offset="player.stability", console="add_stability <n>"),
    _t("War Support", "memory+console", "baseline", baseline="MOHP",
       offset="player.war_support", console="add_war_support <n>"),
    _t("No World Tension", "memory+console", "new", console="set_worldtension <0-1>?",
       notes="verify console command for 1.19"),
    _t("Low Occupation Resistance", "memory+console", "new", console="resistance?",
       notes="verify console command for 1.19"),
    _t("Instant War Goal", "console", "console", console="add_wargoal <target>",
       notes="likely console-only"),
    _t("Fast Recruiting", "memory", "new"),
]


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


def _lua_field(val) -> str:
    """Render a python value as a lua literal (string or nil)."""
    if val is None:
        return "nil"
    return f'"{lua_escape(str(val))}"'


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


def write_targets(targets, out_lua: Path, out_json: Path):
    """Emit the WeMod target/coverage catalog (no .CT required)."""
    lines = []
    lines.append("-- AUTO-GENERATED by tools/extract_baseline.py -- do not edit by hand.")
    lines.append(f"-- Generated: {date.today().isoformat()}")
    lines.append("-- WeMod HOI4 feature wishlist -> route/baseline/console (docs/CHEAT-TARGETS.md).")
    lines.append("local M = {}")
    lines.append("M.targets = {")
    for t in targets:
        lines.append("  {")
        lines.append(f'    feature  = "{lua_escape(t["feature"])}",')
        lines.append(f'    route    = "{lua_escape(t["route"])}",')
        lines.append(f'    status   = "{lua_escape(t["status"])}",')
        lines.append(f'    baseline = {_lua_field(t["baseline"])},')
        lines.append(f'    offset   = {_lua_field(t["offset"])},')
        lines.append(f'    console  = {_lua_field(t["console"])},')
        lines.append(f'    notes    = "{lua_escape(t["notes"])}",')
        lines.append("  },")
    lines.append("}")
    lines.append("return M")
    out_lua.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_json.write_text(
        json.dumps({"generated": date.today().isoformat(), "targets": targets}, indent=2),
        encoding="utf-8")


def coverage_summary(targets):
    counts = {}
    for t in targets:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser(description="Extract baseline AOB catalog from a .CT")
    ap.add_argument("ct", nargs="?", help="path to the source .CT table (omit with --targets-only)")
    ap.add_argument("--game-version", default="1.11.10",
                    help="game version the baseline corresponds to")
    ap.add_argument("--outdir", default=None,
                    help="output data dir (default: ../data relative to this script)")
    ap.add_argument("--targets-only", action="store_true",
                    help="only (re)write the WeMod target catalog; no .CT needed")
    args = ap.parse_args()

    outdir = Path(args.outdir).resolve() if args.outdir else (Path(__file__).resolve().parent.parent / "data")
    outdir.mkdir(parents=True, exist_ok=True)

    # The WeMod target catalog is static -- always (re)write it.
    write_targets(WEMOD_TARGETS, outdir / "wemod_targets.lua", outdir / "wemod_targets.json")
    cov = coverage_summary(WEMOD_TARGETS)
    print(f"WeMod targets: {len(WEMOD_TARGETS)} "
          f"({', '.join(f'{k}={v}' for k, v in sorted(cov.items()))})")
    print(f"  -> {outdir / 'wemod_targets.lua'}")
    print(f"  -> {outdir / 'wemod_targets.json'}")

    if args.targets_only:
        return

    if not args.ct:
        ap.error("a .CT path is required unless --targets-only is given")

    ct_path = Path(args.ct).expanduser().resolve()
    if not ct_path.exists():
        sys.exit(f"ERROR: table not found: {ct_path}")

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
