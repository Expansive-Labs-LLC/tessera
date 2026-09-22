# Custom Models

Tessera ships with a short list of models it knows how to use, and downloads them on first run. You are not limited to that list — you can add any compatible model from [Hugging Face](https://huggingface.co) and Tessera will verify and manage it exactly like a bundled one.

!!! warning "Model weights are not Tessera's software"
    Tessera's code is GPL-2.0-or-later. Model weights are published by third parties under **their own licences**, are downloaded to your machine rather than redistributed by us, and remain your responsibility to use within those terms. Tessera checks what a publisher declares and refuses anything that is not clearly commercial-friendly — but a licence check is not legal advice, and an added model is a choice you are making. See [MODEL-LICENSES.md](https://github.com/Expansive-Labs-LLC/tessera/blob/main/MODEL-LICENSES.md).

---

## Adding a model

1. Open **Edit → Preferences → Add-ons → Tessera**.
2. In the **Models** section, click **Add from Hugging Face**.
3. Fill in the dialog:

| Field | What to enter |
|---|---|
| **Repository** | The Hugging Face repository id, in the form `owner/name` — for example `depth-anything/Depth-Anything-V2-Base`. |
| **Architecture** | Which family the checkpoint belongs to. Tessera can only load architectures it has an adapter for (see below). |
| **Variant** | The variant within that family, where it applies. For Depth Anything V2 this is the encoder: `vits`, `vitb`, `vitl` or `vitg`. |
| **Name** | Optional. What to call it in your model list; derived from the repository name if you leave it blank. |

![The Add Model from Hugging Face dialog, showing the Repository, Architecture, Variant and Name fields with the licence notice below them](../assets/screenshots/custom-models-add-dialog.png)

4. Click **OK**. Tessera looks the repository up, resolves its licence and a checksum for every file, and adds it to the list. **Nothing is downloaded yet.**
5. Click **Download** on the new entry when you want the weights.

![The Models list in preferences with a user-added model, showing its licence, its source repository and the Download and Remove buttons](../assets/screenshots/custom-models-list.png)

To remove one, click **Remove** on its row. That takes it out of your list; use **Delete** first if you also want the cached files off your disk.

## Supported architectures

Tessera instantiates a specific model class for each pipeline stage, so a model must belong to a family it has an adapter for.

| Family | Stage | Can Tessera load an alternative checkpoint? |
|---|---|---|
| **Depth Anything V2** | Depth estimation | ✅ Yes — any `vits` / `vitb` / `vitl` / `vitg` checkpoint |
| **Segment Anything 2** | Segmentation | ⏳ Downloadable and verified, loader not yet wired up |
| **DINOv2** | Feature extraction | ⏳ Downloadable and verified, loader not yet wired up |
| **TRELLIS** | 3D reconstruction | ⏳ Downloadable and verified, loader not yet wired up |

Entries marked ⏳ can be added, licence-checked, downloaded and cached today, but the adapter still resolves a fixed checkpoint, so it cannot be pointed at your copy yet. The model list says so on the row, and names the work that will change it.

## What Tessera checks before adding

Every added model goes through the same gates as a bundled one.

**Licence.** Tessera reads the `license` tag the publisher declared on the repository and classifies it:

| Classification | Examples | What happens |
|---|---|---|
| Allowed | `apache-2.0`, `mit`, `bsd-3-clause`, `cc-by-4.0` | Added normally |
| Restricted | `openrail`, `creativeml-openrail-m`, Llama and Gemma community licences | Refused unless you opt in — these permit commercial use but attach conditions you must pass on to anyone you share output with |
| Prohibited | `cc-by-nc-4.0` and other non-commercial terms | Refused unless you opt in — you may not use the output commercially |
| Unknown | `other`, or no licence declared at all | Refused unless you opt in — there are no stated terms to comply with, which is worse than restrictive ones |

Anything that is not clearly commercial-friendly **fails closed**. To add one anyway, enable **Allow Restricted-Licence Models** in the same preferences panel; it is off by default and shows a warning while it is on.

**Integrity.** Tessera records a SHA-256 for every file at the exact commit you added, and verifies downloads against it. Large files use the checksum the Hub publishes; small ones are fetched and hashed. A file Tessera cannot obtain a checksum for is refused — a model that cannot be verified is not added.

**Pinning.** The repository's current commit is stored with the entry, so the weights you approved are the weights you get. A publisher changing the model — or its licence — later does not change what you downloaded.

**File types.** Only data files are accepted (`.safetensors`, `.pth`, `.pt`, `.bin`, `.onnx`, `.json`, `.yaml`), and weights are always loaded with PyTorch's `weights_only=True`. Prefer `.safetensors` where a publisher offers it: it cannot carry executable content at all.

## Where your list is stored

Added models live in `user_models.json` inside your model cache directory — not inside the add-on — so **they survive add-on updates**. You can copy that file between machines. If it is ever corrupted, Tessera logs the problem, ignores the file and carries on with the bundled models.

## Worked example — a larger depth model

Depth Anything V2 ships in four sizes. Tessera defaults to **Small**, because it is the only one published under Apache-2.0. If your work is non-commercial and you want more accuracy:

1. Enable **Allow Restricted-Licence Models** in preferences. (The Base, Large and Giant checkpoints are CC-BY-NC-4.0 — **non-commercial use only**. You may not sell prints made through them.)
2. **Add from Hugging Face** → Repository `depth-anything/Depth-Anything-V2-Base`, Architecture *Depth Anything V2*, Variant `vitb`.
3. Download it, then select it as your depth model.

If your work *is* commercial, stay on Small. The accuracy difference is modest in Tessera's pipeline, where depth is one prior among several and is masked to the segmented subject before use.

## Troubleshooting

| Message | What it means |
|---|---|
| "is not a Hugging Face repository id" | Enter `owner/name`, not a full URL. |
| "That repository is private or gated" | Tessera only adds publicly downloadable models. Gated repositories that need an access token are not supported. |
| "holds no files Tessera can use" | The repository has no files matching that family's expected types. Check you picked the right architecture. |
| "no published checksum and is too large to verify" | The repository stores a large file without a Hub checksum. Tessera will not add what it cannot verify. |
| "declares its licence as … it was not added" | The licence is non-commercial, restricted or undeclared. Read the terms, and enable restricted models only if your use complies. |

## See Also

- [Preferences](preferences.md) — where the model list and the restricted-licence opt-in live
- [Installation](../installation.md#model-weight-download) — the default model download
- [3D Reconstruction](reconstruction.md) — which model each pipeline stage uses
- [FAQ](../faq.md) — licensing and GPU questions
- [MODEL-LICENSES.md](https://github.com/Expansive-Labs-LLC/tessera/blob/main/MODEL-LICENSES.md) — the terms of every bundled model
