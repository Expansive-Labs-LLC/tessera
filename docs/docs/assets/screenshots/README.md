# Screenshot Manifest

This directory stores screenshots used throughout the Tessera documentation. Screenshots should be captured from a running Blender instance with a representative scene.

---

## Capture Instructions

### Environment Setup

1. Open **Blender 4.2+** with the Tessera add-on installed and enabled.
2. Load a test scene with a simple object (e.g., the default cube or a reference model).
3. Use the **Material Preview** viewport shading mode for consistent appearance.
4. Set the viewport background to the **default Blender gray** (do not customize).
5. Use a **1920×1080** monitor resolution or scale screenshots to this size.
6. Hide any personal information from the Blender window (file paths, recent files).

### Capture Method

- **Linux**: Use ++print-screen++ or `gnome-screenshot -a` for area capture.
- **macOS**: Use ++cmd+shift+4++ for area capture.
- **Windows**: Use ++win+shift+s++ (Snipping Tool) for area capture.

### Image Format

- Save all screenshots as **PNG** format.
- Use descriptive filenames matching the manifest entries below (e.g., `main-panel.png`).
- Crop to show only the relevant UI area — avoid capturing the entire desktop.
- Target file size: under 500 KB per image (compress if necessary).

---

## Screenshot Manifest

### Landing Page & Quick Start

| Filename | Page | Description | Capture Area |
|----------|------|-------------|-------------|
| `main-panel.png` | index.md | Tessera main panel in the 3D Viewport sidebar showing all 4 sections (Image Input, Generation, Validation, Export) | Full Tessera sidebar panel |
| `quickstart-step1.png` | quickstart.md | Blender 3D Viewport with Tessera tab visible in the sidebar | 3D Viewport with sidebar tabs visible |
| `quickstart-step2.png` | quickstart.md | Image Input panel with 3 images loaded and view labels assigned | Image Input panel only |
| `quickstart-step3.png` | quickstart.md | Generation panel with reconstruction in progress (progress bar visible) | Generation panel + viewport mesh preview |
| `quickstart-step4.png` | quickstart.md | Validation panel showing 4 validation checks with results | Validation panel only |
| `quickstart-step5.png` | quickstart.md | Export panel with format selected and success message | Export panel only |

### User Guide Pages

| Filename | Page | Description | Capture Area |
|----------|------|-------------|-------------|
| `image-input-panel.png` | user-guide/image-input.md | Image Input panel with multiple images loaded, showing thumbnails and view label dropdowns | Image Input panel only |
| `reconstruction-generation.png` | user-guide/reconstruction.md | Generation panel during reconstruction with viewport showing the generated mesh | Generation panel + 3D viewport |
| `sketch-to-3d-input-output.png` | user-guide/sketch-to-3d.md | Side-by-side of a sketch input image and the resulting 3D mesh in viewport | Image Input panel (with sketch) + 3D viewport |
| `mesh-cleanup-diagnostics.png` | user-guide/mesh-cleanup.md | Mesh Cleanup panel showing diagnostics with before/after vertex and face counts | Mesh Cleanup panel only |
| `scaling-panel.png` | user-guide/scaling-orientation.md | Scaling panel with dimension inputs and auto-infer toggle | Scaling panel only |
| `refinement-chat.png` | user-guide/refinement.md | Chat panel showing a refinement conversation with user input and AI response | Chat panel only |
| `export-panel.png` | user-guide/export.md | Export panel with format checklist, validation summary, and export directory | Export panel only |
| `preferences-gpu.png` | user-guide/preferences.md | Tessera Preferences panel showing GPU Device section | Blender Preferences window (Tessera section) |
| `preferences-llm.png` | user-guide/preferences.md | Tessera Preferences panel showing LLM Backend section | Blender Preferences window (Tessera section) |

---

## Placeholder Image

Until screenshots are captured, documentation pages reference these filenames as placeholders. MkDocs will display a broken image icon, which is expected. Once screenshots are captured and placed in this directory, the documentation will display them automatically.

!!! tip "Contributing Screenshots"
    When capturing screenshots, ensure no personal file paths, usernames, or identifying information are visible in the Blender window title bar or file browser.
