# Handover Document — Study 2 Descriptor Pipeline
**Date:** 2026-07-21 · **Updated:** 2026-08-10  
**Project:** Muchen Yan — PhD, i.sd, University of Innsbruck  
**Repo:** `Study2_Descriptor_Pipeline`

---

## 1. PhD and Research Context

Muchen's PhD is on nose-to-tail cascading reuse of demolition concrete. The research follows a practice-led trajectory across two sequential studies:

**Study 1** — an urban furniture commission executed as a Research-through-Design case study. Concrete rubble (cast-in-place, ~1920 building, ~20 fragments, 0.5–2 m) was collected from a deconstruction site, digitised via photogrammetry, and used to produce two prototypes in active public use in a community garden at a student housing complex. A 6-stage workflow was developed: Collection & Digitisation → Design Development → Concrete Assembly → As-Built Adaptation → Timber Fabrication → Final Assembly. A retrospective gap analysis identified 11 information gaps across structural, aesthetic, and procedural dimensions, from which an Information Requirements Scheme (IRS) was derived.

**Study 2** (this repo) — a computational descriptor pipeline that takes Study 1 photogrammetry meshes and photographs as input, extracts multi-dimensional descriptors (geometric + surface character), and connects them to the procedural and performance attributes identified as gaps in Study 1. Currently demonstrated as proof-of-concept using pseudo data; real Study 1 fragment data is the next validation target.

**Active paper deadlines:**
- **EKA Extended Abstract** — deadline Thu 24 July 2026. Covers both Study 1 and Study 2. Two reviewers returned comments (scores 67 and 71). Key reviewer comment: *"Future work should focus on validating the computational pipeline with real project data and further demonstrating its applicability in practice."*
- **IASS 2026 full paper** — already accepted, covers Study 1 only, presented September 2026.

---

## 2. Repo Structure

```
Study2_Descriptor_Pipeline/
├── 01_input/
│   ├── meshes/processed/{FRAG_ID}/     ← GLB, texture PNG, scan_coverage.json (per fragment)
│   ├── photogrammetry/raw_exports/     ← raw photogrammetry OBJ exports
│   └── fragments_manifest.csv          ← fragment registry
├── 02_blender/
│   ├── bake_texture.py                 ← remesh + bake + export (original, unchanged)
│   ├── bake_texture_v2.py              ← same + UNSCANNED vertex group sidecar (NEW)
│   ├── export_fragment.py              ← direct GLB export (original, unchanged)
│   └── export_fragment_v2.py           ← same + UNSCANNED vertex group sidecar (NEW)
├── 03_src/
│   ├── run_pipeline.py                 ← main entry point (geometry + AI + report)
│   ├── scan_coverage.py                ← post-process: flag unscanned RANSAC planes (NEW)
│   ├── report.py                       ← HTML report generator
│   ├── descriptors/
│   │   ├── geometry.py                 ← OBB, volume, RANSAC planes, curvature
│   │   └── feature_texture.py          ← per-label highlight texture images
│   └── ai/
│       ├── taxonomy.py                 ← shared label loader (from env/taxonomy.json)
│       ├── vision_client.py            ← GPT-4o vision classification
│       └── texture_segmentation.py     ← Phase 3B grid spatial localisation
├── 04_schema/
│   ├── fragment_schema.json
│   └── descriptor_dictionary.md
├── 05_output/descriptors/              ← per-fragment JSON + HTML + viewer JSON + GLB copy
├── 06_validation/
│   └── study1_decisions.md             ← template for retrospective validation (empty)
├── env/
│   ├── .env                            ← OPENAI_API_KEY — NEVER commit to git
│   ├── .env.example                    ← committed placeholder
│   ├── taxonomy.json                   ← surface label definitions + colours
│   └── venv/                           ← Python virtualenv
├── COMMANDS.md                         ← quick-start command reference
├── CHANGELOG.md                        ← version history (has some old IDs — acceptable)
└── HANDOVER.md                         ← this file
```

---

## 3. Fragment ID Format

```
FRAG-S1-{ARCHETYPE}-{###}
```

Archetype is assigned at physical inspection; `###` resets per archetype.

| Code | Archetype | Code | Archetype |
|---|---|---|---|
| `FS` | Floor Slab | `RS` | Roof Slab |
| `BM` | Beam | `CO` | Column |
| `WL` | Load-bearing Wall | `WP` | Partition Wall |
| `LT` | Lintel | `ST` | Stair |
| `BL` | Balcony | `FP` | Facade Panel |
| `FD` | Foundation | `UN` | Unidentified |

