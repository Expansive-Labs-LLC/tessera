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

"""The wire format shared by the add-on and the engine.

**This file is duplicated verbatim in the engine distribution.** The two
halves ship separately and neither may import the other, so the contract
between them is a file that is byte-for-byte identical on both sides, with
a test asserting it stays that way. A protocol defined twice in prose
drifts; one defined twice in code with an equality test does not.

Numeric arrays cross as base64 raw little-endian buffers rather than
nested JSON numbers (SPEC-TS-0023 FR-027). This is not a micro-
optimisation: a 200,000-vertex mesh is roughly 25 MB as JSON and under
2 MB this way, and the JSON decoder alone would spend longer than the
whole IPC budget NFR-003 allows.

Every decoder validates dtype and rank. The engine treats request fields
as untrusted input (SEC-003), and the add-on has no more reason to trust
what came back off a socket than the engine had to trust what went in.

Spec: SPEC-TS-0023 (FR-025, FR-026, FR-027, FR-029, SEC-003)

Public API:
    CodecError — a payload that does not match the contract
    encode_array / decode_array — raw numeric buffers
    encode_png / decode_png — 8-bit image data
    encode_vision_input / decode_vision_input — one VisionPipelineOutput
    encode_mesh_result / decode_mesh_result — one ReconstructionResult
"""

from __future__ import annotations

import base64
import io
from typing import Any, Optional

import numpy as np

#: Wire dtype names. Fixed strings rather than numpy's platform-dependent
#: spellings, so the contract does not change with the interpreter.
_F32 = "float32"
_I32 = "int32"

#: Fields of ``VisionResult`` that cross as plain JSON scalars.
_VISION_SCALARS = (
    "view_label",
    "label_confidence",
    "label_source",
    "label_needs_confirmation",
)

#: Metadata keys ``StandardMesh`` requires; the add-on cannot construct a
#: valid mesh without every one of them (FR-026).
_MESH_METADATA_KEYS = (
    "model_name",
    "inference_time_s",
    "confidence",
    "vertex_count",
    "face_count",
)


class CodecError(ValueError):
    """A payload does not match the wire contract.

    Carries the field name so the caller can name it in a ``bad_request``
    response rather than reporting that something, somewhere, was wrong.

    Attributes:
        field: The offending field.
    """

    def __init__(self, field: str, detail: str):
        super().__init__(f"{field}: {detail}")
        self.field = field


# ---------------------------------------------------------------------------
# Numeric arrays
# ---------------------------------------------------------------------------


def encode_array(array: np.ndarray, dtype: str) -> dict:
    """Encode an array as a base64 raw buffer with its shape (FR-027).

    Args:
        array: Array to encode. Cast to ``dtype`` if it is not already.
        dtype: Wire dtype, ``"float32"`` or ``"int32"``.

    Returns:
        ``{"b64": str, "dtype": str, "shape": [int, ...]}``.

    Raises:
        CodecError: If ``dtype`` is not one this contract carries.
    """
    if dtype not in (_F32, _I32):
        raise CodecError("dtype", f"{dtype!r} is not a wire dtype")
    # ascontiguousarray because a sliced or transposed view has a buffer
    # whose bytes are not in the order the shape implies.
    buf = np.ascontiguousarray(array, dtype=np.dtype(dtype).newbyteorder("<"))
    return {
        "b64": base64.b64encode(buf.tobytes()).decode("ascii"),
        "dtype": dtype,
        "shape": list(buf.shape),
    }


