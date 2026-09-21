# View Labels

Tessera uses view labels to identify the camera direction of each reference image. Providing view labels dramatically improves reconstruction accuracy by anchoring the coordinate system.

---

## View Label Vocabulary

| Label | Camera Direction | Canonical Azimuth | Canonical Elevation |
|-------|-----------------|-------------------|-------------------|
| `front` | Looking at the front face | 0° | 0° |
| `back` | Looking at the rear face | 180° | 0° |
| `left` | Looking at the left side | 270° | 0° |
| `right` | Looking at the right side | 90° | 0° |
| `top` | Looking straight down | — | 90° |
| `bottom` | Looking straight up | — | −90° |
| `front-left` | 45° between front and left | 315° | 0° |
| `front-right` | 45° between front and right | 45° | 0° |
| `isometric` | Standard isometric view | 45° | 35° |
| `custom:<az>,<el>` | User-specified angles in degrees | User-defined | User-defined |

---

## How View Labels Work

When you assign a view label to an image, Tessera uses the canonical camera matrix for that direction instead of running pose estimation. This provides two benefits:

1. **Accuracy** — The exact camera angle is known, eliminating estimation errors.
2. **Speed** — Pose estimation is skipped for labeled images, reducing processing time.

---

## Auto-Detection

When view labels are not assigned, Tessera runs a lightweight view-direction classifier:

1. The classifier analyzes the object silhouette and up-vector heuristic.
2. If confidence ≥ 80%, the detected label is used automatically (shown in the UI).
3. If confidence < 80%, Tessera prompts you to confirm or manually assign a label.

!!! tip "Label at Least One Image"
    Even labeling a single image (e.g., `front`) anchors the coordinate system and helps Tessera infer poses for the remaining unlabeled images more reliably.

---

## Custom Angles

For non-standard camera angles, use the `custom` label format:

```
custom:<azimuth>,<elevation>
```

**Examples:**

- `custom:30,15` — 30° azimuth, 15° elevation
- `custom:135,0` — 135° azimuth, 0° elevation (between back and right)
- `custom:0,45` — 0° azimuth, 45° elevation (elevated front view)

Azimuth is measured clockwise from the front (0° = front, 90° = right, 180° = back, 270° = left). Elevation is measured from the horizontal plane (0° = level, 90° = directly above, −90° = directly below).

---

## See Also

- [Image Input](../user-guide/image-input.md) — How to load images and assign labels
- [3D Reconstruction](../user-guide/reconstruction.md) — How view labels improve reconstruction

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
