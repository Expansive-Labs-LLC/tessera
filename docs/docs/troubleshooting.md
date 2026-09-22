# Troubleshooting

Solutions for common issues and a complete reference for all Tessera error codes.

---

## Common Issues

These are frequently reported issues that do **not** produce a specific error code.

### Model weights download is slow

The initial download of AI model weights (~2 GB) depends on your internet connection speed.

**Solutions:**

1. Check your internet connection speed — a minimum of 10 Mbps is recommended.
2. Try downloading at a different time of day (server load varies).
3. If the download stalls, cancel and restart it from the Model Manager panel.
4. Change the cache directory to a drive with more space if the disk is nearly full.

**Related:** [Installation — Model Weight Download](installation.md#model-weight-download)

---

### Tessera panel doesn't appear in sidebar

After installing and enabling the add-on, the Tessera tab may not be visible.

**Solutions:**

1. Press ++n++ to toggle the sidebar in the 3D Viewport.
2. Scroll through the sidebar tabs — Tessera may be below the visible area.
3. Verify the add-on is enabled: **Preferences → Add-ons**, search for "Tessera".
4. Restart Blender after enabling the add-on.
5. Re-install the add-on ZIP if the issue persists.

**Related:** [Installation — Verifying Installation](installation.md#verifying-installation)

---

### Generated mesh looks wrong or distorted

The 3D reconstruction produced a mesh that doesn't match the reference images.

**Solutions:**

1. Use higher-quality reference images (sharp, well-lit, plain background).
2. Provide more views (3–6 images from different angles).
3. Assign correct view labels to each image (front, back, left, etc.).
4. Try a different reconstruction adapter (e.g., switch from TripoSR to CRM).
5. Ensure the object fills most of the frame in each image.

**Related:** [Image Input Guide](user-guide/image-input.md), [3D Reconstruction Guide](user-guide/reconstruction.md)

---

### Blender crashes during generation

Blender becomes unresponsive or crashes while generating a 3D model.

**Solutions:**

1. Close other GPU-intensive applications to free VRAM.
2. Check that your GPU drivers are up to date.
3. Try a smaller reconstruction adapter — the single-image path needs less VRAM than multi-view.
4. Reduce input image resolution before processing.
5. Note that macOS and AMD GPUs are not supported in v1 — Tessera's adapters require CUDA.

**Related:** [Installation — GPU VRAM Requirements](installation.md#gpu-vram-requirements)

---

### Export button is grayed out

The Export button is disabled and cannot be clicked.

**Solutions:**

1. Run **Validate** first — export requires validation to complete (pass or fail).
2. Ensure a mesh object is selected in the viewport.
3. If validation failed, enable **Force Export** to export anyway.
4. Check that you have selected an export format (STL, OBJ, or 3MF).

**Related:** [Export & Print Guide](user-guide/export.md)

---

## Error Code Reference

### VRAM Errors

#### BF-E001 — GPU Memory Exhausted (Model Loading)
**Severity:** CRITICAL

The GPU ran out of memory while loading an AI model.

**Solutions:**
1. Close other GPU applications (games, other AI tools, video editors).
2. Switch to a smaller model variant in add-on preferences.
3. Restart Blender to free leaked GPU memory.

**Related:** [Installation — GPU VRAM Requirements](installation.md#gpu-vram-requirements)

---

#### BF-E002 — GPU Memory Exhausted (Inference)
**Severity:** CRITICAL

The GPU ran out of memory during model inference.

**Solutions:**
1. Close other GPU applications to free VRAM.
2. Reduce input image resolution before processing.
3. Switch to a smaller model variant in add-on preferences.

**Related:** [Preferences — GPU Device Selector](user-guide/preferences.md)

---

### Input Errors

#### BF-E003 — Unsupported Image Format
**Severity:** ERROR

The input image format is not supported.

**Solutions:**
1. Convert the image to PNG or JPEG format.
2. Use a different image file with a supported extension (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`).

**Related:** [Image Input — Supported Formats](user-guide/image-input.md#supported-formats)

---

#### BF-E004 — Image Resolution Too Low
**Severity:** ERROR

The input image is smaller than the minimum 256×256 pixels.

**Solutions:**
1. Use a higher resolution image (at least 256×256 pixels).
2. Re-capture the reference photo at a higher resolution.

**Related:** [Image Input — Image Requirements](user-guide/image-input.md#image-requirements)

---

#### BF-E005 — Blurry Image Detected
**Severity:** WARNING

The input image appears blurry, which may reduce output quality.

**Solutions:**
1. Use a sharper reference image.
2. Ensure the camera is focused on the object before capturing.

**Related:** [Image Input — Photography Tips](user-guide/image-input.md#photography-tips)

---

### Model Errors

#### BF-E006 — Model Weights Not Found
**Severity:** ERROR

The required AI model weights have not been downloaded.

**Solutions:**
1. Download model weights via the Tessera Model Manager panel.
2. Check that the cache directory path is correct in add-on preferences.
3. Verify your internet connection and retry the download.

**Related:** [Installation — Model Weight Download](installation.md#model-weight-download)

---

#### BF-E007 — Model Weights Corrupted
**Severity:** ERROR

The model weight file does not match the expected checksum.

**Solutions:**
1. Delete the corrupted weight file and re-download via the Model Manager.
2. Check available disk space — incomplete downloads cause corruption.
3. Verify your internet connection is stable before re-downloading.

**Related:** [Installation — Model Weight Download](installation.md#model-weight-download)

---

#### BF-E008 — Empty Mesh Produced
**Severity:** ERROR

The reconstruction model could not generate geometry from the input.

**Solutions:**
1. Try a different reference image with clearer object boundaries.
2. Ensure the object is well-lit and centered in the image.
3. Try a different reconstruction adapter in add-on preferences.

**Related:** [3D Reconstruction — Troubleshooting](user-guide/reconstruction.md)

---

#### BF-E009 — Reconstruction Timeout
**Severity:** ERROR

The reconstruction operation exceeded the 120-second time limit.

**Solutions:**
1. Try a simpler object or lower-resolution input image.
2. Switch to a faster reconstruction adapter (e.g., InstantMesh).
3. Close other GPU applications to free processing resources.

**Related:** [3D Reconstruction — Choosing an Adapter](user-guide/reconstruction.md#choosing-an-adapter)

---

### Export Errors

#### BF-E010 — Non-Manifold Output
**Severity:** WARNING

The mesh cleanup pipeline could not fully repair the mesh topology.

**Solutions:**
1. Try enabling 'Auto Voxel Fallback' in cleanup settings.
2. Manually inspect the mesh for severe topology issues in Edit Mode.
3. Try a different reconstruction adapter for a cleaner initial mesh.

**Related:** [Mesh Cleanup Guide](user-guide/mesh-cleanup.md)

---

#### BF-E011 — Export Directory Not Writable
**Severity:** ERROR

Cannot save files to the specified export location.

**Solutions:**
1. Choose a different export directory with write permissions.
2. Check that the disk has sufficient free space.
3. Save the `.blend` file first to establish a default export directory.

**Related:** [Export & Print — Export Workflow](user-guide/export.md#export-workflow)

---

### Blender Errors

#### BF-E012 — Incompatible Blender Version
**Severity:** CRITICAL

Tessera requires Blender 4.2 or newer.

**Solutions:**
1. Update Blender to version 4.2 LTS or newer from [blender.org](https://www.blender.org/download/).
2. Check the Tessera documentation for supported Blender versions.

**Related:** [Installation — Prerequisites](installation.md#prerequisites)

---

#### BF-E013 — No GPU Detected
**Severity:** CRITICAL

No supported GPU was detected. Tessera requires an NVIDIA GPU with CUDA; AMD and Apple Silicon GPUs are detected but not supported in v1.

**Solutions:**
1. Install the latest NVIDIA drivers.
2. Verify the GPU is recognized in **Blender Preferences → System → GPU Backend**.
3. If you are on an AMD card or an Apple Silicon Mac, Tessera cannot run inference yet — support is planned, not shipped.

**Related:** [Installation — GPU VRAM Requirements](installation.md#gpu-vram-requirements)

---

#### BF-E014 — Missing Python Dependency
**Severity:** ERROR

A required Python library could not be imported.

**Solutions:**
1. Re-install the Tessera add-on from the latest release ZIP.
2. Check the Tessera documentation for dependency requirements.
3. Report this issue on GitHub with your Blender and Python version.

**Related:** [Installation — Build from Source](installation.md#build-from-source)

---

#### BF-E016 — 3MF Exporter Not Available
**Severity:** WARNING

The built-in 3MF export functionality could not be found.

**Solutions:**
1. Enable 'Import/Export: 3MF' in **Blender Preferences → Add-ons**.
2. Update Blender to version 4.2+ which includes built-in 3MF support.
3. Export to STL format instead if 3MF is not required.

**Related:** [Export & Print — Export Formats](user-guide/export.md#export-formats)

---

### System Errors

#### BF-E015 — Insufficient Disk Space
**Severity:** ERROR

Not enough disk space for model weights (requires ≥2 GB).

**Solutions:**
1. Free disk space by deleting unused files.
2. Change the model cache directory to a drive with more space.
3. Check available disk space with your system's disk utility.

**Related:** [Preferences — Model Cache Directory](user-guide/preferences.md)

---

#### BF-E999 — Unexpected Error
**Severity:** ERROR

An unclassified error occurred.

**Solutions:**
1. Restart Blender and try again.
2. Check the Blender system console for detailed error information.
3. Report this issue on [GitHub](https://github.com/Expansive-Labs-LLC/tessera/issues) with steps to reproduce.

**Related:** [FAQ — How do I report a bug?](faq.md#how-do-i-report-a-bug)

---

## Getting Help

If the solutions above don't resolve your issue:

1. Check the [FAQ](faq.md) for additional answers.
2. Search [Tessera GitHub Issues](https://github.com/Expansive-Labs-LLC/tessera/issues) for known issues.
3. Open a new issue with:
   - Your Blender version and OS
   - GPU model and VRAM
   - The exact error code displayed
   - Steps to reproduce the issue
