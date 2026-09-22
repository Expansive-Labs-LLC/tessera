# Tessera — Go-To-Market Strategy

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Status** | 🟡 Draft — awaiting CSO decisions (§10) |
| **Author** | Orchestrator (AI), for Derek (CSO) |
| **Created** | 2026-09-21 |
| **Implements** | SPEC-TS-0015 / TASK-TS-0015 (extends it — see §11 deviations) |
| **Product version at time of writing** | `0.1.0` (`bl_info`, `blender_manifest.toml`) |

---

## 1 · TL;DR — The Recommendation

**Sell on Superhive (formerly Blender Market) as the discovery channel and Gumroad as the owned channel. Do not plan on extensions.blender.org as a launch channel — Tessera is architecturally ineligible for it today. Do not charge money until the three blockers in §2 are cleared.**

| Channel | Role | Launch phase | Take rate |
|---|---|---|---|
| **Gumroad** | Owned channel — early access, email list, coupons, lifetime-update licences | Phase 1 (first) | ~13.2% + $0.80/sale |
| **Superhive** (ex-Blender Market) | Discovery — where Blender buyers already shop | Phase 2 (at v1.0) | 30% base, down to 10% on a paid creator plan |
| **GitHub Releases** | Free channel, GPL obligation, credibility | Already the source of truth | 0% |
| **extensions.blender.org** | Free reach at Blender-UI scale | Phase 3 — **blocked**, needs an ADR | 0% (free-only platform) |

Recommended price: **$29 early access → $49 at v1.0** (analysis in [pricing/pricing-strategy.md](pricing/pricing-strategy.md)). Not the $19/$14 the spec assumed — that pins Tessera to the $5–$13 "AI toy add-on" tier instead of the $45–$350 professional-tool tier it actually competes in on capability.

---

## 2 · Three Findings That Change the Spec's Plan

SPEC-TS-0015 assumes a four-channel launch with the same `.zip` going everywhere at $19. Three things make that wrong as written.

### 2.1 Tessera cannot be listed on extensions.blender.org as architected 🔴

Blender's add-on guidelines state add-ons **"must not install Python modules, PIP packages, Python-wheels etc."** — dependencies must be bundled as wheels inside the extension `.zip`. `requirements.txt` in this repo says the opposite outright:

> "The heavy ML stack (torch, diffusers, sam2, trellis, ...) is intentionally NOT listed: those are downloaded into Blender's environment at add-on runtime"

Bundling instead is not an escape: the extensions site rejects uploads over ~200 MB with HTTP 413, and a CUDA-enabled `torch` wheel alone is an order of magnitude past that.

**Consequence:** the free official channel is unavailable until the dependency architecture changes. The guideline does leave one compliant path — *"If some additional software required that cannot be bundled, this can be run by the user"* — i.e. split Tessera into a thin Blender-side add-on plus a **separately installed local Tessera Engine** the add-on talks to over localhost. That is an architectural decision, not a marketing one: it needs an ADR, and it would also unlock AMD GPUs and a CPU fallback as a side effect.

**Action:** raise `ADR-TS-00XX — Dependency delivery & Extensions Platform eligibility`. Until it lands, GitHub Releases is the free channel and the Extensions Platform is a Phase 3 goal, not a launch checkbox.

### 2.2 Two bundled model weights forbid or restrict commercial use ✅ FIXED 2026-09-21

`tessera/models/manifest.json` pulls five models. Two are a problem the moment money changes hands:

| Model in manifest | Licence | Commercial sale OK? |
|---|---|---|
| `depth-anything/Depth-Anything-V2-Large` | **CC-BY-NC-4.0** | ❌ Non-commercial only |
| `sudo-ai/zero123plus-v1.2` | **OpenRAIL** | ⚠️ Commercial allowed, but behavioural use restrictions must propagate downstream |
| `facebook/sam2-hiera-large` | Apache-2.0 | ✅ |
| `facebook/dinov2-large` | Apache-2.0 | ✅ |
| `TencentARC/InstantMesh` | Apache-2.0 | ✅ (attribution required) |

