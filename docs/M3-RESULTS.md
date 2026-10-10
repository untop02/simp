# M3 Results — Pure3D/PDDI `NewRenderContext()` Failure

**Game:** *The Simpsons: Road Rage* (2001), original Xbox (PAL retail, Title ID `0x45410013`).
**Toolkit:** `sp00nznet/xboxrecomp` @ `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` (tag `v0.13.1`), **unmodified, clean tree**.
**Executable:** `game/The Simpsons Road Rage/build/srr_recomp.exe` (console build, watchdog-driven).
**Verdict:** **Outcome B — verified blocker, with the root cause of the M2 failure found and fixed.**
The failure the task asked about (`NewRenderContext() failed`, guest `0x000AFEC0`) has been traced
to a *specific, fixed* defect. A **second, independent and systemic** defect on the same path
(undetected functions whose auto-generated stubs have the wrong stack cleanup) now blocks
successful render-context initialisation. Both are documented below with exact evidence.

> **Do not claim the game boots. It does not.** No frame is presented (`NV2A PUT=GET=0`).

---

## 1. Executive summary

The work was driven by one question: **why does `NewRenderContext()` (`0x000AFEC0`) fail?**

**Answer (verified from generated C + XBE bytes + runtime trace):** the Pure3D/PDDI
render-context **constructor was never detected as a function**. It is tail-called by the
vtable method `0x00139440` (render-context vtable slot `+0x14`), but the disassembler's
`tail_jump_alias` pass swallowed `0x00139AD0` into the preceding 8-byte function
`sub_00139AC0` as an *alias*, so the recompiler emitted `sub_00139AD0` as an
**unresolved no-op stub** (`void sub_00139AD0(void){ g_esp += 4; }`). The freshly allocated
`0x45C`-byte context object was therefore returned **unconstructed — with a null vtable**.
The very next virtual call (`call [edx+0x14]` on that object) dereferenced the null vtable,
producing the `[ICALL] target 0x00000000 … skipped` seen in M2, and the context was never
built. This is the direct, mechanical cause of `NewRenderContext() failed`.

**Fix applied (supported mechanism, no upstream edit):** seed `0x00139AD0` and its sibling
constructors as function entry points (`src/recomp/seed_function_starts.json`), re-run the
documented `disasm --seed-functions --force → func_id → abi_analysis → recomp` pipeline.
After the fix the constructor is lifted for real and **installs the vtable `0x1DAAD0`**; the
context object is properly built and the second vtable call receives a valid object
(`this=0x00F83300`). **The M2 root cause is removed.**

**But** the path then exposes a *different* defect: two more **undetected functions on the
render-context path** — `0x0015A7DF` and `0x0015B100` — are stubbed with the wrong stack
cleanup, leaking 4 bytes each and drifting `esp` by 4. At guest `0x000AFF3D` the code reads
`ctx` from `[esp+0xC]`; with esp 4 bytes short it reads the wrong slot, the **third** vtable
call (`ctx->vfn[0x18]` = `0x00139470`) mis-dispatches, so the context is still not built and
`NewRenderContext() failed` is printed again — now for a *legitimate* reason rather than a
null-vtable artefact. The guest then takes its error path holding engine lock `0x00223B38`
(the M2 leak) and the run ends in the familiar IRQL spin with `NV2A PUT=GET=0`.

**This second defect is systematic**, not title-specific: it is the same
*function-boundary / stub-cleanup* class as the constructor. Blanket seeding of the suspected
stubs made detection **worse** (§7), so a clean fix belongs in the toolkit's boundary
detection, not in a title-specific hack.

---

## 2. Environment

Unchanged from M1/M2: Windows 11, Git Bash, Python 3.14 (`py -3`), CMake + Ninja + **Zig**
(no MSVC). `D:` ≈ 36 GB free. The toolkit builds and links the 56 MB `srr_recomp.exe` with
the M0 Zig recipe (see §11).

---

## 3. The failure, traced precisely (verified)

### 3.1 What the code actually does

`sub_000AFEC0` (render-context constructor, `recomp_0020.c:1571`) executes, in order:

1. `sub_00139560(0xE, 5, &ctx)` — **PDDI init**. Returns `eax=1` (success); no error string.
2. `ctx->vfn[0x14]()` — vtable `0x1DAA24`, slot `+0x14` = **`sub_00139440`** — allocates `0x45C`
   and **tail-jumps to the real constructor `0x00139AD0`**.
3. `esi->vfn[0x14](…)` — a second virtual call on the object returned by step 2.
4. `ctx->vfn[0x18](esi)` — slot `+0x18` = **`sub_00139470`**.
5. log `"NewRenderContext() failed"` (`0x001C8814`) with a `setne` flag = result of step 4.

