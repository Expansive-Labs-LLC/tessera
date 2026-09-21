# Installation

Tessera requires **Blender 4.2 LTS** or newer and a CUDA or MPS-compatible GPU with at least **4 GB VRAM**.

---

## Prerequisites

- **Blender 4.2+** — Download from [blender.org](https://www.blender.org/download/)
- **GPU** — NVIDIA (CUDA 11.8+), AMD (ROCm 5.6+), or Apple Silicon (MPS)
- **Disk Space** — At least 2 GB free for AI model weights
- **Internet** — Required for initial model weight downloads only

---

## Installation Steps

=== "Windows"

    1. Download the latest `tessera-vX.X.X.zip` from the [Releases page](https://github.com/Expansive-Labs-LLC/tessera/releases).
    2. Open Blender → **Edit → Preferences → Add-ons**.
    3. Click **Install from Disk...** and select the downloaded ZIP file.
    4. Enable the "Tessera" add-on by checking its checkbox.
    5. The Tessera panel appears in the **3D Viewport sidebar** (press ++n++ to toggle).

    !!! tip "NVIDIA Drivers"
        Ensure you have the latest NVIDIA Game Ready or Studio drivers installed.
        CUDA is included with Blender's bundled Python on Windows.

=== "macOS (Apple Silicon)"

    1. Download the latest `tessera-vX.X.X.zip` from the [Releases page](https://github.com/Expansive-Labs-LLC/tessera/releases).
    2. Open Blender → **Blender → Preferences → Add-ons**.
    3. Click **Install from Disk...** and select the downloaded ZIP file.
    4. Enable the "Tessera" add-on.
    5. Verify the Tessera tab appears in the 3D Viewport sidebar (press ++n++).

    !!! warning "Apple Silicon (M1/M2/M3)"
        Tessera uses MPS (Metal Performance Shaders) on Apple Silicon.
        Performance may vary compared to CUDA GPUs. Ensure macOS 13+ is installed.

=== "Linux"

    1. Download the latest `tessera-vX.X.X.zip` from the [Releases page](https://github.com/Expansive-Labs-LLC/tessera/releases).
    2. Open Blender → **Edit → Preferences → Add-ons**.
    3. Click **Install from Disk...** and select the downloaded ZIP file.
    4. Enable the "Tessera" add-on.
    5. Verify the Tessera tab appears in the 3D Viewport sidebar (press ++n++).

    !!! tip "GPU Drivers"
        - **NVIDIA**: Install CUDA toolkit 11.8+ and latest proprietary drivers.
        - **AMD**: Install ROCm 5.6+ from AMD's official repository.

---

## Build from Source

If you prefer to install from the repository source:

1. Clone the repository:
   ```bash
   git clone https://github.com/Expansive-Labs-LLC/tessera.git
   ```
2. Navigate to the project directory:
   ```bash
   cd tessera
   ```
3. Create the add-on ZIP:
   ```bash
   zip -r tessera.zip tessera/
   ```
4. In Blender, go to **Preferences → Add-ons → Install from Disk** and select `tessera.zip`.
5. Enable the "Tessera" add-on by checking its checkbox.
6. Verify the Tessera panel appears in the 3D Viewport sidebar (press ++n++).

---

## GPU VRAM Requirements

Different features require different amounts of GPU VRAM:

| Feature Tier | Minimum VRAM |
|-------------|-------------|
| Basic reconstruction (single-image) | 4 GB |
| Multi-view reconstruction | 8 GB |
| Sketch-to-3D | 8 GB |
| NL refinement (local LLM) | 8 GB |
| All features simultaneously | 12 GB recommended |

!!! info "Shared Memory on Apple Silicon"
    On Apple Silicon Macs, GPU memory is shared with system RAM. A Mac with 16 GB unified memory provides approximately 10–12 GB usable for GPU tasks.

---

## Apple Silicon (MPS)

!!! note "Apple Silicon Support"
    Tessera uses **Metal Performance Shaders (MPS)** on Apple Silicon Macs (M1, M2, M3, M4).

    - **macOS 13 (Ventura) or newer** is required for MPS support in PyTorch.
    - VRAM is **shared system memory** — a 16 GB Mac allocates GPU memory from the unified pool.
    - Performance characteristics differ from CUDA: some operations may be faster, others slower.
    - MPS support is continually improving in PyTorch — use the latest Blender release for best results.

---

## Model Weight Download

After installation, Tessera needs to download AI model weights (~2 GB total):

1. Open the **Tessera → Model Manager** panel in the 3D Viewport sidebar.
2. Click **Download All Models** to fetch required weights.
3. The download progress is shown in the panel.

Alternatively, Tessera can download models on first use if **Download on First Use** is enabled in preferences (enabled by default).

**Cache directory locations:**

| Platform | Default Cache Path |
|----------|-------------------|
| Linux | `~/.cache/tessera/` |
| macOS | `~/.cache/tessera/` |
| Windows | `%APPDATA%\tessera\` |

To change the cache directory, go to **Blender Preferences → Add-ons → Tessera → Cache Directory**. See the [Preferences guide](user-guide/preferences.md) for details.

---

## Verifying Installation

1. Open a new Blender scene.
2. Press ++n++ to open the sidebar and select the **Tessera** tab.
3. You should see the Tessera panels: Image Input, Generation, Validation, Export.
4. If you see a GPU error, check the [Troubleshooting](troubleshooting.md) page.

---

## Updating

To update Tessera:

1. Download the new version ZIP from the Releases page.
2. In Blender Preferences → Add-ons, find "Tessera" and click **Remove**.
3. Restart Blender.
4. Install the new ZIP following the steps above.

!!! note
    Model weights are preserved between updates — you don't need to re-download them.

---

## See Also

- [Quick Start Guide](quickstart.md) — Create your first model in 5 steps
- [Preferences](user-guide/preferences.md) — Configure GPU, cache, and LLM settings
- [Troubleshooting](troubleshooting.md) — Resolve installation and GPU issues
