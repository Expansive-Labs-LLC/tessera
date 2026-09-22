# ADR-0001: How the GPU inference runtime is delivered

## Status

**Accepted** — 2026-09-22, Derek (CSO)

Implemented by TASK-TS-0023 / SPEC-TS-0023.

> **Two load-bearing claims were not verified before acceptance** and are
> carried forward as explicit work rather than lost: the Extensions Platform
> archive size limit, and whether prebuilt CUDA-extension wheels exist for the
> target GPU generation. Both would change the verdict on Option 1 if wrong.
> They are tracked as the first deliverable of TASK-TS-0023, ahead of any
> engine code, so that a wrong premise is caught before it is built on.

## Date

2026-09-22

## Context

Tessera's model weights are solved: they download on first use, are commit-pinned, digest-verified and licence-gated (SPEC-TS-0002). What is not solved is the **runtime that consumes them**.

Every inference adapter in the codebase needs PyTorch:

| Adapter | Module | torch references |
|---|---|---|
| SAM 2 | `tessera/vision/segmentation/sam2_adapter.py` | 10 |
| DINOv2 | `tessera/vision/features/dinov2_adapter.py` | 12 |
| Depth Anything V2 | `tessera/vision/depth/depth_anything_adapter.py` | present |
| TRELLIS | `tessera/reconstruction/adapters/trellis_adapter.py` | present |

`tessera/models/families.py` records `adapter_ready=False` for `sam2`, `dinov2` and `trellis`, pending TASK-TS-0016 and TASK-TS-0017. **Both tasks are blocked on the same missing thing**, which is why this is one decision rather than two.

TRELLIS additionally requires compiled CUDA extensions (sparse-voxel rasterisation and attention kernels), not just PyTorch.

### Why this cannot simply be bundled

`blender_manifest.toml` declares no `[build] wheels`, and adding them does not resolve it:

- A CUDA-enabled PyTorch distribution is on the order of gigabytes, against an add-on archive currently under 400 KB.
- TRELLIS's CUDA extensions are compiled against a specific CUDA toolkit. Prebuilt wheels for the newest GPU architectures are frequently unavailable, so they build from source — which a Blender add-on install cannot do.
- The add-on is GPL-2.0-or-later. Vendoring a large third-party binary stack into the archive widens the distribution surface materially.
- The Extensions Platform is a curated channel with review and size expectations that a multi-gigabyte binary payload does not fit.

> **To verify before accepting:** the current Extensions Platform archive size limit, and whether prebuilt CUDA-extension wheels exist for the target GPU generation. Both are external facts that change, and neither has been confirmed here.

### Why it is urgent rather than merely open

The generate pipeline falls back to `StubAdapter`, which returns a placeholder cube. That is correct behaviour today — the registry excludes an adapter whose weights are absent — but it means **no configuration of Tessera currently produces a real mesh**. PRD-001 D7 further scopes v1 to NVIDIA CUDA only, and TASK-TS-0022 (Apple Silicon) gates the v1.0 marketplace listing, so the delivery mechanism also determines how hard non-CUDA support later becomes.

## Decision Drivers

- **D1 — Users must be able to generate a mesh.** Nothing else in the product matters until this works.
- **D2 — Installation must stay within what a Blender user will tolerate.** The audience is artists, not ML engineers.
- **D3 — The add-on stays small and GPL-clean.** Distribution surface is a legal and review concern, not only a size one.
- **D4 — Do not foreclose non-CUDA support.** PRD-001 D7/NG8 already name ROCm and Metal as v1 exclusions, not permanent ones.
- **D5 — Weight governance must survive.** Whatever runs inference still resolves weights through the gated, digest-verified cache.
- **D6 — CI must be able to exercise it.** A runtime no pipeline can install is a runtime nobody can test.

## Considered Options

1. **Bundle wheels in the add-on archive**
2. **Thin add-on plus a local engine process**
3. **User-managed environment in Blender's bundled Python**
4. **Swap to backends that run on stock PyTorch**

