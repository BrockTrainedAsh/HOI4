#!/usr/bin/env python3
"""
hoi4_struct.py - find the player struct (pPlayer) by its STRUCTURE, not an AOB.

The Recifense base finds pPlayer via an AOB scan that's dead on 1.19. But the
1.18.2 extension reveals the offset layout off pPlayer:
  Stability    = [pPlayer+0x1160] (x10)   (adjacent...)
  War Support  = [pPlayer+0x1164] (x10)
  PP           = [[pPlayer+0x1028]+0xF8]   (x1000)
  Command Power= [[[pPlayer+0x1028]+0xE0]+0x210] (x1000)
So: scan the heap for the adjacent (stability*10, warsupport*10) pair, treat each as
pPlayer+0x1160, then VERIFY by walking the chain to Command Power - only the real
struct yields CP == the value off your bar. No debugger, no Cheat Engine.

    python hoi4_struct.py <stab%> <war%> <cp> <pp>   e.g.  python hoi4_struct.py 54 57 130 24
    python hoi4_struct.py 54 57 130 24 --setpp 5000   (write PP once verified)
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402

OFF_STAB = 0x1160
OFF_WAR = 0x1164
OFF_PP_DEREF = 0x1028
OFF_PP_ADD = 0xF8
OFF_SUB_DEREF = 0xE0
OFF_CP = 0x210


def ri32(k, h, a):
    d = M.read_bytes(k, h, a, 4)
    return struct.unpack("<i", d)[0] if d and len(d) >= 4 else None


def deref(k, h, a):
    d = M.read_bytes(k, h, a, 8)
    v = struct.unpack("<Q", d)[0] if d and len(d) >= 8 else None
    return v if v and 0x10000 < v < 0x7FFFFFFFFFFF else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stab", type=int); ap.add_argument("war", type=int)
    ap.add_argument("cp", type=int); ap.add_argument("pp", type=int)
    ap.add_argument("--setpp", type=int, default=None)
    a = ap.parse_args()

    # Don't assume the 1.18.2 encoding - try several and see which pair actually exists.
    encs = [
        ("int x10", struct.pack("<i", a.stab * 10) + struct.pack("<i", a.war * 10)),
        ("int x100", struct.pack("<i", a.stab * 100) + struct.pack("<i", a.war * 100)),
        ("int x1000", struct.pack("<i", a.stab * 1000) + struct.pack("<i", a.war * 1000)),
        ("float 0-1", struct.pack("<f", a.stab / 100.0) + struct.pack("<f", a.war / 100.0)),
        ("float pct", struct.pack("<f", float(a.stab)) + struct.pack("<f", float(a.war))),
    ]
    M.log(f"hoi4_struct: hunting adjacent stab/war pair, trying {len(encs)} encodings ...")
    k, h, _ = M.attach(write=a.setpp is not None)

    hits = {name: [] for name, _ in encs}
    for base, rsize, _p in M.iter_regions(k, h):
        off = 0
        while off < rsize:
            n = min(M.CHUNK, rsize - off)
            d = M.read_bytes(k, h, base + off, n)
            if d:
                for name, needle in encs:
                    i = d.find(needle)
                    while i >= 0:
                        hits[name].append(base + off + i)
                        i = d.find(needle, i + 1)
            off += (n - 7) if n == M.CHUNK else n
    for name, _ in encs:
        M.log(f"  encoding {name:10}: {len(hits[name])} adjacent pairs")
    # use whichever encoding produced a workable, non-zero number of candidates
    pairs = []
    for name in ("int x10", "int x100", "int x1000", "float 0-1", "float pct"):
        if 0 < len(hits[name]) < 5000:
            pairs = hits[name]
            M.log(f"  -> verifying {len(pairs)} pairs from encoding '{name}' via Command Power...")
            break
    if not pairs:
        M.log("  no usable stab/war pair in any encoding - 1.19 layout differs; need the real table.")

    verified = []
    for stab_addr in pairs:
        p = stab_addr - OFF_STAB                      # candidate pPlayer
        sub = deref(k, h, p + OFF_PP_DEREF)           # [pPlayer+0x1028]
        if not sub:
            continue
        cp_obj = deref(k, h, sub + OFF_SUB_DEREF)     # [[..]+0xE0]
        cp_val = ri32(k, h, cp_obj + OFF_CP) if cp_obj else None
        pp_val = ri32(k, h, sub + OFF_PP_ADD)         # PP value
        if cp_val is not None and abs(cp_val - a.cp * 1000) <= 2000:
            verified.append((p, sub + OFF_PP_ADD, pp_val, cp_val))
            M.log(f"  VERIFIED pPlayer=0x{p:X}  CP={cp_val} (want {a.cp*1000})  "
                  f"PP={pp_val} (want ~{a.pp*1000}) @ 0x{sub + OFF_PP_ADD:X}")

    if not verified:
        M.log("  NO verified struct - the 1.18.2 offsets do not hold on 1.19 "
              "(need the real 1.19 table / relocation).")
        k.CloseHandle(h); return

    if a.setpp is not None:
        p, pp_addr, _pv, _cv = verified[0]
        w = M.ctypes.c_size_t(0)
        ok = k.WriteProcessMemory(h, M.ctypes.c_void_p(pp_addr),
                                  struct.pack("<i", a.setpp * 1000), 4, M.ctypes.byref(w))
        M.log(f"  WROTE PP @ 0x{pp_addr:X} = {a.setpp} (x1000) -> "
              f"{'OK' if ok and w.value == 4 else 'FAILED'}")
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
