# M1 Results — Real-Executable Analysis (The Simpsons: Road Rage, Xbox)

**Status: COMPLETE — Outcome A (validated pipeline) *and* a first real-execution result.**

The recompilation pipeline was run end-to-end on the real, legally obtained Xbox
executable. It parsed, disassembled, classified, lifted **13,034 functions**, the
generated C **compiled cleanly and linked into a 56 MB native Windows PE**, and
that PE **boots the runtime and executes real guest code** — through the CRT,
kernel calls, DVD authentication and save-data lookup, to a deterministic,
logged point.

Toolkit under test: `sp00nznet/xboxrecomp` @ `193e2995ffaec871bb3e43a43bd66aa5fccfeb1`
(tag `v0.13.1`), working tree **clean** before and after. Nothing is committed.
All game files, generated source and build trees are git-ignored.

> Legend: **[verified]** = observed in this run / read from source;
> **[inferred]** = reasoned from evidence, not directly proven.

---

## 1. Executive summary

| Question | Answer |
|---|---|
| Does the toolkit build and run? | **Yes** (M0; unchanged). |
| Does it accept the real XBE directly? | **Yes** — `default.xbe` is passed as-is; no pre-extraction. **[verified]** |
| Does it lift the real title? | **Yes** — 13,034/13,034 functions, 0 failed, 1.2M lines of C. **[verified]** |
| Does generated C compile? | **Yes** — 55/55 translation units, 0 errors. **[verified]** |
| Does it link to a native EXE? | **Yes** — `srr_recomp.exe`, 56,164,352 bytes. **[verified]** |
| Does the EXE execute guest code? | **Yes** — memory map, 120/120 kernel thunks, entry point, 100+ kernel calls. **[verified]** |
| Does the game render a frame? | **No** — spins in a wait before any GPU submission. **[verified]** |
| Is RenderWare/Pure3D correct (per our docs)? | **No — refuted.** 0 RenderWare identifiers. **[verified]** |
| Is M1 passed? | **Yes (Outcome A).** Proceed to M2 bring-up. |

---

## 2. Environment and dependency versions

Unchanged from M0 (`docs/M0-RESULTS.md`); reconfirmed this run.

| Tool | Version | Notes |
|---|---|---|
| OS | Windows 11, Git Bash (`sh`) | — |
| Python | 3.14.4 (`py -3`) | runs the toolkit |
| CMake | 4.4.4 | `C:\Users\kabyl\AppData\Roaming\Python\Python314\Scripts\cmake.exe` |
| Ninja | 1.13.2 | `D:\Apuohjelmat\python\Scripts\ninja.EXE` |
| Zig (`zig cc`) | 0.16.0, **Clang 21.1.0** | `…\site-packages\ziglang\zig.exe`; no MSVC on this machine |
| capstone | 5.0.7 | used for the manual `0x0011B210` decode check |

No new packages were installed or downloaded for M1. Zig's bundled Windows SDK
import libs cover `d3d11/dxgi/dxguid/winmm/dbghelp`; `xinput` comes from the M0
synthesized import lib in `third_party/_m0_toolchain/importlibs`.

---

## 3. Input: disc image and XBE

### 3.1 ISO — `Simpsons, The - Road Rage (Europe) (En,Fr,De).iso`
- 374,472,704 bytes, in the project root. **[verified]**
- Original-Xbox **XDVDFS** image, *verified by structure, not size*: `MICROSOFT*XBOX*MEDIA`
  magic at `0x10000`, ISO9660 `CD001` descriptors, `XBEH` at `0x121E800`. **[verified]**
- PAL/Europe (disc ships `movies/pal/` and `movies/ntsc/`). **[verified]**
- `default.xbe` extracted with the toolkit's own **read-only** reader (`tools.xiso`,
  pure Python). The ISO was not modified; nothing was downloaded. **[verified]**

### 3.2 Extracted executable
`game\The Simpsons Road Rage\default.xbe` — **2,187,264 bytes**.