def decode_array(
    payload: Any,
    field: str,
    dtype: str,
    rank: Optional[int] = None,
    last_dim: Optional[int] = None,
) -> np.ndarray:
    """Decode a base64 raw buffer, validating dtype and shape.

    Args:
        payload: The encoded object.
        field: Field name, used in errors.
        dtype: The dtype this field must carry.
        rank: Required number of dimensions, or ``None`` to accept any.
        last_dim: Required size of the final axis, or ``None``.

    Returns:
        The decoded array.

    Raises:
        CodecError: On any mismatch, including a buffer whose length does
            not agree with the declared shape.
    """
    if not isinstance(payload, dict):
        raise CodecError(field, "expected an encoded array object")
    if payload.get("dtype") != dtype:
        raise CodecError(field, f"expected dtype {dtype}, got {payload.get('dtype')!r}")

    shape = payload.get("shape")
    if not isinstance(shape, list) or not all(
        isinstance(n, int) and n >= 0 for n in shape
    ):
        raise CodecError(field, "shape must be a list of non-negative integers")
    if rank is not None and len(shape) != rank:
        raise CodecError(field, f"expected {rank} dimensions, got {len(shape)}")
    if last_dim is not None and (not shape or shape[-1] != last_dim):
        raise CodecError(field, f"expected final axis of {last_dim}, got {shape}")

    try:
        raw = base64.b64decode(payload.get("b64", ""), validate=True)
    except Exception as exc:
        raise CodecError(field, "b64 is not valid base64") from exc

    item = np.dtype(dtype).itemsize
    expected = item
    for n in shape:
        expected *= n
    if len(raw) != expected:
        raise CodecError(
            field, f"buffer is {len(raw)} bytes, shape {shape} needs {expected}"
        )

    flat = np.frombuffer(raw, dtype=np.dtype(dtype).newbyteorder("<"))
    # copy() because frombuffer returns a read-only view onto `raw`, and
    # callers reshape, scale and hand these to adapters that write.
    return flat.reshape(shape).astype(dtype, copy=True)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def encode_png(array: np.ndarray, field: str = "image") -> str:
    """Encode 8-bit image data as a base64 PNG (FR-027).

    Args:
        array: ``(H, W, 3)`` uint8 RGB, or ``(H, W)`` uint8 grayscale.
        field: Field name, used in errors.

    Returns:
        Base64 PNG.

    Raises:
        CodecError: If the array is not 8-bit RGB or grayscale.
    """
    from PIL import Image

    arr = np.asarray(array)
    if arr.dtype != np.uint8:
        raise CodecError(field, f"expected uint8, got {arr.dtype}")
    if arr.ndim == 2:
        mode = "L"
    elif arr.ndim == 3 and arr.shape[2] == 3:
        mode = "RGB"
    else:
        raise CodecError(field, f"expected (H, W) or (H, W, 3), got {arr.shape}")

    buffer = io.BytesIO()
    Image.fromarray(arr, mode=mode).save(buffer, format="PNG", optimize=False)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_png(payload: Any, field: str, channels: int) -> np.ndarray:
    """Decode a base64 PNG to a uint8 array.

    Args:
        payload: Base64 PNG string.
        field: Field name, used in errors.
        channels: 1 for grayscale, 3 for RGB.

    Returns:
        ``(H, W)`` or ``(H, W, 3)`` uint8.

    Raises:
        CodecError: If the payload is not a PNG of the expected shape.
    """
    from PIL import Image

    if not isinstance(payload, str):
        raise CodecError(field, "expected a base64 PNG string")
    try:
        raw = base64.b64decode(payload, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise CodecError(field, "could not be decoded as a PNG") from exc

    converted = image.convert("L" if channels == 1 else "RGB")
    arr = np.asarray(converted, dtype=np.uint8)
    if channels == 3 and (arr.ndim != 3 or arr.shape[2] != 3):
        raise CodecError(field, f"expected RGB, got shape {arr.shape}")
    return arr


# ---------------------------------------------------------------------------
# VisionPipelineOutput — the request projection (FR-025)
# ---------------------------------------------------------------------------


def encode_vision_input(result: Any) -> dict:
    """Project one ``VisionPipelineOutput`` onto the wire (FR-025).

    Every field the adapters consume crosses, including ``features`` and
    the ``camera_pose`` SPEC-TS-0007's multi-view adapter attaches. A
    projection that quietly drops fields is how multi-view reconstruction
    would fail on the far side with no visible cause.

    Args:
        result: A ``VisionResult``, optionally carrying ``camera_pose``.

    Returns:
        The wire object.
    """
    pose = getattr(result, "camera_pose", None)
    return {
        "image": encode_png(result.image, "image"),
        "mask": encode_png(result.mask, "mask"),
        "depth_map": encode_array(result.depth_map, _F32),
        "features": encode_array(result.features, _F32),
        "original_size": list(result.original_size),
        "camera_pose": (None if pose is None else encode_array(np.asarray(pose), _F32)),
        **{name: getattr(result, name) for name in _VISION_SCALARS},
    }


def decode_vision_input(payload: Any, index: int = 0) -> dict:
    """Decode one wire input back to the fields a ``VisionResult`` needs.

    Args:
        payload: One element of the request's ``inputs`` array.
        index: Position in that array, used in errors.

    Returns:
        A dict of decoded fields, ready to build a ``VisionResult`` from.

    Raises:
        CodecError: On any missing or malformed field, naming it.
    """
    where = f"inputs[{index}]"
    if not isinstance(payload, dict):
        raise CodecError(where, "expected an object")

    for name in _VISION_SCALARS:
        if name not in payload:
            raise CodecError(f"{where}.{name}", "missing")

    pose = payload.get("camera_pose")
    decoded = {
        "image": decode_png(payload.get("image"), f"{where}.image", 3),
        "mask": decode_png(payload.get("mask"), f"{where}.mask", 1),
        "depth_map": decode_array(
            payload.get("depth_map"), f"{where}.depth_map", _F32, rank=2
        ),
        "features": decode_array(
            payload.get("features"), f"{where}.features", _F32, rank=2
        ),
        "camera_pose": (
            None
            if pose is None
            else decode_array(pose, f"{where}.camera_pose", _F32, rank=2, last_dim=4)
        ),
        **{name: payload[name] for name in _VISION_SCALARS},
    }

    size = payload.get("original_size")
    if (
        not isinstance(size, (list, tuple))
        or len(size) != 2
        or not all(isinstance(n, int) for n in size)
    ):
        raise CodecError(f"{where}.original_size", "expected [width, height]")
    decoded["original_size"] = (int(size[0]), int(size[1]))
    return decoded


# ---------------------------------------------------------------------------
# ReconstructionResult — the response projection (FR-026)
# ---------------------------------------------------------------------------


def encode_mesh_result(
    vertices: np.ndarray,
    faces: np.ndarray,
    vertex_colors: Optional[np.ndarray],
    metadata: dict,
    warnings: Optional[list] = None,
    source_adapter: str = "",
) -> dict:
    """Encode a reconstruction result (FR-026).

    Args:
        vertices: ``(N, 3)`` float32.
        faces: ``(M, 3)`` int32, zero-indexed.
        vertex_colors: ``(N, 3)`` float32 in ``[0, 1]``, or ``None``.
        metadata: Must carry every key in ``_MESH_METADATA_KEYS``.
        warnings: Non-fatal issues to carry across.
        source_adapter: Name of the adapter that produced this.

    Returns:
        The wire object.

    Raises:
        CodecError: If a required metadata key is absent — the add-on
            would otherwise have to invent it.
    """
    missing = [k for k in _MESH_METADATA_KEYS if k not in metadata]
    if missing:
        raise CodecError("metadata", f"missing {', '.join(missing)}")
    return {
        "vertices": encode_array(vertices, _F32),
        "faces": encode_array(faces, _I32),
        "vertex_colors": (
            None if vertex_colors is None else encode_array(vertex_colors, _F32)
        ),
        "warnings": list(warnings or []),
        "source_adapter": source_adapter,
        **{k: metadata[k] for k in _MESH_METADATA_KEYS},
    }


def decode_mesh_result(payload: Any) -> dict:
    """Decode a reconstruction response into mesh arrays and metadata.

    Args:
        payload: The decoded JSON response body.

    Returns:
        ``{"vertices", "faces", "vertex_colors", "metadata", "warnings",
        "source_adapter"}``, every value taken from the response rather
        than defaulted (FR-026).

    Raises:
        CodecError: On a missing or malformed field, naming it.
    """
    if not isinstance(payload, dict):
        raise CodecError("response", "expected an object")

    missing = [k for k in _MESH_METADATA_KEYS if k not in payload]
    if missing:
        raise CodecError("response", f"missing {', '.join(missing)}")

    colors = payload.get("vertex_colors")
    vertices = decode_array(payload.get("vertices"), "vertices", _F32, 2, 3)
    faces = decode_array(payload.get("faces"), "faces", _I32, 2, 3)

    # The counts are not decoration: they are what the add-on reports and
    # what NFR-010 is measured against. A response whose arrays disagree
    # with its own counts is malformed, not merely inconsistent.
    if int(payload["vertex_count"]) != int(vertices.shape[0]):
        raise CodecError("vertex_count", "disagrees with the vertices buffer")
    if int(payload["face_count"]) != int(faces.shape[0]):
        raise CodecError("face_count", "disagrees with the faces buffer")
    if colors is not None and colors is not False:
        decoded_colors = decode_array(colors, "vertex_colors", _F32, 2, 3)
        if decoded_colors.shape[0] != vertices.shape[0]:
            raise CodecError("vertex_colors", "one colour per vertex is required")
    else:
        decoded_colors = None

    return {
        "vertices": vertices,
        "faces": faces,
        "vertex_colors": decoded_colors,
        "metadata": {k: payload[k] for k in _MESH_METADATA_KEYS},
        "warnings": list(payload.get("warnings") or []),
        "source_adapter": payload.get("source_adapter", ""),
    }
