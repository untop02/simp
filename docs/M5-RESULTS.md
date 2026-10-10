# M5 Results — Full Asset Extraction, RadSound Crash Diagnosis, First-Frame Progress

**Game:** *The Simpsons: Road Rage* (2001), original Xbox (PAL retail, Title ID `0x45410013`).
**Toolkit:** `sp00nznet/xboxrecomp` @ `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` (tag `v0.13.1`).
**Executable:** `game/The Simpsons Road Rage/build/srr_recomp.exe` (console build, watchdog-driven).

**Verdict: the asset baseline is complete and verified, and the current crash is fully localised — but it is
not a data wall.** The M4 hypothesis ("provide the disc assets, then re-run — the failure is now a data wall")
is **disproven**: the crash is byte-for-byte the same with the complete disc tree present. The fault is a wild
guest-stack value used as a **registry index** in an indirectly-dispatched message handler. No frame is
presented; `NV2A PUT=GET=0`.

> **Do not claim the game boots. It does not render a frame, and it does not currently get past RadSound
> initialisation.**

---

## 1. Executive summary

| Outcome tracked | Result |
|---|---|
| Complete disc asset tree extracted | **YES** — 48/48 files, all sizes match the ISO |
| Extraction verified | **YES** — zero missing, zero size mismatches |
| All-sections pipeline preserved (no `--text-only`) | **YES** — unchanged from M4 |
| RadSound crash reproduced | **YES** — deterministic |
| Crash root cause localised | **YES** — wild registry index `0xF7F180` in `sub_00119140` |
| Crash fixed | **NO** |
| PDDI render context constructed | **YES** (still, from M4) |
| NV2A commands submitted | **NO** — `PUT=GET=0` |
| First frame presented | **NO** |

Key correction to M4: `tools.xiso unpack` **does** preserve directory hierarchy. The M4 note that "the tool
flattens paths" applies only to `tools.xiso get`, not `unpack` (verified in `tools/xiso/__main__.py:46`:
`dest = os.path.join(args.output, *(d.split("/") ...), e.name)`). No per-file extraction or manual `mv` was
needed.

The crash is **not** caused by a missing asset, nor by an unimplemented kernel API (every kernel call in the
run returns success). It is a **lift / runtime-integration defect**: an indirectly-dispatched handler receives a
guest-*stack* address (`0xF7F180`) where a small registry index is expected. That value flows into the registry
dispatch `sub_00119140`, whose lookup reads a **foreign committed host region** and dereferences garbage
(`0xCF3B41FF`).

---

## 2. Asset extraction — method and verification (Phase 1)

The ISO (`Simpsons, The - Road Rage (Europe) (En,Fr,De).iso`, 374,472,704 bytes) was inspected read-only. Its
payload is **48 files / 373,833,571 bytes** (`logs/m5_iso_listing.txt`). `default.xbe` in the image is
byte-identical to the analysed copy:

```
20e598f86b01dcdb8c35f87a6717e433  game/…/default.xbe          (existing, from M1)
20e598f86b01dcdb8c35f87a6717e433  (extracted from the ISO)
```

Extraction (one command, hierarchy preserved):

```sh
cd third_party/xboxrecomp
PYTHONPATH=. py -3 -m tools.xiso unpack \
  "D:/simpsons recomp/Simpsons, The - Road Rage (Europe) (En,Fr,De).iso" \
  -o "D:/simpsons recomp/game/The Simpsons Road Rage"
# → extracted 48 files to D:/simpsons recomp/game/The Simpsons Road Rage
```

Verification (`scripts/m5_verify_extract.py` compares the ISO listing against the tree, path by path):

```
ISO entries      : 48
ISO total bytes  : 373833571
Matched (size ok): 48
Missing          : 0
Size mismatch    : 0
Extras (not in ISO, excl. build/src/TDATA/UDATA): 3
  EXTRA  .gitignore
  EXTRA  CMakeLists.txt
  EXTRA  default_analysis.json
```

The three "extras" are project files, not disc content. No ISO filesystem metadata was extracted as game
content. The original ISO is untouched and `default.xbe` was not modified (hash above). The full tree
(`art/**`, `movies/{ntsc,pal}`, `sound/**`, `typ/`, `img/`, plus top-level `.rcf` archives and `saveimg.xbx`)
is git-ignored via `/game/`.

Extracted size: `game/The Simpsons Road Rage` is now 623 MB total (356 MB of disc content + 220 MB build tree
+ 47 MB generated C).