| Field | Value |
|---|---|
| Magic | `XBEH` |
| SHA-256 | `42c45d346072e3575828b1e25f6b9f4aabe2af847d3331eccda7ad1dd9a2e23b` |
| Title ID | `0x45410013` (Retail) |
| Build date | 2002-02-12 22:50:03 UTC |
| Certificate date | 2002-02-18 08:58:18 UTC |
| Region | Rest of World (PAL) |
| Media type | DVD_X2, disc 0 v2 |
| Base address | `0x00010000` |
| Entry point | `0x000998AF` (raw `0xA8F5CF04`) |
| Image size | `0x00300F60` (3.00 MB) |
| Kernel thunk table | `0x001B98E0` |
| TLS index address | `0x00223738` (12 zero-fill bytes) |
| Debug path | `D:\project\srrpal\code\build\xbox\Release\simpsons.exe` |

The debug path confirms the retail build is **`simpsons.exe`** — an in-house
executable, not a third-party engine shell. **[verified]**

### 3.3 Sections (23) and imported libraries
Link libraries declared in the XBE header: **XAPILIB, D3D8, XBOXKRNL, LIBC,
LIBCPMT, LIBCI, XGRAPHC** (all `1.0.4039`). **120 kernel imports** across
Av/Ex/Hal/Io/Ke/Kf/Mm/Nt/Ob/Ps/Rtl/Xbox/Xc. **[verified]**

Notable code sections (VA / virtual size):

| Section | VA | VSize | Role |
|---|---|---|---|
| `.text` | `0x00011000` | 1,349,424 | game + CRT |
| `D3D` | `0x0015A740` | 140,176 | D3D8 runtime (RK) |
| `DSOUND` | `0x0017CAE0` | 112,508 | DirectSound runtime |
| `BINK*` (×12) | `0x00198260`+ | — | Bink video codecs (RAD) |
| `XGRPH` | `0x001B1180` | 4,640 | Xbox graphics helpers |
| `XPP` | `0x001B23A0` | 30,016 | Xbox push-buffer helpers |
| `.rdata` | `0x001B98E0` | 244,164 | — |
| `.data` | `0x001F52C0` | 1,102,968 | — |
| `DOLBY` | `0x00302740` | 28,056 | Dolby audio |
| `BINKDATA` | `0x003094E0` | 17,008 | Bink data |
| `$$XTIMAGE` / `$$XSIMAGE` | `0x0030D760` / `0x0030FF60` | 10,240 / 4,096 | XBE title/save images |

**No core RenderWare or Pure3D section** is present. Graphics go straight through
**D3D8** with the XDK's `XGRAPHC`/`XPP` helpers. **[verified]**

---

## 4. Function identification (`tools.func_id`)

- `.text` swept: **497,824 instructions**, **12,977 functions**, **83,527 xrefs**,
  3,859 strings. Function-detection breakdown: `tail_jump_alias` 6,790,
  `call_target` 4,515, `cc_boundary` 748, `prologue` 306, `imm_ref_target` 251,
  `tail_jump_target` 186, `gap_prologue` 177, `indirect_call_slot` 3, `entry_point` 1.
- Functions by section: `.text` 12,859 · `D3D` 67 · `DSOUND` 31 · `BINK` 9 · `XPP` 9 · `XGRPH` 2.

After vtable scanning, the classifier produced **16,314 classifications**:

| Class | Count | Note |
|---|---|---|
| Game (classified) | 9,852 (60.4%) | of which 6,033 vtable methods |
| Unknown | 6,451 (39.5%) | mostly reachable-by-pointer game code |
| CRT/MSVC | 11 | `strcmp, strcpy, memmove, _ftol, _ftol2, _allmul, _aullshr, _allshr, _alldiv, fmod, _purecall` |
| **RenderWare** | **0 (0.0%)** | see §8 |
| Data-init stubs | 0 | |

C++ is pervasive: **968 validated vtables, 11,792 virtual methods, 905
constructors, 3,337 vtable thunks** discovered. This is a C++ title with a heavy
vtable layer — the reason indirect-call feedback (§6.2) matters so much.

`tools/abi_analysis`: 12,977 ABI entries, **2,983 detected `thiscall`** (`me` in
`ecx`). `tools/doctor.py`: *"no known blockers found in supplied artifacts/logs."*

---

## 5. Translation and compilation

### 5.1 Lift
```
py -3 -m tools.recomp "D:/simpsons recomp/game/The Simpsons Road Rage/default.xbe" \
  --game-name "The Simpsons Road Rage" --all --split 250 \
  --gen-dir "D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/gen"
```

