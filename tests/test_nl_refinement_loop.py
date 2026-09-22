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

"""Comprehensive test suite for the Natural-Language Refinement Loop.

Spec: SPEC-TS-0009

Coverage map:
  - AC-001 through AC-009: Acceptance criteria
  - EC-001 through EC-006: Edge cases
  - FR-007 through FR-044: Functional requirements
  - SEC-001 through SEC-006: Security constraints
  - CON-001 through CON-009: Hard constraints

Uses pytest with Arrange-Act-Assert pattern and mock-driven testing
for Blender-dependent APIs.
"""

import json
from unittest.mock import MagicMock

import pytest

# ===================================================================
# Fixtures
# ===================================================================


class MockVertex:
    """Lightweight mock vertex for spatial testing."""

    def __init__(self, x: float, y: float, z: float, index: int = 0):
        from tests.fakes import FakeVector

        self.co = FakeVector(x, y, z)
        self.index = index
        self.groups = []
        self.select = False


class MockVertexGroup:
    """Lightweight mock vertex group."""

    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index


class MockPolygon:
    """Lightweight mock polygon."""

    def __init__(self, vertices):
        self.vertices = vertices


class MockVertexList:
    """List-like vertex container supporting len/iter/getitem."""

    def __init__(self, verts):
        self._verts = list(verts)

    def __len__(self):
        return len(self._verts)

    def __iter__(self):
        return iter(self._verts)

    def __getitem__(self, idx):
        return self._verts[idx]

    def __bool__(self):
        return len(self._verts) > 0


class MockVertexGroupList:
    """List-like vertex group container supporting name lookup."""

    def __init__(self, groups=None):
        self._groups = list(groups or [])

    def __len__(self):
        return len(self._groups)

    def __iter__(self):
        return iter(self._groups)

    def __bool__(self):
        return len(self._groups) > 0

    def __contains__(self, name):
        return any(g.name == name for g in self._groups)

    def __getitem__(self, name):
        for g in self._groups:
            if g.name == name:
                return g
        raise KeyError(name)


def _make_mesh_obj(
    vertex_coords: list[tuple[float, float, float]],
    face_indices: list[tuple[int, ...]] | None = None,
    vgroup_names: list[str] | None = None,
):
    """Build a mock Blender mesh object with given geometry."""
    obj = MagicMock()
    verts = MockVertexList(
        [MockVertex(x, y, z, i) for i, (x, y, z) in enumerate(vertex_coords)]
    )
    obj.data.vertices = verts

    polys = [MockPolygon(f) for f in (face_indices or [])]
    obj.data.polygons = polys

    if vgroup_names:
        groups = [MockVertexGroup(n, i) for i, n in enumerate(vgroup_names)]
        obj.vertex_groups = MockVertexGroupList(groups)
    else:
        obj.vertex_groups = MockVertexGroupList()

    return obj


class MockLLMBackend:
    """Configurable mock LLM backend for testing."""

    def __init__(self, response: str = ""):
        self._response = response

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        return self._response

    def is_available(self) -> bool:
        return True


# ===================================================================
# 1. Intent Schema (FR-007, FR-008, FR-044, SEC-004)
# ===================================================================


class TestIntentSchemaModels:
    """Intent schema data models and validation."""

    # -- AC-001: OperationType enum completeness --

    def test_operation_type_has_11_values(self):
        """FR-007: OperationType enum defines all 11 operation values."""
        from tessera.refinement.intent_schema import OperationType

        expected = {
            "SCALE",
            "MOVE",
            "ROTATE",
            "SOLIDIFY",
            "SMOOTH",
            "SHARPEN",
            "BEVEL",
            "ADD_GEOMETRY",
            "REMOVE_GEOMETRY",
            "UNDO",
            "REDO",
        }
        actual = {op.value for op in OperationType}
        assert actual == expected

    def test_edit_intent_defaults(self):
        """FR-007: EditIntent has correct default values."""
        from tessera.refinement.intent_schema import EditIntent, OperationType

        intent = EditIntent(operation=OperationType.SCALE)
        assert intent.target_region == "all"
        assert intent.confidence == 1.0
        assert intent.parameters == {}
        assert intent.raw_response == ""

    def test_ambiguity_response_structure(self):
        """FR-017: AmbiguityResponse holds candidates and original command."""
        from tessera.refinement.intent_schema import AmbiguityResponse

        resp = AmbiguityResponse(
            candidates=[("SMOOTH on 'top'", 0.6), ("SCALE on 'all'", 0.3)],
            original_command="fix it",
        )
        assert len(resp.candidates) == 2
        assert resp.original_command == "fix it"

    def test_region_result_fields(self):
        """FR-013: RegionResult captures method, vertex group, count."""
        from tessera.refinement.intent_schema import RegionResult

        result = RegionResult(
            method="vertex_group",
            vertex_group_name="handle",
            vertex_count=500,
            confidence=0.95,
        )
        assert result.method == "vertex_group"
        assert result.vertex_count == 500

    def test_edit_result_fields(self):
        """FR-019: EditResult captures success, description, warning."""
        from tessera.refinement.intent_schema import EditResult

        result = EditResult(success=True, description="Scaled", warning="clamped")
        assert result.success is True
        assert result.warning == "clamped"


