# Adapter API Reference

Tessera uses an adapter pattern to support multiple AI model backends. Custom adapters can be created by implementing the base adapter interfaces.

---

## BaseReconstructionAdapter

All reconstruction adapters must implement this interface:

```python
from tessera.reconstruction.base import BaseReconstructionAdapter

class CustomAdapter(BaseReconstructionAdapter):
    """Custom reconstruction adapter."""

    @property
    def model_name(self) -> str:
        return "custom-model-v1"

    def load(self) -> None:
        """Load model weights into GPU memory."""
        ...

    def generate(self, vision_results, **kwargs):
        """Generate a 3D mesh from vision analysis results."""
        ...

    def unload(self) -> None:
        """Release GPU memory."""
        ...
```

### Available Adapters

| Adapter | Class | Model |
|---------|-------|-------|
| TripoSR | `TripoSRAdapter` | TripoSR v1.0 |
| InstantMesh | `InstantMeshAdapter` | InstantMesh |
| CRM | `CRMAdapter` | CRM v1.0 |

---

## Vision Adapters

### SegmentationAdapter

```python
class CustomSegAdapter(SegmentationAdapter):
    @property
    def model_name(self) -> str:
        return "custom-seg"

    def load(self) -> None: ...
    def predict(self, image: np.ndarray) -> np.ndarray: ...
    def unload(self) -> None: ...
```

### DepthAdapter

```python
class CustomDepthAdapter(DepthAdapter):
    @property
    def model_name(self) -> str:
        return "custom-depth"

    def load(self) -> None: ...
    def predict(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray: ...
    def unload(self) -> None: ...
```

### FeatureAdapter

```python
class CustomFeatureAdapter(FeatureAdapter):
    @property
    def model_name(self) -> str:
        return "custom-features"

    def load(self) -> None: ...
    def predict(self, image: np.ndarray) -> np.ndarray: ...
    def unload(self) -> None: ...
```

---

## Registering Custom Adapters

Custom adapters can be injected at pipeline construction:

```python
from tessera.vision.pipeline import VisionPipeline

pipeline = VisionPipeline(
    segmentation_adapter=CustomSegAdapter(),
    depth_adapter=CustomDepthAdapter(),
)
```

!!! note
    Custom adapters must follow the same load/predict/unload lifecycle.
    The pipeline calls `load()` before processing and `unload()` after each stage.