| Metric | Value |
|---|---|
| Functions translated | **13,034 / 13,034 (0 failed)** |
| Lines of C | **1,199,496** |
| Source files | 53 chunks + `recomp_funcs.h` + `recomp_types.h` + `recomp_dispatch.c` + `recomp_stubs_unresolved.c` |
| Generated size | **45 MB** |
| Unresolved call targets (stubbed) | 533 |
| Unimplemented instructions | **57 instructions, 22 distinct mnemonics** |

> Note: passing `--header` *alongside* `--all` silently switches to header-only
> mode and generates no `.c`. The header is already emitted by the split path, so
> do **not** add `--header`. (Toolkit behaviour, verified in source
> `tools/recomp/__main__.py` L377-396.)
>
> **M4 correction:** the analysis above (and the lift it fed) used
> `tools.disasm --text-only`, which sweeps **only `.text`**. The loader
> deliberately treats the Xbox SDK code sections (`D3D`, `DSOUND`, `BINK`,
> `XGRPH`, `XPP`, `DOLBY`) as code and would have disassembled them; `--text-only`
> silently excludes them, so those libraries were left almost entirely
> un-disassembled (D3D: 68 functions out of a 140 KB section; DSOUND: 31). See
> [M4-RESULTS.md](M4-RESULTS.md) §3. Drop `--text-only` to analyse all code
> sections.

Unimplemented mnemonics (all rare/priviliged; none executed in the run so far):
`das, int1, popfd, in, enter, iretd, les, aam, ltr, lldt, verw, sldt, verr, str,
bound, lcall, lds, ljmp, out, outsd, hlt, aas`. These lift to inert no-op
comments — honest, not hidden. Many are almost certainly data misread as code or
rare CRT/system stubs; they must be reviewed if execution ever reaches them.

### 5.2 Compile — all of it
Every generated translation unit was compiled to an object with Zig/Clang:

```
zig cc -fno-sanitize=undefined -w -c -O0 -I<gen> -I third_party/xboxrecomp/src/kernel <file>.c
```

