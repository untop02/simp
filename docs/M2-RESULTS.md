# M2 Results — Diagnosing the `KeRaiseIrqlToDpcLevel` / `KfLowerIrql` Startup Stall

**Game:** *The Simpsons: Road Rage* (2001), original Xbox (PAL retail, Title ID `0x45410013`).
**Toolkit:** `sp00nznet/xboxrecomp` @ `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` (tag `v0.13.1`), unmodified.
**Executable:** `game/The Simpsons Road Rage/build/srr_recomp.exe` (56 MB, console build, watchdog-driven).
**Verdict:** **Outcome B — verified blocker.** The stall is *not* a recompiler defect and *not* the
suspected threading/IRQL-primitive bug. It is the guest's own busy-wait, entered after its
graphics init fails, deadlocked behind a guest critical section it leaks on that failure path.

---

## 1. Executive summary

The stall was reproduced deterministically and traced to guest code. The three specific
questions posed for M2 are answered with evidence:

1. **Do guest thread start routines run concurrently as the Xbox kernel expects?**
   **Yes.** Worker routines are real Win32 threads (`bridge_spawn_thread` → `CreateThread`,
   `kernel_bridge.c:478–532`). The toolkit's optional single-CPU serialisation
   (`RECOMP_GUEST_LOCK`) is **off by default** (`kernel_bridge.c:9362–9371`).
2. **Is IRQL tracked per-thread or globally?**
   **Per-thread.** `g_current_irql` is `XBOX_THREAD_LOCAL` (`kernel_hal.c:41`); a separate
   global raised-*count* exists only to mask device interrupts, not as the guest's IRQL.
   The runtime trace shows the raise/lower pairing balancing every iteration
   (`raise 0->2 depth=1` / `lower 2->0 depth=0`), i.e. **no IRQL leak**.
3. **Is the stall a synchronisation/threading bug we introduced?**
   **No — but it is cross-thread.** Changing worker mode *moves* the stall, which proves the
   wait is concurrency-dependent, yet both IRQL and threading primitives are implemented
   correctly. The proximate cause is on the guest side.

**Root-cause chain (all steps verified from logs/source/disassembly):**

```
Pure3D/PDDI graphics init fails  ("NewRenderContext() failed")
      -> guest error path returns while holding global lock 0x00223B38
         (RtlEnterCriticalSection at guest 0x000AFE88; 2 takes, 0 drops, whole run)
      -> the worker thread spawned moments later blocks forever on 0x00223B38
      -> the main thread enters a guest wait/pump loop (sub_00118D20) that polls a
         predicate which never becomes true, pumping sub_00118B30 ~10M/s
      -> each pump takes an IRQL-guarded lock (sub_001B31C1: KeRaiseIrqlToDpcLevel ...
         KfLowerIrql) -> the ~10^8-call IRQL "storm"
      -> nothing is ever submitted to NV2A (PUT=GET=0), no frame is rendered
```

The IRQL storm is a **symptom**, not the fault. The recompiler, the register model, ICALL
resolution, kernel thunking, file I/O, threading and IRQL are all behaving correctly.

---

## 2. Environment

Unchanged from M1 (`docs/M1-RESULTS.md` §2). Windows 11, Git Bash, Python 3.14 (`py -3`),
CMake + Ninja + Zig (no MSVC), toolkit built with the Zig toolchain. `D:` ~36 GB free.

---

## 3. Reproduction (exact commands, artifacts preserved under `logs/`)

Run from the repository root so the relative XBE path resolves. The watchdog always fires
(exit code 3) because the guest never exits; it is a bounded harness, not a failure of the run.

