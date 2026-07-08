# Changelog

Format: `[version] YYYY-MM-DD — description`  
Versions: `v0.x` = pre-release development, `v1.0` = first full fragment processed end-to-end.

---

## [v0.2] 2026-07-08 — Grill complete, pipeline scaffold updated

### Decided
- Mesh library: trimesh (bounding) + open3d (planarity, curvature)
- Architecture A: standalone Python scripts, no analysis inside Rhino runtime
- Blender → Rhino transfer via .glb (textures embedded)
- Texture source: photogrammetry PNG used directly, no re-rendering
- View strategy: UV crops per planar region (Phase 3), no Blender renders for analysis
- Vision API: Anthropic primary, switchable via `VISION_PROVIDER` in `.env`
- AI-classified features: rebar, surface_origin_type, defect_presence, weathering_severity
- Human annotation: direct JSON edit now, `annotate.gh` when > 3 fragments
- Pipeline trigger: manual CLI with documented trigger points (see WORKFLOW.md)

### Added
- `WORKFLOW.md` — step-by-step workflow with trigger points and git conventions
- `.gitignore`, `.gitattributes` (git-lfs for binary assets)
- `CHANGELOG.md`
- `__init__.py` in all `03_src` subpackages
- `open3d` added to `env/requirements.txt`
- `env/.env.example` with `VISION_PROVIDER` and `VISION_MODEL`
- `01_input/meshes/processed/FRAG-S1-001/` folder ready for Blender export
- `03_src/run_pipeline.py` — main entry point
- Implemented `geometry.py`: bounding_descriptors, planar_regions, curvature_stats

---

## [v0.1] 2026-06-12 — Initial scaffold

### Added
- Folder structure (01_input → 06_validation)
- `PLAN_Study2.md`, `README.md`
- `fragment_schema.json`, `descriptor_dictionary.md`
- `geometry.py`, `vision_client.py` stubs
- `fragments_manifest.csv`
- Photogrammetry folder structure (`raw_exports/`, `projects/`)
- First raw scan: `FRAG-S1-001/concrete_scan.obj`
