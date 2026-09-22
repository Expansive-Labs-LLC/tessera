# Marketplace FAQ

> Buyer-facing questions. Reuse verbatim on Gumroad and Superhive; the Extensions Platform version drops every pricing answer (see `platform-adaptations/extensions-platform.md`).

## Is Tessera open source?

Yes — GPL-2.0-or-later, with the full source on [GitHub](https://github.com/Expansive-Labs-LLC/tessera). Your purchase gets you the pre-built, tested package, update notifications, and direct support from the developers. If you would rather build it from source yourself, you can, and always will be able to.

## What GPU do I need?

An NVIDIA GPU with CUDA support and at least 8 GB of VRAM — 12 GB if you want multi-view reconstruction comfortably. Single-image reconstruction alone runs in 6 GB. **AMD GPUs, Apple Silicon Macs, integrated graphics and CPU-only systems are not supported in v1** — every inference adapter runs on CUDA. Check this before buying: it is the most common reason for a refund request.

## Does Tessera send my images to the cloud?

No. Every model runs locally on your GPU. There is no account, no API key, no per-generation credit, and no telemetry. The only network activity is the one-time download of the AI model weights (~5.5 GB) on first use, and Tessera respects Blender's "Allow Online Access" preference.

## Which Blender versions are supported?

Blender 4.2 LTS and newer, tested through 4.4. Tessera ships as a Blender extension with a `blender_manifest.toml`, so it installs the modern way on 4.2+.

## How long does a model take to generate?

On a recommended-spec machine (RTX 3060, 12 GB), a single-image reconstruction plus cleanup and validation typically completes in a few minutes; multi-view runs take longer and scale with image count. The first run is slower because model weights download once (~5.5 GB).

## How do I get updates?

**Gumroad:** updates are pushed to the same product page and you get an email whenever a new version ships — your licence includes updates for life. **Superhive:** download new versions from your Superhive library; per Superhive's platform policy, purchases include 12 months of updates and support, after which newer versions are available at 50% of list price.

## Can I use my own models?

Yes. Tessera ships no weights — a small curated set downloads on first run, and the list is user-extensible: add any compatible checkpoint from Hugging Face and Tessera reads the publisher's declared licence, pins the exact commit and records a checksum for every file before anything downloads. Anything non-commercial, restricted or undeclared is refused unless you explicitly enable it. Your additions live beside the model cache, so they survive add-on updates.

## Can I use Tessera commercially?

Yes — GPL-2.0-or-later permits commercial use, and models you generate are yours. Note that the AI model weights are downloaded separately and carry their own licences; see [MODEL-LICENSES.md](https://github.com/Expansive-Labs-LLC/tessera/blob/main/MODEL-LICENSES.md) in the repository for the per-model terms before using output in a commercial product.

## Why pay if the code is free on GitHub?

Because building it yourself means cloning the repo, assembling the add-on archive, managing the ML dependency stack, and tracking releases by hand. The paid package is built, tested on Windows/macOS/Linux, versioned, and supported — and buying it funds the next version. That is the whole bargain, stated plainly. If it isn't worth it to you, build from source with our blessing.

## How is this different from Tripo, Meshy, or Hunyuan3D?

Those are generators — they produce a mesh and hand it back. Tessera is a pipeline that ends at a printable file: it validates manifold geometry, watertightness, wall thickness, overhangs, and build-volume fit against your actual printer, repairs what it can, scales to real millimetres, and leaves the result as editable Blender geometry. It also runs entirely on your own hardware with no subscription and no per-generation cost.

## What if it doesn't work on my machine?

Email hello@expansivelabs.com with your GPU model, VRAM, OS, and Blender version and we will help. If your hardware meets the stated requirements and we cannot get it working, you get a full refund — no argument. If your hardware does **not** meet the requirements, please check them before purchasing rather than after.

## Do I need an internet connection?

Only for the first run, to download model weights. After that Tessera works fully offline.

## Is there a trial?

There is no time-limited trial, but the source is public and the free build path is documented — that is the trial. The [documentation site](https://expansivelabs.io/tessera/) also shows the full workflow and real output before you spend anything.
