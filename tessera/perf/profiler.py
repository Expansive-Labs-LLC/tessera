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

"""Performance profiler with per-stage timing and memory tracking.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-010, FR-011, FR-016, EC-004.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from .report import PerfReport, PerfStageResult

logger = logging.getLogger("tessera.perf")

# EC-004: Check tracemalloc availability.
_tracemalloc_available = True
try:
    import tracemalloc as _tracemalloc
except ImportError:
    _tracemalloc_available = False
    _tracemalloc = None  # type: ignore[assignment]
    logger.info(
        "tracemalloc not available. CPU memory tracking disabled."
    )


class PerformanceProfiler:
    """Instruments pipeline stages with timing and memory tracking.

    Usage::

        profiler = PerformanceProfiler()

        with profiler.stage("vision"):
            vision_pipeline.execute(image)

        with profiler.stage("reconstruction"):
            mesh = reconstruction_adapter.generate(vision_result)

        report = profiler.report()
        print(report.to_json())

    Implements: FR-010, FR-011, FR-016, EC-004.
    """

    def __init__(self) -> None:
        self._stages: list[PerfStageResult] = []
        self._start_time: float = 0.0
        self._started = False

    def reset(self) -> None:
        """Reset the profiler for a new pipeline run."""
        self._stages.clear()
        self._start_time = 0.0
        self._started = False

    @contextmanager
    def stage(self, stage_name: str) -> Generator[None, None, None]:
        """Context manager to time a single pipeline stage.

        Records duration and peak CPU memory for the stage.

        Args:
            stage_name: Human-readable stage name.

        Yields:
            None — the timed block executes between enter and exit.

        Implements: FR-010.
        """
        if not self._started:
            self._start_time = time.perf_counter()
            self._started = True

        logger.debug("Pipeline stage started: stage_name=%s", stage_name)

        # Start memory tracking if available (EC-004).
        peak_memory_mb = -1.0
        if _tracemalloc_available and _tracemalloc is not None:
            if not _tracemalloc.is_tracing():
                _tracemalloc.start()
            _tracemalloc.reset_peak()

        start = time.perf_counter()

        try:
            yield
        finally:
            duration = time.perf_counter() - start

            # Read peak memory (EC-004: -1.0 if unavailable).
            if _tracemalloc_available and _tracemalloc is not None:
                try:
                    _, peak = _tracemalloc.get_traced_memory()
                    peak_memory_mb = peak / (1024 * 1024)
                except Exception:
                    peak_memory_mb = -1.0
            else:
                peak_memory_mb = -1.0

            result = PerfStageResult(
                stage_name=stage_name,
                duration_seconds=round(duration, 4),
                peak_memory_mb=round(peak_memory_mb, 2),
            )
            self._stages.append(result)

            logger.info(
                "Pipeline stage completed: stage_name=%s, "
                "duration_seconds=%.3f, peak_memory_mb=%.1f",
                stage_name,
                duration,
                peak_memory_mb,
            )

    def report(self) -> PerfReport:
        """Generate a complete performance report.

        Includes per-stage timing, total duration, and GPU/CPU
        peak memory.

        Returns:
            ``PerfReport`` with all recorded stage data.

        Implements: FR-011, FR-016.
        """
        total_duration = sum(s.duration_seconds for s in self._stages)

        # Get peak GPU memory if torch is available.
        peak_gpu_mb = 0.0
        try:
            import torch

            if torch.cuda.is_available():
                peak_gpu_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        except ImportError:
            pass
        except Exception:
            pass

        # Get peak CPU memory.
        peak_cpu_mb = -1.0
        if _tracemalloc_available and _tracemalloc is not None:
            try:
                _, peak = _tracemalloc.get_traced_memory()
                peak_cpu_mb = peak / (1024 * 1024)
            except Exception:
                peak_cpu_mb = -1.0

        perf_report = PerfReport(
            stages=list(self._stages),
            total_duration_seconds=round(total_duration, 4),
            peak_gpu_memory_mb=round(peak_gpu_mb, 2),
            peak_cpu_memory_mb=round(peak_cpu_mb, 2),
        )

        logger.info(
            "Performance report generated: total_duration_seconds=%.2f, "
            "stage_count=%d",
            total_duration,
            len(self._stages),
        )

        # FR-016 (SHOULD): Log bottleneck recommendations.
        self._log_bottleneck_recommendations(perf_report)

        return perf_report

    def _log_bottleneck_recommendations(
        self, report: PerfReport
    ) -> None:
        """Log recommendations for the top 3 slowest stages.

        Implements: FR-016.
        """
        if not report.stages or report.total_duration_seconds == 0:
            return

        bottlenecks = report.get_bottleneck_stages(top_n=3)
        for stage in bottlenecks:
            pct = (
                stage.duration_seconds / report.total_duration_seconds * 100
            )
            if pct > 50:
                recommendation = self._get_recommendation(stage.stage_name)
                logger.info(
                    "Bottleneck recommendation: %s took %.1fs (%.0f%% of "
                    "total). %s",
                    stage.stage_name,
                    stage.duration_seconds,
                    pct,
                    recommendation,
                )

    @staticmethod
    def _get_recommendation(stage_name: str) -> str:
        """Get a performance recommendation for a stage.

        Args:
            stage_name: The pipeline stage name.

        Returns:
            Recommendation string.
        """
        recommendations = {
            "reconstruction": (
                "Consider using InstantMesh adapter for faster results."
            ),
            "vision": (
                "Consider reducing input image resolution or using "
                "a lighter segmentation model."
            ),
            "cleanup": (
                "Consider disabling optional cleanup steps (quad remesh, "
                "decimation) for faster processing."
            ),
            "validation": (
                "Consider reducing wall-thickness sampling density "
                "for faster validation."
            ),
            "export": (
                "Consider exporting to fewer formats to speed up the "
                "export stage."
            ),
        }
        return recommendations.get(
            stage_name,
            "Review this stage for optimization opportunities.",
        )
