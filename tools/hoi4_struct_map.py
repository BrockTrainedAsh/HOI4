#!/usr/bin/env python3
"""
hoi4_struct_map.py - map the player country struct on 1.19 by anchoring on PP.
PP is int32 = PP*100000 at [pPlayer+0xE0]. Scan for PP, treat each hit minus 0xE0 as a
candidate pPlayer, and look in its neighbourhood for the OTHER bar values in every
plausible encoding. The candidate whose struct holds the most of them IS pPlayer, and
the matched offsets+encodings are the struct map - the recipe for every other cheat.

    python hoi4_struct_map.py pp=15 cp=230 mp=343630 stab=100 war=86 fac=584 conv=611
"""
import array
import struct
import sys

sys.path.insert(0, "tools")
import hoi4_mem as M  # noqa: E402

PCT = {"stab", "war"}
WIN_LO, WIN_HI = -0x200, 0x1800     # struct window around pPlayer to search


def encodings(key, v):
    """(name, predicate(value)->bool) for each plausible storage of bar field key=v."""
    out = []
    out.append((f"int*100000", "i", lambda x: abs(x - v * 100000) <= 100000))
    out.append((f"int*1000", "i", lambda x: abs(x - v * 1000) <= 1500))
    out.append((f"int", "i", lambda x: x == v))
    out.append((f"double", "d", lambda x: abs(x - v) < 0.5))
    if key in PCT:
        out.append((f"double/100", "d", lambda x: abs(x - v / 100.0) < 0.01))
        out.append((f"int*1000(pct)", "i", lambda x: abs(x - v * 1000) <= 1500))
    if key == "mp":
        out.append((f"int(approx)", "i", lambda x: abs(x - v) <= 200))
    return out


def main():
    fields = {}
    for a in sys.argv[1:]:
        if "=" in a:
            k, val = a.split("=", 1)
            fields[k] = int(val)
    pp = fields["pp"]
    others = {k: v for k, v in fields.items() if k != "pp"}
    k, h, _ = M.attach()
    lo, hi = pp * 100000, (pp + 1) * 100000 - 1
    M.log(f"struct_map: scanning for PP {pp} (= int {lo}..{hi}) ...")
    cands = []
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
                        cands.append(base + off + i * 4)
            off += n
            if len(cands) > 6000:
                break
        if len(cands) > 6000:
            break
    M.log(f"  {len(cands)} PP candidates; checking each struct for the other bar values...")

    best = None
    for ppaddr in cands:
        pplayer = ppaddr - 0xE0
        win = M.read_bytes(k, h, pplayer + WIN_LO, WIN_HI - WIN_LO)
        if not win or len(win) < 64:
            continue
        ints = array.array("i"); ints.frombytes(win[:len(win) // 4 * 4])
        dbls = array.array("d"); dbls.frombytes(win[:len(win) // 8 * 8])
        hits = {}
        for key, v in others.items():
            for name, typ, pred in encodings(key, v):
                arr = ints if typ == "i" else dbls
                stride = 4 if typ == "i" else 8
                for idx, x in enumerate(arr):
                    if pred(x):
                        hits[key] = (name, WIN_LO + idx * stride)
                        break
                if key in hits:
                    break
        if best is None or len(hits) > len(best[2]):
            best = (pplayer, ppaddr, hits)
    if best and len(best[2]) >= 2:
        pplayer, ppaddr, hits = best
        M.log(f"FOUND pPlayer = 0x{pplayer:X}  (PP @ 0x{ppaddr:X} = pPlayer+0xE0)")
        M.log("STRUCT MAP (offset from pPlayer):")
        M.log(f"    +0x00E0   pp          int*100000")
        for kk, (nm, off) in sorted(hits.items(), key=lambda x: x[1][1]):
            M.log(f"    {('+0x%04X' % off) if off >= 0 else ('-0x%04X' % -off)}   {kk:<11} {nm}")
    else:
        M.log("  no struct held enough bar values - widen window or check the values/encodings.")
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
