# MAC-MIGRATION — Apple Silicon Development Handoff

Status: **BLOCKED — environment mismatch + empty upstream repository**
Author: continuation session (automated)
Date: 2026-10-10

This document reports the state of the project after an attempt to continue
development on an Apple Silicon MacBook M1. **It does not contain macOS results,
because no macOS environment was reachable from this session.** Every claim below
is either verified by a command run in this session or explicitly labelled as
unverified.

---

## 0. Executive summary (read this first)

Two blocking facts were verified before any migration work could begin:

1. **This session is running on the Windows PC, not on macOS.** The terminal
   identifies as `MINGW64_NT-10.0-26200 ... x86_64 Msys` with `OS=Windows_NT`;
   `sw_vers` (the macOS version tool) is absent. The working directory is
   `/d/simpsons recomp` (i.e. `D:\simpsons recomp`).
2. **The GitHub repository `untop02/simp` is empty and contains none of the
   M1–M5 work.** `git ls-remote` returns no refs; the GitHub API reports
   `"size": 0`. Locally, branch `master` **has no commits at all** — the entire
   project tree is untracked or git-ignored.

Consequently:
- No macOS-specific result can be produced from here without a real Mac
  environment (or a copy of this tree placed on one).
- Cloning `https://github.com/untop02/simp` on the Mac would yield an **empty
  tree** — the previously documented M1–M5 state would NOT be recovered.

What this session *did* establish (all verified): the local Windows tree is
intact, the pinned toolkit is unchanged, and the upstream toolkit has genuine
POSIX/macOS support that makes the Mac route more viable than the earlier
handoff assumed. Details in §3–§7.

---

## 1. Repository URL, branch, and starting commit

| Item | Value | How verified |
|---|---|---|
| GitHub URL | `https://github.com/untop02/simp` | `git ls-remote` / GitHub API |
| GitHub state | **EMPTY** — no branches, no tags, no commits, `size: 0` | `git ls-remote … ; echo $?` → `0` with **no output**; API `size:0`, `created_at 2026-10-09T21:03:27Z` |
| Network sanity check | Works (control `git ls-remote github.com/git/git HEAD` returned a SHA) | same command |
| Local branch | `master` | `git status` |
| Local commits | **none** (`your current branch 'master' does not have any commits yet`) | `git log` |
| Local remote | **none configured** | `git remote -v` (empty) |
| Pinned toolkit | `third_party/xboxrecomp` @ `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` (tag `v0.13.1`) | `git rev-parse HEAD`, `git describe --tags` |
| Toolkit cleanliness | **clean** (`git status --porcelain` empty) | same |

> **Implication:** the Windows work was never pushed. A plain `git clone` on the
> Mac recovers nothing. The git-ignored tree (`game/`, `logs/`,
> `third_party/`, and the ISO) must be transferred out-of-band.

---

## 2. Which M1–M5 artifacts are present or missing

**Present** in this local Windows workspace (but **untracked / git-ignored**, so
absent from GitHub):

| Artifact | Location | Size / count | Git status |
|---|---|---|---|
| Research + milestone reports | `docs/{FEASIBILITY,ARCHITECTURE,ROADMAP,UPSTREAM,PREREQUISITES,M0..M5}-RESULTS.md` | — | **untracked** (never committed) |
| README | `README.md` | 2.5 KB | untracked |
| Helper scripts | `scripts/*.py`, `scripts/m1_analyze.sh` | 15 files | untracked |
| Ignore rules | `.gitignore` | — | untracked |
| Pinned toolkit | `third_party/xboxrecomp` | 158 MB (with the isolated `_m4_xboxrecomp`, `_m0_toolchain`) | **git-ignored** (`/third_party/`) |
| Generated recompiled C | `game/The Simpsons Road Rage/src/recomp/gen/` | 58 files, **47 MB** | **git-ignored** (`src/recomp/gen/`) |
| Built executable | `game/The Simpsons Road Rage/build/srr_recomp.exe` | ~59.7 MB (build tree 220 MB) | **git-ignored** (`*.exe`, `/build/`) |
| Extracted disc tree | `game/The Simpsons Road Rage/` | 48 files, 373,833,571 B total tree 623 MB | **git-ignored** (`/game/`) |
| Original ISO | `Simpsons, The - Road Rage (Europe) (En,Fr,De).iso` | 374,472,704 B | **git-ignored** (`*.iso`) |

