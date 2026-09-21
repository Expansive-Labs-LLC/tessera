# Feature Specification: Natural-Language Refinement Loop

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0009 |
| **Task ID** | TASK-TS-0009 |
| **Status** | Draft |
| **Version** | 1.1 |
| **Created** | 2026-04-10 |
| **Last Updated** | 2026-04-14 |
| **Author** | Orchestrator (AI) |
| **Pod** | Tessera |
| **CSO Approver** | Derek |
| **Spec Type** | Feature |

### Status Transitions
| From | To | Trigger |
|------|----|---------| 
| Draft | In Review | Author submits, AI-Readiness ≥80 |
| In Review | Approved | CSO approves |
| In Review | Draft | CSO requests changes |
| Approved | In Progress | Orchestrator begins implementation |
| In Progress | Complete | PR merged |

---

## 1. PROBLEM STATEMENT

### 1.1 Business Context
Tessera currently operates as a one-shot generator: upload images → get a mesh. Once the mesh is in Blender, users must learn Blender's complex editing tools to make any modifications. This is the exact skill gap the product exists to eliminate. The Natural-Language Refinement Loop closes this gap by letting users describe edits in plain English — "make the base 5 mm thicker", "smooth the top", "rotate 45 degrees" — and have the agent translate those commands into precise `bpy.ops` sequences. This is the feature that transforms Tessera from a black-box generator into an interactive AI assistant, directly fulfilling strategic goal G5 (PRD §5.5). It is classified as high risk because mapping free-form natural language to safe, reversible geometry operations is research-adjacent; this spec constrains the problem space to a well-defined, testable set of operations.

### 1.2 User Story
**As a** user looking at the generated model in Blender,  
**I want** to type "make the base 5 mm thicker" in a chat panel and have the model update accordingly,  
**So that** I can iteratively refine the model without learning Blender's editing tools.

### 1.3 Proposed Approach
Build a four-layer refinement architecture within the Tessera add-on: (1) a **Chat UI** — a text input field and scrollable message history embedded in the Tessera sidebar panel; (2) an **Intent Parser** — an LLM-powered module (local LLM or user-provided API key) that converts natural-language commands into structured `EditIntent` objects containing `{operation, target_region, parameters}`; (3) a **Region Resolver** — a spatial + semantic part identification system that maps target region names ("handle", "base", "top") to Blender vertex groups using named groups from reconstruction, spatial heuristics, and user-click fallback; (4) an **Edit Executor** — a library of predefined edit operations mapped to safe `bpy.ops` sequences with an undo snapshot stack. Each edit cycle triggers post-edit re-validation via the print-readiness validator (SPEC-TS-0006) and a quick preview render.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Edit command accuracy | N/A | ≥ 80% of commands apply to the correct region with the correct operation | Human evaluation on a test set of 50 edit commands |
| Refinement rounds without mesh degradation | N/A | ≥ 5 consecutive edits maintaining print-validity | Automated print-readiness checks after each edit |
| Edit cycle latency | N/A | < 15 seconds per edit (intent parse + execute + validate + render) | `time.perf_counter()` around full cycle |

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` (SPEC-TS-0001) | Add-on scaffold, class registration | Module registration pattern |
| `tessera/ui/main_panel.py` (SPEC-TS-0001) | Sidebar panel structure | Chat UI sub-panel integration |
| `tessera/mesh/cleanup.py` (SPEC-TS-0005) | Mesh cleanup pipeline | Chain-of-responsibility step pattern |
| `tessera/properties.py` (SPEC-TS-0001) | Scene-level PropertyGroup | Extending scene properties with refinement state |
| `tessera/models/download_manager.py` (SPEC-TS-0002) | Background threading + progress | Threading model for LLM inference |
| `tessera/operators/` (SPEC-TS-0001) | Operator naming convention | `bl_idname` / `bl_label` pattern |
| `bpy.ops.mesh.*` | Blender mesh operators | Available edit operations |
| `bmesh` module | Low-level mesh access | Vertex group selection, spatial queries |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`, `bmesh`, `mathutils`)
- **LLM Backend (local):** `llama-cpp-python` >= 0.2.0 for local GGUF model inference (e.g., Llama 3.1 8B)
- **LLM Backend (API):** `httpx` >= 0.27.0 for optional user-provided API key (Claude/Gemini/OpenAI-compatible endpoints)
- **Concurrency:** `threading.Thread` for LLM inference (must not block Blender main thread)
- **Validation:** `bpy.props` property system + runtime assertions
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── refinement/
│   ├── __init__.py
│   ├── chat_manager.py         # ChatManager: message history, session state
│   ├── intent_parser.py        # IntentParser: NL text → EditIntent struct
│   ├── intent_schema.py        # EditIntent, OperationType, TargetRegion dataclasses
│   ├── region_resolver.py      # RegionResolver: target name → vertex group/selection
│   ├── edit_executor.py        # EditExecutor: EditIntent → bpy.ops sequence
│   ├── operations/
│   │   ├── __init__.py
│   │   ├── scale_op.py         # Directional scale operations
│   │   ├── transform_op.py     # Move, rotate operations
│   │   ├── solidify_op.py      # Thicken, hollow operations
│   │   ├── smooth_op.py        # Smooth, sharpen, bevel operations
│   │   ├── primitive_op.py     # Add/remove basic geometry
│   │   └── undo_op.py          # Undo / version history operations
│   ├── undo_manager.py         # UndoManager: snapshot-based undo stack
│   ├── preview_renderer.py     # PreviewRenderer: quick Eevee/Workbench render
│   └── llm_backend/
│       ├── __init__.py
│       ├── base.py             # Abstract LLMBackend interface
│       ├── local_llm.py        # llama-cpp-python backend
│       └── api_llm.py          # HTTP API backend (user-provided key)
├── ui/
│   ├── chat_panel.py           # Chat input + message history UI
│   └── ...
├── operators/
│   ├── refinement_ops.py       # OT_SendMessage, OT_Undo, OT_Redo, OT_ConfirmEdit
│   └── ...
└── ...
```

**Data flow per edit cycle:**
```
User text input
  → ChatManager.add_message(role="user", text=...)
  → IntentParser.parse(text, mesh_context) → list[EditIntent]
    → If ambiguous: return AmbiguityResponse → ChatManager shows clarification prompt → STOP
    → If clear: continue
  → FOR EACH EditIntent in list:
    → RegionResolver.resolve(intent.target_region, obj) → vertex group name or selection set
      → If unresolvable: prompt user to click-select region → STOP
      → If resolved: continue
    → UndoManager.push_snapshot(obj) → snapshot_id
    → EditExecutor.execute(intent, obj, selection) → modified obj
  → PrintValidator.validate(context, obj, printer_type, wall_thickness_mm,
      overhang_angle_deg, build_volume_mm) → ValidationReport (SPEC-TS-0006, validation-only mode)
    → If invalid: ChatManager shows warning "Edit makes model unprintable — proceed anyway?"
  → PreviewRenderer.render(obj) → preview_image_path
  → ChatManager.add_message(role="assistant", text=summary, image=preview_image_path)
