"""M4 probe #3: run the real detect_all() with selectable sections/seeds.

Usage: py -3 scripts/m4_detect_compare.py <xbe> [all|text] [seeds|noseeds]
"""
import sys

from tools.disasm.loader import load_image
from tools.disasm.engine import DisasmEngine
from tools.disasm.functions import FunctionDetector
from tools.disasm.labels import LabelManager
from tools.disasm.xrefs import build_xrefs

MODE = sys.argv[2] if len(sys.argv) > 2 else "all"
SEEDMODE = sys.argv[3] if len(sys.argv) > 3 else "noseeds"

image = load_image(sys.argv[1], None)
if MODE == "text":
    sections = [image.get_section(".text")]
else:
    sections = image.get_code_sections()

eng = DisasmEngine(image)
for s in sections:
    eng.linear_sweep(s)
eng.resync_jump_tables()
xrefs = build_xrefs(eng, image)
labels = LabelManager()
fd = FunctionDetector(eng, image, xrefs, labels)

SEEDS = [0x00139860, 0x00139AD0, 0x0013B940, 0x0013CA90, 0x0013D900, 0x0015A7DF]
if len(sys.argv) > 4:
    SEEDS = [int(x, 16) for x in sys.argv[4].split(",")]
if SEEDMODE == "seeds":
    for a in SEEDS:
        if a not in eng.instructions:
            eng.decode_at(a)
        fd._add_candidate(a, 0.95, "seed_vtable_thunk")

n = fd.detect_all(sections)

WATCH = [0x000AFEC0, 0x00139440, 0x00139AC0, 0x00139AD0, 0x00139730,
         0x0015A760, 0x0015A7DF, 0x0015B100]
print(f"\n[{MODE}/{SEEDMODE}] functions={n} candidates={len(fd._candidates)} "
      f"aliases={len(fd._alias_entries)}")
for a in WATCH:
    f = fd.functions.get(a)
    if f:
        print(f"  0x{a:08X}: FUNC 0x{f.start:08X}-0x{f.end:08X} "
              f"({f.detection_method})")
    else:
        alias = fd._alias_entries.get(a)
        # inside?
        inside = None
        for s, ff in fd.functions.items():
            if s <= a < ff.end:
                inside = ff
                break
        tag = f"alias->0x{alias:08X}" if alias else (
            f"inside {inside.name} 0x{inside.start:08X}-0x{inside.end:08X}"
            if inside else "NOT DETECTED")
        print(f"  0x{a:08X}: {tag}")