---

## 3. Runtime asset paths (verified) and path mismatches

`\Device\CdRom0\` maps directly to the game directory (`src/kernel/kernel_path.c:49`). The run log confirms
guest paths resolve into the extracted tree and read the real bytes:

```
[PATH] \Device\CdRom0\              [PATH] \Device\CdRom0\always.rcf      → [READ] 52 41 44 43 ("RADC")
[PATH] \Device\CdRom0\img\dsstdfx.bin                                     → [READ] want=18068 got=18068
```

No unresolved path mismatches were observed — every file the title requested after extraction was found. The
complete tree means the previous "missing asset" crash (M4's first segfault at a disc-asset read) is gone.

---

## 4. Baseline crash and root-cause evidence (Phase 2)

### 4.1 Reproduce

```sh
RECOMP_WATCHDOG_SECS=12 RECOMP_KERNEL_LOG_BUDGET=4000 \
  timeout 90 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m5_run1_fullassets.log 2>&1
# EXIT=139  (real segfault)  — identical with and without the full asset tree
```

Symptom (unchanged from M4):

```
[GUEST] radSound: Total Sound Memory Available: [4096K]
[GUEST] radSound: Total Aux Sends Available: [2]
[CRASH] Access violation at RIP=…, fault addr=0xCF3C41FF (read)
  Xbox regs: eax=0x0000015C ecx=0xCF3B41FF edx=0x00F7F180 esp=0x00F7F10C
  Xbox regs: ebx=0x00F7F180 esi=0x00F7F180 edi=0x00F7F180
```

### 4.2 Symbolising the fault (new tooling)

dbghelp would not load Zig's PDB via `SymFromAddr` in a fresh process, but *does* load it via `SymFromName`
(or once warmed up) at module base `0x140000000`. `scripts/m5_sym_native.py` resolves a native RVA to a
symbol **and a source line**:

```
0x27D89D7 -> sub_00119140+0x187 [ …/src/recomp/gen/recomp_0030.c:5323]
```

`recomp_0030.c:5323` is `edx = MEM32(ecx);` — the faulting instruction, inside `sub_00119140`
(`0x00119140`, the registry-dispatch function identified in M3/M4's neighbourhood).

`sub_00119140` is:

```c
eax = MEM32(esp + 4);              // arg0  = index
ecx = MEM32(eax * 4 + 0x2F3B08);   // ecx   = registry[index]
if (ecx == 0) { …fallback… }       // (a null slot is handled — no crash)
eax = MEM32(esp + 8);              // arg1
edx = MEM32(ecx);                  // ← FAULT: dereference of a wild pointer
```

The XBE bytes confirm the scaling is real (`8B 0C 85 08 3B 2F 00` = `mov ecx,[eax*4+0x2F3B08]`), so `arg0`
*is* a small element index, not a pointer.

### 4.3 Evaluating the lookup at fault time

A gated crash-time dump was added to the VEH handler (`RECOMP_M5_REGDUMP=1`). It re-evaluates the lookup with
the argument left on the guest stack and reports the mapping state:

```
[M5] esp+4 (arg0/index)=0x00F7F180 esp+8 (arg1/value)=0x0000015C
[M5] lookup idx=0x00F7F180 addr=0x040F0108 host=0x4100108
[M5]   state=0x1000 protect=0x4 region=0x4100000
[M5]   value=0xCF3B41FF (ecx expects 0xCF3B41FF)
```

So:

* the **index is `0xF7F180`** — a guest **stack** address, not an index;
* `0xF7F180 * 4 + 0x2F3B08 = 0x040F0108` maps to host `0x4100108`, which is **committed** (`p=0x4`, RW)
  but is *outside* the 64 MB Xbox RAM view (host `0x10000`–`0x4010000`) — a foreign runtime region;
* the word read there is the garbage pointer `0xCF3B41FF`, which is then dereferenced → access violation.

The registry itself is **entirely empty** (30 slots, all `0x00000000`), and **no lifted function writes it**
(`grep -rn 2F3B08 gen/` returns reads only; the 289 auto-stubs only adjust `esp`). A *valid* index would
therefore take the null-slot fallback and not crash — the defect is the index, not the empty table.

### 4.4 Where the bad index comes from (watchpoint — decisive)

The runtime's supported watchpoint (`RECOMP_WATCH`, `src/kernel/xbox_memory_layout.c:1473`) was armed on the
scratch global `0x2F3B80`, which M4's crash dump showed also held `0xF7F180`:

```
$ RECOMP_WATCH=0x2F3B80 RECOMP_WATCHDOG_SECS=10 RECOMP_KERNEL_LOG_BUDGET=0 \
    timeout 120 "…/srr_recomp.exe" > logs/m5_watch.log 2>&1