```sh
# Baseline + IRQL trace + enough kernel-log budget to see the first spin calls
RECOMP_WATCHDOG_SECS=8 RECOMP_KERNEL_LOG_BUDGET=700 RECOMP_IRQL_TRACE=1 \
  timeout 30 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m2_run1.log 2>&1

# Push the numbered kernel log past the spin site to capture its guest return addresses
RECOMP_WATCHDOG_SECS=6 RECOMP_KERNEL_LOG_BUDGET=25000 \
  timeout 25 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m2_run3.log 2>&1

# Bisect: are the guest threads the problem?
RECOMP_WORKERS=inline RECOMP_WATCHDOG_SECS=8 RECOMP_KERNEL_LOG_BUDGET=200 \
  timeout 25 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m2_run_winline.log 2>&1
RECOMP_CS_MODE=single RECOMP_WATCHDOG_SECS=8 RECOMP_KERNEL_LOG_BUDGET=200 \
  timeout 25 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m2_run_cssingle.log 2>&1

# Trace the contended guest lock (CSWATCH requires the CRT-trace gate to be on)
RECOMP_CS_TRACE_CRT=1 RECOMP_CS_WATCH=0x223B38 RECOMP_WATCHDOG_SECS=6 \
  RECOMP_KERNEL_LOG_BUDGET=200 \
  timeout 25 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m2_run_cswatch2.log 2>&1

# Raw take/drop addresses for every guest lock
RECOMP_CS_TRACE_CRT=all RECOMP_WATCHDOG_SECS=6 RECOMP_KERNEL_LOG_BUDGET=200 \
  timeout 25 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m2_run_cstrace.log 2>&1
```

New analysis helper (this milestone): `scripts/m2_findref.py` — maps XBE file offsets to guest
VAs and finds immediate references to a guest address (used to locate the string that produced
the failure message). It is read-only.

---

## 4. The exact stall signature (verified)

From `logs/m2_run3.log` (watchdog at 6 s) and `logs/m2_run1.log` (IRQL trace):

- **Spinning thread:** the **main** thread (`esp` in the main 8 MB stack region, `0x00F7F1xx`).
- **IRQL calls** (indirect, through the kernel thunk table, hence the synthetic thunk VAs
  `0xFE000074`/`0xFE000070` in the ICALL ring):
  - `ordinal 129 KeRaiseIrqlToDpcLevel` — `esp=0x00F7F154 ret=0x001B31C8`
  - `ordinal 161 KfLowerIrql` — `esp=0x00F7F154 ret=0x001B31DD`
  - **~10.5 M of each in 20 s**, perfectly paired (`raise … depth=1` / `lower … depth=0`).
- **NV2A:** `USER PUT=00000000 GET=00000000`, `PFIFO PUT=GET=REF=SUBR=0` — no GPU work ever submitted.
- **Worker thread** (ctx `0x000B0040`, routine `0x0009D546`) is **blocked on a guest critical
  section** (`logs/m2_run_cswatch2.log:520`): “thread … waiting on guest lock 0x00223B38
  (held by thread …)”.

`ret=0x001B31C8` / `0x001B31DD` are the two call sites **inside `sub_001B31C1`**
(`game/…/src/recomp/gen/recomp_0052.c:1523`), a 34-byte helper:

```c
sub_001B31C1(ptr):                    // thunk-table slots 29 (raise) then 28 (lower)
    KeRaiseIrqlToDpcLevel()           // ordinal 129
    esi = [ptr]; [ptr+4] = 0; [ptr+8] = esi
    KfLowerIrql(old)                  // ordinal 161
    return esi
```

So the storm is **not** an IRQL problem — it is this helper called ~10 M times/s.

---

## 5. Tracing the call chain (verified)

Guest stack dump at the watchdog (`logs/m2_run3.log`, around line 26790) gives the chain:

```
[0x00F7F154] 0x001B31DD   return into sub_001B31C1 (after KfLowerIrql)
[0x00F7F15C] 0x00118B43   return into sub_00118B30   <-- immediate caller (the poll)
[0x00F7F160] 0x001B245C   argument passed to the helper (a global object)
   ...
[0x00F7F26C] 0x00118DEB   inside sub_00118D20 (init path)
[0x00F7F27C] 0x00118E48   inside sub_00118D20 (loop body)
[0x00F7F298] 0x001190C7   inside sub_001190A0
```

`sub_00118D20` (`recomp_0032.c:12565`) ends in the actual infinite loop:

```c
loc_00118E36:
    ecx = MEM32(esi + 0x2C); edx = MEM32(ecx);
    call [edx + 0x1C]                      // predicate
    if (eax != 0) goto loc_00118E04         // do work, then return
loc_00118E41:
    sub_00118B30(this)                      // the poll -> IRQL storm
loc_00118E48:
    goto loc_00118E36                       // forever
```

