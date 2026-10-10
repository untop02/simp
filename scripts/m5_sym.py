"""M5 helper: resolve guest VAs to containing functions from functions.json.

Usage:
  py -3 scripts/m5_sym.py 0x0011E858 0x001174DE ...
"""
import json
import sys

FUNCS = "third_party/xboxrecomp/tools/disasm/output/functions.json"


def load_funcs():
    with open(FUNCS) as f:
        data = json.load(f)
    items = data["functions"] if isinstance(data, dict) else data
    out = []
    for e in items:
        s = e["start"]
        s = int(s, 16) if isinstance(s, str) else s
        en = e["end"]
        en = int(en, 16) if isinstance(en, str) else en
        out.append((s, en, e.get("name", ""), e.get("detection_method", "")))
    out.sort()
    return out


def main():
    fl = load_funcs()
    for a in sys.argv[1:]:
        va = int(a, 16)
        hit = next(((s, e, n, m) for s, e, n, m in fl if s <= va < e), None)
        if hit:
            s, e, n, m = hit
            print("%s -> %-24s 0x%08X-0x%08X off+%d method=%s"
                  % (a, n, s, e, va - s, m))
        else:
            print("%s -> <not in any function>" % a)


if __name__ == "__main__":
    main()
