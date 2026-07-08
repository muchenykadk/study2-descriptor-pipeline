# Study 2 — Descriptor Extraction Pipeline: Realization Plan

**Working doc** (source of truth). Status: v0.1 — 2026-06-12
**Basis:** EKA extended abstract, Section 5. Environment: Rhino 8 + Python 3 (CPython in ScriptEditor/GH), cloud vision APIs for texture classification & semantic annotation.

---

## Goal restated

Prototype a pipeline that takes Study 1 photogrammetry meshes + texture maps + photographs and extracts:

1. **Geometric descriptors** — planarity, curvature, bounding geometry
2. **Surface character descriptors** — roughness, colour entropy, texture classification via semantic mesh annotation
3. **Composite descriptors** — combined, supporting design-stage inventory queries

…and links them to Study 1's procedural/performance attributes (connection strategy, machinery handling, design assignment). Proof-of-concept with **pseudo data**; validated by checking whether computed characterization recovers the designer's Study 1 selection logic.

---

## Phase 0 — Tools setup (Week 1)

| Tool | Purpose | Setup |
|---|---|---|
| Rhino 8 + Grasshopper | Host CAD environment, mesh handling, visualization | Already licensed; update to latest SR |
| ScriptEditor (CPython 3.9) | Python 3 components inside GH | Built-in; `# r:` requirements lines auto-install pip packages |
| numpy / scipy | Point-based analysis, PCA, statistics | `# r: numpy scipy` |
| open3d or trimesh | Mesh sampling, normals, OBB, RANSAC plane segmentation | `# r: trimesh` (lighter, pure-python deps) — fall back to open3d via external venv if needed |
| scikit-image | Colour entropy from texture maps | `# r: scikit-image` |
| anthropic / openai SDK | Vision API calls for texture classification + semantic labels | `# r: anthropic`; API key in `env/.env`, never in GH file |
| Git | Version control on `03_src/` and `02_gh/` | Repo at folder root; GH files saved as .ghx (XML) for diffability where practical |

**Checkpoints:** a GH canvas with a CPython component that imports numpy+trimesh and round-trips a Rhino mesh; one successful vision API call returning JSON.

## Phase 1 — Data preparation (Week 1–2)

1. Collect Study 1 assets into `01_input/`: photogrammetry exports (.obj + texture .png) → `photogrammetry/raw_exports/FRAG-S1-###/`, software project files → `photogrammetry/projects/`, per-fragment photographs → `photos/FRAG-S1-###/`.
2. Mesh hygiene script: unify units (mm), repair/close where possible, record vertex count, decimate to analysis resolution (~50–100k faces) → `meshes/processed/FRAG-S1-###/`. Raw exports stay untouched.
3. Build `fragments_manifest.csv`: ID, source files, scan quality notes, known mass/dimensions if recorded.
4. **Pseudo data:** for attributes not yet measurable (e.g., rebar presence, compressive class, actual mass), define plausible value ranges and generate per-fragment pseudo entries, flagged `"data_status": "pseudo"` in the schema so real data can replace them later without structural change.

## Phase 2 — Geometric descriptors (Week 2–4)

Per fragment, Python component(s) compute:

- **Bounding geometry:** oriented bounding box (PCA), dimensions, volume, convex hull volume, rectangularity/convexity ratios, estimated mass (volume x 2400 kg/m³, flagged pseudo until weighed).
- **Planarity:** RANSAC plane segmentation → candidate flat faces; per face: area, fit RMS deviation, normal orientation. Output the top-N planar regions as the "usable face" set (these drive connection strategy and seating orientation).
- **Curvature:** per-vertex discrete curvature (mean/Gaussian) on the decimated mesh; aggregate to histogram + summary stats per face region and whole fragment.

Output: one `FRAG-S1-###_geometry.json` per fragment + GH preview (colour-coded planar regions, OBB display) for figures.

## Phase 3 — Surface character descriptors (Week 4–6)

- **Roughness:** deviation of vertices from their fitted plane within each planar region (RMS, peak-to-valley) — multi-scale: coarse (cm, fracture topology) vs. fine (mm, texture), separated by neighbourhood radius.
- **Colour entropy:** Shannon entropy on the texture map per face region (UV-mapped crop), plus mean colour, variance — proxies for weathering/staining heterogeneity.
- **Texture classification / semantic annotation (cloud vision):**
  1. Render 4–8 calibrated views per fragment (and per major face region) from the textured mesh in Rhino.
  2. Send views to vision API with a fixed taxonomy prompt: {formwork imprint, fracture surface, weathered, exposed aggregate, rebar visible, staining, original finish, …} → structured JSON labels + confidence.
  3. Map labels back onto mesh face regions (semantic mesh annotation); store per-region label sets.
  4. Cache every API response in `05_output/ai_cache/` keyed by image hash — reproducibility + cost control.

