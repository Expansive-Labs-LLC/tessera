# Sketch-to-3D

Tessera can generate 3D models from hand-drawn sketches — photographs of drawings on paper or digital line art. This experimental feature uses sketch-conditioned reconstruction with symmetry priors.

![Sketch Input panel showing a photographed pencil drawing of a vase on the left and the resulting 3D mesh on the right in the Blender viewport](assets/screenshots/sketch-to-3d-input-output.png)

---

## What is Sketch Input?

Sketch input accepts two types of drawings:

- **Paper sketches** — Photograph a hand-drawn sketch with your phone or camera. Tessera preprocesses the image to extract clean line art.
- **Digital line art** — Import a digital drawing (PNG with transparent or white background). Clean outlines on a plain background work best.

Unlike photo-based reconstruction, sketch-to-3D infers 3D geometry from 2D outlines using shape priors and symmetry assumptions.

---

## Workflow

1. Draw your object on paper or in a drawing app.
2. If on paper, photograph the drawing with even lighting and minimal shadows.
3. Load the image in the **Image Input** panel.
4. Tessera detects the sketch input and switches to sketch-conditioned reconstruction.
5. Select symmetry options (bilateral, radial, or none).
6. Click **Generate 3D Model**.

---

## Sketch Preprocessing

Tessera applies the following preprocessing steps to sketch inputs:

1. **Edge detection** — Extracts clean contour lines from the image using Canny edge detection.
2. **Background removal** — Separates the drawing from the paper/background.
3. **Line cleanup** — Removes noise, gaps, and stray marks to produce clean outlines.
4. **Contrast normalization** — Ensures consistent line weight for the reconstruction model.

!!! tip "Drawing Tips"
    - Use a dark pen or marker on white paper for best contrast.
    - Draw clean, connected outlines — gaps in lines may cause artifacts.
    - Include a side view in addition to the front view for better depth inference.

---

## Symmetry Enforcement

Sketch-to-3D supports symmetry options to improve results for symmetric objects:

| Option | Description | Best For |
|--------|-------------|----------|
| **Bilateral** | Mirrors geometry across the X axis | Vases, bottles, furniture |
| **Radial** | Applies rotational symmetry | Cups, bowls, wheels |
| **None** | No symmetry constraint | Asymmetric objects |

---

## Limitations

- **Simple shapes only** — Sketch-to-3D works best with basic geometric forms (vases, cups, bottles, boxes). Highly detailed or complex organic shapes may not reconstruct well.
- **No textures** — Sketch input produces geometry only. Surface detail, color, and texture are not inferred from sketches.
- **Single object** — Each sketch should depict one object. Multi-object scenes are not supported.
- **Line quality matters** — Faint, broken, or overlapping lines reduce output quality.

!!! warning "Experimental Feature"
    Sketch-to-3D is an experimental feature. Results vary based on drawing quality and object complexity. For production-quality models, use photo-based reconstruction with 3–6 reference images.

---

## See Also

- [Image Input](image-input.md) — Prepare and load reference images
- [3D Reconstruction](reconstruction.md) — Photo-based reconstruction for higher quality

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