`sub_00139AD0` (bytes verified `56 8B F1 E8 …` = `push esi; mov esi,ecx; call …`) is the true
constructor: at `0x00139AF0` it executes `C7 06 D0 AA 1D 00` = `mov dword [esi], 0x1DAAD0`,
i.e. **it writes the object's vtable**. Its vtable `0x1DAAD0` is fully populated in the XBE
(all 16 entries resolve to lifted functions).

### 3.2 Why it failed

| Step | Evidence |
|---|---|
| `0x00139AD0` is **not** in `functions.json` as a start | containment query: it sits inside `sub_00139AC0` (0x139AC0–0x139B60, `detection_method="tail_jump_alias"`) |
| The bytes at `0x139AC0` are an 8-byte function then 7 NOPs, then the ctor | `0x139AC0 push 0; call 0x13E060; pop ecx; ret` / `90×7` / `0x139AD0 push esi; mov esi,ecx; …` |
| The recompiler emitted a **stub** for it | `recomp_stubs_unresolved.c`: `void sub_00139AD0(void) { g_esp += 4; /* 0x00139AD0: not detected */ }` |
| ⇒ the `0x45C` object is returned unconstructed (null vtable) | M2 log: `[ICALL] target 0x00000000 is not code -- skipped …` immediately before `[GUEST] NewRenderContext() failed` |

The `tail_jump_alias` handler (`tools/disasm/functions.py:872 _build_alias_entries`) is meant
to give a tail-jump target a callable second body. Here the target landed *inside* the body of
the tail-jump-alias function `sub_00139AC0` itself, so no alias body was created for
`0x00139AD0` — it was only ever referenced by name, and the recompiler stubbed it.

---

## 4. Audit of the existing graphics implementation

Read: `src/d3d/*` (`d3d8_device.c`, `xbox_Direct3DCreate8`), `src/kernel/nv2a_pb_exec.c`,
`nv2a_pb_scan.c`, `nv2a_combiner.c`, `nv2a_vsh_interp.c`, `src/kernel/xbox_memory_layout.c`
(NV2A aperture, watchdog), `src/apu/*`, `templates/new-game/*`, `docs/technical/d3d-translation.md`,
`src/d3d/README.md`.

Findings:

- The toolkit's **D3D8→D3D11 backend (`xbox_d3d8`) is never entered** for this title — no
  `D3D8:` line is ever printed. The guest statically links its **own** Xbox D3D8 (`D3D` section
  at VA `0x0015A740`) and calls into it directly. That backend is **not** the fix here, and the
  M3 task's instruction not to assume it was correct.
- The failure is **entirely upstream of the host graphics layer**: it happens in the guest's
  Pure3D/PDDI object construction, before any device is created or any pushbuffer is touched
  (`NV2A PUT=GET=0` throughout).
- No project-side initialisation hook was missing. The template wiring
  (`main.c` → `xbox_MemoryLayoutInit` → `xbox_kernel_init` → `xbox_kernel_bridge_init` →
  `xbe_entry_point`) is complete and functioning; the gap is in the **guest code translation**
  (missed function boundaries), which no amount of host wiring fixes.

---

## 5. The fix (smallest justified, project-side)

Add the missed function entry points to a **seed list** and re-run the supported pipeline.
`src/recomp/seed_function_starts.json` (new) holds six addresses, each individually justified:

| VA | Why it must be a function |
|---|---|
| `0x00139AD0` | the render-context ctor (tail-jumped by `sub_00139440`, slot `+0x14`); installs vtable `0x1DAAD0` — **root cause** |
| `0x00139860` | PDDI cluster getter (tail-jump target), was stubbed |
| `0x0013B940` | PDDI cluster ctor (tail-jump target), was stubbed |
| `0x0013CA90` | render-context ctor (tail-jumped by `sub_001394B0`, slot `+0x1C`) |
| `0x0013D900` | render-context ctor (tail-jumped by `sub_001394D0`, slot `+0x20`) |
| `0x0015A7DF` | epilogue block of `sub_0015A760` reached by `jge`; its stub modelled only `ret 0x18` and omitted the block's `pop esi` |

Each was verified to be real code (valid prologue / `ret`, referenced by a tail-jump or call
xref) before seeding. `--seed-functions` is the toolkit's documented mechanism for exactly
this (`tools/disasm/__main__.py` help; used in M1 for the same class of miss).

**Verification that the fix works** (runtime, `RECOMP_M3_TRACE=1`, `logs/m3_run5.log`):

