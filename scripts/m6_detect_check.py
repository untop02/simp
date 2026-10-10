"""Check whether the detector resolves specific VAs (tail-jump / alias cases).

Usage: py -3 scripts/m6_detect_check.py <xbe> [va,va,...]
Run with PYTHONPATH pointing at the toolkit copy under test.
"""
import sys

from tools.disasm.loader import load_image
from tools.disasm.engine import DisasmEngine
from tools.disasm.functions import FunctionDetector
from tools.disasm.labels import LabelManager
from tools.disasm.xrefs import build_xrefs

WATCH = [0x001228B0, 0x0017CC32]
if len(sys.argv) > 2:
    WATCH = [int(x, 16) for x in sys.argv[2].split(",")]

image = load_image(sys.argv[1], None)
sections = image.get_code_sections()

eng = DisasmEngine(image)
for s in sections:
    eng.linear_sweep(s)
eng.resync_jump_tables()
xrefs = build_xrefs(eng, image)
labels = LabelManager()
fd = FunctionDetector(eng, image, xrefs, labels)

SEEDS = [0x00139860, 0x00139AD0, 0x0013B940, 0x0013CA90, 0x0013D900]
for a in SEEDS:
    if a not in eng.instructions:
        eng.decode_at(a)
    fd._add_candidate(a, 0.95, "seed_vtable_thunk")

n = fd.detect_all(sections)
print(f"\nfunctions={n} candidates={len(fd._candidates)} "
      f"aliases={len(fd._alias_entries)}")
for a in WATCH:
    f = fd.functions.get(a)
    if f:
        print(f"  0x{a:08X}: FUNC 0x{f.start:08X}-0x{f.end:08X} "
              f"({f.detection_method})")
    else:
        alias = fd._alias_entries.get(a)
        inside = None
        for s, ff in fd.functions.items():
            if s <= a < ff.end:
                inside = ff
                break
        tag = f"alias->0x{alias:08X}" if alias else (
            f"inside {inside.name} 0x{inside.start:08X}-0x{inside.end:08X}"
            if inside else "NOT DETECTED")
        print(f"  0x{a:08X}: {tag}")
