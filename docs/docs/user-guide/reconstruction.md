# 3D Reconstruction

Tessera uses AI-powered reconstruction to generate 3D meshes from reference images. Choose from multiple adapters optimized for different input types.

![Generation panel showing TripoSR adapter selected with reconstruction in progress and a 3D mesh preview appearing in the Blender viewport](assets/screenshots/reconstruction-generation.png)

---

## Single-Image Reconstruction

With a single reference image, Tessera uses a single-view reconstruction adapter to infer the 3D geometry. This is the fastest workflow but may miss details not visible in the photo.

1. Load one reference image in the Image Input panel.
2. Select **TripoSR** as the reconstruction adapter (optimized for single-view).
3. Click **Generate 3D Model**.
4. The mesh appears in the viewport in approximately 5 seconds.

!!! tip "Best for Prototyping"
    Single-image reconstruction is ideal for quick prototypes and simple objects.
    For production-quality results, use 3–6 images with different view angles.

---

## Multi-View Reconstruction

With 3 or more images from different angles, Tessera produces significantly more accurate and detailed 3D meshes.

1. Load 3–6 reference images with different viewpoints.
2. Assign view labels (front, back, left, etc.) for best accuracy.
3. Select **InstantMesh** or **CRM** as the reconstruction adapter.
4. Click **Generate 3D Model**.
5. The pipeline aligns the views, fuses depth maps, and generates the mesh.

---

## Adapter Comparison

| Adapter | Best For | VRAM Required | Speed | Quality |
|---------|----------|---------------|-------|---------|
| **TripoSR** | Quick prototyping with 1 image | ~4 GB | Fast (~5s) | Good |
| **InstantMesh** | Balanced quality with 2–4 views | ~6 GB | Medium (~15s) | High |
| **CRM** | Maximum quality with 4–6 views | ~8 GB | Slow (~30s) | Highest |

### Choosing an Adapter

- **TripoSR** — Use when you have a single image and need results quickly. Best for simple, symmetric objects.
- **InstantMesh** — Use when you have 2–4 views and want a good balance of speed and quality.
- **CRM** — Use when you have 4–6 views and quality is more important than speed. Best for complex, detailed objects.

---

## Reconstruction Pipeline

1. **Vision Analysis** — Segments objects, estimates depth, extracts visual features
2. **Conditioning** — Prepares multi-view conditioning data from processed images
3. **Generation** — Runs the selected adapter to produce a 3D mesh
4. **Import** — Loads the generated mesh into Blender as an editable object

---

## Output Quality

The output mesh typically has:

- 10,000–150,000 faces (depends on adapter and input quality)
- Triangulated topology (converted to quads by mesh cleanup if desired)
- May contain non-manifold edges or small holes (fixed by the [Mesh Cleanup](mesh-cleanup.md) pipeline)

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Empty mesh | Poor input image quality | Try clearer images with better lighting |
| Timeout (>120s) | Complex object or slow GPU | Reduce image resolution or try a faster adapter |
| VRAM error | Insufficient GPU memory | Close other GPU apps or use a smaller adapter |
| Distorted output | Incorrect view labels | Verify view labels match actual camera angles |

See the [Troubleshooting page](../troubleshooting.md) for full error code details.

---

## See Also

- [Image Input](image-input.md) — How to prepare and load reference images
- [Mesh Cleanup](mesh-cleanup.md) — Clean up and optimize the generated mesh

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
