# Printer Profiles

Tessera includes built-in printer profiles for common FDM and SLA 3D printers. Profiles define bed dimensions and default validation thresholds.

---

## Built-in Profiles

| Profile Name | Build Volume (W×D×H mm) | Printer Type | Default Wall Thickness | Default Overhang Angle |
|-------------|------------------------|-------------|----------------------|----------------------|
| Generic FDM | 220×220×250 | FDM | 1.2 mm | 45° |
| Ender 3 | 220×220×250 | FDM | 1.2 mm | 45° |
| Prusa MK4 | 250×210×220 | FDM | 1.2 mm | 45° |
| Bambu Lab P1S | 256×256×256 | FDM | 1.2 mm | 45° |
| Elegoo Mars 3 | 143×89×175 | SLA | 0.5 mm | 30° |
| Elegoo Saturn 3 | 218×123×250 | SLA | 0.5 mm | 30° |
| Custom | User-defined | Any | User-defined | User-defined |

---

## Profile Details

### Generic FDM

A conservative profile suitable for most FDM printers with a standard 220×220×250 mm build volume. Use this when your specific printer is not listed.

### Ender 3

Creality Ender 3 and Ender 3 V2/V3. Standard 220×220×250 mm build volume with Bowden or direct-drive extruder.

### Prusa MK4

Prusa Research MK4 and MK3.5. Features a 250×210×220 mm build volume with input shaper for faster printing.

### Bambu Lab P1S

Bambu Lab P1S enclosed printer. Cubic 256×256×256 mm build volume with fully enclosed chamber for ABS/ASA printing.

### Elegoo Mars 3

Elegoo Mars 3 MSLA resin printer. Compact 143×89×175 mm build volume with 4K mono LCD for fine detail.

### Elegoo Saturn 3

Elegoo Saturn 3 large-format MSLA resin printer. 218×123×250 mm build volume with 12K mono LCD.

### Custom

Define your own build volume dimensions, printer type, wall thickness threshold, and overhang angle limit. Use this for printers not listed above.

---

## Validation Thresholds

Printer profiles automatically configure validation thresholds:

| Setting | FDM Default | SLA Default |
|---------|-------------|-------------|
| Minimum wall thickness | 1.2 mm | 0.5 mm |
| Maximum overhang angle | 45° | 30° |
| Build volume check | Per profile | Per profile |
| Manifold requirement | Required | Required |

!!! tip "Custom Thresholds"
    You can override the default thresholds for any profile in the Validation panel. For example, set wall thickness to 0.8 mm if your FDM printer handles thin walls well.

---

## See Also

- [Export & Print](../user-guide/export.md) — Validation and export using printer profiles
- [Scaling & Orientation](../user-guide/scaling-orientation.md) — Ensure your model fits the build volume

*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*
