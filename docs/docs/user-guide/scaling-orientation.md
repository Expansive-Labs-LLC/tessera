# Scaling & Orientation

Tessera helps you set real-world dimensions and optimal print orientation for your 3D model.

![Scaling panel showing dimension inputs for width height and depth in millimeters with auto-infer enabled and a print orientation optimize button](assets/screenshots/scaling-panel.png)

---

## Auto-Infer Scaling

Tessera can automatically estimate real-world dimensions based on the detected object class:

1. Enable **Auto Infer** in the Scaling panel.
2. Tessera classifies the object type (e.g., "mug", "figurine", "bracket") using vision features.
3. Dimensions are estimated from learned size priors for that class.
4. Review and adjust the estimated dimensions as needed.

!!! info "Estimation Accuracy"
    Auto-inferred dimensions are approximate. Always verify the final dimensions before printing, especially for functional parts where precise fit matters.

---

## Manual Dimension Entry

For precise control, enter target dimensions directly:

1. Select the dimension to constrain: **Width (X)**, **Height (Z)**, or **Depth (Y)**.
2. Enter the target value in millimeters.
3. Click **Apply Scale** to resize the object proportionally.

You can also enter all three dimensions independently if you need non-uniform scaling:

| Dimension | Axis | Description |
|-----------|------|-------------|
| Width | X | Left-to-right measurement |
| Depth | Y | Front-to-back measurement |
| Height | Z | Bottom-to-top measurement |

!!! tip "One Dimension is Enough"
    Setting one dimension scales the other two proportionally, preserving the object's shape. Use this for quick sizing.

---

## Print Orientation Optimizer

The print orientation optimizer suggests the best orientation for 3D printing:

1. Click **Optimize Orientation** in the Scaling panel.
2. Tessera analyzes the mesh geometry and evaluates multiple orientations.
3. The optimizer selects the orientation that:
   - **Minimizes support material** — Reduces overhanging surfaces below the threshold angle.
   - **Flattens the bottom face** — Ensures a stable, flat base on the print bed.
   - **Maximizes surface quality** — Orients visible surfaces away from support contact points.

!!! warning "Review the Result"
    The optimizer handles most cases well, but you may need to manually adjust orientation for objects with specific aesthetic requirements or functional constraints.

---

## Unit System Configuration

Tessera uses millimeters (mm) as the default unit system for all dimensions, consistent with 3D printing conventions.

- **Blender's unit system** is set to Metric with a scale of 0.001 (1 Blender unit = 1 mm).
- All dimension inputs in the Scaling panel are in millimeters.
- Export formats (STL, 3MF) use the configured unit scale.

---

## See Also

- [Mesh Cleanup](mesh-cleanup.md) — Fix topology issues before scaling
- [Export & Print](export.md) — Validate dimensions against printer build volumes

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
