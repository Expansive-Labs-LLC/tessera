# Error Codes

Quick-reference table for all Tessera error codes. Click a code for detailed troubleshooting steps.

---

## Error Code Quick Reference

| Code | Severity | Category | Description | Details |
|------|----------|----------|-------------|---------|
| BF-E001 | CRITICAL | VRAM | GPU memory exhausted while loading model | [Troubleshooting](../troubleshooting.md#bf-e001--gpu-memory-exhausted-model-loading) |
| BF-E002 | CRITICAL | VRAM | GPU memory exhausted during inference | [Troubleshooting](../troubleshooting.md#bf-e002--gpu-memory-exhausted-inference) |
| BF-E003 | ERROR | Input | Unsupported image format | [Troubleshooting](../troubleshooting.md#bf-e003--unsupported-image-format) |
| BF-E004 | ERROR | Input | Image resolution too low (min 256×256) | [Troubleshooting](../troubleshooting.md#bf-e004--image-resolution-too-low) |
| BF-E005 | WARNING | Input | Blurry image detected | [Troubleshooting](../troubleshooting.md#bf-e005--blurry-image-detected) |
| BF-E006 | ERROR | Model | Model weight file not found | [Troubleshooting](../troubleshooting.md#bf-e006--model-weights-not-found) |
| BF-E007 | ERROR | Model | Model weight file corrupted (hash mismatch) | [Troubleshooting](../troubleshooting.md#bf-e007--model-weights-corrupted) |
| BF-E008 | ERROR | Model | Reconstruction produced empty mesh | [Troubleshooting](../troubleshooting.md#bf-e008--empty-mesh-produced) |
| BF-E009 | ERROR | Model | Reconstruction timed out (>120s) | [Troubleshooting](../troubleshooting.md#bf-e009--reconstruction-timeout) |
| BF-E010 | WARNING | Export | Mesh cleanup failed to produce manifold | [Troubleshooting](../troubleshooting.md#bf-e010--non-manifold-output) |
| BF-E011 | ERROR | Export | Export directory not writable | [Troubleshooting](../troubleshooting.md#bf-e011--export-directory-not-writable) |
| BF-E012 | CRITICAL | Blender | Incompatible Blender version (<4.2) | [Troubleshooting](../troubleshooting.md#bf-e012--incompatible-blender-version) |
| BF-E013 | CRITICAL | Blender | No CUDA/ROCm GPU detected | [Troubleshooting](../troubleshooting.md#bf-e013--no-gpu-detected) |
| BF-E014 | ERROR | Blender | Required Python dependency missing | [Troubleshooting](../troubleshooting.md#bf-e014--missing-python-dependency) |
| BF-E015 | ERROR | System | Insufficient disk space for model weights | [Troubleshooting](../troubleshooting.md#bf-e015--insufficient-disk-space) |
| BF-E016 | WARNING | Blender | 3MF exporter add-on not available | [Troubleshooting](../troubleshooting.md#bf-e016--3mf-exporter-not-available) |
| BF-E999 | ERROR | System | Unexpected/unclassified error | [Troubleshooting](../troubleshooting.md#bf-e999--unexpected-error) |

---

## Severity Levels

| Severity | Icon | Meaning |
|----------|------|---------|
| **CRITICAL** | 🔴 | Operation cannot continue; immediate action required |
| **ERROR** | 🟠 | Operation failed; user action needed to resolve |
| **WARNING** | 🟡 | Operation completed with caveats; results may be suboptimal |
| **INFO** | 🔵 | Informational message; no action required |

---

## Error Categories

| Category | Codes | Description |
|----------|-------|-------------|
| **VRAM** | BF-E001, BF-E002 | GPU memory issues |
| **Input** | BF-E003, BF-E004, BF-E005 | Image format or quality problems |
| **Model** | BF-E006, BF-E007, BF-E008, BF-E009 | AI model loading or inference failures |
| **Export** | BF-E010, BF-E011 | Mesh or file export issues |
| **Blender** | BF-E012, BF-E013, BF-E014, BF-E016 | Blender compatibility issues |
| **System** | BF-E015, BF-E999 | OS-level or unclassified errors |

---

## See Also

- [Troubleshooting](../troubleshooting.md) — Detailed error descriptions and solutions
- [FAQ](../faq.md) — Answers to common questions

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