[WATCH] [002F3B80] 00000000 -> 00F7F180  (esp=00F7F110)
         [esp+20  ] 001174DE            ← sub_00117460
         [esp+288 ] 001318FC
         [esp+344 ] 00121426
```

`[esp+20] = 0x001174DE` is the return address of `sub_0011E840` (verified: `recomp_0031.c:4180`), and
writer `esp = 0xF7F110` is exactly 4 above the crash `esp` — i.e. the write is
`sub_0011E840`'s `MEM32(0x2F3B80) = esi;` (`recomp_0031.c:4179`), one instruction before it calls
`sub_00119140`. So `esi` (the bad index) is `sub_0011E840`'s argument, not something it computed.

Tracing the argument:

| Step | Guest addr | Finding |
|---|---|---|
| `sub_00119140` arg0 | `0x119140` | index `= 0xF7F180` |
| caller `sub_0011E840` | `0x11E840` | `esi = MEM32(esp+0x1C)` → **arg4**; passes it as arg0 |
| only caller | `0x1174D9` | inside `sub_00117460`; arg4 is pushed from `edi` (`recomp_0029.c:12328`) |
| `edi` loaded | `0x117499` | `edi = MEM32(esp+0x148)` → `sub_00117460`'s **arg3** |
| `sub_00117460` reached | dispatch table + thunk | no direct callers; only `{0x117460, …}` in `recomp_dispatch.c`, and the 5-byte thunk `sub_00117570` (`0x117570`: `jmp 0x117460`) |

So `sub_00117460` — an **indirectly-dispatched message handler** — is invoked with `arg3 = 0xF7F180`, a
guest-stack address, where a small index is expected. The value is pushed by the (indirect) dispatcher.

All of this is generated from verified-correct liftings: the XBE disassembly of `sub_00117460`, `sub_0011E840`
and `sub_00119140` was compared line-by-line against the generated C and matches, including the argument
offsets.

---

## 5. Every change made (and why)

| File | Change | Justification |
|---|---|---|
| `game/…/` (whole tree) | **extracted 48 disc files** via `tools.xiso unpack` | Phase 1 — complete, verified asset baseline |
| `game/…/src/main.c` | crash handler: name faulting **module** + base + RVA; print **native raw stack** and the **registry/lookup** dump under `RECOMP_M5_REGDUMP` | needed to symbolise the fault and evaluate the lookup; gated so normal runs stay clean; diagnostics preserved |
| `game/…/CMakeLists.txt` | (attempted `-Wl,-Map`; **reverted** — Zig's linker rejects `-Map`) | left exactly as it was |
| `scripts/m5_verify_extract.py` | new — verify ISO listing vs extracted tree | Phase 1 evidence |
| `scripts/m5_sym.py` | new — resolve guest VAs to functions | analysis |
| `scripts/m5_sym_native.py` | new — resolve EXE RVA → symbol+source line via dbghelp/PDB | analysis (dbghelp needs a `SymFromName` warm-up) |
| `scripts/m5_disasm_exe.py` | new — disassemble the linked EXE at an RVA (no PDB) | analysis |
| `docs/M5-RESULTS.md` | this document | — |
| `docs/M4-RESULTS.md` | correction note: the crash is **not** a data wall; `unpack` preserves hierarchy | verified finding |

No upstream file was touched. No fault was suppressed, no watchdog removed, and no render context or frame was
faked. The all-sections pipeline is unchanged.

---

## 6. Tests run and results

| Test | Command | Result |
|---|---|---|
| Extract baseline | `tools.xiso unpack …` | 48 files extracted |
| Extraction verification | `scripts/m5_verify_extract.py` | 48/48 sizes match, 0 missing |
| Crash repro (full assets) | `logs/m5_run1_fullassets.log` | exit 139, same fault |
| Guest symbolisation | `scripts/m5_sym.py` | chain resolved |
| Native symbolisation | `scripts/m5_sym_native.py` | `recomp_0030.c:5323` = `edx = MEM32(ecx)` |
| Lookup evaluation | `RECOMP_M5_REGDUMP=1` | index `0xF7F180` → foreign region → `0xCF3B41FF` |
| Watchpoint | `RECOMP_WATCH=0x2F3B80` | writer = `sub_0011E840` (line 4179) |
| ABI check | separate build with `-DRECOMP_ABI_CHECK` | 11 flagged sites (see below) |

### 6.1 `RECOMP_ABI_CHECK` (the toolkit's own diagnostic)

Built in a throwaway tree (deleted afterwards) with:

```sh
MSYS2_ARG_CONV_EXCL='*' cmake -S "game/The Simpsons Road Rage" -B "…/build_abi" -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_COMPILER="C:/Users/kabyl/AppData/Roaming/Python/Python314/site-packages/ziglang/zig.exe" \
  -DCMAKE_C_COMPILER_ARG1=cc -DCMAKE_MAKE_PROGRAM="D:/Apuohjelmat/python/Scripts/ninja.EXE" \
  -DCMAKE_AR="D:/simpsons recomp/third_party/_m0_toolchain/ar.bat" \
  -DCMAKE_RANLIB="D:/simpsons recomp/third_party/_m0_toolchain/ranlib.bat" \
  -DCMAKE_EXE_LINKER_FLAGS='-L"D:/simpsons recomp/third_party/_m0_toolchain/importlibs"' \
  -DCMAKE_C_FLAGS="-fno-sanitize=undefined -DRECOMP_ABI_CHECK"