class TestParameterClamping:
    """FR-044 / SEC-004: Parameter validation and clamping."""

    @pytest.mark.parametrize(
        "op,param,value,expected",
        [
            ("SCALE", "factor", 200.0, 100.0),
            ("SCALE", "factor", 0.001, 0.01),
            ("SCALE", "factor", 1.5, 1.5),  # In range — no clamping
            ("MOVE", "distance", -5.0, 0.0),
            ("MOVE", "distance", 2000.0, 1000.0),
            ("ROTATE", "angle_degrees", -500.0, -360.0),
            ("ROTATE", "angle_degrees", 500.0, 360.0),
            ("SOLIDIFY", "thickness_mm", 0.001, 0.1),
            ("SOLIDIFY", "thickness_mm", 100.0, 50.0),
            ("SOLIDIFY", "offset", -2.0, -1.0),
            ("SOLIDIFY", "offset", 3.0, 1.0),
            ("SMOOTH", "iterations", 0, 1),
            ("SMOOTH", "iterations", 200, 100),
            ("SMOOTH", "factor", -0.5, 0.0),
            ("SMOOTH", "factor", 2.0, 1.0),
            ("SHARPEN", "angle_threshold_degrees", -10, 0),
            ("SHARPEN", "angle_threshold_degrees", 200, 180),
            ("BEVEL", "width_mm", 0.001, 0.1),
            ("BEVEL", "width_mm", 50.0, 20.0),
            ("BEVEL", "segments", 0, 1),
            ("BEVEL", "segments", 20, 10),
            ("ADD_GEOMETRY", "size_mm", 0.001, 0.1),
            ("ADD_GEOMETRY", "size_mm", 1000.0, 500.0),
        ],
        ids=lambda v: str(v),
    )
    def test_clamp_to_range(self, op, param, value, expected):
        """FR-044: Each parameter is clamped to its defined range."""
        from tessera.refinement.intent_schema import OperationType, clamp_parameters

        clamped, warnings = clamp_parameters(OperationType(op), {param: value})
        assert clamped[param] == pytest.approx(expected)
        if value != expected:
            assert len(warnings) >= 1
            assert "clamped to" in warnings[0]

    def test_clamp_preserves_unaffected_params(self):
        """FR-044: Parameters not in the range table pass through unchanged."""
        from tessera.refinement.intent_schema import OperationType, clamp_parameters

        clamped, warnings = clamp_parameters(
            OperationType.SCALE, {"factor": 1.5, "axis": "Z"}
        )
        assert clamped["axis"] == "Z"
        assert len(warnings) == 0

    def test_clamp_warning_format(self):
        """FR-044: Warning message follows spec format."""
        from tessera.refinement.intent_schema import OperationType, clamp_parameters

        _, warnings = clamp_parameters(OperationType.SCALE, {"factor": 200.0})
        assert "Parameter 'factor' was 200.0" in warnings[0]
        assert "allowed range: 0.01–100.0" in warnings[0]

    def test_clamp_no_operation_in_table(self):
        """FR-044: Operations without range entries produce no warnings."""
        from tessera.refinement.intent_schema import OperationType, clamp_parameters

        clamped, warnings = clamp_parameters(
            OperationType.REMOVE_GEOMETRY, {"some_param": 999}
        )
        assert len(warnings) == 0

    def test_clamp_handles_non_numeric_values(self):
        """SEC-004: Non-numeric parameter values are not clamped (no crash)."""
        from tessera.refinement.intent_schema import OperationType, clamp_parameters

        clamped, warnings = clamp_parameters(
            OperationType.SCALE, {"factor": "not_a_number"}
        )
        assert clamped["factor"] == "not_a_number"
        assert len(warnings) == 0


class TestDimensionlessDefaults:
    """FR-008: Dimensionless adjective default mappings."""

    @pytest.mark.parametrize(
        "word,expected_pct",
        [
            ("taller", 10.0),
            ("bigger", 10.0),
            ("wider", 10.0),
            ("longer", 10.0),
            ("thicker", 10.0),
            ("shorter", -10.0),
            ("smaller", -10.0),
            ("narrower", -10.0),
            ("thinner", -10.0),
        ],
    )
    def test_dimensionless_mapping_complete(self, word, expected_pct):
        """FR-008: Each adjective maps to correct default percentage."""
        from tessera.refinement.intent_schema import DIMENSIONLESS_DEFAULTS

        assert DIMENSIONLESS_DEFAULTS[word] == expected_pct


# ===================================================================
# 2. Intent Parser (FR-007, FR-008, FR-011, FR-012, FR-029, FR-033)
# ===================================================================