Depth Anything V2 **Small** is Apache-2.0; only Base/Large/Giant are CC-BY-NC. Tessera never ships weights in the `.zip` (they download at first run), which reduces but does not remove exposure — you would be selling a product whose advertised pipeline defaults to a non-commercial model, to buyers doing commercial print work.

**Resolved 2026-09-21.** The default depth model is now `depth-anything-v2-small` (Apache-2.0, 99 MB); Large stays available for non-commercial work but is licence-gated. `manifest.json` now declares `license` / `license_url` / `commercial_use` per model, every download path calls a licence gate that **fails closed** on anything not unambiguously commercial-friendly, and the opt-in (`allow_restricted_license_models`, default off) lives in add-on preferences. Revisions are pinned to commit SHAs so upstream cannot change weights or terms under a shipped release. Full breakdown: [`MODEL-LICENSES.md`](../MODEL-LICENSES.md).

**Also closed 2026-09-21:** every model file now carries a verified SHA-256 digest (28 files, 7 models) and the placeholder bypass that silently skipped verification is gone, so integrity checks fail closed. TRELLIS — the primary reconstruction model, previously absent from the manifest and therefore ungoverned — is now recorded as MIT, pinned and checksummed.

**Closed 2026-09-21:** `zero123plus-v1.2` (undeclared licence) and `instantmesh` were **removed from the manifest** — no adapter referenced either, and together they cost 3.3 GB on "Download All". The OpenRAIL propagation question and the Zero123++ → InstantMesh legal read go with them; both must be answered before either model is ever wired in, not after. The manifest is now five models: 6.86 GB total, **5.52 GB for the default pipeline**, which is exactly the working set.

**Nothing licence-related now blocks a paid listing.**

### 2.3 The product is `0.1.0` with an unverified release path 🟡

`TASK-INDEX.md` shows TASK-TS-0001 … 0015 all as "☐ Not Started" (stale — the code exists), the README's CI badge is still inactive pending TASK-TS-0013/0014, there are no captured screenshots anywhere in the repo, and the working tree is on `fix/ci-lint-and-test-config` with uncommitted changes. Nothing here has yet produced a tested `.zip` that a buyer could install.

**Consequence:** the correct launch motion is **paid early access on your own channel first** — not a Superhive listing. Superhive listings accumulate public reviews and a refund history from day one, and a Blender add-on that fails on a buyer's RTX 3060 earns a one-star review that outlives the bug. Gumroad early access gets you revenue and real GPU-diversity bug reports with no permanent reputational record.

### 2.4 The product is NVIDIA-only, and the listings said otherwise 🔴 *(found 2026-09-21)*

The PRD, the README, the docs site and the first draft of every listing here promised **Apple Silicon (MPS)** support, and the docs additionally promised **AMD ROCm**. The code does neither: `gpu_detection.py` *detects* CUDA, ROCm and Metal, but every inference adapter hardcodes CUDA —

- `sam2_adapter.py` → `device="cuda"`
- `depth_anything_adapter.py` → `self._device = "cuda"`
- `dinov2_adapter.py` → `self._device = "cuda"`
- `trellis_adapter.py` → `map_location="cuda"`

On a Mac or an AMD card, model loading fails. There is no MPS code path anywhere in the add-on — only an error-catalog string that *advises* checking MPS.

**Why this is a GTM problem, not just a docs bug:** Blender's user base skews Mac-heavy, and "works on my M-series MacBook" is a purchase assumption most buyers will not check. Shipping a listing that says Apple Silicon and a product that fails on it is the fastest possible route to the refund rate and one-star reviews that §8 flags as the metric to watch.

**Fixed in the copy (2026-09-21):** every listing file, the README and the docs site now say NVIDIA CUDA only, with AMD and Apple Silicon marked "detected, not supported in v1".

**Decided 2026-09-21 (D8): ship NVIDIA-only, fix the PRD, raise the MPS task before the v1.0 listing.** Done:

