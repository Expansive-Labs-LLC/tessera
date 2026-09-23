# Tessera engine — Linux x64 release

Implements SPEC-TS-0023 FR-030, FR-031 and FR-042.

## Why the engine is a separate artifact at all

PyTorch with CUDA is gigabytes and TRELLIS needs compiled extensions. The
Blender Extensions Platform rejects uploads above 200 MB, so none of it can
ship inside the add-on archive — which builds at 399 KB and stays there. See
`specs/tessera/adr/ADR-0001-inference-runtime-delivery.md` and its premise
verification.

## v1 is Linux x64 only

Windows is deferred to SPEC-TS-0024. It is blocked on a code-signing identity,
not on engineering: an unsigned Windows installer trips SmartScreen, which is a
worse outcome for ADR-0001 D2 than not shipping one. The add-on's discovery,
client and status model already resolve Windows paths, so what is deferred is
packaging.

macOS waits longer — v1 is CUDA-only (PRD-001 D7/NG8), so there is no device
path to install for.

## Build prerequisites

| Requirement | Why |
|---|---|
| **CUDA toolkit ≥ 12.8** | TRELLIS's extensions build from source, and Blackwell (`sm_120`) is not a target CUDA 12.0 knows. The build refuses rather than producing kernels that will not launch |
| Python 3.11+ | The venv the artifact carries |
| `gpg` with the release key | FR-042 |

PyTorch itself needs no build — it is installed from the published `cu128`
index, which has carried native `sm_120` support since 2.7.0.

### Getting a toolkit without root

```bash
packaging/linux/provision_toolchain.sh
```

Installs `nvcc` into `.cuda-toolchain/` beside the engine venv, pinned to
whatever CUDA version PyTorch was built against. About 400 MB, no root,
removable with `rm -rf`. The build script picks it up automatically.

Two routes that do **not** work, recorded so nobody spends an afternoon on
them again:

- **pip.** NVIDIA's `nvidia-cuda-nvcc-cu12` wheel ships only `ptxas` — at
  12.8.93 and 12.9.86 alike. No `nvcc` driver, no `cicc`. It exists for JIT
  through nvrtc, not for compiling an extension offline.
- **The distro package.** Needs root, installs system-wide, and on Ubuntu is
  frequently a version behind what current GPUs require. This workstation
  shipped 12.0, whose `nvcc` rejects `sm_120` outright.

Pin the toolkit to torch's CUDA version rather than the newest available. A
toolkit ahead of torch can compile extensions that then fail to load against
torch's runtime, and that failure appears at import rather than at build.

> **`ninja` must be on `PATH`, not merely installed.** Torch's extension
> builder shells out to it by name. It is a venv console script, so running
> `.venv/bin/python` directly is not enough — the venv's `bin` has to be on
> `PATH`. The error names ninja rather than `PATH`, which sends you the wrong
> way. Both scripts here handle it.

## Building

```bash
export TESSERA_SIGNING_KEY=C353C8F1A9FC2DA4
packaging/linux/build_engine_installer.sh 1.0.0
```

Produces in `dist/`:

```
tessera-engine-1.0.0-linux-x64.tar.gz
tessera-engine-1.0.0-linux-x64.tar.gz.sha256
tessera-engine-1.0.0-linux-x64.tar.gz.asc
```

`CUDA_ARCH_LIST` (default `8.6;8.9;12.0` — Ampere, Ada, Blackwell) is the
contract, not a hint: the artifact serves those compute capabilities and the
build verifies the toolkit can target every one before it starts. The list is
recorded in `build-info.json` inside the artifact so the engine can refuse a
GPU it was not built for instead of failing inside a kernel launch.

## Installing

```bash
tar -xzf tessera-engine-1.0.0-linux-x64.tar.gz
./tessera-engine/install.sh
```

Per-user, no root. Nothing the engine does needs system-wide privilege, and
asking for it would be asking the user to trust more than the job requires.

Installs to `${XDG_DATA_HOME:-~/.local/share}/tessera/engine/` and writes the
installation marker at `install.json` in the same directory. The marker's
presence is what the add-on treats as *installed* — probing the port cannot
answer that question, because nothing listening means stopped or absent, and
those two want opposite advice.

## Verifying a release

```bash
gpg --recv-keys 368C203CD177EF8A0169842EC353C8F1A9FC2DA4
gpg --verify tessera-engine-1.0.0-linux-x64.tar.gz.asc \
             tessera-engine-1.0.0-linux-x64.tar.gz
sha256sum -c tessera-engine-1.0.0-linux-x64.tar.gz.sha256
```

Release signing key:

```
368C 203C D177 EF8A 0169  842E C353 C8F1 A9FC 2DA4
Derek DeJonghe <derek@expansivelabs.io>
```

The signature is for people verifying the distribution themselves. The add-on's
own integrity gate is the pinned SHA256 it checks before running the installer
(FR-041), which works whether or not the user has imported a key.

## Uninstalling

```bash
rm -rf ~/.local/share/tessera/engine
```

Removing the marker is what makes the add-on report `Not installed` again; it
then falls back to `StubAdapter` and stays usable.
