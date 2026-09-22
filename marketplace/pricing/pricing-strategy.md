# Pricing Strategy

| Field | Value |
|---|---|
| **Status** | 🟡 Recommendation — pending CSO confirmation (GTM-STRATEGY D1) |
| **Created** | 2026-09-21 |
| **Applies to** | Gumroad and Superhive only. GitHub Releases and extensions.blender.org are free. |

---

## 1 · Recommendation

| Phase | Price | Channels | Update terms |
|---|---|---|---|
| **Early Access** (v0.x) | **$29** | Gumroad only | Lifetime updates — "founding licence" |
| **v1.0 standard** | **$49** | Gumroad + Superhive | Gumroad: lifetime. Superhive: 12 months, then 50% for newer versions (platform policy) |
| **v1.0 launch promo** | **$39** for 14 days | Both | Same as standard |

Early-access buyers are grandfathered to the v1.0 tier at no additional cost. State that at the point of sale — it is the cheapest goodwill you will ever buy, and it converts the first 25 buyers into advocates.

**This supersedes SPEC-TS-0015 FR-036 ($19 standard / $14 introductory).** Rationale in §3.

---

## 2 · Competitive survey

Prices observed 2026-09-21. Marketplace prices move — re-check before publishing.

| Product | Platform | Price | What it does | Band |
|---|---|---|---|---|
| Blender GPT | Gumroad | $4.99 | LLM prompt console inside Blender | Novelty |
| Image2Mesh | Gumroad | $10 | AI mesh from images | Novelty |
| Shap-E (Text to 3D) | Gumroad | $10.99 | Text→3D generator | Novelty |
| Nukleos | Gumroad | $12.99+ | Mesh cleanup/optimisation for 3D printing | Utility |
| 3D Print Toolbox 4 | Superhive | listed (price varies) | Manifold checks and repair for Blender 4+ | Utility |
| Blender AI Library Pro | Superhive | listed (price varies) | AI models, materials, HDRIs from text/images | Suite |
| MESHmachine | Superhive | $44.99 – $344.99 | Hard-surface mesh toolkit, tiered | Professional |
| UVPackmaster | Superhive | $55 – $349 | UV packing engine, tiered | Professional |

Two clear bands, and almost nothing between them:

- **$5–$13 — AI novelty.** Single-purpose wrappers. Bought on impulse, abandoned in a week, reviewed harshly.
- **$45–$350 — professional workflow tools.** Deep, maintained, supported. Bought by people who bill for their time.

**Tessera is functionally in the second band** — an eight-stage pipeline with validation, printer profiles, refinement and export — and there is no product in the survey that does photo→validated printable mesh at all. Pricing it at $19 does not make it a bargain; it makes it read as the first band, which is the wrong audience and invites the review behaviour of that band.

## 3 · Why not $19

1. **Signal.** In this market, price is the primary quality signal before purchase. $19 places Tessera next to $10 novelty wrappers rather than next to $45 workflow tools.
2. **Wrong buyer.** $19 optimises for the P3 "curious Blender generalist" segment — the lowest-value, highest-support, most refund-prone buyer. $49 optimises for the P1/P2 makers and designers who have a real problem.
3. **Revenue.** At the 90-day target of 250 units (60% Gumroad / 40% Superhive), $49 nets roughly **$9,700** versus roughly **$3,700** at $19 — about $6,000 of difference on identical effort and identical support load.
4. **Direction of travel.** Lowering a price is a launch tactic. Raising one alienates every buyer who paid less. Start at $49 with a $39 promo, not at $19 hoping to raise it.
5. **Support economics.** A GPU-gated AI add-on generates real support tickets. At $19 and even 2 tickets per sale, the hourly rate is negative.

The counter-argument — "the product is 0.1.0, $49 is a lot for unproven software" — is real, and the answer is the $29 **early access** tier, not a permanently low price. Early access prices the risk honestly and keeps the v1.0 anchor intact.

## 4 · Net revenue per sale

### Gumroad (direct sale, Discover off)

Fees: 10% platform + $0.50 per sale, plus payment processing (~2.9% + $0.30). Gumroad has been merchant of record since Jan 2025 and remits VAT/GST/sales tax.

| List price | Platform fee | Flat fee | Processing | **Net to you** | Effective rate |
|---|---|---|---|---|---|
| $19 | $1.90 | $0.50 | $0.85 | **$15.75** | 17.1% |
| $29 | $2.90 | $0.50 | $1.14 | **$24.46** | 15.7% |
| $39 | $3.90 | $0.50 | $1.43 | **$33.17** | 15.0% |
| $49 | $4.90 | $0.50 | $1.72 | **$41.88** | 14.5% |