```

> **Important build note:** `CMAKE_C_FLAGS` must keep `-fno-sanitize=undefined`. The generated code performs
> benign signed-32-bit multiply overflow (`ecx * 0x1F` etc.); without it, Zig/Clang UBSan aborts at the first
> such instruction (`recomp_0048.c:6666`, `sub_00158A70`).

It caught exactly the corruption that produces the crash index, on the RadSound path:

```
[ABI] sub_001226F0: ebx esi edi
      ebx 00000000->00F7F180  esi 00000000->00F97DB8  edi 00F97DB8->00000000
```

i.e. `sub_001226F0` (an SEH-protected RadSound-side constructor reached from `sub_00122B20`) leaves `ebx`
holding **`0xF7F180`** — the exact bad index. Full list of flagged sites: `sub_0012C014`, `sub_0012C04D`,
`sub_00138080`, `sub_000B1460`, `sub_000AFEC0`, `sub_00068B90`, `sub_0006A3B0`, `sub_00123720`,
`sub_00123A90`, `sub_001226F0`, `sub_00122B20`.

**Caveat (do not over-claim):** the same diagnostic also flags `sub_000AFEC0` — the render-context constructor
whose lifting M4 *verified as correct* — and several MSVC SEH/unwind helpers that legitimately do not return
conventionally. So `RECOMP_ABI_CHECK` is **suggestive, not conclusive**, here; it is evidence of a
register/stack-corruption class, consistent with the watchpoint result, but the exact corrupting function is
not proven by it alone.

---

## 7. Before-and-after boot milestones

| Milestone | M3 | M4 | **M5** |
|---|---|---|---|
| Render context constructed | NO | YES | YES |
| Thread activity | stalled (IRQL spin) | worker threads spawn | worker threads spawn |
| Asset loading | fails (missing) | partial | **full tree, real reads** |
| Audio init (RadSound) | not reached | reached | reached |
| Graphics init | not reached | not reached | not reached |
| First NV2A submission | no (`PUT=GET=0`) | no | no |
| First presented frame | no | no | no |
| Outcome | IRQL stall | segfault at asset read | **segfault: wild registry index** |

---

## 8. Remaining blocker

**Primary:** `sub_00119140` receives an index (`0xF7F180`, a guest-stack address) instead of a small integer,
from the indirectly-dispatched handler `sub_00117460` (via the `jmp` thunk `sub_00117570`). The lookup reads
foreign committed memory and dereferences `0xCF3B41FF`.

* faulting guest function: `sub_00119140` (`recomp_0030.c:5323`, `edx = MEM32(ecx)`)
* bad index origin: `sub_00117460` arg3 ← pushed by the indirect dispatcher
* corrupting callee (ABI-check lead): `sub_001226F0` / `sub_00122B20` / `sub_00123A90`
* registry: `0x2F3B08` (30 slots, all zero; never written by lifted code)

**Secondary (unchanged from M4, not the current blocker):** guest critical-section `0x00223B38` is leaked —
a worker thread holds it (taken at guest `0x000AFE88`, inside the render-constructor region) while another
thread waits on it; `[CS] enters=414 leaves=412 (outstanding 2)`.

**Why `PUT`/`GET` are zero:** the guest never reaches the NV2A submission path. It faults during RadSound
initialisation, before any graphics device is created. The NV2A backend is not implicated — it is simply never
entered.

---

## 9. Pinned checkout cleanliness

`third_party/xboxrecomp` is at `193e2995ffaec871bb3be43a43bd66aa5fccfeb1` with a **clean** working tree
(`git status --short` empty). No upstream file was modified; the ABI-check experiment lived in a separate
build tree that has been deleted. Nothing is committed (`git status` shows only the pre-existing untracked
`README.md`, `docs/`, `scripts/`, `.gitignore`).

---

## 10. Exact commands to reproduce

```sh
cd "D:/simpsons recomp"