```
[M3] >00139440 this=00F832E0 esp=00F7F1A8     # first vtable call, ctx
[M3] <00139440 ret=00000000 esp=00F7F1B0     # esp now balances exactly (+8 = ret 4 + arg 4)
[M3] >00139730 this=00F83300 esp=00F7F190     # second call: this is the CONSTRUCTED object
```
`0x00F83300` is the object allocated by `0x139440`/`0x139AD0`, and its vtable is now
`0x1DAAD0` (set by the newly-lifted ctor). Before the fix the same call skipped as a null
target. **The M2 root cause is removed.**

---

## 6. Why it still fails: a second, systemic defect (verified)

With the path executing correctly, `sub_00139730` (second vtable call, `ctx` device vtable
slot `+0x14`) runs and internally calls `sub_0015A760`, which tails into `0x0015A7DF` and calls
`0x0015B100`. Two of these are **undetected-function stubs with wrong stack cleanup**:

- `0x0015A7DF` (before the seed): stub did `g_esp += 28` (models `ret 0x18`) but the block is
  `mov eax,[esp+0x1c]; test; …; pop esi; ret 0x18` — **the `pop esi` was omitted**.
- `0x0015B100` (still a stub after the final build): stub does `g_esp += 4`, but the original
  is `sub esp,0x168; …; pop esi; add esp,0x168; ret 4` (stdcall), so it **leaks the argument**.

Runtime esp trace (`--trace-functions`, `logs/m3_run6.log`):

```
sub_00139730 entry            esp=00F7F190
  sub_0015A760 entry          esp=00F7F168
    sub_0015A7DF entry        esp=00F7F160
    sub_0015A7DF exit         esp=00F7F164     # +4, then +ret 0x18 -> block total 32 (ok)
  @after call 0x0015A760      esp=00F7F180     # +0x18 = +24, should be +28  <-- 4 leaked
  @after call 0x0015B100      esp=00F7F160     # unchanged: stub popped only the ret, arg leaked
  ... sub_00139730 exit       esp=00F7F18C     # 4 bytes short of 00F7F190
```

Consequently at guest `0x000AFF3D` the code reads `ctx` from `[esp+0xC]` four bytes off, the
**third** vtable call (`ctx->vfn[0x18]` = `sub_00139470`) mis-dispatches, the context is never
built, and `NewRenderContext() failed` is printed again — this time because a real call-chain
fault, not a null vtable. The guest then returns holding engine lock `0x00223B38` on its error
path (M2's leak), the worker deadlocks, and the main thread enters the IRQL spin
(`esp=0x00F7F154`). **`NV2A PUT=GET=0`: no command is ever submitted.**

Note that seeding `0x0015B100` does **not** fix it cleanly: the detector measures its end at the
first `ret 4` (`0x15B147`), orphaning the function's own success path (its `jne 0x15b147`
leaves the seeded range). That is why it is left as a documented stub rather than papered over.

---

## 7. Blanket seeding is *not* a safe fix (verified — important negative result)

To test whether the whole stub class could be cleared:

| Seed set | Functions | Stubs | Result |
|---|---|---|---|
| none (M2) | 13,041 | 533 | null vtable → `NewRenderContext() failed` |
| 6 (this fix) | 13,042 | 527 | ctor runs; esp drift ⇒ `NewRenderContext() failed` |
| 144 tail-call-target stubs | 13,255 | 462 | **`0x139AD0` reverted to a stub**; new stack corruption (`esp=0xFFFFFFD0`) |
| 222 "gap" stubs + 6 | 13,338 | **576** | detection perturbed: *more* stubs, severe corruption |

Blanket seeding shifts the detector's outcome unpredictably and can re-stub the very function
being fixed. This is direct evidence that the remaining problem is a **toolkit
function-boundary/stub-cleanup limitation**, and that the correct fix is upstream (or a
principled stack-balance audit), not more per-address seeds.

---

## 8. Verification summary (the five items, reported separately)

Measured with `logs/m3_final.log` (watchdog 10 s) and the traced runs:

| # | Item | Result |
|---|---|---|
| 1 | **PDDI initialization succeeds** | **YES** — `sub_00139560` returns `eax=1`; no "Cannot initialize PDDI library" string. (Unchanged from M2.) |
| 2 | **Leaked critical section resolved** | **NO** — `[CS] enters=… leaves=… (outstanding 2)`; `0x00223B38` still leaked on the failure path |
| 3 | **Wait loop exits** | **NO** — watchdog `esp=0x00F7F154` (the M2 IRQL-spin site) |
| 4 | **First graphics commands submitted (`PUT`/`GET`)** | **NO** — `NV2A USER PUT=00000000 GET=00000000` |
| 5 | **A frame is presented** | **NO** |

So the *observable* boot outcome is unchanged from M2 — but the failure is now **understood
and its first cause fixed**, and the next cause is identified to the byte.

