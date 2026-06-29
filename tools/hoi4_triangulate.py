#!/usr/bin/env python3
"""
hoi4_triangulate.py - cross-check the bar values to identify the real player struct
and learn the 1.19 layout. PP is a double; the other bar values live at offsets from
the same pPlayer. So for each PP-tracking candidate (logs/pp_cands.json), read its
neighborhood and look for the OTHER bar values in every plausible encoding. The real
PP sits in a window that ALSO contains command power, manpower, etc. - that lights it
up, and the matched offsets+encodings ARE the struct map.

    python hoi4_triangulate.py cp=132 mp=168980 stab=73 war=56 fac=339 conv=194
      cp/conv/fac/mp = plain counts;  stab/war = percents (tried as fraction too)

Reads only; pokes nothing.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoi4_mem as M  # noqa: E402

WINDOW = 0x4000           # +/- around each candidate to search
PCT_KEYS = {"stab", "war"}


def encodings(key, v):
    """Return [(name, packed_bytes, tol_bytes_len)] to search for value v of field key."""
    out = []
    fv = float(v)
    # doubles
    out.append((f"{key}=double({v})", struct.pack("<d", fv), 8))
    if key in PCT_KEYS:
        out.append((f"{key}=double({v}/100)", struct.pack("<d", fv / 100.0), 8))
    # ints
    out.append((f"{key}=int({v})", struct.pack("<i", int(v)), 4))
    out.append((f"{key}=int({v}*1000)", struct.pack("<i", int(v) * 1000), 4))
    # floats
    out.append((f"{key}=float({v})", struct.pack("<f", fv), 4))
    if key in PCT_KEYS:
        out.append((f"{key}=float({v}/100)", struct.pack("<f", fv / 100.0), 4))
    return out


def main():
    fields = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            fields[k] = int(v)
    if not fields:
        sys.exit("usage: hoi4_triangulate.py cp=132 mp=168980 stab=73 war=56 ...")

    cj = M.ROOT / "logs" / "pp_cands.json"
    if not cj.exists():
        sys.exit("logs/pp_cands.json not found - run hoi4_find_pp.py --double first")
    data = json.loads(cj.read_text())
    pp_addrs = [int(a, 16) for a in data["addrs"]]
    M.log(f"triangulate: {len(pp_addrs)} PP candidates; fields={fields}")

    needles = {k: encodings(k, v) for k, v in fields.items()}
    k32, h, _ = M.attach()
    best = None
    for pa in pp_addrs:
        win = M.read_bytes(k32, h, pa - WINDOW, 2 * WINDOW)
        if not win:
            continue
        hits = {}
        for key, encs in needles.items():
            for name, nb, _ln in encs:
                idx = win.find(nb)
                if idx >= 0:
                    off = (pa - WINDOW + idx) - pa     # signed offset from the PP candidate
                    hits[key] = (name, off)
                    break
        if hits:
            M.log(f"  PP@0x{pa:X}: {len(hits)} bar values nearby -> "
                  + "; ".join(f"{k} {n} @PP{off:+#x}" for k, (n, off) in hits.items()))
        if best is None or len(hits) > len(best[1]):
            best = (pa, hits)
    if best and best[1]:
        pa, hits = best
        M.log(f"BEST: PP@0x{pa:X} with {len(hits)} cross-confirmed values - this is the real struct.")
        M.log("STRUCT MAP (offsets from the PP address):")
        for kk, (nm, off) in sorted(hits.items(), key=lambda x: x[1][1]):
            M.log(f"    PP{off:+#07x}  {nm}")
    else:
        M.log("  no neighbourhood matched other bar values; widen WINDOW or values may be in a "
              "separate sub-object (trace PP with hoi4_dbg to reach pPlayer first).")
    k32.CloseHandle(h)


if __name__ == "__main__":
    main()