# 1. Extract + verify the asset tree (idempotent; re-running re-extracts identical bytes)
cd third_party/xboxrecomp
PYTHONPATH=. py -3 -m tools.xiso unpack \
  "D:/simpsons recomp/Simpsons, The - Road Rage (Europe) (En,Fr,De).iso" \
  -o "D:/simpsons recomp/game/The Simpsons Road Rage"
cd "D:/simpsons recomp"
py -3 scripts/m5_verify_extract.py logs/m5_iso_listing.txt "game/The Simpsons Road Rage"

# 2. Build (cmake is not on PATH in Git Bash)
"/c/Users/kabyl/AppData/Roaming/Python/Python314/Scripts/cmake.exe" \
  --build "game/The Simpsons Road Rage/build"

# 3. Reproduce the crash (exit 3 = watchdog harness; 139 = real crash)
RECOMP_WATCHDOG_SECS=12 RECOMP_KERNEL_LOG_BUDGET=4000 \
  timeout 90 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m5_run1_fullassets.log 2>&1

# 4. Crash diagnostics
RECOMP_M5_REGDUMP=1 RECOMP_WATCHDOG_SECS=12 RECOMP_KERNEL_LOG_BUDGET=2000 \
  timeout 90 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m5_run5_lookup.log 2>&1
py -3 scripts/m5_sym_native.py "game/The Simpsons Road Rage/build/srr_recomp.exe" --rva 0x27D89D7

# 5. Watchpoint on the scratch global
RECOMP_WATCH=0x2F3B80 RECOMP_WATCHDOG_SECS=10 RECOMP_KERNEL_LOG_BUDGET=0 \
  timeout 120 "game/The Simpsons Road Rage/build/srr_recomp.exe" > logs/m5_watch.log 2>&1
```

`$XBE`, seeds, and the all-sections recomp pipeline are unchanged from M4 (see `docs/M4-RESULTS.md` §11).

---

## 11. Disk-space considerations

| Artifact | Size |
|---|---|
| Extracted disc content | 356 MB |
| Generated C (`src/recomp/gen`, 58 files) | 47 MB |
| Build tree (`build/`) | 220 MB |
| `logs/` | 128 MB |
| `D:` free | **36 GB (97% used)** |

The extractions are affordable; the largest disposable item is still `logs/`. The ABI-check build tree (a
further ~220 MB) was deleted after use and is reproducible with §6.1.

---

## 12. Single highest-value next step

**Catch the moment the bad index is created, by watching the *object field*, not the scratch slot.**

The watchpoint proved the bad value is `sub_00117460`'s arg3, set by the indirect dispatcher. The next
experiment is to arm `RECOMP_WATCH` on the field that the dispatcher copies the argument from (the handler
record it selects), so the corrupting write is reported with its own guest stack:

1. Re-create the ABI-check build (§6.1) and re-run — it reproduces the crash *and* points at the
   `sub_00122xxx`/`sub_00123AB0` SEH cluster. Confirm whether the ABI-flagged registers (`ebx=0xF7F180`)
   reach `sub_00117460` in the same thread, or whether that cluster is an independent (false-positive) set.
2. Watch the dispatch record's argument slot with `RECOMP_WATCH=[0x…]+0x…` and `RECOMP_WATCH_RAW=1` to name
   the writer of the argument.
3. Only once the index is correct should the empty registry `0x2F3B08` be revisited — confirm whether a startup
   registrar is stubbed/never called (nothing in the lifted set writes it), then the `0x00223B38` lock leak,
   then the NV2A pushbuffer and the first frame.

The empty registry is a *second* independent problem: even with a corrected index it will take the null-slot
fallback, so both must be resolved before graphics can initialise.