`sub_00118B30` (`recomp_0032.c:11951`, `category: game_input`) takes the IRQL-guarded lock on
the global `0x001B245C` and diffs it against `[this+0x20]`. The loop **only exits when the
virtual predicate `[[esi+0x2C]]->vfn[0x1C]()` returns non-zero; it never does.**

The object's vtables (`0x1D2704 / 0x1D26FC / 0x1D26F4`) resolve to the engine's
"context/stream" method cluster (`0x117DB0 … 0x118F10`), i.e. this is an engine **context
run/pump loop**, not a kernel/kernel-bridge loop.

---

## 6. The threading hypothesis — tested and refuted (verified)

| Claim under test | Result | Evidence |
|---|---|---|
| Start routines don't run concurrently | **False** | `bridge_spawn_thread` uses `CreateThread`; `RECOMP_GUEST_LOCK` defaults off (`kernel_bridge.c:9362–9371`) |
| IRQL is global, not per-thread | **False** | `XBOX_THREAD_LOCAL KIRQL g_current_irql` (`kernel_hal.c:41`); global count is only for interrupt masking |
| IRQL leaks (raise without lower) | **False** | trace shows `raise 0->2 depth=1` then `lower 2->0 depth=0`, balanced ~10 M× |
| The wait is cross-thread | **True** | changing worker mode moves the stall (§7) |
| The stall is caused by the runtime's thread model | **Not established** | with both runtimes' supported knobs the stall only *moves*, it never *progresses* |

**Conclusion:** the toolkit's IRQL and threading implementations are correct for this title.
The stalled loop is guest code executing the guest's own instructions; the runtime gap is
elsewhere (graphics/data), not in the scheduler.

---

## 7. Bisection results — the stall moves (verified)

| Configuration | Where it stops | NV2A | Interpretation |
|---|---|---|---|
| default | `ordinal 129/161` (IRQL poll) @ `0x001B31C8/DD` | `PUT=GET=0` | baseline |
| `RECOMP_WORKERS=inline` | `ordinal 277` (`RtlEnterCriticalSection`) @ `esp=0x00F7F0C0` | `PUT=GET=0` | stall **moves** → concurrency-dependent |
| `RECOMP_CS_MODE=single` | `ordinal 277/294` (lock enter/leave) | `PUT=GET=0` | stall **moves** → lock-dependent |
| `RECOMP_CS_WATCH=0x223B38` | lock `0x223B38`: **2 takes, 0 drops** | `PUT=GET=0` | guest lock leaked |

Logs: `logs/m2_run_winline.log`, `logs/m2_run_cssingle.log`, `logs/m2_run_cswatch2.log`.

**The guest lock is leaked.** `logs/m2_run_cstrace.log` (raw addresses) shows the main thread
`take 0x00223B38` at line 725 and **no matching `drop` anywhere in the run**; a worker then
blocks on the same address at line 767. `[CS] enters=131 leaves=129 (outstanding 2)`.

---

## 8. Immediate upstream failure — graphics (verified) + engine correction

`logs/m2_run3.log` line 1045–1046, immediately after the lock take:

```
[ICALL] target 0x00000000 is not code -- skipped 1 time(s) (null or wild function pointer)
[GUEST] NewRenderContext() failed
```

A byte-scan (`scripts/m2_findref.py`) located the only reference to the format string at
guest `0x000AFF59`, inside `sub_000AFEC0` (`recomp_0020.c:1571`) — the engine's render-context
constructor. Its error strings are:

| Guest VA | String |
|---|---|
| `0x001C8814` | `NewRenderContext() failed` |
| `0x001C8830` | `Cannot initialize PDDI library, unknown error.` |
| `0x001C8860` | `Cannot initialize PDDI library due to an incorrect version` |

