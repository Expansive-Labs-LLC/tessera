# Export & Print

Tessera validates meshes for 3D printing and exports in multiple formats with embedded metadata.

![Export panel showing STL and 3MF formats selected with validation results displayed and an Export button ready to click](assets/screenshots/export-panel.png)

---

## Export Formats

| Format | Extension | Best For | Metadata | Slicer Support |
|--------|-----------|----------|----------|----------------|
| **STL** | `.stl` | Universal compatibility | None | All slicers |
| **OBJ** | `.obj` | Vertex colors, UV maps | Material file (`.mtl`) | Most slicers |
| **3MF** | `.3mf` | Modern workflows | Print settings, validation report | PrusaSlicer, Bambu Studio, Cura |

!!! tip "Prefer 3MF"
    3MF is the recommended format for 3D printing. It embeds print metadata, validation results, and supports units natively — your slicer reads them automatically.

### 3MF Metadata

When exporting to 3MF with **Embed 3MF Metadata** enabled (default), Tessera injects:

**Standard Metadata:**

- Title, Designer, Creation/Modification dates

**Print Settings** (Tessera namespace `bf:`):

- `bf:PrinterType` — FDM or SLA
- `bf:WallThicknessMM` — Minimum wall thickness
- `bf:InfillSuggestion` — Recommended infill percentage
- `bf:SupportSuggestion` — Support structure recommendation
- `bf:SourceImages` — Number of reference images used

**Validation Report:**

- `bf:ManifoldStatus` — Pass/Fail
- `bf:WallThicknessStatus` — Pass/Fail
- `bf:OverhangStatus` — Pass/Fail
- `bf:VolumeMMCubed` — Object volume

---

## Print-Readiness Validation

Before export, Tessera runs these validation checks:

| Check | Description | FDM Threshold | SLA Threshold |
|-------|-------------|---------------|---------------|
| **Manifold** | Mesh is watertight (no holes or dangling edges) | Required | Required |
| **Wall Thickness** | Minimum printable wall thickness | ≥1.2 mm | ≥0.5 mm |
| **Overhang Angle** | Maximum unsupported overhang angle | ≤45° | ≤30° |
| **Build Volume** | Model fits within printer bed dimensions | Per profile | Per profile |

Each check reports ✅ Pass, ⚠️ Warning, or ❌ Fail with a specific message.

### Force Export

If validation fails, you can still export by enabling **Force Export**. A confirmation dialog explains the specific risks (e.g., "Mesh has 3 non-manifold edges — slicer may produce incorrect toolpaths").

!!! warning "Force Export Risks"
    Exporting a non-validated mesh may result in failed prints, wasted material, or slicer errors. Use Force Export only when you've manually verified the mesh in Edit Mode.

---

## Printer Profiles

| Profile Name | Build Volume (W×D×H mm) | Printer Type | Default Wall Thickness | Default Overhang Angle |
|-------------|------------------------|-------------|----------------------|----------------------|
| Generic FDM | 220×220×250 | FDM | 1.2 mm | 45° |
| Ender 3 | 220×220×250 | FDM | 1.2 mm | 45° |
| Prusa MK4 | 250×210×220 | FDM | 1.2 mm | 45° |
| Bambu Lab P1S | 256×256×256 | FDM | 1.2 mm | 45° |
| Elegoo Mars 3 | 143×89×175 | SLA | 0.5 mm | 30° |
| Elegoo Saturn 3 | 218×123×250 | SLA | 0.5 mm | 30° |
| Custom | User-defined | Any | User-defined | User-defined |

Select a printer profile in the Validation panel before running validation. For custom printers, enter your build volume dimensions manually.

---

## Export Workflow

1. Run **Validate** in the Validation panel (required before export).
2. Select output format(s): STL, OBJ, and/or 3MF.
3. Choose an export directory (defaults to the `.blend` file location).
4. Click **Export**.
5. Files are saved as `{object_name}.{ext}`.

---

## See Also

- [Mesh Cleanup](mesh-cleanup.md) — Fix topology issues before export
- [Scaling & Orientation](scaling-orientation.md) — Set real-world dimensions
- [Printer Profiles Reference](../reference/printer-profiles.md) — Full printer profile specifications

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
