"""Resolve EXE RVAs (or absolute addresses) to symbols via dbghelp + PDB.

Usage:
  py -3 scripts/m5_sym_native.py <exe> --rva <hex> [<hex> ...]
  py -3 scripts/m5_sym_native.py <exe> --abs <base-hex> <addr-hex> [<addr-hex> ...]
"""
import ctypes
import os
import struct
import sys
from ctypes import wintypes

dbghelp = ctypes.WinDLL("dbghelp")


def image_size(path):
    d = open(path, "rb").read(0x400)
    e = struct.unpack_from("<I", d, 0x3C)[0]
    opt = e + 24
    magic = struct.unpack_from("<H", d, opt)[0]
    return struct.unpack_from("<I", d, opt + (56 if magic == 0x20B else 56))[0]


class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG),
        ("Reserved", ctypes.c_ulonglong * 2), ("Index", wintypes.ULONG),
        ("Size", wintypes.ULONG), ("ModBase", ctypes.c_ulonglong),
        ("Flags", wintypes.ULONG), ("Value", ctypes.c_ulonglong),
        ("Address", ctypes.c_ulonglong), ("Register", wintypes.ULONG),
        ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
        ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG),
        ("Name", ctypes.c_char * 1),
    ]


def main():
    exe = os.path.abspath(sys.argv[1]).replace("/", "\\")
    mode = sys.argv[2]
    proc = ctypes.windll.kernel32.GetCurrentProcess()
    dbghelp.SymSetOptions(0x00000004)
    if not dbghelp.SymInitialize(proc, os.path.dirname(exe).encode(), False):
        print("SymInitialize failed")
        return 1
    mod = dbghelp.SymLoadModuleEx(proc, None, exe.encode(), None,
                                  ctypes.c_ulonglong(0x140000000),
                                  image_size(exe), None, 0)
    _ = mod

    buf = ctypes.create_string_buffer(ctypes.sizeof(SYMBOL_INFO) + 1024)
    sym = ctypes.cast(buf, ctypes.POINTER(SYMBOL_INFO))
    name_off = SYMBOL_INFO.Name.offset

    class IMAGEHLP_LINE64(ctypes.Structure):
        _fields_ = [("SizeOfStruct", wintypes.DWORD), ("Key", ctypes.c_void_p),
                    ("LineNumber", wintypes.DWORD),
                    ("FileName", ctypes.c_char_p),
                    ("Address", ctypes.c_ulonglong)]

    def resolve(addr):
        ctypes.memset(buf, 0, ctypes.sizeof(buf))
        sym.contents.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO)
        sym.contents.MaxNameLen = 1023
        disp = ctypes.c_ulonglong(0)
        nm = "<no symbol>"
        d = 0
        if dbghelp.SymFromAddr(proc, ctypes.c_ulonglong(addr),
                               ctypes.byref(disp), sym):
            nm = ctypes.string_at(ctypes.addressof(buf) + name_off,
                                  sym.contents.NameLen).decode()
            d = disp.value
        ln = IMAGEHLP_LINE64()
        ln.SizeOfStruct = ctypes.sizeof(IMAGEHLP_LINE64)
        ld = ctypes.c_ulong(0)
        loc = ""
        if dbghelp.SymGetLineFromAddr64(proc, ctypes.c_ulonglong(addr),
                                        ctypes.byref(ld), ctypes.byref(ln)):
            fn = ln.FileName.decode() if ln.FileName else "?"
            loc = " [%s:%d]" % (fn, ln.LineNumber)
        print("0x%X -> %s+0x%X%s" % (addr, nm, d, loc))

    # Warm up: SymFromName forces the PDB to load (SymFromAddr alone can
    # return nothing while the module is still deferred).
    ctypes.memset(buf, 0, ctypes.sizeof(buf))
    sym.contents.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO)
    sym.contents.MaxNameLen = 1023
    dbghelp.SymFromName(proc, b"sub_00119140", sym)
    print("warmup sub_00119140: modbase=0x%X addr=0x%X value=0x%X"
          % (sym.contents.ModBase, sym.contents.Address, sym.contents.Value))

    if mode == "--rva":
        for a in sys.argv[3:]:
            resolve(0x140000000 + int(a, 16))
    elif mode == "--abs":
        b = int(sys.argv[3], 16)
        for a in sys.argv[4:]:
            resolve(int(a, 16) - b + 0x140000000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