- **PRD-001 v0.4.0** — NG8 (non-CUDA backends out of scope for v1), a Compute-backend row in §8, decision D7, and a risk row for the Mac/AMD segment.
- **[TASK-TS-0022](../specs/tessera/tasks/TASK-TS-0022-apple-silicon-mps-support.md)** — Apple Silicon (MPS) support, P1, gating the v1.0 listing. Covers a device abstraction to replace every hardcoded `"cuda"`, adapter migration, MPS OOM and operator-gap handling, and restoring the claim to the listings only after it passes on real hardware. ROCm is flagged as a CSO call inside it.
- **Runtime guard shipped** — the add-on no longer lets a Mac or AMD user reach model load before finding out. `gpu_detection.SUPPORTED_INFERENCE_BACKENDS` is the single source of truth; the main panel warns when a GPU is detected but unusable, and the vision pipeline refuses to start with the device named. SPEC-TS-0001 (EC-006, FR-010a) and SPEC-TS-0003 (FR-022) amended accordingly — both awaiting CSO approval.

The §2.1 thin-add-on/local-engine ADR remains the lever that would unlock AMD, Apple Silicon **and** the free Extensions Platform channel together — still open as D3.

---

## 3 · Positioning

**Category:** not "an AI add-on". Tessera is a **reference-photo-to-print-bed pipeline that happens to live inside Blender**.

**One-liner:** *Turn reference photos into print-ready 3D models, entirely inside Blender — no cloud, no API keys, no modelling skill.*

**The wedge — print-readiness, not generation.** Tripo, Meshy, Hunyuan3D and a dozen Gumroad add-ons already do image→mesh. What none of them guarantee is a *manifold, watertight, wall-thickness-validated, correctly-scaled-in-millimetres* mesh. Tessera's validator + mm scaling + orientation optimiser is the part nobody else ships, and it is exactly the part that separates "cool mesh" from "successful print". Lead with the print, never with the AI.

**Three defensible claims** (all verified against implemented code, not aspiration):

1. **It prints.** Manifold / watertight / wall-thickness / overhang validation with auto-repair, plus real printer profiles (Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, Elegoo Saturn 3) carrying real build volumes.
2. **It's local.** Every model runs on the user's own GPU. No account, no API key, no upload, no per-generation credits — the entire competitive set charges per generation or per month.
3. **It's yours.** GPL-2.0-or-later, source on GitHub, and the output is editable Blender geometry rather than an opaque download.

**Anti-positioning — say this out loud in the listing.** Requires an **NVIDIA CUDA GPU** with ≥8 GB VRAM; no AMD, no Apple Silicon, no integrated graphics, no CPU fallback in v1 (verified 2026-09-21: every inference adapter hardcodes CUDA). Refunds from unmet system requirements are the #1 margin killer for GPU-dependent add-ons. Put the requirement above the fold, in the first screenshot, and in the FAQ.

## 4 · Who Buys It

| Segment | Why they buy | Willingness to pay | Priority |
|---|---|---|---|
| **Functional-print makers** (r/functionalprint, r/3Dprinting) — want a replacement bracket/knob/adapter from a photo | Skill barrier is absolute; they will never learn CAD | Med — used to free STLs, but pays for tools that save a weekend | **P1** |
| **Miniature / tabletop printers** | Volume printing of custom figures; already pay for STL subscriptions | High | **P1** |
| **Product designers & prototypers** using Blender | Want editable geometry, not a black-box download; bill by the hour | High — $49 is a rounding error | **P2** |
| **Blender generalists curious about AI** | Impulse buy on a good demo video | Low ($10–20 tier) | P3 — do not price for them |
| **Educators / makerspaces** | Sketch-to-3D for students; local-only matters to school IT | Med, but slow procurement | P3 — nurture, don't target at v1 |

The P1 segments are **not on Blender Market**. They are on Reddit, Printables, MakerWorld and YouTube. That asymmetry is the core of §7.

---

## 5 · Channel Strategy

### 5.1 Gumroad — the owned channel (launch here)

