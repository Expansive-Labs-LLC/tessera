# Screenshot Capture Runbook — Tessera Documentation

Step-by-step instructions for capturing all 15 screenshots required by the Tessera documentation site.

---

## Prerequisites

- [ ] Blender 4.2+ installed
- [ ] Tessera add-on installed and enabled
- [ ] At least 3 reference photos of a real object (e.g., a coffee mug)
  - Front view, left side, and back view
- [ ] Screenshot tool ready:
  - **Linux**: `gnome-screenshot -a` or ++print-screen++
  - **macOS**: ++cmd+shift+4++
  - **Windows**: ++win+shift+s++
- [ ] Output directory created: `docs/docs/assets/screenshots/`

---

## Environment Checklist

Before capturing, configure Blender consistently:

- [ ] **Viewport shading**: Material Preview (press ++z++ → Material Preview)
- [ ] **Sidebar visible**: Press ++n++ to show the sidebar
- [ ] **Tessera tab selected**: Click the "Tessera" tab in the sidebar
- [ ] **Viewport background**: Default Blender gray (do not customize)
- [ ] **Window size**: Full screen or maximized on a 1920×1080 display
- [ ] **No personal info**: Hide file paths in title bar (save file as `tessera-demo.blend`)

---

## Capture Sequence

Work through these in order — each step builds on the previous scene state.

### Screenshot 1: `main-panel.png`
**Used on**: `index.md` (landing page)

1. Open a new Blender scene with the default cube.
2. Press ++n++ → Tessera tab.
3. Collapse all sections so Image Input, Generation, Validation, and Export headers are all visible.
4. **Capture**: The full Tessera sidebar panel showing all 4 section headers.
5. **Crop**: Sidebar panel only (no 3D viewport).
6. **Save as**: `main-panel.png`

- [ ] Captured

---

### Screenshot 2: `quickstart-step1.png`
**Used on**: `quickstart.md` — Step 1

1. Same scene as above.
2. Ensure the Tessera tab is visible in the sidebar tab list.
3. **Capture**: The 3D Viewport with the sidebar tabs visible, highlighting the Tessera tab.
4. **Crop**: Include the 3D viewport and sidebar tab strip.
5. **Save as**: `quickstart-step1.png`

- [ ] Captured

---

### Screenshot 3: `quickstart-step2.png`
**Used on**: `quickstart.md` — Step 2

1. In the Image Input panel, click **Add Images**.
2. Load 3 reference photos of your object (front, left, back).
3. Assign view labels: front, left, back.
4. **Capture**: The Image Input panel showing 3 loaded images with thumbnails and view labels.
5. **Crop**: Image Input panel only.
6. **Save as**: `quickstart-step2.png`

- [ ] Captured

---

### Screenshot 4: `quickstart-step3.png`
**Used on**: `quickstart.md` — Step 3

1. Select TripoSR as the reconstruction adapter.
2. Click **Generate 3D Model**.
3. While the progress bar is visible (~75%), take the screenshot.
4. **Capture**: The Generation panel with progress bar + the 3D viewport showing the partially generated mesh.
5. **Crop**: Generation panel and 3D viewport together.
6. **Save as**: `quickstart-step3.png`

!!! tip
    If the generation is too fast to catch the progress bar, use the CRM adapter for a slower generation (~30s).

- [ ] Captured

---

### Screenshot 5: `quickstart-step4.png`
**Used on**: `quickstart.md` — Step 4

1. After generation completes, go to the Validation panel.
2. Select a printer profile (e.g., "Generic FDM").
3. Click **Validate**.
4. **Capture**: The Validation panel showing 4 check results (Manifold, Wall Thickness, Overhang, Volume).
5. **Crop**: Validation panel only.
6. **Save as**: `quickstart-step4.png`

- [ ] Captured

---

### Screenshot 6: `quickstart-step5.png`
**Used on**: `quickstart.md` — Step 5

1. In the Export panel, select STL format.
2. Set the export directory.
3. Click **Export**.
4. **Capture**: The Export panel showing the format selection, directory, and the green success message.
5. **Crop**: Export panel only.
6. **Save as**: `quickstart-step5.png`

- [ ] Captured

---

### Screenshot 7: `image-input-panel.png`
**Used on**: `user-guide/image-input.md`

1. Load the same 3 images from Step 3.
2. Ensure thumbnails and view label dropdowns are visible.
3. **Capture**: The Image Input panel with all images and labels visible.
4. **Crop**: Image Input panel only, showing full detail.
5. **Save as**: `image-input-panel.png`

- [ ] Captured

---

### Screenshot 8: `reconstruction-generation.png`
**Used on**: `user-guide/reconstruction.md`

1. Run generation again (or use the completed state).
2. **Capture**: The Generation panel showing adapter selection + the 3D viewport with the generated mesh visible.
3. **Crop**: Include both the Generation panel and the viewport mesh.
4. **Save as**: `reconstruction-generation.png`

