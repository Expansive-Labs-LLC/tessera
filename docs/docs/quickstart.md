# Quick Start Guide

Create your first 3D-printable model from a reference photo in **5 steps**.

---

## Step 1: Open the Tessera Panel

Open Blender and press ++n++ to reveal the sidebar. Click the **Tessera** tab to access all panels.

![Tessera sidebar tab visible in the Blender 3D Viewport with the main panel expanded showing Image Input, Generation, Validation, and Export sections](assets/screenshots/quickstart-step1.png)

!!! tip "First Time?"
    If you don't see the Tessera tab, make sure you've enabled the add-on in **Preferences → Add-ons**.

---

## Step 2: Load Reference Images

In the **Image Input** panel, click **Add Images** and select 1–6 reference photos. Assign view labels (front, back, left, etc.) for best results.

![Image Input panel with 3 images loaded and view labels assigned showing front, left, and back views of a ceramic vase](assets/screenshots/quickstart-step2.png)

!!! tip "Better Photos = Better Models"
    Use well-lit, sharp photos on a plain background. 3–6 views from different angles produce the best results.

---

## Step 3: Generate the 3D Model

In the **Generation** panel, select a reconstruction adapter (default: **TripoSR**) and click **Generate 3D Model**. The reconstructed mesh appears in the viewport.

![Generation panel showing TripoSR adapter selected with a progress bar at 75% and a partially visible 3D mesh in the viewport](assets/screenshots/quickstart-step3.png)

!!! tip "Adapter Selection"
    Use **TripoSR** for speed (single image) or **CRM** for quality (4+ images). See the [Reconstruction guide](user-guide/reconstruction.md) for details.

---

## Step 4: Validate for Printing

In the **Validation** panel, select your printer type (FDM or SLA) and click **Validate**. Tessera checks manifold integrity, wall thickness, overhang angles, and build volume fit.

![Validation panel showing 4 checks with green checkmarks for Manifold, Wall Thickness, and Volume, and a yellow warning for Overhang Angle at 52 degrees](assets/screenshots/quickstart-step4.png)

!!! tip "Auto Repair"
    Enable **Auto Repair** to automatically fix common issues like non-manifold edges and thin walls.

---

## Step 5: Export Your Model

In the **Export** panel, select your output format (STL, OBJ, or 3MF), choose a directory, and click **Export**. Your print-ready model is saved and ready for slicing.

![Export panel showing STL format selected with export directory set and a green success message confirming the file was saved](assets/screenshots/quickstart-step5.png)

!!! tip "3MF Recommended"
    3MF format embeds print settings and validation metadata — your slicer can read them automatically.

---

## Next Steps

- [Image Input Guide](user-guide/image-input.md) — Optimize your reference photos and view labels
- [Refinement Guide](user-guide/refinement.md) — Use natural language to modify your model
- [Export Guide](user-guide/export.md) — Learn about export formats, printer profiles, and metadata
- [Troubleshooting](troubleshooting.md) — Resolve common issues

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