- **Take rate:** 10% + $0.50 platform fee, plus processing (~2.9% + $0.30) on direct sales ⇒ **~$24.46 net on a $29 sale**. Gumroad Discover-attributed sales are a flat 30% instead — leave Discover **off**; its discovery is worthless for Blender add-ons and it triples the take rate.
- **Merchant of record since Jan 2025** — Gumroad collects and remits VAT/GST/sales tax worldwide. For a US LLC selling to EU/UK buyers that removes a genuine compliance problem; do not self-host checkout to save 13%.
- **Why first:** no approval queue, you control pricing and coupons, and you keep the buyer email list — the most valuable asset a launch produces. Superhive owns its customer relationships; Gumroad lets you own yours.
- **Strategic lever:** Gumroad is where you can offer **lifetime updates**, which Superhive structurally can no longer match (§5.2). Make that the reason to buy direct.

### 5.2 Superhive (formerly Blender Market) — the discovery channel (add at v1.0)

- **Take rate:** 70% commission to the creator on the free plan (30% to the platform), rising to as much as 90% on a paid creator subscription across four tiers. Verify current tier pricing at `superhivemarket.com/pricing` before subscribing — at $49 and low volume the free tier is correct; a subscription only pays for itself past roughly 20–30 sales/month.
- **Why it matters:** it is the only place a Blender user *shopping for an add-on* will find you. Organic discovery, category browsing, affiliate coupons, and an audience that has already proven it pays for Blender tooling ($45–$350 tools like MESHmachine and UVPackmaster live there).
- **⚠️ Policy change you must price in:** since **12 May 2026**, Superhive purchases include **12 months of support and updates**; after that, buyers pay **50% of list price** for newer versions. It applies to all vendors, retroactively, with no opt-out, and it drew significant creator and customer backlash. Two implications: (a) your Superhive revenue has a renewal tail you didn't design, and (b) "buy direct on Gumroad for lifetime updates" is now a truthful differentiator — use it in your own channels, but do **not** disparage Superhive inside the Superhive listing.
- **Timing:** seller applications are reviewed, not instant, and product submissions get a further review. Apply for the seller account **≥14 days before** the v1.0 date even though you won't list until then — approval is free and non-committal.

### 5.3 GitHub Releases — the free channel (already the source of truth)

GPL-2.0-or-later means a free build must exist and be redistributable; pretending otherwise invites exactly the "why should I pay, it's free on GitHub" refund request. Reframe it instead — the free path is *build from source*, the paid path is *tested, packaged, supported, and updated*. That is the same bargain every GPL add-on on Superhive makes, and it works.

### 5.4 extensions.blender.org — blocked, and worth unblocking

Free-only by design ("no commercialization will happen in the platform"), and explicitly tolerant of you selling the same or a similar extension on Gumroad/Superhive — so there is no conflict in listing there *later*. The blocker is purely technical (§2.1). When it clears, the payoff is large: the platform is wired into Blender's own UI under Preferences → Get Extensions, the highest-intent discovery surface that exists for Blender add-ons.

Hard rules for that day: no pricing, no purchase CTA, no links to Gumroad/Superhive in the listing, the manifest, or any add-on UI element; declare the `network` permission with a truthful reason; respect `bpy.app.online_access` before any weight download.

### 5.5 Channels deliberately not used

FlippedNormals (sculpt/asset buyers, thin add-on traffic), ArtStation Marketplace (weak for tooling), itch.io (wrong buyer), and a self-hosted store (you become the merchant of record — not worth it below roughly $50k/yr).

---

## 6 · Pricing Summary

Full analysis and competitor table: [pricing/pricing-strategy.md](pricing/pricing-strategy.md).

| Phase | Price | Where | What the buyer gets |
|---|---|---|---|
| Early Access (v0.x) | **$29** | Gumroad only | Lifetime updates ("founding licence"), direct email support, changelog access |
| v1.0 launch | **$49** | Gumroad + Superhive | Gumroad: lifetime updates. Superhive: 12 months, per platform policy |
| Launch promo | **$39** for the first 14 days at v1.0 | Both | Coupon `TESSERA-LAUNCH` |

