# Tessera

**AI-powered Blender add-on that turns reference images into 3D-printable models**

![CI](https://github.com/Expansive-Labs-LLC/tessera/actions/workflows/ci.yml/badge.svg)
![Docs](https://github.com/Expansive-Labs-LLC/tessera/actions/workflows/docs.yml/badge.svg)
![License](https://img.shields.io/badge/License-GPL--2.0--or--later-blue.svg)
![Blender](https://img.shields.io/badge/Blender-4.2+-orange.svg)
![Release](https://img.shields.io/github/v/release/Expansive-Labs-LLC/tessera?include_prereleases)

Give the agent a couple of images and receive a watertight, manifold mesh ready for slicing. Tessera bridges the gap between "I have a picture of what I want" and "I have an STL on my print bed" — no 3D-modeling expertise required. All inference runs locally on your GPU with zero cloud dependencies.

## Features

- **Multi-view 3D reconstruction** — combine 2–6 reference images for accurate geometry
- **Single-image generation** — create 3D models from a single photo or render
- **Sketch-to-3D pathway** — draw a shape on paper, photograph it, get a 3D model
- **AI-powered mesh cleanup** — automatic topology optimization and quad-dominant remeshing
- **Print-readiness validation** — manifold, watertight, wall thickness, and overhang checks
- **STL / 3MF / OBJ export** — export with metadata, print settings, and correct mm scaling
- **Natural-language refinement** — say "make the handle thicker" and the model updates
- **Real-world scaling** — set exact dimensions or let the agent infer from object type
- **Print orientation optimizer** — automatically orient models to minimize supports
- **Local GPU inference** — all AI runs on your hardware with no data leaving your machine

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Blender** | 4.2 LTS | 4.3+ |
| **GPU** | NVIDIA with CUDA support _or_ Apple Silicon with MPS backend | NVIDIA RTX 3060+ |
| **VRAM** | 8 GB | 12 GB |
| **System RAM** | 16 GB | 32 GB |
| **Disk Space** | 5 GB (for model weights) | 10 GB |
| **Python** | 3.11+ (bundled with Blender) | — |

## Installation

### Marketplace Install

> [Marketplace link coming soon] — One-click install from the Blender Extensions Platform or Blender Market.

1. Open the marketplace listing.
2. Click **Install** — the add-on is downloaded and enabled automatically.
3. Open Blender → **Edit → Preferences → Add-ons** → verify "Tessera" is enabled.

### Build from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/Expansive-Labs-LLC/tessera.git
   ```
2. Navigate to the project root:
   ```bash
   cd tessera
   ```
3. Create the add-on ZIP:
   ```bash
   zip -r tessera-addon.zip tessera/
   ```
4. Open Blender → **Edit → Preferences → Add-ons**.
5. Click **Install…** → select `tessera-addon.zip`.
6. Enable the "Tessera" add-on in the list.

## Quick Start

1. **Open Blender** and ensure Tessera is enabled in Preferences → Add-ons.
2. **Open the Tessera panel** in the 3D Viewport sidebar (press `N` → Tessera tab).
3. **Load reference images** — click "Add Images" and select 1–6 photos of your object.
4. **Generate the model** — click "Generate" and wait for the pipeline to complete.
5. **Export for printing** — click "Export STL" to save a print-ready mesh file.

## Documentation

Full documentation is available at [https://expansivelabs.io/tessera/](https://expansivelabs.io/tessera/).

Key pages:

- [Installation Guide](https://expansivelabs.io/tessera/installation/)
- [User Guide: Image Input](https://expansivelabs.io/tessera/user-guide/image-input/)
- [API Reference: Pipeline](https://expansivelabs.io/tessera/api/pipeline/)
- [Troubleshooting](https://expansivelabs.io/tessera/troubleshooting/)

## Contributing

We welcome contributions from the community! Whether it's bug fixes, new features, or documentation improvements — every contribution helps make Tessera better.

Please read our [Contributing Guide](CONTRIBUTING.md) for details on the development workflow, commit conventions, and pull request process.

## License

This project is licensed under the **GNU General Public License v2.0 or later** — see the [LICENSE](LICENSE) file for details.

Documentation content is licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

## Security

Tessera runs all AI inference locally on your GPU. No data leaves your machine, and no telemetry or analytics are collected. For vulnerability reporting, see our [Security Policy](SECURITY.md).
