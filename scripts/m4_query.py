"""M4 read-only helper: query function boundaries + dump/disassemble XBE bytes.

Usage:
  py -3 scripts/m4_query.py <xbe> bytes <hex-va> [count]
  py -3 scripts/m4_query.py <xbe> disasm <hex-va> [count]
  py -3 scripts/m4_query.py <xbe> func <hex-va>          # function containing VA
  py -3 scripts/m4_query.py <xbe> at <hex-va>            # function starting at VA

functions.json is read from third_party/xboxrecomp/tools/disasm/output/functions.json.
"""
import json
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

FUNCS = "third_party/xboxrecomp/tools/disasm/output/functions.json"
XBE_MAGIC = b"XBEH"


def load(path):
    with open(path, "rb") as f:
        return f.read()


def sections(xbe):
    base = struct.unpack_from("<I", xbe, 0x104)[0]
    n = struct.unpack_from("<I", xbe, 0x11C)[0]
    hdr = struct.unpack_from("<I", xbe, 0x120)[0] - base
    out = []
    for i in range(n):
        off = hdr + i * 0x38
        _flags, va, vsize, raw, rsize = struct.unpack_from("<IIIII", xbe, off)
        out.append((va, vsize, raw & 0x1FFFFFFF,
                    rsize if rsize else vsize))
    return base, out


def va_to_off(secs, va):
    for sva, vsize, raw, rsize in secs:
        if sva <= va < sva + max(vsize, rsize):
            return raw + (va - sva)
    return None


def funcs():
    with open(FUNCS) as f:
        data = json.load(f)
    items = data["functions"] if isinstance(data, dict) else data
    out = []
    for e in items:
        out.append((int(e["start"], 16) if isinstance(e["start"], str) else e["start"],
                    int(e["end"], 16) if isinstance(e["end"], str) else e["end"],
                    e.get("name", ""), e.get("detection_method", ""),
                    e.get("num_instructions", 0)))
    out.sort()
    return out


def containing(fl, va):
    for s, e, n, m, c in fl:
        if s <= va < e:
            return (s, e, n, m, c)
    return None


def starting(fl, va):
    for s, e, n, m, c in fl:
        if s == va:
            return (s, e, n, m, c)
    return None


def main():
    xbe_path = sys.argv[1]
    cmd = sys.argv[2]
    va = int(sys.argv[3], 16)
    count = int(sys.argv[4], 0) if len(sys.argv) > 4 else 64

    xbe = load(xbe_path)
    assert xbe[:4] == XBE_MAGIC
    base, secs = sections(xbe)
    fl = funcs()

    if cmd == "func":
        r = containing(fl, va)
        if r:
            s, e, n, m, c = r
            print(f"0x{va:08X} inside {n} 0x{s:08X}-0x{e:08X} "
                  f"({e - s} B, {c} insns, method={m})")
        else:
            print(f"0x{va:08X} not inside any detected function")
        return
    if cmd == "at":
        r = starting(fl, va)
        if r:
            s, e, n, m, c = r
            print(f"{n} 0x{s:08X}-0x{e:08X} ({e - s} B, {c} insns, method={m})")
        else:
            print(f"no detected function starts at 0x{va:08X}")
        return

    off = va_to_off(secs, va)
    if off is None:
        print(f"0x{va:08X} not mapped")
        return
    raw = xbe[off:off + count]

    if cmd == "bytes":
        for i in range(0, len(raw), 16):
            chunk = raw[i:i + 16]
            print(f"0x{va + i:08X}: " + " ".join(f"{b:02X}" for b in chunk))
        return

    if cmd == "disasm":
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        for insn in md.disasm(raw, va):
            print(f"0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}")
        return

    print("unknown command")


if __name__ == "__main__":
    main()
