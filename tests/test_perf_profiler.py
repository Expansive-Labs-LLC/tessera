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

"""Tests for the performance profiler.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Covers: TS-003, TS-013, TS-016, TS-024, TS-025.

All ``bpy`` dependencies are mocked via conftest.py fixtures.
Imports from ``tessera.*`` are deferred to test body.
"""

from __future__ import annotations

import json
import time

import pytest


# -------------------------------------------------------------------
# TS-003: PerformanceProfiler stage() timing
# -------------------------------------------------------------------
class TestPerformanceProfiler:
    """Test PerformanceProfiler timing accuracy."""

    def test_stage_records_duration(self) -> None:
        """stage() records a non-zero duration."""
        from tessera.perf.profiler import PerformanceProfiler

        profiler = PerformanceProfiler()
        with profiler.stage("test_stage"):
            time.sleep(0.01)
        report = profiler.report()
        assert len(report.stages) == 1
        assert report.stages[0].duration_seconds > 0

    def test_stage_records_stage_name(self) -> None:
        """stage() records the correct stage name."""
        from tessera.perf.profiler import PerformanceProfiler

        profiler = PerformanceProfiler()
        with profiler.stage("vision"):
            pass
        report = profiler.report()
        assert report.stages[0].stage_name == "vision"

    def test_multiple_stages_accumulate(self) -> None:
        """Multiple stage() calls are all recorded."""
        from tessera.perf.profiler import PerformanceProfiler

        profiler = PerformanceProfiler()
        for name in ["vision", "reconstruction", "cleanup"]:
            with profiler.stage(name):
                time.sleep(0.001)
        report = profiler.report()
        assert len(report.stages) == 3

    def test_total_duration_is_sum_of_stages(self) -> None:
        """total_duration_seconds ≈ sum of stage durations."""
        from tessera.perf.profiler import PerformanceProfiler

        profiler = PerformanceProfiler()
        with profiler.stage("a"):
            time.sleep(0.01)
        with profiler.stage("b"):
            time.sleep(0.01)
        report = profiler.report()
        stage_sum = sum(s.duration_seconds for s in report.stages)
        assert abs(report.total_duration_seconds - stage_sum) < 0.01

    def test_reset_clears_stages(self) -> None:
        """reset() clears all recorded stages."""
        from tessera.perf.profiler import PerformanceProfiler

        profiler = PerformanceProfiler()
        with profiler.stage("test"):
            pass
        profiler.reset()
        report = profiler.report()
        assert len(report.stages) == 0


# -------------------------------------------------------------------
# TS-013: Profiler memory tracking (EC-004 fallback)
# -------------------------------------------------------------------
class TestMemoryTracking:
    """Test memory tracking with tracemalloc."""

    def test_peak_memory_is_recorded(self) -> None:
        """peak_memory_mb is non-negative (or -1 if unavailable)."""
        from tessera.perf.profiler import PerformanceProfiler

        profiler = PerformanceProfiler()
        with profiler.stage("test"):
            _ = [0] * 10000
        report = profiler.report()
        assert report.stages[0].peak_memory_mb >= -1.0


# -------------------------------------------------------------------
# TS-016: PerfReport JSON serialization
# -------------------------------------------------------------------
class TestPerfReport:
    """Test PerfReport serialization and utilities."""

    def test_to_json_is_valid_json(self) -> None:
        """to_json() produces valid JSON."""
        from tessera.perf.report import PerfReport, PerfStageResult

        report = PerfReport(
            stages=[
                PerfStageResult("vision", 1.5, 100.0),
                PerfStageResult("reconstruction", 3.0, 200.0),
            ],
            total_duration_seconds=4.5,
        )
        data = json.loads(report.to_json())
        assert data["total_duration_seconds"] == 4.5
        assert len(data["stages"]) == 2

    def test_get_bottleneck_stages(self) -> None:
        """get_bottleneck_stages() returns stages sorted by duration."""
        from tessera.perf.report import PerfReport, PerfStageResult

        report = PerfReport(
            stages=[
                PerfStageResult("fast", 1.0, 0.0),
                PerfStageResult("slow", 10.0, 0.0),
                PerfStageResult("medium", 5.0, 0.0),
            ]
        )
        bottlenecks = report.get_bottleneck_stages(top_n=2)
        assert len(bottlenecks) == 2
        assert bottlenecks[0].stage_name == "slow"
        assert bottlenecks[1].stage_name == "medium"

    def test_add_stage(self) -> None:
        """add_stage() appends a new stage result."""
        from tessera.perf.report import PerfReport, PerfStageResult

        report = PerfReport()
        report.add_stage(PerfStageResult("test", 1.0, 0.0))
        assert len(report.stages) == 1


# -------------------------------------------------------------------
# TS-024 / TS-025: ModelCache LRU eviction
# -------------------------------------------------------------------
class TestModelCache:
    """Test ModelCache LRU eviction and lazy loading."""

    def test_get_or_load_caches_model(self) -> None:
        """get_or_load() caches and returns the model."""
        from tessera.perf.optimizer import ModelCache

        cache = ModelCache(max_size=3)
        model = cache.get_or_load("sam2", lambda: "sam2_model")
        assert model == "sam2_model"
        assert cache.size == 1

    def test_cache_hit_returns_same_object(self) -> None:
        """Second call returns cached model without reloading."""
        from tessera.perf.optimizer import ModelCache

        load_count = 0

        def loader():
            nonlocal load_count
            load_count += 1
            return "model"

        cache = ModelCache(max_size=3)
        cache.get_or_load("m1", loader)
        cache.get_or_load("m1", loader)
        assert load_count == 1

    def test_eviction_when_full(self) -> None:
        """LRU model is evicted when cache is full."""
        from tessera.perf.optimizer import ModelCache

        cache = ModelCache(max_size=2)
        cache.get_or_load("m1", lambda: "model1")
        cache.get_or_load("m2", lambda: "model2")
        cache.get_or_load("m3", lambda: "model3")
        assert cache.get("m1") is None
        assert cache.size == 2

    def test_active_model_not_evicted(self) -> None:
        """Active model is never evicted."""
        from tessera.perf.optimizer import ModelCache

        cache = ModelCache(max_size=2)
        cache.get_or_load("m1", lambda: "model1")
        cache.mark_active("m1")
        cache.get_or_load("m2", lambda: "model2")
        cache.get_or_load("m3", lambda: "model3")
        assert cache.get("m1") is not None
        assert cache.get("m2") is None

    def test_all_active_raises_error(self) -> None:
        """RuntimeError when cache is full and all models are active."""
        from tessera.perf.optimizer import ModelCache

        cache = ModelCache(max_size=2)
        cache.get_or_load("m1", lambda: "model1")
        cache.get_or_load("m2", lambda: "model2")
        cache.mark_active("m1")
        cache.mark_active("m2")
        with pytest.raises(RuntimeError, match="all.*active"):
            cache.get_or_load("m3", lambda: "model3")

    def test_explicit_evict(self) -> None:
        """evict() removes a specific model."""
        from tessera.perf.optimizer import ModelCache

        cache = ModelCache(max_size=3)
        cache.get_or_load("m1", lambda: "model1")
        assert cache.evict("m1")
        assert cache.size == 0

    def test_clear_removes_all(self) -> None:
        """clear() removes all models."""
        from tessera.perf.optimizer import ModelCache

        cache = ModelCache(max_size=3)
        cache.get_or_load("m1", lambda: "model1")
        cache.get_or_load("m2", lambda: "model2")
        cache.clear()
        assert cache.size == 0
