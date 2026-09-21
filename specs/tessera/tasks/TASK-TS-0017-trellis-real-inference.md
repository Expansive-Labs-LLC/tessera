# Task: Trellis Adapter Real Inference

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0017 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-04-18 |
| **Assignment Method** | Handoff from Pipeline Wiring |
| **Sprint/Iteration** | Phase 1 — Integration |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P0 | L | High | Integration | Implementation Gap |

**Note:** The Trellis adapter has a `reconstruct()` method but checkpoint verification is placeholder. Currently the `AdapterRegistry` falls back to `StubAdapter` (returns a test cube). This task makes the adapter produce real 3D meshes.

---

## ⚠️ Special Instructions

> If Trellis model weights are too large or the inference pipeline is incompatible with Blender's Python, evaluate InstantMesh as an alternative backend. The adapter pattern allows swapping without changing the engine.

---

## Business Context

### Why This Matters
This is the core "magic" — converting a 2D image into a 3D mesh. Without real inference, the generate button produces a test cube. With it, users get an actual AI-generated 3D model.

### Why Now
The generate operator pipeline is wired. Vision pipeline outputs feed directly into `ReconstructionEngine.reconstruct()` which calls the adapter. The adapter must produce real output.

### User Story
**As a** user who uploaded a photo and clicked "Generate 3D Model",  
**I want** a recognizable 3D mesh to appear in my Blender scene,  
**So that** I can refine and 3D-print it without manual modeling skills.

### Master PRD Reference
- **PRD Section:** §5.2 3D Reconstruction Engine
- **Spec:** SPEC-TS-0004

---

## Initial Requirements

### What Needs to Be Built

1. **Checkpoint Verification** (`tessera/reconstruction/adapters/trellis_adapter.py`)
   - Replace placeholder checksum logic with real SHA256 verification
   - Verify model files exist in cache before attempting to load
   - Return clear error if weights are missing with download instructions

2. **Real Inference**
   - `reconstruct()` must load Trellis model, run inference on VisionPipelineOutput inputs
   - Produce `StandardMesh` with valid `vertices` (N,3) float32 and `faces` (M,3) int32
   - Populate `vertex_colors` (N,3) float32 if available from Trellis output
   - Set metadata: `model_name`, `inference_time_s`, `confidence`, `vertex_count`, `face_count`

3. **GPU Memory Management**
   - Clear CUDA cache after inference
   - Handle OOM gracefully with actionable error message
   - Respect VRAM guard checks (min_vram_gb in capabilities)

4. **Fallback Behavior**
   - When Trellis weights unavailable → fall back to StubAdapter (existing)
   - When VRAM insufficient → return error with VRAM requirement
   - When inference fails → return error with suggestion to try different image

### Known Constraints
- Trellis requires ~6GB VRAM for inference on consumer GPU
- Model weights are large — verify download manager fetches all required files
- Output may need conversion from Trellis-native format to StandardMesh arrays
- Inference must complete within 120s timeout (FR-022)

### Success Looks Like
User uploads a photo of a mug, clicks Generate, and a recognizable mug-shaped mesh appears in the 3D viewport within 60 seconds. The mesh has correct general proportions and vertex colors.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Reconstruction Engine Spec | `specs/tessera/feature-spec/active/SPEC-TS-0004-reconstruction-engine.md` | Full requirements |
| Trellis Adapter | `tessera/reconstruction/adapters/trellis_adapter.py` | Implementation to complete |
| Stub Adapter | `tessera/reconstruction/adapters/stub_adapter.py` | Reference for adapter interface |
| Engine | `tessera/reconstruction/engine.py` | Orchestrator that calls adapter |
| Mesh Output Types | `tessera/reconstruction/mesh_output.py` | StandardMesh, ReconstructionResult |
| Trellis GitHub | [github.com/microsoft/TRELLIS](https://github.com/microsoft/TRELLIS) | Upstream model |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0016 (Vision Adapter Validation) | Pending | Blocks this | Reconstruction needs valid VisionResult inputs |
| TASK-TS-0002 (Model Weights) | ✅ Complete | Partial | Trellis weight download status needs verification |
| Generate Operator Wiring | ✅ Complete | - | Pipeline calls engine.reconstruct() |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Trellis Weight Download Verified** | TBD |
| **Inference Produces Mesh** | TBD |
| **OOM/Error Handling Tested** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Is Trellis the right model? Should we evaluate alternatives (InstantMesh, TripoSR) in a spike first?
2. What's the minimum VRAM to run inference? Need to set `min_vram_gb` correctly in capabilities.
3. Should we offer a "quality vs speed" toggle (e.g., fewer diffusion steps for faster results)?

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