**Missing from GitHub:** all of the above. **Nothing is missing from the local
Windows tree** that M1–M5 required.

**Missing on this session's host (cannot be determined here):** the macOS
version, CPU architecture, toolchain versions, and whether the project tree
exists on the Mac at all. See §3.

---

## 3. Detected macOS version, architecture, and toolchain

**Not detectable from this session.** This session runs on Windows; the macOS
host was not reachable. To fill this section in, run the following *on the Mac*
and record the output:

```bash
uname -a
uname -m                       # expect arm64
sw_vers                        # macOS version
sysctl -n machdep.cpu.brand_string
xcode-select -p                # Command Line Tools present?
clang --version                # Apple Clang
git --version
python3 --version              # expect 3.10+
python3 -c "import capstone; print('capstone', capstone.__version__)"  # expect 5.x
cmake --version                # 3.20+
ninja --version
df -h .                        # free space (toolkit + tree + ISO ≈ 1.4 GB)
```

Do **not** treat any of the above as verified until it has actually been run on
the Mac. This section is intentionally left as instructions rather than results.

---

## 4. Which analysis / build stages work natively on Apple Silicon

Assessment derived by inspecting the pinned toolkit source and CMake (verified
in this session), not by running anything on macOS.

| # | Stage | Mac feasibility | Evidence |
|---|---|---|---|
| 1 | XISO extraction / verification | **Native** | `tools/xiso` is pure Python; `scripts/m5_verify_extract.py` pure Python |
| 2 | XBE parsing / analysis | **Native** | `tools/xbe_parser` pure Python; existing `default_analysis.json` |
| 3 | Disassembly + function discovery | **Native** | `tools/disasm`, `tools/func_id` — Python + `capstone` only |
| 4 | ABI / calling-convention analysis | **Native** | `tools/abi_analysis` — Python + `capstone` |
| 5 | Recompile guest → C | **Native** | `tools/recomp` — Python; emits `.c` + headers |
| 6 | Compile/link generated C into an EXE | **Needs adjustment** | Generated C is portable, but the project `CMakeLists.txt` is Windows-bound (§5) |
| 7 | Execute the guest | **Substantial porting risk** | Runtime libs are split WIN32/POSIX, but the POSIX GL backend is a "FIRST cut" (§5) |
| 8 | Graphics init + frame present | **Substantial porting risk** | Same; the title exercises features the GL backend lists as not-yet-done (§5) |

**Practical read:** stages 1–5 — the entire *analysis and translation* half — run
natively on macOS ARM64 with only Python 3 + `capstone`. Stages 6–8 are where
platform work is required.

---

## 5. Which components require Windows or substantial porting

This is where the earlier handoff can now be **corrected with evidence**.

### 5.1 Upstream toolkit DOES have a POSIX/OpenGL path

Verified from the pinned source:

- `src/d3d/CMakeLists.txt` splits on `if(WIN32)`:
  - Windows → `d3d8_device.c`, `d3d8_shaders.c`, `d3d8_combiners.c`, … linking
    `d3d11 dxgi dxguid d3dcompiler`.
  - **POSIX → `d3d8_gl.c`**, linking `SDL2::SDL2` and `libepoxy` via
    `pkg_check_modules(EPOXY REQUIRED epoxy)`.
- `src/d3d/d3d8_gl.c` header: *"OpenGL 3.3 backend for the D3D8 compat layer …
  The CMake split picks this file on POSIX."* It states it is the **first cut**,
  with these explicitly listed as **not yet done**: real texture-format mapping,
  FVF input layouts beyond position/diffuse/UV, **Xbox programmable vertex
  shader bytecode → GLSL**, and **register-combiner pixel programs → GLSL**.
- `src/platform/CMakeLists.txt`: on non-Windows builds a real static library
  `platform` from `win32_compat.c` (POSIX implementations of Win32 primitives).
  `win32_compat.c` contains **9 `__APPLE__` guards** — i.e. real Darwin code
  (Mach VM stats, `P_TRACED`, `memset_s`, `anon_map_fd`, waitable timers, etc.),
  matching the README's *"The Darwin `TODO`s became implementations"* changelog.
