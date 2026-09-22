# Runbook — Blender Extensions Platform (extensions.blender.org)

> ## 🔴 BLOCKED — do not submit yet
>
> Tessera is ineligible as currently architected. Blender's add-on guidelines forbid installing Python modules, pip packages or wheels at runtime, and `requirements.txt` states that the ML stack downloads into Blender's environment at add-on runtime. Bundling the stack instead is not viable either: uploads above ~200 MB are rejected with HTTP 413, and a CUDA `torch` wheel alone is many times that.
>
> **A rejected submission is public and makes a later attempt harder.** Clear the blocker first — see GTM-STRATEGY §2.1 and CSO decision D3.

---

## Part 0 · Unblocking (the actual work)

The guidelines allow one compliant path: *"If some additional software required that cannot be bundled, this can be run by the user."* That means splitting Tessera into:

- a **thin Blender-side add-on** — panels, operators, mesh I/O, validation — with no heavy Python dependencies, well under the size cap
- a **separately installed local Tessera Engine** — the ML stack, installed by the user outside Blender and reached over localhost

Side benefits worth weighing in the ADR: AMD/ROCm and CPU fallback become possible, engine updates decouple from add-on updates, and the add-on becomes testable without a GPU.

**Exit criteria before any submission:**

- [ ] ADR approved and implemented
- [ ] The add-on `.zip` installs and runs with zero runtime package installation
- [ ] `.zip` comfortably under 200 MB
- [ ] Any bundled Python dependency is an unmodified wheel from PyPI, declared in `blender_manifest.toml`
- [ ] `bpy.app.online_access` is honoured before every network call, including weight downloads
- [ ] No string anywhere in `tessera/ui/` or the manifest mentions purchasing, pricing, or a paid channel

## Part 1 · First-time setup

1. Create a Blender ID at `id.blender.org` if you do not have one — this is the same account used across blender.org services.
2. Sign in at `extensions.blender.org` and accept the developer terms. There is no approval process for developer accounts; only extensions are moderated.
3. Decide the maintainer identity now: `blender_manifest.toml` currently declares `Expansive Labs LLC <hello@expansivelabs.com>`, and the listing should match.

## Part 2 · Submission

4. Choose **Submit Extension** and upload the `tessera-v<VERSION>.zip` built by CI, which already carries `blender_manifest.toml` and `LICENSE` at the archive root.
5. Verify the auto-populated metadata matches the manifest: id `tessera`, name `Tessera`, tagline, version, `blender_version_min = 4.2.0`, licence `SPDX:GPL-2.0-or-later`, and both declared permissions.
6. Paste the listing description from `copy/platform-adaptations/extensions-platform.md`. Re-read it once for any commercial language before saving — this is the one platform where that gets you rejected.
7. Set category **3D View** and tags `ai`, `3d-printing`, `reconstruction`, `mesh`, `modeling`.
8. Submit for moderation. Expect **1–5 business days**; moderators may ask questions, so watch the email tied to your Blender ID.

## Part 3 · Compliance — re-check before every submission

The platform is free-only and prohibits commercial advertising. The listing, the manifest, and the add-on UI must contain **no** link to Gumroad or Superhive, **no** pricing or purchase CTA, **no** "pro/premium/paid version" language, and **no** donation or sponsorship appeal.

Listing here while selling the same extension elsewhere is explicitly permitted — the platform says so directly. The only rule is that the free listing must not advertise the paid ones.

Also required: the `network` permission must carry a truthful reason string, and the add-on must respect Blender's *Allow Online Access* preference — no network traffic at all when the user has disabled it.

## Version updates

1. Open the existing extension page and choose **Upload New Version**.
2. Upload the new CI-built `.zip`.
3. Add version notes drawn from `CHANGELOG.md`, with any commercial phrasing stripped.
4. Submit for re-review — each new version is moderated again.

## Sources

- [Add-on Guidelines](https://developer.blender.org/docs/handbook/extensions/addon_guidelines/) · [Python Wheels](https://docs.blender.org/manual/en/latest/advanced/extensions/python_wheels.html) · [About](https://extensions.blender.org/about/) · [Terms of Service](https://extensions.blender.org/terms-of-service/) · [413 on large uploads](https://projects.blender.org/infrastructure/extensions-website/issues/328)
