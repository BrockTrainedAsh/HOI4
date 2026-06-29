#!/usr/bin/env python3
"""
hoi4_find_pp.py - find the REAL Political Power address: the one whose value, when
written, actually changes the HUD (every junk buffer that merely held a PP-shaped
number is rejected). Pipeline, all measured, no AI in the loop:
  1. OCR PP, seed-scan the heap for PP*1000.
  2. Narrow over a few seconds (tolerant window so the true value survives drift).
  3. WRITE-TEST each survivor: poke a distinctive value, OCR the bar, restore.
     Only the real PP (or a live render copy) makes the bar read the poked value.
Outputs the confirmed address(es) - the anchor to FREEZE (cheat) and to TRACE
(hoi4_dbg -> pPlayer + real offsets for every other value).
"""
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402

TESTVAL = 4321          # distinctive PP value to poke (x1000 in memory)
KEEP = 120              # narrow until <= this many, then write-test
SEED_CAP = 8_000_000    # high: don't cap before the real PP's region is scanned


def ri32(k, h, a):
    d = M.read_bytes(k, h, a, 4)
    return struct.unpack("<i", d)[0] if d and len(d) >= 4 else None


def wi32(k, h, a, v):
    w = M.ctypes.c_size_t(0)
    return k.WriteProcessMemory(h, M.ctypes.c_void_p(a), struct.pack("<i", v), 4,
                                M.ctypes.byref(w)) and w.value == 4


def screencap():
    shot = M.SHOTDIR / "ft.png"
    M._ps("screencap.ps1", "-Out", str(shot), "-H", "90")
    return shot


def ocr_pp(shot):
    r = M._ps("ocr.ps1", "-Path", str(shot), "-X", "150", "-Y", "0", "-W", "230", "-H", "90")
    txt = (r.stdout or "").strip().replace(",", "").replace(".", "").upper()
    m = re.search(r"\d+", txt)
    return int(m.group()) if m and "K" not in txt else None


def main():
    time.sleep(3)                       # let window focus settle after background launch
    pp = None
    for _ in range(8):
        pp = M._ocr_pp()
        if pp:
            break
    if not pp:
        M.log("find_pp: could not OCR PP after retries"); return
    M.log(f"find_pp: OCR PP={pp}; seeding [{pp*1000},{(pp+1)*1000-1}] ...")
    k, h, _ = M.attach(write=True)
    capmb = 48 * 1024 * 1024

    lo, hi = pp * 1000, (pp + 20) * 1000 - 1   # wide: cover PP drift during the slow seed
    cands = {}
    for base, rsize, _p in M.iter_regions(k, h):
        if rsize > capmb:
            continue
        off = 0
        while off < rsize:
            n = min(M.CHUNK, rsize - off)
            d = M.read_bytes(k, h, base + off, n)
            if d:
                arr = M.array.array("i")
                arr.frombytes(d[:len(d) // 4 * 4])
                for i, v in enumerate(arr):
                    if lo <= v <= hi:
                        cands[base + off + i * 4] = v
            off += n
            if len(cands) > SEED_CAP:
                break
        if len(cands) > SEED_CAP:
            break
    M.log(f"  seed -> {len(cands)} candidates")

    for it in range(10):
        if len(cands) <= KEEP:
            break
        time.sleep(2.0)
        pp = M._ocr_pp()
        if pp is None:
            continue
        lo, hi = (pp - 2) * 1000, (pp + 4) * 1000 - 1   # tolerant: survive drift/lag
        cands = {a: nv for a in cands if (nv := ri32(k, h, a)) is not None and lo <= nv <= hi}
        M.log(f"  iter {it}: OCR PP={pp} -> {len(cands)} candidates")

    addrs = list(cands)[:KEEP]
    M.log(f"  write-testing {len(addrs)} candidates (poke {TESTVAL}, OCR, restore)...")
    real = []
    for a in addrs:
        orig = ri32(k, h, a)
        if orig is None:
            continue
        end = time.time() + 0.35          # hold the poke so the render draws it
        while time.time() < end:
            wi32(k, h, a, TESTVAL * 1000)
        shot = screencap()                # capture while the value is still poked
        wi32(k, h, a, orig)               # restore original
        if ocr_pp(shot) == TESTVAL:
            real.append(a)
            M.log(f"  *** REAL PP @ 0x{a:X} (HUD read {TESTVAL} when poked) ***")
    if not real:
        M.log("  no candidate moved the HUD - widen KEEP or re-run (PP may have drifted out).")
    else:
        M.log("FOUND real PP address(es): " + ", ".join(f"0x{a:X}" for a in real))
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
