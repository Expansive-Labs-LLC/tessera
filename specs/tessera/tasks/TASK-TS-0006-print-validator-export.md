# Task: Print-Readiness Validator & Export Pipeline

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0006 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-03-26 |
| **Assignment Method** | Sprint Planning |
| **Sprint/Iteration** | Phase 1 — Foundation |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P1 | L | Low | Feature | PRD |

---

## Business Context

### Why This Matters
The entire promise of Tessera is "printable output." This task is the gatekeeper — it runs automated validation checks, attempts auto-repair on failures, and only exports when the mesh is genuinely ready for a slicer. Without this, users get broken STLs that waste filament and time.

### Why Now
Needed for Phase 1 exit criteria (M1.6) — "STL export with print-readiness validation." This completes the end-to-end pipeline.

### User Story
**As a** user who wants to 3D print the generated model,  
**I want** the agent to validate that the mesh is printable and automatically fix common issues,  
**So that** I can confidently send the exported file to my slicer without worrying about errors.

### Master PRD Reference
- **PRD Section:** §5.4 Print-Readiness Validator, §7 Output Specification, §9 Phase 1 (M1.6)
- **Strategic Goal:** G3 — Guarantee manifold, watertight, 3D-print-ready; G6 — Export to STL/3MF/OBJ

---

## Initial Requirements

### What Needs to Be Built

#### Validation Checks (from PRD §5.4)
1. **Non-manifold edges** — `bpy.ops.mesh.select_non_manifold()` → auto-repair: fill holes, merge by distance
2. **Self-intersections** — BVH tree overlap test (`mathutils.bvhtree`) → auto-repair: boolean union to self
3. **Zero-area faces** — Face area < ε → auto-repair: dissolve degenerate faces
4. **Minimum wall thickness** — Ray-cast inward; flag if < threshold (1.2 mm FDM / 0.5 mm SLA) → auto-repair: Solidify modifier
5. **Overhang angle** — Face normal vs build-plate > 45° → flag for user; optionally auto-orient
6. **Mesh volume** — Must be > 0 (closed surface) → auto-repair: voxel remesh fallback
7. **Scale sanity** — Bounding box within printer build volume → warn or auto-scale

#### Export Pipeline
8. **STL export** — Binary STL via `bpy.ops.export_mesh.stl()` with mm scale
9. **3MF export** — Basic 3MF via Blender exporter (Phase 4 adds metadata)
10. **OBJ export** — For compatibility
11. **Validation report** — JSON + human-readable summary with pass/warn/fail per check

#### Scale & Orientation
12. **Real-world scaling** — Map mesh to mm using user-specified or inferred dimensions (PRD §5.3 step 4)
13. **Print orientation** — Orient object to minimize supports; flatten bottom face (PRD §5.3 step 5)

### Known Constraints
- Must leverage Blender's built-in 3D Print Toolbox add-on where possible
- Auto-repair must not destroy user edits — operate on a copy if destructive
- Export formats must be properly scaled to mm

### Success Looks Like
User clicks "Export for Print" → validation runs → any issues are auto-repaired or flagged → STL is exported → validation report shows all green. Prints successfully on first attempt.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §5.4 and §7 |
| Blender 3D Print Toolbox | [docs.blender.org](https://docs.blender.org/manual/en/latest/addons/mesh/3d_print_toolbox.html) | Built-in validation tool |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0001 (Add-on Scaffold) | Pending | Blocks this | Needs Blender context + UI |
| TASK-TS-0005 (Mesh Import) | Pending | Blocks this | Needs clean mesh to validate |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spec Approved** | TBD |
| **PR Submitted** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Should auto-repair operate on the original mesh or a copy? Destructive repair (mesh booleans) could surprise users.
   - **Suggested resolution:** Operate on a duplicate named `ObjectName_print`; keep original intact

### For Orchestrator to Add

1. _[Orchestrator adds questions here after reviewing task]_

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
| Ready to begin Spec | ☐ |

**Acknowledged Date:** [Date]  
**Target Spec Submission:** [Date]