Early-access buyers are grandfathered to the $49 tier at no cost — announce that explicitly at purchase time. It converts early buyers into the loudest advocates you will get.

**Why not the spec's $19/$14:** the $5–$13 band is where AI-novelty add-ons sit (Blender GPT $4.99, Image2Mesh $10, Shap-E $10.99); serious workflow tools sit at $45+ (Nukleos asks $12.99 for mesh cleanup *alone*, MESHmachine $44.99+, UVPackmaster $55+). Tessera ships an entire validated pipeline, not a novelty. Pricing at $19 both leaves ~60% of the revenue on the table and actively signals "toy" to the P1/P2 buyers who would pay more. Price is also the cheapest thing to lower later and the hardest to raise.

---

## 7 · Demand Generation — Launch Plan

Your P1 buyers do not browse add-on marketplaces. The marketplace listing is the *conversion* surface; demand comes from the 3D-printing community.

### The asset that does all the work

**One 60–90 second video:** phone photo of a real broken or missing object → Tessera panel → validation panel showing green checks → slicer → print timelapse → the printed part in hand, fitting. No narration needed. That single clip is the Reddit post, the YouTube short, the listing hero, the BlenderNation submission, and the Superhive product video. Shoot it before writing a word of copy. **Choose a functional part, not a figurine** — a part that fits proves manifold geometry and mm accuracy in a way no figurine can.

### Sequence

**T-14 days — Preparation**
- Apply for the Superhive seller account (review takes days; approval is free).
- Create the Gumroad account, verify identity and payout (note: since March 2026 unverified accounts need a $100 balance before the first payout — verify early).
- Capture the seven marketplace screenshots ([assets/screenshots/README.md](assets/screenshots/README.md)) and build the hero banner.
- Publish the docs site and confirm a GitHub Release `.zip` installs clean on a fresh Blender 4.2 on Windows **and** macOS.
- Seed 5–10 real prints from real photos. You need a gallery, and you need to know the actual first-attempt success rate before you claim one.