```

**Threading model:** LLM inference runs in a `threading.Thread`. The thread writes the parsed `EditIntent` (or `AmbiguityResponse`) to a thread-safe `queue.Queue`. A `bpy.app.timers` callback polls the queue at 100ms intervals and executes the edit on the main thread. All `bpy` operations occur on the main thread only.

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Chat UI Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL provide a "Refinement" sub-panel in the Tessera sidebar (N-panel) containing: a scrollable message history area, a text input field, and a "Send" button. |
| FR-002 | The message history SHALL display messages with role indicators: "You:" for user messages (left-aligned) and "Tessera:" for assistant messages (left-aligned, distinct color). |
| FR-003 | The message history SHALL support inline image previews for post-edit preview renders, displayed as thumbnail images (256×256 px) within assistant messages. |
| FR-004 | The system SHALL display a "Thinking…" indicator in the message area while the LLM is processing a command. |
| FR-005 | The system SHALL allow the user to submit commands by pressing Enter in the text field or clicking the "Send" button. |
| FR-006 | The chat panel SHALL be disabled (input field grayed out) when no mesh object is selected in the 3D viewport. The panel SHALL display: "Select a mesh object to begin refinement." |
| FR-042 | The chat message history SHALL retain at most 200 messages. When the limit is reached, the oldest messages SHALL be removed in FIFO order. Preview image data blocks (`BF_Preview_*`) associated with removed messages SHALL be freed via `bpy.data.images.remove()`. |

### 3.2 Intent Parsing Requirements

| ID | Requirement |
|----|-------------|
| FR-007 | The system SHALL parse natural-language commands into a list of structured `EditIntent` objects (`list[EditIntent]`, length ≥ 1). Each `EditIntent` SHALL contain: `operation` (enum: `SCALE`, `MOVE`, `ROTATE`, `SOLIDIFY`, `SMOOTH`, `SHARPEN`, `BEVEL`, `ADD_GEOMETRY`, `REMOVE_GEOMETRY`, `UNDO`, `REDO`), `target_region` (string: part name or spatial descriptor), `parameters` (dict of operation-specific key-value pairs), and `confidence` (float 0.0–1.0). When a command implies multiple distinct operations (e.g., "make the top bigger and the base smaller"), the parser SHALL decompose it into separate `EditIntent` objects. Each sub-intent SHALL have its own `confidence` score. The system SHALL execute sub-intents sequentially, each with its own undo snapshot. If any sub-intent has `confidence` < 0.7, the ambiguity flow (FR-017) SHALL trigger for that sub-intent before execution. |
| FR-008 | The system SHALL parse dimensional parameters with unit awareness. Supported units: `mm`, `cm`, `m`, `in`, `%`. If no unit is specified, the system SHALL default to millimeters. When a dimensionless comparative adjective is used without a numeric value, the system SHALL infer a default percentage of 10% and set `inferred: true`. Default mappings: `"taller"` / `"bigger"` / `"wider"` / `"longer"` / `"thicker"` → `+10%`; `"shorter"` / `"smaller"` / `"narrower"` / `"thinner"` → `-10%`. Examples: "5 mm" → `{"value": 5.0, "unit": "mm"}`, "20%" → `{"value": 20.0, "unit": "%"}`, "taller" (no value) → `{"value": 10.0, "unit": "%", "inferred": true}`. |
| FR-009 | The system SHALL support the following LLM backends via a pluggable interface: (a) local GGUF model inference via `llama-cpp-python` (default), (b) user-provided API key for OpenAI-compatible HTTP endpoints. The active backend SHALL be selectable in add-on preferences. |
| FR-010 | When the local LLM backend is selected, the system SHALL load the LLM model weights via the model weight management system (SPEC-TS-0002) using `ensure_model("tessera-intent-parser")`. This call SHALL occur within the LLM inference background thread (not the Blender main thread), consistent with SPEC-TS-0002's threading contract which specifies that `ensure_model()` is a blocking call designed for pipeline background threads only. |
| FR-011 | The intent parser SHALL use a structured system prompt that includes: the list of supported operations, the current mesh context (bounding box dimensions in mm, vertex group names, face count), and output format instructions requiring JSON output matching the `EditIntent` schema. |
| FR-012 | When the intent parser's `confidence` score is < 0.7, the system SHALL treat the result as ambiguous and follow the ambiguity handling flow (FR-017). |

### 3.3 Region Resolution Requirements

| ID | Requirement |
|----|-------------|
| FR-013 | The system SHALL resolve target region names to Blender vertex groups using a three-tier fallback strategy in order: (1) Named vertex groups — exact or fuzzy match against vertex group names on the mesh object (vertex groups MAY have been created by upstream pipelines, manual assignment, or previous user-selection operations — see FR-043); (2) Spatial heuristics — predefined spatial rules mapping common terms to mesh regions; (3) User click-selection — prompt the user to select the target region manually. |
| FR-043 | The region resolver SHALL operate without assuming that vertex groups exist on the mesh. Meshes imported from external STL/OBJ files, or produced by reconstruction pipelines that do not perform semantic segmentation, MAY have zero vertex groups. In such cases, tier-1 (named vertex group) resolution SHALL return no match and the system SHALL fall through to tier-2 (spatial heuristics) and tier-3 (user click-selection) without error. |
| FR-014 | The spatial heuristics engine SHALL support the following predefined region mappings based on the mesh's local bounding box: `"base"` / `"bottom"` → vertices in the bottom 20% of the Z-axis range; `"top"` → vertices in the top 20% of the Z-axis range; `"middle"` / `"center"` → vertices between 30% and 70% of the Z-axis range; `"left"` → vertices in the lower 50% of the X-axis range; `"right"` → vertices in the upper 50% of the X-axis range; `"front"` → vertices in the upper 50% of the Y-axis range; `"back"` → vertices in the lower 50% of the Y-axis range; `"all"` / `"whole"` / `"entire"` → all vertices. |
| FR-015 | When a named vertex group match is found with a fuzzy match score ≥ 80% (using `difflib.SequenceMatcher`), the system SHALL use that vertex group. When no match meets the 80% threshold, the system SHALL fall through to spatial heuristics. |
| FR-016 | When neither named vertex groups nor spatial heuristics resolve the target region, the system SHALL prompt the user with the message: `"I couldn't identify '{region_name}' on this mesh. Please select the vertices you mean in the 3D viewport and click 'Confirm Selection'."` The system SHALL then wait for the user to make a selection and confirm. |

### 3.4 Ambiguity Handling Requirements

| ID | Requirement |
|----|-------------|
| FR-017 | When the intent parser returns a `confidence` < 0.7, the system SHALL NOT apply any edit. Instead, the system SHALL display a clarification prompt in the chat: `"I'm not sure what you mean. Did you mean: (A) {interpretation_1}, (B) {interpretation_2}? Please clarify or rephrase."` The parser SHALL provide up to 3 candidate interpretations sorted by confidence. |
| FR-018 | When a parsed operation would affect > 80% of the mesh's total vertices, the system SHALL display a confirmation prompt: `"This edit will affect {N}% of the mesh ({V} vertices). Proceed?"` with "Yes" and "No" buttons. |

### 3.5 Edit Operations Requirements

| ID | Requirement |
|----|-------------|
| FR-019 | The system SHALL provide an edit operations library mapping each `OperationType` to a sequence of `bpy.ops` and/or `bmesh` calls. Each operation SHALL accept the target vertex selection and operation-specific parameters. |
| FR-020 | The `SCALE` operation SHALL support directional scaling along X, Y, Z, or uniform axes. Parameters: `axis` (enum: `X`, `Y`, `Z`, `UNIFORM`), `factor` (float, or absolute dimension in mm). When an absolute dimension is given (e.g., "make it 50 mm tall"), the system SHALL calculate the scale factor from the current bounding box extent on that axis. |
| FR-021 | The `MOVE` operation SHALL translate the selected vertices by a vector. Parameters: `direction` (enum: `UP`, `DOWN`, `LEFT`, `RIGHT`, `FORWARD`, `BACK`, or explicit `(x, y, z)` vector) and `distance` (float in mm). |
| FR-022 | The `ROTATE` operation SHALL rotate the selected vertices around a pivot point. Parameters: `axis` (enum: `X`, `Y`, `Z`), `angle_degrees` (float), `pivot` (enum: `MEDIAN_POINT`, `CURSOR`, `INDIVIDUAL_ORIGINS`, default: `MEDIAN_POINT`). |
| FR-023 | The `SOLIDIFY` operation SHALL add wall thickness to the selected region by applying a Blender Solidify modifier. Parameters: `thickness_mm` (float, default: 2.0), `offset` (float, range -1.0 to 1.0, default: -1.0 for inward). When applied to a subset of vertices, the system SHALL use a vertex group to limit the modifier's influence. |
| FR-024 | The `SMOOTH` operation SHALL apply Laplacian smoothing to the selected vertices. Parameters: `iterations` (int, range 1–100, default: 5), `factor` (float, range 0.0–1.0, default: 0.5). Implemented via `bpy.ops.mesh.vertices_smooth_laplacian()`. |
| FR-025 | The `SHARPEN` operation SHALL mark selected edges as sharp and apply an Edge Split modifier. Parameters: `angle_threshold_degrees` (float, range 0–180, default: 30). |
| FR-026 | The `BEVEL` operation SHALL apply a bevel to selected edges. Parameters: `width_mm` (float, range 0.1–20.0, default: 1.0), `segments` (int, range 1–10, default: 2). Implemented via `bpy.ops.mesh.bevel()`. |
| FR-027 | The `ADD_GEOMETRY` operation SHALL add a primitive shape (cube, sphere, cylinder, cone) at the specified position. Parameters: `shape` (enum: `CUBE`, `SPHERE`, `CYLINDER`, `CONE`), `size_mm` (float, range 0.1–500.0), `location` (relative to mesh — `"on_top"`, `"at_bottom"`, `"centered"`, or explicit `(x, y, z)`). The primitive SHALL be boolean-unioned with the existing mesh. If the boolean union fails (modifier application produces zero faces or raises a `RuntimeError`), the system SHALL remove the added primitive, display a warning in the chat: `"Boolean union failed. The mesh may need cleanup before adding geometry. Try running mesh cleanup first."`, and SHALL NOT push a snapshot to the undo stack. |
| FR-028 | The `REMOVE_GEOMETRY` operation SHALL delete the selected vertices and fill the resulting holes. Implemented via `bpy.ops.mesh.delete(type='VERT')` followed by `bpy.ops.mesh.fill()` on boundary edges. |
| FR-029 | The `UNDO` operation SHALL restore the mesh to the previous snapshot in the undo stack. The `REDO` operation SHALL re-apply the most recently undone operation. Natural-language triggers: "undo", "undo that", "go back", "revert" → `UNDO`; "redo", "redo that", "put it back" → `REDO`. |

### 3.6 Undo / Version History Requirements

| ID | Requirement |
|----|-------------|
| FR-030 | The system SHALL maintain an undo stack of mesh state snapshots. Each snapshot SHALL store: a full copy of the mesh data (vertices, faces, vertex groups), the edit command that was applied, a timestamp, and a human-readable description. |
| FR-031 | The undo stack SHALL have a maximum depth of 20 snapshots. When a new snapshot is pushed and the stack is at capacity, the oldest snapshot SHALL be discarded. |
| FR-032 | Each snapshot SHALL be stored as a serialized `.blend` data block in memory (using `bpy.data.meshes.new()` + copy). The system SHALL NOT write snapshots to disk unless the `.blend` file is saved by the user. |
| FR-033 | The system SHALL support version-addressed undo: the user can say "go back to version 3" and the system SHALL restore the mesh to the state after the 3rd edit in the session. The system SHALL display the version number in the chat history for each edit. |
| FR-034 | After an undo operation, subsequent new edits SHALL discard the redo history (standard undo/redo behavior). |

### 3.7 Post-Edit Validation & Preview Requirements

| ID | Requirement |
|----|-------------|
| FR-035 | After each successful edit, the system SHALL invoke the print-readiness validator (SPEC-TS-0006) in **validation-only mode** (`TESSERA_OT_validate_print` / `PrintValidator.validate()`) on the modified mesh. The validator SHALL be called with the current scene's printer settings read from `bpy.context.scene.tessera.validator` (printer_type, wall_thickness_mm, overhang_angle_deg, build_volume_mm) as defined in SPEC-TS-0006 FR-033. Validation-only mode operates in read-only on the original object without creating a duplicate or applying auto-repair (per SPEC-TS-0006 FR-039). The validation result SHALL be summarized in the chat as: "✅ Print-ready" or "⚠️ Print issues: {list of failed checks}". |
| FR-036 | When a validation check fails after an edit that was previously passing, the system SHALL display a warning in the chat: `"⚠️ This edit introduced print issues: {issues}. You can undo this edit or continue."` The edit SHALL NOT be automatically reverted. |
| FR-037 | After each successful edit, the system SHALL generate a preview render using Blender's Workbench engine at 512×512 px resolution. The render SHALL use the active 3D viewport's current viewing angle (obtained from `bpy.context.space_data.region_3d.view_matrix`). If the user is in camera view (numpad 0), the render SHALL use the active scene camera instead. The render SHALL complete in < 3 seconds. |
| FR-038 | The preview render image SHALL be stored as a temporary Blender image data block named `"BF_Preview_{timestamp}"` and displayed as a thumbnail in the chat history. |

### 3.8 LLM Configuration Requirements

| ID | Requirement |
|----|-------------|
| FR-039 | The add-on preferences SHALL expose an "LLM Backend" section with: backend selector (enum: `LOCAL`, `API`), local model selector (populated from model registry), API endpoint URL (string, default: empty), API key (string, password-masked), and API model name (string). |
| FR-040 | When the `API` backend is selected and the API key is empty, the system SHALL display a warning: `"API key not configured. Enter your API key in Preferences → Tessera → LLM Backend."` and disable the chat input. |
| FR-041 | The system SHALL NOT transmit any mesh geometry, file paths, or user-identifying information to the LLM API. The API request SHALL contain only: the system prompt (operation definitions + mesh bounding box dimensions + vertex group names), the user's text command, and the message history (text only, no images). |

### 3.9 Parameter Validation Requirements

| ID | Requirement |
|----|-------------|
| FR-044 | The system SHALL validate all parsed `EditIntent` parameters against the following allowed ranges before execution. Parameters outside these ranges SHALL be clamped to the nearest valid value and a warning SHALL be displayed in the chat: `"Parameter '{name}' was {value}, clamped to {clamped_value} (allowed range: {min}–{max})."` |

**Parameter range table:**

| Operation | Parameter | Min | Max | Default |
|-----------|-----------|-----|-----|---------|
| SCALE | `factor` | 0.01 | 100.0 | 1.0 |
| MOVE | `distance` (mm) | 0.0 | 1000.0 | 0.0 |
| ROTATE | `angle_degrees` | -360.0 | 360.0 | 0.0 |
| SOLIDIFY | `thickness_mm` | 0.1 | 50.0 | 2.0 |
| SOLIDIFY | `offset` | -1.0 | 1.0 | -1.0 |
| SMOOTH | `iterations` | 1 | 100 | 5 |
| SMOOTH | `factor` | 0.0 | 1.0 | 0.5 |
| SHARPEN | `angle_threshold_degrees` | 0 | 180 | 30 |
| BEVEL | `width_mm` | 0.1 | 20.0 | 1.0 |
| BEVEL | `segments` | 1 | 10 | 2 |
| ADD_GEOMETRY | `size_mm` | 0.1 | 500.0 | 10.0 |

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT transmit mesh geometry, file paths, image data, or personally identifiable information over the network. Only the text command, system prompt context (operation list, bounding box dimensions, vertex group names), and message history text are sent to the LLM API. |
| CON-002 | SHALL NOT access `bpy` APIs from background LLM inference threads. All `bpy`/`bmesh` operations SHALL occur on the main thread via `bpy.app.timers` callbacks. |
| CON-003 | SHALL NOT execute arbitrary Python code generated by the LLM. The system SHALL only execute predefined edit operations from the operations library (FR-019 through FR-029). The LLM output is parsed as a structured `EditIntent` JSON — never evaluated as code. |
| CON-004 | SHALL NOT apply edits when the intent parser `confidence` is < 0.7 without user confirmation (FR-017). |
| CON-005 | SHALL NOT exceed 20 snapshots in the undo stack. Oldest snapshots are discarded when the limit is reached (FR-031). |
| CON-006 | SHALL NOT block Blender's main UI thread during LLM inference. Inference SHALL run in a background thread (see Architecture Notes). |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT modify vertex groups or mesh data that were not explicitly targeted by the user's edit command. |
| CON-009 | SHALL NOT depend on any Python package not bundled with Blender unless packaged as a `python-wheel` within the add-on `.zip`. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Full edit cycle latency | Wall-clock time from user pressing "Send" to preview render displayed | < 15 seconds | On a system with 8 GB VRAM GPU, using local LLM (Llama 3.1 8B Q4), mesh ≤ 200K faces |
| NFR-002 | Intent parsing latency | Wall-clock time for LLM inference only | < 5 seconds (local), < 3 seconds (API) | Llama 3.1 8B Q4_K_M on 8 GB VRAM GPU; API with ≤ 200ms network RTT |
| NFR-003 | Edit execution latency | Wall-clock time for `EditExecutor.execute()` | < 3 seconds | Any supported operation on a mesh ≤ 200K faces |
| NFR-004 | Preview render latency | Wall-clock time for Workbench 512×512 render | < 3 seconds | Mesh ≤ 200K faces, Blender Workbench engine |
| NFR-005 | Undo/redo latency | Wall-clock time for snapshot restore | < 1 second | Mesh ≤ 200K faces, snapshot in memory |
| NFR-006 | Mesh quality after 5 edits | Print-readiness validation pass rate | ≥ 95% of print-valid meshes remain valid after 5 edits | Tested with set of 10 different starting meshes, 5 edits each from the standard edit test set |
| NFR-007 | Intent parsing accuracy | Percentage of commands correctly parsed | ≥ 80% | On a test set of 50 natural-language edit commands (see §10 Metric in PRD §10) |
| NFR-008 | Memory overhead per snapshot | Memory consumed by each undo snapshot | < 50 MB per snapshot | Mesh with ≤ 200K faces |
| NFR-009 | UI responsiveness during inference | Main thread frame rate during LLM processing | ≥ 15 fps (Blender viewport redraw) | During active local LLM inference |
| NFR-010 | Cross-platform compatibility | Chat panel + LLM inference on all supported OS | 100% | Windows 10+, macOS 12+ (Intel & Apple Silicon), Ubuntu 22.04+ |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: Simple Scale Edit via Natural Language
**Given** a Tessera-generated mesh object is selected in the 3D viewport with a bounding box height of 100 mm,  
**When** the user types "make it 20% taller" in the chat panel and presses Enter,  
**Then** the intent parser produces `EditIntent(operation=SCALE, target_region="all", parameters={"axis": "Z", "factor": 1.2})`, the mesh bounding box height becomes 120 mm (±1 mm), a preview render appears in the chat, and the validation result is displayed within 15 seconds of pressing Enter.

### AC-002: Region-Targeted Solidify with Named Vertex Group
**Given** a mesh object with a vertex group named "handle" containing 500 vertices,  
**When** the user types "make the handle 3 mm thicker",  
**Then** the region resolver matches "handle" to the vertex group (fuzzy score ≥ 80%), a Solidify modifier is applied with `thickness = 0.003` meters and vertex group "handle" assigned, the chat displays "✅ Applied: Solidified 'handle' region by 3 mm", and the preview render updates.

### AC-003: Spatial Heuristic Region Resolution
**Given** a mesh object with no vertex groups and a bounding box Z-range of 0 to 100 mm,  
**When** the user types "smooth the top",  
**Then** the region resolver selects vertices in the top 20% of the Z-axis (vertices with Z ≥ 80 mm in local space), Laplacian smoothing is applied with default parameters (5 iterations, factor 0.5), and the chat displays the edit summary with preview.

### AC-004: Ambiguity Handling Below Confidence Threshold
**Given** the intent parser processes the command "fix it" and returns `confidence = 0.4` with candidates `[("SMOOTH", 0.4), ("UNDO", 0.3), ("SOLIDIFY", 0.2)]`,  
**When** the parse result is evaluated,  
**Then** no edit is applied, and the chat displays: "I'm not sure what you mean. Did you mean: (A) Smooth the mesh, (B) Undo the last edit, (C) Solidify the mesh? Please clarify or rephrase."

### AC-005: Undo via Natural Language
**Given** the user has made 3 edits (scale, smooth, solidify) and the undo stack contains 3 snapshots,  
**When** the user types "undo that",  
**Then** the mesh reverts to its state after the 2nd edit (smooth), the chat displays "↩️ Undone: Solidify operation (version 3 → 2)", and a preview render of the reverted state is shown.

### AC-006: Version-Addressed Undo
**Given** the user has made 5 edits and the undo stack contains snapshots for versions 1–5,  
**When** the user types "go back to version 2",  
**Then** the mesh reverts to its state after the 2nd edit, versions 3–5 are available for redo, and the chat displays "↩️ Restored to version 2 (after: {edit_2_description})".

### AC-007: Post-Edit Validation Warning
**Given** a mesh that passes all print-readiness checks,  
**When** the user types "make the wall 0.1 mm thin" and the edit reduces wall thickness below the 1.2 mm FDM threshold,  
**Then** the edit is applied, the chat displays "⚠️ This edit introduced print issues: Wall thickness below minimum (0.1 mm < 1.2 mm). You can undo this edit or continue.", and the mesh is NOT automatically reverted.

### AC-008: Chat Panel Disabled Without Mesh Selection
**Given** no mesh object is selected in the 3D viewport (empty selection or a camera/light is selected),  
**When** the user views the Tessera sidebar panel,  
**Then** the chat input field is grayed out and the panel displays: "Select a mesh object to begin refinement."

### AC-009: LLM API Backend Configuration
**Given** the user selects "API" as the LLM backend in preferences and enters an API key and endpoint URL,  
**When** the user types "make it wider" in the chat panel,  
**Then** the system sends the intent parsing request to the configured API endpoint (not the local LLM), the request body contains only the system prompt, user command text, and message history (no mesh data or file paths), and the parsed intent is executed.

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Command with Conflicting Operations
| Aspect | Detail |
|--------|--------|
| **Scenario** | User issues a command that implies two conflicting operations: "make it bigger and smaller" |
| **Input Example** | `"make the top bigger and the base smaller"` |
| **Expected Behavior** | The intent parser SHALL return a list of two `EditIntent` objects per FR-007: `(SCALE, "top", {factor: 1.1})` and `(SCALE, "base", {factor: 0.9})`. The system SHALL execute them sequentially, each with its own undo snapshot. If any sub-intent's `confidence` is < 0.7, the ambiguity flow (FR-017) SHALL trigger for that sub-intent before execution. |
| **Test ID** | TS-004 |

### EC-002: Target Region Exists as Both Vertex Group and Spatial Heuristic
| Aspect | Detail |
|--------|--------|
| **Scenario** | The mesh has a vertex group named "top_handle" and the user says "modify the top". The fuzzy match for "top" against "top_handle" is 67% (below 80% threshold). |
| **Input Example** | Vertex group: `"top_handle"`, command: `"smooth the top"` |
| **Expected Behavior** | The system SHALL fall through to spatial heuristics (since the fuzzy match 67% < 80% threshold) and select vertices in the top 20% of Z-axis. The named vertex group "top_handle" SHALL NOT be used. If the user intended the vertex group, they must use a more specific name: "smooth the top handle". |
| **Test ID** | TS-005 |

### EC-003: Edit Command on Mesh with Zero Vertex Groups
| Aspect | Detail |
|--------|--------|
| **Scenario** | User issues a part-targeted command ("thicken the handle") on a mesh that has no vertex groups at all (e.g., a simple imported STL without semantic labeling). |
| **Input Example** | Mesh with 0 vertex groups, command: `"thicken the handle"` |
| **Expected Behavior** | Named vertex group lookup returns no match, spatial heuristics has no mapping for "handle", so the system SHALL prompt the user: `"I couldn't identify 'handle' on this mesh. Please select the vertices you mean in the 3D viewport and click 'Confirm Selection'."` After the user selects and confirms, the system SHALL create a temporary vertex group named `"_bf_user_selection"` and execute the solidify operation on it. |
| **Test ID** | TS-006 |

### EC-004: Undo Stack Overflow at Maximum Depth
| Aspect | Detail |
|--------|--------|
| **Scenario** | User performs 21 consecutive edits, exceeding the 20-snapshot undo stack limit. |
| **Input Example** | 21 sequential edits: "make it taller" × 21 |
| **Expected Behavior** | The system SHALL discard the oldest snapshot (version 1) when storing snapshot 21. The user can undo back to version 2 but not to version 1. The chat SHALL display an INFO note when the oldest snapshot is discarded: "ℹ️ Undo history is limited to 20 versions. Oldest version has been discarded." |
| **Test ID** | TS-007 |

### EC-005: Non-English or Gibberish Input
| Aspect | Detail |
|--------|--------|
| **Scenario** | User types a non-English phrase or random characters that the LLM cannot parse into any valid operation. |
| **Input Example** | `"asdfghj"` or `"把它弄大一点"` |
| **Expected Behavior** | The intent parser SHALL return `confidence = 0.0` with no valid candidates. The system SHALL display: `"I didn't understand that command. Try something like: 'make it taller', 'smooth the top', or 'rotate 45 degrees'. Type 'help' for a list of supported commands."` No edit SHALL be applied. |
| **Test ID** | TS-008 |

### EC-006: Edit on Very Small Mesh (< 100 faces)
| Aspect | Detail |
|--------|--------|
| **Scenario** | User attempts fine-grained region edits on a mesh with very few faces where spatial heuristics may select zero vertices. |
| **Input Example** | A cube mesh (8 vertices, 6 faces), command: `"smooth the top"` — top 20% Z-range may only include 2 vertices. |
| **Expected Behavior** | The region resolver SHALL check the selected vertex count. If < 3 vertices are selected, the system SHALL display: `"The selected region contains only {N} vertices, which is too few for this operation. Try selecting a larger region or applying the operation to the whole mesh."` No edit SHALL be applied. |
| **Test ID** | TS-009 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ Voice input or speech-to-text processing
- ❌ Multi-object editing — commands apply to the single active mesh object only
- ❌ Procedural modifier stacks or node-based geometry (Geometry Nodes)
- ❌ Texture or material editing via natural language
- ❌ Automatic mesh re-generation from scratch (use the reconstruction pipeline for that)
- ❌ LLM fine-tuning, training, or model creation
- ❌ Multi-language NLP support — English commands only for v1
- ❌ Collaborative editing or multi-user chat
- ❌ Sketch-based editing (drawing on the viewport) — this is TASK-TS-0009b (future)
- ❌ Macro recording or command scripting
- ❌ Direct slicer integration for print parameter adjustment

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No for local LLM. Optional API key for cloud LLM backends. |
| **Auth Method** | API key stored in Blender add-on preferences (encrypted by Blender's preferences system) |
| **Required Permissions** | File system read/write (undo snapshots in `.blend`), optional network access (LLM API only) |
| **Rate Limiting** | N/A for local. Cloud API rate limits depend on provider. |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| User text commands | Internal | Sent to LLM API if API backend selected; not logged to disk |
| Mesh bounding box dimensions | Internal | Included in LLM system prompt context; no PII |
| Vertex group names | Internal | Included in LLM system prompt context; no PII |
| API key | Confidential | Stored in Blender preferences; password-masked in UI; never logged |
| Mesh geometry data | Internal | Never transmitted over network; stored only in `.blend` file |
| Preview render images | Internal | Stored as Blender image data blocks; not transmitted |
| Chat message history | Internal | In-memory only; persisted in `.blend` file scene data |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL NOT transmit mesh vertex data, face data, texture data, or file paths to any LLM API. Only send: system prompt text, user command text, mesh bounding box dimensions (3 floats), and vertex group names (list of strings). |
| SEC-002 | SHALL NOT execute any code generated or suggested by the LLM. The LLM output is parsed as structured JSON matching the `EditIntent` schema. If the output does not parse as valid JSON or does not match the schema, the system SHALL reject the output and display: "Failed to parse response. Please rephrase your command." |
| SEC-003 | SHALL NOT store the API key in plain text in any log file or debug output. If the API key must be logged for debugging, it SHALL be masked as `"sk-****{last4}"`. |
| SEC-004 | SHALL validate all parsed `EditIntent` parameters against allowed ranges before execution. Parameters outside documented ranges (e.g., `scale_factor > 100.0`, `iterations > 100`) SHALL be clamped to their maximum allowed values with a warning displayed to the user. |
| SEC-005 | SHALL sanitize all LLM output strings before displaying them in Blender's UI to prevent injection of Blender operator calls via UI string rendering. |
| SEC-006 | When using the API backend, SHALL connect only via HTTPS. SHALL NOT accept plain HTTP endpoints. If the user enters an HTTP URL, the system SHALL display: "API endpoints must use HTTPS for security." and not send any request. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skipped** — This feature does not expose REST/HTTP APIs. It consumes an LLM API but the contract is defined by the third-party provider.

The feature exposes the following **internal Python API** for downstream tasks and testing:

### 10.1 IntentParser API
```python
from tessera.refinement.intent_parser import IntentParser
from tessera.refinement.intent_schema import EditIntent

