# M0 Results — Validating the Recompilation Toolchain

**Milestone:** M0 — set up and validate the recompilation technology.
**Date:** 2026-10-09
**Outcome:** **Outcome A — validated pipeline** (with one environment caveat to carry forward).
**Scope:** toolchain only. No renderer, audio, gameplay, or asset work was written.

This document records what was actually built, run, and observed. Every command in
the "Commands" blocks was executed in this workspace; the quoted outputs are real.
Where something is inferred rather than observed it is labelled **Hypothesis**.

---

## 1. Executive summary

`sp00nznet/xboxrecomp` (MIT) is a **complete original-Xbox static-recompilation
toolkit**, not just an x86→C translator. It ships:

- a Python pipeline — `xbe_parser → disasm → func_id → abi_analysis → recomp`
  (plus `split`, `fusion`, `doctor`, `conformance`, `kernel_audit`, …);
- **eight C runtime libraries** (`platform`, `kernel`, `d3d8`, `dsound`, `apu`,
  `nv2a`, `usb`, `input`, `video`) that implement the Xbox kernel, D3D8→D3D11
  graphics, DirectSound→software mixer, MCPX APU, NV2A GPU, USB gamepad, input
  and FMV playback;
- game-project templates (`templates/new-game`, `templates/runtime`).