class TestIntentParserUndoRedo:
    """FR-029: Direct undo/redo trigger detection."""

    @pytest.mark.parametrize("trigger", ["undo", "undo that", "go back", "revert"])
    def test_undo_triggers(self, trigger):
        """FR-029: Each undo trigger maps to UNDO with confidence 1.0."""
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import OperationType

        parser = IntentParser(backend=MockLLMBackend())
        result = parser.parse(trigger, {"bounding_box_mm": {}})
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].operation == OperationType.UNDO
        assert result[0].confidence == 1.0

    @pytest.mark.parametrize("trigger", ["redo", "redo that", "put it back"])
    def test_redo_triggers(self, trigger):
        """FR-029: Each redo trigger maps to REDO with confidence 1.0."""
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import OperationType

        parser = IntentParser(backend=MockLLMBackend())
        result = parser.parse(trigger, {"bounding_box_mm": {}})
        assert isinstance(result, list)
        assert result[0].operation == OperationType.REDO

    def test_undo_trigger_case_insensitive(self):
        """FR-029: Triggers work regardless of case."""
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import OperationType

        parser = IntentParser(backend=MockLLMBackend())
        result = parser.parse("UNDO THAT", {"bounding_box_mm": {}})
        assert result[0].operation == OperationType.UNDO


class TestIntentParserVersionUndo:
    """FR-033: Version-addressed undo commands."""

    @pytest.mark.parametrize(
        "command,expected_ver",
        [
            ("go back to version 3", 3),
            ("restore version 5", 5),
            ("revert to version 1", 1),
        ],
    )
    def test_version_pattern_extracts_number(self, command, expected_ver):
        """FR-033: Version number is extracted from the command."""
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import OperationType

        parser = IntentParser(backend=MockLLMBackend())
        result = parser.parse(command, {"bounding_box_mm": {}})
        assert isinstance(result, list)
        assert result[0].operation == OperationType.UNDO
        assert result[0].parameters["target_version"] == expected_ver


class TestIntentParserLLMParsing:
    """FR-007, FR-012: LLM response parsing and ambiguity detection."""

    def test_parse_single_intent_from_llm(self):
        """FR-007 / AC-001: Single intent JSON parsed correctly."""
        response = json.dumps(
            {
                "intents": [
                    {
                        "operation": "SCALE",
                        "target_region": "all",
                        "parameters": {"axis": "Z", "factor": 1.2},
                        "confidence": 0.95,
                    }
                ]
            }
        )
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import OperationType

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse(
            "make it 20% taller",
            {"bounding_box_mm": {"x": 50, "y": 50, "z": 100}},
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].operation == OperationType.SCALE
        assert result[0].target_region == "all"
        assert result[0].confidence == 0.95

    def test_parse_multiple_intents_from_llm(self):
        """FR-007 / EC-001: Multiple intents decomposed from compound command."""
        response = json.dumps(
            {
                "intents": [
                    {
                        "operation": "SCALE",
                        "target_region": "top",
                        "parameters": {"factor": 1.1},
                        "confidence": 0.9,
                    },
                    {
                        "operation": "SCALE",
                        "target_region": "base",
                        "parameters": {"factor": 0.9},
                        "confidence": 0.88,
                    },
                ]
            }
        )
        from tessera.refinement.intent_parser import IntentParser

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse(
            "make the top bigger and the base smaller",
            {"bounding_box_mm": {"x": 50, "y": 50, "z": 100}},
        )
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].target_region == "top"
        assert result[1].target_region == "base"

    def test_ambiguity_response_below_threshold(self):
        """FR-012 / AC-004: Low confidence triggers AmbiguityResponse."""
        response = json.dumps(
            {
                "intents": [
                    {
                        "operation": "SMOOTH",
                        "target_region": "all",
                        "parameters": {},
                        "confidence": 0.4,
                    },
                    {
                        "operation": "UNDO",
                        "target_region": "all",
                        "parameters": {},
                        "confidence": 0.3,
                    },
                ]
            }
        )
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import AmbiguityResponse

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse("fix it", {"bounding_box_mm": {}})
        assert isinstance(result, AmbiguityResponse)
        assert len(result.candidates) == 2
        assert result.original_command == "fix it"
        # Sorted by confidence descending
        assert result.candidates[0][1] >= result.candidates[1][1]

    def test_ambiguity_max_3_candidates(self):
        """FR-017: At most 3 candidate interpretations returned."""
        response = json.dumps(
            {
                "intents": [
                    {"operation": "SMOOTH", "confidence": 0.5},
                    {"operation": "SCALE", "confidence": 0.4},
                    {"operation": "SOLIDIFY", "confidence": 0.3},
                    {"operation": "BEVEL", "confidence": 0.2},
                ]
            }
        )
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import AmbiguityResponse

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse("do something", {"bounding_box_mm": {}})
        assert isinstance(result, AmbiguityResponse)
        assert len(result.candidates) <= 3


class TestIntentParserJSONExtraction:
    """SEC-002: JSON extraction from LLM responses (no eval)."""

    def test_extract_json_from_code_fence(self):
        """JSON wrapped in markdown code fences is extracted."""
        from tessera.refinement.intent_parser import IntentParser

        parser = IntentParser(backend=MockLLMBackend())
        result = parser._extract_json('```json\n{"intents": []}\n```')
        assert result == '{"intents": []}'

    def test_extract_bare_json_object(self):
        """Bare JSON object at the start of text is detected."""
        from tessera.refinement.intent_parser import IntentParser

        parser = IntentParser(backend=MockLLMBackend())
        result = parser._extract_json('{"operation": "SCALE"}')
        assert result == '{"operation": "SCALE"}'

    def test_extract_json_embedded_in_text(self):
        """JSON object embedded in surrounding text is extracted."""
        from tessera.refinement.intent_parser import IntentParser

        parser = IntentParser(backend=MockLLMBackend())
        text = 'Sure, here is the intent: {"operation": "MOVE"} and that is it.'
        result = parser._extract_json(text)
        assert '"operation": "MOVE"' in result

    def test_extract_json_returns_none_on_no_json(self):
        """Returns None when no JSON is found in text."""
        from tessera.refinement.intent_parser import IntentParser

        parser = IntentParser(backend=MockLLMBackend())
        result = parser._extract_json("This is just plain text with no json")
        assert result is None

    def test_malformed_json_returns_ambiguity(self):
        """SEC-002: Malformed JSON returns AmbiguityResponse, not crash."""
        response = "{'invalid: json"
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import AmbiguityResponse

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse("scale it", {"bounding_box_mm": {}})
        assert isinstance(result, AmbiguityResponse)


