# Task: Vision Pipeline Adapter Validation

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0016 |
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

**Note:** Critical blocker — the generate button is now wired but real inference has not been validated against downloaded model weights inside Blender's Python environment.

---

## ⚠️ Special Instructions

> Each adapter must be tested individually against real model weights inside Blender's bundled Python. The snap sandbox may restrict GPU access — document any workarounds needed.

---

## Business Context

### Why This Matters
The vision pipeline is the first stage of the generate flow. If SAM2/DepthAnything/DINOv2 adapters fail to load or produce garbage output, the entire pipeline is broken. This is the #1 blocker to a working demo.

### Why Now
The generate operator was just wired up (2026-04-18). The pipeline flow is `images → VisionPipeline → ReconstructionEngine → MeshImporter`. VisionPipeline calls these adapters — they must work.

### User Story
**As a** user who clicks "Generate 3D Model",  
**I want** the vision pipeline to analyze my reference images correctly,  
**So that** the reconstruction engine receives high-quality segmentation masks, depth maps, and feature embeddings.

### Master PRD Reference
- **PRD Section:** §5.1 Vision Analysis Pipeline
- **Spec:** SPEC-TS-0003

---

## Initial Requirements

### What Needs to Be Validated

1. **SAM2 Adapter** (`tessera/vision/segmentation/sam2_adapter.py`)
   - `load()` — loads `sam2-hiera-large` weights from `~/.config/blender/5.1/scripts/addons/tessera/cache/`
   - `predict(image)` — accepts (H, W, 3) uint8 ndarray, returns (H, W) uint8 mask (0 or 255)
   - `unload()` — frees GPU memory, `torch.cuda.empty_cache()`

2. **Depth Anything V2 Adapter** (`tessera/vision/depth/depth_anything_adapter.py`)
   - `load()` — loads `depth_anything_v2_vitl.pth` from cache
   - `predict(image, mask)` — returns (H, W) float32 depth map, values in [0.0, 1.0]
   - `unload()` — frees GPU memory

3. **DINOv2 Adapter** (`tessera/vision/features/dinov2_adapter.py`)
   - `load()` — loads DINOv2 ViT-B/14 from cache
   - `predict(image)` — returns (1, D) float32 CLS token embedding
   - `unload()` — frees GPU memory

4. **End-to-End Validation**
   - `VisionPipeline().process([ImageInput(filepath="test.jpg")])` completes without error
   - Returns valid `VisionResult` with all fields populated
   - Total pipeline time < 30s on consumer GPU

### Known Constraints
- Blender uses its own Python (snap: `/snap/blender/current/...`)
- `huggingface_hub` installed to `~/.config/blender/5.1/scripts/modules/`
- PyTorch must be available in Blender's Python — may need manual install
- GPU access through snap sandbox may require `--classic` or environment vars

### Success Looks Like
Running the generate operator on a single test image produces a valid `VisionResult` with a non-trivial segmentation mask, depth map, and feature embedding. Console shows per-stage timing without errors.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Vision Pipeline Spec | `specs/tessera/feature-spec/active/SPEC-TS-0003-vision-pipeline.md` | Full requirements |
| SAM2 Adapter | `tessera/vision/segmentation/sam2_adapter.py` | Implementation to validate |
| Depth Anything Adapter | `tessera/vision/depth/depth_anything_adapter.py` | Implementation to validate |
| DINOv2 Adapter | `tessera/vision/features/dinov2_adapter.py` | Implementation to validate |
| Model Manifest | `tessera/models/manifest.json` | Weight file paths and hashes |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0002 (Model Weights) | ✅ Complete | Blocks this | SAM2 + DINOv2 downloaded; Depth Anything needs verification |
| Generate Operator Wiring | ✅ Complete | Blocks this | Pipeline flow wired 2026-04-18 |
| PyTorch in Blender Python | ❓ Unknown | Blocks this | Must verify torch is importable |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **PyTorch Availability Check** | TBD |
| **Individual Adapter Tests** | TBD |
| **End-to-End Pipeline Test** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Is PyTorch installed in Blender's Python environment? If not, what's the install procedure for the snap version?
2. Does the snap sandbox allow CUDA/ROCm GPU access? The HIPEW warning suggests HIP (AMD) isn't loading — is CUDA functional?
3. Should we provide a CPU fallback for users without GPUs? The pipeline currently raises `GPUNotAvailableError`.

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
