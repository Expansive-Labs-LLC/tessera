# Glossary

Definitions of key terms used throughout the Tessera documentation.

---

## 3MF

3D Manufacturing Format — a modern, XML-based 3D print file format that supports metadata, materials, textures, and print settings. Recommended over STL for modern slicers.

## Adapter

A pluggable backend module in Tessera that implements a specific AI model interface. Tessera supports multiple reconstruction adapters (TripoSR, InstantMesh, CRM) and vision adapters (SAM 2, Depth Anything V2, DINOv2).

## bpy

Blender's Python API module (`bpy`) used for scripting and automation. Tessera uses `bpy` to manipulate meshes, manage scenes, and control the UI within Blender.

## Build Volume

The maximum physical dimensions (width × depth × height) that a 3D printer can produce in a single print. Models exceeding the build volume must be scaled down or split into parts.

## CRM

Convolutional Reconstruction Model — a multi-view reconstruction adapter in Tessera that produces the highest quality meshes from 4–6 reference images. Requires approximately 8 GB VRAM.

## CUDA

NVIDIA's parallel computing platform and API for GPU-accelerated computing. Required for running Tessera on NVIDIA GPUs.

## Decimation

A mesh simplification technique that reduces the polygon (face) count while preserving the overall shape. Used to optimize mesh size for 3D printing where extremely fine detail is unnecessary.

## Depth Anything V2

A monocular depth estimation model that predicts per-pixel depth maps from a single image. Used in Tessera's vision pipeline to estimate 3D depth from reference photos.

## DINOv2

A self-supervised Vision Transformer model by Meta AI used for feature extraction. Tessera uses DINOv2 (ViT-B/14) to extract visual features that guide the 3D reconstruction process.

## FDM

Fused Deposition Modeling — the most common 3D printing technology. Works by melting and extruding thermoplastic filament (PLA, ABS, PETG) layer by layer. Typical minimum wall thickness: 1.2 mm.

## GGUF

A file format for storing quantized large language model weights. Used by Tessera's local LLM backend for natural language refinement. Supports various quantization levels (Q4, Q5, Q8) to balance quality vs. VRAM usage.

## InstantMesh

A multi-view reconstruction adapter in Tessera that provides a good balance of speed and quality. Best for 2–4 reference images. Requires approximately 6 GB VRAM.

## Manifold

A mesh property where every edge is shared by exactly two faces — no holes, no dangling edges, no self-intersections. Manifold meshes are required for 3D printing because slicers need a closed surface to compute infill and toolpaths.

## MPS

Metal Performance Shaders — Apple's GPU compute framework for Apple Silicon (M1/M2/M3/M4) chips. Tessera detects Metal GPUs but does **not** use MPS for inference in v1; its adapters require CUDA.

## Overhang Angle

The angle between a mesh face and the vertical build direction. Faces with overhang angles exceeding the threshold (typically 45° for FDM, 30° for SLA) require support structures during printing.

## Quad Remesh

A mesh processing technique that converts triangulated topology to quad-dominant topology (four-sided faces). Produces cleaner meshes for subdivision surface modeling and manual editing.

## ROCm

AMD's open-source GPU computing platform, analogous to NVIDIA's CUDA. Tessera detects ROCm GPUs but does **not** run inference on them in v1 — support is planned, not shipped.

## SAM 2

Segment Anything Model 2 by Meta AI — an image segmentation model used in Tessera's vision pipeline to isolate the target object from its background.

## SLA

Stereolithography — a 3D printing technology that uses UV light to cure liquid photopolymer resin layer by layer. Produces higher detail than FDM with typical minimum wall thickness of 0.5 mm.

## Slicer

Software that converts a 3D mesh into G-code instructions for a 3D printer. Popular slicers include PrusaSlicer, Cura, Bambu Studio, and ChiTuBox. Tessera exports print-ready files compatible with all major slicers.

## STL

Standard Tessellation Language — the most widely supported 3D print file format. Stores only geometry (triangulated faces) without metadata. Compatible with virtually all slicers and 3D printing services.

## TripoSR

A fast single-view reconstruction adapter in Tessera. Generates a 3D mesh from a single reference image in approximately 5 seconds. Requires approximately 4 GB VRAM.

## VRAM

Video Random Access Memory — dedicated memory on a GPU used for storing model weights, input data, and intermediate computations. Tessera requires a minimum of 4 GB VRAM, with 8+ GB recommended for all features.

## Voxel Remesh

A mesh processing technique that converts any mesh into a regular voxel grid and re-extracts the surface. Guarantees a manifold, watertight output but may lose sharp edges. Controlled by voxel size parameter.

## Watertight

A mesh property where the surface forms a completely closed volume with no holes or gaps. All watertight meshes are manifold, but not all manifold meshes are watertight (a manifold mesh could have internal isolated surfaces). Required for slicers to correctly compute infill.

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