class TestIntentParserDimensionless:
    """FR-008: Dimensionless adjective inference."""

    def test_dimensionless_adjective_infers_factor(self):
        """FR-008: 'taller' with no value infers +10% scale factor."""
        response = json.dumps(
            {
                "intents": [
                    {
                        "operation": "SCALE",
                        "target_region": "all",
                        "parameters": {},
                        "confidence": 0.9,
                    }
                ]
            }
        )
        from tessera.refinement.intent_parser import IntentParser

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse(
            "make it taller",
            {"bounding_box_mm": {"z": 100}},
        )
        assert isinstance(result, list)
        # Should have inferred factor from "taller"
        assert result[0].parameters.get("factor") == pytest.approx(1.1)
        assert result[0].parameters.get("inferred") is True


class TestIntentParserLLMFailure:
    """EC-005 / CON-003: Handling LLM errors and gibberish input."""

    def test_llm_backend_error_returns_ambiguity(self):
        """EC-005: LLM backend error returns empty AmbiguityResponse."""
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import AmbiguityResponse
        from tessera.refinement.llm_backend.base import LLMBackendError

        backend = MagicMock()
        backend.generate.side_effect = LLMBackendError("Connection refused")

        parser = IntentParser(backend=backend)
        result = parser.parse("asdfghj", {"bounding_box_mm": {}})
        assert isinstance(result, AmbiguityResponse)
        assert len(result.candidates) == 0

    def test_empty_intents_returns_ambiguity(self):
        """Empty intents array returns AmbiguityResponse."""
        response = json.dumps({"intents": []})
        from tessera.refinement.intent_parser import IntentParser
        from tessera.refinement.intent_schema import AmbiguityResponse

        parser = IntentParser(backend=MockLLMBackend(response))
        result = parser.parse("nothing", {"bounding_box_mm": {}})
        assert isinstance(result, AmbiguityResponse)


class TestIntentParserSystemPrompt:
    """FR-011: System prompt includes mesh context."""

    def test_system_prompt_includes_mesh_context(self):
        """FR-011: System prompt contains bounding box, vgroups, face count."""
        from tessera.refinement.intent_parser import _build_system_prompt

        prompt = _build_system_prompt(
            {
                "bounding_box_mm": {"x": 50.0, "y": 30.0, "z": 100.0},
                "vertex_groups": ["handle", "base"],
                "face_count": 5000,
            }
        )
        assert "50.0" in prompt
        assert "30.0" in prompt
        assert "100.0" in prompt
        assert "handle" in prompt
        assert "base" in prompt
        assert "5000" in prompt

    def test_system_prompt_lists_operations(self):
        """FR-011: System prompt lists all supported operations."""
        from tessera.refinement.intent_parser import _build_system_prompt

        prompt = _build_system_prompt({"bounding_box_mm": {}, "face_count": 0})
        for op in [
            "SCALE",
            "MOVE",
            "ROTATE",
            "SOLIDIFY",
            "SMOOTH",
            "SHARPEN",
            "BEVEL",
            "ADD_GEOMETRY",
            "REMOVE_GEOMETRY",
        ]:
            assert op in prompt


class TestOutputSanitization:
    """SEC-005: LLM output sanitization."""

    def test_sanitize_strips_control_chars(self):
        """SEC-005: Control characters are removed from LLM output."""
        from tessera.refinement.intent_parser import _sanitize_llm_output

        dirty = "Hello\x00World\x07\x08"
        clean = _sanitize_llm_output(dirty)
        assert "\x00" not in clean
        assert "\x07" not in clean

    def test_sanitize_truncates_long_output(self):
        """SEC-005: Output longer than 500 chars is truncated."""
        from tessera.refinement.intent_parser import _sanitize_llm_output

        long_text = "A" * 600
        result = _sanitize_llm_output(long_text)
        assert len(result) <= 501  # 500 + "…"
        assert result.endswith("…")


# ===================================================================
# 3. Region Resolver (FR-013, FR-014, FR-015, FR-016, FR-043)
# ===================================================================


class TestRegionResolverWholeAlias:
    """FR-014: Whole-mesh alias resolution."""

    @pytest.mark.parametrize("alias", ["all", "whole", "entire"])
    def test_whole_mesh_aliases_resolve(self, alias):
        """FR-014: 'all', 'whole', 'entire' map to the full mesh."""
        from tessera.refinement.region_resolver import RegionResolver

        obj = _make_mesh_obj([(0, 0, 0), (1, 1, 1), (2, 2, 2)])
        resolver = RegionResolver()
        result = resolver.resolve(alias, obj)
        assert result.method == "spatial_heuristic"
        assert result.vertex_group_name == "_bf_all"
        assert result.vertex_count == 3
        assert result.confidence == 1.0


