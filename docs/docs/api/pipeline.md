# Pipeline API Reference

Developer documentation for Tessera's internal pipeline API.

---

## VisionPipeline

The vision pipeline processes reference images through four sequential stages.

```python
from tessera.vision.pipeline import VisionPipeline

pipeline = VisionPipeline()
results = pipeline.process([
    ImageInput(filepath="/path/to/image.jpg", view_label="front"),
])
```

### Stages

1. **Segmentation** — SAM 2 Large adapter
2. **Depth Estimation** — Depth Anything V2 Large adapter
3. **View Classification** — Silhouette-based heuristic
4. **Feature Extraction** — DINOv2 ViT-B/14 adapter

### Custom Adapters

Inject custom adapters via the constructor:

```python
pipeline = VisionPipeline(
    segmentation_adapter=FastSAMAdapter(),
    depth_adapter=CustomDepthAdapter(),
)
```

---

## ExportPipeline

The export pipeline validates and exports meshes.

```python
from tessera.export import ExportPipeline

pipeline = ExportPipeline()
result = pipeline.execute(context, obj, settings)
```

---

## ErrorHandler

Centralized error handling for all pipeline stages.

```python
from tessera.errors import ErrorHandler, ERROR_CATALOG

handler = ErrorHandler(catalog=ERROR_CATALOG)

try:
    result = some_pipeline_stage()
except Exception as exc:
    error_result = handler.catch(exc, stage_name="vision")
    print(error_result.user_message)
```

---

## PerformanceProfiler

Instruments pipeline stages with timing and memory tracking.

```python
from tessera.perf import PerformanceProfiler

profiler = PerformanceProfiler()

with profiler.stage("vision"):
    vision_results = pipeline.process(images)

with profiler.stage("reconstruction"):
    mesh = adapter.generate(vision_results)

report = profiler.report()
print(report.to_json())
```

---

## GoldenMeshRegistry

Manages golden-mesh references for regression testing.

```python
from tessera.testing import GoldenMeshRegistry

registry = GoldenMeshRegistry("tests/golden_meshes/")

# Create a reference
ref = registry.create_reference("cube", vertices, faces)

# Compare against reference
match, detail = registry.compare("cube", new_vertices, new_faces)
```
