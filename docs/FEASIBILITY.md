# Feasibility Report — Native PC Recompilation of *The Simpsons: Road Rage* (2001)

Status: **Research / pre-implementation**
Scope: determine whether the original game can be **statically recompiled** into a native
Windows executable that preserves original gameplay, assets, physics, missions and behavior.

> This report distinguishes **Verified** claims (checked against live repositories,
> documentation, or other primary/authoritative sources) from **Hypothesis** (reasoned
> inference not yet confirmed). Nothing in this document should be treated as a supported
> feature of a tool unless it is marked Verified.

---

## 1. Executive summary

**Realistically achievable: yes, with caveats and a long horizon — and the original Xbox
release is the only sensible target.**

The single most important technical fact: the **original Xbox is an x86 machine** (Intel
Pentium III / Coppermine-class CPU), not PowerPC. Its executables are **XBE** files containing
x86 machine code. Recompiling x86 → native x86-64 is dramatically easier than any other path
here because it needs no endianness swap, no vector-unit emulation, and no exotic ISA
semantics.

There is a **mature, MIT-licensed, actively developed static recompiler for original Xbox
binaries** (`sp00nznet/xboxrecomp`) and a **growing set of shipped precedent projects** built
on it, including at least one with a **D3D8 → D3D11 rendering backend**. This is the pipeline
we should build on.

**Recommendation: target the original Xbox version.** PS2 (MIPS R5900 + VU0/VU1 + GS) and
GameCube (PowerPC Gekko + GX, big-endian) are both substantially harder and have no
Road Rage–specific starting point.

**First executable milestone:** a Windows binary that loads the user's legally-owned
`default.xbe`, translates and executes the entry point and CRT initialization through a
minimal kernel/HAL shim, and reaches a **deterministic, logged halt** — with **no rendering**.
This proves the x86→C translation and the boot path before any graphics or asset work.

---

## 2. Original releases and platforms

**Verified** (developer/publisher/date facts are well-documented):

| Platform | Executable format | CPU architecture | Graphics API | Audio | Executable/format notes |
|---|---|---|---|---|---|
| **Sony PlayStation 2** | ELF (`.elf`/`.irx` modules) | MIPS R5900 "EE" (little-endian) + R3000 IOP; VU0/VU1 vector units | Sony GS (Graphics Synthesizer), via libgraphics/paths | SPU2 + `libsd` | Shipped Nov 19, 2001 |
| **Microsoft Xbox (original)** | **XBE** | **x86 (Intel Pentium III / Coppermine-class)**, little-endian | **Direct3D 8** | **DirectSound** | Shipped Dec 2001; ~64 MB RAM |
| **Nintendo GameCube** | DOL | **PowerPC "Gekko" (big-endian)** | GX | AX / musyx | Shipped Dec 2001 |

Other releases:
- **Game Boy Advance** version exists (a different, 2D game). **Out of scope.**

**Verified**: Developed by **Radical Entertainment**, published by **Electronic Arts**. The
game is a *Crazy Taxi* clone; Sega sued over the similarity and the matter was settled
privately.

**Corrected in M1 — engine identity was wrong.** The Xbox executable is **not
RenderWare**. `tools.func_id` found **0 RenderWare identifiers**, and the XBE links
`XAPILIB / D3D8 / XBOXKRNL / LIBC / XGRAPHC` with `D3D`, `DSOUND`, `BINK*`, `XGRPH`,
`XPP`, `DOLBY` sections — a **direct-XDK Direct3D 8** title built from an in-house
toolchain (debug path `…\srrpal\code\build\xbox\Release\simpsons.exe`). See
`docs/M1-RESULTS.md` §8.

> The earlier sentence here claimed RenderWare + **Pure3D/P3D(P3DZ)** assets as
> *Verified*. The RenderWare half was wrong and is refuted. The **Pure3D half is now
> confirmed by M2**: the engine logs PDDI errors (`NewRenderContext() failed`,
> `Cannot initialize PDDI library …`), and PDDI is Pure3D's Device Driver Interface
> (see `docs/M2-RESULTS.md` §8). What remains open is the **asset container** format:
> the disc's assets live in `.rcf` archives under `art/` and `sound/`, and only
> `default.xbe` has been extracted so far, so the contents of those archives are
> still unexamined.

