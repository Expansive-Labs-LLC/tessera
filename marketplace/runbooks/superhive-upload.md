# Runbook — Superhive (formerly Blender Market) Product Setup

> Superhive is the rebranded Blender Market — `superhivemarket.com`, support docs at `support.superhivemarket.com`. SPEC-TS-0015 still calls it "BlenderMarket".
>
> **Timeline: start 14+ days before you intend to list.** Seller approval and product review are both human-reviewed queues. Total hands-on time is about an hour, spread across those two waits.

---

## Part 0 · Decide whether you are ready

Do not list here until:

- [ ] v1.0 is tagged, and the `.zip` has been installed clean on Windows **and** macOS by someone other than you
- [ ] You have at least 10 real prints produced through the pipeline, and know your genuine first-attempt success rate
- [ ] You have 3+ testimonials or public reactions from early-access buyers
- [ ] A verified GPU compatibility table exists (what actually worked, on what hardware)
- [ ] The model-licence blocker is cleared (GTM-STRATEGY §2.2)

Superhive listings carry **public reviews and a permanent refund history**. A one-star review earned by a 0.x bug outlives the fix by years. Early access on Gumroad exists precisely so the bugs get found somewhere without a permanent record.

## Part 1 · Seller application (start at T-14 days)

1. Apply at `superhivemarket.com` → *Become a Creator* (linked from the footer and the account menu). Approval is free and commits you to nothing, so apply as soon as the v1.0 date is set.
2. Supply the business details for **Expansive Labs LLC**: legal name, address, tax information (W-9 for a US LLC), and payout details.
3. Expect **3–10 business days**. If you are still waiting at T-4, email support rather than re-applying.
4. Choose the **free creator tier** at signup. Commission is 70% on the free plan and up to 90% on paid subscriptions — but subscriptions only pay off above roughly 20–30 sales/month (pricing strategy §4). Revisit after your first full month.

## Part 2 · Prepare the submission

5. Substitute the confirmed price into `copy/platform-adaptations/superhive.md`, replacing every `$[PRICE]` token.
6. Fill the **product requirements field** with the GPU warning block from that copy file, verbatim. Superhive surfaces this field prominently and it is your best refund defence.
7. Assemble the gallery in the order given in the copy file — the demo video first. Superhive's product cards favour video, and it converts far better than a static banner.
8. Have ready: the `tessera-v<VERSION>.zip` from the GitHub Release, the hero banner, the 7 screenshots, the seller bio, and the FAQ.

## Part 3 · Create the product

9. From the creator dashboard choose **New Product** and set: name `Tessera — AI Image-to-3D for Blender`, category *Add-ons → Modeling*, licence *GPL-2.0-or-later*.
10. Set **Blender version compatibility** to 4.2, 4.3 and 4.4, and tick Windows, macOS and Linux for operating systems. Do not tick a Blender version you have not actually launched the add-on in.
11. Paste the full description from the copy file. Superhive's editor accepts Markdown-ish formatting — check the preview, especially the tables.
12. Upload the `.zip` as the deliverable, then the gallery images and video in order.
13. Set the price and, if you are running the launch promo, configure the discount with a hard end date.
14. Add tags: `ai`, `3d-printing`, `image-to-3d`, `photogrammetry`, `mesh`, `stl`, `reconstruction`, `modeling`.
15. Submit for **product review** — expect a further 3–5 business days. Reviewers check that the product works, matches its description, and complies with licensing.

## Part 4 · After approval

16. Confirm the live listing renders correctly, especially the requirements block and the compatibility matrix.
17. Answer every product question within 24 hours. Superhive's Q&A is public and doubles as pre-sale marketing.
18. Enable **affiliate coupons** once you have a few reviews. They cost commission but reach buyers you cannot.
19. Add the listing URL to `README.md` — but **not** to the extensions.blender.org listing, the `blender_manifest.toml`, or any in-add-on UI string (CON-002).

## ⚠️ The 12-month support policy — know what you signed up for

Since **12 May 2026**, every Superhive purchase carries 12 months of support and updates; after that buyers pay 50% of list price for newer versions. It applies to all vendors, retroactively, with no opt-out, and it generated real customer and creator backlash.

Practical consequences:

- Your Superhive revenue has a renewal tail you did not design. Do not promise "lifetime updates" in the Superhive listing — you cannot deliver it there.
- You **can** promise lifetime updates on Gumroad, and that is a legitimate reason for buyers to choose the direct channel. Say so on your own site, your own posts, and your own emails — **never inside the Superhive listing or its Q&A.**
- Expect questions about it. Answer factually, point to Superhive's policy page, and do not editorialise on their platform.

---

## Version update procedure (~5 minutes)

1. Download the new `tessera-v<VERSION>.zip` from the GitHub Release.
2. On the product management page, upload it as the current file — version bumps do not require re-review.
3. Paste the release notes into the "What's New" field from `copy/changelog-template.md`, matching the text you sent Gumroad buyers.
4. Update the Blender version compatibility if the supported range changed, and save.

## If something goes wrong

| Symptom | Action |
|---|---|
| Seller application rejected | Ask for the specific reason, fix it, re-apply. Launch on Gumroad on schedule regardless — Superhive is the discovery channel, not the dependency |
| Product review rejected | Usually description/product mismatch or a licensing detail. Fix and resubmit; the queue is short the second time |
| Review complains about GPU requirements | Reply publicly, factually, and point at the requirements block. Then check whether that block is actually visible on the live listing |
| Review complains "it's free on GitHub" | Reply once, plainly: yes, GPL, source public, the listing pays for packaging, testing, support and development. Do not argue past one reply |
