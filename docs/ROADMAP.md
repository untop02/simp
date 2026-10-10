# Roadmap — Road Rage Native PC Recompilation

Target: **original Xbox** → native Windows x86-64 via static recompilation.
Strategy: prove the pipeline end-to-end on the smallest possible increment before adding
breadth. **No runtime code is written until M0 confirms a viable pipeline.**

Legend: ✅ done · 🟡 in progress · ⬜ not started

---

## M0 — Toolchain & pipeline validation *(research → concrete)*

**Goal:** eliminate the unknowns in `FEASIBILITY.md` §10 before writing any runtime.

Tasks:
- ✅ Cloned/built **`sp00nznet/xboxrecomp`** (v0.13.1, `193e2995`). Emits **C**; **ships a
  full runtime** (8 libraries: kernel, D3D8→D3D11, DirectSound→mixer, APU, NV2A, USB,
  input, video); builds with MSVC *or* free Clang/Zig; indirect calls use a generated flat
  dispatch table (binary-search fallback).
- ✅ Confirmed the **XBE** is the recompiler's direct input (no separate unpack step).
- ✅ Inventoried licenses (see `UPSTREAM.md`): core **MIT**; `src/apu`, `src/nv2a` regs
  **LGPL-2.1+** (xemu-derived).
- ⬜ Acquire a **legally-owned** copy/dump of the Xbox disc — **deferred to M1** (the
  synthetic XBE fixture was sufficient for M0).

**Deliverable:** `docs/M0-RESULTS.md` (supersedes the planned `M0_FINDINGS.md`). Decision:
`xboxrecomp` is viable as-is; no Ghidra-assisted annotation required at this stage.

**Exit criteria (MET):** we know which tool does what, have a named build recipe, and have a
reproducible end-to-end translation of an XBE that compiles **and executes** correctly.

---

## M1 — First executable: load XBE, boot to a deterministic logged halt ⬜

**This is the first executable milestone.**

**Goal:** a Windows binary that:
1. loads the user's own `default.xbe` (XBE parse/unpack),
2. runs the **entry point and CRT initialization** through a minimal kernel/HAL shim,
3. reaches a **deterministic, logged halt** (e.g. a specific known point / import we log),
4. has **no rendering and no asset loading**.

**Why this first:** it proves the x86→C translation is faithful and that the boot path and
memory model are sufficient — the two highest-risk unknowns — without the cost of graphics
or asset work.

Tasks:
- ⬜ `src/xbe` — XBE header/section parser and image loader.
- ⬜ Run `xboxrecomp` on `default.xbe`; integrate generated C.
- ⬜ `src/runtime` — memory/address-space model; stub kernel calls with logging.
- ⬜ `src/host` — WinMain, CLI (`--xbe <path>`), main loop that runs init then halts.
- ⬜ CMake build producing `roadrage.exe`.

**Exit criteria:** running `roadrage.exe --xbe <user copy>` produces a deterministic log
including a recognized boot-phase marker, reproducible across runs.

---

## M2 — Kernel / HAL coverage ⬜

**Goal:** implement the kernel/HAL surface the game actually imports, until init completes
and reaches the point where it would create a D3D device.

- ⬜ Enumerate imported kernel functions from the XBE import table.
- ⬜ Implement file I/O, memory allocation (contiguous/virtual), threads/sync, timing, DbgPrint.
- ⬜ Reference `xita`'s kernel layer (archived; GPL-3.0) for behavior.
- ⬜ Differential-check behavior against `xemu` where useful (emulator = reference oracle).

**Exit criteria:** initialization proceeds past HAL/kernel use up to device creation.

---

## M3 — Rendering: D3D8 device creation + clear screen ⬜

**Goal:** first pixels — create a D3D8-compatible device over D3D11 and clear the screen.

- ⬜ Measure the actual D3D8 surface used by the binary (fixed-function vs shaders, RTs, etc.).
- ⬜ Implement `src/render` D3D8→D3D11 backend (device, swapchain, states, clear).
- ⬜ Reference `xboxdashboard` (D3D8→D3D11) and `mm3-recomp` (D3D11) — license permitting.
- ⬜ Present a cleared frame in a window at the game's target resolution.

**Exit criteria:** window opens, clears to the game-requested color, stable frame loop.

---

## M4 — First Pure3D asset load ⬜

**Goal:** decode and load a real asset from the user's disc.

- ⬜ Integrate P3DZ decompression (`BaseCrunch/Road-Rage-P3DZ-Decompressor`, MIT).
- ⬜ `src/assets` — Pure3D chunk reader for the chunks the game actually uses.
- ⬜ Load one known asset (e.g. a mesh/texture) and verify decoded contents.
- ⬜ Render that asset (or at least validate its decoded structure).

**Exit criteria:** a specific Pure3D asset from the user's disc decodes and renders/uploads
correctly.

---

## M5 — Main menu ⬜

**Goal:** the game's own main menu renders and responds to input.

- ⬜ Complete enough D3D8 state coverage for UI rendering.
- ⬜ Input shim (XInput) drives menu navigation.
- ⬜ Audio device up (DirectSound→XAudio2) for menu music/SFX.

**Exit criteria:** menu navigation works; the game's own UI logic is running unmodified.

---

## M6 — In-game ⬜

**Goal:** start a mission and drive.

- ⬜ Full gameplay render path (world, vehicles, HUD).
- ⬜ Physics/mission/AI logic verified faithful (comes "for free" if translation is faithful).
- ⬜ Save/load, pause, options as reachable.

**Exit criteria:** a mission is playable end-to-end with correct behavior.

---

## M7 — Fidelity & compatibility pass ⬜

- ⬜ Performance work (hot paths, batching in the render backend).
- ⬜ Render-correctness pass (blending, depth, texture formats, shaders).
- ⬜ Audio correctness (streaming, positional audio).
- ⬜ Road Rage map/asset edge cases; verify against `xemu` reference where practical.
- ⬜ Packaging: bring-your-own-disc instructions, no assets bundled.

---

## Immediate next step

Execute **M0**: build and inspect `xboxrecomp`, resolve the toolchain/runtime questions, and
record findings in `docs/M0_FINDINGS.md`. Only then begin M1. This project does **not** write
the game runtime before the pipeline is confirmed.
