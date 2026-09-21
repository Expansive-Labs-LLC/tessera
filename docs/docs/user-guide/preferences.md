# Preferences

Tessera's preferences panel controls GPU configuration, model caching, and LLM backend settings. Access preferences via **Blender Preferences → Add-ons → Tessera**.

![Tessera Preferences panel showing GPU Device selector displaying NVIDIA RTX 3080 with 10 GB VRAM, cache directory path, and LLM backend dropdown set to Local GGUF](assets/screenshots/preferences-gpu.png)

---

## GPU Device Selector

The GPU section displays your detected GPU and available VRAM:

- **GPU Name** — The detected GPU device (e.g., "NVIDIA GeForce RTX 3080").
- **VRAM** — Available GPU memory in GB.
- **Backend** — The compute backend (CUDA, ROCm, or MPS).

!!! info "GPU Detection"
    GPU information is detected automatically when the add-on loads. If your GPU is not detected, check that GPU drivers are installed and the GPU is recognized in **Blender Preferences → System**.

---

## Model Cache Directory

Configure where Tessera stores downloaded AI model weights:

- **Default**: `~/.cache/tessera/` (Linux/macOS) or `%APPDATA%\tessera\` (Windows)
- Click the folder icon to browse for a different directory.
- Tessera validates that the selected directory has write permissions.

!!! warning "Write Permission Required"
    If the selected directory is not writable, Tessera displays an error. Choose a directory where your user account has write access.

---

## LLM Backend Selection

Tessera uses an LLM to interpret natural language refinement commands. Two backend options are available:

### Local GGUF

Runs a GGUF-format language model locally on your GPU.

- **Model Path** — Path to the `.gguf` model file.
- **VRAM Usage** — Approximately 8 GB additional VRAM required.
- **Advantage** — Fully offline, no API keys needed.

### API Backend

Connects to a local or remote LLM API endpoint.

- **API Endpoint** — The URL of the LLM API server (e.g., `http://localhost:11434/v1`).
- **API Key** — Authentication key for the API (leave blank for local servers like Ollama).
- **Advantage** — Lower VRAM usage; LLM runs on a separate server.

![Tessera Preferences panel showing LLM Backend section with API selected, endpoint URL field, and API key field with masked input](assets/screenshots/preferences-llm.png)

---

## Model Download Management

Manage AI model weight downloads from the preferences panel:

- **Download All Models** — Downloads all required model weights (~2 GB total).
- **Clear Cache** — Deletes all cached model weights to free disk space.
- **Cache Size** — Displays the current total size of cached model files.

---

## Download on First Use

When enabled (default), Tessera automatically downloads model weights the first time each model is needed, instead of requiring a manual download-all step.

- **Enabled (default)** — Models download automatically when first needed. Requires internet connection on first use of each feature.
- **Disabled** — All models must be downloaded manually via the Model Manager panel before use.

!!! tip "Offline Workflows"
    If you work offline or want to avoid unexpected downloads, disable this option and use **Download All Models** to pre-download everything while connected.

---

## See Also

- [Installation](../installation.md) — Initial setup and GPU requirements
- [Refinement](refinement.md) — Using the LLM-powered refinement loop

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
