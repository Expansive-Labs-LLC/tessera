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

"""Performance report dataclasses.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-011.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class PerfStageResult:
    """Timing and memory data for a single pipeline stage.

    Attributes:
        stage_name: Name of the pipeline stage.
        duration_seconds: Wall-clock duration in seconds.
        peak_memory_mb: Peak CPU memory usage in MB (via tracemalloc).
            Set to ``-1.0`` if tracemalloc is unavailable.

    Implements: FR-010.
    """

    stage_name: str
    duration_seconds: float
    peak_memory_mb: float


@dataclass
class PerfReport:
    """Complete performance report for a pipeline execution.

    Attributes:
        stages: Per-stage timing and memory results.
        total_duration_seconds: Total wall-clock duration.
        peak_gpu_memory_mb: Peak GPU memory via
            ``torch.cuda.max_memory_allocated()``.
        peak_cpu_memory_mb: Peak CPU memory via tracemalloc.
            Set to ``-1.0`` if tracemalloc is unavailable.

    Implements: FR-011.
    """

    stages: list[PerfStageResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    peak_gpu_memory_mb: float = 0.0
    peak_cpu_memory_mb: float = 0.0

    def to_json(self) -> str:
        """Serialize the report to a JSON string.

        Returns:
            JSON string representation of the report.

        Implements: FR-011.
        """
        return json.dumps(asdict(self), indent=2)

    def add_stage(self, result: PerfStageResult) -> None:
        """Add a stage result to the report.

        Args:
            result: The ``PerfStageResult`` to add.
        """
        self.stages.append(result)

    def get_bottleneck_stages(self, top_n: int = 3) -> list[PerfStageResult]:
        """Return the top N slowest stages.

        Args:
            top_n: Number of stages to return.

        Returns:
            List of ``PerfStageResult`` sorted by duration descending.

        Implements: FR-016.
        """
        return sorted(
            self.stages,
            key=lambda s: s.duration_seconds,
            reverse=True,
        )[:top_n]
