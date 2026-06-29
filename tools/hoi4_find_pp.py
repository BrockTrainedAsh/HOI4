#!/usr/bin/env python3
"""
hoi4_find_pp.py - find the REAL Political Power address by its behaviour, with no
assumption about scale that turned out wrong. PP is NOT int*1000 on 1.19 (a tracking
scan collapsed to 0), so default to FLOAT (Paradox stores resources as floats).

  1. OCR PP, seed every address whose value (as float, or int/1000) reads near PP.
  2. Narrow whenever PP CHANGES in either direction (you spend it too) - keep the
     addresses whose value still equals the OCR'd PP. Static look-alikes fall away.
  3. WRITE-TEST survivors: poke a distinctive value, OCR the bar, restore. Only the
     real PP (the render source) makes the bar read it - scale-independent proof.

    python hoi4_find_pp.py            # float (default)
    python hoi4_find_pp.py --int      # int x1000 (legacy)
"""
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402

KEEP = 140
SEED_CAP = 8_000_000
TESTVAL = 4321
DOUBLE = "--double" in sys.argv
FLOAT = (not DOUBLE) and ("--int" not in sys.argv)
if DOUBLE:
    FMT, ATYP, SIZE = "<d", "d", 8
elif FLOAT:
    FMT, ATYP, SIZE = "<f", "f", 4
else:
    FMT, ATYP, SIZE = "<i", "i", 4
REAL = FLOAT or DOUBLE


def to_pp(v):
    return v if REAL else v / 1000.0


def poke_bytes():
    return struct.pack(FMT, float(TESTVAL) if REAL else TESTVAL * 1000)


def rd(k, h, a):
    d = M.read_bytes(k, h, a, SIZE)
    return struct.unpack(FMT, d)[0] if d and len(d) >= SIZE else None


def wr(k, h, a, b):
    w = M.ctypes.c_size_t(0)
    return k.WriteProcessMemory(h, M.ctypes.c_void_p(a), b, len(b), M.ctypes.byref(w)) and w.value == len(b)


def screencap():
    shot = M.SHOTDIR / "ft.png"
    M._ps("screencap.ps1", "-Out", str(shot), "-H", "90")
    return shot


def ocr_pp(shot=None):
    # X=190 starts AFTER the PP icon (X=150 catches the icon and OCRs to nothing);
    # W=130 still fits a 4-digit poke like 4321. Verified reads 59/80/148.
    if shot is None:
        shot = screencap()
    r = M._ps("ocr.ps1", "-Path", str(shot), "-X", "190", "-Y", "0", "-W", "130", "-H", "90")
    txt = (r.stdout or "").strip().replace(",", "").upper()
    m = re.search(r"\d+", txt)
    return int(m.group()) if m and "K" not in txt else None


def read_pp():
    for _ in range(8):
        v = ocr_pp()
        if v:
            return v
    return None


def main():
    time.sleep(3)
    pp = read_pp()
    if not pp:
        M.log("find_pp: could not OCR PP after retries"); return
    lo_pp, hi_pp = pp - 3, pp + 18
    M.log(f"find_pp ({'float' if FLOAT else 'int x1000'}): PP={pp}; seeding PP in [{lo_pp},{hi_pp}] ...")
    k, h, _ = M.attach(write=True)
    capmb = 64 * 1024 * 1024
    cands = {}
    for base, rsize, _p in M.iter_regions(k, h):
        if rsize > capmb:
            continue
        off = 0
        while off < rsize:
            n = min(M.CHUNK, rsize - off)
            d = M.read_bytes(k, h, base + off, n)
            if d:
                arr = M.array.array(ATYP)
                arr.frombytes(d[:len(d) // SIZE * SIZE])
                for i, v in enumerate(arr):
                    p = to_pp(v)
                    if lo_pp <= p <= hi_pp:
                        cands[base + off + i * SIZE] = v
            off += n
            if len(cands) > SEED_CAP:
                break
        if len(cands) > SEED_CAP:
            break
    M.log(f"  seed -> {len(cands)} candidates")

    last = pp
    for it in range(50):
        if len(cands) <= KEEP:
            break
        cur = None
        for _ in range(25):
            time.sleep(1.5)
            cur = read_pp()
            if cur and abs(cur - last) >= 1:    # PP changed (up OR down)
                break
        if not cur or abs(cur - last) < 1:
            M.log(f"  iter {it}: PP not changing ({cur}); stopping with {len(cands)} left")
            break
        last = cur
        fresh = read_pp()                    # re-OCR right before re-reading memory (PP moves fast)
        if fresh:
            cur = fresh
        cands = {a: nv for a in cands
                 if (nv := rd(k, h, a)) is not None and abs(to_pp(nv) - cur) <= 3.0}
        M.log(f"  iter {it}: PP={cur} -> {len(cands)} candidates")

    addrs = list(cands)[:KEEP]
    M.log(f"  write-testing {len(addrs)} candidates (poke {TESTVAL}, OCR, restore)...")
    poke = poke_bytes()
    real = []
    for a in addrs:
        orig = M.read_bytes(k, h, a, SIZE)
        if not orig:
            continue
        end = time.time() + 0.35
        while time.time() < end:
            wr(k, h, a, poke)
        shot = screencap()
        w = M.ctypes.c_size_t(0)
        k.WriteProcessMemory(h, M.ctypes.c_void_p(a), orig, SIZE, M.ctypes.byref(w))  # restore
        if ocr_pp(shot) == TESTVAL:
            real.append(a)
            M.log(f"  *** REAL PP @ 0x{a:X} (HUD read {TESTVAL} when poked) ***")
    if real:
        M.log("FOUND real PP: " + ", ".join(f"0x{a:X}" for a in real))
    else:
        M.log("  no candidate moved the HUD (try --int, or PP got spent mid-run; re-run).")
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