- [ ] Captured

---

### Screenshot 9: `sketch-to-3d-input-output.png`
**Used on**: `user-guide/sketch-to-3d.md`

1. Load a hand-drawn sketch image (photograph of a pencil drawing, or a digital line art PNG).
2. Run generation with the sketch input.
3. **Capture**: The Image Input panel (showing the sketch thumbnail) alongside the 3D viewport (showing the resulting mesh).
4. **Crop**: Both panels side by side.
5. **Save as**: `sketch-to-3d-input-output.png`

!!! note
    If you don't have a sketch input, photograph a simple pencil drawing of a vase or cup on white paper.

- [ ] Captured

---

### Screenshot 10: `mesh-cleanup-diagnostics.png`
**Used on**: `user-guide/mesh-cleanup.md`

1. After generating a mesh, open the Mesh Cleanup panel.
2. Click **Run Cleanup** to show diagnostics.
3. **Capture**: The Mesh Cleanup panel showing before/after vertex counts, face counts, and repair statistics.
4. **Crop**: Mesh Cleanup panel only.
5. **Save as**: `mesh-cleanup-diagnostics.png`

- [ ] Captured

---

### Screenshot 11: `scaling-panel.png`
**Used on**: `user-guide/scaling-orientation.md`

1. Open the Scaling panel.
2. Enable Auto Infer (if available) or enter manual dimensions (e.g., 80mm height).
3. **Capture**: The Scaling panel showing dimension inputs, Auto Infer toggle, and Optimize Orientation button.
4. **Crop**: Scaling panel only.
5. **Save as**: `scaling-panel.png`

- [ ] Captured

---

### Screenshot 12: `refinement-chat.png`
**Used on**: `user-guide/refinement.md`

1. Select the generated mesh in the viewport.
2. Open the Chat panel.
3. Type a refinement command (e.g., "make it wider") and submit.
4. Wait for the response showing the applied operation.
5. **Capture**: The Chat panel showing the user message, AI response, and the updated mesh in the viewport.
6. **Crop**: Chat panel only (or panel + viewport if both fit).
7. **Save as**: `refinement-chat.png`

- [ ] Captured

---

### Screenshot 13: `export-panel.png`
**Used on**: `user-guide/export.md`

1. Open the Export panel.
2. Check STL and 3MF format boxes.
3. Set an export directory.
4. **Capture**: The Export panel showing format selections, validation summary, and export directory.
5. **Crop**: Export panel only.
6. **Save as**: `export-panel.png`

- [ ] Captured

---

### Screenshot 14: `preferences-gpu.png`
**Used on**: `user-guide/preferences.md`

1. Open **Blender Preferences → Add-ons**.
2. Search for "Tessera" and expand its preferences.
3. **Capture**: The GPU Device section showing GPU name, VRAM, and backend.
4. **Crop**: The Tessera preferences section (GPU area).
5. **Save as**: `preferences-gpu.png`

- [ ] Captured

---

### Screenshot 15: `preferences-llm.png`
**Used on**: `user-guide/preferences.md`

1. Same Preferences window as above.
2. Scroll to the LLM Backend section.
3. **Capture**: The LLM Backend section showing backend dropdown, API endpoint, and API key fields.
4. **Crop**: The Tessera preferences section (LLM area).
5. **Save as**: `preferences-llm.png`

- [ ] Captured

---

## Post-Capture Checklist

After capturing all screenshots:

- [ ] All 15 PNG files are saved in `docs/docs/assets/screenshots/`
- [ ] All filenames match the manifest exactly (lowercase, hyphens)
- [ ] No personal file paths or usernames are visible in any screenshot
- [ ] Each image is cropped to show only the relevant UI area
- [ ] Each image is ≤500 KB (compress with `pngquant` or similar if needed)
- [ ] Run `mkdocs serve` locally to verify all images render correctly

### Compression (optional)

If any screenshots exceed 500 KB:

```bash
# Install pngquant (one-time)
sudo apt install pngquant  # Linux
brew install pngquant      # macOS

# Compress all screenshots
cd docs/docs/assets/screenshots/
pngquant --quality=65-80 --ext .png --force *.png
```

---

## File Listing

After completion, the directory should contain:

```
docs/docs/assets/screenshots/
├── README.md
├── main-panel.png
├── quickstart-step1.png
├── quickstart-step2.png
├── quickstart-step3.png
├── quickstart-step4.png
├── quickstart-step5.png
├── image-input-panel.png
├── reconstruction-generation.png
├── sketch-to-3d-input-output.png
├── mesh-cleanup-diagnostics.png
├── scaling-panel.png
├── refinement-chat.png
├── export-panel.png
├── preferences-gpu.png
└── preferences-llm.png
```
