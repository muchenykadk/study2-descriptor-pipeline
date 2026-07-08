# Descriptor Dictionary

One row per descriptor: definition, computation method, unit, source. Keep in sync with `fragment_schema.json` — this table goes (excerpted) into the paper.

| Descriptor | Category | Definition | Method | Unit | Source |
|---|---|---|---|---|---|
| obb_dims | geometric | Oriented bounding box dimensions | PCA on vertices | mm | computed |
| volume | geometric | Mesh volume (watertight or hull fallback) | trimesh | m³ | computed |
| convexity | geometric | volume / convex hull volume | trimesh | – | computed |
| mass_est | geometric | volume x 2400 kg/m³ | derived | kg | pseudo→measured |
| planarity (per region) | geometric | RANSAC plane fit RMS over segmented region | RANSAC | mm | computed |
| curvature_stats | geometric | Discrete mean/Gaussian curvature histogram | per-vertex | 1/mm | computed |
| roughness_coarse | surface | RMS deviation from region plane, radius ≥ 20 mm | neighbourhood filter | mm | computed |
| roughness_fine | surface | RMS deviation, radius < 5 mm | neighbourhood filter | mm | computed |
| colour_entropy | surface | Shannon entropy of UV texture crop per region | scikit-image | bits | computed |
| texture_class | surface | Semantic label(s) per face region | vision API, fixed taxonomy | – | ai-annotated |
| connection_strategy | procedural | Linked from planarity + surface condition | rule (documented) | class | derived |
| handling_class | procedural | Linked from mass + OBB dims | rule (documented) | class | derived |
| design_assignment | procedural | Linked from region semantic labels | rule (documented) | class | derived |

## Texture taxonomy (draft — derive from Study 1 spolia criteria, review with supervisors)

formwork_imprint, fracture_surface, weathered, exposed_aggregate, rebar_visible, staining, original_finish
