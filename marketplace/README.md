# Tessera — Marketplace & Go-To-Market

Listing copy, launch assets, pricing analysis, and operational runbooks for publishing Tessera. Implements TASK-TS-0015 / SPEC-TS-0015, with the deviations recorded in [GTM-STRATEGY.md §11](GTM-STRATEGY.md#11--deviations-from-spec-ts-0015).

## Start here

| If you want to… | Read |
|---|---|
| Understand the strategy and which marketplace to use | **[GTM-STRATEGY.md](GTM-STRATEGY.md)** |
| Set up the Gumroad page (the launch channel) | [runbooks/gumroad-upload.md](runbooks/gumroad-upload.md) |
| Plan the launch itself | [runbooks/launch-week.md](runbooks/launch-week.md) |
| Decide the price | [pricing/pricing-strategy.md](pricing/pricing-strategy.md) |
| Ship a new version | [runbooks/release-checklist.md](runbooks/release-checklist.md) |

## The short version

Sell on **Gumroad** first (owned channel, ~13% take rate, lifetime-update licences), add **Superhive** — formerly Blender Market — at v1.0 for discovery (30% take rate, where Blender buyers shop). **extensions.blender.org is blocked**: the platform forbids runtime pip installation and caps uploads near 200 MB, and Tessera downloads its ML stack at runtime. Recommended price: **$29 early access → $49 at v1.0**.

Three things must be cleared before any money changes hands — all in [GTM-STRATEGY.md §2](GTM-STRATEGY.md#2--three-findings-that-change-the-specs-plan):

1. ✅ ~~`Depth-Anything-V2-Large` is CC-BY-NC-4.0~~ — **fixed 2026-09-21**: default is now the Apache-2.0 Small checkpoint, with a fail-closed licence gate on every download path ([MODEL-LICENSES.md](../MODEL-LICENSES.md)). Residual: `zero123plus-v1.2` declares no licence
2. 🔴 extensions.blender.org eligibility needs a dependency-architecture ADR
3. 🟡 The product is `0.1.0` with no captured screenshots and no verified release install

## Contents

```
marketplace/
├── GTM-STRATEGY.md                  # Strategy, channels, launch plan, risks, open CSO decisions
├── copy/
│   ├── product-description.md       # ← source of truth for every listing claim
│   ├── feature-list.md              # 61 features by workflow stage
│   ├── faq.md                       # 12 buyer questions
│   ├── changelog-template.md        # Per-release notes, same text on every channel
│   └── platform-adaptations/
│       ├── gumroad.md               # Paste-ready Gumroad page + settings
│       ├── superhive.md             # Paste-ready Superhive listing + seller bio
│       └── extensions-platform.md   # Free listing copy — DO NOT SUBMIT YET
├── assets/
│   ├── hero-banner.png              # 2400×750 interim illustrated banner — see screenshots/README.md
│   └── screenshots/
│       ├── README.md                # Capture manifest, annotation style, demo-video script
│       └── 01..07-*.png             # 1×1 placeholders (CON-007)
├── pricing/
│   └── pricing-strategy.md          # Competitor survey, fee maths, discount rules
└── runbooks/
    ├── gumroad-upload.md            # Page setup + version updates
    ├── superhive-upload.md          # Seller application, submission, the 12-month support policy
    ├── extensions-platform-upload.md# Blocked — unblocking criteria + submission steps
    ├── launch-week.md               # T-14 → T+30, channel-by-channel, with post templates
    └── release-checklist.md         # Pre-launch one-time list + per-release checklist
```

## House rules

- **`copy/product-description.md` is canonical.** Change a claim there first, then propagate to all three platform adaptations in the same commit (NFR-008).
- **Never claim a feature that isn't implemented** (CON-006). Every claim in this directory traces to a module under `tessera/`.
- **Never claim exclusivity.** Tessera is GPL-2.0-or-later; paid listings sell packaging, testing, updates and support.
- **Never link a paid channel from the Extensions Platform listing, `blender_manifest.toml`, or any add-on UI string** (CON-002).
- **`$[PRICE]` tokens stay until the CSO confirms pricing** (CON-004).
- Marketplace fees and policies change. Re-verify every external number on the day you publish; sources are cited at the bottom of each file.
