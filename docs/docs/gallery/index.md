# Gallery

Example outputs from the Tessera pipeline across 5 object categories. Each entry includes input image count, adapter used, face count, generation time, and print status.

---

## Categories

### 🏠 Household Objects

Objects commonly found in homes — mugs, vases, bottles, lamps.

| Object | Input | Output | Views | Adapter | Faces | Time | Print Status |
|--------|-------|--------|-------|---------|-------|------|-------------|
| Coffee Mug | ![Coffee mug reference photo showing a white ceramic mug on a gray background from front-left angle](assets/screenshots/gallery-mug-input.png) | ![Generated 3D mesh of a coffee mug in the Blender viewport with solid shading](assets/screenshots/gallery-mug-output.png) | 4 | TripoSR | 24,512 | ~8s | ✅ FDM Ready |
| Ceramic Vase | ![Ceramic vase reference photo showing a blue glazed vase on white background from front angle](assets/screenshots/gallery-vase-input.png) | ![Generated 3D mesh of a ceramic vase showing smooth surface detail](assets/screenshots/gallery-vase-output.png) | 3 | InstantMesh | 31,280 | ~18s | ✅ FDM Ready |

### 🎮 Figurines & Toys

Character figurines, miniatures, and collectibles.

| Object | Input | Output | Views | Adapter | Faces | Time | Print Status |
|--------|-------|--------|-------|---------|-------|------|-------------|
| Chess Knight | ![Chess knight reference photo showing a carved wooden knight piece on dark background](assets/screenshots/gallery-chess-input.png) | ![Generated 3D mesh of a chess knight with detailed mane and head features](assets/screenshots/gallery-chess-output.png) | 2 | TripoSR | 18,900 | ~6s | ✅ FDM Ready |
| Action Figure | ![Action figure reference photo showing a detailed character figurine from multiple angles](assets/screenshots/gallery-figure-input.png) | ![Generated 3D mesh of an action figure with limbs and surface detail](assets/screenshots/gallery-figure-output.png) | 6 | CRM | 52,100 | ~35s | ✅ SLA Ready |

### 🔧 Mechanical Parts

Functional parts, enclosures, brackets, and hardware.

| Object | Input | Output | Views | Adapter | Faces | Time | Print Status |
|--------|-------|--------|-------|---------|-------|------|-------------|
| Cable Clip | ![Small cable clip reference photo on white background from top angle](assets/screenshots/gallery-clip-input.png) | ![Generated 3D mesh of a cable clip showing snap-fit geometry](assets/screenshots/gallery-clip-output.png) | 1 | TripoSR | 8,200 | ~5s | ✅ FDM Ready |
| Hinge Bracket | ![Metal hinge bracket reference photo showing two plates with a pivot from multiple angles](assets/screenshots/gallery-hinge-input.png) | ![Generated 3D mesh of a hinge bracket with flat plates and cylindrical pivot](assets/screenshots/gallery-hinge-output.png) | 4 | InstantMesh | 14,600 | ~16s | ✅ FDM Ready |

### 🌿 Organic Forms

Natural objects, plants, animals, and artistic sculptures.

| Object | Input | Output | Views | Adapter | Faces | Time | Print Status |
|--------|-------|--------|-------|---------|-------|------|-------------|
| Succulent Plant | ![Potted succulent reference photo showing detailed leaves from overhead angle](assets/screenshots/gallery-succulent-input.png) | ![Generated 3D mesh of a succulent plant with individual leaf geometry](assets/screenshots/gallery-succulent-output.png) | 3 | InstantMesh | 42,300 | ~20s | ✅ SLA Ready |
| Seashell | ![Natural seashell reference photo showing spiral structure from multiple angles](assets/screenshots/gallery-shell-input.png) | ![Generated 3D mesh of a seashell capturing spiral ridges and opening](assets/screenshots/gallery-shell-output.png) | 4 | CRM | 38,100 | ~32s | ✅ FDM Ready |

### 🏛️ Architectural Elements

Decorative elements, ornaments, and structural components.

| Object | Input | Output | Views | Adapter | Faces | Time | Print Status |
|--------|-------|--------|-------|---------|-------|------|-------------|
| Column Capital | ![Ornate column capital reference photo showing acanthus leaf carvings from front and side](assets/screenshots/gallery-column-input.png) | ![Generated 3D mesh of a column capital with detailed leaf ornamentation](assets/screenshots/gallery-column-output.png) | 5 | CRM | 61,000 | ~38s | ✅ SLA Ready |
| Door Knob | ![Round door knob reference photo showing brushed metal finish on white background](assets/screenshots/gallery-knob-input.png) | ![Generated 3D mesh of a door knob with smooth round surface and mounting plate](assets/screenshots/gallery-knob-output.png) | 2 | TripoSR | 15,400 | ~6s | ✅ FDM Ready |

---

## Tips for Best Results

1. **More views = better quality** — 3–6 views consistently outperform single-view reconstruction
2. **Lighting matters** — Even, diffuse lighting produces the cleanest meshes
3. **Background contrast** — Plain backgrounds improve segmentation accuracy
4. **Object complexity** — Simple geometric shapes reconstruct most reliably
5. **Adapter selection** — Match the adapter to your quality/speed requirements

---

## Contributing to the Gallery

We welcome community-submitted examples! To contribute:

1. Fork the [Tessera repository](https://github.com/Expansive-Labs-LLC/tessera)
2. Add your entry to `docs/docs/gallery/gallery.yaml`
3. Include: object name, category, number of views, adapter used, face count, generation time, and print status
4. Submit a pull request with a brief description