## Decision Outcome

**Decision: Option 2 — thin add-on plus a local engine process.**

The add-on stays a small, GPL-clean Blender extension containing UI, operators, weight management and the licence gate. A separate local engine — its own virtual environment, its own PyTorch and CUDA stack, installed once — performs inference and is reached over localhost IPC. The add-on detects whether the engine is present and reports its absence as an actionable state rather than a failure inside `torch`.

This is the only option satisfying D1–D4 simultaneously. It is also already gestured at in `MODEL-LICENSES.md`, which notes that a thin-add-on / local-engine split "would unlock ROCm and Metal together with the free Extensions Platform channel."

### Positive Consequences

- The add-on remains small enough for the Extensions Platform, and its GPL surface does not absorb a binary ML stack.
- The engine's environment is independent of Blender's bundled Python, so PyTorch, CUDA and compiled extensions can be versioned and rebuilt without touching the add-on.
- Non-CUDA support becomes an engine build rather than an add-on redesign, which is what makes TASK-TS-0022 tractable.
- The process boundary contains inference crashes and OOM, which today would take Blender down with them.
- CI can run the engine directly, so adapters become testable without Blender in the loop.

### Negative Consequences

- **A second installable artifact.** This is the real cost: a one-time engine install, with its own platform matrix, update path and failure modes. It must be close to one click or D2 is violated.
- IPC adds serialisation and latency — acceptable for multi-second inference, and it forces the adapter boundary to be explicit.
- Two things can now be version-skewed. The engine and add-on need a negotiated protocol version, checked on connect.
- Weight-cache ownership must be settled: the add-on governs licences and digests (D5), so the engine should be handed resolved paths rather than resolving its own.

## Pros and Cons of the Options

### Option 1 — Bundle wheels in the add-on

- Good: single artifact; nothing extra for the user to install.
- Good: no IPC, no protocol, no version skew.
- Bad: archive grows from kilobytes to gigabytes.
- Bad: TRELLIS's CUDA extensions frequently have no prebuilt wheel for current GPU generations, and an add-on install cannot compile.
- Bad: one archive per platform and per CUDA version.
- Bad: materially widens the GPL distribution surface.
- **Rejected:** fails D2 and D3, and is likely not installable at all on the newest hardware.

### Option 2 — Thin add-on plus a local engine process

- Good: satisfies D1–D4 together; the only option that does.
- Good: isolates crashes and OOM from Blender.
- Good: makes non-CUDA a build-matrix problem rather than an architectural one.
- Good: adapters become testable in CI without Blender.
- Bad: a second installable artifact, with its own install UX to get right.
- Bad: introduces a protocol to version and maintain.
- **Chosen.**

### Option 3 — User-managed environment in Blender's bundled Python

- Good: no new architecture; adapters keep working in-process.
- Good: zero distribution surface added.
- Bad: requires users to `pip install` a CUDA PyTorch build into Blender's Python — beyond the target audience (D2).
- Bad: mutating Blender's bundled Python is fragile and can break Blender itself.
- Bad: unsupportable — every user ends up with a different environment.
- **Rejected:** fails D2 outright, and makes support cost unbounded.

### Option 4 — Swap to backends that run on stock PyTorch

- Good: removes the compiled-CUDA-extension problem entirely.
- Good: possibly combinable with Option 1 at a workable size.
- Bad: still ships gigabytes of PyTorch, so D3 is unresolved.
- Bad: the obvious candidate, InstantMesh, was removed from the manifest on 2026-09-21 — unused by any adapter, and its terms are unresolved because it builds on Zero123++ (see `MODEL-LICENSES.md`).
- Bad: a quality regression of unknown size, for a reason unrelated to quality.
- **Not rejected, but not sufficient:** worth revisiting as an engine-side choice under Option 2, not as an alternative to it.

## Open Questions

