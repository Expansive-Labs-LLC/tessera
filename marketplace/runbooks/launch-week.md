# Runbook — Launch Week

> The marketplace page converts traffic; it does not create it. This is the plan for creating it. Assumes the Gumroad page is built ([gumroad-upload.md](gumroad-upload.md)) and the demo video exists.
>
> Every post below links to the **Gumroad page**, not to GitHub — GitHub is one click further in, for the people who want it.

---

## T-14 → T-1 · Preparation

| Day | Task |
|---|---|
| T-14 | Submit the Superhive seller application (free, non-committal, slow queue) |
| T-14 | Create and verify the Gumroad account and payout method |
| T-12 | Clear the model-licence blocker (GTM-STRATEGY §2.2) — nothing ships before this |
| T-10 | Print 5–10 real objects through the pipeline. Record what worked, what failed, and why. **This is the gallery and the honest success rate** |
| T-7 | Shoot the demo video. Functional part, not a figurine. Photo → mesh → validation → slicer → timelapse → part in hand |
| T-5 | Capture and annotate the 7 screenshots and the hero banner |
| T-3 | Build the Gumroad page. Self-purchase with a 100% coupon and test the full install path |
| T-2 | Verify the docs site, every listing link, and a clean install on a second machine |
| T-1 | Draft every post below. Writing them live on launch day guarantees the worst version of each |

## T-0 · Launch day

Post in this order, spacing them across the day rather than firing everything at 9am.

| Time | Channel | Format | Notes |
|---|---|---|---|
| 09:00 | **r/functionalprint** | Photo of the printed part first, tool mentioned in the comments | This subreddit rewards the object, not the tool. Lead with the part that fits |
| 10:00 | **BlenderArtists → Released Add-ons and Extensions** | Full post: video, screenshots, feature list, price, requirements | The canonical Blender add-on announcement venue. Reply to every reply |
| 11:00 | **r/blender** | Demo video, tool disclosed in the title | Read the self-promotion rules first; disclosure is required and unflagged ads get removed |
| 13:00 | **r/3Dprinting** | The video, framed as "photo → printable model" | Hostile to undisclosed advertising. Be explicit that it is your tool and it is paid |
| 14:00 | **Bluesky / X** | Video + `#b3d` | `#b3d` is the tag Blender developers and artists actually follow |
| 15:00 | **Blender Discord** — add-on showcase channel | Video + link | Read the channel rules; some limit self-promo to specific channels or days |
| 16:00 | **BlenderNation tip submission** | Short pitch + video + link | They cover new add-ons and drive meaningful traffic. One submission, no follow-up pestering |
| Evening | **Printables + MakerWorld** | Upload the printed model's STL, credit Tessera in the description | Shared files buy you the right to mention the tool |

**Rules for every post:**
- Lead with the printed object. The AI is the mechanism, not the story.
- State the GPU requirement in the post itself, not only on the listing.
- Say the price. Hiding it reads as a bait-and-switch and gets punished in comments.
- Say it is GPL with public source. In these communities that earns goodwill rather than losing sales.
- Answer every comment for the first 48 hours, including the hostile ones, briefly and without defensiveness.

## T+1 → T+7 · The week

- **Daily:** answer every comment, email and issue within a few hours. Launch-week responsiveness is what produces the first reviews.
- **T+2:** post the first "here's what broke" update — a real bug found by a real buyer and what you did. This is the highest-trust post you can make and nobody expects it.
- **T+3:** email early buyers asking for one sentence and a photo of their print. Two or three replies are enough to carry the v1.0 listing.
- **T+5:** publish a GPU compatibility table built from real buyer reports. Add it to the listing and the docs.
- **T+7:** ship a patch release, however small, and send the update email. Visible velocity is the strongest quality signal an early-access product has.

## T+30 · Review

Pull the numbers against GTM-STRATEGY §8 and answer four questions honestly:

1. **Refund rate.** Above 10%? The listing is overpromising — usually the GPU requirement or the success rate. Fix the copy before spending on anything else.
2. **Conversion.** Below 1.5%? The video is not proving the print. Reshoot with a part that visibly fits where it belongs.
3. **Support load.** Over 3 tickets per 10 sales? Find the top ticket and fix it in the product or the docs before scaling traffic.
4. **Which channel sold?** Double down there next time; drop the ones that produced nothing rather than repeating them out of habit.

Then decide whether v1.0 and the Superhive listing are 30 days away or 90.

## Post templates

Keep these in the repo so they are edited and improved rather than rewritten each time.

**BlenderArtists / Reddit long-form:**
```
I built a Blender add-on that turns reference photos into print-ready models.

[VIDEO]

The part in the video is a [object] I needed and couldn't buy. Two phone photos,
one generate, one validation pass, printed on a [printer] — it fits.

The bit I actually care about: it validates before you export. Manifold,
watertight, wall thickness, overhangs, build-volume fit against your printer's
real dimensions, with auto-repair. Most image-to-3D tools hand you a mesh that
looks fine and fails in the slicer.

Everything runs locally on your GPU. No account, no API key, no credits, nothing
uploaded. Needs an NVIDIA CUDA card with 8GB+ VRAM — no AMD, no Apple Silicon
and no integrated graphics yet, sorry.

GPL-2.0-or-later, source is on GitHub. The paid package is the built, tested,
supported version: [PRICE] at [GUMROAD URL].

Happy to answer anything, including what it's bad at.
```

**Short social:**
```
Photo of a broken [object] → print-ready STL, without leaving Blender.

Runs on your own GPU. Validates manifold geometry, wall thickness and build
volume before export, so it doesn't die in the slicer.

[VIDEO] #b3d #3dprinting
```
