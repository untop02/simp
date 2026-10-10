# M6 Results — Registry Crash Fixed, Stack-Drift Class Eliminated, Audio Init Reached

**Game:** *The Simpsons: Road Rage* (2001), original Xbox (PAL retail, Title ID `0x45410013`).
**Toolkit:** `sp00nznet/xboxrecomp` @ `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` (tag `v0.13.1`), with an
**isolated patched working copy** at `third_party/_m4_xboxrecomp` (upstream left untouched).
**Executable:** `game/The Simpsons Road Rage/build/srr_recomp.exe` (console build, watchdog-driven).
**Host:** Windows (MINGW64). The MacBook M1 target remains unreachable — see `docs/MAC-MIGRATION.md`.

**Verdict: the M5 registry-index crash is fixed, and two further stack-drift defects of the same class were
found and fixed. The game now completes RadSound/audio initialisation and reaches its main loop. It still does
not present a frame (`NV2A PUT=GET=0`); a new, further-along crash in a linked-list walker is the current
blocker.**

> **Do not claim the game boots. It does not render a frame.**

---

## 1. Executive summary

| Outcome tracked | M5 | M6 |
|---|---|---|
| Functions translated | 13,386 | **14,312** |
| Translation failures | 0 | **0** |
| Unresolved stubs | 289 | **152** |
| Runtime ICALL failures | 243 | **5** |
| M5 registry-index crash | present | **FIXED** |
| `sub_00050EC0` / `sub_00050FB0` stubs | present | **FIXED** |
| Main-loop stack leak (`0x00013FF0`) | present | **FIXED** |
| RadSound / audio init | fails (`DSERR_NODRIVER`) | **reaches completion** (with env var) |
| Reaches main loop | no | **yes** |
| NV2A commands submitted | no | **no** — `PUT=GET=0` |
| First frame presented | no | **no** |

---

## 2. Toolkit patches (working copy only)

All patches live in `third_party/_m4_xboxrecomp/tools/disasm/functions.py`. Upstream is unmodified.

1. **Alias-aware tail-jump pass** (carried from M4, `scripts/m4_patch_upstream.py`):
   `_pass_tail_jump_targets(..., include_aliases=True)` re-run after `_pass_data_ptr_targets` to a fixpoint.
2. **D3D section vtable scan guard:** in `_pass_data_ptr_targets`, skip the `D3D` section
   (`if sec.name in code_names and sec.name not in ("D3D",): continue`).
3. **Conditional-branch shared epilogues (NEW):** in `_pass_cond_branch_orphans`, a `jcc` target landing
   *inside another function* now registers an alias when `probes_as_returning_body(target, max_insns=64)`
   passes. MSVC reaches a function's cleanup block via `je`/`ja` as well as `jmp`; the pass previously only
   considered unconditional jumps, so the branch was lifted as a call to a stub that pops only the return
   address, leaking the frame.
4. **Immediate-pass probe cap (NEW):** in `_pass_imm_ref_targets`,
   `probes_as_returning_body(target)` → `probes_as_returning_body(target, max_insns=256)`.

---

## 3. Fixes confirmed this milestone

1. **M5 registry-index crash — FIXED.** Root cause was `0x0017CC32` (a real `ret 4` function) emitted as a
   stub, causing 4-byte stack drift up the dispatch chain. Fixed by patches #1/#2.
2. **`sub_00050EC0` / `sub_00050FB0` stubs — FIXED.** Valid functions (81 and 72 instructions) rejected by the
   64-instruction probe cap. Fixed by patch #4.
3. **Audio init — REACHED.** `sub_0017E85B` polls MCPX APU register `0xFEC00130` for a ready bit; the aperture
   is zeroed unless `RECOMP_AC97_READY=1` is set. With that env var, `sub_0017E986` returns 0, `[sys+0x18]` is
   set, the RadSound envelope constructor gets a valid `field_0x4C`, and audio init completes. **This is an
   environment requirement, not a code bug.**
4. **Main-loop stack leak at `0x00013FF0` — FIXED.** `sub_00094F20` does `sub esp,0x6D0` then tail-jumps to
   `0x000957FB`, a shared epilogue inside `sub_000957ED` reached by `je`/`ja`. `0x000957FB` was undetected →
   stub → **3504 bytes leaked per iteration** (esp drifted `0xF7FFF0` → `0x00000D18`). Fixed by patch #3.

---

## 4. Current blocker (new, further along)

Crash: `fault addr=0x8B09752C (read)`, `eax=0`, `ecx=0x00F7F2D8`, `edx=0`, `esp=0x00F7F2AC`, `ebx=0`,
`esi=0x8B087524`, `edi=0`.

