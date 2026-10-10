# Prerequisites & Build Tools

Everything required to develop, build, and run the recompilation pipeline.
Items marked *[confirm at M0]* must be verified against `xboxrecomp`'s actual README/build
files — do not assume.

## Required software

| Tool | Purpose | Notes |
|---|---|---|
| **Windows 10/11 x86-64** | Host/target platform | |
| **Clang/LLVM** *or* **MSVC** *or* **Zig (`zig cc`)** | C compiler for the runtime + generated code | **Verified at M0**: `xboxrecomp` builds with a free Clang/Zig toolchain; MSVC is *not* required. MSVC is the documented primary path. |
| **CMake** (3.20+) | Build system | Verified with CMake 4.4.4 |
| **Ninja** | CMake generator (optional but used here) | Verified with Ninja 1.13.2 |
| **Git** | Source control + fetching upstreams | |
| **Python 3.9+** | `xboxrecomp` pipeline + asset tooling | Verified on Python 3.14.4. Pipeline deps: `capstone`, `pytest`, `pefile`. |
| **Ghidra** (with the Xbox loader if available) | Disassembly / control-flow annotation *if* the recompiler needs help | Not required for M0 |
| **IDA Pro (optional)** | Apply RenderWare FLIRT signatures for symbol recovery | `ifarbod/renderware3-flirt` |
| **xemu** (optional) | Emulator used as a **reference oracle** for differential testing | GPL-2.0; not a recompiler |

## Hardware

- A development machine capable of compiling large generated translation units (the
  recompiled game can be large). **16 GB RAM** and a modern multi-core CPU recommended.
- A GPU supporting **Direct3D 11** (the toolkit's render backend target).
- A Windows audio output device (the toolkit's DirectSound layer is a **software mixer** over
  the host audio API — `waveOut`; no XAudio2 SDK needed).

## Legally-obtained input (user-supplied, NOT in repo)

- A **legally owned** copy of *The Simpsons: Road Rage* for the **original Xbox**, and a dump
  of its **`default.xbe`** and disc assets.
- **Never** committed, bundled, or downloaded by tooling.

## Python packages (asset tooling)

- As required by `BaseCrunch/Road-Rage-P3DZ-Decompressor` (verify its requirements file).
- Likely a small set of pure-Python or well-known packages; confirm at M0.

## Build tools for upstream components

- **`xboxrecomp`** — verified build recipe (M0, see `docs/M0-RESULTS.md` §4): CMake + Ninja,
  `-DCMAKE_C_COMPILER=<zig> -DCMAKE_C_COMPILER_ARG1=cc`, plus an archiver
  (`CMAKE_AR=<zig ar wrapper>`) and, on a Zig-only setup, generated import libs for
  `xinput` and `d3dcompiler` (Zig only ships the versioned defs `xinput1_4` /
  `d3dcompiler_47`). MSVC + Windows SDK needs none of those workarounds.
- **Python pipeline deps** — `pip install capstone pytest pefile`.
- **`MANXFramework` / `xita`** — **not required** (the toolkit ships its own runtime); keep
  only as GPL clean-room references.
- **`xemu`** (if used as oracle) — prebuilt binaries; no build needed.

## Optional / nice-to-have

- **RenderDoc** — capture and inspect D3D11 frames from the recompiled renderer.
- **PIX / GPU debugging tools** — for render-backend correctness.
- **PerfView / sampling profilers** — once M7 performance work begins.

## Prerequisite checklist before starting M1

- [x] `xboxrecomp` cloned and buildable on this machine (M0: all 8 libraries + smoke tests).
- [x] Toolchain confirmed: free Clang/Zig works; MSVC optional (see `M0-RESULTS.md` §4).
- [ ] Python asset tooling runnable against a test input (asset work begins at M4).
- [ ] Legally-owned Xbox `default.xbe` available locally (never committed) — **needed for M1**.
- [x] Licenses reviewed (`docs/UPSTREAM.md`) — core is MIT; note the `src/apu` /
      `src/nv2a` **LGPL-2.1+** (xemu) exception.