- `tools/macos/setup.sh` is upstream's supported macOS entry point. It installs
  `sdl2 libepoxy` via Homebrew ("the OpenGL video backend links against" them),
  creates a `.venv` with `capstone pytest pefile numpy`, installs a `py` shim,
  and (optionally, `--test`) builds three Docker images for the conformance
  suite. It states the suite then *"runs exactly as it does on Windows."*

> **Correction to prior assumption:** the runtime is **not** uniformly
> Win32/D3D11-only. It is conditionally compiled, with a POSIX OpenGL backend
> and a Darwin compatibility layer already present upstream.

### 5.2 But the game project side is currently Windows-bound

Verified from `game/The Simpsons Road Rage/CMakeLists.txt`:

- Line 33: **hard-coded** `set(XBOXRECOMP_DIR "D:/simpsons recomp/third_party/xboxrecomp" …)`.
- Line 66: `add_executable(${PROJECT_NAME} WIN32 …)`.
- Lines 87–96: links Windows-only libraries `d3d11 dxgi dxguid xinput winmm dbghelp`.
- `src/main.c` uses `WinMain`, `MessageBox`, `GetModuleHandle`, and a
  dbghelp-based fault handler (per M5). The upstream template
  `templates/new-game/CMakeLists.txt` has the same `WIN32` + `d3d11` shape.

So even though *upstream* can build for POSIX, **this game project's harness is
not yet portable.** Making stages 6–8 run on macOS would require:
1. De-Windows-ing the project `CMakeLists.txt` (relative `XBOXRECOMP_DIR`,
   drop the `WIN32` executable flag and the Windows SDK link list, add a POSIX
   branch).
2. Porting/replacing the project-side `main.c` boot harness (console/entry
   point, fault handler) — upstream's POSIX path exists but the project's copy
   is Windows-specific.
3. Depending on the upstream POSIX GL backend to be complete enough for a
   RenderWare/Pure3D title — which §5.1 shows it currently is **not** (VSH
   bytecode and register combiners are listed as unfinished, and those are
   exactly what a RenderWare title uses).

### 5.3 Apple Silicon Windows-VM caveat (unchanged)

Virtualization on Apple Silicon (Parallels / UTM / VMware Fusion) does not
expose a real GPU, so D3D11 would need a translation layer with unproven
compatibility and performance. **Do not assume a Windows VM is a drop-in
execution target** for the current D3D11 runtime.

### 5.4 Recommended division of work

- **Mac (native, low risk):** stages 1–5, all static analysis, the registry-index
  investigation, source edits, portable regression tests, git history,
  reproducible patches.
- **Windows PC (no GPU translation risk):** stages 6–8 dynamic execution and
  frame bring-up, using the existing D3D11 runtime and debug tooling.
- **Optional later:** complete the upstream POSIX GL backend so the title can run
  natively on the Mac. This is a real project, not a migration step — treat it
  as such and only after the guest reaches graphics submission on Windows.

---

## 6. Required assets and whether they are available

| Asset | Available? | Location | Notes |
|---|---|---|---|
| Original Xbox PAL `default.xbe` | **Yes (local Windows only)** | `game/The Simpsons Road Rage/default.xbe` (2,187,264 B) | git-ignored; must be transferred to the Mac out-of-band |
| Full extracted disc tree (48 files) | **Yes (local Windows only)** | `game/The Simpsons Road Rage/` | git-ignored; not on GitHub |
| Original ISO (Europe En/Fr/De) | **Yes (local Windows only)** | repo root, 374,472,704 B | git-ignored; `*.iso` |
| Anything on GitHub | **No** | — | repo empty |

No assets were downloaded or fabricated. **Do not commit the ISO, XBE, or the
extracted game data.** If the Mac needs them, copy them from the PC manually
(same files, verified by size in M5).

---

## 7. Current status of the registry-index investigation

This continues the M5 blocker. Findings below are as recorded in
`docs/M5-RESULTS.md` and were re-checked against the generated sources in this
session. **The root cause is localised but NOT fixed.**

