# Gumroad Listing Copy — Paste-Ready

> **Price tokens:** replace `$[PRICE]` before publishing (CON-004 — pending CSO D1). Recommended: `$29` early access, `$49` at v1.0.
> `sed -i 's/\$\[PRICE\]/$29/g' copy/platform-adaptations/gumroad.md`
>
> Source of truth: [../product-description.md](../product-description.md). Do not let this file drift.

---

## Product name

```
Tessera — AI Image-to-3D for Blender
```

## Custom URL slug

```
tessera-blender
```

## Summary line (shows under the title)

```
Turn reference photos into print-ready 3D models, entirely inside Blender. Runs on your GPU — no cloud, no API keys, no subscription.
```

## Price

`$[PRICE]` USD — one-time. **Lifetime updates included.**

## Cover image

`../../assets/hero-banner.png` (1920×600 minimum)

---

## Description (paste into the Gumroad rich-text editor)

### Print the thing in the photo.

Turning a photo of something into a model you can actually print takes either hours of CAD work or a skill you don't have. The AI services that promise to skip that step hand back meshes that look fine on screen and fail in the slicer — non-manifold edges, paper-thin walls, no real-world scale, and geometry you can't edit because it arrived as a finished download.

Tessera closes that gap inside Blender. Load one to six reference photos of an object — or a sketch on paper, photographed with your phone — and Tessera reconstructs the geometry, cleans the topology, validates it against your printer's real constraints, and hands you a watertight mesh scaled in millimetres, sitting in your scene as editable Blender geometry.

### The part nobody else ships

Before export, Tessera checks the mesh for non-manifold edges, self-intersections, zero-area faces, minimum wall thickness, overhang angle, and build-volume fit against your printer's actual dimensions — and repairs what it can automatically. You get a pass/fail report, not a surprise at the slicer.

### Close, but not right? Just say so.

"Make the base 5 mm thicker." "Smooth the edges." Tessera modifies the geometry in place and re-runs validation. Set exact millimetre dimensions, or let it infer scale. Let it orient the model to minimise supports.

### Everything runs on your machine

No account. No API key. No per-generation credits. No image ever leaves your computer — which matters when the part belongs to a client. Model weights download once on first use and run locally from then on.

---

### What's included

- ✅ Pre-built, tested `.zip` — one-click install, no build toolchain
- ✅ **Lifetime updates** — every future version, free, for as long as the product exists
- ✅ Direct email support from the developers
- ✅ Full documentation and troubleshooting guide

### Features

- Multi-view reconstruction from 2–6 reference images
- Single-image generation from one photo
- Sketch-to-3D — photograph a drawing, get a model
- Automatic mesh cleanup, remeshing, and decimation
- Print-readiness validation with auto-repair
- Printer profiles: Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, Elegoo Saturn 3
- Real-world millimetre scaling
- Support-minimising print orientation
- Natural-language refinement
- STL / 3MF / OBJ export with print metadata
- 100% local GPU inference — no cloud, no telemetry
- Bring your own models from Hugging Face — licence-checked and verified automatically

---

### ⚠️ System requirements — please read before buying

| | Minimum | Recommended |
|---|---|---|
| Blender | 4.2 LTS | 4.3+ |
| GPU | **NVIDIA CUDA** (required) | RTX 3060 or better |
| VRAM | 8 GB | 12 GB |
| RAM | 16 GB | 32 GB |
| Disk | 5.5 GB for model weights | 10 GB |
| OS | Windows 10+ or Linux | — |

**Tessera requires an NVIDIA CUDA GPU. AMD GPUs, Apple Silicon Macs, integrated graphics, and CPU-only systems are not supported in v1.** Model weights (~5.5 GB) download on first use and need an internet connection once. If you are unsure whether your machine qualifies, email us before you buy — we would rather answer a question than process a refund.

---

### Licence & open source

Tessera is licensed under **GPL-2.0-or-later**, and the source code is freely available on [GitHub](https://github.com/Expansive-Labs-LLC/tessera). Your purchase supports continued development and includes a pre-built tested package, lifetime update access, and email support. If you prefer to build from source, visit the repository — that path is free and always will be.

AI model weights are downloaded separately and carry their own licences; see [MODEL-LICENSES.md](https://github.com/Expansive-Labs-LLC/tessera/blob/main/MODEL-LICENSES.md).

### Support & refunds

Questions, install help, bug reports: **hello@expansivelabs.com**

30-day no-questions-asked refund. (And yes — the source is free on GitHub, so if the package isn't worth it to you, take the refund and build it yourself.)

### Links

- 📖 Documentation — https://expansivelabs.io/tessera/
- 💾 Source — https://github.com/Expansive-Labs-LLC/tessera
- 🐛 Issues — https://github.com/Expansive-Labs-LLC/tessera/issues

---

## Gumroad configuration values

| Setting | Value |
|---|---|
| Product type | Digital product |
| Delivery | Direct download, single file |
| File | `tessera-v<VERSION>.zip` from the GitHub Release |
| Tags | `blender`, `3d-printing`, `ai`, `addon`, `3d-modeling`, `stl` |
| Support email | `hello@expansivelabs.com` |
| Refund policy | 30-day, no questions asked |
| Gumroad Discover | **OFF** — Discover sales cost 30% vs ~13%; it drives no meaningful Blender add-on traffic |
| Receipt note | "Your licence includes lifetime updates. You'll get an email whenever a new version ships." |
| Launch coupon | `TESSERA-LAUNCH` — see pricing strategy for amount and window |

## Gallery order (matters — first two do the selling)

1. `hero-banner.png`
2. Demo video (the 60–90 s photo→print clip)
3. `04-validation.png` — the validation report, the differentiator
4. `01-image-upload.png`
5. `02-reconstruction.png`
6. `05-export.png`
7. `03-mesh-cleanup.png`
8. `06-refinement-chat.png`

## FAQ

Paste [../faq.md](../faq.md) verbatim, minus the "How do I get updates?" Superhive paragraph.
