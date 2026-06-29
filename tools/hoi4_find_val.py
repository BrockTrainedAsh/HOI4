#!/usr/bin/env python3
"""
hoi4_find_val.py - scan the heap for a value in [LO,HI] as both int32 and double, save
the matches. For UNIQUE-valued bar fields (manpower, etc.) this returns a small set the
debugger can then disambiguate (the one the game's code actually touches = the player's).

    python hoi4_find_val.py 558000 558600
"""
import array
import json
import os
import struct  # noqa: F401
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402


def main():
    lo, hi = float(sys.argv[1]), float(sys.argv[2])
    k, h, _ = M.attach()
    ints, dbls = [], []
    for base, rsize, _p in M.iter_regions(k, h):
        if rsize > 64 * 1024 * 1024:
            continue
        off = 0
        while off < rsize:
            n = min(M.CHUNK, rsize - off)
            d = M.read_bytes(k, h, base + off, n)
            if d:
                ia = array.array("i")
                ia.frombytes(d[:len(d) // 4 * 4])
                for i, v in enumerate(ia):
                    if lo <= v <= hi:
                        ints.append((base + off + i * 4, v))
                da = array.array("d")
                da.frombytes(d[:len(d) // 8 * 8])
                for i, v in enumerate(da):
                    if lo <= v <= hi:
                        dbls.append((base + off + i * 8, v))
            off += n
    M.log(f"find_val [{lo:.0f},{hi:.0f}]: {len(ints)} int32, {len(dbls)} double")
    for a, v in dbls[:24]:
        M.log(f"  DBL 0x{a:X} = {v}")
    for a, v in ints[:16]:
        M.log(f"  INT 0x{a:X} = {v}")
    (M.ROOT / "logs" / "val_cands.json").write_text(json.dumps(
        {"int": [[hex(a), v] for a, v in ints], "double": [[hex(a), v] for a, v in dbls]}))
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