**55/55 files, 0 failures, 152 s, 113 MB of objects.** Only warnings (benign
`-Wparentheses-equality` from the lifter's `if ((_fa == 0))` idiom).

### 5.3 Link — full native executable
Project scaffolded from `templates/new-game` into `game/The Simpsons Road Rage/`
(CMakeLists + `src/main.c` + `src/recomp_manual.c`), configured with the M0 Zig
recipe and built with Ninja.

**Result: `srr_recomp.exe`, 56,164,352 bytes, 0 errors.** **[verified]**

Two build fixes were needed and are recorded here (project-side only — **no
upstream source was modified**):

1. **`recomp_dispatch_init` was undeclared in the template `main.c`.**
   MSVC only *warns* (C4013) on the implicit declaration, so the template works
   under MSVC. **Clang 21 / Zig rejects it as an error.** Fixed by adding an
   explicit `extern int recomp_dispatch_init(void);` to our `main.c`. This is a
   genuine MSVC-vs-Clang portability gap in the template, not a bug we introduced.
   *(Root cause of the first link failure — the only error in the first build.)*
2. **`/LARGEADDRESSAWARE` cannot be set through `zig cc`.** Zig rejects both
   `-Wl,/LARGEADDRESSAWARE` and `-Wl,--large-address-aware` and exposes no native
   switch. Dropped: the guest maps at image base `0x00010000` with a 64 MB RAM
   window, all below the 2 GB ceiling of a non-LAA 32-bit process, so it is not
   required for bring-up. **If the title ever needs VAs ≥ 2 GB, this becomes a
   real blocker** and would require MSVC or a PE post-processing step.

---

## 6. Runtime behaviour — the EXE actually runs

Built as a **console** app (`WIN32_EXECUTABLE FALSE`) purely to see the boot log;
run from the repo root so the relative XBE path resolves.

### 6.1 Unseeded run — reaches the guest, then stalls
`logs/m1_run1.log` **[verified]**

1. Loaded XBE (2,187,264 bytes).
2. `xbox_MemoryLayoutInit`: mapped 65,536 KB; 23/23 sections; 120-entry kernel
   thunk table; 8 MB stack; TLS+TIB; 64 MB contiguous window at `0x80000000`;
   NV2A aperture at `0xFD000000`; MCPX/Flash apertures; 48 MB heap; RAM mirror
   (28/28 views); tiled aperture alias verified. Offset `0x10000`.
3. Kernel + kernel bridge: **120/120 thunks resolved (120 bridged, 0 stub)**.
4. `g_esp = 0x00F7FFF0`; called `xbe_entry_point()`.
5. Guest ran → **kernel call #1, ordinal 255 `PsCreateSystemThreadEx`** (ret `0x0009D61D`).
6. Then **stuck in a tight loop**: ~105k+ indirect calls, every one failing —
   `[ICALL] Failed to resolve VA 0x0011B210`. Watchdog: *"no exit after 15s."*

**Root cause (verified):** `0x0011B210` is a real function. A manual Capstone
decode shows a textbook `thiscall` prologue (`sub esp,8; push ebx/ebp/esi; mov esi,ecx`).
The detector had **merged it into `0x0011B1B0`** (adjacent method, no padding),
so it had no dispatch entry and `recomp_lookup` returned NULL. **[verified]**

### 6.2 Indirect-call feedback loop — it works
This is the toolkit's documented bring-up loop. `tools.seed_from_log` read the run
log and emitted **5** gated seeds (`logs/…` → `src/recomp/seed_functions.json`):

```
+ 00099840  new function   (PsCreateSystemThreadEx StartContext1 observed)
+ 000B0040  new function   (PsCreateSystemThreadEx StartContext1 observed)
+ 000D5500  alias inside sub_000D54F0 (indirect-call target)
+ 0011B210  new function   (indirect-call target)
+ 0011D270  new function   (PsCreateSystemThreadEx StartContext1 observed)
```

Three are **thread start routines** — invisible to static analysis (they are only
ever passed as an argument to `PsCreateSystemThreadEx`), the toolkit's documented
"it built and did nothing" cause. The seeds were fed back through
`disasm --seed-functions … --force` (all 5 became starts), then `func_id`,
`abi_analysis`, `recomp` (now 13,036 funcs, 1,200,111 lines) and a rebuild.

### 6.3 Seeded run — deep into init, then a wait
`logs/m1_run2.log` **[verified]** — the ICALL failure loop is **gone**.
The guest now issues 100+ kernel calls of many ordinals, including:

- `#1 PsCreateSystemThreadEx` (routine `0x0009D546`), `#2 RtlEnterCriticalSection`
  (`#277`), `RtlLeaveCriticalSection` (`#294`), `#4 KeInitializeDpc` (`#107`),
  `#5 KeInitializeTimerEx` (`#113`), `#8 KeSetTimer` (`#149`)
- `#6 ExQueryNonVolatileSetting` (`#24`), `#7 RtlNtStatusToDosError` (`#301`)
- `#9/#10 NtAllocateVirtualMemory` (`#184`)
- `#12 NtOpenFile` (`#202`) → **`\Device\CdRom0`**; `#13 NtDeviceIoControlFile`
  (`#196`) → **DVD MODE SENSE page 0x3E authentication**
- `#15 NtOpenFile` → `\Device\Harddisk0\partition1\`; `#18/#24 IoCreateSymbolicLink` (`#67`)
- save-data probes `\Device\Harddisk0\partition1\TDATA\45410013` and `…\UDATA\45410013`
- `RtlInitAnsiString` (`#289`), `RtlEqualString` (`#279`)

So the recompiled CRT + engine entry genuinely runs: it authenticates the disc,
looks up save directories by the real title ID, and sets up timers/DPCs.

**Then it spins.** The watchdog fires at 20 s with:
- `KeRaiseIrqlToDpcLevel` (ordinal **129**) and `KfLowerIrql` (ordinal **161**)
  called ~**10⁸ times**, plus a synthetic-VA indirect call (`FE000070/FE000074`),
  and ~3.1×10⁸ total indirect calls;
- `NV2A USER PUT=00000000 GET=00000000` and `PFIFO PUT=GET=0` — **nothing has been
  submitted to the GPU.**

**[inferred]** This is a synchronisation/threading wait (an IRQL-guarded spin,
very likely waiting on a thread or signal that the current runtime geometry never
satisfies), *before* any rendering. It is a runtime gap, **not** a translation
defect — the code is executing the guest's own instructions in the guest's own
loop.

---

## 7. Runtime functionality: provided vs. required

### 7.1 Already provided by the toolkit **[verified]**
- XBE load + section mapping at original VAs, 64 MB RAM window, tiled alias,
  NV2A/MCPX/Flash apertures, heap.
- **All 120 kernel imports routed** (170/371 ordinals have Win32 bridges; every
  ordinal is reachable). This run exercised `Nt*`, `Ke*`, `Rtl*`, `Ex*`, `Io*`,
  `PsCreateSystemThreadEx`, DVD auth and save-path translation successfully.
- Generated-code scaffolding: register model, `MEM32`/`XBOX_PTR`/`PUSH32`, flat
  dispatch + binary search, unresolved-target stubs, SEH prolog/epilog, CRT
  `setjmp/longjmp`, ICALL-feedback instrumentation hooks.
- VEH crash handler with guest-context + stack dump; hang watchdog; dbghelp
  symbol resolution.

### 7.2 Provided by existing reusable projects **[verified present, not yet exercised]**
The toolkit bundles emulation libraries ported from other projects (per its
`README`/`src/README.md`): `xbox_nv2a` (from xemu), `xbox_apu` (MCPX, from xemu),
`xbox_d3d8` (D3D8→D3D11), `xbox_dsound` (software mixer), `xbox_input`
(gamepad→XInput), `xbox_usb`, `xbox_usb/ohci` (D3D smoke tests built in M0).

### 7.3 Requires our own work
- **Threading/synchronisation geometry.** The observed spin is the immediate
  blocker. The bridge "calls the StartRoutine synchronously" for
  `PsCreateSystemThreadEx`; the guest clearly expects real concurrent threads and
  a wait to be satisfied. This needs investigation (thread model, event/timer
  signalling, IRQL no-ops) before anything else will progress.
- Non-volatile/settings + save-data semantics (currently synthetic).
- Whatever title-specific behaviour the deeper CRT/engine init expects.

### 7.4 Unknown / needs investigation
- Why the loop is IRQL-guarded and which wait never resolves (needs `--trace-functions`
  and `RECOMP_WATCHDOG` bring-up, possibly `icall_feedback` again after progress).
- The 533 stubbed unresolved targets and the 57 unimplemented instructions — are
  any on the critical boot path? (None struck yet.)
- Whether the guest ever reaches D3D8 push-buffer submission (it has not).

---

## 8. Documentation corrections (verified findings)

- **RenderWare/Pure3D assumption is REFUTED.** `func_id` found **0 RenderWare ID
  strings**, and the XBE confirms it: libraries are XAPILIB/D3D8/XBOXKRNL/CRT/
  XGRAPHC; sections are `D3D`, `DSOUND`, `BINK*`, `XGRPH`, `XPP`, `DOLBY`. The
  builder path is `simpsons.exe`. **This is a direct-XDK D3D8 title with an
  in-house engine, not RenderWare.** (`FEASIBILITY.md`/`ARCHITECTURE.md` language
  that anticipates a RenderWare bridge layer should be corrected accordingly.)
- **Audio is Bink + DOLBY + DirectSound**, not a single API. Bink video codecs
  are statically linked into the XBE.
- A correct `recomp` invocation must **not** include `--header` with `--all`.
- The `new-game` template's `main.c` is **MSVC-oriented** (implicit function
  declaration). It needs one explicit declaration to build under Clang/Zig (§5.3).

