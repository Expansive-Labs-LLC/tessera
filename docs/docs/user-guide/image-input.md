# Image Input

Tessera accepts 1–6 reference images per batch. Quality and variety of input images directly impact the final 3D model quality.

![Image Input panel with 3 reference images loaded showing thumbnails, assigned view labels (front, left, back), and an Analyze Images button](assets/screenshots/image-input-panel.png)

---

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| JPEG | `.jpg`, `.jpeg` | Best for photos; smallest file size |
| PNG | `.png` | Supports transparency; lossless |
| WebP | `.webp` | Compact modern format |
| HEIC | `.heic` | Apple devices (iOS/macOS) |

!!! warning "Unsupported Formats"
    BMP, TIFF, GIF, and RAW formats are not supported. Convert to JPEG or PNG first.

---

## Image Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Resolution | 256×256 px | 1024×1024 px or higher |
| Maximum Resolution | 4096×4096 px | — |
| Sharpness | Non-blurry | Sharp, in-focus |
| Background | Any | Plain, high-contrast |
| Lighting | Visible object | Even, diffuse lighting |

---

## Photography Tips

### Single Image

- Center the object in the frame
- Use a plain background (white, gray, or contrasting color)
- Ensure even lighting with minimal shadows
- Capture from a 3/4 front angle for best results

### Multi-View (3–6 Images)

For the highest quality models, provide multiple views:

1. **Front** — Straight-on view of the primary face
2. **Back** — Opposite side of the object
3. **Left Side** — 90° from front
4. **Right Side** — 90° from front (opposite of left)
5. **Top** — Looking down at the object
6. **3/4 View** — Angled view showing front and one side

!!! tip "Consistency"
    Keep the same lighting, distance, and camera settings across all views.
    The object should be the same size in each image.

---

## View Labels

Tessera auto-detects which angle each image represents. You can manually override by selecting a label from the dropdown.

Available labels: `front`, `back`, `left`, `right`, `top`, `bottom`, `front-left`, `front-right`, `isometric`, `custom`.

For the full vocabulary with camera directions and angles, see the [View Labels Reference](../reference/view-labels.md).

!!! info "Why Use View Labels?"
    Even a single labeled image (e.g., `front`) anchors the coordinate system and helps the AI infer poses for remaining unlabeled images more accurately.

---

## Batch Processing

- Maximum 6 images per batch
- Images that fail to load are skipped (the pipeline continues)
- Processing time scales linearly with the number of images

---

## See Also

- [3D Reconstruction](reconstruction.md) — How Tessera turns your images into 3D meshes
- [View Labels Reference](../reference/view-labels.md) — Full vocabulary table with camera angles

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