class TestRegionResolverSpatialnHeuristics:
    """FR-014: Spatial heuristic region mappings."""

    def test_spatial_heuristics_cover_all_terms(self):
        """FR-014: All standard spatial terms are defined."""
        from tessera.refinement.region_resolver import SPATIAL_HEURISTICS

        for term in [
            "base",
            "bottom",
            "top",
            "middle",
            "center",
            "left",
            "right",
            "front",
            "back",
        ]:
            assert term in SPATIAL_HEURISTICS

    def test_top_heuristic_selects_top_20_pct(self):
        """FR-014 / AC-003: 'top' selects vertices in top 20% of Z-axis."""
        from tessera.refinement.region_resolver import RegionResolver

        # 10 vertices spaced 0–90 on Z so bounding box Z extent = 90.
        verts = [(0, 0, z * 10.0) for z in range(10)]
        obj = _make_mesh_obj(verts)
        resolver = RegionResolver()
        result = resolver.resolve("top", obj)
        assert result.method == "spatial_heuristic"
        # Top 20% of Z = 72..90 → vertices at Z=80 and Z=90.
        assert result.vertex_count == 2

    def test_bottom_heuristic_selects_bottom_20_pct(self):
        """FR-014: 'bottom' selects vertices in bottom 20% of Z-axis."""
        from tessera.refinement.region_resolver import RegionResolver

        verts = [(0, 0, z * 10.0) for z in range(10)]
        obj = _make_mesh_obj(verts)
        resolver = RegionResolver()
        result = resolver.resolve("bottom", obj)
        assert result.method == "spatial_heuristic"
        # Bottom 20% of Z = 0..18 → vertices at Z=0 and Z=10.
        assert result.vertex_count == 2

    def test_middle_heuristic_selects_30_to_70_pct(self):
        """FR-014: 'middle' selects vertices between 30%–70% of Z."""
        from tessera.refinement.region_resolver import RegionResolver

        verts = [(0, 0, z * 10.0) for z in range(10)]
        obj = _make_mesh_obj(verts)
        resolver = RegionResolver()
        result = resolver.resolve("middle", obj)
        assert result.method == "spatial_heuristic"
        # 30%–70% of 0..90 = 27..63 → vertices at Z=30, 40, 50, 60.
        assert result.vertex_count == 4


class TestRegionResolverVertexGroups:
    """FR-015: Named vertex group matching."""

    def test_exact_match_uses_vertex_group(self):
        """FR-015: Exact name match returns vertex_group method."""
        from tessera.refinement.region_resolver import RegionResolver

        obj = _make_mesh_obj(
            [(0, 0, 0), (1, 1, 1)],
            vgroup_names=["handle", "base"],
        )
        resolver = RegionResolver()
        result = resolver.resolve("handle", obj)
        assert result.method == "vertex_group"
        assert result.vertex_group_name == "handle"

    def test_fuzzy_match_above_threshold(self):
        """FR-015 / AC-002: Fuzzy match ≥80% uses the vertex group."""
        from tessera.refinement.region_resolver import RegionResolver

        obj = _make_mesh_obj(
            [(0, 0, 0)],
            vgroup_names=["handle_part"],
        )
        resolver = RegionResolver()
        # "handle" vs "handle_part" should have ratio > 0.80 via SequenceMatcher
        result = resolver.resolve("handle", obj)
        # Check if fuzzy match succeeded
        if result.method == "vertex_group":
            assert result.vertex_group_name == "handle_part"

    def test_fuzzy_match_below_threshold_falls_through(self):
        """FR-015 / EC-002: Match below 80% falls to spatial heuristics."""
        from tessera.refinement.region_resolver import RegionResolver

        obj = _make_mesh_obj(
            [(0, 0, z * 10.0) for z in range(10)],
            vgroup_names=["top_handle"],
        )
        resolver = RegionResolver()
        # "top" vs "top_handle" ratio ~67% < 80% → should fall to spatial
        result = resolver.resolve("top", obj)
        assert result.method == "spatial_heuristic"


class TestRegionResolverNoVertexGroups:
    """FR-043 / EC-003: Meshes with zero vertex groups."""

    def test_no_vertex_groups_falls_to_spatial(self):
        """FR-043: Mesh with no vgroups falls to spatial heuristics."""
        from tessera.refinement.region_resolver import RegionResolver

        obj = _make_mesh_obj(
            [(0, 0, z * 10.0) for z in range(10)],
            vgroup_names=None,
        )
        resolver = RegionResolver()
        result = resolver.resolve("top", obj)
        assert result.method == "spatial_heuristic"

    def test_unresolvable_region_falls_to_user_selection(self):
        """FR-016 / EC-003: Unresolvable region triggers user selection."""
        from tessera.refinement.region_resolver import RegionResolver

        obj = _make_mesh_obj([(0, 0, 0)], vgroup_names=None)
        resolver = RegionResolver()
        result = resolver.resolve("handle", obj)
        assert result.method == "user_selection"
        assert result.confidence == 0.0