---

## 9. Disk-space considerations

| Before M1 | After M1 |
|---|---|
| `D:` free **36.9 GB** | `D:` free **36 GB** |

Consumed ≈ **1 GB total** on `D:` for: 45 MB generated source + 113 MB object tree
(`logs/obj`, transient) + 56 MB EXE + build tree. This is well inside the
2–3 GB budget from Stage 1, far below the Burnout-3 precedent (200 MB+ source)
because this title is ~60% the function count. **No disk pressure.** The ISO
(357 MB) and extracted XBE (2.1 MB) also live on `D:`.

---

## 10. Is startup feasible?

**Yes, and it is already past the hard part.** The pipeline is proven end-to-end
on the *real* binary: parse → classify → lift → compile → link → **execute guest
code through CRT init, disc authentication and save-data lookup**. The remaining
wall is a specific runtime synchronisation wait, and the toolkit supplies the
diagnostic tooling (`seed_from_log`, `icall_feedback`, `--trace-functions`,
`RECOMP_WATCHDOG_SECS`) to attack it.

We must **not** claim the game "boots" — no frame is rendered and the guest never
submits GPU work. It reaches a deterministic, logged execution point, which is the
M1 Stage-4 goal.

---

## 11. Exact next steps (M2)

1. **Attack the IRQL spin.** Re-run with `--trace-functions` on the handful of
   functions around the `KeRaiseIrqlToDpcLevel` call site and with the watchdog on;
   determine which condition the guest is polling and which service never sets it.
   Prime suspects: `PsCreateSystemThreadEx` being run synchronously instead of as a
   real concurrent thread, and event/timer signalling.
