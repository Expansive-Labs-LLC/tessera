# Task: Mesh Import, Cleanup & Topology Optimization

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0005 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-03-26 |
| **Assignment Method** | Sprint Planning |
| **Sprint/Iteration** | Phase 1 — Foundation / Phase 2 — Quality |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P1 | L | Low | Feature | PRD |

---

## Business Context

### Why This Matters
AI-generated meshes are universally messy — overlapping faces, non-manifold edges, bad normals, and triangle soup. This task is the "cleanup crew" that transforms raw AI output into printable geometry inside Blender. It's the difference between a file that crashes your slicer and one that prints perfectly.

### Why Now
Bridges Phase 1 (M1.5 — basic import + repair) and Phase 2 (M2.2 — topology optimization). The basic version is needed in Phase 1 for the end-to-end demo; quad remesh and poly-count optimization come in Phase 2.

### User Story
**As a** user who just generated a 3D reconstruction,  
**I want** the mesh to be automatically cleaned up and imported into Blender with proper topology,  
**So that** I can edit it if needed and it's ready for 3D printing without manual repair.

### Master PRD Reference
- **PRD Section:** §5.3 Blender Orchestrator (steps 1–3), §9 Phase 1 (M1.5), Phase 2 (M2.2)
- **Strategic Goal:** G2, G3 — Geometry inside Blender, manifold and print-ready

---

## Initial Requirements

### What Needs to Be Built

#### Phase 1 Scope (basic)
1. **Mesh import** — Import raw mesh (vertices, faces) from reconstruction engine into Blender scene as a new object
2. **Duplicate removal** — `bpy.ops.mesh.remove_doubles()` with configurable merge distance
3. **Normal recalculation** — `bpy.ops.mesh.normals_make_consistent()` to fix inside-out faces
4. **Hole filling** — Detect and fill boundary edges to achieve watertight mesh
5. **Basic remesh** — Voxel remesh as fallback when mesh is too damaged for surgical repair

#### Phase 2 Scope (quality)
6. **Quad remesh** — Convert triangle mesh to quad-dominant topology using Blender's QuadriFlow or Instant Meshes
7. **Poly-count optimization** — Decimate modifier with target face count; preserve sharp edges
8. **Object hierarchy** — Named objects in Blender outliner; proper origin point placement

### Known Constraints
- Must operate entirely via `bpy` API
- Must preserve overall shape fidelity during cleanup — aggressive remesh should be optional
- Target: <5 seconds for cleanup on meshes up to 500K faces

### Success Looks Like
Raw AI mesh goes in → clean, properly-oriented Blender object comes out with no non-manifold edges, consistent normals, and reasonable poly count. User sees the object in the viewport ready for editing.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §5.3 Blender Orchestrator |
| Blender Mesh Ops API | [docs.blender.org/api](https://docs.blender.org/api/current/bpy.ops.mesh.html) | All mesh-level operations |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0001 (Add-on Scaffold) | Pending | Blocks this | Needs Blender context |
| TASK-TS-0004 (Reconstruction) | Pending | Blocks this | Produces raw mesh input |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spec Approved** | TBD |
| **Phase 1 PR** | TBD |
| **Phase 2 PR** | TBD |

---

## Open Questions

### Flagged by CSO

1. Should quad remesh be the default or optional? High-quality quad remesh is slow on complex meshes.
   - **Suggested resolution:** Default to voxel remesh for speed; offer quad remesh as "high quality" option in UI

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
