# Model Weight Licences

Tessera's own source code is licensed **GPL-2.0-or-later**. The AI model weights it uses are **not** part of Tessera, are **not** covered by that licence, and are **not** redistributed by this project. They are downloaded from third-party repositories onto your machine on first use, and each carries its own terms.

This file records those terms. It is the reference for the licence gate in [`tessera/models/licensing.py`](tessera/models/licensing.py) and for the `license` / `commercial_use` fields in [`tessera/models/manifest.json`](tessera/models/manifest.json).

Verified 2026-09-21 against the upstream repositories. **Licences change — re-verify before any commercial release.**

Totals: 5 models, 25 files, **6.86 GB** if every model is fetched. The default pipeline — SAM 2, Depth Anything V2 Small, DINOv2, TRELLIS — is **5.52 GB**; the remaining 1.34 GB is the licence-gated Depth Anything V2 Large.

---

## Summary

| Model ID | Repository | Licence | Commercial use | Gated? |
|---|---|---|---|---|
| `sam2-hiera-large` | [facebook/sam2-hiera-large](https://huggingface.co/facebook/sam2-hiera-large) | Apache-2.0 | ✅ Allowed | No |
| `trellis-image-large` | [microsoft/TRELLIS-image-large](https://huggingface.co/microsoft/TRELLIS-image-large) | MIT | ✅ Allowed | No |
| `depth-anything-v2-small` | [depth-anything/Depth-Anything-V2-Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small) | Apache-2.0 | ✅ Allowed | No |
| `depth-anything-v2-large` | [depth-anything/Depth-Anything-V2-Large](https://huggingface.co/depth-anything/Depth-Anything-V2-Large) | **CC-BY-NC-4.0** | ❌ **Prohibited** | **Yes** |
| `dinov2-large` | [facebook/dinov2-large](https://huggingface.co/facebook/dinov2-large) | Apache-2.0 | ✅ Allowed | No |

"Gated" means Tessera refuses to download the weights unless the user enables **Allow Restricted-Licence Models** in Preferences → Add-ons → Tessera.

---

## Depth estimation — why Small is the default

Depth Anything V2 is published under **two different licences depending on checkpoint size**:

| Checkpoint | Parameters | Licence |
|---|---|---|
| **Small (ViT-S)** | 24.8 M | **Apache-2.0** |
| Base (ViT-B) | 97.5 M | CC-BY-NC-4.0 |
| **Large (ViT-L)** | 335 M | **CC-BY-NC-4.0** |
| Giant (ViT-G) | — | CC-BY-NC-4.0 |

Tessera defaults to **Small** (`depth_anything_v2_vits.pth`, 99.2 MB) because it is the only checkpoint whose terms permit commercial use. Large remains selectable for research and other non-commercial work, but is licence-gated and must be enabled deliberately.

If you enable Large: **you may not use its output commercially.** That includes selling prints generated through it, using it in client work, or shipping it inside a commercial product.

The accuracy trade-off is real but modest for Tessera's purposes — depth output is one prior among several feeding reconstruction, and is masked to the segmented subject before use.

## Removed from the manifest — Zero123++ and InstantMesh

Both were declared in the manifest but referenced by **no adapter**, and together they cost 3.3 GB on "Download All". They were removed on 2026-09-21. The findings are kept here because they should inform any decision to bring either back:

- **Zero123++** — the code ([SUDO-AI-3D/zero123plus](https://github.com/SUDO-AI-3D/zero123plus)) is Apache-2.0; the **v1.1 weights** declare **OpenRAIL**; the **v1.2 weights** that were in the manifest publish **no model card and no licence declaration at all**. OpenRAIL permits commercial use but attaches behavioural use restrictions that must be passed on to every downstream user and to anyone receiving derivatives. An undeclared licence is worse than a restrictive one — there are no stated terms to comply with. If it returns, pin v1.1 and propagate the restrictions, or get a clarification from the publisher.
- **InstantMesh** — the weights declare Apache-2.0, which is clean on its own. But InstantMesh is architecturally built on Zero123++ multi-view output, so a Zero123++ → InstantMesh pipeline may carry the upstream terms regardless. That needs a legal read *before* either is wired in, not after.

Nothing in the current pipeline depends on either, so neither question blocks a commercial launch today.

## Attribution obligations you actually have

- **Apache-2.0 models** (SAM 2, Depth Anything V2 Small, DINOv2) — retain copyright and licence notices, and state any modifications. Since Tessera downloads rather than redistributes these weights, the practical obligation is attribution: this file plus the links above satisfy it.
- **MIT** (TRELLIS) — retain the copyright and permission notice. No further obligation.
- **CC-BY-NC-4.0** (Depth Anything V2 Large) — attribution *and* non-commercial use only.

Zero123++ and InstantMesh were removed from the manifest on 2026-09-21, so their terms impose **no current obligation**. The OpenRAIL propagation requirement noted above would apply again only if Zero123++ were reinstated.

## How the gate works

1. Every entry in `manifest.json` declares `license`, `license_url` and `commercial_use` (`allowed` / `restricted` / `prohibited` / `unknown`).
2. A missing or unrecognised classification **fails closed** and is treated as `unknown`, i.e. gated. A weight nobody has checked is assumed unsafe.
3. `DownloadManager._download_model()` calls `licensing.check_download_allowed()` before any network access, so every path — single download, background download, download-all, and first-use auto-download — is covered.
4. `start_download_all_missing()` skips gated models entirely rather than failing the batch.
5. The download operator surfaces the block on the main thread with an actionable message, and the preferences model list shows each weight's licence and disables the download button for blocked entries.
6. The opt-in (`allow_restricted_license_models`, default **off**) is mirrored into a module-level flag because downloads run on worker threads, which must not touch `bpy` (SPEC-TS-0002 CON-003).

## Integrity

Every file in the manifest now carries a **verified SHA-256 digest** (2026-09-21). Digests came from Hugging Face's `paths-info` API — the LFS `oid` of a file *is* its SHA-256 — with small non-LFS files downloaded at the pinned revision and hashed locally. All revisions are pinned to commit SHAs, so a digest and the licence it was checked against refer to the same immutable snapshot.

Verification **fails closed**: a missing or placeholder digest is reported as a verification failure rather than skipped (`cache_manager.verify_integrity`), and `_download_model` raises `IntegrityError` on any failure. The previous behaviour — skipping files whose digest was `"TODO"` — silently disabled the control and has been removed (TASK-TS-0018).

## User-added models

The manifest is **user-extensible** (SPEC-TS-0002 v1.4): anyone can add a model from Hugging Face through Preferences → Add-ons → Tessera → Models → *Add from Hugging Face*. Those models are not curated by this file, so the guarantees have to come from code instead — and they do:

| Guarantee | How it is enforced for a model we never saw |
|---|---|
| **Licence recorded** | `GET /api/models/{repo}` returns the publisher's declared `license` tag. `licensing.classify_license()` maps it to allowed / restricted / prohibited / unknown using the same vocabulary as this file. |
| **Licence enforced** | The same fail-closed gate. `cc-by-nc-*` is prohibited; OpenRAIL, RAIL, Llama and Gemma community licences are restricted; `other` or no declaration at all is unknown. All three are refused unless the user opts in. The refusal names the licence, so the user learns the terms without downloading anything. |
| **Integrity** | `POST /api/models/{repo}/paths-info/{revision}` returns each file's LFS `oid`, which **is** its SHA-256. Small non-LFS files are fetched and hashed locally. A file with no obtainable digest is refused — Tessera does not add what it cannot verify. Every digest in this file was obtained the same way. |
| **Pinning** | The repository's commit SHA is resolved at add time and stored in the entry. A publisher cannot change the weights, or the terms, under a model the user already approved. |
| **Code-execution safety** | Only data extensions are accepted (SEC-004) and `weights_only=True` is never relaxed (SEC-003). The docs steer users to `.safetensors`, which cannot carry executable content at all. |
| **Isolation** | User entries live in `<cache_dir>/user_models.json`, outside the add-on, so they survive updates. They cannot shadow or remove a bundled model, and a corrupt file is skipped rather than taking model management down. |

**Where our responsibility ends.** Tessera does not host, mirror or redistribute weights; it reads what a publisher declares and refuses what does not look clearly commercial-friendly. A licence classification is a machine-readable check, not legal advice, and a user who enables restricted models is making that decision themselves. The Custom Models documentation says so in those words, and the add dialog repeats it before anything is added.

**What this does not cover.** A repository that declares a permissive tag while its model card says otherwise, or weights trained on data the publisher had no right to, will pass the check. That risk is inherent to third-party weights and is the reason the curated default set stays small, pinned and hand-verified.

## Weights used or planned but **not** in the manifest

These bypass the gate entirely because the registry never sees them.

| Weight | Where it appears | Terms | Status |
|---|---|---|---|
| **`tessera-intent-parser`** (GGUF) | `tessera/refinement/llm_backend/local_llm.py` calls `ensure_model("tessera-intent-parser")` | Unknown — no model chosen yet | ⚠️ Not in the manifest; `ensure_model` raises `ModelNotFoundError`. Pick a model and record its terms (TASK-TS-0021) |

**TRELLIS is now governed** (added 2026-09-21) — `trellis-image-large`, MIT, pinned, 17 files, 3.30 GB, all digests verified. One mismatch remains: `TrellisAdapter` still looks for a single placeholder file, `trellis_pipeline.safetensors`, which does not exist upstream. The real repository is `pipeline.json` plus `ckpts/*.{json,safetensors}`. The adapter's `_WEIGHT_FILES`, `_EXPECTED_CHECKSUMS` and its `torch.load` path must be reconciled with this entry in **TASK-TS-0017** — the manifest entry is correct; the adapter is not.

Note also that `zero123plus-v1.2` and `instantmesh` are declared in the manifest but not yet referenced by any adapter. Gating `zero123plus-v1.2` therefore blocks nothing today — but their terms must be settled before either is wired in, and together they add 3.3 GB to "Download All Required" for no current benefit.

## Outstanding

- [x] ~~**SHA-256 digests**~~ — done 2026-09-21: all 28 files across 7 models carry verified digests, and the placeholder bypass is removed (TASK-TS-0018).
- [ ] **Licence clarification for `zero123plus-v1.2`** — ask the publisher, or pin to v1.1.
- [ ] **Legal review of the Zero123++ → InstantMesh chain** before a commercial launch.
- [x] ~~**Add TRELLIS to the manifest**~~ — done 2026-09-21. Still open: reconcile `TrellisAdapter`'s placeholder filenames with the entry (TASK-TS-0017).
- [ ] **Add `tessera-intent-parser` to the manifest** once a model is chosen, so it is licence-recorded and checksum-verified like everything else (TASK-TS-0021).
- [x] ~~**Decide whether `zero123plus-v1.2` and `instantmesh` stay in the manifest**~~ — removed 2026-09-21. "Download All" is now 5.52 GB, exactly the working set.
- [ ] **If a user-selectable model browser ships** (see below), the gate must read licence and digest from the Hugging Face API at download time rather than from a static manifest.
- [ ] Revisions are now pinned to commit SHAs rather than `main`, so upstream cannot silently change weights or terms underneath a release. Re-verify the licence table whenever a revision is bumped.
