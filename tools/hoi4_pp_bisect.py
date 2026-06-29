#!/usr/bin/env python3
"""
hoi4_pp_bisect.py - extract the ONE real Political Power address from the saved
tracking-double candidates. Two phases, no display-scrambling batch pokes:
  REFINE: re-read all candidates as PP changes and keep only those still equal to the
          live PP. Coincidental look-alikes (frozen at their old value) fall away; the
          real PP and its true copies track. A collapse guard never drops below 3.
  TEST:   poke each survivor ONE AT A TIME to 4321, read the whole bar, restore. The
          one that makes the bar read 4321 is the real PP.

    python hoi4_pp_bisect.py
"""
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402

TESTVAL = 4321


def screencap():
    shot = M.SHOTDIR / "bis.png"
    M._ps("screencap.ps1", "-Out", str(shot), "-H", "90")
    return shot


def read_pp():
    for _ in range(8):
        shot = screencap()
        r = M._ps("ocr.ps1", "-Path", str(shot), "-X", "190", "-Y", "0", "-W", "130", "-H", "90")
        txt = (r.stdout or "").strip().replace(",", "").upper()
        m = re.search(r"\d+", txt)
        if m and "K" not in txt:
            return int(m.group())
    return None


def read_full(shot):
    r = M._ps("ocr.ps1", "-Path", str(shot))
    txt = (r.stdout or "").strip().replace(",", "")
    m = re.search(r"(\d+)", txt)
    return int(m.group(1)) if m else None


def main():
    data = json.loads((M.ROOT / "logs" / "pp_cands.json").read_text())
    cands = [int(a, 16) for a in data["addrs"]]
    size = data.get("size", 8)
    fmt = {8: "<d", 4: "<f"}.get(size, "<d")
    M.log(f"bisect: {len(cands)} candidates ({data.get('type')})")
    k, h, _ = M.attach(write=True)

    def rd(a):
        d = M.read_bytes(k, h, a, size)
        return struct.unpack(fmt, d)[0] if d and len(d) >= size else None

    # ---- REFINE: cull non-trackers as PP changes ----
    last = read_pp()
    for it in range(12):
        if len(cands) <= 40:
            break
        cur = None
        for _ in range(25):
            time.sleep(1.5)
            cur = read_pp()
            if cur and last and abs(cur - last) >= 2:
                break
        if not cur or not last or abs(cur - last) < 2:
            M.log(f"  refine {it}: PP not moving ({cur}); stop with {len(cands)}")
            break
        last = cur
        kept = [a for a in cands if (v := rd(a)) is not None and abs(v - cur) <= 2.5]
        if len(kept) >= 3:
            cands = kept
        M.log(f"  refine {it}: PP={cur} -> {len(cands)} trackers")

    # ---- TEST: poke each survivor alone ----
    M.log(f"  write-testing {len(cands)} survivors one at a time...")
    poke = struct.pack(fmt, float(TESTVAL))
    w = M.ctypes.c_size_t(0)
    real = []
    for a in cands[:80]:
        orig = M.read_bytes(k, h, a, size)
        if not orig:
            continue
        end = time.time() + 0.5
        while time.time() < end:
            k.WriteProcessMemory(h, M.ctypes.c_void_p(a), poke, size, M.ctypes.byref(w))
        shot = screencap()
        k.WriteProcessMemory(h, M.ctypes.c_void_p(a), orig, size, M.ctypes.byref(w))  # restore
        if read_full(shot) == TESTVAL:
            real.append(a)
            M.log(f"  *** REAL PP @ 0x{a:X} ***")
    if real:
        M.log("REAL PP ADDRESS = " + ", ".join(f"0x{a:X}" for a in real))
        (M.ROOT / "logs" / "pp_real.json").write_text(json.dumps(
            {"addr": hex(real[0]), "type": data.get("type"), "size": size}))
    else:
        M.log("  none confirmed; re-run the finder for a fresh candidate set.")
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
