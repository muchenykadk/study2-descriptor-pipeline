# Changelog

Format: `[version] YYYY-MM-DD — description`  
Versions: `v0.x` = pre-release development, `v1.0` = first full fragment processed end-to-end.

---

## [v1.0] 2026-08-10 — Six real fragments end-to-end; UNSCANNED handling; spatial feature map

### Added
- `02_blender/bake_texture_v2.py`, `export_fragment_v2.py` — write `_scan_coverage.json` sidecar from the `UNSCANNED` vertex group before remesh
- `03_src/scan_coverage.py` — flags RANSAC planes matching the unscanned face normal as `scan_reliable: false`; integrated into `run_pipeline.py` (auto-runs when a sidecar exists), kept as standalone re-annotator
- UNSCANNED texture-mask exclusion: masked grid cells removed before AI classification and spatial vote
- 3D spatial majority-vote feature map (8×8 XZ grid, vertex colours) replacing UV→cell mapping; per-point `feature_id` in viewer JSON (5-element points)
- Archetype system: `FRAG-S1-{ARCHETYPE}-{###}` IDs parsed and shown in reports
- `--batch`, `--force`, `--serve`, `--ransac-threshold` CLI flags; inventory `index.html` with 3D viewers
- `04_schema/feature_hierarchy.csv`
- Fragments FRAG-S1-FS-001 … 006 processed (001 geometry-only); UNSCANNED verified on FS-003/FS-006

### Changed
- Rhino / Grasshopper stage superseded; `02_gh/` unused
- Vision provider: GPT-4o with multi-run majority voting

### Removed
- `debug_unscanned.py` (temporary diagnostic)

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