**Design decision to log:** taxonomy is the aesthetic vocabulary of the paper — derive it from the spolia criteria used in Study 1, not ad hoc.

## Phase 4 — Composite descriptors + schema (Week 6–8)

1. Formalize the **data requirements schema** from Study 1's gap analysis as JSON Schema (`04_schema/fragment_schema.json`): three blocks — structural, aesthetic, procedural — each field annotated with source (`computed | measured | pseudo | ai-annotated`).
2. Implement the linking rules as explicit, documented functions:
   - planarity + surface condition → **connection strategy** class (e.g., direct bolt / adaptive bracket / no-drill)
   - mass + OBB dims → **machinery handling** class (manual / 2-person / excavator, grab type)
   - face-region semantic labels → **design assignment** (show-face vs. seat-face vs. buried)
3. Composite descriptors = derived fields combining geometry + surface (e.g., "display value" = planar area x texture-interest score) to support inventory queries.

## Phase 5 — Inventory + query interface (Week 8–9)

- Aggregate all fragment JSONs into a queryable inventory (`05_output/inventory/inventory.json` + CSV mirror).
- GH definition `inventory_query.gh`: filter/sort sliders + value lists over descriptor fields, live 3D gallery of matching fragments. This is the "design-stage inventory query" demonstrator for the paper.

## Phase 6 — Validation against Study 1 (Week 9–11)

1. From Study 1 records, reconstruct the documented selection decisions: which fragments chosen for which position, and the stated/implicit reasons.
2. Encode each decision as a query over the schema (e.g., "seat fragment: large planar top face, low roughness, mass < excavator limit").
3. Run queries on the pipeline output → compare ranked results with actual choices. Report agreement/divergence per decision; divergences are findings (either missing descriptor or tacit knowledge → discussion section).
4. Write up as the assessment subsection; this closes objective 4.

## Phase 7 — Documentation & paper integration (Week 11–12)

- Pipeline diagram (Fig. for Study 2, mirroring Fig. 1 style), descriptor table, schema excerpt, query-vs-decision comparison table.
- Freeze code state (git tag), export figure renders to `06_validation/figures/`.

---

## Folder structure

```
Study2_Descriptor_Pipeline/
├── PLAN_Study2.md                  ← this doc
├── README.md
├── env/
│   ├── requirements.txt
│   └── .env.example                 (API keys — real .env gitignored)
├── 01_input/
│   ├── photogrammetry/
│   │   ├── projects/                (Metashape/RealityCapture project files)
│   │   └── raw_exports/FRAG-S1-###/ (full-res mesh + texture straight from software, untouched)
│   ├── meshes/
│   │   └── processed/FRAG-S1-###/   (cleaned, unit-unified, decimated analysis meshes)
│   ├── photos/FRAG-S1-###/
│   ├── pseudo_data/
│   └── fragments_manifest.csv
├── 02_gh/                           (Grasshopper definitions)
│   ├── descriptor_extraction.gh
│   └── inventory_query.gh
├── 03_src/                          (Python modules, imported by GH components)
│   ├── descriptors/  (geometry.py, surface.py, composite.py)
│   ├── ai/           (vision_client.py, taxonomy.py, cache.py)
│   └── schema/       (validate.py)
├── 04_schema/
│   ├── fragment_schema.json
│   └── descriptor_dictionary.md     (definition + method + unit per descriptor)
├── 05_output/
│   ├── descriptors/                 (per-fragment JSON)
│   ├── ai_cache/
│   ├── renders/
│   └── inventory/
└── 06_validation/
    ├── study1_decisions.md
    ├── query_experiments/
    └── figures/
```

## Risks / open questions

- **CPython in Rhino 8 + heavy libs:** open3d wheels can fail inside Rhino's runtime → mitigation: trimesh first; if insufficient, external venv called via subprocess from GH.
- **Texture/UV quality from photogrammetry** limits colour-entropy reliability → log per-fragment scan quality in manifest; report as limitation.
- **Vision API consistency:** fix model version + temperature, cache responses, run each classification 3x and take majority label.
- **Taxonomy validity:** ground in spolia criteria from Study 1; have supervisors review before bulk annotation.

## Next actions

- [ ] Phase 0 setup checkpoints
- [ ] Move Study 1 meshes/photos into `01_input/`
- [ ] Draft texture taxonomy from Study 1 spolia criteria