---

## 3. Per-platform dependency & dependency-surface summary

Every version must be evaluated on four axes: **CPU translation**, **platform APIs**,
**rendering**, and **audio**. The host target is assumed to be **Windows x86-64**.

### 3.1 Xbox (original) — the recommended path

- **CPU translation:** x86 → x86-64. Little-endian → little-endian. No ISA translation
  semantics to invent. The main work is code discovery (function boundaries), handling of
  indirect calls/jump tables, and self-modifying/dynamically-generated code if any.
- **Platform APIs:** small, well-documented kernel/HAL surface (Xbe/Xe file I/O, memory
  virtual/commit, threads, timing, input via XInput-style XDK calls). Emulator source
  (`xemu`) documents expected behavior; a static-recomp runtime reference exists (`xita`).
- **Rendering:** Direct3D 8. D3D8 is close in shape to D3D9/D3D11 (device, resources,
  state blocks). A D3D8→D3D11 backend has already been demonstrated in a shipped
  recomp project (`xboxdashboard`).
- **Audio:** DirectSound (buffer creation, play/stop, pan/volume). Liftable to XAudio2 or
  a DirectSound shim.

### 3.2 PlayStation 2

- **CPU translation:** MIPS R5900 + two vector units (VU0/VU1) + R3000 IOP. Requires a real
  MIPS recompiler plus VU microcode handling — extremely high effort and largely unexplored
  for static recompilation.
- **Rendering:** GS is a fixed-function, unusual pipeline (no z-buffer in the modern sense,
  display lists, `GIF` packets). No proven static-recomp lift path.
- **Audio:** SPU2.
- **Verdict:** Research-grade effort with no reusable Road Rage tooling. **Not recommended.**

### 3.3 GameCube

- **CPU translation:** PowerPC Gekko (big-endian). A static-recomp toolkit exists
  (`sp00nznet/gcrecomp`) and other GameCube static-recomp efforts exist, but Road Rage has
  no GameCube-specific starting point.
- **Rendering:** GX (fixed-function-ish; TEV stages). Lift path needs proving.
- **Audio:** AX / musyx.
- **Verdict:** Possible in principle; more endianness/ISA friction than Xbox and no
  Road Rage precedent. **Second choice at best.**

---

## 4. Existing recompilation frameworks — what can actually be reused

**Verified via repository metadata and READMEs.**

### 4.1 Primary toolchain — original Xbox

- **`sp00nznet/xboxrecomp`** — **MIT**. Static recompiler that turns an Xbox game binary
  into a native host executable ("No emulation. No interpreter."). Actively developed.
  **This is the core reusable component.**
- **`sp00nznet/xboxdashboard`** — static recomp of `xboxdash.xbe` (x86 → C) with a
  **D3D8 → D3D11 backend**. Proves the rendering lift path. *(No license file present —
  treat as reference, not a dependency, until clarified.)*

### 4.2 Runtime / host components

- **`CrownParkComputing/MANXFramework`** (**GPL-3.0**) and its fork
  **`RetroRecompilations/MANXFramework`** — reusable runtime/host components for original-Xbox
  recomp applications. Related titles: `MANXBurnout3`, `MANXFlatOut1`, `MANXLARush`.
- **`Xita-Project/xita`** (**GPL-3.0**) — static recompilation of original Xbox games
  (x86 → C) including an **Xbox kernel, D3D8, and DirectSound runtime layer** (targeted PS
  Vita). Marked **closed/archived**; Halo work continues at `BirchWoodGod/halo-ce-vita`.
  Use as a **reference implementation** of the kernel/D3D8/DirectSound layer, not a live
  dependency.

### 4.3 Shipping precedent (original Xbox → native, on `xboxrecomp`)

Cite as **precedent and study material**, not as mature dependencies — several are days to
weeks old with low star counts and no license.