1. **Engine distribution.** Platform installer, `pipx`-style bootstrap, or a container? This determines whether D2 is met and is the main risk in Option 2.
2. **IPC transport.** HTTP on localhost is simplest and debuggable; a socket or shared memory is faster for large tensors. Mesh payloads are modest, so start simple.
3. **Lifecycle.** Does the add-on spawn and supervise the engine, or does the user run a service? Spawning is better UX; a service is easier to debug.
4. **Weight-cache ownership.** Confirm the add-on resolves and verifies, and passes paths — preserving D5 and the licence gate as the single choke point.
5. **Does the engine subsume TASK-TS-0022?** If the engine carries per-platform builds, Apple Silicon support may become an engine build rather than an adapter rewrite.

## Consequences for Existing Work

Implemented by **TASK-TS-0023 / SPEC-TS-0023**.

> **The first version of this section was incomplete.** It named two affected
> specs. A scan of all fifteen found six, three of which contain a constraint
> that this decision *directly contradicts* rather than merely dates. The
> corrected list is below.

### Direct contradictions — these specs currently forbid what this ADR decides

Each of these carries a constraint requiring inference to run inside the
Blender process. Accepting Option 2 makes them wrong, not merely stale, and an
implementer following them would build the rejected option.

| Spec | Status | Constraint |
|---|---|---|
| **SPEC-TS-0004** Reconstruction engine | Approved | CON-008 — "SHALL NOT use `subprocess` or shell commands to invoke model inference. All inference SHALL run in-process via Python/PyTorch." |
| **SPEC-TS-0007** Multi-view reconstruction | Submitted | CON-009 — "SHALL NOT use `subprocess` or shell commands to invoke SfM or reconstruction. All processing SHALL run in-process via Python/PyTorch." |
| **SPEC-TS-0010** Sketch-to-3D | Draft | CON-008 — "SHALL NOT use `subprocess` or shell commands for inference. All inference SHALL run in-process via Python/PyTorch." |

These three SHALL be amended before any engine work begins. The constraint's
intent — no shelling out to opaque binaries mid-pipeline — is still right; it
needs rewording to permit the sanctioned engine boundary while continuing to
forbid ad-hoc subprocess invocation.

### Consequential amendments — correct today, wrong once the engine exists

| Spec | Status | What moves |
|---|---|---|
| **SPEC-TS-0003** Vision pipeline | Approved | NFR-003 measures `torch.cuda.max_memory_allocated()` and EC-00x catches `torch.cuda.OutOfMemoryError` — both now occur in a different process and reach the add-on as structured errors |
| **SPEC-TS-0011** Production hardening | Draft | FR-007, FR-011 and FR-013 define VRAM handling, the perf report and an LRU model cache in terms of `torch.cuda.*`; all become engine-side concerns |
| **SPEC-TS-0015** Marketplace publication | Draft | Must describe the engine install — it changes what a buyer agrees to install |

### Tasks

- **TASK-TS-0016** (SAM 2, DINOv2 adapters) and **TASK-TS-0017** (TRELLIS) are blocked by TASK-TS-0023, not merely by this decision. Their adapters move engine-side, so their scope changes as well as their timing.
- **TASK-TS-0021** (refinement LLM backend) should be assessed: `local_llm.py` calls `ensure_model()` for a GGUF model, which is a second local runtime. Whether it shares the engine or stays separate is an open question this ADR does not settle.
- **TASK-TS-0022** (Apple Silicon) is materially cheaper under Option 2 and should be re-estimated.

## References

- `MODEL-LICENSES.md` — notes the thin-add-on / local-engine split as the route that also unlocks ROCm and Metal
- `PRD-001_Tessera.md` §8, D7, NG8 — NVIDIA-only v1 scope
- `tessera/models/families.py` — `adapter_ready` and `pending_task` per family
- TASK-TS-0016, TASK-TS-0017, TASK-TS-0022
