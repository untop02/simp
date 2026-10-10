"""Disassemble the linked EXE at an RVA (no PDB needed).

Usage:
  py -3 scripts/m5_disasm_exe.py <exe> <rva-hex> [before] [after]
"""
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_64


def sections(data):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew + 4] == b"PE\x00\x00"
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    image_base = struct.unpack_from("<Q", data, opt + 24)[0] if magic == 0x20B \
        else struct.unpack_from("<I", data, opt + 28)[0]
    sec = opt + opt_size
    out = []
    for i in range(nsec):
        off = sec + i * 40
        name = data[off:off + 8].rstrip(b"\x00").decode("ascii", "replace")
        vsize, vaddr, rsize, raw = struct.unpack_from("<IIII", data, off + 8)
        out.append((name, vaddr, max(vsize, rsize), raw, rsize))
    return image_base, out


def rva_to_off(secs, rva):
    for _n, vaddr, vsize, raw, _rs in secs:
        if vaddr <= rva < vaddr + vsize:
            return raw + (rva - vaddr)
    return None


def main():
    path = sys.argv[1]
    rva = int(sys.argv[2], 16)
    before = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x20
    after = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x40

    with open(path, "rb") as f:
        data = f.read()
    image_base, secs = sections(data)
    print("image base 0x%X" % image_base)
    off = rva_to_off(secs, rva)
    if off is None:
        print("RVA 0x%X not in any section" % rva)
        return 1

    start = rva - before
    raw = data[rva_to_off(secs, start):off + after]
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for insn in md.disasm(raw, image_base + start):
        marker = " <== RIP" if insn.address == image_base + rva else ""
        print("  0x%08X: %-8s %s%s" % (insn.address, insn.mnemonic,
                                        insn.op_str, marker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
