# Methodology — relocating broken cheats after a patch

This is the guided workflow the Lua scripts support. It assumes Cheat Engine
7.4+ and that you can load a HOI4 save (so all the relevant systems are actually
in memory).

## 0. Setup

In Cheat Engine: **Table → Lua Engine**. Set the toolkit path once per session:

```lua
TOOLKIT_DIR = [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
```

Attach CE to `hoi4.exe` and load a save before scanning.

## 1. Triage — what actually broke

```lua
dofile(TOOLKIT_DIR..[[\lua\healthcheck.lua]])
```

You get one line per cheat: `[ ok ]`, `[warn]` (pattern matches more than once —
needs lengthening), or `[FAIL]` (gone — needs relocating). The three **anchor**
scans are flagged: fix those first, because most other cheats are just offsets
off the anchors.

## 2. Relocate the anchor (player struct)

The player struct (`pPlayer`) is the backbone. To find it from a known value:

```lua
dofile(TOOLKIT_DIR..[[\lua\find_player_base.lua]])
pbFirst(700000)   -- Political Power is stored x1000, so 700 PP -> 700000
-- spend or gain PP in-game so the number changes, then:
pbNext(685000)
-- repeat pbNext(<current value>) until pbList() shows a handful of addresses
pbList()
```

Then in the CE GUI: right-click a surviving address → **Find out what accesses
this address** → trigger it in-game (open the politics screen). In the access
list you'll see an instruction like `mov [rax+000000C8],ecx`. The base register
(`rax` here) is a pointer into the player struct. Cross-check against
`data/signatures.lua → M.knownOffsets`:

```
player.political_power = [[pPlayer+0xEA0]+0xC8]
```

So `rax` = `[pPlayer+0xEA0]`, and you can walk back one indirection to `pPlayer`.
Once you have a reliable pointer to `pPlayer`, the PP / stability / war support /
command power / XP cheats all reuse it via their offsets.

## 3. Mint a fresh signature for the injection point

Once you've found the instruction you want to hook (from step 2's "what accesses"
window, or "what writes"), note its address and:

```lua
AOBGEN_ADDR = "hoi4.exe+1A2B3C4"   -- the instruction's address
AOBGEN_LEN  = 24
dofile(TOOLKIT_DIR..[[\lua\aobgen.lua]])
```

`aobgen` reads the bytes, wildcards the displacement of any relative
call/jmp/jcc (those move between patches), and grows the pattern until it's
unique inside `hoi4.exe`. Paste the printed signature into your table's
`AOBScanModule(SYMBOL,$process, ...)`.

## 4. Re-verify

Re-run `healthcheck.lua`. The symbol you just fixed should flip to `[ ok ]`.
Repeat for each broken cheat. Start from anchors outward — many "broken" cheats
resolve themselves once the struct pointer is correct.

## Which offsets tend to survive a patch?

- **Struct field offsets** (e.g. PP at `+0xC8` within its sub-object) are usually
  stable across minor patches — Paradox rarely reorders existing fields.
- **Code signatures** (the byte patterns) break easily, because any added/removed
  instruction nearby shifts everything.

That asymmetry is why the strategy is: relocate a *pointer* once via a value
scan, then lean on stored offsets, rather than re-finding every cheat's code
pattern from scratch.

## Safety

- Work on a copy of your save. Bad writes can corrupt a campaign.
- Keep a per-version record: when you confirm new patterns, add them to
  `data/` alongside the baseline so future diffs show exactly what moved.
