#!/usr/bin/env python3
"""
hoi4_accum.py - find doubles that are actively ACCUMULATING (real game resources), not
static look-alikes. Snapshot every double in [LO,HI], wait, re-read, keep the ones that
rose by a small positive amount. These are addresses the game's code writes each tick,
so the debugger fires on them and they lead to the player struct.

    python hoi4_accum.py 70 300 10      # range [70,300], watch 10s
"""
import array
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402


def main():
    lo, hi = float(sys.argv[1]), float(sys.argv[2])
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    k, h, _ = M.attach()
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
    M.log(f"accum: snapshot {len(snap)} doubles in [{lo:.0f},{hi:.0f}]; waiting {wait}s...")
    time.sleep(wait)
    accum = []
    for a, v in snap.items():
        d = M.read_bytes(k, h, a, 8)
        if not d or len(d) < 8:
            continue
        nv = struct.unpack("<d", d)[0]
        if 0.05 <= (nv - v) <= 50:      # rose a little = accumulating; not static, not a jump
            accum.append((a, v, nv))
    accum.sort(key=lambda x: x[2] - x[1])
    M.log(f"accum: {len(accum)} doubles rose over {wait}s")
    for a, v, nv in accum[:40]:
        M.log(f"  0x{a:X}: {v:.3f} -> {nv:.3f}  (+{nv - v:.3f})")
    (M.ROOT / "logs" / "accum.json").write_text(json.dumps(
        {"addrs": [hex(a) for a, _v, _nv in accum]}))
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