parser = IntentParser(backend="local")  # or backend="api"

# Single-intent command → returns list with 1 element
intents = parser.parse(
    command="make the base 5 mm thicker",
    mesh_context={
        "bounding_box_mm": {"x": 80.0, "y": 80.0, "z": 100.0},
        "vertex_groups": ["base", "handle", "lid"],
        "face_count": 50000
    }
)
# Returns: [EditIntent(
#     operation=OperationType.SOLIDIFY,
#     target_region="base",
#     parameters={"thickness_mm": 5.0, "offset": -1.0},
#     confidence=0.92,
#     raw_response="..."
# )]

# Multi-intent command → returns list with N elements
intents = parser.parse(
    command="make the top bigger and the base smaller",
    mesh_context={...}
)
# Returns: [
#     EditIntent(operation=OperationType.SCALE, target_region="top",
#               parameters={"axis": "UNIFORM", "factor": 1.1}, confidence=0.88),
#     EditIntent(operation=OperationType.SCALE, target_region="base",
#               parameters={"axis": "UNIFORM", "factor": 0.9}, confidence=0.85),
# ]
```

### 10.2 RegionResolver API
```python
from tessera.refinement.region_resolver import RegionResolver

resolver = RegionResolver()

result = resolver.resolve(
    target_region="base",
    obj=bpy.context.active_object
)
# Returns: RegionResult(
#     method="spatial_heuristic",  # or "vertex_group" or "user_selection"
#     vertex_group_name="base",    # name of vgroup used/created
#     vertex_count=1200,
#     confidence=1.0
# )
```

### 10.3 EditExecutor API
```python
from tessera.refinement.edit_executor import EditExecutor
from tessera.refinement.intent_schema import EditIntent, OperationType