- Faulting site: `sub_00013020+0x60F` → `recomp_0000.c:8969` (`test MEM32(esi+8), eax`). `sub_00013020` is a
  linked-list walker (`esi = MEM32(ecx)` at `loc_00013040`).
- `esi = 0x8B087524` is a **wild pointer** (not a guest address); fault address `0x8B09752C = esi + 8`.
- Call chain: `sub_00013800`-region → `0x0001387A call 0x13020` (return `0x0001387F`) → crash. Caller
  `0x0001376F` (`cmp eax,1`) → `0x0001376A call 0x130B0`.
- Preceded by `[ICALL] Failed to resolve VA 0x0006E940` — a real SEH function at `0x0006E940`, referenced only
  from a `.rdata` table at `0x1BFCA0`; **not detected** (`probes_as_function_body(64)` fails, needs 256).
- `[CS]` critical-section leak still present: `enters=19481 leaves=19479 (outstanding 2)`, guest `0x00223B38`
  (also `0x000B2272`, `0x000B0057`, `0x0009D5B8`, `0x001318FC`, `0x001C7E48`, `0x000B0040`).
- No rendered frame yet.

---

## 5. Open questions / next actions (priority order)

1. **Clean up temporary instrumentation** in the generated files (`recomp_0000.c`, `recomp_0033.c`,
   `recomp_0053.c` contain `#include <stdio.h>` and `[LOOP]`/`[RSSYS-CTOR]`/`[ENV-CTOR]`/`[CTOR]`/`[DTOR]`/
   `[VT48]`/`[22870]`/`[23A90]`/`[E9F9]` `fprintf` lines). Cleanest path: re-run the pipeline (overwrites all
   `.c` files).
2. **Investigate the `sub_00013020` crash.** Determine what list it walks (`ecx` = `this`, `[this+0x40..0x80]`
   bucket array, `esi = MEM32(ecx)`) and which caller passes the bad list.
3. **Decide on `0x0006E940`.** Raising `probes_as_function_body` to 256 in `_pass_data_ptr_targets` regressed
   stubs (152 → 161); reverted. Consider a targeted fix (instruction-boundary + not `int3`/`nop`, or a
   `.rdata`-table-specific pass) and re-measure.
4. **Re-check the `[CS]` critical-section leak** (`0x00223B38`, 2 outstanding enters).
5. Only after the guest reaches graphics: NV2A pushbuffer, `PUT`/`GET`, first frame. Do **not** port the
   graphics backend before the guest reaches graphics submission.

---

## 6. Reproduction

Pipeline (run from `third_party/_m4_xboxrecomp`, `PYTHONPATH=.`):

```
py -3 -m tools.disasm "$XBE" --seed-functions "$S1" --seed-functions "$S2" --force
py -3 -m tools.func_id "$XBE"
py -3 -m tools.abi_analysis "$XBE"
py -3 -m tools.recomp "$XBE" --game-name "The Simpsons Road Rage" --all --split 250 \
  --gen-dir "D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/gen"
```

where `XBE=game/The Simpsons Road Rage/default.xbe`,
`S1=.../src/recomp/seed_functions.json`, `S2=.../src/recomp/seed_function_starts.json`.
**Never use `--text-only`.**

Build (cmake not on PATH):

```
"/c/Users/kabyl/AppData/Roaming/Python/Python314/Scripts/cmake.exe" \
  --build "game/The Simpsons Road Rage/build"
```

Run:

```
RECOMP_AC97_READY=1 RECOMP_WATCHDOG_SECS=15 RECOMP_KERNEL_LOG_BUDGET=4000 \
  timeout 120 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m6_runN.log 2>&1
```

(exit 139 = real crash, 127 = watchdog/exit path.)

---

## 7. Pitfalls

- **`RECOMP_AC97_READY=1` is required** to get past DirectSound init; without it you get `DSERR_NODRIVER` and a
  downstream null-deref that looks like a code bug but is not.
- The M5 hypothesis that `sub_00117460`'s argument offsets are mis-lifted is **REFUTED** — the lift is
  byte-faithful. Do not re-investigate.
- The M5 "ABI-check flags `sub_001226F0`" lead was a **symptom, not the cause**.
- Raising `probes_as_function_body` to 256 in `_pass_data_ptr_targets` **regressed stubs (152 → 161)**. The
  64-cap is load-bearing; do not raise it globally without measuring.
- Raising the cond-branch-orphan probe to 256 added 519 aliases vs 290 at 64; 64 was kept.
- `.rdata` is **not** in `image.get_code_sections()`, so adding it to the `_pass_data_ptr_targets` exception
  does nothing.
- Generated `.c` files do **not** include `<stdio.h>`; adding `fprintf` instrumentation requires adding the
  include to that file.
