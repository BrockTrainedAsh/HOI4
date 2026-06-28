# Cheat target catalog

The feature list below is the **target spec** for what we want working on the
current game version. It's taken from the WeMod (MrAntiFun) HOI4 trainer's public
feature list, used here purely as a checklist of desirable cheats.

Important: WeMod's trainer is closed-source and also memory-based. We do **not**
copy their code or signatures — we use their feature *list* as our goal and find
our own signatures with the toolkit (`docs/METHODOLOGY.md`), or implement the
effect via the in-game console where one exists.

Two routes to each cheat:
- **memory** — hook/edit `hoi4.exe` (durable feature, breaks on patch, needs
  re-finding). Maps to a Recifense baseline symbol where one already exists.
- **console** — type a command (works in any non-Ironman game; in Ironman after
  Fuwa's enabler). Fast to ship; some effects have no console equivalent.

> Console command *names* drift between versions — verify syntax in-game before
> relying on it. Names below are best-known, not guaranteed for 1.19.

> **Machine-readable catalog:** `data/wemod_targets.json` (regenerate with
> `python3 tools/extract_baseline.py --targets-only`) is the source of truth for the
> route/baseline/console of every target. The per-feature Cheat Engine checklist is
> `docs/CE-RELOCATION-1.19.md` §6. The symbols below are approximate; the catalog
> uses the authoritative `MO**` Recifense symbols.

## Player

| Feature | Baseline sym | Route | Status | Notes |
|---|---|---|---|---|
| Fast Research | MRP | memory / console (`research_on_icon_click`) | baseline-known | |
| Super Production | PNP/PP1 | memory | baseline-known | no clean console cmd |
| Fast Construction | MCP | memory / console (`instantconstruction`) | baseline-known | console toggle confirmed (builds instantly, incl. ships) |
| Set Command Power | MPC | memory / console (`add_command_power`) | baseline-known | offset player+0x1C4 |
| Unlimited Convoy | — | memory / console (`add_equipment N convoy`) | NEW target | |
| Fast National Focus | MFP | memory / console (`fa` / focus.autocomplete) | baseline-known | |
| Unlimited Resources | MMR | memory | baseline-known | |
| Unlimited Organization | GMD-ish | memory | NEW target | WeMod splits this out from God Mode |
| Unlimited Vehicles Fuel | — | memory / console (`fuel`?) | NEW target | verify console cmd |
| God Mode | GMD/GMS/GS2 | memory | baseline-known | |
| Instant Movement | MAM/AM1 | memory | baseline-known | |
| Enable Ironman Console | (Fuwa) | memory patch | available via Fuwa | use Fuwa's extension table |
| Instant Agency Construction | MAC | memory | baseline-known | |
| Instant Agency Upgrade | MAU | memory | baseline-known | |
| Instant Agency Operatives | MOR | memory | baseline-known | |
| Instant Intel Network | MNP | memory | baseline-known | |
| Instant Intel Ops Prepare | MOP | memory | baseline-known | |
| Instant Intel Op Execute | OPH | memory | baseline-known | |
| Unlimited Breakthroughs | — | memory | NEW target | combat stat |
| Instant Prototype | — | memory | NEW target | |
| Instant Special Project (radar, jets, nukes facility) | — | memory | NEW target | AAT facility research; `complete_special_project` is script-only (no console) → CE memory cheat. Scan the project's progress value. |
| Instant Intel Decrypting | MDP | memory | baseline-known | |

## Stats

| Feature | Baseline sym | Route | Status | Notes |
|---|---|---|---|---|
| Set Army Exp | MPX (part) | memory / console (`xp N`) | baseline-known | player+0x1E0 |
| Set Navy Exp | MPX (part) | memory / console (`xp N`) | baseline-known | player+0x1F8 |
| Set Air Exp | MPX (part) | memory / console (`xp N`) | baseline-known | player+0x210 |

(Recifense sets all three XP pools together; WeMod exposes them separately —
same three offsets, just individual setters.)

## Weapons

| Feature | Baseline sym | Route | Status | Notes |
|---|---|---|---|---|
| Unlimited Nukes | — | memory / console (`add_nukes`?) | NEW target | verify console cmd |

## Game

| Feature | Baseline sym | Route | Status | Notes |
|---|---|---|---|---|
| Unlimited ManPower | MMM | memory / console (`manpower N`) | baseline-known | |
| Set Political Power | MPP | memory / console (`add_political_power N`) | baseline-known | [[player+0xEA0]+0xC8] |
| No World Tension | — | memory / console (`set_world_tension 0`?) | NEW target | |
| Unlimited Stability | MSY | memory / console (`add_stability`?) | baseline-known | player+0xFA8 |
| Low Occupation Resistance | — | memory / console (`resistance`?) | NEW target | |
| Instant War Goal | — | console (`add_wargoal`?) | NEW target | likely console-only |
| Fast Recruiting | — | memory | NEW target | |
| War Support (Recifense extra) | MWS | memory | baseline-known | player+0xFAC |
| Weak Foe (Recifense extra) | MWF | memory | baseline-known | not in WeMod list |

## Summary

- **Already in baseline (signatures known for 1.11.10, need relocating):** ~19 of
  the WeMod features map directly onto Recifense symbols. The toolkit's
  healthcheck + re-anchor flow handles these.
- **NEW targets (no baseline signature — find from scratch):** Unlimited Convoy,
  Unlimited Organization (standalone), Unlimited Vehicles Fuel, Unlimited
  Breakthroughs, Instant Prototype, Unlimited Nukes, No World Tension, Low
  Occupation Resistance, Instant War Goal, Fast Recruiting.
- **Quick wins via console (no memory work):** PP, manpower, XP, command power,
  national focus, convoys/equipment — shippable as console-button entries in the
  table right now, for non-Ironman or with Fuwa's enabler.

Next step for this track: once attached to the live 1.19 game, run
`lua/healthcheck.lua`, relocate the anchors, and tick these off one by one. Keep
this table updated with the new signatures as they're confirmed.
