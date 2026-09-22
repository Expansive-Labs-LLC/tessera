# Runbook — Gumroad Product Page Setup

> **This is the launch channel.** Set this up first; Superhive comes at v1.0.
>
> Gumroad's UI labels shift between redesigns. Where a label below doesn't match what you see, the step is described by function — find the equivalent control and carry on. Expect **45–60 minutes** for first-time setup, **~5 minutes** per version update afterwards.

---

## Part 0 · Before you start

- [ ] GTM blockers cleared — no non-commercial model weight in the default path (GTM-STRATEGY §2.2)
- [ ] A GitHub Release exists with `tessera-v<VERSION>.zip` attached, and you have **installed it from scratch on a clean Blender 4.2** and generated one model end to end
- [ ] Price confirmed (CSO D1) and substituted into `copy/platform-adaptations/gumroad.md`
- [ ] Hero banner + 7 screenshots captured, annotated, compressed
- [ ] Demo video uploaded somewhere embeddable (YouTube unlisted works)
- [ ] Docs site live at `https://expansivelabs.io/tessera/`
- [ ] `hello@expansivelabs.com` monitored by a human who can answer within one business day

## Part 1 · Account and payout (do this early — it has a waiting period)

1. Create the account at `gumroad.com` using a business address, not a personal one. Use `hello@expansivelabs.com` so support mail lands where the team reads it.
2. Open **Settings → Payments** and connect the payout account for Expansive Labs LLC. Complete identity verification now — since March 2026 unverified accounts must accumulate a $100 balance before their first payout, which will strand your launch revenue.
3. Fill in **Settings → Settings**: creator name "Expansive Labs", profile bio (reuse the seller bio in `copy/platform-adaptations/superhive.md`), and profile image.
4. Under **Settings → Payments**, confirm the tax/VAT section shows Gumroad acting as merchant of record. Gumroad collects and remits VAT/GST/sales tax worldwide — you do not register anywhere yourself.

## Part 2 · Create the product

5. **Products → New product → Digital product.** Name it `Tessera — AI Image-to-3D for Blender` and set the price to the confirmed amount.
6. On the product edit screen, set the **custom URL slug** to `tessera-blender` so the link reads `expansivelabs.gumroad.com/l/tessera-blender`. Lock this in before you share any link anywhere — changing it later breaks every post you have made.
7. Paste the **description** from `copy/platform-adaptations/gumroad.md` into the rich-text editor. Keep the system-requirements warning block near the top, above the fold — it is the single biggest lever on your refund rate.
8. Upload the **cover image** (`assets/hero-banner.png`) and then the gallery images in the order given in the copy file. Add the demo video as the second gallery item.
9. Set the **call-to-action button** to "I want this!" or "Buy now" — not "Name a fair price". Pay-what-you-want signals uncertainty for a tool at this price.

## Part 3 · Content and delivery

10. Open the **Content** tab and upload `tessera-v<VERSION>.zip` from the GitHub Release. Do not rebuild it locally — upload the exact artifact CI published, so the file buyers get matches the tag you support.
11. Set delivery to a direct download of that single file. Do not gate it behind an external link or a licence key; the product is GPL and keys are both unenforceable and a licence breach.
12. Add a short content note above the file: install instructions in three lines, a link to the docs site, and the support address. Most buyers read this and nothing else.
13. In **Settings → Receipt/Thank-you note**, add: "Your licence includes lifetime updates — you'll get an email whenever a new version ships. Trouble installing? Reply to this email or write to hello@expansivelabs.com."

## Part 4 · Settings that matter

14. **Turn Gumroad Discover OFF** for this product. Discover-attributed sales cost a flat 30% versus roughly 13% on direct sales, and it sends effectively no Blender add-on traffic.
15. Add product **tags**: `blender`, `3d-printing`, `ai`, `addon`, `3d-modeling`, `stl`.
16. Set the **refund policy** to 30 days, no questions asked, and state it in the description too. Note that Gumroad keeps its 10% + $0.50 on refunded sales — budget for that rather than being surprised by it.
17. Enable **ratings/reviews** display. A GPL tool with public source and visible reviews converts better than one hiding both.
18. Create the launch coupon under **Discounts / Offer codes**: code `TESSERA-LAUNCH`, the promo amount, with a hard expiry date set at creation time.

## Part 5 · Publish

19. Preview the page at mobile width. If the system-requirements block is below three scrolls, move it up.
20. Buy your own product with a 100% coupon to test the full path: checkout → receipt → download → install in Blender. Refund yourself afterwards.
21. **Publish**, then paste the live URL into `.github/FUNDING.yml` under the `custom` key and into `README.md`'s Installation section (replacing the "[Marketplace link coming soon]" placeholder).

---

## Version update procedure (~5 minutes)

1. Download `tessera-v<VERSION>.zip` from the new GitHub Release — again, never a local rebuild.
2. **Products → Tessera → Content**: remove the old `.zip` and upload the new one.
3. Update the version number and any changed feature claims in the description; if the feature list changed, update `copy/product-description.md` first and propagate from there (NFR-008).
4. Go to **Posts → New post**, paste the release notes from `copy/changelog-template.md`, and send it to all customers. This is the "update notification" the listing promises — skipping it breaks the value proposition you sold.
5. Save and confirm the live page shows the new version.

## If something goes wrong

| Symptom | Action |
|---|---|
| Payout held | Complete identity verification; the $100 first-payout threshold applies to unverified accounts |
| Buyer reports a corrupt `.zip` | Verify the SHA-256 against the GitHub Release asset; re-upload if they differ |
| Refund request citing "it's free on GitHub" | Refund immediately and without argument, then link the build-from-source guide. This is by design (pricing strategy §5) |
| Refund request from an AMD/integrated-GPU user | Refund, then check whether the requirement is visible above the fold. If two of these arrive in a week, the listing is at fault, not the buyer |
| Chargeback | Gumroad handles it as merchant of record; supply the download log if asked |
