# Superhive Listing Copy — Paste-Ready

> Superhive is the platform formerly known as **Blender Market** (`superhivemarket.com`). SPEC-TS-0015 refers to it as "BlenderMarket" throughout — see GTM-STRATEGY §11 deviation 2.
>
> **Price tokens:** replace `$[PRICE]` before publishing (CON-004 — pending CSO D1). Recommended: `$49` at v1.0.
>
> Source of truth: [../product-description.md](../product-description.md).

---

## Product metadata

| Field | Value |
|---|---|
| Product name | `Tessera — AI Image-to-3D for Blender` |
| Category | Add-ons → Modeling |
| Secondary category | Add-ons → Import/Export (if a second is allowed) |
| Blender versions | 4.2, 4.3, 4.4 |
| Operating systems | Windows, Linux |
| Licence | GPL-2.0-or-later |
| Price | `$[PRICE]` USD |
| Tags | `ai`, `3d-printing`, `image-to-3d`, `photogrammetry`, `mesh`, `stl`, `reconstruction`, `modeling` |
| Support email | `hello@expansivelabs.com` |
| Documentation URL | `https://expansivelabs.io/tessera/` |

## Product requirements field (Superhive shows this prominently — use it)

```
Requires an NVIDIA CUDA GPU with 8 GB+ VRAM (12 GB recommended).
AMD GPUs, Apple Silicon Macs, integrated graphics and CPU-only systems are NOT
supported in v1 — every inference adapter runs on CUDA.
A one-time ~5 GB download of AI model weights is required on first use.
```

---

## Short description (search results / card)

```
Reference photos in, print-ready 3D models out — validated for manifold geometry, wall thickness, and your printer's build volume. Runs entirely on your own GPU.
```

## Full description

### Print the thing in the photo.

Turning a photo of an object into a model you can actually print takes either hours of CAD work or a skill you don't have. The AI services that promise to skip that step hand back meshes that look fine on screen and fail in the slicer — non-manifold edges, paper-thin walls, no real-world scale, and geometry you can't edit because it arrived as a finished download.

Tessera closes that gap inside Blender. Load one to six reference photos of an object — or a sketch on paper, photographed with your phone — and Tessera reconstructs the geometry, cleans the topology, validates it against real printer constraints, and hands you a watertight mesh scaled in millimetres, sitting in your scene as editable Blender geometry.

### Validation is the feature

Before export, Tessera checks every mesh for:

- Non-manifold edges → auto-repaired by hole fill and merge-by-distance
- Self-intersections → detected by BVH overlap testing
- Zero-area and degenerate faces → dissolved
- Minimum wall thickness → measured by inward ray-cast, with FDM and SLA defaults
- Overhang angle → flagged against the build-plate normal, with auto-orientation
- Positive volume → confirms a genuinely closed surface
- Build-volume fit → against your actual printer's dimensions

You get a pass/fail report inside Blender before you export, not a surprise in the slicer.

### Refine in plain language

"Make the base 5 mm thicker." "Smooth the edges." Tessera resolves the region, modifies the geometry in place, and re-runs validation. No regeneration, no starting over.

### Built for real printers

Printer profiles for Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3 and Elegoo Saturn 3 carry real build volumes and FDM/SLA wall-thickness defaults. Set exact millimetre dimensions or let Tessera infer them, then let the orientation optimiser minimise your support material.

### Runs entirely on your machine

No account, no API key, no per-generation credits, no subscription, no telemetry, and no image ever leaving your computer — which matters when the part belongs to a client. Model weights download once on first use and run locally from then on.

### Full feature list

**Input** — 1–6 reference images; view labels as pose priors; automatic view classification; background segmentation; phone-camera tolerant

**Reconstruction** — single-image, few-image and multi-view paths; sketch-to-3D with symmetry priors; pluggable adapter architecture; automatic engine selection by VRAM and image count

**Mesh processing** — topology repair; quad-dominant remeshing; decimation to a polygon budget; normal recalculation; watertight repair via voxel remesh; cleanup diagnostics

**Validation** — the seven checks above, with auto-repair and an explicit force-export override

**Scaling & orientation** — exact mm dimensions; inferred scale; printer profiles; support-minimising orientation; base flattening; over-volume warnings

**Refinement** — natural-language edits; spatial region resolution; automatic re-validation; Blender undo/redo integration

**Export** — STL, 3MF (with embedded print metadata), OBJ, and `.blend`; correct mm scaling throughout

**Models** — no weights are bundled; a curated set downloads on first run and the list is user-extensible from Hugging Face, with every addition licence-classified, commit-pinned and checksum-verified before download

### Open source

Tessera is GPL-2.0-or-later and the source is public on [GitHub](https://github.com/Expansive-Labs-LLC/tessera). Buying here gets you the packaged, tested build plus support and updates — and funds the next version. Building from source is free and always will be.

AI model weights download separately and carry their own licences; see MODEL-LICENSES.md in the repository.

### Documentation & support

Full documentation, troubleshooting guide, and error-code reference at https://expansivelabs.io/tessera/ — support at hello@expansivelabs.com.

---

## Seller bio — Expansive Labs LLC

```
Expansive Labs builds practical AI tooling for people who make physical things. Tessera came out of a simple frustration: the gap between having a photo of an object and having a file you can print is still measured in hours of CAD work, and the AI services that claim to close it produce meshes that fail in the slicer. We build tools that run on your own hardware, keep your data on your machine, and ship as open source. Support: hello@expansivelabs.com
```

## Gallery order

1. Demo video (60–90 s photo→print clip) — Superhive weights video heavily
2. `hero-banner.png`
3. `04-validation.png`
4. `01-image-upload.png`
5. `02-reconstruction.png`
6. `05-export.png`
7. `03-mesh-cleanup.png`
8. `07-scaling-panel.png`

## FAQ

Paste [../faq.md](../faq.md) verbatim, keeping the Superhive paragraph in "How do I get updates?".

## ⚠️ Do not include

- Any link to the Gumroad listing, or the phrase "lifetime updates available elsewhere" — Superhive's 12-month support policy applies to this listing; differentiating on it is fine in *your own* channels, not inside a Superhive product page.
- Any claim of exclusivity. The product is GPL and also on GitHub; say so plainly instead.