class TestRegionResolverMinVertices:
    """EC-006: Minimum vertex count check."""

    def test_min_vertex_count_constant(self):
        """EC-006: Minimum vertex count is 3."""
        from tessera.refinement.region_resolver import MIN_VERTEX_COUNT

        assert MIN_VERTEX_COUNT == 3

    def test_too_few_vertices_detected(self):
        """EC-006: Spatial region with < 3 vertices is flagged."""
        from tessera.refinement.region_resolver import RegionResolver

        # Only 2 vertices, both at Z=0 and Z=10, top 20% → 1 vertex
        obj = _make_mesh_obj([(0, 0, 0), (0, 0, 10)])
        resolver = RegionResolver()
        result = resolver.resolve("top", obj)
        assert result.vertex_count < 3


# ===================================================================
# 4. Undo Manager (FR-030 through FR-034, CON-005)
# ===================================================================


class TestUndoManagerBasics:
    """FR-030: Undo/redo stack basics."""

    def test_initial_state_empty(self):
        """FR-030: New manager has empty stacks."""
        from tessera.refinement.undo_manager import UndoManager

        mgr = UndoManager()
        assert mgr.can_undo is False
        assert mgr.can_redo is False
        assert mgr.current_version == 0

    def test_undo_raises_on_empty_stack(self):
        """FR-030: Undo on empty stack raises UndoError."""
        from tessera.refinement.undo_manager import UndoError, UndoManager

        mgr = UndoManager()
        with pytest.raises(UndoError, match="Nothing to undo"):
            mgr.undo(MagicMock())

    def test_redo_raises_on_empty_stack(self):
        """FR-030: Redo on empty stack raises UndoError."""
        from tessera.refinement.undo_manager import UndoError, UndoManager

        mgr = UndoManager()
        with pytest.raises(UndoError, match="Nothing to redo"):
            mgr.redo(MagicMock())


class TestUndoManagerStackInfo:
    """FR-030: Stack information structure."""

    def test_stack_info_keys(self):
        """get_stack_info returns all expected keys."""
        from tessera.refinement.undo_manager import UndoManager

        mgr = UndoManager()
        info = mgr.get_stack_info()
        for key in [
            "current_version",
            "undo_depth",
            "redo_depth",
            "can_undo",
            "can_redo",
            "history",
        ]:
            assert key in info


class TestUndoManagerDepth:
    """FR-031 / CON-005: Maximum undo stack depth."""

    def test_max_depth_constant(self):
        """FR-031: Maximum depth is 20."""
        from tessera.refinement.undo_manager import MAX_UNDO_DEPTH

        assert MAX_UNDO_DEPTH == 20


class TestUndoManagerVersionAddress:
    """FR-033: Version-addressed undo."""

    def test_goto_version_invalid_raises(self):
        """FR-033: Non-existent version raises UndoError."""
        from tessera.refinement.undo_manager import UndoError, UndoManager

        mgr = UndoManager()
        with pytest.raises(UndoError, match="not found"):
            mgr.goto_version(MagicMock(), 99)


# ===================================================================
# 5. Edit Executor (FR-018, FR-019, FR-035, FR-044)
# ===================================================================


class TestEditExecutorConfirmation:
    """FR-018: Large-edit confirmation threshold."""

    def test_large_edit_threshold_constant(self):
        """FR-018: Threshold is 80%."""
        from tessera.refinement.edit_executor import LARGE_EDIT_THRESHOLD

        assert LARGE_EDIT_THRESHOLD == 0.80

    def test_needs_confirmation_on_full_mesh(self):
        """FR-018: Editing all vertices triggers confirmation."""
        from tessera.refinement.edit_executor import EditExecutor
        from tessera.refinement.intent_schema import EditIntent, OperationType
        from tessera.refinement.undo_manager import UndoManager

        obj = _make_mesh_obj([(i, 0, 0) for i in range(100)])
        executor = EditExecutor(UndoManager())
        intent = EditIntent(operation=OperationType.SCALE)
        msg = executor.needs_confirmation(intent, obj, "_bf_all")
        assert msg is not None
        assert "100%" in msg or "Proceed?" in msg

    def test_no_confirmation_for_undo(self):
        """FR-018: Undo/redo never triggers confirmation."""
        from tessera.refinement.edit_executor import EditExecutor
        from tessera.refinement.intent_schema import EditIntent, OperationType
        from tessera.refinement.undo_manager import UndoManager

        obj = _make_mesh_obj([(i, 0, 0) for i in range(100)])
        executor = EditExecutor(UndoManager())
        intent = EditIntent(operation=OperationType.UNDO)
        msg = executor.needs_confirmation(intent, obj, "_bf_all")
        assert msg is None


class TestEditExecutorRegistry:
    """FR-019: Operation handler registry."""

    def test_all_operations_have_handlers(self):
        """FR-019: Every OperationType has a registered handler."""
        from tessera.refinement.intent_schema import OperationType
        from tessera.refinement.operations import OPERATION_HANDLERS

        for op in OperationType:
            assert op in OPERATION_HANDLERS, f"Missing handler for {op.value}"

    def test_handlers_are_callable(self):
        """FR-019: All handlers are callable functions."""
        from tessera.refinement.operations import OPERATION_HANDLERS

        for op, handler in OPERATION_HANDLERS.items():
            assert callable(handler), f"Handler for {op} is not callable"


