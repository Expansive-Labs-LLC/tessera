# ADR-0001 Premise Verification

| Field | Value |
|---|---|
| **Verifies** | ADR-0001 — How the GPU inference runtime is delivered |
| **Required by** | SPEC-TS-0023 FR-001, TASK-TS-0023 deliverable 1 |
| **Verified** | 2026-09-22 |
| **Verified by** | Derek |
| **Outcome** | **Both premises confirmed. ADR-0001 stands; no reopening required.** |

ADR-0001 was accepted with two load-bearing claims unverified, and gated all
engine-side work on confirming them first, so that a wrong premise would be
caught before it was built on. This is that record.

---

## Premise 1 — The Extensions Platform archive size limit

**Claim under test:** the Extensions Platform is a curated channel whose size
expectations a multi-gigabyte binary payload does not fit.

**Finding: confirmed.** The platform rejects uploads above **200 MB** with
HTTP 413, raised from an earlier 100 MB. Raising it further is described by the
maintainers as requiring considerable changes to the system, so it is not a
limit to plan around.

**Bearing on the decision.** A CUDA-enabled PyTorch distribution is measured in
gigabytes — the cu128 wheel alone is well over 200 MB before TRELLIS, its
compiled extensions, or any weight. Option 1 (bundle wheels in the add-on
archive) is not merely undesirable on this channel; it is not uploadable.

For reference, the add-on as built today is **399 KB** against its own 1 MB
budget (SPEC-TS-0023 NFR-004), which is roughly 0.2% of the platform ceiling.
The split keeps three orders of magnitude of headroom.

---

## Premise 2 — Prebuilt CUDA-extension wheels for the target GPU generation

**Claim under test:** TRELLIS's CUDA extensions are compiled against a specific
toolkit, prebuilt wheels for the newest architectures are frequently
unavailable, and they therefore build from source — which a Blender add-on
install cannot do.

**Finding: confirmed, and the distinction matters more than the ADR assumed.**
Tested against the target hardware rather than from documentation:

| Fact | Evidence |
|---|---|
| Target GPU is Blackwell, compute capability **12.0** (`sm_120`) | `nvidia-smi` — NVIDIA GeForce RTX 5090, 32,607 MiB, driver 580.173.02 |
| The installed CUDA toolkit **cannot target it at all** | `nvcc --list-gpu-arch` stops at `compute_90`; `nvcc -arch=sm_120` → `nvcc fatal : Value 'sm_120' is not defined for option 'gpu-architecture'` |
| Installed toolkit version | CUDA 12.0.140 — predates Blackwell, which needs ≥ 12.8 |
| **PyTorch itself is prebuilt and available** | `pip index versions torch --index-url .../cu128` → 2.7.0 through 2.11.0, all `+cu128` |

So the two halves of the dependency behave differently, and the ADR treated
them as one:

- **PyTorch is a solved, prebuilt problem.** Wheels with native `sm_120`
  support have existed since 2.7.0. Nothing needs compiling.
- **TRELLIS's compiled extensions are not.** They build from source against a
  toolkit new enough for the architecture. On this machine that build would
  fail today, because the installed toolkit rejects `sm_120` outright.

**Bearing on the decision.** The premise holds and the conclusion is
unchanged — an add-on install cannot run `nvcc`, cannot install a CUDA toolkit,
and cannot be asked to. But the refinement is load-bearing for the installer:

> The engine installer cannot simply carry "prebuilt wheels". It must carry
> extensions **built in CI against a toolkit matching each supported GPU
> architecture**, or build them on the user's machine — and building on the
> user's machine reintroduces exactly the toolchain requirement ADR-0001 D2
> exists to avoid.

This is recorded against SPEC-TS-0023 FR-030, which says the installer carries
"its own pinned CPython interpreter, virtual environment and prebuilt wheels".
That is right, and this is the constraint that makes producing them a CI
problem per architecture rather than a packaging step.

---

## Consequences

1. **ADR-0001 is not reopened.** Both premises support the decision it took;
   neither contradicts it. Option 1 remains correctly rejected, on two
   independent grounds rather than one.
2. **Engine-side implementation is unblocked** (SPEC-TS-0023 FR-001).
3. **A CUDA toolkit ≥ 12.8 is a prerequisite** for building TRELLIS's
   extensions for the target hardware, on a developer machine and in CI alike.
   The toolkit installed on the current workstation is not sufficient.
4. **FR-030's build matrix is per GPU architecture, not only per platform.**
   An installer built against one toolkit does not serve a GPU generation that
   toolkit does not know.

## Sources

- Blender Extensions Platform upload limit — `projects.blender.org/infrastructure/extensions-website` issue 328 (413 Content Too Large above the configured ceiling)
- PyTorch Blackwell support — `download.pytorch.org/whl/cu128`, queried 2026-09-22
- Local hardware and toolkit — `nvidia-smi`, `nvcc --list-gpu-arch`, `nvcc -arch=sm_120`, run 2026-09-22
