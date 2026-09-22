# Task: Apple Silicon (MPS) Inference Support

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0022 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-09-21 |
| **Assignment Method** | CSO decision D7 (GTM analysis) / PRD-001 D7 |
| **Sprint/Iteration** | Phase 5 — Pre-Launch |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟠 P1 | L | Medium | Feature | Implementation Gap / GTM |

**Note:** Gates the v1.0 marketplace listing. v1 ships NVIDIA-only by decision; this task removes that limitation for Apple Silicon, which is the largest addressable segment currently turned away.

---

## ⚠️ Special Instructions

> Requires an Apple Silicon Mac for development and verification. MPS coverage in PyTorch is incomplete — expect operator-level gaps that need CPU fallback for specific ops, and verify numerical output against CUDA rather than assuming parity.

---

## Business Context

### Why This Matters
Every inference adapter hardcodes CUDA (`sam2_adapter.py` `device="cuda"`, `depth_anything_adapter.py` and `dinov2_adapter.py` `self._device = "cuda"`, `trellis_adapter.py` `map_location="cuda"`). GPU detection reports CUDA, ROCm and Metal correctly, which made the add-on *look* cross-platform while generation failed at model load on anything but NVIDIA.

Blender's user base skews Mac-heavy. Shipping a paid listing that excludes Apple Silicon leaves the second-largest segment of that audience unable to buy — and, before the 2026-09-21 correction, the PRD, README, docs site and draft listings all promised Apple Silicon support the product did not have.

### Why Now
v1 ships NVIDIA-only with that limitation stated in the listings, the README, the docs and a runtime banner (2026-09-21). That is honest, but it is a ceiling on the addressable market. The GTM plan launches paid early access on Gumroad first and the Superhive listing at v1.0 — this task should land before the v1.0 listing so the flagship listing does not open with the restriction baked into its reviews.

### User Story
**As a** Blender user on an Apple Silicon Mac,
**I want** Tessera's reconstruction pipeline to run on my GPU,
**So that** I can generate print-ready models without owning an NVIDIA machine.

### Master PRD Reference
- **PRD Section:** NG8, §8 Technology Stack (Compute backend), §12 D7
- **Specs:** SPEC-TS-0001 (GPU detection, FR-008–FR-010, EC-006), SPEC-TS-0003 (vision pipeline, FR-022), SPEC-TS-0004 (reconstruction engine)

---

## Initial Requirements

### What Needs to Be Built

1. **Device abstraction** (new, e.g. `tessera/utils/device.py`)
   - One resolver that maps detected backend → a `torch.device`, replacing every hardcoded `"cuda"` string.
   - Exposes the memory-query and cache-clear operations each backend needs (`torch.cuda.empty_cache()` has no direct MPS equivalent).
   - Single source of truth for `SUPPORTED_INFERENCE_BACKENDS` in `gpu_detection.py`.

2. **Adapter migration**
   - `sam2_adapter.py`, `depth_anything_adapter.py`, `dinov2_adapter.py`, `trellis_adapter.py`, `neus2_backend.py`, `hloc_estimator.py` all resolve their device through the abstraction.
   - `torch.load(..., map_location=...)` uses the resolved device.
   - VRAM guards read unified memory on Apple Silicon (already reported as shared by `gpu_detection`).

3. **OOM and operator-gap handling**
   - Catch the MPS equivalents of `torch.cuda.OutOfMemoryError` and raise `InsufficientVRAMError` with the same actionable wording.
   - Where an operator is unimplemented on MPS, fall back per-op to CPU with a logged warning rather than failing the run.

4. **Guard removal and messaging**
   - Add `"MPS"` to `SUPPORTED_INFERENCE_BACKENDS` only once the pipeline passes end to end.
   - Update the main-panel banner, `unsupported_backend_message()`, SPEC-TS-0001 EC-006 and SPEC-TS-0003 FR-022 accordingly.

5. **Model weight compatibility**
   - Verify every model in `manifest.json` loads on MPS — `.pth` checkpoints, safetensors, and the TRELLIS pipeline in particular.

6. **Claim restoration**
   - Once verified, restore Apple Silicon to the README, docs site (`installation.md`, `faq.md`, `index.md`, `troubleshooting.md`, glossary) and all `marketplace/copy/` files, which were corrected to NVIDIA-only on 2026-09-21. Do not restore the claim before the pipeline passes on real hardware.

