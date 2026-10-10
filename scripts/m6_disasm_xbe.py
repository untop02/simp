"""Disassemble the original Xbox XBE at a virtual address (32-bit x86).

Usage:
  py -3 scripts/m6_disasm_xbe.py <xbe> <va-hex> [before] [after]
"""
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32


def parse_xbe(data):
    assert data[:4] == b"XBEH", "not an XBE"
    base = struct.unpack_from("<I", data, 0x104)[0]
    nsec = struct.unpack_from("<I", data, 0x11C)[0]
    sec_hdr_va = struct.unpack_from("<I", data, 0x120)[0]
    # section headers live at file offset (va - base) since header is mapped at base
    sec_off = sec_hdr_va - base
    secs = []
    for i in range(nsec):
        off = sec_off + i * 0x38
        flags, vaddr, vsize, raw_addr, raw_size = struct.unpack_from("<IIIII", data, off)
        name_va = struct.unpack_from("<I", data, off + 0x14)[0]
        name_off = name_va - base
        name = data[name_off:name_off + 8].rstrip(b"\x00").decode("ascii", "replace")
        secs.append((name, vaddr, vsize, raw_addr, raw_size))
    return base, secs


def va_to_off(secs, va):
    for _n, vaddr, vsize, raw, _rs in secs:
        if vaddr <= va < vaddr + vsize:
            return raw + (va - vaddr)
    return None


def main():
    path = sys.argv[1]
    va = int(sys.argv[2], 16)
    before = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x20
    after = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x40

    with open(path, "rb") as f:
        data = f.read()
    base, secs = parse_xbe(data)
    print("XBE base 0x%X" % base)
    start = va - before
    off = va_to_off(secs, start)
    end = va_to_off(secs, va + after)
    if off is None or end is None:
        print("VA 0x%X not mapped" % va)
        return 1
    raw = data[off:end]
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for insn in md.disasm(raw, start):
        marker = " <== TARGET" if insn.address == va else ""
        print("  0x%08X: %-8s %s%s" % (insn.address, insn.mnemonic,
                                        insn.op_str, marker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