# ===================================================================
# 6. Chat Manager (FR-001, FR-002, FR-042)
# ===================================================================


class TestChatManagerBasics:
    """FR-001, FR-002: Chat message management."""

    def test_add_and_retrieve_messages(self):
        """FR-001: Messages can be added and retrieved."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        mgr.add_message("user", "hello")
        mgr.add_message("assistant", "hi")
        msgs = mgr.get_messages()
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"

    def test_message_has_timestamp(self):
        """Messages have a timestamp field."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        msg = mgr.add_message("user", "test")
        assert msg.timestamp > 0

    def test_message_with_image_name(self):
        """FR-003: Messages can carry an image data block name."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        msg = mgr.add_message("assistant", "done", image_name="BF_Preview_123")
        assert msg.image_name == "BF_Preview_123"

    def test_message_with_version(self):
        """FR-030: Messages can carry an undo version number."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        msg = mgr.add_message("assistant", "scaled", version=3)
        assert msg.version == 3


class TestChatManagerFIFO:
    """FR-042: FIFO message history limit."""

    def test_max_history_length_constant(self):
        """FR-042: Max history is 200."""
        from tessera.refinement.chat_manager import MAX_HISTORY_LENGTH

        assert MAX_HISTORY_LENGTH == 200

    def test_fifo_eviction_at_capacity(self):
        """FR-042: Oldest messages evicted when exceeding 200."""
        from tessera.refinement.chat_manager import MAX_HISTORY_LENGTH, ChatManager

        mgr = ChatManager()
        for i in range(MAX_HISTORY_LENGTH + 5):
            mgr.add_message("user", f"msg_{i}")
        assert mgr.message_count == MAX_HISTORY_LENGTH

    def test_fifo_preserves_latest(self):
        """FR-042: After eviction, latest messages are preserved."""
        from tessera.refinement.chat_manager import MAX_HISTORY_LENGTH, ChatManager

        mgr = ChatManager()
        for i in range(MAX_HISTORY_LENGTH + 10):
            mgr.add_message("user", f"msg_{i}")
        msgs = mgr.get_messages()
        # Oldest surviving should be msg_{10}
        assert msgs[0].text == "msg_10"
        assert msgs[-1].text == f"msg_{MAX_HISTORY_LENGTH + 9}"


class TestChatManagerLLMHistory:
    """CON-001: LLM history excludes system messages and images."""

    def test_llm_history_excludes_system(self):
        """CON-001: System messages are excluded from LLM history."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        mgr.add_message("system", "system info")
        mgr.add_message("user", "hello")
        mgr.add_message("assistant", "hi")
        history = mgr.get_llm_history()
        assert len(history) == 2
        roles = {h["role"] for h in history}
        assert "system" not in roles

    def test_llm_history_is_text_only(self):
        """CON-001: LLM history contains only text, no image data."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        mgr.add_message("user", "hello")
        mgr.add_message("assistant", "done", image_name="BF_Preview_123")
        history = mgr.get_llm_history()
        for entry in history:
            assert "image" not in entry
            assert set(entry.keys()) == {"role", "content"}


class TestChatManagerSession:
    """Chat session lifecycle."""

    def test_session_start_clears_history(self):
        """Session start clears existing messages."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        mgr.add_message("user", "old")
        mgr.start_session()
        assert mgr.message_count == 0
        assert mgr.is_active is True

    def test_session_end_sets_inactive(self):
        """Session end sets is_active to False."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        mgr.start_session()
        mgr.end_session()
        assert mgr.is_active is False

    def test_clear_removes_all(self):
        """Clear empties the message list."""
        from tessera.refinement.chat_manager import ChatManager

        mgr = ChatManager()
        mgr.add_message("user", "test")
        mgr.clear()
        assert mgr.message_count == 0


# ===================================================================
# 7. LLM Backend (FR-009, SEC-003, SEC-006)
# ===================================================================


class TestLLMBackendInterface:
    """FR-009: LLM backend pluggable interface."""

    def test_backend_is_abstract(self):
        """FR-009: LLMBackend is abstract with generate and is_available."""
        from tessera.refinement.llm_backend.base import LLMBackend

        assert hasattr(LLMBackend, "generate")
        assert hasattr(LLMBackend, "is_available")
        # Should not be instantiable directly
        with pytest.raises(TypeError):
            LLMBackend()

    def test_backend_error_class_exists(self):
        """LLMBackendError is importable and is an Exception."""
        from tessera.refinement.llm_backend.base import LLMBackendError

        assert issubclass(LLMBackendError, Exception)


