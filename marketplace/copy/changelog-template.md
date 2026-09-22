# Changelog Template — Marketplace Version Notes

> Copy this block for every release. Post the same text to Gumroad (as a product update email), Superhive (the "What's New" field), and the GitHub Release body. Keep wording identical across channels — buyers compare.

---

## Tessera v[X.Y.Z] — [Month DD, YYYY]

**[One-sentence summary of why this release matters to a user, not to a developer.]**

### What's New

- **[Feature name]** — [what it does, in the user's words, and what it lets them do that they couldn't before]
- **[Feature name]** — [...]

### Improvements

- [Measurable change: "multi-view reconstruction is ~30% faster on 6-image projects"]
- [...]

### Bug Fixes

- Fixed [symptom the user would have noticed] ([#issue](https://github.com/Expansive-Labs-LLC/tessera/issues/N))
- [...]

### Breaking Changes

> Delete this section if there are none. Never bury one.

- [What broke, who it affects, and the exact migration step]

### Update Instructions

**Gumroad buyers:** re-download from your Gumroad library or the link in your purchase email, then in Blender go to Edit → Preferences → Add-ons, remove the previous Tessera version, and install the new `.zip`.

**Superhive buyers:** download the new version from your Superhive library, then follow the same remove-and-install steps.

**Building from source:** `git pull && ./scripts/build_addon.sh`

**Model weights:** [State whether this release requires a new weight download and how large it is — or "no weight changes in this release".]

### Compatibility

- Blender: [4.2 LTS – 4.x]
- GPU: [unchanged / new minimum]
- Breaking changes to saved `.blend` scenes: [none / describe]

---

### Pre-publication checklist

- [ ] Version number matches `blender_manifest.toml` and `bl_info`
- [ ] Every "What's New" claim is implemented and tested, not planned
- [ ] Issue links resolve publicly
- [ ] Breaking changes stated at the top of the Gumroad update email, not only here
- [ ] Same text posted to all channels within the same hour
