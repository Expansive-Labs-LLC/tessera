# Mesh Cleanup

After reconstruction, Tessera's cleanup pipeline automatically repairs topology issues and optimizes the mesh for 3D printing.

![Mesh Cleanup panel showing diagnostics with counts for duplicate vertices removed, degenerate faces dissolved, normals recalculated, and holes filled](assets/screenshots/mesh-cleanup-diagnostics.png)

---

## Automatic Cleanup Pipeline

When you click **Run Cleanup**, the following repairs are applied in order:

1. **Duplicate vertex removal** — Merges vertices that are closer than 0.0001 units apart.
2. **Degenerate face removal** — Dissolves faces with zero area or collapsed edges.
3. **Normal recalculation** — Ensures all face normals point outward consistently.
4. **Hole filling** — Detects and fills holes up to 32 edges in size.

Each step reports the number of elements fixed in the diagnostics panel.

!!! info "Non-Destructive"
    Cleanup is applied as a separate operation. You can undo it with ++ctrl+z++ if the results are not satisfactory.

---

## Topology Controls

### Voxel Remesh

Converts the mesh to a uniform voxel grid and re-extracts the surface. Produces a guaranteed manifold mesh but loses sharp edges.

- **Voxel Size** — Controls resolution (smaller = more detail, more faces). Default: 0.02.
- **Best for** — Organic shapes, complex topology that other methods can't repair.

### Quad Remesh

Converts the triangulated mesh to a quad-dominant topology. Better for subdivision surface modeling and manual editing.

- **Target Face Count** — Approximate number of output quads. Default: 10,000.
- **Best for** — Models you plan to manually edit or refine in Edit Mode.

### Decimation

Reduces the polygon count while preserving the overall shape. Useful for reducing file size.

- **Ratio** — Target reduction ratio (0.5 = half the faces). Default: 0.5.
- **Best for** — Reducing file size for 3D printing where fine mesh detail is unnecessary.

---

## Cleanup Diagnostics

After running cleanup, the diagnostics panel shows:

| Metric | Description |
|--------|-------------|
| **Vertices** | Total vertex count (before → after) |
| **Faces** | Total face count (before → after) |
| **Non-Manifold Edges** | Edges shared by ≠2 faces (should be 0) |
| **Degenerate Faces** | Zero-area faces remaining (should be 0) |
| **Holes** | Open boundaries remaining (should be 0) |
| **Volume** | Mesh volume in mm³ (must be >0 for valid mesh) |

!!! tip "Check Before Export"
    Always review the diagnostics before exporting. A successful cleanup should show 0 non-manifold edges, 0 degenerate faces, and 0 holes.

---

## Manual Cleanup Tips

If automatic cleanup doesn't fully resolve all issues, you can manually fix problems in Blender's Edit Mode:

1. Press ++tab++ to enter Edit Mode.
2. Select non-manifold edges: **Select → All by Trait → Non Manifold**.
3. Fill holes: Select boundary edges and press ++f++ to create a face.
4. Merge close vertices: **Mesh → Clean Up → Merge by Distance**.
5. Recalculate normals: **Mesh → Normals → Recalculate Outside**.
6. Press ++tab++ to return to Object Mode.

---

## See Also

- [3D Reconstruction](reconstruction.md) — How the initial mesh is generated
- [Scaling & Orientation](scaling-orientation.md) — Set real-world dimensions after cleanup

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
