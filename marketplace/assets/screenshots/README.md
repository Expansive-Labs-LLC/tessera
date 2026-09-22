# Marketplace Screenshot Manifest

> Listing imagery for Gumroad and Superhive. **Separate from** the documentation screenshots in `docs/docs/assets/screenshots/` — those explain, these sell. Some scenes overlap; capture both in one session using [docs/RUNBOOK-screenshot-capture.md](../../../docs/RUNBOOK-screenshot-capture.md) for the environment setup.
>
> The files in this directory are **1×1 transparent placeholders** (CON-007, FR-014). Replace them with real captures before any listing goes live.
>
> The hero banner (`../hero-banner.png`) is **no longer a placeholder** — it is a 2400×750 illustrated banner (generated, not photographed). It is usable for draft listings and previews, but it does not yet satisfy the third panel of the brief below, which calls for a photograph of the real printed part. Replace it once a part has been printed and photographed.

---

## Environment (identical for every capture)

| Setting | Value |
|---|---|
| Blender version | 4.2 LTS or newer |
| Theme | **Blender default dark** — do not customise |
| Window size | 1920×1080, maximised, on a 1920×1080 display |
| Viewport shading | Material Preview |
| Sidebar | Open (`N`), Tessera tab selected |
| Scene file | Saved as `tessera-demo.blend` — no personal paths in the title bar |
| Subject | One real object photographed from 3+ angles. **Use a functional part** (bracket, knob, hook, adapter), not a figurine — it proves dimensional accuracy |

Before capturing: clear the Recent Files list, hide any second monitor, and confirm no file path in the header reveals a personal directory.

## Annotation style (FR-015)

| Element | Spec |
|---|---|
| Arrow / callout colour | `#FFD700` gold — reads on Blender's dark grey |
| Label font | Inter, Roboto, or any clean sans — **≥ 14 pt** at 1920×1080 |
| Label background | `#000000` at 60% opacity, 4 px padding, 2 px corner radius |
| Arrows per image | **1–2 maximum.** More than two and nobody reads any of them |
| Tool | GIMP, Figma, or equivalent |

Marketplace thumbnails render small. Every annotation must survive being shrunk to 400 px wide — check each one at that size before committing it.

---

## Required captures

| # | Filename | What it shows | Setup | Annotation |
|---|---|---|---|---|
| 1 | `01-image-upload.png` | Image Input panel with 3+ reference photos loaded and view labels assigned | Load 3 photos of the subject, assign front/left/back | Arrow → the view-label dropdown: "View labels improve accuracy" |
| 2 | `02-reconstruction.png` | Generation panel mid-run with the progress bar visible | Start a generation, capture at ~40–60% | Arrow → progress bar: "Runs locally on your GPU" |
| 3 | `03-mesh-cleanup.png` | Mesh Cleanup panel with topology controls and post-cleanup diagnostics | Run cleanup on the generated mesh; wireframe overlay on to show topology | Arrow → diagnostics: "Quad-dominant topology, automatically" |
| 4 | `04-validation.png` | **The money shot** — Print Validation results with pass/fail checks | Run validation on a mesh that passes manifold/watertight/thickness and warns on one overhang | Arrow → the check list: "Validated before it reaches your slicer" |
| 5 | `05-export.png` | Export panel with format and printer profile selected | STL selected, printer profile dropdown open showing the five profiles | Arrow → profile dropdown: "Scaled in millimetres for your printer" |
| 6 | `06-refinement-chat.png` | NL refinement chat with a real exchange | Type "make the base 5 mm thicker", let it complete, capture the before/after | Arrow → the command: "Edit in plain language" |
| 7 | `07-scaling-panel.png` | Scaling & Orientation panel with mm dimensions entered | Enter an exact height, show the orientation optimiser control | Arrow → dimension field: "Exact real-world dimensions" |

Screenshots 1–5 are required (FR-010); 6–7 are strongly recommended (FR-012) — refinement and scaling are differentiators and deserve a frame each.

## Hero banner — `../hero-banner.png`

| Property | Spec |
|---|---|
| Dimensions | 1920×600 minimum (2400×750 preferred for retina listing cards) |
| Background | Dark, consistent with Blender's theme (`#1D1D1D`–`#2B2B2B`) |
| Composition | Three panels left→right: **reference photo → Blender viewport with the generated mesh → the physical printed part on a bed or in hand** |
| Text overlay | "Tessera" (large) + "Turn reference photos into print-ready 3D models" (sub) |
| Contrast | Tested legible at 600 px wide — listing cards downscale hard |
| What to avoid | Stock AI imagery, glowing neural-network motifs, generic "AI" iconography. The printed object is the proof; lead with it |

The third panel — the real printed part — does most of the work. Do not ship a banner that stops at the mesh.

### Current banner (interim)

`../hero-banner.png` is a 2400×750 illustrated banner that follows this composition — reference photos → quad-dominant mesh in a viewport → the part on a print bed — with the wordmark, tagline, and a gold accent matching the annotation colour. Everything in it is rendered geometry, not photography, and the same L-bracket appears in all three panels so the progression stays honest.

| Property | Status |
|---|---|
| Dimensions | 2400×750 ✅ |
| File size | ~208 KB, under the 500 KB per-image budget ✅ |
| `marketplace/` total | ~316 KB, under the 2 MB NFR-007 cap ✅ |
| Legible at 600 px | Wordmark, tagline and panel captions ✅; the badge labels and the strapline do not survive ⚠️ |
| Third panel is a real printed part | ❌ — illustrated, not photographed |

Regenerate or adjust it with `scripts/generate_hero_banner.py` (`--check` also writes the 600 px and 400 px downscales). Retire it in favour of a photographic banner before the paid listing goes live.

## Demo video (not a screenshot, but the highest-value asset)

60–90 seconds, no narration required, 1920×1080:

1. (0–10 s) Phone photo of a real object, or the physical object itself
2. (10–35 s) Images loaded into Tessera → Generate → mesh appears in the viewport
3. (35–50 s) Validation panel, green checks landing one by one
4. (50–60 s) Export → slicer → print timelapse
5. (60–90 s) The printed part in hand, fitting where it belongs

This clip is the Gumroad gallery item #2, the Superhive gallery item #1, the Reddit post, and the BlenderNation submission. Budget more time for it than for all seven screenshots combined.

## Pre-publication checklist

- [ ] All 7 screenshots captured at 1920×1080 and annotated
- [ ] Each one checked for legibility at 400 px wide
- [ ] No personal file paths, usernames, or second-monitor artefacts visible
- [x] Hero banner produced and checked at 600 px wide — interim illustrated version; still needs the real printed part in panel three
- [ ] Demo video recorded and uploaded (YouTube unlisted is fine as a source)
- [ ] Every image compressed under 500 KB (`pngquant --quality=65-85`)
- [ ] `marketplace/` total size still under 2 MB, or images hosted externally and the placeholders left in place (NFR-007)

> ⚠️ NFR-007 caps `marketplace/` at 2 MB. Seven annotated 1920×1080 PNGs plus a banner will exceed that. Either compress aggressively and check `du -sh marketplace/`, or keep the real assets outside the repo and leave placeholders here — decide before committing captures.
