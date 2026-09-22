# Product Description — Source of Truth

> **This file is canonical.** Every marketplace listing is an adaptation of the text below. If a claim changes here, update all three files in `copy/platform-adaptations/` in the same commit (NFR-008: 100% feature parity).
>
> **Price tokens:** listing copy uses `$[PRICE]` until CSO confirms (CON-004). Recommended values live in [../pricing/pricing-strategy.md](../pricing/pricing-strategy.md).

---

## Title

**Tessera — AI-Powered Image-to-3D for Blender**

## Tagline (≤ 64 characters, matches `blender_manifest.toml`)

`AI-powered 3D-printable model generation from reference images`

## Alternate tagline (≤ 80 characters, for paid channels)

`Turn reference photos into print-ready 3D models, entirely within Blender`

---

## Body

Turning a photo of something into a thing you can actually print takes either hours of CAD work or a skill you don't have. The AI services that promise to skip that step hand back meshes that look fine on screen and fail in the slicer — non-manifold edges, paper-thin walls, no real-world scale, and geometry you can't edit because it arrived as a finished download.

Tessera closes that gap inside Blender. Load one to six reference photos of an object — or a sketch on paper, photographed with your phone — and Tessera reconstructs the geometry, cleans the topology, validates it against real printer constraints, and hands you a watertight mesh scaled in millimetres, sitting in your scene as editable Blender geometry.

The part nobody else ships is the validation. Before export, Tessera checks the mesh for non-manifold edges, self-intersections, zero-area faces, minimum wall thickness, overhang angle, and build-volume fit against your printer's actual dimensions — and repairs what it can automatically. You see a pass/fail report, not a surprise at the slicer.

When the result is close but not right, you don't start over. Tell Tessera "make the base 5 mm thicker" or "smooth the edges" in plain language and it modifies the geometry in place, then re-runs validation. Set exact dimensions, or let Tessera infer scale from the object type. Let it orient the model to minimise supports.

All of it runs on your own GPU. There is no account to create, no API key to paste, no per-generation credit to buy, and no image ever leaves your machine — which matters if you're reconstructing a client's part or a prototype under NDA. The AI weights download once on first use and run locally from then on.

Tessera is free software under GPL-2.0-or-later, with the full source on GitHub. What you're buying here is the packaged, tested build, one-click install, update notifications, and direct support from the people who wrote it.

---

## Key Features

- **Multi-view reconstruction** — combine 2–6 reference images, with view labels as pose priors for accurate geometry
- **Single-image generation** — produce a 3D model from one photo or render
- **Sketch-to-3D** — draw a shape on paper, photograph it, get a symmetric 3D object back
- **Pluggable reconstruction engines** — Trellis, multi-view, and sketch pipelines behind one adapter layer, selected automatically for your VRAM and image count
- **AI mesh cleanup** — automatic topology repair, quad-dominant remeshing, decimation, and normal recalculation
- **Print-readiness validation** — manifold, watertight, self-intersection, zero-area face, wall thickness, overhang, and build-volume checks with auto-repair
- **Built-in printer profiles** — Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3 and Elegoo Saturn 3, with real build volumes and FDM/SLA wall-thickness defaults
- **Real-world scaling** — set exact millimetre dimensions or let Tessera infer them from the object
- **Print orientation optimiser** — auto-orient to minimise supports and flatten the base
- **Natural-language refinement** — "make the handle thicker" updates the model in place and re-validates
- **STL / 3MF / OBJ export** — correct mm scaling, with print metadata embedded in 3MF
- **100% local GPU inference** — runs on your own NVIDIA GPU: no cloud, no API keys, no telemetry, no data leaving your machine
- **Bring your own models** — the bundled model list is a starting point, not a limit: add any compatible checkpoint from Hugging Face and Tessera licence-checks it, pins the commit and verifies every file before downloading
- **Editable Blender output** — named object hierarchy you can keep modelling, not a black-box download

## System Requirements

| | Minimum | Recommended |
|---|---|---|
| **Blender** | 4.2 LTS | 4.3+ |
| **GPU** | **NVIDIA with CUDA** (required) | NVIDIA RTX 3060 or better |
| **VRAM** | 8 GB | 12 GB |
| **System RAM** | 16 GB | 32 GB |
| **Disk** | 5.5 GB for model weights | 10 GB |
| **OS** | Windows 10+ or Linux | — |

> ⚠️ **Tessera requires an NVIDIA CUDA GPU.** AMD GPUs, Apple Silicon Macs, integrated graphics, and CPU-only systems are **not supported** in v1 — every inference adapter runs on CUDA. Model weights (~5.5 GB) download on first use and need an internet connection once.

## What You Get

- A **pre-built, tested `.zip`** — install in one click, no build toolchain, no Python environment surgery
- **Update notifications** when new versions ship
- **Direct email support** for installation and usage questions, from the developers
- **The source code is also free.** Tessera is GPL-2.0-or-later and the full source is on [GitHub](https://github.com/Expansive-Labs-LLC/tessera). If you would rather build it yourself, you can — this listing sells the packaging, testing, and support, not exclusive access

## Links

- Documentation — https://expansivelabs.io/tessera/
- Source code — https://github.com/Expansive-Labs-LLC/tessera
- Issue tracker — https://github.com/Expansive-Labs-LLC/tessera/issues
- Support — hello@expansivelabs.com
