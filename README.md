# Study 2 — Fragment Descriptor Pipeline

A computational pipeline that extracts multi-dimensional descriptors from 3D scans of demolition concrete fragments and structures them into a queryable per-fragment record. It operationalizes the information requirements derived from Study 1 (the IASS case study) into a machine-readable descriptor schema, and is demonstrated on real Study 1 fragment scans.

Implemented as **Blender** (mesh cleaning, UV unwrap, texture bake, UNSCANNED marking) + **standalone Python** (trimesh / open3d geometry, GPT-4o vision) + an **HTML / Three.js** report viewer. (The earlier Rhino 8 + Grasshopper plan is superseded; `02_gh/` is unused.)

## What it extracts

- **Geometric descriptors** (deterministic): oriented bounding box, volume, convexity, estimated mass, RANSAC planar regions (area, fit RMS, normal), multi-scale curvature.
- **Surface descriptors** (evaluated, and NOT exceeding a null baseline — see below): roughness, colour entropy, and a configurable multi-label feature vocabulary classified by GPT-4o with multi-run majority voting. Classification is **region-based**: RANSAC planes and fracture clusters are segmented first, each region's UV footprint is cut out of the texture atlas, and the crops are classified individually. Features live in `env/taxonomy.json` and are managed with `03_src/taxonomy_tool.py`; one can be added, retired or removed without touching code. Nothing in the vocabulary competes: a region carries every feature that applies, and the vocabulary is bounded by what the capture resolves, so labels needing evidence finer than the texel density (`crack`, `spalling`, `weathered`) are retired with the reason recorded. Optional **calibration by exemplar** (`01_input/reference_surfaces/`) sends labelled crops from this same building ahead of the regions, so the categories are defined by samples rather than by wording alone.
- **Scan-coverage flagging**: the ground-contact face is never scanned; the UNSCANNED method marks the reconstructed region, flags matching RANSAC planes as `scan_reliable: false`, and excludes it from surface classification.
- **Procedural linkage** (computed, flagged `data_status: proposed`): `handling_class`, `drill_zone`, `connection_strategy`, `design_assignment`, `finishing_requirement`, plus candidate uses. Encoded in `env/design_factors.json` and executed into every record, so they are queryable alongside the measured descriptors. The thresholds come from Study 1 and general practice and are not expert-verified.

## Validation status — read this before trusting the surface labels

The **geometric** half is verified: oriented bounding box, volume and mass recompute exactly
from the mesh, and the design factors trace to measured values.

The **surface** half was measured on 26 blind-sampled, hand-labelled held-out tiles against a
null model that answers the two commonest features and looks at nothing:

| | recall | precision |
|---|---:|---:|
| null model | 80% | **75%** |
| the classifier | 80% | **66%** |

It does not exceed the null model. Two frequent features are recovered at rates a constant
guess already achieves; the distinctive ones are not found. Asking one yes/no question per
feature instead of a list moved `brick_inclusion` from 0 of 5 to 2 of 5, which is the only
evidence here that the model can identify a distinctive inclusion.

`drill_zone` and `finishing_requirement` are **on hold**: both read `rebar_visible`, which the
classifier has never reported, so "no bars visible" is an untested negative and must not be
used as drilling guidance.

Full evidence and what it licenses you to claim: `04_schema/CLASSIFIER_BEHAVIOUR.md`.
Paper consequences: `paper_draft/SCOPE_REVISION_2026-08-20.md`.

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
