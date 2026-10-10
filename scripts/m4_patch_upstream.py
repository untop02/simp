"""Apply the M4 alias-aware tail-jump fix to the isolated toolkit copy.

Target: third_party/_m4_xboxrecomp/tools/disasm/functions.py
Idempotent: re-running after the patch is applied is a no-op.

The fix has two parts:
  1. _pass_tail_jump_targets gains `include_aliases`, so the ranges in
     self._alias_entries are treated as code regions too.
  2. detect_all re-runs the tail-jump loop after _pass_data_ptr_targets (which
     is what creates vtable/data-table alias entries), so tail jumps whose
     source lives inside an alias-only body are followed.
"""
import sys

PATH = "third_party/_m4_xboxrecomp/tools/disasm/functions.py"

OLD_SIG = (
    "    def _pass_tail_jump_targets(self, sections: List[SectionInfo]) -> bool:\n"
)
NEW_SIG = (
    "    def _pass_tail_jump_targets(self, sections: List[SectionInfo],\n"
    "                                include_aliases: bool = False) -> bool:\n"
)

OLD_BODIES = (
    "        bodies = sorted((f.start, f.end) for f in self.functions.values())\n"
    "        starts = [b[0] for b in bodies]\n"
    "        added = False\n"
    "\n"
    "        for insn in self.engine.instructions.values():\n"
    "            if not insn.is_jump or insn.is_cond_jump:\n"
)
NEW_BODIES = (
    "        bodies = sorted((f.start, f.end) for f in self.functions.values())\n"
    "        if include_aliases and self._alias_entries:\n"
    "            # A body that exists only as an alias entry (a vtable/data-table\n"
    "            # entry materialised by _build_alias_entries at the very end) is\n"
    "            # still code a tail jump can live inside. Without it, a `jmp`\n"
    "            # there looks like it is in no known function and is skipped.\n"
    "            #\n"
    "            # A gap alias can carry an end measured before the later bodies\n"
    "            # existed (see _build_alias_entries), so clamp each region to the\n"
    "            # next region start: an over-long alias must not swallow a real\n"
    "            # function's tail jump and hide it.\n"
    "            region_starts = sorted(set(b[0] for b in bodies)\n"
    "                                   | set(self._alias_entries))\n"
    "            for _addr, _end in self._alias_entries.items():\n"
    "                if _end <= _addr:\n"
    "                    continue\n"
    "                _k = bisect.bisect_right(region_starts, _addr)\n"
    "                if _k < len(region_starts):\n"
    "                    _end = min(_end, region_starts[_k])\n"
    "                bodies.append((_addr, _end))\n"
    "            bodies.sort()\n"
    "        starts = [b[0] for b in bodies]\n"
    "        added = False\n"
    "\n"
    "        for insn in self.engine.instructions.values():\n"
    "            if not insn.is_jump or insn.is_cond_jump:\n"
)

OLD_DETECT = (
    "        # materialised by _build_alias_entries once boundaries are final.\n"
    "        self._pass_data_ptr_targets(sections)\n"
)
NEW_DETECT = (
    "        # materialised by _build_alias_entries once boundaries are final.\n"
    "        self._pass_data_ptr_targets(sections)\n"
    "\n"
    "        # The tail-jump loop above ran before any alias entry existed, so a\n"
    "        # tail jump whose source lies inside a body that is only an alias\n"
    "        # entry (a vtable/blocks entry materialised later) was dropped. Now\n"
    "        # that the data-pointer pass has registered those aliases, re-run the\n"
    "        # pass treating alias ranges as code regions, to a fixpoint.\n"
    "        aliased = 0\n"
    "        for _round in range(8):\n"
    "            before = len(self._candidates)\n"
    "            if not self._pass_tail_jump_targets(sections,\n"
    "                                                include_aliases=True):\n"
    "                break\n"
    "            aliased += len(self._candidates) - before\n"
    "            self.functions.clear()\n"
    "            self._build_functions(sections)\n"
    "        if aliased:\n"
    "            print(f\"  tail-jump pass (aliases): +{aliased} standalone\")\n"
)


def main():
    with open(PATH, "r", encoding="utf-8", newline="") as f:
        src = f.read()

    if NEW_SIG in src:
        print("already patched")
        return 0

    for old, new in ((OLD_SIG, NEW_SIG), (OLD_BODIES, NEW_BODIES),
                     (OLD_DETECT, NEW_DETECT)):
        if src.count(old) != 1:
            print(f"ERROR: anchor not found exactly once "
                  f"({src.count(old)}): {old[:60]!r}", file=sys.stderr)
            return 1
        src = src.replace(old, new)

    with open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    print("patched", PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
