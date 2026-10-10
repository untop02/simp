"""M4 read-only probe: inspect the disasm engine's raw state for a set of VAs.

Usage: py -3 scripts/m4_probe.py <xbe> <hex-va> [<hex-va> ...]
"""
import sys

from tools.disasm.loader import load_image
from tools.disasm.engine import DisasmEngine

ADDRS = [int(a, 16) for a in sys.argv[2:]]

image = load_image(sys.argv[1], None)
print(f"base=0x{image.base_address:08X} entry=0x{image.entry_point:08X}")
code_secs = image.get_code_sections()
print("code sections:", ", ".join(s.name for s in code_secs))
for s in image.sections:
    if 0x0015A740 <= s.virtual_addr < 0x00160000:
        print(f"  section {s.name}: va=0x{s.virtual_addr:08X} "
              f"vsize=0x{s.virtual_size:X} raw=0x{s.raw_addr:08X} "
              f"rsize=0x{s.raw_size:X} exec={s.executable} flags={s.flags} "
              f"in_code={s in code_secs}")

eng = DisasmEngine(image)
for s in code_secs:
    eng.linear_sweep(s)
eng.resync_jump_tables()

ctargets = eng.get_call_targets()
print(f"\ncall targets: {len(ctargets)}")

for a in ADDRS:
    print(f"\n=== 0x{a:08X} ===")
    sec = image.get_section_at_va(a)
    print(f"  section={sec.name if sec else None} "
          f"exec={sec.executable if sec else None}")
    insn = eng.instructions.get(a)
    if insn:
        print(f"  decoded: 0x{insn.address:08X} {insn.mnemonic} {insn.op_str}")
    else:
        print("  NOT a decoded instruction start")
    cov = eng.instruction_covering(a)
    if cov:
        print(f"  covered by insn at 0x{cov.address:08X} "
              f"({cov.mnemonic} {cov.op_str}, size {cov.size})")
    else:
        print("  no instruction covers it")
    print(f"  call target? {a in ctargets}")
    print(f"  probes_as_function_body? {eng.probes_as_function_body(a)}")
    print(f"  probes_as_prologue? {eng.probes_as_prologue(a)}")
    print(f"  probes_as_constant_stub? {eng.probes_as_constant_stub(a)}")

# Who calls 0x15B100?
print("\n=== callers of 0x15B100 ===")
for insn in eng.instructions.values():
    if insn.call_target == 0x0015B100:
        print(f"  call at 0x{insn.address:08X}")