### Known Constraints
- Apple Silicon VRAM is unified memory — the existing "(shared)" reporting path already exists in `gpu_detection.py`.
- PyTorch MPS does not implement every operator; some paths will need CPU fallback and will be slower.
- `torch.cuda.*` calls are scattered across adapters and perf profiling — grep for `cuda` before declaring the migration complete.
- macOS 13+ is the practical floor for usable MPS support in PyTorch.

### Success Looks Like
On an M-series Mac with 16 GB unified memory, a user loads two photos, clicks Generate, and a print-valid mesh appears in the viewport — with no CUDA references in the logs and no unsupported-backend banner.

### Secondary scope — CSO call required
**AMD (ROCm)** hits the identical wall and the same device abstraction would carry it, but it needs Linux + ROCm hardware to verify and has a smaller Blender audience. Recommend: build the abstraction so ROCm is a configuration rather than a rewrite, but do not commit to verifying ROCm in this task. See Open Questions.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| GTM analysis §2.4 | `marketplace/GTM-STRATEGY.md` | Why this gates the v1.0 listing; decision D8 |
| GPU detection | `tessera/gpu_detection.py` | `SUPPORTED_INFERENCE_BACKENDS`, `is_inference_supported()`, `unsupported_backend_message()` |
| Add-on scaffold spec | `specs/tessera/feature-spec/active/SPEC-TS-0001-addon-scaffold.md` | FR-008–FR-010, EC-006 (Apple Silicon detection) |
| Vision pipeline spec | `specs/tessera/feature-spec/active/SPEC-TS-0003-vision-pipeline.md` | FR-022 GPU validation |
| Vision adapters | `tessera/vision/{segmentation,depth,features}/` | Hardcoded `"cuda"` to migrate |
| Reconstruction adapter | `tessera/reconstruction/adapters/trellis_adapter.py` | Hardcoded `map_location="cuda"` |
| PyTorch MPS backend | [pytorch.org/docs/stable/notes/mps.html](https://pytorch.org/docs/stable/notes/mps.html) | Operator coverage and fallback behaviour |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0016 (Vision Adapter Validation) | Pending | Blocks this | The CUDA path must be proven working before porting it |
| TASK-TS-0017 (Trellis Real Inference) | Pending | Blocks this | The reconstruction adapter's device handling is placeholder today |
| ADR — dependency delivery / Extensions Platform eligibility (GTM D3) | Not raised | Strongly related | A thin add-on + local engine would make non-CUDA backends a packaging choice rather than a `bpy`-bundled-torch problem, and unlocks the free channel at the same time. Decide the ADR before committing to an approach here |
| Apple Silicon hardware | Not procured | Blocks verification | Required for development and sign-off |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **ADR decision on dependency delivery** | TBD |
| **Device abstraction merged (CUDA behaviour unchanged)** | TBD |
| **Vision pipeline runs end to end on MPS** | TBD |
| **Reconstruction runs end to end on MPS** | TBD |
| **Claims restored in README, docs and listings** | TBD |
| **Target Complete — before the v1.0 Superhive listing** | TBD |

---

## Open Questions

### Flagged by CSO

1. Is AMD (ROCm) in scope for this task, a follow-up task, or dropped for v1? Recommendation: build the abstraction to accommodate it, verify only MPS here.
2. Does the thin-add-on / local-engine ADR (GTM D3) land first? If it does, this work should target the engine process rather than Blender's bundled Python — it changes the approach materially.
3. What is the acceptable performance delta versus CUDA before we would rather ship nothing? MPS will be slower; a 3× slowdown on a 10-minute generation is a different product experience.
4. Is Apple Silicon hardware being procured, or is verification outsourced to a beta tester with an M-series Mac?

---

## Escalation

| Need | Contact | Channel |
|------|---------|---------|
| Technical questions | TBD | DM |
| Business/Requirements | Derek | DM |
| Blocked | — | #blocked |

---

## Orchestrator Acknowledgment

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Questions added above (if any) | ☐ |
| Questions resolved with CSO/Deputy | ☐ |
| Ready to begin | ☐ |

**Acknowledged Date:** [Date]
**Target Completion:** [Date]
