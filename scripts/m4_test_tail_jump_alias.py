"""A tail jump inside an alias-only body is followed when aliases are included.

The detector keeps two kinds of code region: real bodies in ``self.functions``
and alias entries in ``self._alias_entries`` (a vtable/data-table entry, or a
conditional-branch orphan). The tail-jump pass originally looked only at
``self.functions``, so a ``jmp`` whose *source* sat inside a body that exists
only as an alias entry was miscounted as "not inside any known function" and
dropped. Its target then got no body and was emitted as a stub that returned
without unwinding the frame.

The Simpsons: Road Rage (original Xbox) hits this exactly:
  * 0x00139440 is a vtable entry, so it is an alias, not a candidate;
  * the `jmp 0x139AD0` at 0x13945E lives inside it;
  * 0x139AD0 is the PDDI render-context constructor. Dropped, it was stubbed
    with a null vtable, and NewRenderContext() failed.

These tests use in-memory fakes, like test_alias_bounds.py.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.disasm.functions import FunctionDetector, Function  # noqa: E402

SEC_LO, SEC_HI = 0x1000, 0x2000


class _Insn:
    def __init__(self, addr, jmp=None):
        self.address = addr
        self.end_address = addr + 4
        self.is_ret = False
        self.is_jump = jmp is not None
        self.is_cond_jump = False
        self.is_branch = jmp is not None
        self.jump_target = jmp
        self.jump_table = None


class _Section:
    name = "TEXT"
    virtual_addr = SEC_LO
    virtual_size = SEC_HI - SEC_LO
    raw_size = SEC_HI - SEC_LO
    executable = True


class _Image:
    def get_section_at_va(self, addr):
        return _Section() if SEC_LO <= addr < SEC_HI else None


class _Engine:
    jump_tables = {}

    def __init__(self, insns):
        self.instructions = {i.address: i for i in insns}

    def get_instruction(self, addr):
        return self.instructions.get(addr)

    def get_instructions_in_range(self, lo, hi):
        return [i for a, i in sorted(self.instructions.items()) if lo <= a < hi]


class _Labels:
    def get(self, addr):
        return None

    def auto_name_function(self, *args):
        pass


def _detector(insns, functions, aliases):
    det = FunctionDetector.__new__(FunctionDetector)
    det.engine = _Engine(insns)
    det.image = _Image()
    det.labels = _Labels()
    det.functions = {s: Function(start=s, end=e, name=f"sub_{s:08X}")
                     for s, e in functions}
    det._candidates = {}
    det._alias_entries = dict(aliases)
    return det


class TailJumpInAliasBodyTest(unittest.TestCase):
    # 0x1440 is an alias-only body [0x1440, 0x1470); 0x14C0 is another
    # alias-only body [0x14C0, 0x1500). A tail jump inside the first targets an
    # address inside the second.
    SRC, SRC_END = 0x1440, 0x1470
    TGT, TGT_BODY_END = 0x14D0, 0x1500

    def _run(self, include_aliases):
        insns = [_Insn(self.SRC, jmp=self.TGT), _Insn(self.TGT)]
        det = _detector(insns, functions=[], aliases={
            self.SRC: 0x1600, self.TGT - 0x10: self.TGT_BODY_END})
        det._pass_tail_jump_targets([_Section()], include_aliases=include_aliases)
        return det

    def test_without_aliases_the_jump_is_missed(self):
        det = self._run(include_aliases=False)
        self.assertNotIn(self.TGT, det._alias_entries)
        self.assertNotIn(self.TGT, det._candidates)

    def test_with_aliases_the_jump_target_becomes_an_alias(self):
        det = self._run(include_aliases=True)
        self.assertEqual(det._alias_entries.get(self.TGT), self.TGT_BODY_END)
        # The enclosing alias body is not split: 0x14C0 keeps its own end.
        self.assertEqual(det._alias_entries[self.TGT - 0x10], self.TGT_BODY_END)

    def test_a_jump_inside_a_real_body_still_works(self):
        insns = [_Insn(self.SRC, jmp=self.TGT), _Insn(self.TGT)]
        det = _detector(insns, functions=[(self.SRC, self.SRC_END)],
                        aliases={self.TGT - 0x10: self.TGT_BODY_END})
        det._pass_tail_jump_targets([_Section()], include_aliases=True)
        self.assertEqual(det._alias_entries.get(self.TGT), self.TGT_BODY_END)

    def test_an_intra_alias_branch_is_not_a_tail_jump(self):
        # A jump that stays inside the alias body that contains it is not a
        # tail call and must not register the target.
        insns = [_Insn(self.SRC, jmp=self.SRC + 8), _Insn(self.SRC + 8)]
        det = _detector(insns, functions=[],
                        aliases={self.SRC: self.SRC_END})
        det._pass_tail_jump_targets([_Section()], include_aliases=True)
        self.assertNotIn(self.SRC + 8, det._alias_entries)
        self.assertNotIn(self.SRC + 8, det._candidates)


if __name__ == "__main__":
    unittest.main()