**T-0 — Early access (Gumroad)**
- Publish the Gumroad page at $29.
- Post the video to: r/3Dprinting, r/functionalprint, r/blender (read each subreddit's self-promo rules first — r/blender requires tool disclosure, r/3Dprinting is hostile to undisclosed ads), BlenderArtists → *Released Add-ons and Extensions*, the Blender Discord add-on showcase, Bluesky/X with `#b3d` (the tag Blender devs actually read), and a BlenderNation tip submission (they cover new add-ons and drive real traffic).
- Cross-post the printed result to Printables and MakerWorld with the model files and "made with Tessera" in the description. Those communities reward shared STLs and tolerate tool mentions attached to them.

**T+30 to T+60 — Iterate in public**
- Ship weekly; post each changelog to the same channels. Visible velocity is the strongest quality signal an early-access product has.
- Collect and publish GPU compatibility data from real buyers — that table becomes the most-read section of the listing and cuts refunds.
- Ask your first 20 buyers for a testimonial and a print photo. Both go into the v1.0 listing.

**v1.0 — Superhive listing**
- Submit with testimonials, gallery, and a verified compatibility matrix already in hand. A Superhive launch with social proof converts several times better than a cold one, and it starts your review history at five stars instead of gambling it.
- Run the $39 launch coupon for 14 days on both channels simultaneously.

**Post-v1.0 — Free reach**
- Land the dependency ADR, then list on extensions.blender.org for the top-of-funnel free tier.

### Content cadence (low-effort, high-yield)

One build-in-public post per week: a print that worked, a print that failed and why, a feature clip. Blender and 3D-printing audiences reward failure posts unusually well — "here's the mesh that came out non-manifold and how the validator caught it" is better marketing than any feature list.

---

## 8 · Metrics

| Metric | Early access target (30d) | v1.0 target (90d) | Why it matters |
|---|---|---|---|
| Units sold | 25 | 250 | Validates willingness to pay at all |
| Refund rate | < 10% | **< 5%** | The GPU-requirement honesty test. Above 10% means the listing overpromises |
| Gumroad page conversion | 2% | 3% | Below 1.5% means the hero video isn't proving the print |
| First-attempt print success (self-measured) | ≥ 70% | ≥ 90% | The PRD's own Phase 4 exit criterion — and the product claim |
| Support tickets per 10 sales | < 3 | < 1 | Determines whether $49 is sustainable solo |
| Email list size | 100 | 750 | The only channel you own |
| Superhive review average | — | ≥ 4.5 | Compounds or destroys organic discovery |

Refund rate is the metric to watch weekly. For a GPU-gated GPL add-on it is the one honest signal of whether the listing matches the product.

---

## 9 · Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Non-commercial model weight ships in a paid product | ~~High~~ **Low** (mitigated 2026-09-21) | **Severe** — legal + reputational | ✅ Default swapped to Depth-Anything-V2-Small; fail-closed licence gate on every download path; `MODEL-LICENSES.md` published. Residual: `zero123plus-v1.2` terms undeclared — §2.2 |
| Refund wave from users on AMD / Apple Silicon / 8 GB / integrated GPUs | **High** | High | Listings now say NVIDIA-only (corrected 2026-09-21). Add an in-app pre-flight GPU check with a clear failure message, and restate the requirement at checkout. **Mac buyers are the biggest exposure — Blender's user base is Mac-heavy and the PRD promised Apple Silicon** |
| "It's GPL, I'll just get it free" | Medium | Medium | Lead with packaging + support + updates; never claim exclusivity; the free path is *build from source* |
| Superhive's 12-month support policy sours buyers on paid add-ons generally | Medium | Medium | Offer lifetime updates on Gumroad and make it a stated reason to buy direct |
| Extensions Platform rejection if submitted as-is | **Certain** if submitted today | Medium | Do not submit until the dependency ADR lands; a rejection is public and slows a later attempt |
| Model weight URLs or licences change under you | ~~Medium~~ **Low** | Medium | ✅ All revisions pinned to commit SHAs (2026-09-21). Remaining: fill the `"TODO"` SHA-256 digests before selling (TASK-TS-0018) |
| First-attempt print success below the claim | Medium | High | Measure across 20+ real objects before publishing any percentage; then publish the real number |

---

## 10 · Open Decisions — CSO (Derek)

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| D1 | Confirm price points | $29 early access → $49 at v1.0, $39 launch coupon | All listing copy (`$[PRICE]` tokens) |
| D2 | Approve Gumroad-first, Superhive-at-v1.0 sequencing | Approve | Launch runbooks |
| D3 | Authorise the dependency-architecture ADR (thin add-on + local engine) | Raise it now; it gates the free channel and AMD support | extensions.blender.org listing |
| D4 | ~~Approve swapping the default depth model to Depth-Anything-V2-Small~~ **Done 2026-09-21** — review the change | Review and merge; decide separately whether to pin `zero123plus` to v1.1 or seek clarification | Legal exposure on every paid sale |
| D5 | Lifetime updates on Gumroad — commit or not? | Commit. It is the one thing Superhive cannot match | Gumroad copy + FAQ |
| D6 | Seller entity and support address | Expansive Labs LLC / `hello@expansivelabs.com` | Both seller applications |
| D7 | Superhive creator subscription tier | Free tier at launch; revisit past ~25 sales/month | Superhive setup |
| D8 | ~~NVIDIA-only v1, or build an MPS path first?~~ **Decided 2026-09-21** — ship NVIDIA-only; PRD fixed, TASK-TS-0022 raised, runtime guard shipped | Keep TASK-TS-0022 ahead of the v1.0 Superhive listing | ✅ Closed (§2.4) |

---

## 11 · Deviations From SPEC-TS-0015

This document and the files beside it implement TASK-TS-0015 with five deliberate deviations. The spec should be amended to match before CSO sign-off.

| # | Spec says | This delivers | Why |
|---|---|---|---|
| 1 | Four channels at launch, incl. Extensions Platform | Three, with the Extensions Platform deferred behind an ADR | §2.1 — technically ineligible today |
| 2 | `blendermarket.md`, "BlenderMarket" throughout | `superhive.md`, "Superhive (formerly Blender Market)" | Platform rebranded; URLs and support docs are now `superhivemarket.com` |
| 3 | $19 standard / $14 introductory | $29 early access / $49 v1.0 / $39 promo | §6 — competitive band analysis |
| 4 | Gumroad nets $16.52 on a $19 sale (10% + 2.9% + $0.30) | Corrected fee model incl. the $0.50 per-sale platform fee and the 30% Discover rate | Gumroad's fee schedule changed; merchant of record since Jan 2025 |
| 5 | Adapters listed as "TripoSR, InstantMesh, CRM" | Trellis, multi-view (NeuS2 backend), sketch pipeline, stub fallback | CON-006 — claims must match `tessera/reconstruction/adapters/` |

Added beyond spec scope: this strategy document, [runbooks/launch-week.md](runbooks/launch-week.md), and the GPU-compatibility and model-licence risk items above.

| 6 | System requirements list "NVIDIA CUDA **or** Apple Silicon (MPS)" (inherited from the PRD and README) | NVIDIA CUDA only, with AMD and Apple Silicon marked unsupported in v1 | §2.4 — CON-006: no adapter implements a non-CUDA device path |

---

## 12 · Sources

- [Blender Add-on Guidelines](https://developer.blender.org/docs/handbook/extensions/addon_guidelines/) — no runtime pip/wheel installation; network permission; `bpy.app.online_access`
- [Extensions Platform: 750MB upload returns 413](https://projects.blender.org/infrastructure/extensions-website/issues/328) — effective ~200 MB cap
- [About — Blender Extensions](https://extensions.blender.org/about/) and [Terms of Service](https://extensions.blender.org/terms-of-service/) — free/GPL-only, no commercialization, third-party paid channels explicitly tolerated
- [Python Wheels — Blender Manual](https://docs.blender.org/manual/en/latest/advanced/extensions/python_wheels.html) — wheels must be bundled unmodified
- [How Your Commission Earnings Are Calculated — Superhive](https://support.superhivemarket.com/article/32-how-commission-earnings-are-calculated) and [Introducing Creator Subscriptions](https://superhivemarket.com/posts/introducing-creator-subscriptions) — 70% base, up to 90%
- [Incoming Policy Changes on Superhive — BlenderNation, 2026-04-01](https://www.blendernation.com/2026/04/01/incoming-policy-changes-on-superhive/) — 12-month support window from 2026-05-12
- [Gumroad Fees 2026](https://roo.beehiiv.com/p/gumroad-fees-2026) and [Gumroad Pricing 2026 — Swell](https://www.swell.is/content/gumroad-pricing) — 10% + $0.50, 30% Discover, merchant of record
- [depth-anything/Depth-Anything-V2-Large-hf](https://huggingface.co/depth-anything/Depth-Anything-V2-Large-hf) and the [licence discussion](https://github.com/DepthAnything/Depth-Anything-V2/issues/162) — CC-BY-NC-4.0; Small is Apache-2.0
- [InstantMesh LICENSE](https://github.com/TencentARC/InstantMesh/blob/main/LICENSE) — Apache-2.0; [zero123plus-v1.2](https://huggingface.co/sudo-ai/zero123plus-v1.2) — OpenRAIL
- Competitor prices: [27 Best Blender Addons 2026 — StraySpark](https://www.strayspark.studio/blog/best-blender-addons-2026), [Nukleos](https://egretstudios.gumroad.com/l/nukleos), [Shap-E](https://devbud.gumroad.com/l/Shap-e), [Blender GPT](https://kruithne.gumroad.com/l/blender-gpt)

> Marketplace fees, policies and model licences change. Re-verify every number in §5 and §6 on the day you publish.