- `andeecollard/jsrf-recomp` — Jet Set Radio Future → native macOS, D3D8 lift (MIT).
- `sp00nznet/hl2-recomp` — Half-Life 2 (Xbox 2005) → native Windows (MIT).
- `MattSG/mm3-recomp` — Midtown Madness 3 → native Windows x64 with **D3D11 renderer**
  (no license file).
- `MatiasRiveraC/SSX-Tricky-PC` — SSX Tricky → native PC (no license file).
- `jv36/fifastreet2-recomp` — FIFA Street 2 via **Ghidra + xboxrecomp** (no license file).
- `aknavj/scghost-recomp` — StarCraft: Ghost Xbox exe via XboxRecomp (no license file).
- `TheSaltTrader/DEF-Jam-Fight-for-New-York…` (MIT), `TheSaltTrader/Hulk-…` (MIT),
  `portingpete/Black-2006-Recomp` (MIT), `SirSymo/SM2-Recomp` (other), 
  `GTTeancum/OpenXML1xbox` (X-Men Legends, D3D8 target, no license file).

### 4.4 Road Rage–specific prior art

- **`BaseCrunch/Road-Rage-P3DZ-Decompressor`** — **MIT**, Python. Standalone decompressor
  for **Road Rage Xbox P3DZ-compressed Pure3D files**, with CLI, drag-and-drop Windows
  support, format documentation, validation, and tests. **Directly relevant to asset loading.**
- **`Cwf1997/thesimpsonsroadrage`** — MIT, described as "a decompilation project of The
  Simpsons: Road Rage for the Xbox." **Created Dec 2025, ~1 KB, no meaningful commits —
  effectively an empty stub. Do NOT rely on it.**
- `Superposition28/TheSimpsonsRoadRage` and `…-PS2` — no usable content.
- `JacobEGarcia/springfield-road-rage` — unrelated JavaScript fan game.

**Verified conclusion: no existing Road Rage recompilation project exists.**

### 4.5 RenderWare reverse-engineering aids

- `ifarbod/renderware3-flirt` — IDA **FLIRT signatures for RenderWare 3.x**, useful for
  recovering RW symbol boundaries in the binary. *(No license file.)*
- `eonflux7/csf-editor` (**MIT**) and `qxlies/satk-gta` (**MIT**) — RenderWare RE toolkits
  aimed at other RW titles; useful format references.

---

## 5. Can Xbox **360** recompilation tooling be reused? — **No.**

**Verified, from the XenonRecomp README:** `hedge-dev/XenonRecomp` (MIT, ~6.5k stars) is
specific to **Xbox 360 XEX executables**, which are **PowerPC/VMX, big-endian**. It:

- relies on **`.pdata`** segment metadata that XBE has no equivalent of;
- emits **VMX intrinsics**;
- reconstructs **`__restgprlr_14`-style** save/restore functions;
- supports **XEXP title updates** and Xbox-360-specific structures.

**None of this applies to an original-Xbox x86 XBE.** Likewise `Mr-Wiseguy/N64Recomp` is
MIPS/N64/RSP-specific and not applicable.

So the Xbox 360 ecosystem is **not** a reusable path; the correct reuse target is the
**original-Xbox** recompiler (`xboxrecomp`) plus its runtime ecosystem.

GameCube static-recomp tooling exists (`sp00nznet/gcrecomp`, `aharonahdoot/RecompCore`,
`aharonahdoot/GXRuntime`, `BlackLineInteractive/NWiiRecomp`, `dougchansan/GekkoCTR`,
`jackpoison-prog/RingOut`, various `ant0-blase/*-GC-RECOMP`) and would be the basis of a
GameCube attempt — but it is not relevant to the Xbox target and has no Road Rage precedent.

---

## 6. Platform comparison & recommendation

| Criterion | Xbox (original) | PlayStation 2 | GameCube |
|---|---|---|---|
| ISA difficulty (→ x86-64) | **Lowest** (x86, LE) | Very high (MIPS + VU0/VU1) | High (PPC, BE) |
| Existing static recompiler | **Yes, MIT, active** | No comparable tool | Yes, but no RR precedent |
| Rendering lift proven | **Yes (D3D8→D3D11)** | No | Partially |
| Audio lift | DirectSound → XAudio2 | SPU2 | AX |
| RR-specific asset tooling | **Yes (P3DZ decompressor)** | No | No |
| RR-specific decomp progress | Stub only | None | None |