**Current fragment status:**

| ID | Archetype | Status (2026-08-10) |
|---|---|---|
| FRAG-S1-FS-001 | Floor Slab | geometry-only descriptors (no AI run yet) |
| FRAG-S1-FS-002 | Floor Slab | processed — descriptors + feature map complete |
| FRAG-S1-FS-003 | Floor Slab | processed — descriptors + feature map complete; UNSCANNED sidecar |
| FRAG-S1-FS-004 | Floor Slab | processed — descriptors + feature map complete |
| FRAG-S1-FS-005 | Floor Slab | processed — descriptors + feature map complete |
| FRAG-S1-FS-006 | Floor Slab | processed — descriptors + feature map complete; UNSCANNED verified |

---

## 4. Environment Setup

```powershell
cd "C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"
env\venv\Scripts\activate
```

**IMPORTANT:** `env/.env` contains `OPENAI_API_KEY` and must NEVER be committed to git. Only `env/.env.example` is tracked.

---

## 5. Standard Pipeline Workflow (per fragment)

### Step A — Blender (bake + export)

1. Import photogrammetry mesh into Blender
2. Clean mesh (delete floor plane, stray artifacts)
3. Close the ground-contact hole manually: Edit Mode → select boundary edge loop (Alt+Click) → F to fill
4. **NEW:** Assign UNSCANNED vertex group to the closed faces:
   - The filled faces are already selected after step 3 — don't click away
   - Properties → Object Data Properties → Vertex Groups → `+` → name `UNSCANNED` → Assign
   - Verify: deselect all (Alt+A) → select UNSCANNED group → click Select → closed patch should highlight
5. Select cleaned mesh in viewport
6. Run **`02_blender/bake_texture_v2.py`** (set `FRAG_ID` at top first)
   - This remeshes, bakes texture, exports GLB, and writes `_scan_coverage.json` sidecar from the vertex group before the remesh destroys the topology

### Step B — Python pipeline

```powershell
env\venv\Scripts\activate
python 03_src/run_pipeline.py FRAG-S1-FS-003
```

`run_pipeline.py` runs geometry descriptors + GPT-4o vision + HTML report, and now reads the `_scan_coverage.json` sidecar automatically (RANSAC planes matching the unscanned face normal are flagged `scan_reliable: false`; UNSCANNED texture cells are excluded from AI classification). `scan_coverage.py` still works as a standalone re-annotator: `python 03_src/scan_coverage.py FRAG-S1-FS-003`.

### Step C — Git commit

```powershell
git add 01_input/meshes/processed/FRAG-S1-FS-003/
git add 05_output/
git commit -m "data: descriptors FRAG-S1-FS-003"
```

---

## 6. The UNSCANNED Face Problem (designed this session)

**Problem:** Photogrammetry scans fragments lying on the ground — the bottom (ground-contact) face is never captured. The mesh reconstruction software fills the hole with either repeated UV texture or a low-res interpolation. Both produce false surface character data that can pollute descriptor outputs, especially RANSAC plane detection and AI surface label classification.

**Solution designed:**

1. **User marks in Blender:** Assign a vertex group named `UNSCANNED` to the manually-closed ground-contact faces on the original mesh.

2. **`bake_texture_v2.py`** reads the vertex group BEFORE the voxel remesh (which destroys all topology), extracts the average face normal + centroid + face count, and writes `{FRAG_ID}_scan_coverage.json` to the fragment's input folder.

3. **`scan_coverage.py`** (run after `run_pipeline.py`) reads the sidecar, compares the unscanned normal against each RANSAC plane normal using dot product, and flags planes within 25° as `scan_reliable: false`. Adds a `scan_coverage` block to the geometry JSON.

**Why material assignment won't work:** The voxel remesh in `bake_texture.py` creates entirely new topology — material assignments on the original mesh don't survive. Vertex group reading must happen before the remesh step, which is why v2 scripts were created rather than modifying originals.

**Pending integration:** `scan_coverage.py` currently runs as a separate command. The cleaner solution (not yet implemented) is to refactor it to expose an `annotate()` function and call it automatically from the end of `run_single()` in `run_pipeline.py` whenever a sidecar exists. This would reduce the workflow to one command.

---

## 7. Feature Map Spatialization (implemented this session)

### Problem
The original Feature Map overlay in the 3D mesh viewer coloured individual mesh faces by their UV grid cell label. Because Smart UV Project creates many small scattered UV islands, adjacent 3D faces often map to completely different UV cells — producing fragmented triangular patches with no spatial coherence.

