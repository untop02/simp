"""Find references to a guest VA (immediate) inside an XBE .text image.

Usage: py -3 scripts/m2_findref.py <xbe> <hex-va>

Maps each hit's file offset to a guest VA using the XBE section table, so the
result can be cross-referenced against generated code / disassembly.
"""
import struct
import sys

XBE_MAGIC = b"XBEH"


def load(path):
    with open(path, "rb") as f:
        return f.read()


def sections(xbe):
    base = struct.unpack_from("<I", xbe, 0x104)[0]
    n = struct.unpack_from("<I", xbe, 0x11C)[0]
    # Section headers are given as a VA; convert to a file offset.
    hdr = struct.unpack_from("<I", xbe, 0x120)[0] - base
    out = []
    for i in range(n):
        off = hdr + i * 0x38
        # Header: Flags, VirtualAddress, VirtualSize, RawAddress, RawSize, ...
        _flags, va, vsize, raw, rsize = struct.unpack_from("<IIIII", xbe, off)
        out.append((va, vsize, raw & 0x1FFFFFFF,
                    rsize if rsize else vsize))
    return base, out


def file_to_va(secs, foff):
    for va, vsize, raw, rsize in secs:
        if raw <= foff < raw + rsize:
            return va + (foff - raw)
    return None


def main():
    xbe = load(sys.argv[1])
    assert xbe[:4] == XBE_MAGIC, "not an XBE"
    needle_va = int(sys.argv[2], 16)
    base, secs = sections(xbe)
    pat = struct.pack("<I", needle_va)
    print(f"XBE base 0x{base:08X}, {len(secs)} sections")
    hits = 0
    i = 0
    while True:
        j = xbe.find(pat, i)
        if j < 0:
            break
        gva = file_to_va(secs, j)
        where = f"file 0x{j:08X} -> guest 0x{gva:08X}" if gva else f"file 0x{j:08X}"
        print(f"  ref to 0x{needle_va:08X} at {where}")
        hits += 1
        i = j + 1
    print(f"{hits} references")


if __name__ == "__main__":
    main()