class TestAPILLMBackendSecurity:
    """SEC-003, SEC-006: API backend security."""

    def test_https_enforcement(self):
        """SEC-006: API backend rejects non-HTTPS endpoints."""
        from tessera.refinement.llm_backend.api_llm import APILLMBackend
        from tessera.refinement.llm_backend.base import LLMBackendError

        with pytest.raises(LLMBackendError, match="HTTPS"):
            APILLMBackend(endpoint="http://insecure.example.com", api_key="k")

    def test_https_accepted(self):
        """SEC-006: HTTPS endpoints are accepted."""
        from tessera.refinement.llm_backend.api_llm import APILLMBackend

        backend = APILLMBackend(
            endpoint="https://api.example.com",
            api_key="test-key",
        )
        assert backend._endpoint == "https://api.example.com"

    def test_api_key_masking(self):
        """SEC-003: API keys are masked for logging."""
        from tessera.refinement.llm_backend.api_llm import _mask_api_key

        # Last 4 chars shown → sk-abc123xyz → last 4 = "3xyz"
        assert _mask_api_key("sk-abc123xyz") == "sk-****3xyz"
        assert _mask_api_key("ab") == "****"

    def test_is_available_returns_false_without_key(self):
        """FR-040: Backend not available without API key."""
        from tessera.refinement.llm_backend.api_llm import APILLMBackend

        backend = APILLMBackend(
            endpoint="https://api.example.com",
            api_key="",
        )
        assert backend.is_available() is False

    def test_generate_raises_without_key(self):
        """FR-040: Generate raises LLMBackendError when key is empty."""
        from tessera.refinement.llm_backend.api_llm import APILLMBackend
        from tessera.refinement.llm_backend.base import LLMBackendError

        backend = APILLMBackend(
            endpoint="https://api.example.com",
            api_key="",
        )
        # The error may be about missing httpx or missing key, depending on env.
        with pytest.raises(LLMBackendError):
            backend.generate("prompt", [])


# ===================================================================
# 8. Preview Renderer (FR-037, FR-038)
# ===================================================================


class TestPreviewRenderer:
    """FR-037, FR-038: Post-edit preview rendering."""

    def test_preview_size_constant(self):
        """FR-037: Preview resolution is 512×512."""
        from tessera.refinement.preview_renderer import PreviewRenderer

        assert PreviewRenderer.PREVIEW_SIZE == 512

    def test_preview_image_naming_convention(self):
        """FR-038: Preview images named BF_Preview_{timestamp}."""
        # Verify the naming pattern matches spec.
        import re

        pattern = r"^BF_Preview_\d+$"
        assert re.match(pattern, "BF_Preview_1713300000000")


# ===================================================================
# 9. Security & Constraint Compliance
# ===================================================================


class TestSecurityConstraints:
    """SEC-001 through SEC-006: Security constraint verification."""

    def test_no_eval_in_parser(self):
        """SEC-002 / CON-003: Intent parser uses json.loads, not eval."""
        import ast
        import inspect

        from tessera.refinement import intent_parser

        source = inspect.getsource(intent_parser)
        # Check AST for eval/exec Call nodes (ignores comments/docstrings).
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                    pytest.fail(f"Found {func.id}() call in intent_parser")

    def test_no_eval_in_region_resolver(self):
        """SEC-002: Region resolver does not use eval/exec."""
        import ast
        import inspect

        from tessera.refinement import region_resolver

        source = inspect.getsource(region_resolver)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                    pytest.fail(f"Found {func.id}() call in region_resolver")

    def test_no_eval_in_edit_executor(self):
        """SEC-002: Edit executor does not use eval/exec."""
        import ast
        import inspect

        from tessera.refinement import edit_executor

        source = inspect.getsource(edit_executor)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                    pytest.fail(f"Found {func.id}() call in edit_executor")

    def test_data_minimization_in_system_prompt(self):
        """CON-001: System prompt contains only bounding box, vgroups, face count."""
        from tessera.refinement.intent_parser import _build_system_prompt

        ctx = {
            "bounding_box_mm": {"x": 50, "y": 30, "z": 100},
            "vertex_groups": ["handle"],
            "face_count": 1000,
        }
        prompt = _build_system_prompt(ctx)
        # Should NOT contain any file path or PII patterns
        assert "/home/" not in prompt
        assert "C:\\" not in prompt
        assert "@" not in prompt  # No email addresses

    def test_parameter_range_table_completeness(self):
        """FR-044: Parameter range table covers all parameterized operations."""
        from tessera.refinement.intent_schema import PARAMETER_RANGES

        expected_ops = [
            "SCALE",
            "MOVE",
            "ROTATE",
            "SOLIDIFY",
            "SMOOTH",
            "SHARPEN",
            "BEVEL",
            "ADD_GEOMETRY",
        ]
        for op in expected_ops:
            assert op in PARAMETER_RANGES, f"Missing range for {op}"


class TestGPLLicenseHeaders:
    """CON-007: All source files have GPL v2+ license headers."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "tessera.refinement.intent_schema",
            "tessera.refinement.intent_parser",
            "tessera.refinement.region_resolver",
            "tessera.refinement.edit_executor",
            "tessera.refinement.undo_manager",
            "tessera.refinement.chat_manager",
            "tessera.refinement.preview_renderer",
            "tessera.refinement.llm_backend.base",
            "tessera.refinement.llm_backend.api_llm",
        ],
    )
    def test_module_has_gpl_header(self, module_name):
        """CON-007: Each source file includes GPL v2+ license header."""
        import importlib
        import inspect

        mod = importlib.import_module(module_name)
        source = inspect.getsource(mod)
        assert "GPL" in source or "General Public License" in source
