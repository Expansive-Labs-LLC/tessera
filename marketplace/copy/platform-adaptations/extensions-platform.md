# Blender Extensions Platform Listing Copy

> ## 🔴 DO NOT SUBMIT YET
>
> Tessera is **not eligible** for extensions.blender.org as currently architected. Blender's add-on guidelines state add-ons *"must not install Python modules, PIP packages, Python-wheels etc."*, and `requirements.txt` documents that the ML stack is downloaded into Blender's environment at runtime. Bundled wheels are not a workaround either — uploads above ~200 MB are rejected, and a CUDA `torch` wheel alone far exceeds that.
>
> A submission today would be rejected publicly, which makes a later attempt harder. See GTM-STRATEGY §2.1 and the pending dependency ADR (CSO decision D3).
>
> This file is the listing copy to use **once that blocker clears**.

---

## Metadata (must match `blender_manifest.toml` exactly)

| Field | Value |
|---|---|
| Name | `Tessera` |
| Tagline (≤ 64 chars) | `AI-powered 3D-printable model generation from reference images` |
| Type | Add-on |
| Category | 3D View |
| Licence | `SPDX:GPL-2.0-or-later` |
| Blender version min | `4.2.0` |
| Maintainer | `Expansive Labs LLC <hello@expansivelabs.com>` |
| Tags | `ai`, `3d-printing`, `reconstruction`, `mesh`, `modeling` |
| Permissions — files | Import reference images and export 3D models |
| Permissions — network | Download AI model weights on first use |

---

## Description

Tessera turns reference photographs into 3D-printable geometry without leaving Blender.

Load one to six reference images of an object — or a photographed sketch — and Tessera reconstructs the geometry, cleans the topology, validates it for printing, and places the result in your scene as editable Blender geometry, scaled in millimetres.

**Reconstruction.** Single-image, few-image, and multi-view paths, plus a sketch-to-3D pipeline with symmetry priors. View labels act as pose priors; unlabelled images are classified automatically. Reconstruction engines sit behind a pluggable adapter layer and are selected automatically based on available VRAM and image count.

**Mesh processing.** Topology repair, quad-dominant remeshing, decimation to a polygon budget, normal recalculation, and watertight repair via voxel remesh, with diagnostics reporting what changed.

**Print validation.** Before export, Tessera checks non-manifold edges, self-intersections, zero-area faces, minimum wall thickness, overhang angle, positive volume, and build-volume fit, repairing what it can automatically and reporting the rest as pass/warn/fail.

**Scaling and orientation.** Exact millimetre dimensions or inferred scale, printer profiles carrying real build volumes (Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, Elegoo Saturn 3), a support-minimising orientation optimiser, and base flattening.

**Refinement.** Edit the result with plain-language commands such as "make the base 5 mm thicker"; Tessera resolves the region, modifies the geometry in place, and re-validates.

**Export.** STL, 3MF with embedded print metadata, OBJ, and `.blend`, with correct millimetre scaling throughout.

**Your own models.** The bundled model list is a default, not a limit: any compatible checkpoint can be added from Hugging Face, and Tessera reads its declared licence, pins the commit and verifies every file before downloading.

**Local inference.** All AI models run on your own GPU. No account, no API key, and no telemetry. Model weights (~5 GB) are downloaded once on first use; Tessera respects Blender's Allow Online Access preference and performs no network activity when it is disabled.

### Requirements

- Blender 4.2 LTS or newer
- NVIDIA GPU with CUDA support (AMD and Apple Silicon are not supported in v1)
- 8 GB VRAM minimum (12 GB recommended), 16 GB system RAM
- 5.5 GB free disk space for model weights
- AMD GPUs, Apple Silicon Macs, integrated graphics, and CPU-only systems are not supported

### Links

- Documentation: https://expansivelabs.io/tessera/
- Source code: https://github.com/Expansive-Labs-LLC/tessera
- Report an issue: https://github.com/Expansive-Labs-LLC/tessera/issues

---

## ⚠️ Compliance rules for this listing (CON-002, FR-017)

The Extensions Platform is free-only and prohibits commercial advertising. This listing — and the add-on UI itself, and `blender_manifest.toml` — **SHALL NOT** contain:

- ❌ Links to Gumroad, Superhive, or any paid marketplace
- ❌ Prices, purchase calls-to-action, or discount codes
- ❌ The words "premium", "pro", "paid version", or any implication of a commercial tier
- ❌ Links to GitHub Sponsors or `.github/FUNDING.yml`
- ❌ Donation appeals of any kind

Listing on extensions.blender.org while also selling on Gumroad/Superhive is explicitly permitted by the platform — the constraint is only that the free listing must not advertise the paid ones.

**Before submitting, re-verify:** that the network permission reason in `blender_manifest.toml` matches actual behaviour, that `bpy.app.online_access` is honoured before any download, and that no UI string anywhere in `tessera/ui/` mentions purchasing.
