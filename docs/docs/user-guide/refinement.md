# Refinement

Tessera's natural language refinement loop lets you modify 3D models by describing changes in plain English. An LLM interprets your instructions and applies the corresponding Blender operations.

![Chat panel showing a refinement conversation with the user typing make the base wider and Tessera responding with the applied scale operation and updated mesh preview](assets/screenshots/refinement-chat.png)

---

## How It Works

1. Select the mesh object you want to modify in the viewport.
2. Open the **Tessera → Chat** panel.
3. Type a modification request in natural language.
4. Tessera interprets your request and applies the modification.
5. Review the result and iterate with additional requests.

---

## Supported Modification Types

| Operation | Description | Example Command |
|-----------|-------------|-----------------|
| **Scale** | Resize the object or a dimension | "Make it 20% larger" |
| **Translate** | Move the object or parts | "Move it up 5mm" |
| **Bevel** | Round edges and corners | "Bevel the top edges" |
| **Subdivide** | Add geometric detail | "Subdivide the surface twice" |
| **Solidify** | Add wall thickness | "Make the walls 2mm thick" |
| **Decimate** | Reduce polygon count | "Reduce to 10,000 faces" |

---

## Example Refinement Commands

Here are 5 concrete examples with their expected outcomes:

1. **"Make it wider"** → Scales the object along the X axis by 120%, maintaining height and depth.

2. **"Smooth the edges"** → Applies a bevel modifier to all sharp edges with 2 segments and 0.5mm width.

3. **"Make the base 5mm thicker"** → Identifies the bottom region of the mesh and extrudes it downward by 5mm.

4. **"Reduce the polygon count by half"** → Applies a decimate modifier with ratio 0.5, reducing face count while preserving shape.

5. **"Make it exactly 80mm tall"** → Measures the current bounding box height and applies a uniform scale to achieve exactly 80mm.

---

## Undo / Redo and Version History

Every refinement operation is recorded in Blender's undo stack:

- Press ++ctrl+z++ to **undo** the last modification.
- Press ++ctrl+shift+z++ to **redo** an undone modification.
- You can undo multiple steps to return to any previous state.
- Type **"undo that"** in the chat to undo the last AI-applied change.

!!! info "Version Tracking"
    Each refinement step is logged in the Chat panel history. You can review what was changed and when.

---

## LLM Backend Configuration

Tessera supports two LLM backends for interpreting natural language commands:

### Local GGUF Model

- Runs entirely on your machine — no internet required.
- Requires ~8 GB VRAM for the LLM model (in addition to reconstruction models).
- Configure the GGUF model path in **Tessera Preferences → LLM Backend**.

### API Backend

- Connects to a local or remote LLM API endpoint.
- Configure the API URL and key in **Tessera Preferences → LLM Backend**.
- Lower VRAM usage since the LLM runs on a separate server.

See [Preferences](preferences.md) for detailed LLM backend configuration.

---

## Tips for Best Results

- **Be specific** — "Make it 50mm tall" works better than "make it bigger"
- **Use incremental changes** — Apply one modification at a time
- **Reference dimensions** — Specify sizes in mm for print accuracy
- **Use standard terms** — "scale", "bevel", "smooth", "subdivide" are well-understood
- **Check validation** — Run validation after each change to ensure print-readiness

---

## Limitations

- Complex topological changes (adding holes, splitting objects) may require manual editing in Edit Mode.
- The LLM processes text descriptions — it cannot interpret images during refinement.
- Results depend on the LLM backend configured in Tessera preferences.
- Semantic part identification ("make the handle thicker") works best with simple, distinct object regions.

---

## See Also

- [Mesh Cleanup](mesh-cleanup.md) — Clean up topology after refinement
- [Export & Print](export.md) — Validate and export after refinement
- [Preferences](preferences.md) — Configure LLM backend settings

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
