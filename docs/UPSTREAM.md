# Upstream Repositories & Licenses

Status of every repository referenced by this project. **A repo with no license file may not
be used as a dependency without explicit permission from its author — it is reference reading
only.**

License statuses below are **as observed on the repository**; verify before relying on any of
them (licenses can change, and several of these repos are very new).

## Core / reusable (recommended dependencies)

| Repository | Purpose | License | Use |
|---|---|---|---|
| `sp00nznet/xboxrecomp` | Full original-Xbox recompilation toolkit: x86→**C** recompiler **plus** the runtime (kernel, D3D8→D3D11, DirectSound→mixer, APU, NV2A, USB, input, video) | **MIT**, except `src/apu/**` + `src/nv2a/nv2a_regs.h` = **LGPL-2.1-or-later** (xemu-derived) | **Core toolchain + runtime** (verified at M0) |
| `BaseCrunch/Road-Rage-P3DZ-Decompressor` | Road Rage Xbox P3DZ Pure3D decompressor (Python, CLI, docs, tests) | **MIT** | **Asset loading** |
| `CrownParkComputing/MANXFramework` | Reusable runtime/host components for original-Xbox recomp apps | **GPL-3.0** | Runtime components (GPL obligations apply) |
| `RetroRecompilations/MANXFramework` | Fork of the above | **GPL-3.0** | Same |

## Reference implementations (read; reuse only if license permits)

| Repository | Purpose | License | Notes |
|---|---|---|---|
| `sp00nznet/xboxdashboard` | Recomp of `xboxdash.xbe` + **D3D8→D3D11 backend** | **(none)** | Proves the render lift path |
| `Xita-Project/xita` | Original-Xbox static recomp: kernel + D3D8 + DirectSound runtime | **GPL-3.0** | **Archived/closed**; reference layer |
| `BirchWoodGod/halo-ce-vita` | Ongoing xita-derived Halo work | verify | Successor to xita's Halo effort |
| `andeecollard/jsrf-recomp` | Jet Set Radio Future → macOS (D3D8 lift) | **MIT** | Precedent |
| `sp00nznet/hl2-recomp` | Half-Life 2 (Xbox 2005) → Windows | **MIT** | Precedent |
| `MattSG/mm3-recomp` | Midtown Madness 3 → Windows x64, D3D11 | **(none)** | Precedent renderer |
| `MatiasRiveraC/SSX-Tricky-PC` | SSX Tricky → native PC | **(none)** | Precedent |
| `jv36/fifastreet2-recomp` | FIFA Street 2 (Ghidra + xboxrecomp) | **(none)** | Precedent; shows Ghidra-assisted flow |
| `aknavj/scghost-recomp` | StarCraft: Ghost Xbox exe | **(none)** | Precedent |
| `TheSaltTrader/DEF-Jam-Fight-for-New-York---An-original-Xbox-recompilation` | DEF JAM FFNY recomp | **MIT** | Precedent |
| `TheSaltTrader/Hulk-...` | Hulk recomp | **MIT** | Precedent |
| `portingpete/Black-2006-Recomp` | Black (2006) recomp | **MIT** | Precedent |
| `SirSymo/SM2-Recomp` | Spider-Man 2 recomp | **Other** | Precedent |
| `GTTeancum/OpenXML1xbox` | X-Men Legends, D3D8 target | **(none)** | Precedent |

## RenderWare / Pure3D reverse-engineering aids

| Repository | Purpose | License | Notes |
|---|---|---|---|
| `ifarbod/renderware3-flirt` | IDA **FLIRT signatures for RenderWare 3.x** | **(none)** | Symbol recovery in the binary |
| `eonflux7/csf-editor` | RenderWare asset viewer/RE toolkit | **MIT** | Format reference |
| `qxlies/satk-gta` | GTA SA RenderWare RE toolkit | **MIT** | Format reference |

## Emulator (oracle for differential testing, not a recompiler)

| Repository | Purpose | License | Notes |
|---|---|---|---|
| `xemu-project/xemu` | Original-Xbox emulator (QEMU fork) | **GPL-2.0** (+ others) | Authoritative hardware/kernel reference; **not** a recompiler |

## Not applicable (documented so we don't waste time)

| Repository | Why not |
|---|---|
| `hedge-dev/XenonRecomp` | **Xbox 360** XEX / PowerPC-VMX only. Cannot recompile an original-Xbox x86 XBE. |
| `Mr-Wiseguy/N64Recomp` | MIPS / N64 / RSP specific. Not applicable. |
| `sp00nznet/gcrecomp` | GameCube static-recomp toolkit. Only relevant if we retarget GameCube. |
| `aharonahdoot/RecompCore`, `aharonahdoot/GXRuntime` | GameCube (Dolphin-derived) static-recomp components. |
| `BlackLineInteractive/NWiiRecomp`, `dougchansan/GekkoCTR`, `jackpoison-prog/RingOut`, `ant0-blase/*-GC-RECOMP` | GameCube recomp efforts. Not applicable to Xbox target. |

## Road Rage–specific (assessed, mostly unusable)

| Repository | Assessment |
|---|---|
| `Cwf1997/thesimpsonsroadrage` | Described as a Road Rage Xbox **decompilation**, MIT — but **~1 KB, no meaningful commits; effectively empty.** Do not rely on it. |
| `Superposition28/TheSimpsonsRoadRage`, `…-PS2` | No usable content. |
| `JacobEGarcia/springfield-road-rage` | Unrelated JS fan game. |

**No existing Road Rage recompilation project exists.**

---

## License-compatibility notes

- `xboxrecomp` (MIT) and `Road-Rage-P3DZ-Decompressor` (MIT) are permissive — safe to build
  on, with attribution. **Caveat:** `xboxrecomp`'s `src/apu/` and `src/nv2a/nv2a_regs.h` are
  **LGPL-2.1-or-later** (extracted from xemu). Linking them from MIT/proprietary code is
  permitted provided the LGPL notices are retained; modifications to those files stay LGPL.
  Decide deliberately whether to keep or replace the APU/NV2A register files.
- Since `xboxrecomp` ships its own runtime, `MANXFramework` / `xita` are **not needed as
  dependencies**; keep them as GPL clean-room references only.
- `MANXFramework` and `xita` are **GPL-3.0** — using their code makes the resulting project
  subject to GPL-3.0 obligations. Decide deliberately whether the runtime layer is GPL or
  whether these are used as **references only** (clean-room reimplementation).
- Repos marked **(none)** have no license file: **all rights reserved by default**. Reading
  them for understanding is fine; **copying code is not** without permission.
- Recommendation: keep the project's own code permissively licensed (e.g. MIT) and reimplement
  the runtime layer cleanly, referencing GPL/unlicensed projects for guidance.
