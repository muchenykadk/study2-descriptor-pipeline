# Descriptor Dictionary

One row per descriptor: definition, computation method, unit, source. Keep in sync with `fragment_schema.json` — this table goes (excerpted) into the paper.

| Descriptor | Category | Definition | Method | Unit | Source |
|---|---|---|---|---|---|
| obb_dims | geometric | Oriented bounding box dimensions | PCA on vertices | mm | computed |
| volume | geometric | Mesh volume (watertight or hull fallback) | trimesh | m³ | computed |
| convexity | geometric | volume / convex hull volume | trimesh | – | computed |
| mass_kg_est | geometric | volume × 2500 kg/m³. EN 1991-1-1 Annex A Table A.1 gives 25 kN/m³ for concrete with normal reinforcement, 24 for plain; these fragments are reinforced. Was 2400 until 2026-08-25. | derived | kg | provisional on the density until a fragment is weighed |
| planarity (per region) | geometric | RANSAC plane fit RMS over segmented region | RANSAC | mm | computed |
| curvature_stats | geometric | Discrete mean/Gaussian curvature histogram | per-vertex | 1/mm | computed |
| fit_rms_mm | surface | RMS deviation of a region's points from its fitted plane. This is the roughness measure; `roughness_coarse` and `roughness_fine` were listed here for a year and never implemented, and this field is what they described. | RANSAC plane residual | mm | measured |
| curvature.fine_mm / coarse_mm | surface | Normal deviation over 20 mm and 60 mm radii, as mean, sd and quartiles. Overall form and surface texture, not defect detection: at 10,000 samples over ~4 m² the spacing is ~20 mm. | KDTree neighbourhood | rad | measured |
| colour_entropy_bits | surface | Shannon entropy of the region's colour distribution, RGB quantised to 64 bins. 0 for a flat colour, 6 at maximum. Per region, so a face-level design rule can read it. | `region_colour_entropy` | bits | measured |
| texture_class | surface | One label per segmented region | vision API, configurable taxonomy | – | ai-annotated |
| connection_strategy | procedural | Linked from planarity + surface condition | rule (documented) | class | derived |
| handling_class | procedural | Linked from mass + OBB dims | rule (documented) | class | derived |
| design_assignment | procedural | Linked from region semantic labels | rule (documented) | class | derived |
| drill_zone | procedural | Section depth + exposed reinforcement | rule (documented) | class | derived |
| finishing_requirement | procedural | Surface label, anomalies, curvature | rule (documented) | class | derived |

## Texture taxonomy

**The list is no longer fixed here.** It lives in `env/taxonomy.json` and is managed with
`03_src/taxonomy_tool.py` (`list`, `check`, `add`, `retire`, `remove`). Reproducing it in
this file only guarantees the two drift apart.

```powershell
python 03_src/taxonomy_tool.py list
```

Two properties of that file matter when reading old records:

- **The order of `labels` is each label's integer `feature_id`**, stored in every
  `*_viewer.json`. New labels are appended; nothing is inserted mid-array.
- **A retired label keeps its id.** It leaves the prompt and the interface but still
  resolves for data already written, so a record from an earlier run stays readable.

See `04_schema/TAXONOMY_REVIEW.md` for where the categories come from, why they overlap,
and the open question of splitting them into origin / exposure / condition.