> Sales attributed to **Gumroad Discover** are charged a flat **30%** instead (processing included) — $49 would net $34.30. Keep Discover **off**; it produces negligible Blender add-on traffic and doubles the take rate.

### Superhive (free creator plan, 70% commission)

| List price | **Net to you (70%)** | Platform keeps |
|---|---|---|
| $19 | $13.30 | $5.70 |
| $29 | $20.30 | $8.70 |
| $39 | $27.30 | $11.70 |
| $49 | **$34.30** | $14.70 |

Paid creator subscriptions raise commission to as much as 90% and reduce merchant fees, across four tiers. Verify current tier pricing at `superhivemarket.com/pricing` before subscribing, then apply:

```
subscription is worth it when:
  (new commission % − 70%) × monthly gross revenue  >  monthly subscription cost
```

At $49 and 70%→80%, each sale gains $4.90 — so a hypothetical $20/month plan breaks even at ~4 sales/month, and a $100/month plan at ~21. **Start on the free tier** and re-evaluate after the first full month of Superhive sales (CSO D7).

### Channel comparison at $49

Gumroad nets **$41.88** against Superhive's **$34.30** — but Superhive supplies discovery Gumroad cannot. The mix is the point: Gumroad for traffic you bring, Superhive for traffic it brings you.

## 5 · GPL and what the price actually buys

Tessera is GPL-2.0-or-later. Buyers may redistribute it. That is not a leak to be plugged — it is the same footing every paid add-on on Superhive stands on, and DRM or licence keys would be both unenforceable and a breach of the licence.

State plainly, on every paid listing, that the price buys:

- a pre-built, tested, versioned package (no build toolchain, no dependency surgery)
- update notifications and access to new versions
- direct support from the developers
- continued development

and **never** that it buys exclusivity, private access, or a licence the GitHub source doesn't already grant.

This framing also defuses the predictable "it's free on GitHub, refund me" ticket: yes, it is, that is by design, here is the refund, and here is the build-from-source guide. Budget for a handful of those; they are cheaper than a bad-faith reputation.

## 6 · Discounting rules

- **Launch promo:** `TESSERA-LAUNCH`, $39, 14 days, both channels, announced with an end date. Never extend it — an extended "limited" discount teaches buyers to wait.
- **Bundle events:** Superhive runs periodic creator bundles. Worth joining once for reach, not repeatedly — bundles anchor the perceived price low.
- **Educational / makerspace:** 40% on request via email, case by case. Do not build a self-serve tier for it at this volume.
- **Affiliate coupons (Superhive):** enable at default terms once reviews exist; they cost commission but bring buyers you would not reach.
- **No permanent sales.** A product that is always 30% off is a $34 product with a fake $49 sticker, and Blender buyers recognise it instantly.

## 7 · Future pricing

- Re-evaluate at v1.0 + 90 days against real refund rate and support load. If refunds sit under 5% and tickets under 1 per 10 sales, **$59–$69 is defensible** for v2 — the professional band supports it.
- **No free tier on paid channels.** GitHub Releases, and eventually extensions.blender.org, are the free tier.
- **No subscription.** Blender add-on buyers are hostile to them, and Superhive's own 12-month support policy is already generating that backlash — do not volunteer for it.
- **Tiered pricing (personal / studio) is worth considering at v2**, following MESHmachine and UVPackmaster, once there is a feature line that genuinely separates the tiers. Do not invent one for v1.
- A paid **model-weights convenience bundle** (pre-downloaded, checksum-verified weights) is a possible future SKU — but only for weights whose licences permit redistribution. Depth Anything V2 Large (CC-BY-NC) and anything under OpenRAIL are excluded; see GTM-STRATEGY §2.2.

## 8 · Sources

- [Gumroad Fees 2026](https://roo.beehiiv.com/p/gumroad-fees-2026), [Gumroad Pricing 2026 — Swell](https://www.swell.is/content/gumroad-pricing)
- [How Your Commission Earnings Are Calculated — Superhive](https://support.superhivemarket.com/article/32-how-commission-earnings-are-calculated), [Introducing Creator Subscriptions](https://superhivemarket.com/posts/introducing-creator-subscriptions)
- [Incoming Policy Changes on Superhive — BlenderNation](https://www.blendernation.com/2026/04/01/incoming-policy-changes-on-superhive/)
- Competitor prices: [StraySpark — 27 Best Blender Addons 2026](https://www.strayspark.studio/blog/best-blender-addons-2026), [Nukleos](https://egretstudios.gumroad.com/l/nukleos), [Shap-E](https://devbud.gumroad.com/l/Shap-e), [Blender GPT](https://kruithne.gumroad.com/l/blender-gpt), [3D Print Toolbox 4](https://superhivemarket.com/products/3d-print--checker)
