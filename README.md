# Study 2 — Fragment Descriptor Pipeline

A computational pipeline that extracts multi-dimensional descriptors from 3D scans of demolition concrete fragments and structures them into a queryable per-fragment record. It operationalizes the information requirements derived from Study 1 (the IASS case study) into a machine-readable descriptor schema, and is demonstrated on real Study 1 fragment scans.

Implemented as **Blender** (mesh cleaning, UV unwrap, texture bake, UNSCANNED marking) + **standalone Python** (trimesh / open3d geometry, GPT-4o vision) + an **HTML / Three.js** report viewer. (The earlier Rhino 8 + Grasshopper plan is superseded; `02_gh/` is unused.)

## What it extracts

- **Geometric descriptors** (deterministic): oriented bounding box, volume, convexity, estimated mass, RANSAC planar regions (area, fit RMS, normal), multi-scale curvature.
- **Surface descriptors**: roughness, colour entropy, and a seven-class surface taxonomy (`formwork_imprint`, `fracture_surface`, `exposed_aggregate`, `rebar_visible`, `weathered`, `staining`, `original_finish`) classified by GPT-4o with multi-run majority voting, then localized via an 8×8 grid over the UV texture and reprojected to the 3D mesh.
- **Scan-coverage flagging**: the ground-contact face is never scanned; the UNSCANNED method marks the reconstructed region, flags matching RANSAC planes as `scan_reliable: false`, and excludes it from surface classification.
- **Procedural linkage** (schema + proposed rules, not yet computed): `connection_strategy`, `handling_class`, `design_assignment`, linking descriptors to encoded domain knowledge of handling and design implications.

## Data status

Geometric and surface descriptors are computed from real Study 1 scans. Attributes not yet measurable (concrete class, reinforcement) are carried as flagged `pseudo` entries; encoded procedural knowledge is provisional pending expert verification. Every descriptor field records its computation method and data status.

## Toolchain / workflow

```
Scaniverse (iPad, LiDAR-assisted photogrammetry)  → raw textured mesh (.glb)
Blender (bake_texture_v2.py, export_fragment_v2.py) → cleaned GLB + texture PNG + UNSCANNED sidecar
Python  (03_src/run_pipeline.py)                    → geometry + GPT-4o vision → per-fragment JSON + HTML report
        (03_src/scan_coverage.py)                   → applies scan_reliable flags from the sidecar
```

See `WORKFLOW.md` for the per-fragment procedure and `HANDOVER.md` for the current implementation detail.

## Fragment ID convention

`FRAG-S1-{ARCHETYPE}-{###}` (e.g. `FRAG-S1-FS-006`). Archetype codes (FS floor slab, WL load-bearing wall, CO column, etc.) are assigned at physical inspection; `###` resets per archetype. Registry in `01_input/fragments_manifest.csv`.

## Setup

```powershell
cd "Study2_Descriptor_Pipeline"
python -m venv env\venv          # first time only
env\venv\Scripts\activate         # every session
pip install -r env/requirements.txt   # first time only
```

Copy `env/.env.example` → `env/.env` and add `OPENAI_API_KEY` (gitignored; never commit `.env`).

Run:
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-006          # geometry + AI + report
python 03_src/run_pipeline.py FRAG-S1-FS-006 --geometry-only   # no API key needed
python 03_src/scan_coverage.py FRAG-S1-FS-006         # apply UNSCANNED flags
```

## Key documents

- `HANDOVER.md` — current implementation state and design decisions.
- `WORKFLOW.md` — when to do what, per fragment.
- `COMMANDS.md` — quick command reference.
- `PLAN_Study2.md` — original realization plan (some parts superseded).
- `04_schema/fragment_schema.json`, `04_schema/descriptor_dictionary.md`, `feature_hierarchy.csv` — the descriptor schema.
- `paper_draft/` — EKA full-paper section drafts (outline, intro, objectives/methodology, Study 1 recap, pipeline, validation method, discussion/outlook).