All of the above was **verified by building and running it** in this workspace with a
free toolchain (Zig's `clang`, pip-installed CMake + Ninja):

| Check | Result |
|---|---|
| Unit/functional test suite (`pytest tools/`) | **638 passed, 3 skipped, 0 failed**, 106 subtests |
| Build all 8 runtime libraries | **8/8 static libraries produced** |
| Build + run toolkit's own D3D smoke tests | **4/4 executables link and pass** |
| End-to-end translation of a synthetic XBE | parse → disasm → func_id → abi → recomp → **5/5 functions lifted to C** |
| Compile the generated C | **succeeds** |
| **Execute** the generated C against expected values | **9/9 checks pass** |

The one caveat: Microsoft's documented toolchain (MSVC / Windows SDK) provides two
import libraries — `xinput` and `d3dcompiler` — that Zig's bundled Windows SDK does
**not** ship. They were generated from Zig's own versioned `.def` files
(`xinput1_4`, `d3dcompiler_47`) with `zig dlltool`; with those on the linker path the
entire build is green. This is an environment detail, not a toolkit defect, and it is
fully reproducible.

**Is the project realistically achievable?** For the *translation technology*, yes —
demonstrated. Whether Road Rage itself runs depends on per-title runtime coverage
that M0 deliberately did not attempt (see §10–§11). M1 is justified.

---

## 2. Environment and dependency versions

| Item | Value |
|---|---|
| OS | Windows (Git Bash shell) |
| Python | 3.14.4 (`D:\Apuohjelmat\python`) |
| pip-installed `cmake` | 4.4.4 (`%APPDATA%\Python\Python314\Scripts\cmake.exe`) |
| pip-installed `ziglang` | 0.16.0 (`…\site-packages\ziglang\zig.exe`, LLVM/Clang 21.1.0) |
| `ninja` | 1.13.2 (`D:\Apuohjelmat\python\Scripts\ninja.exe`) |
| `capstone` | 5.0.7 |
| `pytest` | 9.1.1 |
| `pefile` | 2024.8.26 |
| MSVC / Windows SDK | **not installed** (volumes are 96–99 % full; a multi-GB MSVC install is impractical) |
| Disk | `D:` ~37 GB free, `C:` ~5 GB free, `E:` ~5.7 GB free |

No global configuration was changed. `cmake` and `ziglang` are pip packages installed
into the user site; the compiler/archiver shims live in the repository under
`third_party/_m0_toolchain/` (see §4).

### Compiler shims (`third_party/_m0_toolchain/`)

The test suite locates a compiler with `shutil.which("clang") or shutil.which("gcc")`.
`gcc.bat` / `clang.bat` expose `zig cc` under those names and add
`-fno-sanitize=undefined` (see §5). `ar.bat` / `ranlib.bat` expose `zig ar` /
`zig ranlib` (CMake needs an archiver; Zig bundles LLVM's).

---

## 3. Upstream repository and exact revision

| Field | Value |
|---|---|
| Repository | `https://github.com/sp00nznet/xboxrecomp` |
| Revision tested | `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` |
| Tag / subject | `v0.13.1` — "Release v0.13.1 -- \"Cut Short\"" (committed 2026-10-07) |
| Clone | `git clone --depth 1` into `third_party/xboxrecomp` |
| License | **MIT** (`LICENSE`), except `src/apu/**` and `src/nv2a/nv2a_regs.h` which are **LGPL-2.1-or-later** (xemu-derived). LGPL permits linking from MIT/proprietary code provided notices are preserved. |

The toolkit's own reference title is **Burnout 3: Takedown** (a RenderWare game); the
README lists RenderWare engines as the *easier* target class ("shared patterns") and
lists shipped/underway ports: Burnout 3, Xbox Dashboard, Wreckless (3,407 functions),
Blood Wake (4,608 functions, 367K lines C, 99.1 % success), Halo, Half-Life 2.

---

## 4. Build instructions and results

The upstream README documents CMake + MSVC. Because MSVC is unavailable here, the
build was performed with CMake + Ninja + Zig. **No upstream source file was modified.**

### 4.1 One-time environment setup (already done in this workspace)

Compiler/archiver shims and the two synthesized import libraries:

```sh
# third_party/_m0_toolchain/gcc.bat  and  clang.bat:
"…\ziglang\zig.exe" cc -fno-sanitize=undefined %*
# third_party/_m0_toolchain/ar.bat  /  ranlib.bat:
"…\ziglang\zig.exe" ar %*        #  … zig.exe ranlib %*
```

```sh
# Synthesize the two import libs Zig does not bundle, from Zig's own defs:
ZIG="C:\Users\kabyl\AppData\Roaming\Python\Python314\site-packages\ziglang\zig.exe"
DEFDIR="…\ziglang\lib\libc\mingw\lib-common"
OUT="third_party/_m0_toolchain/importlibs"

"$ZIG" dlltool -d "$DEFDIR/xinput1_4.def"      -D xinput1_4.dll      -l "$OUT/libxinput.a"
"$ZIG" dlltool -d "$DEFDIR/d3dcompiler_47.def" -D d3dcompiler_47.dll -l "$OUT/libd3dcompiler.a"
```

Zig already bundles `d3d11`, `dxgi`, `dxguid`, `winmm`, `dbghelp`, `mfplat`, `ws2_32`,
`user32`, `gdi32`, `ole32`, `uuid` — verified by linking a probe program against each.
Only `xinput` and `d3dcompiler` were absent.

### 4.2 Configure and build the runtime libraries

```sh
cd third_party/xboxrecomp
CMAKE="…\Scripts\cmake.exe"; NINJA="…\ninja.exe"; ZIG="…\zig.exe"
"$CMAKE" -S . -B …/_m0_build/xr -G Ninja \
    -DCMAKE_MAKE_PROGRAM="$NINJA" \
    -DCMAKE_C_COMPILER="$ZIG" -DCMAKE_C_COMPILER_ARG1=cc \
    -DCMAKE_AR="…/_m0_toolchain/ar.bat" \
    -DCMAKE_RANLIB="…/_m0_toolchain/ranlib.bat" \
    -DCMAKE_BUILD_TYPE=Release \
    '-DCMAKE_EXE_LINKER_FLAGS=-L"…/_m0_toolchain/importlibs"'
"$CMAKE" --build …/_m0_build/xr
```

Result — **every target builds**, including the toolkit's own executables:

```
src/apu/libxbox_apu.a
src/audio/libxbox_dsound.a
src/d3d/libxbox_d3d8.a
src/input/libxbox_input.a
src/kernel/libxbox_kernel.a
src/nv2a/libxbox_nv2a.a
src/usb/libxbox_usb.a
src/video/libxbox_video.a
src/d3d/d3d8_smoke/d3d8_smoke.exe        d3d8_states_smoke.exe
src/d3d/d3d8_smoke/d3d8_a8.exe           d3d8_gamma.exe
```

Two build notes discovered by doing it:

1. `CMAKE_AR` was `-NOTFOUND` until pointed at a real archiver; CMake's `find_program`
   does not find a bare `ar` on this box. Zig's `zig ar` fixes it.
2. `xbox_d3d8` (and the `new-game` template) link `xinput` and `d3dcompiler` by
   unsuffixed name; Zig only has versioned defs. Hence §4.1.

### 4.3 Run the toolkit's own tests

```sh
…/_m0_build/xr/src/d3d/d3d8_smoke/d3d8_states_smoke.exe   # -> 0 FAILURE(S)
…/_m0_build/xr/src/d3d/d3d8_smoke/d3d8_gamma.exe          # -> 0 failures, 9 captured + 1 real DXGI present
…/_m0_build/xr/src/d3d/d3d8_smoke/d3d8_a8.exe             # -> 0 failures (336 A8 + 4 RHW draws)
…/_m0_build/xr/src/d3d/d3d8_smoke/d3d8_smoke.exe          # -> ALL PASS
```

`d3d8_gamma`/`d3d8_a8` created a **real D3D11 device**, compiled the D3D8→D3D11
fixed-function shaders through `d3dcompiler_47.dll`, and presented — i.e. the graphics
compatibility layer is functional on this machine, not merely compiled.

---

## 5. Tests and reproducible results

### 5.1 Python suite

```sh
cd third_party/xboxrecomp
export PATH="/d/simpsons recomp/third_party/_m0_toolchain:$PATH"
python -m pytest tools/ -q
# 638 passed, 3 skipped, 106 subtests passed in ~80s
```

**Without a compiler on `PATH`** the same command reports `601 passed, 40 skipped` —
forty compile-dependent tests skip *silently*. A green run therefore proves nothing on
its own; the compiler must be present. The 40 skipped tests are the ones that compile
and run generated code.

### 5.2 The three skipped tests (all environmental, none indicate a toolkit defect)

```
SKIPPED tools/conformance/test_conformance.py:23
        needs a 32-bit MSVC (vcvars32.bat) to assemble and build the harness,
        or XBOXRECOMP_PYTEST_DOCKER=1
SKIPPED tools/conformance/test_fuzz.py:62   needs 32-bit MSVC
SKIPPED tools/recomp/test_lifter_sf_overflow.py:129
        this compiler has no signed-integer-overflow sanitiser
```

- The two **conformance** tests are the differential suite (assemble snippets with
  MSVC, lift the same bytes, run both and compare). They require a 32-bit MSVC
  toolchain or the project's Linux/i386 Docker images — neither is available here.
  This is the *most valuable* remaining test (see §10); it is a genuine coverage gap in
  M0, not a failure.
- `test_lifter_sf_overflow` needs `-fsanitize=signed-integer-overflow`, which Zig's
  `zig cc` does not expose as a detection; it skips by design.

### 5.3 Compiler-behaviour findings (the previously failing tests)

Three tests failed before this session's work was applied:
the two `test_lifter_double_shift.py::test_negative_control_*` cases and
`test_result_sign_width.py::test_result_sign_uses_operand_width`.

**Root cause:** these are *negative-control* tests. They deliberately compile the
**old, buggy** SHLD/SHRD expression and require the process to exit **1**, i.e. they
depend on the host compiler **silently wrapping** the C shift-by-32 (`>> (32 - 0)`)
undefined behaviour, as MSVC and Clang do at `-O0`. `zig cc` in its default (Debug)
mode instead **traps UB**:

```
thread 18496 panic: shift exponent 32 is too large for 32-bit type 'uint32_t'
    ub.c:8: eax = (eax << (LO8(ecx))) | (edx >> (32 - (LO8(ecx))));
exit=3
```

so `assert ran.returncode == 1` failed. The **positive** tests
(`test_matches_x86_at_every_count`, `test_the_count_is_masked_and_zero_is_a_no_op`)
always passed, proving the *current* lifter output is correct.

**Resolution:** the shims add `-fno-sanitize=undefined`, which restores MSVC/Clang
wrapping semantics (exactly what a recompiler needs — x86 relies on wrapping):

```
zig cc -fno-sanitize=undefined ub.c && ./ub.exe   # -> no trap
python -m pytest tools/recomp/test_lifter_double_shift.py tools/recomp/test_result_sign_width.py -q
# 7 passed
```

This was an **environment/compiler-behaviour incompatibility**, not an upstream bug.
No upstream source was changed.

---

## 6. Confirmed input and output formats

Verified from source and by running the pipeline.

**Input:** an original-Xbox `default.xbe` (the toolkit parses the XBE header, certificate,
section table, `XbeLibraryVersion` entries and the kernel-import/thunk table directly).
No separate extraction step is required for the recompiler itself; disc **assets** are
read at runtime from the game directory. Verified flags (`tools/recomp/__main__.py`):
`--all`, `--game-only`, `-f/--function`, `-c/--category`, `-n/--max-funcs`,
`--split N`, `--gen-dir`, `--output-dir`, `--manual-functions`, `--exclude-manual`,
`--force-return`, `--coalesce-functions`, `--icall-sites`, … The dispatch table is
generated and uses a flat indexed table with a binary-search fallback
(`recomp_dispatch.c`).

**Output:** **C** (not C++, not assembly, not objects). Confirmed by running `recomp`:
it emitted `recomp_0000.c`, `recomp_dispatch.c`, `recomp_funcs.h`, `recomp_types.h`.
Each lifted function is a `void f(void)` that manipulates a **global register model**
(`g_eax`, `g_ecx`, … via `#define eax g_eax`), a simulated SDK stack
(`MEM32`/`PUSH32`/`POP32`), and per-instruction flag snapshots — real x86 semantics.
The starter project (`templates/new-game`) is compiled and linked with CMake.

**Two things are supplied by the host project, not generated:** the register/memory
runtime (`src/kernel/xbox_memory_layout.c` defines `g_eax`, `g_xbox_mem_offset`, …) and
`recomp_lookup` / `recomp_lookup_manual` dispatch (the generated `recomp_dispatch.c`
provides `recomp_lookup`; hand overrides live in `src/recomp_manual.c`).

---

## 7. Runtime functionality already provided by the toolkit

Verified from `src/**` and the root `CMakeLists.txt` (which links all eight libraries
into an `xboxrecomp` umbrella INTERFACE target; "this repo builds libraries only — there
is no game `.exe` here"):

| Library | Provides |
|---|---|
| `platform` | Win32/NT vocabulary + POSIX-ish host primitives |
| `kernel` | Xbox kernel → Win32: memory layout/`CreateFileMapping` at Xbox VAs, file I/O + `D:\` path translation, threading, `KeXxx` sync, crypto, HAL, EEPROM, SMBus. **170 of 371 kernel ordinals have dedicated bridges; all 371 are routed** (real bridge, documented stub, or data entry). |
| `d3d8` | **D3D8 → D3D11**: 4-stage multi-texture FFP, NV2A register combiners, programmable vertex shaders (NV2A microcode → HLSL), hardware T&L, fog, `DrawPrimitiveUP` ring buffer, texture unswizzle, 20+ format converters. Uses `D3DCompile` (`d3dcompiler`). |
| `dsound` | DirectSound8 → software mixer |
| `apu` | MCPX APU (256-voice; xemu, LGPL) |
| `nv2a` | NV2A register handlers / MMIO / push-buffer → D3D11 |
| `input` | Xbox pad → XInput |
| `usb` | MCPX OHCI host controllers (a pad exists only if these registers do) |
| `video` | FMV via Media Foundation → D3D8 texture |

The `new-game` template's `WinMain` shows the intended boot order: load XBE →
`xbox_MemoryLayoutInit` → `xbox_kernel_init` → `xbox_path_init` → `xbox_kernel_bridge_init`
→ `g_esp = XBOX_STACK_TOP` → `recomp_dispatch_init()` → `xbe_entry_point()`, with a VEH
fault handler and a hang watchdog.

---

## 8. Missing runtime functionality (what our project must still supply)

- **Per-title correctness.** The libraries are title-agnostic, but every uncovered
  kernel ordinal, unimplemented instruction, misrouted thunk or indirect-call target is
  found per title. `tools/doctor.py`, `tools.kernel_audit`, `--icall-feedback` and
  `--force-return` exist precisely to find these.
- **Asset/format layer.** Whatever Road Rage uses to read its disc data (its own
  filesystem reader / chunk formats) must resolve through the recompiled engine or a
  loader we add. *(Not investigated in M0 — needs the XBE/assets.)*
- **Hand-written overrides.** Some functions (threading gates, main loop, anything the
  lifter cannot resolve) may need `src/recomp_manual.c` entries. Burnout 3's write-up
  is explicit that a "merge, not a swap" of hand code and recompiled code is normal.
- **A game project.** `templates/new-game` must be copied and given the XBE path, entry
  point, game name and generated sources.
- **Two import libs on a non-MSVC workflow:** `xinput`, `d3dcompiler` (solved here, §4.1).

Nothing above is a blocker; all are the documented, normal per-title bring-up work.

---

## 9. Game-specific prerequisites

Not needed for M0 (the synthetic fixture sufficed). For **M1** we will need, from the
user's own legally obtained copy:

1. **`default.xbe`** — required because `xbe_parser`, `disasm`, `func_id`,
   `abi_analysis` and `recomp` all take the XBE directly, and the runtime re-reads it
   at boot to lay out guest memory. Nothing is bundled or downloaded.
2. **The disc's data/asset files** (the game directory) — required only once we reach
   asset loading (M4+), because the recompiled code reads them at runtime.

The XBE alone is enough to begin M1 (parse → disassemble → classify → recompile →
build → boot-to-logged-halt). No file is required *now*.

---

## 10. Technical risks and unresolved questions

1. **Conformance suite not run.** The differential 5,843-vector CPU-vs-lifted-C check
   needs 32-bit MSVC or the Linux/i386 Docker images. Our synthetic execution test
   (§11) is a weaker substitute. **Highest-value way to close this.**
2. **RenderWare / engine identity — unverified.** The docs assume Road Rage is
   RenderWare/Pure3D. **This must be confirmed from the real XBE** (`tools.func_id`
   classifies CRT/RenderWare/vtable signatures; the presence of RW signatures is the
   test). Do not treat the engine as known until then.
3. **Real-XBE ingestion untested.** Only a synthetic XBE (5 leaf functions, no imports,
   no signature, no TLS) went through the pipeline. Real XBEs exercise imports, TLS,
   library sections (`--extra-sections XIPS,DOLBY`), jump tables and thousands of
   functions.
4. **Kernel/ABI fidelity for Road Rage.** 170/371 ordinal bridges are implemented; how
   many Road Rage actually needs, and whether any are among the stubbed ones, is unknown
   until we run it.
5. **D3D8 surface of Road Rage** (fixed-function vs. shaders, render targets, formats) —
   unknown until measured.
6. **Build scale.** Generated C for a retail title is large; the README warns about
   `--split 250` (not 1000) and `/bigobj`. Our Zig build hasn't been exercised at that
   scale.
7. **Disk headroom** is tight (96–99 % full); Budget before any large generation/steps.
8. **`dxguid` / API-coverage subtlety:** `dxguid` happened to link, but interface GUIDs
   the D3D8 layer needs must be present in the toolkit's own headers/lib.

---

## 11. Whether proceeding to M1 is justified

**Yes.** The M0 completion criterion for Outcome A is met and exceeded:

- the recompiler **builds** (all 8 libraries + its own executables);
- its **input/output behaviour is verified** (input = XBE; output = C; CLI confirmed);
- a **minimal reproducible translation test succeeds**: the synthetic XBE was parsed,
  disassembled, classified, ABI-analysed and translated (5/5 functions → 142 lines of C),
  the C **compiles**, and — beyond the minimum — it **executes correctly**
  (9/9 value checks against hand-computed x86 results through the real calling
  convention: args on the simulated stack, return in `g_eax`).

Reproduce the end-to-end test:

```sh
cd third_party/xboxrecomp
D=…/_m0_tmp/xbefix                      # contains default.xbe (from tools/conformance/test.xbe)
python -m tools.xbe_parser  "$D/default.xbe" --json "$D/default_analysis.json"
python -m tools.disasm      "$D/default.xbe" --text-only
python -m tools.func_id     "$D/default.xbe" -v
python -m tools.abi_analysis "$D/default.xbe" -v
python -m tools.recomp      "$D/default.xbe" --all --split 250 --gen-dir "$D/gen"
"…\zig.exe" cc -std=c11 -fno-sanitize=undefined -I "$D/gen" \
    -o "$D/harness.exe" "$D/harness.c" "$D/gen/recomp_0000.c" "$D/gen/recomp_dispatch.c"
"$D/harness.exe"                        # -> HARNESS PASSED (0 failures)
```

```
ok add3   … = 0x00000006      ok cmpsel … = 0x00000005
ok submul … = 0x00000012      ok cmpsel … = 0x00000005
ok shifts … = 0x23456780      ok bits   … = 0x00000001
HARNESS PASSED (0 failures)
```

> **Distinguish carefully:** "the recompiler builds" (✅ all libs) ≠ "translation
> succeeded" (✅ 5/5) ≠ "generated code executes" (✅ 9/9 synthetic). None of this is
> proof that a **real Road Rage title** boots — that is M1.

---

## 12. The single highest-value next step

**Obtain the user's own `default.xbe` and take it through the full pipeline**
(`xbe_parser → disasm → func_id → abi_analysis → recomp`), then build the
`new-game` project and attempt a **boot to a deterministic logged halt**. In the same
pass, use `tools.func_id` output to **verify or refute the RenderWare/Pure3D engine
assumption** and run `tools/doctor.py` to enumerate the real per-title gaps
(unimplemented instructions, unresolved indirect calls, unbridged ordinals).

The only file required from the user is **`default.xbe`** from their legally obtained
copy. It is required because every pipeline stage consumes the XBE directly and the
runtime re-reads it to lay out guest memory.
