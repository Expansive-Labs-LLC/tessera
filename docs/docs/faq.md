# Frequently Asked Questions

Answers to common questions about Tessera, organized by category.

---

## Installation & Setup

### What GPU do I need?

Tessera requires an **NVIDIA GPU with CUDA** and at least **6 GB VRAM** for basic reconstruction; 8 GB is the practical minimum for multi-view, sketch-to-3D and refinement, and 12 GB is recommended for everything at once. AMD (ROCm) and Apple Silicon (Metal) GPUs are detected but **not supported in v1** — the inference adapters run on CUDA only. See the [Installation guide](installation.md#gpu-vram-requirements) for the full VRAM table.

### Can I use Tessera without a GPU?

**No.** Tessera relies on GPU-accelerated AI inference for 3D reconstruction and cannot run on CPU alone. An NVIDIA CUDA GPU with at least 6 GB VRAM is required. Integrated graphics will not meet the minimum requirements.

### Does Tessera work on macOS?

**Not in v1.** Tessera detects Apple Silicon GPUs, but its inference adapters currently run on CUDA only, so model loading fails on macOS. Apple Silicon support is planned; please wait for a release that lists macOS explicitly. See the [Installation guide](installation.md#apple-silicon-and-amd).

### How do I update Tessera?

To update Tessera, download the latest release ZIP from the [Tessera GitHub releases page](https://github.com/Expansive-Labs-LLC/tessera/releases) or your marketplace. Then open **Blender Preferences → Add-ons → Install from Disk** and select the new ZIP — it will overwrite the previous version. Your cached model weights are preserved across updates. See the [Installation guide](installation.md).

### Does Tessera require an internet connection?

Only for the **initial download of AI model weights** (about 5.5 GB for the default pipeline). After model weights are cached locally, Tessera operates **fully offline**. No data is sent to external servers during image processing, reconstruction, or export.

### What licence are the AI model weights under?

Tessera's own code is **GPL-2.0-or-later**, but the AI model weights are third-party and are **not** covered by it. Each carries its own terms, listed in `MODEL-LICENSES.md` in the repository.

Tessera downloads only weights whose terms permit commercial use. Weights that restrict or prohibit it — such as **Depth Anything V2 Large (CC-BY-NC-4.0)** — are blocked, and appear in the model list as "Blocked by licence". Tessera uses the Apache-2.0 **Depth Anything V2 Small** checkpoint by default instead.

If your work is non-commercial and you want the larger checkpoint, enable **Allow Restricted-Licence Models** in Preferences → Add-ons → Tessera. You are responsible for complying with each model's terms.

### Can I use my own models?

Yes. Tessera's model list is user-extensible: **Preferences → Add-ons → Tessera → Models → Add from Hugging Face** adds any compatible checkpoint, and Tessera licence-checks it, pins its commit and records a checksum for every file before anything downloads. Your additions live beside the model cache, so they survive add-on updates.

Tessera can only *load* architectures it has an adapter for — Depth Anything V2 works end to end today; SAM 2, DINOv2 and TRELLIS can be added and verified but their loaders are still pinned to one checkpoint. See [Custom Models](user-guide/custom-models.md).

### What are the minimum system requirements?

Tessera requires **Blender 4.2+**, an **NVIDIA CUDA GPU with 6 GB VRAM** (8 GB recommended), **16 GB system RAM**, and about **5.5 GB free disk space** for AI model weights. See the [Installation guide](installation.md) for full details.

---

## Usage & Features

### How many images do I need?

Tessera works with **1–6 reference images** per batch. A single image produces a basic 3D model; using 3–6 images from different angles significantly improves quality. See the [Image Input guide](user-guide/image-input.md) for photography tips.

### What image formats are supported?

Tessera accepts **JPEG**, **PNG**, **WebP**, and **HEIC** formats. The minimum resolution is 256×256 pixels, with 1024×1024 or higher recommended. RAW, BMP, TIFF, and GIF are not supported. See the [Image Input guide](user-guide/image-input.md).

### Does Tessera send my data to the cloud?

**No.** All processing runs entirely on your local GPU. Your images and 3D models never leave your machine. Tessera downloads AI model weights once during initial setup and then operates completely offline with zero telemetry.

### Which reconstruction adapter should I use?

- **TripoSR** — Use for quick prototyping with 1 image (~5 seconds, 4 GB VRAM).
- **InstantMesh** — Use for balanced quality with 2–4 images (~15 seconds, 6 GB VRAM).
- **CRM** — Use for maximum quality with 4–6 images (~30 seconds, 8 GB VRAM).

See the [Reconstruction guide](user-guide/reconstruction.md#adapter-comparison) for a detailed comparison.

### What is a manifold mesh?

A **manifold mesh** is a watertight 3D model where every edge is shared by exactly two faces, with no holes, self-intersections, or disconnected geometry. Manifold meshes are required for 3D printing because slicers need a continuous, closed surface to calculate toolpaths correctly. Tessera's validation step checks manifold integrity automatically. See the [Glossary](reference/glossary.md#manifold).

### Can I generate models from sketches instead of photos?

Yes. Tessera's **Sketch-to-3D** feature accepts hand-drawn sketches and digital line art. It uses sketch-conditioned reconstruction with optional symmetry enforcement. See the [Sketch-to-3D guide](user-guide/sketch-to-3d.md).

### Why did reconstruction produce an empty mesh?

An empty mesh (BF-E008) usually means the AI model couldn't extract meaningful geometry from the input. This typically happens with very dark or overexposed images, objects blending into the background, or extremely small objects in the frame. Try using better-lit images with a plain, contrasting background.

---

## Printing & Export

### What is the difference between STL and 3MF?

**STL** stores only raw triangle geometry — no color, no metadata, no units. **3MF** is a modern format that embeds print metadata, units (mm), textures, and validation results. 3MF is recommended because your slicer can read the embedded settings automatically. Tessera supports both formats plus OBJ. See the [Export guide](user-guide/export.md).

### How do I know if my model is printable?

Run the **Validate** step in the Validation panel before exporting. Tessera checks manifold integrity, wall thickness, overhang angles, and build volume fit. All checks must pass (or be acknowledged with Force Export) before export. See the [Export guide](user-guide/export.md).

### My model has thin walls — will it print?

Tessera's validation checks wall thickness against the printer profile threshold (1.2 mm for FDM, 0.5 mm for SLA). If your model fails, you can use the Refinement panel ("make the walls 2mm thick"), manually thicken in Edit Mode, or switch to an SLA printer profile. See the [Printer Profiles reference](reference/printer-profiles.md).

### What printer profiles are available?

Tessera includes **7 built-in printer profiles**: Generic FDM, Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, Elegoo Saturn 3, and Custom. Each profile defines build volume dimensions and default validation thresholds. See the [Printer Profiles reference](reference/printer-profiles.md).

---

## Performance & GPU

### How do I fix 'GPU Memory Exhausted' errors?

GPU Memory Exhausted errors (BF-E001, BF-E002) mean your GPU ran out of VRAM. Try these steps: (1) close other GPU-intensive applications, (2) switch to a smaller adapter (TripoSR uses the least VRAM), (3) reduce input image resolution, (4) restart Blender to free cached GPU memory. See the [Troubleshooting page](troubleshooting.md).

### How do I report a bug?

Open a new issue on the [Tessera GitHub repository](https://github.com/Expansive-Labs-LLC/tessera/issues/new) with your Blender version, OS, GPU model, the exact error code (e.g., BF-E001), and steps to reproduce.

### Where can I find the error code meanings?

See the [Error Codes reference](reference/error-codes.md) for a quick-reference table of all 17 error codes, or the [Troubleshooting page](troubleshooting.md) for detailed descriptions with resolution steps.

### Tessera crashed Blender — what happened?

GPU memory exhaustion (BF-E001, BF-E002) is the most common cause of crashes. Close other GPU-intensive applications, try a smaller reconstruction adapter (TripoSR uses the least VRAM), and ensure your GPU drivers are up to date. See the [Troubleshooting page](troubleshooting.md) for more solutions.

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