---

## 9. Files changed

| File | Change | Reversible |
|---|---|---|
| `game/The Simpsons Road Rage/src/recomp/seed_function_starts.json` | **new** — 6 verified function seeds (5 PDDI ctors + `0x15A7DF`) | delete to revert |
| `game/The Simpsons Road Rage/src/recomp/trace_m3.json` | **new** — `--trace-functions` list (diagnostic only) | delete |
| `game/The Simpsons Road Rage/src/recomp_manual.c` | added `RECOMP_M3_TRACE`-gated diagnostic wrappers for the render vtable methods (off by default; calls the real bodies unchanged) | remove the block |
| `game/…/src/recomp/gen/*` | regenerated by the documented pipeline (git-ignored) | rerun pipeline |
| `logs/m3_*.log` | run/trace/build logs (git-ignored) | delete |
| `docs/M3-RESULTS.md` | this document | — |

**No upstream file was modified** (`third_party/xboxrecomp` is byte-identical at
`193e2995…`). **Nothing is committed.** Watchdogs and diagnostics are preserved; no failure
message was suppressed and no render context was faked.

---

## 10. Remaining unverified / open questions

- Whether *all* remaining render-path stack drift is caused by this one stub class, or whether
  some is a genuine lifter bug. Only two instances were chased to the byte.
- Whether the correct resolutions are (a) an upstream fix to `_build_alias_entries` /
  `_find_function_end` so tail-jump targets inside an alias body get real bodies, and
  (b) stub generation that does not guess `g_esp += 4` for a `call`-referenced gap function.
- Whether the toolkit's host `xbox_d3d8` backend needs to replace the guest's statically
  linked D3D8 at all — not yet reachable.

---

## 11. Exact commands (this milestone)

Run from the repo root; the pipeline runs from `third_party/xboxrecomp`.

```sh
# 1. Re-analyse + re-lift with the seeds (supported mechanism)
cd third_party/xboxrecomp
XBE="D:/simpsons recomp/game/The Simpsons Road Rage/default.xbe"
S1="D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/seed_functions.json"
S2="D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/seed_function_starts.json"
py -3 -m tools.disasm "$XBE" --text-only --seed-functions "$S1" --seed-functions "$S2" --force
# M4 correction: drop --text-only. It sweeps only .text and leaves the SDK code
# sections (D3D, DSOUND, BINK, XGRPH, XPP, DOLBY) un-disassembled, so functions
# reachable only from within them (0x0015B100) become stubs. See M4-RESULTS.md.
py -3 -m tools.func_id "$XBE"
py -3 -m tools.abi_analysis "$XBE"
py -3 -m tools.recomp "$XBE" --game-name "The Simpsons Road Rage" --all --split 250 \
  --gen-dir "D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/gen"
# (add --trace-functions <trace_m3.json> to instrument specific functions)

# 2. Build (M0 Zig recipe)
cd "D:/simpsons recomp"
cmake --build "game/The Simpsons Road Rage/build"

# 3. Run (watchdog is the bounded harness; exit code 3 = watchdog, not a failure)
RECOMP_WATCHDOG_SECS=10 RECOMP_KERNEL_LOG_BUDGET=1200 \
  timeout 40 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m3_final.log 2>&1
# with the vtable-method trace:
RECOMP_M3_TRACE=1 RECOMP_WATCHDOG_SECS=8 RECOMP_KERNEL_LOG_BUDGET=50 \
  timeout 30 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m3_run5.log 2>&1
```

---

## 12. Single best next step

**Fix the function-boundary/stub-cleanup class in the toolkit, then re-lift.**

Concretely, the next milestone should:

1. **Repair `_build_alias_entries` / `_find_function_end`** so a tail-jump target that lands
   inside a `tail_jump_alias` body becomes its own real function (this is exactly what hid
   `0x00139AD0`), and so a function reached by `call` into a code gap is detected as a
   function with its true extent — not stubbed with a guessed `g_esp += 4`.
   This is upstream work; keep it out of the title's tree.
2. **Add a stack-balance check** to the bring-up harness: instrument each lifted function to
   assert `esp` returns to its entry value (net = declared `ret N`). That converts "silent
   esp drift ⇒ mis-dispatch ⇒ mysterious `NewRenderContext() failed`" into a named function,
   which is the single most useful diagnostic this title needs.
3. Only after the render context builds successfully, revisit the M2 lock leak
   (`0x00223B38`) and the wait loop, then the host graphics path.

Secondary, cheap: keep the `RECOMP_M3_TRACE` wrappers; they already name the render vtable
calls, their `this`, and their esp, which is how this milestone's path was pinned.