### Solution: 3D spatial majority-vote

**Python (`run_pipeline.py` — `build_viewer_data`):**

1. Divide the mesh XZ bounding box into an 8×8 grid of spatial cells (same grid_n as the texture grid).
2. For each mesh vertex, look up its UV-grid label (`cells[ugr][ugc]`) and vote for its XZ spatial cell.
3. Dominant label per spatial cell wins (`dom_label`).
4. Sampled point cloud points are assigned `feature_id` by their XZ spatial cell, not by UV.
5. UNSCANNED points (region_id == VIEWER_UNSCANNED_ID = 100) are explicitly set to `feature_id = -1`.

**JavaScript (`report.py` — `_buildSpatialLabels` / `_applyFeatureVertexColors`):**

Same logic runs in the browser on the loaded GLB mesh. `_buildSpatialLabels()` traverses all mesh vertices, bins them into XZ spatial cells using world-space coordinates, and elects a dominant label per cell. `_applyFeatureVertexColors(targetLabel)` paints each vertex by its XZ cell's dominant label. Result: clean rectangular blocks that match the physical surface layout.

### UNSCANNED exclusion from texture classification

Before the grid is sent to the AI, `build_unscanned_texture_mask()` identifies the UNSCANNED face by the same normal + position filter used in `build_viewer_data`, rasterises its UV triangles into a binary 1080×1080 mask, and `_mask_to_excluded_cells()` converts that to a set of (row, col) grid cells where ≥50 % of pixels are masked. Those cells are set to `None` in `grid_data["cells"]` before the AI call and before the spatial vote — so the fake bottom-face texture is invisible to both the AI classifier and the 3D viewer colour logic.

### Point format change

Viewer JSON points changed from 4-element `[x, y, z, region_id]` to 5-element `[x, y, z, region_id, feature_id]`. JS reads `(p.length >= 5) ? p[4] : -1` for backward compatibility with old viewer JSONs.

### Verified on FRAG-S1-FS-006

The 8×8 grid came out as:
```
Row 0:  F  F  F  F  F  F  F  F    ← formwork_imprint (smooth top surface)
Row 1:  F  F  F  F  F  F  F  .    ← . = UNSCANNED cell (cleared)
Row 2:  E  E  E  E  E  E  E  .
Row 3:  E  E  E  E  E  E  E  .    ← exposed_aggregate (fractured edges)
Rows 4-7:  all E
```
3 cells cleared (col 7, rows 1–3) — the small UV island of the manually filled bottom face. 455 of 2000 sampled points assigned feature_id = -1. The 2-label result (formwork_imprint + exposed_aggregate) is **correct** for a floor slab fragment: the top surface was cast against formwork; all other visible faces are fracture surfaces.

### Key constant

`VIEWER_UNSCANNED_ID = 100` — sentinel `region_id` assigned to UNSCANNED points in the viewer JSON so the JS can colour them grey-blue.

---

## 8. Pipeline Output Schema (geometry JSON)

Output: `05_output/descriptors/{FRAG_ID}_geometry.json`

Key top-level fields:
```json
{
  "fragment_id": "FRAG-S1-FS-003",
  "archetype": "FS",
  "archetype_label": "Floor Slab",
  "input_type": "mesh",
  "bounding": { "obb_dims_mm": [...], "volume_mm3": ..., "mass_kg_est": ..., "watertight": ... },
  "planarity": [
    {
      "normal_xyz": [...],
      "area_m2_est": ...,
      "fit_rms_mm": ...,
      "scan_reliable": true,          ← added by scan_coverage.py
      "angle_to_unscanned_deg": ...   ← added by scan_coverage.py
    }
  ],
  "curvature": { "fine_mm": {...}, "coarse_mm": {...} },
  "vision": {
    "dominant_label": "formwork_imprint",
    "labels_present": [...],
    "surface_condition": "good",
    "confidence": "high",
    "grid_classification": {...}       ← Phase 3B spatial localisation
  },
  "scan_coverage": {                   ← added by scan_coverage.py
    "has_unscanned_face": true,
    "unscanned_avg_normal": [...],
    "angle_threshold_deg": 25.0,
    "data_status": "annotated"
  }
}
```

---

## 8. Surface Taxonomy

Labels defined in `env/taxonomy.json`. Loaded by `03_src/ai/taxonomy.py` (single source of truth — edit JSON, not Python).

