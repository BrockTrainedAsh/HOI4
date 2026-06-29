# Reverse-engineering findings — HOI4 1.19.1.0 (Operation Postern)

Hard-won facts from live analysis (`tools/hoi4_mem.py`, `hoi4_dbg.py`, `hoi4_accum.py`).

## Storage / encoding
- **Political Power is a `double`** (8-byte float), not `int × 1000`. Every pre-1.19
  table assumes int×1000 → all fail (the 1.11.10 Recifense AOBs score 0/26). The
  *displayed* PP is computed/copied: doubles that equal & track it exist, but writing
  them does nothing (the HUD value is recomputed). Same likely for the other HUD totals.
- HUD digits OCR reliably only after **3× upscaling the crop** (`tools/ocr.ps1`).

## Module base
- `hoi4.exe` loaded at **`0x7FF786A20000`** across multiple restarts (fixed base / no
  exe ASLR observed). So `hoi4.exe + RVA` absolute addresses are stable between runs.

## Found instruction — per-entity regen (God-Mode candidate)
A multiply-accumulate that rewrites a per-entity value every tick (org/strength/xp-like;
values seen 95→114, regenerating). Found by `hoi4_accum.py` (catch accumulating doubles)
+ `hoi4_dbg.py trace --write` (the breakpoint reported the *next* instruction, so the
writer is the MOVSD just before it):

```
RVA 0x22649D3:  F2 0F 59 46 78     MULSD  XMM0, [RSI+0x78]
RVA 0x22649D8:  F2 0F 58 C7        ADDSD  XMM0, XMM7
RVA 0x22649DC:  F2 0F 11 46 68     MOVSD  [RSI+0x68], XMM0   <-- writes the value
RVA 0x22649E1:  33 DB              XOR    EBX, EBX
RVA 0x22649E3:  8B 86 CC 00 00 00  MOV    EAX, [RSI+0xCC]    ; count
                48 8B 86 C0 00 00 00  MOV RAX,[RSI+0xC0]     ; array ptr (sub-entities)
                F3 0F 10 8B D8..      MOVSS XMM1,[RBX+0xD8]  ; sub-entity field
```
`RSI` = the entity struct: value at **+0x68**, sub-count at **+0xCC**, sub-array ptr at
**+0xC0**, sub-field at **+0xD8**. AOB for the writer (wildcard the disp if needed):
`F2 0F 11 46 68 33 DB 8B 86 CC 00 00 00`.

## Tooling state
- `hoi4_dbg.py` "find what accesses" **works** (16-byte-aligned CONTEXT was the fix) but
  **crashes the game** — arming hardware breakpoints across ~100 threads (suspend/resume
  churn) destabilizes HOI4 even with a verified clean detach. Use it sparingly, or do the
  find-what-writes in Cheat Engine (mature debugger) and bring the instruction here.
- Reading code/memory and computing RVAs is **safe** (no crashes) — prefer it.

## Next (careful)
Turn the writer into a cheat via **AOB code-injection** (the proven trainer method):
back up the 5 original bytes, allocate a cave, `push`/`pop` to preserve registers, force
`[RSI+0x68]` to a max constant, `jmp` back. Identify the value first (is it org/strength
worth maxing). High-risk on a live game — gate behind a save + a one-keystroke restore.
