# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Sketch synthesizer — ControlNet sketch-to-rendered-image conversion.

Uses a locally-hosted Stable Diffusion model with ControlNet
(scribble/lineart conditioning) to generate a photo-realistic
rendered image from a preprocessed sketch.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SketchSynthesizer — diffusion-based sketch-to-image (FR-016)

Implements: FR-016, FR-017, FR-018, FR-019, FR-020, FR-021, FR-022,
            FR-023, CON-001, CON-002, CON-004, CON-008, SEC-003,
            SEC-004, SEC-006.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from tessera.sketch.types import (
    DEFAULT_SYNTHESIS_PROMPT,
    SYNTHESIS_RESOLUTION,
    PreprocessedSketch,
    SketchConfig,
    SynthesizedImage,
)

logger = logging.getLogger("tessera.sketch")


class SketchSynthesizer:
    """Convert a preprocessed sketch into a photo-realistic rendered image.

    Uses ControlNet (scribble/lineart conditioning) with Stable Diffusion
    to bridge the domain gap between line drawings and photorealistic
    inputs required by 3D reconstruction models.

    All inference runs locally on the user's GPU (CON-001). The
    diffusion model is loaded on demand and unloaded after synthesis
    to free VRAM for downstream reconstruction (FR-023, CON-002).

    Args:
        cache_dir: Absolute path to the model weight cache directory.

    Example::

        synth = SketchSynthesizer(cache_dir="/path/to/cache")
        result = synth.synthesize(preprocessed_sketch, "a vase", config)
        print(f"Output shape: {result.rendered_image.shape}")

    Implements: FR-016.
    """

    def __init__(self, cache_dir: str) -> None:
        self._cache_dir = cache_dir
        self._pipe = None

    def synthesize(
        self,
        sketch: PreprocessedSketch,
        prompt: str,
        config: SketchConfig,
    ) -> SynthesizedImage:
        """Generate a photo-realistic rendering from a sketch.

        Args:
            sketch: Preprocessed sketch from ``SketchPreprocessor``.
            prompt: Text prompt describing the object. Empty string
                or ``None`` uses the default prompt (FR-018).
            config: Synthesis configuration (seed, guidance scale,
                inference steps).

        Returns:
            ``SynthesizedImage`` with the rendered output.

        Implements: FR-016–FR-023, CON-001, CON-002, SEC-003, SEC-004.
        """
        # FR-018: Use default prompt if none provided.
        if not prompt:
            prompt = DEFAULT_SYNTHESIS_PROMPT

        logger.info(
            "Sketch synthesis started: prompt=%s, seed=%d, "
            "guidance_scale=%.1f, num_steps=%d",
            prompt,
            config.synthesis_seed,
            config.guidance_scale,
            config.num_inference_steps,
        )

        t0 = time.monotonic()

        try:
            rendered = self._run_diffusion(sketch, prompt, config)
        finally:
            # FR-023: Always unload model from VRAM after synthesis.
            self._unload_model()

        inference_time = time.monotonic() - t0

        result = SynthesizedImage(
            rendered_image=rendered,
            prompt_used=prompt,
            seed=config.synthesis_seed,
            inference_time_s=inference_time,
            guidance_scale=config.guidance_scale,
        )

        logger.info(
            "Sketch synthesis complete: inference_time_s=%.2f, " "output_size=%s",
            inference_time,
            f"{rendered.shape[1]}x{rendered.shape[0]}",
        )
        return result

    def _run_diffusion(
        self,
        sketch: PreprocessedSketch,
        prompt: str,
        config: SketchConfig,
    ) -> np.ndarray:
        """Run ControlNet + Stable Diffusion inference.

        Loads the diffusion pipeline, prepares the control image from
        the sketch, and generates a 512×512 rendered image.

        CON-008: All inference runs in-process via Python/PyTorch.
        CON-001: No network calls — all weights from local filesystem.
        SEC-004: No temp files — all processing in memory.

        Args:
            sketch: Preprocessed sketch.
            prompt: Synthesis prompt.
            config: Pipeline configuration.

        Returns:
            Rendered image as ``(512, 512, 3)`` uint8 RGB.

        Implements: FR-017, FR-019, FR-020, FR-021.
        """
        try:
            import torch
            from diffusers import (
                ControlNetModel,
                StableDiffusionControlNetPipeline,
                UniPCMultistepScheduler,
            )
            from PIL import Image as PILImage
        except ImportError as e:
            logger.error("Required diffusion libraries not available: %s", e)
            raise RuntimeError(
                "Sketch synthesis requires 'diffusers' and 'torch' "
                "libraries. Please install them."
            ) from e

        # CON-004: Resolve model paths within cache directory.
        controlnet_path = Path(self._cache_dir) / "controlnet-scribble-v1"
        sd_path = Path(self._cache_dir) / "stable-diffusion-v1-5"

        # SEC-006: Validate paths reside within cache.
        resolved_cache = Path(self._cache_dir).resolve()
        for model_path in (controlnet_path, sd_path):
            resolved = model_path.resolve()
            if not str(resolved).startswith(str(resolved_cache)):
                raise ValueError(f"Model path {resolved} is outside cache directory")

        # Load ControlNet model.
        load_start = time.monotonic()

        controlnet = ControlNetModel.from_pretrained(
            str(controlnet_path),
            torch_dtype=torch.float16,
            local_files_only=True,  # CON-001: No network calls.
        )

        # Load Stable Diffusion pipeline with ControlNet.
        pipe = StableDiffusionControlNetPipeline.from_pretrained(
            str(sd_path),
            controlnet=controlnet,
            torch_dtype=torch.float16,
            local_files_only=True,  # CON-001: No network calls.
        )

        # Use efficient scheduler.
        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)

        # Move to GPU.
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        pipe = pipe.to(device)

        # Enable memory optimisations.
        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()

        self._pipe = pipe

        load_time = time.monotonic() - load_start
        vram_used = 0.0
        if torch.cuda.is_available():
            vram_used = torch.cuda.memory_allocated() / (1024**2)
        logger.debug(
            "Diffusion model loaded: model_name=SD1.5+ControlNet, "
            "vram_used_mb=%.0f, load_time_s=%.2f",
            vram_used,
            load_time,
        )

        # Prepare control image from sketch.
        # Use the thinned image resized to 512×512.
        import cv2

        control_image = cv2.resize(
            sketch.thinned_image,
            (SYNTHESIS_RESOLUTION, SYNTHESIS_RESOLUTION),
            interpolation=cv2.INTER_LINEAR,
        )
        # ControlNet expects RGB — convert single-channel to 3-channel.
        control_rgb = np.stack([control_image] * 3, axis=-1)
        control_pil = PILImage.fromarray(control_rgb)

        # FR-020: Fixed random seed for deterministic output.
        generator = torch.Generator(device=device).manual_seed(config.synthesis_seed)

        # FR-021: Run inference.
        output = pipe(
            prompt=prompt,
            image=control_pil,
            num_inference_steps=config.num_inference_steps,
            guidance_scale=config.guidance_scale,
            generator=generator,
        )

        # FR-019: Extract 512×512 RGB uint8 output.
        rendered_pil = output.images[0]
        rendered = np.array(
            rendered_pil.resize((SYNTHESIS_RESOLUTION, SYNTHESIS_RESOLUTION))
        )

        # Ensure uint8 RGB format.
        if rendered.dtype != np.uint8:
            rendered = (rendered * 255).clip(0, 255).astype(np.uint8)
        if rendered.ndim == 2:
            rendered = np.stack([rendered] * 3, axis=-1)
        elif rendered.shape[2] == 4:
            rendered = rendered[:, :, :3]

        return rendered

    def _unload_model(self) -> None:
        """Unload the diffusion model from GPU VRAM.

        FR-023: Must be called after synthesis completes (both
        success and failure) to free VRAM for reconstruction.

        Implements: FR-023, CON-002.
        """
        vram_before = 0.0
        try:
            import torch

            if torch.cuda.is_available():
                vram_before = torch.cuda.memory_allocated() / (1024**2)
        except ImportError:
            pass

        if self._pipe is not None:
            del self._pipe
            self._pipe = None

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                vram_after = torch.cuda.memory_allocated() / (1024**2)
                freed = vram_before - vram_after
                logger.debug("Diffusion model unloaded: vram_freed_mb=%.0f", freed)
        except ImportError:
            pass

        import gc

        gc.collect()