- Crash: `fault addr = 0xCF3C41FF`.
- Faulting guest instruction is in `sub_00119140` (`recomp_0030.c:5323`,
  `edx = MEM32(ecx)`), a registry dispatcher doing
  `ecx = MEM32(index*4 + 0x002F3B08)`.
- The **index argument is a guest stack address `0x00F7F180`** instead of a
  small integer. That resolves outside the 64 MB Xbox RAM view and yields
  garbage.
- Argument chain (verified): `sub_0011E840` reads its `esi` from `[esp+0x1C]`
  and forwards it to `sub_00119140` as arg0; that `esi` originates as `edi` in
  `sub_00117460`, which reads `edi = [esp+0x148]` on entry — i.e. an 8th
  argument to `sub_00117460` carries a stack pointer.
- `sub_00117460` has **no direct callers**; it is reached only through the
  generated dispatch table (`recomp_dispatch.c:7496`), i.e. an **indirect call**.
  `sub_00117570` is a 5-byte tail-jump thunk to `sub_00117460`
  (`recomp_dispatch.c:7500`).
- The registry at `0x002F3B08` is all-zero and no lifted function writes it,
  so even a valid index would take the null fallback path — **the defect is the
  index, not the empty registry**.
- `RECOMP_ABI_CHECK` flags 11 sites, including `sub_001226F0` leaving
  `ebx = 0xF7F180` (the exact bad value) and `sub_00122B20`/`sub_00123A90`. It
  *also* flags known-good functions and MSVC SEH helpers, so it is **suggestive,
  not conclusive**.

**Next experiment (unchanged in priority):** identify what writes the 8th
argument slot of `sub_00117460` (the `[esp+0x148]` value) and who reaches it via
the dispatcher, using the existing watchpoint tooling with
`RECOMP_WATCH_RAW=1`. Then determine whether the ABI-flagged cluster
(`sub_001226F0` et al.) is the writer in the same thread or an independent false
positive. This is **dynamic** and therefore runs on the Windows PC (or wherever
the game currently executes); it is *not* a macOS-only task.

---

## 8. Tests executed in this session and their actual results

Everything below was run in this session. Nothing here is a game-execution test;
no new boot attempt was made (the environment question had to be resolved first,
and the game halts at a known deterministic crash anyway).

| Test | Command | Result |
|---|---|---|
| Host OS / arch | `uname -a ; echo $OS` | Windows / MINGW64, `OS=Windows_NT` — **not macOS** |
| macOS tool present? | `command -v sw_vers` | absent |
| Local git state | `git status ; git log ; git remote -v` | branch `master`, **no commits**, no remote |
| GitHub repo state | `git ls-remote https://github.com/untop02/simp` | exit 0, **no refs** (empty) |
| Network sanity | `git ls-remote …/git/git HEAD` | returned a SHA — network fine, repo genuinely empty |
| GitHub API | `GET api.github.com/repos/untop02/simp` | `"size": 0`, `default_branch: "main"`, created 2026-10-09 |
| Pinned toolkit | `git rev-parse HEAD` in `third_party/xboxrecomp` | `193e2995ffaec871bb3e43a43bd66aa5fccfeb1` |
| Toolkit cleanliness | `git status --porcelain` | empty — **clean** |
| Upstream macOS support | read `tools/macos/setup.sh`, `src/d3d/CMakeLists.txt`, `src/d3d/d3d8_gl.c`, `src/platform/CMakeLists.txt`, README | POSIX/OpenGL + Darwin compat **present** |
| Project portability | read `game/The Simpsons Road Rage/CMakeLists.txt` | Windows-bound (`D:/…` path, `WIN32`, `d3d11`, …) |
| Disk space | `df -h /d` | 36 GB free (97% used) |
| Artifact sizes | `du -sh …` | gen 47 MB / 58 files; build 220 MB; game tree 623 MB; third_party 158 MB |

No build or run was executed because doing so would not have advanced the Mac
question, and the previous milestone's run is already characterised.

---

## 9. Exact commands to reproduce the successful steps

### 9.1 Analysis stages 1–5 — portable, run on the Mac