**Recommendation: original Xbox.**

Rationale: (1) x86 → x86-64 is the easiest possible translation; (2) a mature MIT recompiler
already exists and has shipped multiple titles; (3) the D3D8 lift path is proven by
`xboxdashboard`/`mm3-recomp`; (4) Road Rage–specific Pure3D/P3DZ asset tooling exists;
(5) PS2 and GameCube are each substantially harder with no Road Rage starting point.

---

## 7. Minimum requirements for translation → native code

The following are the **minimum** work items to turn the Xbox `default.xbe` into a native
Windows program. Some are handled by `xboxrecomp`; the rest are the project's own
responsibility. *(Which items `xboxrecomp` handles automatically must be confirmed against
its source before we commit to a build plan — see the open questions in §10.)*

1. **XBE parsing / unpacking.** Read the XBE header, sections, entry point. Handle any
   compression/encryption on the executable image.
2. **CPU translation (x86 → C/C++, recompiled to x86-64).** Emit C for each basic block /
   function; resolve function boundaries and indirect control flow (vtables, jump tables,
   function pointers). Handle `call [eax+off]` idiom and similar.
3. **Memory model.** Provide an address-space that preserves the Xbox's expected layout well
   enough for absolute addresses and pointer arithmetic to work. Decide between a 32-bit-ish
   shadow space vs. remapping to host memory with a compatibility layer.
4. **Kernel / HAL shim.** Implement the Xbox kernel export surface the game actually calls:
   file I/O (`Xe*`/`Nt*` file APIs), memory (`MmAllocateContiguousMemory`, `VirtualAlloc`
   equivalents), threads/synchronization, timing (`KeQuery…`, performance counters), and
   `DbgPrint`. Reference `xita`.
5. **Input.** Map Xbox controller reads to XInput / keyboard+mouse, preserving semantics.
6. **Rendering — D3D8.** Either implement D3D8 on top of D3D11/12 or forward to a thin D3D8
   shim. Reference `xboxdashboard`'s D3D8→D3D11 backend and `mm3-recomp`.
7. **Audio — DirectSound.** Implement DirectSound buffer semantics over XAudio2 (or a
   DirectSound passthrough on Windows).
8. **Asset loading.** Read the game's Pure3D/P3D files, including **P3DZ** compression, from
   the user's legally-obtained disc image/dump. Reference
   `BaseCrunch/Road-Rage-P3DZ-Decompressor`.
9. **Bring-your-own-disc design.** Never ship or fetch copyrighted assets; the runtime loads
   assets from a user-supplied disc dump only.

---

## 8. Legal / ethical constraints (binding for this project)

- **Do not download, bundle, mirror, or redistribute copyrighted game assets or executables.**
- The runtime is **bring-your-own-disc**: it operates on a dump the user already legally owns.
- Recompilation is a transformative engineering act on a user's own copy; this project is
  **non-commercial research**. Keep it that way unless counsel says otherwise.
- Reused third-party code must be **license-compatible**. Repos with **no license file** may
  not be used as dependencies without permission — they are reference reading only.
  (See `UPSTREAM.md` for the license status of every cited repo.)

---

## 9. Verified vs. Hypothesis

### Verified
- Xbox original = x86 (Pentium III class), XBE format, Direct3D 8, DirectSound.
- PS2 = MIPS R5900 + VU0/VU1 + GS + SPU2; GameCube = PowerPC Gekko + GX + AX.
- `xboxrecomp` exists, is MIT, is actively developed, and is an original-Xbox static
  recompiler.
- `xboxdashboard` demonstrates a D3D8→D3D11 backend on that recompiler.
- `xboxrecomp` ships its **own** original-Xbox runtime — 8 libraries (kernel, D3D8→D3D11,
  DirectSound→mixer, MCPX APU, NV2A, USB, input, video) — and emits **C**. Verified in M0 by
  building and running it end-to-end (`M0-RESULTS.md`); this supersedes the need for
  `xita`/`MANXFramework` as runtime dependencies.
