# The Simpsons: Road Rage — Native PC Recompilation

Research and engineering effort to **statically recompile** *The Simpsons: Road Rage* (2001,
Radical Entertainment / EA) into a native Windows executable that preserves the original
gameplay, assets, physics, missions, and behavior.

This is **not** a remake, a Unity recreation, or a conventional emulator. It is static
recompilation of the original binary, **targeting the original Xbox release** (x86 → x86-64).

## Status

**Through milestone M6.** The full static-recompilation pipeline is working end to end: the
original Xbox PAL/European release (Title ID `0x45410013`) is parsed, all code sections are
disassembled and function-discovered, and **14,312 functions are translated to C with zero
translation failures** (152 unresolved stubs). The generated code compiles and links into a
native Windows executable that runs the guest runtime.

The game now completes kernel/HAL init, thread creation, file I/O, and RadSound/audio
initialisation, and reaches its main loop. It does **not** yet present a frame
(`NV2A PUT=GET=0`); the current blocker is a wild-pointer crash in a linked-list walker
(`sub_00013020`). See [`docs/M6-RESULTS.md`](docs/M6-RESULTS.md) for the current state and
[`docs/M5-RESULTS.md`](docs/M5-RESULTS.md) for the prior milestone.

> **It does not boot yet.** A successful build or a running process is not a working game.

## Documents

| Document | Contents |
|---|---|
| [`docs/FEASIBILITY.md`](docs/FEASIBILITY.md) | Releases/platforms, per-platform architectures, tooling, recommendation, requirements, **verified vs hypothesis** |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Proposed pipeline and component design |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Milestone plan, starting with the first executable milestone (M1) |
| [`docs/UPSTREAM.md`](docs/UPSTREAM.md) | Upstream repositories and their licenses |
| [`docs/PREREQUISITES.md`](docs/PREREQUISITES.md) | Required software, hardware, and build tools |

## Headline conclusions

- **Achievable:** yes, realistically, on a long horizon — building on
  `sp00nznet/xboxrecomp` (MIT) and the original-Xbox recomp ecosystem.
- **Target platform:** **original Xbox.** It is an x86 machine (Pentium III class), so
  x86 → x86-64 needs no endianness swap or exotic ISA work. PS2 and GameCube are far harder.
- **Reusable tools:** `xboxrecomp` (core, MIT), `MANXFramework` (runtime, GPL-3.0),
  `xita` (reference), `xboxdashboard`/`mm3-recomp` (D3D8→D3D11 renderer references),
  `BaseCrunch/Road-Rage-P3DZ-Decompressor` (MIT, asset loading).
- **Not reusable:** Xbox 360 tooling (`XenonRecomp`) — PowerPC/XEX only, cannot handle an
  original-Xbox x86 XBE.
- **First executable milestone:** a Windows binary that loads the user's own `default.xbe`,
  runs the entry point + CRT init through a minimal kernel/HAL shim, and reaches a
  deterministic logged halt — **no rendering yet**.

## Legal

The runtime is **bring-your-own-disc**: it never contains or downloads copyrighted assets or
executables. Recompilation output derives from a user's legally-owned binary and is treated as
local build output, not committed. This is non-commercial research.
