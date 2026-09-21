# Task: Sketch-to-3D Operator Integration

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0019 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-04-18 |
| **Assignment Method** | Handoff from Pipeline Wiring |
| **Sprint/Iteration** | Phase 2 — Features |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟡 P1 | M | Medium | Feature | SPEC-TS-0010 |

---

## Business Context

### Why This Matters
Sketch-to-3D lets users draw rough sketches instead of uploading photos — a major differentiator. The pipeline code exists (`tessera/sketch/`) but no Blender operator triggers it.

### User Story
**As a** user who prefers sketching over photography,  
**I want** to draw a rough sketch and generate a 3D model from it,  
**So that** I can go from concept to 3D print without needing a photo or modeling skills.

### Master PRD Reference
- **PRD Section:** §5.5 Sketch-to-3D Pipeline
- **Spec:** SPEC-TS-0010

---

## Initial Requirements

### What Needs to Be Built

1. **New Operator** — `TESSERA_OT_SketchGenerate` in `tessera/operators/sketch_ops.py`
   - Opens file browser for sketch images
   - Sets `force_sketch=True` on `ImageInput`
   - Calls sketch pipeline preprocessor then routes to VisionPipeline
   - Imports resulting mesh

2. **UI Integration**
   - Add sketch mode toggle or separate button in the Generation panel
   - Visual indicator for sketch vs photo mode

3. **Operator Registration**
   - Add `sketch_ops` to `tessera/operators/__init__.py`

### Existing Code (already written)
- `tessera/sketch/pipeline.py` — `SketchPipeline.process()`
- `tessera/sketch/preprocessor.py` — line detection, cleanup
- `tessera/sketch/detector.py` — sketch vs photo classification
- `tessera/sketch/symmetry.py` — symmetry axis detection

---

## Context & References

| Document | Location |
|----------|----------|
| Sketch-to-3D Spec | `specs/tessera/feature-spec/active/SPEC-TS-0010-sketch-to-3d.md` |
| Sketch Pipeline | `tessera/sketch/pipeline.py` |
| Vision Pipeline | `tessera/vision/pipeline.py` |

### Dependencies
| Task/Item | Status | Dependency |
|-----------|--------|------------|
| TASK-TS-0016 (Vision Adapter Validation) | Pending | Needed for inference |
| TASK-TS-0017 (Trellis Inference) | Pending | Needed for reconstruction |

---

## Orchestrator Acknowledgment

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Ready to begin | ☐ |

**Acknowledged Date:** [Date]