2. **Second ICALL-feedback pass.** Re-run the game after any progress, feed the new
   log to `seed_from_log` → `icall_feedback`, re-disasm with `--seed-functions`,
   re-lift, rebuild. Expect more thread routines and vtable targets to surface.
3. **Triage the 57 unimplemented instructions** and 533 stubs — only if execution
   reaches them.
4. **Introduce real D3D8/NV2A output** only once the guest reaches a push-buffer
   submit (currently `PUT=GET=0`).
5. **Durable bring-up harness:** keep the seeded pipeline as a script
   (`scripts/m1_translate.sh`) so every rebuild is reproducible.

---

## 12. Reproducible command log (this milestone)

```sh
# Stage 2 — analysis (logs/ holds every output)
bash scripts/m1_analyze.sh                     # parser, disasm, func_id, abi, doctor

# Stage 3 — lift, compile, link
py -3 -m tools.recomp "D:/simpsons recomp/game/The Simpsons Road Rage/default.xbe" \
  --game-name "The Simpsons Road Rage" --all --split 250 \
  --gen-dir "D:/simpsons recomp/game/The Simpsons Road Rage/src/recomp/gen"
# compile every TU (0 failures):
for f in <gen>/recomp_*.c; do zig cc -fno-sanitize=undefined -w -c -O0 \
  -I<gen> -I third_party/xboxrecomp/src/kernel "$f" -o logs/obj/$(basename "$f" .c).o; done
# configure + build the game exe
cmake -S "game/The Simpsons Road Rage" -B "game/The Simpsons Road Rage/build" -G Ninja \
  -DCMAKE_MAKE_PROGRAM=<ninja> -DCMAKE_C_COMPILER=<zig> -DCMAKE_C_COMPILER_ARG1=cc \
  -DCMAKE_AR=<ar.bat> -DCMAKE_RANLIB=<ranlib.bat> -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_FLAGS=-fno-sanitize=undefined \
  '-DCMAKE_EXE_LINKER_FLAGS=-L"D:/simpsons recomp/third_party/_m0_toolchain/importlibs"'
cmake --build "game/The Simpsons Road Rage/build"

# Stage 4 — run (bounded by the watchdog)
RECOMP_WATCHDOG_SECS=20 "game/The Simpsons Road Rage/build/srr_recomp.exe"   # from repo root

# ICALL feedback round
py -3 -m tools.seed_from_log <run.log> <xbe> --functions tools/disasm/output/functions.json \
  --seeds "game/The Simpsons Road Rage/src/recomp/seed_functions.json"
py -3 -m tools.disasm <xbe> --text-only \
  --seed-functions "game/The Simpsons Road Rage/src/recomp/seed_functions.json" --force
# M4: drop --text-only. It sweeps only .text and leaves the SDK code sections
# (D3D, DSOUND, BINK, XGRPH, XPP, DOLBY) un-disassembled. See M4-RESULTS.md §3.
py -3 -m tools.func_id <xbe>   &&  py -3 -m tools.abi_analysis <xbe>
# …then re-run tools.recomp and rebuild.
```

Artifacts kept (all git-ignored): `game/The Simpsons Road Rage/` (XBE, generated
`src/recomp/gen`, build tree), `logs/` (analysis + run logs), `scripts/`.

**Nothing committed. No upstream file modified. Game binaries never in version control.**
