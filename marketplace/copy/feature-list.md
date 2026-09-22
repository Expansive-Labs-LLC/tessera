# Feature List — By Workflow Stage

> Structured feature inventory for listing bullets, comparison tables, and the docs site. Every entry is traceable to an implemented module under `tessera/` (CON-006 — no aspirational claims).

## 1 · Image Input

- Load 1–6 reference images per project (JPEG, PNG)
- Assign view labels (front / back / left / right / top / bottom) to constrain the pose graph
- Automatic view classification via silhouette analysis when labels are omitted
- Low-confidence detections prompt for confirmation rather than guessing
- Background segmentation isolates the subject from cluttered photos
- Phone-camera input tolerated — no studio lighting or turntable required
- Per-image preview and removal inside the Blender sidebar

## 2 · 3D Reconstruction

- Single-image reconstruction from one photo or render
- Few-image reconstruction (2 views) for improved silhouette accuracy
- Multi-view reconstruction (3–6 views) with pose estimation and neural refinement
- Sketch-to-3D pipeline with symmetry priors for hand-drawn input
- Pluggable adapter architecture — reconstruction engines swap without touching the rest of the pipeline
- Automatic adapter selection by available VRAM, image count, and downloaded weights
- Monocular depth estimation to recover surface relief
- DINOv2 feature extraction for shape and symmetry cues
- Graceful degradation to a fallback path when VRAM is tight
- Progress reporting with cancellation during long generations

## 3 · Mesh Processing

- Automatic import of generated geometry into the active Blender scene
- Named object hierarchy — the result is normal, editable Blender geometry
- Merge-by-distance and duplicate vertex removal
- Normal recalculation and consistent winding
- Quad-dominant remeshing for clean topology
- Decimation to a target polygon budget for printable file sizes
- Degenerate and zero-area face dissolution
- Hole filling and watertight repair via voxel remesh fallback
- Cleanup diagnostics reporting what changed and by how much

## 4 · Print Validation

- Non-manifold edge detection with auto-repair
- Self-intersection detection via BVH overlap testing
- Zero-area face detection
- Minimum wall-thickness check (FDM and SLA defaults, user-overridable)
- Overhang-angle analysis against the build-plate normal
- Positive mesh volume (closed surface) verification
- Build-volume fit check against the selected printer profile
- Pass / warn / fail report per check, surfaced in the sidebar before export
- Force-export override for users who want to repair downstream

## 5 · Scaling & Orientation

- Exact millimetre dimension entry on any axis, with proportional lock
- Inferred real-world scale from object type when dimensions aren't given
- Printer profiles with real build volumes — Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, Elegoo Saturn 3
- FDM and SLA wall-thickness presets per profile
- Print orientation optimiser that minimises support material
- Base flattening for bed adhesion
- Over-volume warning with optional auto-scale to fit

## 6 · Refinement

- Natural-language edit commands ("make the base 5 mm thicker", "smooth the edges")
- Spatial region resolution — named regions and geometry selection from plain language
- In-place geometry modification, no regeneration required
- Automatic re-validation after every edit
- Conversation history panel inside Blender
- Undo / redo integration with Blender's own stack

## 7 · Export

- STL export with correct millimetre scaling
- 3MF export with print settings and metadata embedded
- OBJ export for downstream tooling
- `.blend` output retaining full editability
- Export-time validation gate with explicit override
- Printer-profile-aware export defaults

## 8 · Platform & Operations

- 100% local inference — no cloud calls, no API keys, no telemetry
- One-time model weight download with checksum verification and a cache manager
- User-extensible model list — add any compatible Hugging Face checkpoint, licence-classified, commit-pinned and checksum-verified before download
- Added models persist outside the add-on, so they survive updates
- GPU detection and VRAM reporting with actionable failure messages
- Performance profiler and per-stage timing report
- Catalogued, human-readable error codes with documented remedies
- In-panel help linking to the documentation site
- Blender 4.2 LTS through 4.4 compatibility