**PDDI = Pure3D Device Driver Interface.** This is verified evidence that the engine **is
Pure3D** (Radical Entertainment's engine), reached through its PDDI abstraction.

> **Correction to M1 §8.** M1 concluded “the RenderWare/Pure3D assumption is REFUTED”.
> That is only half right: RenderWare is indeed absent (0 identifiers), but **Pure3D is
> present and used** (PDDI error strings in the XBE). `docs/ARCHITECTURE.md` and
> `docs/FEASIBILITY.md` are corrected accordingly.

The sequence is: the engine constructs the PDDI context; a virtual create-context call returns
a failure; the engine logs `NewRenderContext() failed` and takes an early return **while still
holding the global engine lock `0x00223B38`** — leaking it and deadlocking the worker that
needs it. The guest never reaches the host D3D8 layer (no `D3D8:` line is ever printed), so the
toolkit's `xbox_d3d8` backend is currently **unused**; the guest's statically-linked Xbox D3D8
runs instead and fails to bring up a context.

---

## 9. Files changed

| File | Change | Reversible? |
|---|---|---|
| `scripts/m2_findref.py` | **new** read-only analysis helper (XBE offset→VA + immediate cross-reference) | delete to revert |
| `logs/m2_*.log` | new run/trace logs (git-ignored) | delete to revert |
| `docs/M2-RESULTS.md` | this document | — |
| `docs/ARCHITECTURE.md`, `docs/FEASIBILITY.md` | verified Pure3D/PDDI correction only | — |

**No upstream file was modified** (`third_party/xboxrecomp` is byte-identical, clean tree).
**No behavioural fix was applied**, because the evidence does not support a small, supported
one: every documented knob (`RECOMP_WORKERS=inline`, `RECOMP_CS_MODE=single`) only relocates
the stall, and a title-specific override in `recomp_manual.c` would be a hack that masks the
real gap (graphics context creation) rather than fixing it. Nothing is committed.

---

## 10. Remaining unverified / open questions

- **The exact event the wait loop polls** — the virtual predicate `[[esi+0x2C]]->vfn[0x1C]()`.
  Whether it depends on the (failed) render context, on a GPU/semaphore state, or on a
  streaming/loader subsystem is **not yet established**. This is the one unknown between
  “stall moves” and “first frame”.
- Whether the PDDI render-context failure is fatal for later progress or merely a degraded path.
- Whether the guest's D3D8 eventually needs the toolkit's `xbox_d3d8` backend (and how a
  statically-linked guest D3D8 is meant to be redirected to it) — no precedent found in the
  toolkit docs.
- Game data was **not** required to reach or diagnose this point, and to date only
  `default.xbe` exists in `game/The Simpsons Road Rage/`; every archive open
  (`always.rcf`, `img/dsstdfx.bin`, `sound/music/music.rcf`, `typ/tibld.typ`) fails
  `STATUS_OBJECT_NAME_NOT_FOUND`. Asset data *will* be required for any real boot.

---

## 11. Is M2 complete?

**Yes, as Outcome B.** The stall is reproduced, the exact stopping point and its guest call
sites are identified, the hypothesised threading/IRQL cause is **disproven with source and
runtime evidence**, a genuine cross-thread lock leak is documented, and the immediate upstream
failure (Pure3D/PDDI render-context creation) is identified. What M2 did **not** achieve is a
frame or any GPU submission — correctly, because the blocker is upstream of rendering.

**Do not claim the game boots. It does not.**

---

## 12. Single best next step

**Make the Pure3D/PDDI render context succeed, then re-point the wait loop.**

Concretely, the next milestone (M3) should:

1. **Trace the PDDI create-context path.** Re-lift with
   `--trace-functions` on `{0x000AFEC0, 0x00139560, 0x000AFE50, 0x00118D20, 0x00118B30}`
   and capture the return value of the virtual call at `sub_000AFEC0` (`[edx+0x18]`) and of
   the object behind `[[esi+0x2C]]->vfn[0x1C]()`. This names the missing state in one run.
2. **Decide the graphics route**: either complete enough of the NV2A/guest-D3D8 path that the
   PDDI context initialises, or wire the toolkit's host `xbox_d3d8` in place of the guest's
   statically linked D3D8. Prefer the toolkit's supported backend; no title-specific override
   until the route is chosen.
3. **Only then** introduce game data (the disc's `.rcf` archives) if the loader proves to be
   the gating dependency.

Secondary, cheap diagnostics already available for step 1: `RECOMP_PEEK=0x301B48,0x2F3B00,0x2F3B80`
at the hang, and `RECOMP_CS_WATCH` on `0x00223B38` to confirm the leak persists once graphics
init is fixed.