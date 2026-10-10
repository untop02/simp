"""M4 read-only probe #2: trace a candidate address through the detector passes."""
import sys

from tools.disasm.loader import load_image
from tools.disasm.engine import DisasmEngine
from tools.disasm.functions import FunctionDetector
from tools.disasm.labels import LabelManager
from tools.disasm.xrefs import build_xrefs

TARGET = 0x0015B100
SECOND = 0x0015A7DF

image = load_image(sys.argv[1], None)
sections = image.get_code_sections()
eng = DisasmEngine(image)
for s in sections:
    eng.linear_sweep(s)
eng.resync_jump_tables()
xrefs = build_xrefs(eng, image)
labels = LabelManager()

fd = FunctionDetector(eng, image, xrefs, labels)

# Seeds (mirror the project's seed set)
seeds = [0x00139860, 0x00139AD0, 0x0013B940, 0x0013CA90, 0x0013D900, 0x0015A7DF]
for a in seeds:
    fd._add_candidate(a, 0.95, "seed_vtable_thunk")


def report(tag):
    in_c = TARGET in fd._candidates
    in_f = TARGET in fd.functions
    end = None
    if in_f:
        end = fd.functions[TARGET].end
    alias = fd._alias_entries.get(TARGET)
    s2c = SECOND in fd._candidates
    s2f = SECOND in fd.functions
    s2end = fd.functions[SECOND].end if s2f else None
    print(f"[{tag}] 15B100 cand={in_c} func={in_f} "
          f"end={('0x%08X' % end) if end else '-'} alias={alias} | "
          f"15A7DF cand={s2c} func={s2f} "
          f"end={('0x%08X' % s2end) if s2end else '-'}")


fd._pass_known_addresses()
for s in sections:
    fd._pass_prologues(s)
for s in sections:
    fd._pass_cc_boundaries(s)
fd._pass_call_targets(sections)
report("after call_targets")
fd._pass_indirect_call_slots()
report("after icall_slots")
fd._build_functions(sections)
report("after build_functions")
fd._pass_tail_jump_targets(sections)
fd.functions.clear()
fd._build_functions(sections)
report("after tail_jump")
fd._pass_imm_ref_targets(sections)
fd.functions.clear()
fd._build_functions(sections)
report("after imm_ref")
fd._pass_gap_prologues(sections)
fd.functions.clear()
fd._build_functions(sections)
report("after gap_prologue")
fd._pass_data_ptr_targets(sections)
report("after data_ptr")
fd._pass_seed_aliases()
fd._build_alias_entries()
report("after alias_entries")

# Who is the next candidate before 0x15B100 in build_functions?
starts = sorted(fd._candidates.keys())
import bisect
i = bisect.bisect_left(starts, TARGET)
print("candidate before 15B100:", f"0x{starts[i-1]:08X}" if i > 0 else None)
print("candidate 15B100 present in list:", TARGET in starts)
print("next candidate after 15B100:", f"0x{starts[i]:08X}" if i < len(starts) else None)
print("total candidates:", len(fd._candidates), "funcs:", len(fd.functions))
print("num insns in 15B100..next:",
      len(eng.get_instructions_in_range(TARGET, starts[i + 1] if i + 1 < len(starts) else TARGET + 0x200)))