- `xita` implements an Xbox kernel + D3D8 + DirectSound runtime layer (archived) — now only a
  cross-reference oracle, not required.
- `MANXFramework` (GPL-3.0) provides reusable original-Xbox runtime/host components.
- Multiple original-Xbox games have shipped as native recompilations (JSFR, HL2, MM3, …).
- `BaseCrunch/Road-Rage-P3DZ-Decompressor` decompresses Road Rage Xbox P3DZ Pure3D files.
- `Cwf1997/thesimpsonsroadrage` is an empty stub (no meaningful commits).
- **XenonRecomp is PPC/XEX-only and cannot recompile an original-Xbox XBE.**
- `xemu` is an original-Xbox emulator (QEMU-derived), not a recompiler.

### Hypotheses (to validate during the proof-of-feasibility milestone)
- `xboxrecomp` sufficiently handles Road Rage's control-flow patterns (jump tables, indirect
  calls, vtables) without heroic manual intervention.
- The Xbox build's D3D8 usage is within the subset `xboxdashboard`-style backends support.
- The DirectSound usage is simple enough to map cleanly to XAudio2.
- The game's game-code (physics, missions, AI) is largely CPU-side and therefore preserved
  "for free" by faithful recompilation — i.e. there is no hidden dependence on Xbox-specific
  hardware behavior that alters gameplay.
- Pure3D/P3DZ assets can be read and fed to the recompiled engine without needing to
  reimplement the whole RenderWare runtime.
- Road Rage's RenderWare version is within the range covered by existing RW FLIRT tooling.

### Explicitly not claimed
- That any specific tool "supports Road Rage." No tool claims that.
- That this will be quick. Multi-title precedent took sustained effort.
- That assets can be shipped. They cannot.

---

## 10. Open questions to resolve before writing any runtime code

1. ~~**What exactly does `xboxrecomp` emit and require?**~~ **Answered in M0**
   (`M0-RESULTS.md`): it emits **C**, and it **does** supply the runtime — eight libraries
   (`kernel`, `d3d8`, `dsound`, `apu`, `nv2a`, `usb`, `input`, `video`). The documented
   toolchain is MSVC; a free Clang/Zig toolchain was verified to build everything.
   *(The earlier "expect it does not supply the runtime, like XenonRecomp" guess was wrong.)*
2. **Licenses:** Can `xboxdashboard`/`mm3-recomp`/`SSX-Tricky-PC` code be used, or are they
   read-only references (no license file)? Confirm with authors if we intend to reuse code.
3. **Which RW/Pure3D versions** do the Xbox assets use, and does the P3DZ decompressor cover
   all chunks Road Rage uses?
4. **D3D8 surface** actually exercised by the game (shaders? fixed-function only? render
   targets?) — measure from the binary before choosing the backend.
5. **DirectSound surface** — static buffers vs. streaming, 3D positional audio.

These are answered by the proof-of-feasibility milestone in `ROADMAP.md`, not before it.

---

## 11. Bottom line

- **Achievable?** Yes — realistically, on a long horizon, **if** we target the Xbox version
  and build on `xboxrecomp` + the original-Xbox runtime ecosystem.
- **Target platform?** **Original Xbox.**
- **Reusable tools?** `xboxrecomp` (MIT, core), `MANXFramework` (GPL-3.0, runtime),
  `xita` (reference runtime layer), `xboxdashboard`/`mm3-recomp` (renderer references),
  `BaseCrunch/Road-Rage-P3DZ-Decompressor` (MIT, assets), RenderWare FLIRT (symbol recovery).
- **First executable milestone?** A Windows binary that loads the user's own `default.xbe`,
  recompiles/executes the entry point + CRT init through a minimal kernel/HAL shim, and hits
  a deterministic logged halt — **no rendering**. This proves the translation and boot path.
- **Not reused:** Xbox 360 tooling (XenonRecomp) — wrong architecture and executable format.

See `ARCHITECTURE.md` for the proposed pipeline and `ROADMAP.md` for the milestone plan.