| Label | Description |
|---|---|
| `formwork_imprint` | Cast face; smooth, shows mould texture |
| `fracture_surface` | Internal concrete exposed by demolition break; rough |
| `exposed_aggregate` | Coarse aggregate visible at surface |
| `rebar_visible` | Steel reinforcement exposed |
| `weathered` | Carbonated, eroded, surface-degraded |
| `staining` | Rust, moss, oil, paint, or contamination |
| `original_finish` | Intentional architectural finish (tile, plaster, render) |

---

## 9. Pending Tasks

### Done since 2026-07-21

- ~~Run pipeline on FRAG-S1-FS-003 and FRAG-S1-FS-004~~ — done; FS-005 also processed. All of FS-001 to FS-006 have descriptor output (FS-001 geometry-only).
- ~~Integrate `scan_coverage.py` into `run_pipeline.py`~~ — done; sidecar is read automatically before Phase 3B, standalone script kept as re-annotator.
- ~~Delete `debug_unscanned.py`~~ — deleted 2026-08-10.

### Immediate

- **EKA full paper:** section drafts in `paper_draft/` (on hold; current focus is application development)
- **Run AI classification on FRAG-S1-FS-001** (currently geometry-only)

### Near-term

- **Retrospective validation study:** Run pipeline on all ~20 Study 1 fragments (meshes already exist from photogrammetry). Compare pipeline descriptor outputs against documented design decisions from Study 1 project records (which fragments were selected, why, which faces were used for connections). Three validation axes:
  1. Surface labels ↔ aesthetic selection (formwork_imprint / original_finish → preferred fragments)
  2. Planarity of faces ↔ connection zone decisions (which faces were actually connected on site)
  3. Mass estimate ↔ handling classification (excavator vs. hand placement records)
- **Update `06_validation/study1_decisions.md`:** Fill in the decision table from Study 1 project records

### Git state (2026-08-10)

Outstanding code, docs, and text outputs were committed on `feature/feature-labels-viewer` on 2026-08-10. Binary data files (GLB/PNG, git-lfs) for FS-005/006 inputs and FS-003 to 006 outputs still need `git add` and push from a terminal with git-lfs and GitHub credentials. `main` is local-only and behind; merge and push once the feature branch is verified.

---

## 10. Key Technical Decisions (rationale)

| Decision | Why |
|---|---|
| Vertex group (not material) for UNSCANNED | Voxel remesh destroys all face-level data; vertex group must be read before remesh |
| scan_coverage.py as separate script (not in run_pipeline.py) | Non-destructive addition; run_pipeline.py continues to work for all existing fragments without change |
| bake_texture_v2.py as new file (not edit of original) | Existing fragments don't have vertex group; original script must continue to work unchanged |
| GLB as primary mesh format (over OBJ) | Preserves UV + texture in single file; required for Three.js viewer in HTML report |
| HTTP server for report (not file://) | GLB + Three.js and feature textures fail on file:// due to CORS; run_pipeline.py --serve starts SimpleHTTPRequestHandler |
| FRAG-S1-{ARCHETYPE}-{###} ID format | Encodes structural origin at ID level; archetype parsed by pipeline automatically |
| taxonomy.json as single source of truth | Labels used by both AI vision prompt and report renderer; one edit location |
| 3D XZ spatial grid (not UV→cell) for feature colouring | Smart UV Project creates many scattered UV islands; adjacent 3D faces map to different UV cells; XZ spatial majority-vote gives coherent rectangular blocks |
| Vertex colours (not texture PNG) for Feature Map overlay | Texture PNG approach required per-label texture loads and CORS-safe serving; vertex colours work directly on the GLB with no extra files |
| `abs()` in UNSCANNED normal filter | Catches both downward-pointing bottom face AND upward-pointing top face; position filter then separates them by Y height |
| 5-element points `[x,y,z,region_id,feature_id]` | Adds feature label per point while keeping backward compat; JS checks `p.length >= 5` |
| `VIEWER_UNSCANNED_ID = 100` as sentinel | Avoids collision with real RANSAC region IDs (0-indexed); lets JS paint grey-blue without extra flag |

---

## 11. Files to Read at Session Start

1. `COMMANDS.md` — quick command reference
2. `03_src/run_pipeline.py` — understand full pipeline flow
3. `02_blender/bake_texture_v2.py` — current Blender workflow
4. `env/taxonomy.json` — surface labels
5. This file (`HANDOVER.md`)

**Do not read:**
- `env/.env` — contains API key, never commit
- `env/venv/` — virtualenv, not source code
