# Maintenance run log

Record of orchestrated `/run-all` maintenance passes. Newest first.

---

## 2026-06-28 — full toolkit pass (HOI4 1.19)

Target HOI4 user dir: `C:\Users\Brock\Documents\Paradox Interactive\Hearts of Iron IV`
(the C: Documents folder — **not** the `$HOME/...` default in the slash command).
Workshop: `F:/SteamLibrary/steamapps/workshop/content/394360` · Vanilla:
`F:/SteamLibrary/steamapps/common/Hearts of Iron IV`.

### Phase 1 — diagnostics
| Tool | Result |
|---|---|
| `hoi4_log_watch.py` | 279 error/warning lines. `parse_error ×42` + `broken_ref ×36` = the real bug (regimental categories). `texture_gfx ×141` / `missing_file ×30` / `other ×30` = cosmetic, from **GEO World War 2 Models Mod** (missing `.anim`/`.dds`/entity attachments). |
| `mod_conflict_scan.py` | No file-override conflicts among the 8 enabled mods. |
| `mod_version_bump.py --to 1.19.* --dry-run` | All 8 descriptors already `1.19.*` — bump was applied in a prior run (`.bak` files dated `20260628-190537`). |

Enabled playset (load order): Unlimited Dockyards · Improved vanilla technology
icons · Expanded tank designer · GEO WW2 Models · Majors Tank Blueprints ·
Unlimited Factory Slot · WASD Move (1.15+) · **UTTNH_2.0**.

### Phase 2 — fix applied
**Root cause:** `UTTNH_2.0` (`ugc_3413890094`) overrides
`common/unit_tags/00_categories.txt` with a stale copy missing **6** sub-unit
categories that HOI4 1.19 defines. Vanilla `common/units/fire_support.txt` and the
land doctrine files (`grand_doctrines/land_grand_doctrines.txt`,
`subdoctrines/land/*`) reference those categories → 78 "Invalid subunit category" /
"Unexpected token" errors.

> The `/run-all` plan blamed UTTNH's `common/units` override; the evidence shows the
> culprit is its `common/unit_tags` override. No enabled mod touches `fire_support.txt`
> at all — that file is vanilla.

**Action:** backed up
`…/394360/3413890094/common/unit_tags/00_categories.txt` →
`…00_categories.txt.20260628-135103.bak`, then **additively** inserted the 6 missing
vanilla categories before the closing brace, preserving UTTNH's 3 mod-added
helicopter categories:
`category_marines_and_amphibious`, `category_divisional_support_battalions`,
`category_regimental_support_battalions`, `category_tank_destroyer_regimental_support`,
`category_self_propelled_anti_air_regimental_support`,
`category_regimental_support_artillery`.

**Verified at source:** UTTNH now defines every vanilla 1.19 category (the
missing-set is empty), helicopters intact, braces balanced. The static diff is the
meaningful confirmation — `error.log` only updates when the game runs, so the
error-count drop must be confirmed by relaunching HOI4.

**Caveat — non-durable:** this edits Steam Workshop content. A UTTNH update or Steam
"Verify integrity of game files" will revert it; re-apply from the `.bak` or re-run
`/run-all`. A local override mod (provide a corrected `00_categories.txt` loaded
after UTTNH) would survive Steam — switch to that if UTTNH updates often.

### Phase 3 — Cheat Engine memory track (prepared only)
CE cannot run headless. The exact, script-grounded relocation runbook for the 1.19
patch is in **`docs/CE-RELOCATION-1.19.md`** (health check → MOHP/MOSF/MOSR anchor
relocation → high-value cheats → regenerate `data/signatures.*`). Run it in CE when
you next want the cheat table rebuilt.

### Needs the maintainer
- [ ] **Relaunch HOI4 1.19**, then re-run `/watch-logs` — expect the regimental
  `parse_error`/`broken_ref` buckets (~78 lines) to clear.
- [ ] (Optional) The cosmetic GEO-models errors (missing animations/textures/entities)
  are harmless; clean up only if the visual glitches bother you.
- [ ] **Cheat Engine relocation** per `docs/CE-RELOCATION-1.19.md` (requires the
  running game + CE).
- [ ] Decide durability of the UTTNH fix (workshop edit vs. local override mod).
- [ ] Mirror repos: out of scope until specs are provided.

### Guardrails honored
Backup before edit; no files deleted; no force-push; version-bump left as a dry-run
(already applied); CE not run.
