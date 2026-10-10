"""Compare each function's XBE ret/ret N against the generated C epilogue.

Usage:
  py -3 scripts/m6_ret_check.py <xbe> <gen-dir> <va> [<va> ...]
"""
import glob
import os
import re
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32


def parse_xbe(data):
    base = struct.unpack_from("<I", data, 0x104)[0]
    nsec = struct.unpack_from("<I", data, 0x11C)[0]
    sec_hdr_va = struct.unpack_from("<I", data, 0x120)[0]
    sec_off = sec_hdr_va - base
    secs = []
    for i in range(nsec):
        off = sec_off + i * 0x38
        flags, vaddr, vsize, raw_addr, raw_size = struct.unpack_from("<IIIII", data, off)
        secs.append((vaddr, vsize, raw_addr, raw_size))
    return base, secs


def va_to_off(secs, va):
    for vaddr, vsize, raw, _rs in secs:
        if vaddr <= va < vaddr + vsize:
            return raw + (va - vaddr)
    return None


def xbe_ret(data, secs, va):
    off = va_to_off(secs, va)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for insn in md.disasm(data[off:off + 0x400], va):
        if insn.mnemonic == "ret":
            return insn.op_str or "0"
        if insn.mnemonic == "jmp":
            return "jmp " + insn.op_str
    return "?"


def gen_epilogue(gen_dir, va):
    pat = re.compile(r"void sub_%08X\(void\)" % va)
    for path in glob.glob(os.path.join(gen_dir, "*.c")):
        with open(path, "r", errors="replace") as f:
            txt = f.read()
        m = pat.search(txt)
        if not m:
            continue
        # find the function body: from match to next "\n}\n"
        end = txt.find("\n}\n", m.end())
        body = txt[m.end():end]
        rets = re.findall(r"esp \+= (\d+); return; /\* ret(?: (\d+))? \*/", body)
        return os.path.basename(path), rets
    return None, None


def main():
    xbe = sys.argv[1]
    gen_dir = sys.argv[2]
    with open(xbe, "rb") as f:
        data = f.read()
    _base, secs = parse_xbe(data)
    for arg in sys.argv[3:]:
        va = int(arg, 16)
        xr = xbe_ret(data, secs, va)
        fn, rets = gen_epilogue(gen_dir, va)
        print("0x%08X  XBE ret=%-8s  gen(%s) rets=%s" % (va, xr, fn, rets))


if __name__ == "__main__":
    main()