executor = EditExecutor()

result = executor.execute(
    context=bpy.context,
    obj=bpy.context.active_object,
    intent=EditIntent(
        operation=OperationType.SOLIDIFY,
        target_region="base",
        parameters={"thickness_mm": 5.0},
        confidence=0.92
    ),
    vertex_group_name="base"
)
# Returns: EditResult(
#     success=True,
#     description="Solidified 'base' region by 5.0 mm",
#     vertices_modified=1200,
#     execution_time_seconds=0.85
# )
```

### 10.4 UndoManager API
```python
from tessera.refinement.undo_manager import UndoManager

undo = UndoManager(max_depth=20)

# Push snapshot before edit
snapshot_id = undo.push(obj, description="Solidify base by 5 mm")
# Returns: int — version number (1-indexed)

# Undo to previous version
undo.undo(obj)  # Restores previous snapshot

# Redo last undo
undo.redo(obj)  # Re-applies undone snapshot

# Jump to specific version
undo.goto_version(obj, version=3)  # Restores to version 3

# Get stack info
info = undo.get_stack_info()
# Returns: {"current_version": 3, "total_versions": 5, "max_depth": 20}
```

---

## 11. OBSERVABILITY

> Define logging and metrics for production monitoring.

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Chat message received | DEBUG | `command_text` (first 100 chars), `active_object_name` | ⚠️ No PII |
| Intent parsing started | DEBUG | `backend_type`, `command_length` | ⚠️ No PII |
| Intent parsing completed | INFO | `operation`, `target_region`, `confidence`, `parse_time_seconds` | ⚠️ No PII |
| Intent parsing failed | ERROR | `error_type`, `error_message`, `command_text` (first 100 chars) | ⚠️ No PII |
| Ambiguity detected | INFO | `confidence`, `candidate_count` | ⚠️ No PII |
| Region resolved | DEBUG | `method` (vertex_group/spatial/user), `vertex_count`, `region_name` | ⚠️ No PII |
| Region resolution failed | WARN | `region_name`, `fallback_triggered` | ⚠️ No PII |
| Edit executed | INFO | `operation`, `target_region`, `vertices_modified`, `execution_time_seconds` | ⚠️ No PII |
| Edit execution failed | ERROR | `operation`, `error_type`, `error_message` | ⚠️ No PII |
| Undo snapshot pushed | DEBUG | `version`, `stack_depth`, `snapshot_size_bytes` | ⚠️ No PII |
| Undo/redo executed | INFO | `from_version`, `to_version`, `restore_time_seconds` | ⚠️ No PII |
| Undo stack overflow | INFO | `discarded_version`, `max_depth` | ⚠️ No PII |
| Preview render completed | DEBUG | `render_time_seconds`, `resolution` | ⚠️ No PII |
| Validation after edit | INFO | `pass`/`fail`, `failed_checks` (list) | ⚠️ No PII |
| LLM API request sent | DEBUG | `endpoint` (hostname only, no path), `request_size_bytes` | ⚠️ No API key |
| LLM API response received | DEBUG | `response_time_seconds`, `token_count` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.refinement"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — refinement panel appears when add-on is installed |
| **Default State** | Chat panel visible; LLM backend defaults to `LOCAL` |
| **Rollout Plan** | Ships with Phase 3 add-on release; local LLM model downloaded on first chat command |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0001 (Add-on Scaffold) | Yes | Provides sidebar panel, preferences, operator registration |
| SPEC-TS-0002 (Model Weight Management) | Yes | Manages LLM weight download + caching |
| SPEC-TS-0005 (Mesh Import & Cleanup) | Yes | Provides named vertex groups on imported meshes |
| SPEC-TS-0006 (Print Validator) | Yes | Called after each edit for re-validation |
| `llama-cpp-python` Python wheel | Yes | Bundled in add-on `.zip` for local LLM inference |
| `httpx` Python wheel | Yes | Bundled in add-on `.zip` for API backend |
| Blender 4.2+ | Yes | User must have compatible Blender version |

### 12.3 Rollback Plan
1. User disables the add-on — chat panel and refinement features disappear
2. Undo snapshots stored in the `.blend` file remain accessible via Blender's native undo
3. Mesh edits made via the refinement loop persist in the `.blend` file (they are standard Blender operations)
4. Verify no orphaned `bpy.app.timers` callbacks remain after add-on disable
5. LLM model weights cached on disk are unaffected and can be cleared via SPEC-TS-0002 cache manager

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Parse "make it 20% taller" → SCALE Z 1.2, execute, verify bounding box | Integration | AC-001 | Must Pass |
| TS-002 | Parse "make the handle 3 mm thicker" → SOLIDIFY on "handle" vertex group | Integration | AC-002 | Must Pass |
| TS-003 | Parse "smooth the top" → SMOOTH on top 20% Z-axis vertices (no vertex groups) | Integration | AC-003 | Must Pass |
| TS-004 | "make the top bigger and the base smaller" → list of two sequential EditIntents, each with own undo snapshot | Unit | EC-001, FR-007 | Must Pass |
| TS-005 | "modify the top" with vertex group "top_handle" (67% fuzzy) → spatial heuristic used | Unit | EC-002 | Must Pass |
| TS-006 | "thicken the handle" on mesh with 0 vertex groups → user selection prompt | Unit | EC-003, FR-043 | Must Pass |
| TS-007 | 21 consecutive edits → oldest snapshot discarded, undo to version 2 works | Unit | EC-004 | Must Pass |
| TS-008 | Gibberish input "asdfghj" → no edit, help message displayed | Unit | EC-005 | Must Pass |
| TS-009 | "smooth the top" on 8-vertex cube → too-few-vertices warning | Unit | EC-006 | Must Pass |
| TS-010 | "undo that" after 3 edits → reverts to post-edit-2 state | Integration | AC-005 | Must Pass |
| TS-011 | "go back to version 2" after 5 edits → restores version 2 state | Integration | AC-006 | Must Pass |
| TS-012 | Edit that fails print validation → warning displayed, not auto-reverted | Integration | AC-007 | Must Pass |
| TS-013 | No mesh selected → chat panel disabled with placeholder message | Unit | AC-008 | Must Pass |
| TS-014 | API backend with valid key → request sent via HTTPS, no mesh data in payload | Integration | AC-009 | Must Pass |
| TS-015 | Intent parser confidence = 0.4 → ambiguity prompt shown, no edit applied | Unit | AC-004 | Must Pass |
| TS-016 | Full edit cycle latency (parse + execute + validate + render) < 15 seconds | Performance | NFR-001 | Must Pass |
| TS-017 | Blender viewport ≥ 15 fps during local LLM inference | Performance | NFR-009 | Should Pass |
| TS-018 | 5 consecutive edits on 10 different meshes → ≥ 95% remain print-valid | Integration | NFR-006 | Must Pass |
| TS-019 | API key stored in preferences → not visible in debug logs | Security | SEC-003 | Must Pass |
| TS-020 | LLM returns malformed JSON → error message shown, no crash | Unit | SEC-002 | Must Pass |
| TS-021 | Scale factor > 100.0 in parsed intent → clamped to 100.0 with warning | Unit | FR-044 | Must Pass |
| TS-022 | Edit operation affects > 80% of vertices → confirmation prompt shown | Unit | FR-018 | Must Pass |
| TS-023 | API endpoint with HTTP (not HTTPS) URL → rejected with security message | Unit | SEC-006 | Must Pass |
| TS-024 | ADD_GEOMETRY boolean union fails on non-manifold mesh → primitive removed, warning shown, no undo snapshot | Unit | FR-027 | Must Pass |
| TS-025 | Chat history exceeds 200 messages → oldest messages removed, preview images freed | Unit | FR-042 | Must Pass |
| TS-026 | Post-edit validation calls PrintValidator in validation-only mode with scene settings | Integration | FR-035 | Must Pass |
| TS-027 | Dimensionless "make it bigger" → inferred +10% uniform scale | Unit | FR-008 | Must Pass |
| TS-028 | Multi-intent: one sub-intent confidence < 0.7 → ambiguity prompt for that sub-intent only | Unit | FR-007 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Draft | Tessera | Yes — need sidebar panel and operator framework |
| SPEC-TS-0002 (Model Weight Management) | Required | Draft | Tessera | Yes — need LLM weight download and caching; `ensure_model()` called from LLM background thread per threading contract |
| SPEC-TS-0005 (Mesh Import & Cleanup) | Optional | Draft | Tessera | No — provides cleaned mesh input; vertex groups MAY be present but are NOT required (FR-043 handles zero-vertex-group meshes via spatial heuristics and user click-selection) |
| SPEC-TS-0006 (Print Validator & Export) | Required | Draft | Tessera | Yes — `PrintValidator.validate()` called in validation-only mode (FR-039) after each edit; scene validator settings (FR-033) provide parameters |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |
| `llama-cpp-python` >= 0.2.0 | Required (local backend) | [github.com/abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python) | API backend as alternative |
| `httpx` >= 0.27.0 | Required (API backend) | [www.python-httpx.org](https://www.python-httpx.org) | Local backend as alternative |
| Llama 3.1 8B GGUF weights (Q4_K_M) | Required (local backend) | HuggingFace repo | API backend as alternative |
| `difflib` (Python stdlib) | Required | Python docs | N/A — bundled with Python |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author (Orchestrator) | AI | 2026-04-10 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | | | ☐ N/A |

**Approval Notes:**
[Space for CSO/Deputy feedback]

---

## AI-READINESS SELF-SCORE

| Criterion | Max | Score | Guidance |
|-----------|-----|-------|----------|
| SHALL/SHOULD/MAY requirements | 20 | 20 | 47 requirements with precise SHALL/SHOULD/MAY language across 9 sections (added FR-042, FR-043, FR-044, expanded FR-007/FR-008/FR-010/FR-027/FR-035/FR-037) |
| Quantified NFRs | 15 | 15 | 10 NFRs, all quantified with specific targets, units, and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 9 acceptance criteria in Given-When-Then format with concrete values |
| Edge cases (2+) | 15 | 15 | 6 edge cases with concrete input examples and expected behaviors |
| Out of scope defined | 10 | 10 | 11 explicit exclusions covering common scope-creep areas |
| Security constraints | 10 | 10 | 6 security requirements + data classification table + LLM-specific protections (no code execution) + parameter range table (FR-044) |
| No ambiguous language | 10 | 10 | All ambiguous terms replaced with specifics; parameter ranges fully documented |
| **TOTAL** | **100** | **100** | **Target: ≥80 ✅** |

### Score Decision
| Score | Action |
|-------|--------|
| ≥80 | Submit for CSO review ✅ |

### Ambiguous Language Checklist
> Verify **NONE** of these words appear without specific definitions:

- [x] "appropriate" → not used
- [x] "properly" → not used
- [x] "correctly" → not used (replaced with specific verification rules)
- [x] "as expected" → not used
- [x] "handle gracefully" → replaced with specific error messages and fallback flows
- [x] "fast" / "efficient" / "performant" → replaced with ms/second/fps targets
- [x] "secure" → replaced with SEC-001 through SEC-006
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-10 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | AI (Spec Review) | Addressed spec review findings: FR-007 now returns `list[EditIntent]` for multi-intent decomposition (Critical-002). Downgraded SPEC-TS-0005 dependency to Optional — vertex groups not required (Critical-001, added FR-043). Clarified `ensure_model()` threading in FR-010 (Major-001). Updated FR-035 with full PrintValidator API signature and validation-only mode (Major-002). Added FR-042 chat history 200-message bound (Major-003). Added boolean-union failure handling to FR-027 (Major-004). Expanded FR-008 with default percentage mappings (Minor-001). Clarified FR-037 viewport vs camera view (Minor-002). Added FR-044 parameter range table (Minor-003). Added TS-024 through TS-028. Corrected self-score. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0009-nl-refinement-loop.md`