```bash
# One-time (macOS)
git clone https://github.com/sp00nznet/xboxrecomp.git third_party/xboxrecomp
cd third_party/xboxrecomp && git checkout 193e2995ffaec871bb3e43a43bd66aa5fccfeb1
python3 -m venv .venv && .venv/bin/pip install capstone pytest pefile numpy
# (tools/macos/setup.sh does the venv, Homebrew SDL2/epoxy, and the `py` shim)
```

```bash
# Pipeline (NO --text-only) — paths relative to the repo root
XBE="game/The Simpsons Road Rage/default.xbe"
GEN="game/The Simpsons Road Rage/src/recomp/gen"
S1="game/The Simpsons Road Rage/src/recomp/seed_functions.json"
S2="game/The Simpsons Road Rage/src/recomp/seed_function_starts.json"

cd third_party/xboxrecomp
PYTHONPATH=. python3 -m tools.disasm "$XBE" --seed-functions "$S1" --seed-functions "$S2" --force
PYTHONPATH=. python3 -m tools.func_id "$XBE"
PYTHONPATH=. python3 -m tools.abi_analysis "$XBE"
PYTHONPATH=. python3 -m tools.recomp "$XBE" \
    --game-name "The Simpsons Road Rage" --all --split 250 --gen-dir "$GEN"
# Expected: 13,386 functions, 0 failed, 289 stubs (deterministic; see M5).
```

Asset verification (portable):

```bash
PYTHONPATH=third_party/xboxrecomp python3 scripts/m5_verify_extract.py
# Expected: 48/48 sizes match, 0 missing, 0 mismatches
```

### 9.2 Execution (stages 6–8) — Windows for now

Retain the existing recipe from `docs/M5-RESULTS.md` §10 (Zig cc + Ninja +
Apple-Python CMake, `-fno-sanitize=undefined`, 12 s watchdog). Do **not** port
the backend before the guest reaches graphics submission.

### 9.3 To get this work onto GitHub (so the Mac can pull it)

Requires explicit approval (nothing has been committed). Only non-copyrighted
content should be pushed; `game/`, `*.iso`, `*.xbe`, `logs/`, `third_party/`,
`src/recomp/gen/`, and build output are already git-ignored.

```bash
git remote add origin https://github.com/untop02/simp.git
git add .gitignore README.md docs scripts
git commit -m "M0–M5 research, reports, and tooling"
git push -u origin master        # remote default branch is `main`; see §10
```

---

## 10. Single highest-value next action

**Decide where execution happens, and get the tree onto GitHub so the Mac has
real content.**

Concretely, in priority order:

1. **Push the non-copyrighted project to `untop02/simp`** (docs, scripts,
   `.gitignore`, README) so the Mac can clone a meaningful tree. Do this only
   with your explicit go-ahead; note the remote default branch is `main` while
   the local branch is `master`.
2. **Transfer the git-ignored exec/input tree to the Mac** one way or another
   (`game/`, the ISO, `logs/`, `third_party/`, generated `gen/`). Without this,
   the Mac cannot reproduce stages 6–8 at all.
3. On the Mac, run §3 to record the real environment, then prove stages 1–5
   reproduce the Windows `functions.json` / generated C byte-for-byte. This is
   the concrete portable test that validates the Mac toolchain.
4. Keep the **registry-index investigation** on whichever machine executes the
   game (currently Windows), per §7 — that is still the true blocker to a
   bootable game.

If the intent was for **Zed on this PC to be connected to the Mac**, that is not
the case: this session's shell is Windows/MINGW64. Attaching Zed to the Mac (or
opening this tree from a Mac-side copy) is required before any genuine macOS
result can be produced.

---

## Appendix A — Corrections to earlier documents

- **M4 note "tools.xiso flattens paths"** was wrong for `unpack` (only `get`
  flattens). Already corrected in `docs/M5-RESULTS.md` §4.3.
- **Prior assumption "the runtime is uniformly Windows/D3D11-bound and must not
  be ported"** is **partially incorrect**. Upstream is conditionally compiled
  with a POSIX/OpenGL backend and a Darwin compat layer; the *game project
  harness* is what is currently Windows-specific. See §5.
- No historical M1–M5 report has been rewritten. This document only adds the
  migration view.
