# Runbook — Release Checklist

> Run this for every version CI publishes. **Target: ≤ 20 minutes of hands-on work** across all channels, excluding moderation waits (NFR-006).

---

## Pre-launch checklist (one-time, before the first listing)

### Blockers — none of the rest matters until these clear

- [x] **Model licences audited** — default depth model swapped to Depth-Anything-V2-Small (Apache-2.0); Large licence-gated behind an explicit opt-in; fail-closed gate on every download path *(done 2026-09-21)*
- [x] **`MODEL-LICENSES.md`** published in the repo *(done 2026-09-21)* — [ ] still to be linked from every listing
- [x] **OpenRAIL terms for `zero123plus`** — resolved 2026-09-21 by removing `zero123plus-v1.2` and `instantmesh` from the manifest; no adapter used either. Re-open only if one is wired in
- [x] **Platform claims match the code** — NVIDIA CUDA only in v1, stated in every listing, the README, the docs site and a runtime banner (2026-09-21). [TASK-TS-0022](../../specs/tessera/tasks/TASK-TS-0022-apple-silicon-mps-support.md) must land before the v1.0 Superhive listing if Apple Silicon is to be claimed
- [x] **`manifest.json` revisions pinned** to commit SHAs instead of `"main"` *(done 2026-09-21)*
- [x] **Every `"TODO"` SHA-256 filled in** *(done 2026-09-21)* — all 28 files across 7 models verified, and the placeholder bypass removed so verification fails closed (TASK-TS-0018)
- [ ] **Price confirmed** by CSO (D1) and every `$[PRICE]` token substituted

### Accounts

- [ ] Gumroad account created, identity and payout verified
- [ ] Superhive seller application submitted (≥ 14 days before the v1.0 date)
- [ ] Superhive seller application approved
- [ ] Blender ID created — only needed when the Extensions Platform blocker clears

### Assets

- [ ] 7 screenshots captured, annotated, compressed, legible at 400 px
- [ ] Hero banner produced and checked at 600 px
- [ ] Demo video recorded and hosted
- [ ] Product description, FAQ and platform adaptations finalised and consistent (NFR-008)

### Product

- [ ] Docs site live at `https://expansivelabs.io/tessera/`
- [ ] GitHub Release exists with a `tessera-v<VERSION>.zip` asset
- [ ] `.zip` installed from scratch on a clean Blender 4.2 on Windows **and** macOS
- [ ] One full photo → validated mesh → printed object cycle completed by someone who did not write the code
- [ ] `README.md` marketplace placeholder replaced with the live URL
- [ ] `.github/FUNDING.yml` `custom` key set to the Gumroad URL — and **not** the extensions.blender.org URL (FR-041)

---

## Per-release checklist

### 1 · Verify the build (~5 min)

- [ ] CI created the GitHub Release with the correct tag and `.zip` asset
- [ ] Version in `blender_manifest.toml` and `bl_info` matches the tag
- [ ] Download the `.zip` **from the Release** and install it in Blender — never ship a local rebuild
- [ ] Smoke test: load an image, generate, validate, export

### 2 · Write the notes once (~5 min)

- [ ] Fill in `copy/changelog-template.md` for this version
- [ ] Every "What's New" claim is implemented and tested, not planned
- [ ] Breaking changes stated at the top, never buried
- [ ] Note whether new model weights are required and how large they are

### 3 · Gumroad (~5 min)

- [ ] Replace the `.zip` in the product's Content tab
- [ ] Update the version number and any changed claims in the description
- [ ] **Posts → New post** — send the release notes to all customers (this is the update notification the listing promises)
- [ ] Confirm the live page shows the new version

### 4 · Superhive (~5 min)

- [ ] Upload the new `.zip` (no re-review required for version bumps)
- [ ] Paste the same release notes into "What's New"
- [ ] Update Blender version compatibility if the supported range changed

### 5 · Extensions Platform (only once unblocked — 5 min + 1–5 business days)

- [ ] Upload New Version with the CI `.zip`
- [ ] Version notes with all commercial language stripped
- [ ] Submitted for re-review

### 6 · Announce (~5 min)

- [ ] GitHub Release body carries the same notes
- [ ] Posted to GitHub Discussions
- [ ] Posted to the channels that actually produced buyers last time (see `launch-week.md`)
- [ ] For a significant release: BlenderArtists thread bump and a BlenderNation tip

### 7 · Consistency check

- [ ] The same version number is live on every channel
- [ ] The same release notes text is on every channel
- [ ] Feature claims still match `copy/product-description.md` — if not, update the source of truth first and propagate (NFR-008)

---

## Time budget

| Step | Hands-on | Wait |
|---|---|---|
| Verify build | 5 min | — |
| Release notes | 5 min | — |
| Gumroad | 5 min | — |
| Superhive | 5 min | — |
| Extensions Platform | 5 min | 1–5 business days moderation |
| Announce | 5 min | — |
| **Total** | **~20–30 min** | moderation only |

If this regularly exceeds 30 minutes, the bottleneck is almost always hand-written release notes — write them once into the template and paste everywhere.
