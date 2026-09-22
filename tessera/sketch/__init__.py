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

"""Sketch-to-3D pathway for the Tessera Blender add-on.

Provides image classification, preprocessing, diffusion-based synthesis,
symmetry enforcement, and pipeline orchestration to convert hand-drawn
sketches into 3D-printable meshes.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SketchPipeline — main pipeline entry point (FR-030)
    SketchDetector — photo vs. sketch classification (FR-001)
    SketchPreprocessor — sketch cleaning and normalisation (FR-007)
    SketchSynthesizer — ControlNet sketch-to-rendered-image (FR-016)
    SymmetryEnforcer — bilateral symmetry post-processing (FR-024)
"""

from tessera.sketch.detector import SketchDetector
from tessera.sketch.pipeline import SketchPipeline
from tessera.sketch.preprocessor import SketchPreprocessor
from tessera.sketch.symmetry import SymmetryEnforcer
from tessera.sketch.synthesizer import SketchSynthesizer
from tessera.sketch.types import (
    PreprocessedSketch,
    SketchConfig,
    SketchDetectionResult,
    SketchPipelineResult,
    SymmetryConfig,
    SynthesizedImage,
)

__all__ = [
    "SketchPipeline",
    "SketchDetector",
    "SketchPreprocessor",
    "SketchSynthesizer",
    "SymmetryEnforcer",
    "SketchConfig",
    "SymmetryConfig",
    "SketchDetectionResult",
    "PreprocessedSketch",
    "SynthesizedImage",
    "SketchPipelineResult",
]
