# Tessera — Image-to-3D for Blender

![Tessera main panel showing Image Input, Generation, Validation, and Export sections in the Blender 3D Viewport sidebar](assets/screenshots/main-panel.png)

**Transform reference photos into print-ready 3D models, entirely within Blender.**

Tessera is a Blender add-on that combines AI-powered vision analysis with multi-view 3D reconstruction to generate production-quality meshes from as few as 1–6 reference images. The full pipeline — from image input through validation and export — runs locally on your GPU with zero cloud dependencies. Your data never leaves your machine.

---

## ✨ Key Features

- **AI-Powered Vision Pipeline** — SAM 2 segmentation, Depth Anything V2, DINOv2 feature extraction
- **Multi-View Reconstruction** — TripoSR, InstantMesh, and CRM adapters with automatic model management
- **Sketch-to-3D** — Generate 3D models from hand-drawn sketches and line art
- **Mesh Cleanup & Topology Optimization** — Manifold repair, degenerate removal, voxel/quad remesh
- **Print-Readiness Validation** — Wall thickness, overhang angle, build volume, watertightness checks
- **Natural Language Refinement** — Describe modifications in plain English via LLM-powered chat
- **Real-World Scaling & Print Orientation** — Auto-infer dimensions from object class or set manual targets
- **Multi-Format Export** — STL, OBJ, and 3MF with embedded print metadata
- **Local GPU Inference** — All AI models run on your hardware; no cloud APIs, no subscriptions

## 🚀 Quick Start

1. [Install Tessera](installation.md) in Blender 4.2+
2. Follow the [Quick Start Guide](quickstart.md) to create your first model in 5 steps
3. Explore the [User Guide](user-guide/image-input.md) for advanced features

## 📋 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Blender | 4.2 LTS | 4.3+ |
| GPU | NVIDIA CUDA or Apple Silicon MPS, 4 GB VRAM | 8+ GB VRAM |
| RAM | 8 GB | 16+ GB |
| Disk | 2 GB (model weights) | 5+ GB |
| OS | Windows 10+, macOS 13+ (Apple Silicon), Linux | — |

## 📖 Documentation

- [Installation Guide](installation.md) — Platform-specific setup instructions
- [Quick Start](quickstart.md) — Create your first 3D model in 5 steps
- [User Guide](user-guide/image-input.md) — Detailed feature documentation
- [Reference](reference/view-labels.md) — View labels, shortcuts, printer profiles, glossary
- [FAQ](faq.md) — Answers to common questions
- [API Reference](api/pipeline.md) — Developer documentation
- [Troubleshooting](troubleshooting.md) — Error codes and solutions
- [Gallery](gallery/index.md) — Example outputs and print results

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
