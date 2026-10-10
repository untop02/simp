# M4 Results — Function-Boundary / Stack-Cleanup Failures on the PDDI Render-Context Path

**Game:** *The Simpsons: Road Rage* (2001), original Xbox (PAL retail, Title ID `0x45410013`).
**Toolkit:** `sp00nznet/xboxrecomp` @ `193e2995ffaec871bb3be43a43bd66aa5fccfeb1` (tag `v0.13.1`),
**unmodified, clean tree** (upstream fix prototyped in an isolated copy — §5).
**Executable:** `game/The Simpsons Road Rage/build/srr_recomp.exe` (console build, watchdog-driven).

**Verdict: M4 objective achieved — the render context is now constructed.** `NewRenderContext() failed`
is gone, the three suspect addresses are lifted correctly, and with the disc's `always.rcf` present the
title runs on into **RadSound audio initialisation**. No frame is presented yet (`NV2A PUT=GET=0`): a new,
different crash in the RadSound path is the blocker, and the leaked critical section is not fully resolved.

> **Do not claim the game boots. It does not render a frame.**

---

## 1. Executive summary

The milestone began from M3's framing: three addresses on the PDDI/PDDI-init path were "function-boundary
and stack-cleanup" failures. **That framing was partly wrong, and the difference matters.**

Three defects were confirmed, in two distinct classes:

| # | Address | Class | Root cause |
|---|---|---|---|
| 1 | `0x0015B100` | **pipeline scope** | The lift ran `tools.disasm --text-only`, so the SDK code section `D3D` was never swept. `0x0015B100` is called only from *inside* `D3D`, so it was invisible → stub with a guessed `g_esp += 4`. |
| 2 | `0x0015A760` / `0x0015A7DF` | **pipeline scope** | Same cause: with `D3D` unswept, `sub_0015A760` was measured short at its first `ret` (`0x15A7DF`), and `0x15A7DF` became a bogus alias to `0x15B880`. With `D3D` swept, `sub_0015A760` measures `0x15A760–0x15A7F3` and `0x15A7DF` is correctly an *intra-function* branch target. |
| 3 | `0x00139AD0` | **genuine detector gap** | The tail-jump pass (`_pass_tail_jump_targets`) runs before `_pass_data_ptr_targets` and only considers materialised bodies (`self.functions`), not alias entries. The `jmp 0x139AD0` at `0x13945E` lives inside the vtable entry `0x139440`, which is an *alias*, so it was dropped and the constructor stubbed. |

**Fixes:**

1. **Configuration (dominant):** drop `--text-only`. This is supported behaviour — the loader already
   classifies `D3D`/`DSOUND`/`BINK`/`XGRPH`/`XPP`/`DOLBY` as code sections; `--text-only` silently
   excludes them. This alone fixes #1 and #2, and lifted the vendor libraries properly
   (D3D 68→333 functions, DSOUND 31→378, BINK 9→150, XPP 9→220).
2. **Seed set:** reduced from 6 to 5 — `0x0015A7DF` removed (it is no longer a function; keeping it
   truncated `sub_0015A760`). `0x00139AD0` is still seeded in the shipped build.
3. **Upstream (isolated prototype):** an alias-aware tail-jump pass, with synthetic regression tests,
   that resolves `0x00139AD0` **without any seed** and passes the toolkit's full disasm + recomp suites.

**Measured result:** the recompiler now emits **13,386 functions, 0 failed, 289 unresolved stubs**
(down from 527), and the runtime reaches RadSound initialisation — a state M2/M3 never approached.

---

## 2. Objective and outcome tracking

| # | Tracked outcome | Result |
|---|---|---|
| 1 | **Correct function bodies generated** at all three addresses | **YES** — verified in generated C (§6) |
| 2 | **Stack balanced** across the suspect calls | **YES** — `ret 4`/`ret 0x18` cleanups now come from real bodies; `pop esi` present on every path |
| 3 | **PDDI render context constructed** | **YES** — `[GUEST] NewRenderContext() failed` no longer printed; execution continues far past it |
| 4 | **Critical-section deadlock eliminated** | **NO** — `[CS] … outstanding 2`; lock `0x00223B38` still held on an error path |
| 5 | **NV2A commands submitted** | **NO** — `PUT=GET=0` |
| 6 | **First frame presented** | **NO** |

---

## 3. Root cause #1 & #2 — the pipeline never swept the SDK code sections

Evidence, all verified:

- `third_party/xboxrecomp/tools/disasm/output/.disasm_cache.json` records the last real run:
  `"text_only": true`.
- `tools/disasm/disasm.py:313` — `if self.text_only: sections = [.text]`. `--text-only` restricts the
  sweep to `.text` only; `_get_target_sections()` never returns the other code sections.
- The `.disasm_cache` option is the only source of truth here: `summary.json`'s `sections_analyzed`
  field is **misleading** — `tools/disasm/output.py:88` lists every section from
  `get_code_sections()` regardless of what was swept. The function counts expose it: `D3D` had **68**
  functions in a **140 KB** section, `DSOUND` **31** in **112 KB** — these are only the functions
  *directly called from `.text`* (reached by `_pass_call_targets`' `decode_at`), not a sweep.

Reproduced directly with the pinned toolkit (read-only probe, `scripts/m4_detect_compare.py`):

```
[text/noseeds] functions=12977   # what the shipped pipeline did
  0x0015A760: FUNC 0x0015A760-0x0015A7DF (call_target)   # truncated at first ret
  0x0015A7DF: alias->0x0015B880                           # bogus alias
  0x0015B100: NOT DETECTED                                # -> g_esp += 4 stub

[all/noseeds]  functions=13334   # sweep every code section
  0x0015A760: FUNC 0x0015A760-0x0015A7F3 (call_target)   # correct extent
  0x0015A7DF: inside sub_0015A760 0x0015A760-0x0015A7F3   # intra-function branch
  0x0015B100: FUNC 0x0015B100-0x0015B642 (call_target)   # real body
```

Why the stub is *also* wrong: `translator._stub_ret_bytes` (`tools/recomp/translator.py:1278`) walks
straight-line from the target but **stops at a `call` or `jmp`**. `0x0015B100`'s body begins
`sub esp,0x168; push esi; …; call esi → …`, so the walk stops at the indirect `call esi` and returns 0,
and the stub is emitted as `g_esp += 4` (cdecl) although the real function ends `ret 4` (stdcall, 1 arg).
No guess can fix this — only detecting the function does.

**This is not a function-boundary bug.** It is scope: the pipeline analysed one section out of thirteen.
Both suspect addresses in the `D3D` section are fixed by sweeping all code sections, with no seeds.

Rejected alternatives (per the M3 negative result, re-confirmed): blanket seeding the
`D3D`/tail-call stubs. Seeding `0x15A7DF` *truncates* `sub_0015A760` at `0x15A7DF` — a seed sets a
start, and `_build_functions` treats it as the next function's boundary.

---

## 4. Root cause #3 — tail jumps inside an alias-only body are dropped

The remaining address, `0x00139AD0`, is independent of section scope: it is in `.text` and was still
swallowed as an "interior of `sub_00139AC0`" after the full sweep.

Traced with a read-only engine probe against the pinned detector:

```
0x13945E: jmp 0x139AD0         # inside sub_00139440 (0x139440-0x139470), a ctx vtable entry
0x00139440: alias=0x139510  func=tail_jump_alias end=0x139470
0x00139AC0: alias=0x139C90  func=tail_jump_alias end=0x139B60
0x00139AD0: alias=None      func=None      # <-- never registered
```

Timing probe of `_pass_tail_jump_targets` shows why:

```
[wrap] containing 13945E=['0x1393d0', '0x1393f4']   # the jmp is NOT inside any materialised body
       containing 139AD0=['0x139890', '0x1399fc']
[wrap after] alias139AD0=None cand=False
```

The `jmp` at `0x13945E` lies in region `0x139440`, which exists only as an **alias entry** (a vtable
data pointer created by `_pass_data_ptr_targets`). That pass runs **after** the tail-jump loop, and
`_build_alias_entries` materialises alias bodies only at the very end. So throughout the tail-jump pass
`0x139440` is not in `self.functions`, the `jmp` is classed as "not inside any known function" and
skipped (`insn.address >= body_end → continue`). `0x139AD0` is never registered and the recompiler
stubs it (`g_esp += 4`), returning the freshly allocated `0x45C` context **with a null vtable** — the M3
root cause, now explained generically.

**Fix (isolated prototype):** give `_pass_tail_jump_targets` an `include_aliases` mode that treats
`self._alias_entries` ranges as code regions, and re-run it (to a fixpoint) after
`_pass_data_ptr_targets`. See §5.

---

## 5. The fix — configuration + a minimal upstream change

### 5.1 Configuration (shipped build)

- Pipeline: `tools.disasm` **without** `--text-only` (all code sections), then `func_id`,
  `abi_analysis`, `recomp` as before.
- Seeds: `src/recomp/seed_function_starts.json` reduced to 5 (the M3 file is preserved as
  `seed_function_starts.m3.json`). Dropped `0x0015A7DF`; kept the four other PDDI ctors and
  `0x00139AD0`.

Detector result with all sections + these 5 seeds:

```
0x00139AD0: FUNC 0x139AD0-0x139B51 (seed_vtable_thunk)
0x0015A760: FUNC 0x15A760-0x15A7F3 (call_target)
0x0015A7DF: inside sub_0015A760           # no longer a function
0x0015B100: FUNC 0x15B100-0x15B642 (call_target)
```

### 5.2 Upstream prototype (isolated copy — pinned tree untouched)

The pinned toolkit is **not modified**. The change lives in `third_party/_m4_xboxrecomp/` (a copy),
applied reproducibly by `scripts/m4_patch_upstream.py`. Exact diff: `logs/m4_upstream_fix.diff`.

`tools/disasm/functions.py`:
- `_pass_tail_jump_targets(self, sections, include_aliases=False)`.
- When `include_aliases`, merge `self._alias_entries` into the region list, **clamping each alias end
  to the next region start** so an over-long gap alias cannot swallow a real function's tail jump.
- In `detect_all`, after `_pass_data_ptr_targets`, iterate the tail-jump pass with
  `include_aliases=True` to a fixpoint.

Result on the game (all sections, **no seeds at all**):

```
tail-jump pass (aliases): +234 standalone
[all/noseeds] functions=13531
  0x00139AD0: FUNC 0x139AD0-0x139B51 (tail_jump_target)   # fixed generically, no seed
  0x0015A760: FUNC 0x15A760-0x15A7F3 (call_target)
  0x0015A7DF: inside sub_0015A760
  0x0015B100: FUNC 0x15B100-0x15B642 (call_target)
```

So with the upstream fix the shipped build would need **no seeds at all**; M4 retains the 5-seed path
for the working build and documents the fix as an upstream candidate.

---

## 6. Regression tests

Added: `third_party/_m4_xboxrecomp/tools/disasm/test_tail_jump_alias.py` (source:
`scripts/m4_test_tail_jump_alias.py`). Synthetic x86-shaped fakes, in the style of the toolkit's own
`tools/disasm/test_alias_bounds.py`. It reproduces, minimally:

- A tail-jump target inside an alias-only body → **missed** without `include_aliases` (the bug), and
  registered as an alias **with** it.
- The enclosing alias body is not split.
- A jump inside a real body still works with `include_aliases=True`.
- An intra-alias branch is not misclassified as a tail jump.

Test results (in the isolated copy):

```
py -3 -m pytest tools/disasm  ->  57 passed        (53 upstream + 4 new)
py -3 -m pytest tools/recomp ->  453 passed, 38 skipped, 57 subtests passed
```

The pinned copy is unchanged, so its suite is unaffected.

---

## 7. Generated code at the three addresses (shipped build)

- `sub_00139AD0` (`recomp_0035.c:25199`): real body; `MEM32(esi) = 0x1DAAD0` — installs the value
  vtable. (Was a stub.)
- `sub_0015A760` (`recomp_0049.c:835`): `if (CMP_GE(...)) goto loc_0015A7DF;` — an **intra-function**
  branch; both exits `POP32(esp, esi); esp += 28; return; /* ret 24 */`. (Was split into a 127-byte
  function plus a bogus `0x15B880` alias.)
- `sub_0015B100` (`recomp_0049.c:2169`): real body, `esp -= 0x168` prologue, and on each exit
  `POP32(esp, esi); esp += 0x168; … esp += 8; return; /* ret 4 */`. (Was `g_esp += 4; /* not detected */`.)

## 8. Runtime verification

Build recipe unchanged from M0 (Zig, no MSVC); the CMake/vendor build is invoked through the absolute
path to `cmake.exe` (see §11). Three bounded runs (`RECOMP_WATCHDOG_SECS`; a watchdog exit code of 3 is
the harness, a segfault is a real crash):

| Run | Config | Outcome |
|---|---|---|
| `logs/m4_repro_baseline.log` | pinned, `--text-only`, M3 seeds | **reproduced**: `[GUEST] NewRenderContext() failed` (L1046), `[CS] outstanding 2`, watchdog `PUT=GET=0` |
| `logs/m4_fullsections_run1.log` | all sections, 5 seeds | **NewRenderContext failure GONE**; thread spawn, heap, TDATA/UDATA probes; segfault at disc-asset read |
| `logs/m4_withassets_run2.log` | + `always.rcf` and `img/dsstdfx.bin` from the disc | **reaches RadSound init** — `[GUEST] radSound: Total Sound Memory Available: [4096K]`, `Total Aux Sends Available: [2]`; then a new segfault |

The baseline's IRQL-spin stall and the `NewRenderContext() failed` artefact are both gone. Disk assets
are genuinely required to go further (the CD device maps to the game directory; see §10).

Remaining: `[CS] enters=411 leaves=409 (outstanding 2)` — one lock is still leaked, and the new crash
(`fault=0xCF3C41FF`, innermost guest return `0x0011E858`, inside the RadSound path) is unresolved.

---

## 9. Disk-space considerations

| Artifact | Size |
|---|---|
| Generated C (`src/recomp/gen`, 54 chunks) | 47 MB |
| CMake build tree (`build/`) | 220 MB |
| `logs/` | 126 MB |
| Isolated toolkit copy (`third_party/_m4_xboxrecomp`) | 17 MB |
| `D:` free | **36 GB (97% used)** |

The full-section sweep costs little extra source (13,341 vs 12,985 functions, ~47 MB either way); the
isolated copy is small because outputs/build trees are excluded. Run logs should be pruned; `logs/`
is the largest disposable item.

---

## 10. Game-specific prerequisites (verified against the disc)

The ISO is `Simpsons, The - Road Rage (Europe) (En,Fr,De).iso`. `\Device\CdRom0\` maps to the game
directory (`src/kernel/kernel_path.c:49`). The boot path requests, and **needs**, real disc files:

| File | Size | Status |
|---|---|---|
| `default.xbe` | 2,187,264 B | present (M1) |
| `always.rcf` | 165,888 B | **required**; extracted for the §8 run — removed the first crash |
| `img/dsstdfx.bin` | 18,068 B | required by RadSound; extracted for the §8 run |
| `loading.rcf`, `nis.rcf`, `stechng.rcf`, `art/**/*.rcf` | up to 123 MB | **not yet present**; likely needed to get past the current crash |

These are copyrighted assets from the user's own legally obtained copy; they are git-ignored
(`/game/`, `/assets/`) and must not be committed or redistributed.

---

## 11. Exact commands (this milestone)

From the repo root. `$XBE`, `$S1`, `$S2` as in §5.1.

```sh
# Detection — note: NO --text-only, and the 5-seed file
cd third_party/xboxrecomp
PYTHONPATH=. py -3 -m tools.disasm "$XBE" \
  --seed-functions "$S1" --seed-functions "$S2" --force
PYTHONPATH=. py -3 -m tools.func_id "$XBE"
PYTHONPATH=. py -3 -m tools.abi_analysis "$XBE"
PYTHONPATH=. py -3 -m tools.recomp "$XBE" --game-name "The Simpsons Road Rage" \
  --all --split 250 --gen-dir "D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/gen"

# Build (cmake is not on PATH in Git Bash)
cd "D:/simpsons recomp"
"/c/Users/kabyl/AppData/Roaming/Python/Python314/Scripts/cmake.exe" \
  --build "game/The Simpsons Road Rage/build"

# Run (watchdog code 3 = bounded harness; 139 = real crash)
RECOMP_WATCHDOG_SECS=12 RECOMP_KERNEL_LOG_BUDGET=2000 \
  timeout 60 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m4_withassets_run2.log 2>&1

# Isolated upstream fix + its tests
py -3 scripts/m4_patch_upstream.py
cp scripts/m4_test_tail_jump_alias.py \
  third_party/_m4_xboxrecomp/tools/disasm/test_tail_jump_alias.py
cd third_party/_m4_xboxrecomp && PYTHONPATH=. py -3 -m pytest tools/disasm tools/recomp -q

# Read-only investigation helpers (new)
py -3 scripts/m4_query.py  "$XBE" disasm 0x0015B100 120
py -3 scripts/m4_probe.py  "$XBE" 0x0015B100 0x0015A7C4
py -3 scripts/m4_detect_compare.py "$XBE" all noseeds
```

---

## 12. Files changed

| File | Change | Reversible |
|---|---|---|
| `game/…/src/recomp/seed_function_starts.json` | **5 seeds** (dropped `0x0015A7DF`) | restore from `seed_function_starts.m3.json` |
| `game/…/src/recomp/seed_function_starts.m3.json` | **new** — preserved M3 6-seed file | delete |
| `game/…/src/recomp/gen/*` | regenerated with all code sections (git-ignored) | rerun pipeline |
| `game/…/always.rcf`, `game/…/img/dsstdfx.bin` | **new** — disc assets for the §8 run (git-ignored) | delete |
| `scripts/m4_query.py`, `m4_probe.py`, `m4_detect_compare.py`, `m4_patch_upstream.py`, `m4_test_tail_jump_alias.py` | **new** — read-only helpers / patch / test | delete |
| `third_party/_m4_xboxrecomp/` | **new** — isolated toolkit copy with the fix + test | delete |
| `logs/m4_*.log`, `logs/m4_upstream_fix.diff` | run logs + exact upstream diff (git-ignored) | delete |
| `docs/M1-RESULTS.md`, `docs/M3-RESULTS.md` | added "M4 correction" notes about `--text-only` | revert the note |
| `docs/M4-RESULTS.md` | this document | — |

**`third_party/xboxrecomp` is byte-identical at `193e2995…` and clean. Nothing is committed.**
Watchdogs and diagnostics are preserved; no fault was suppressed and no render context was faked.

---

## 13. Technical risks and unresolved questions

- **`--text-only` may have been intentional** (build size / detector cost). The full sweep is required
  for correctness here; whether it perturbs `.text` boundaries on other titles is untested (this title:
  `.text` fell 12,866 → 12,222 while total rose to 13,341 — a re-attribution, not a loss).
- **The upstream fix changes detection** (+~200 functions on this title, +139 in the verified run). It
  passes both suites, but the alias-end clamping is a judgement call and should be reviewed upstream.
- **Lock leak `0x00223B38` persists** (`outstanding 2`), so a race/deadlock risk remains even though the
  run now proceeds past it.
- **The RadSound crash is undiagnosed.** Its fault (`0xCF3C41FF`) and the `[READ]` immediately before it
  suggest either a further missing asset or a defect in the newly-lifted `DSOUND` code — not yet
  distinguished.
- **RadSound/GUEST log lines** are the game's own debug prints; they confirm the audio subsystem is
  reached but not that it functions.
- Whether the host `xbox_d3d8` backend must replace the guest's statically linked D3D8 is still open —
  no device is created and no pushbuffer is touched.

---

## 14. Single best next step

**Provide the disc assets, then re-run — the failure is now a data wall, not a code wall.**

1. Extract the disc tree (at least `always.rcf`, `loading.rcf`, and `art/**/*.rcf`) into
   `game/The Simpsons Road Rage/`, preserving relative paths (`py -3 -m tools.xiso unpack <iso> -o
   "game/The Simpsons Road Rage"`, or `get` per file — the tool flattens paths, so `img/` files must be
   moved into place). These are the user's own legally obtained assets; keep them out of git.
2. Re-run under the watchdog and check whether the RadSound crash moves — that distinguishes a missing
   asset from a `DSOUND` mis-lift.
3. In parallel, if the crash persists with assets present, symbolise guest `0x0011E858` (innermost
   caller) and its callees from `functions.json`, and inspect the lifted `DSOUND` code there against the
   XBE bytes.
4. Only after the RadSound path is clean should the pending items be revisited: the `0x00223B38` lock
   leak, then the NV2A pushbuffer (`PUT`/`GET`) and the first presented frame.

The upstream alias fix (§5.2) should be offered upstream — with its regression tests — so the shipped
build can drop the seed set entirely.

---

## 15. M5 correction (verified)

The "data wall" framing in §14 is **wrong**, and one detail about extraction is wrong:

- **It is not a data wall.** With the complete disc tree extracted (`tools.xiso unpack`, all 48 files,
  sizes verified), the crash is byte-for-byte identical — same fault `0xCF3C41FF`, same guest return
  `0x0011E858`. The blocker is a lift/runtime-integration defect (a wild guest-*stack* value
  `0xF7F180` used as a registry index in `sub_00119140`), not a missing asset.
- **`tools.xiso unpack` preserves directory hierarchy.** Only `tools.xiso get` flattens paths
  (`tools/xiso/__main__.py:35-36` vs `:46`). No manual `mv` into `img/` is required when unpacking.

See `docs/M5-RESULTS.md` for the evidence.
