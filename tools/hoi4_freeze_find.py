#!/usr/bin/env python3
"""
hoi4_freeze_find.py - find the REAL Political Power address by freeze-testing.
Freezing is proven to hold (a per-entity value stayed at 999 against the game's regen),
so the real PP is the address that, when frozen to a distinctive value, makes the BAR
read it. Pipeline: snapshot doubles near PP -> keep the ones that ROSE (real, changing,
not static look-alikes) -> freeze each to 7000 and OCR the PP slot -> the one that moves
the bar is the authoritative PP.

    python hoi4_freeze_find.py
"""
import array
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402

POKE = 7000.0


def ocr_pp():
    for _ in range(8):
        shot = M.SHOTDIR / "ffp.png"
        M._ps("screencap.ps1", "-Out", str(shot), "-H", "90")
        r = M._ps("ocr.ps1", "-Path", str(shot), "-X", "190", "-Y", "0", "-W", "130", "-H", "90")
        txt = (r.stdout or "").strip().replace(",", "").upper()
        m = re.search(r"\d+", txt)
        if m and "K" not in txt:
            return int(m.group())
    return None


def main():
    pp = ocr_pp()
    if not pp:
        M.log("freeze_find: no PP read"); return
    lo, hi = pp - 3, pp + 25
    M.log(f"freeze_find: PP={pp}; snapshot doubles in [{lo},{hi}]")
    k, h, _ = M.attach(write=True)
    snap = {}
    for base, rsize, _p in M.iter_regions(k, h):
        if rsize > 64 * 1024 * 1024:
            continue
        off = 0
        while off < rsize:
            n = min(M.CHUNK, rsize - off)
            d = M.read_bytes(k, h, base + off, n)
            if d:
                da = array.array("d")
                da.frombytes(d[:len(d) // 8 * 8])
                for i, v in enumerate(da):
                    if lo <= v <= hi:
                        snap[base + off + i * 8] = v
            off += n
    M.log(f"  snapshot {len(snap)}; waiting 12s for PP to rise...")
    time.sleep(12)
    pp2 = ocr_pp() or pp
    risers = []
    for a, v in snap.items():
        d = M.read_bytes(k, h, a, 8)
        if d and len(d) >= 8:
            nv = struct.unpack("<d", d)[0]
            if 0.03 <= (nv - v) <= (pp2 - pp + 6):
                risers.append(a)
    (M.ROOT / "logs" / "pp_copies.json").write_text(json.dumps({"addrs": [hex(a) for a in risers]}))
    M.log(f"  saved {len(risers)} PP-tracking copies to logs/pp_copies.json (for the debugger)")
    if "--copies-only" in sys.argv:
        k.CloseHandle(h); return
    M.log(f"  PP {pp}->{pp2}; {len(risers)} rising candidates; freeze-testing vs the bar...")
    poke = struct.pack("<d", POKE)
    w = M.ctypes.c_size_t(0)
    real = []
    for a in risers[:100]:
        orig = M.read_bytes(k, h, a, 8)
        if not orig:
            continue
        end = time.time() + 0.6
        while time.time() < end:
            k.WriteProcessMemory(h, M.ctypes.c_void_p(a), poke, 8, M.ctypes.byref(w))
        seen = ocr_pp()
        k.WriteProcessMemory(h, M.ctypes.c_void_p(a), orig, 8, M.ctypes.byref(w))  # restore
        if seen and seen >= 5000:
            real.append(a)
            M.log(f"  *** REAL PP @ 0x{a:X} (bar showed {seen} when frozen) ***")
    if real:
        M.log("FOUND real PP: " + ", ".join(f"0x{a:X}" for a in real))
        (M.ROOT / "logs" / "pp_real.json").write_text(json.dumps(
            {"addr": hex(real[0]), "type": "double", "size": 8}))
    else:
        M.log("  none of the rising candidates moved the bar - PP's displayed value is "
              "computed from a source not in this set; need the code hook.")
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
