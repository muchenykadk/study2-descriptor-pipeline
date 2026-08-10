# Study 2 — Pipeline Workflow

Source of truth for **when to do what**, what to run, and when to upgrade.  
Keep this open alongside Blender during active work sessions.

---

## Tool map

```
Scaniverse (iPad Pro)   → raw scan (.glb — fused geometry + baked texture)
Blender                 → clean mesh, UNSCANNED marking, UV unwrap, texture bake → .glb + _texture.png + sidecar
Python (run_pipeline.py)→ geometry + AI descriptors + scan-coverage flags → JSON + HTML report
HTML / Three.js viewer  → per-fragment report + inventory (run_pipeline.py --serve)
```

(The earlier Rhino / Grasshopper stage is superseded; `02_gh/` is unused.)

---

## Step 1 — Photogrammetry capture (on site)

Use **Scaniverse** on iPad Pro (LiDAR-assisted photogrammetry).  
Select **Medium Object** scan mode. Export as `.glb` (textured mesh).

Save the raw export untouched to:
```
01_input/photogrammetry/raw_exports/FRAG-S1-###/
```
Naming: keep the original export filename here. Do not rename raw files.

> **Git:** after dropping in a new raw export, run `git add` and commit:  
> `git commit -m "feat: add raw scan FRAG-S1-FS-001"`

---

## Step 2 — Blender: clean mesh + export

Open the raw `.glb` from `raw_exports/FRAG-S1-###/`.

### Cleaning checklist
- [ ] Remove isolated vertices and floating faces
- [ ] Fix inverted normals (Mesh > Normals > Recalculate Outside)
- [ ] Close small holes where possible
- [ ] Decimate to ~50–100k faces for analysis (Modifier > Decimate, keep UV)
- [ ] Move mesh to world origin (Object > Set Origin > Geometry to Origin, then G-X/Y/Z to zero)
- [ ] Confirm units are millimetres (Scene Properties > Units)

### UV / texture checklist
If the UV map survived cleaning (no topology changes): skip re-bake.  
If you deleted faces, merged vertices, or decimated heavily:
- [ ] Keep original scan as a separate object (don't delete it)
- [ ] Smart UV Project on the cleaned mesh (Edit Mode → UV → Smart UV Project)
- [ ] Create a new blank Image Texture node on the cleaned mesh material
- [ ] Bake: select cleaned mesh first (active), shift-click original scan, Bake type = Diffuse, uncheck Direct/Indirect, enable Selected to Active, Ray Distance ~5 mm
- [ ] Save the baked texture PNG

### Mark the UNSCANNED ground-contact face (before export)

The ground-contact face is never captured by the scan. After closing the hole manually (select boundary edge loop → F):

- [ ] With the filled faces still selected: Object Data Properties → Vertex Groups → `+` → name `UNSCANNED` → Assign
- [ ] Verify: deselect all → select the `UNSCANNED` group → Select → the closed patch highlights

### Export — run the Blender script (automates both exports + sidecar)

Open **`02_blender/bake_texture_v2.py`** (remesh + UV + bake + export) or **`02_blender/export_fragment_v2.py`** (export only, if the texture is already good) in the Blender Scripting tab.  
Set `FRAG_ID` at the top, select the cleaned mesh, click Run Script (▶).

This produces:
- `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###.glb` — mesh + UV (pipeline input + 3D viewer)
- `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###_texture.png` — rebaked albedo (AI analysis)
- `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###_scan_coverage.json` — UNSCANNED sidecar (read automatically by the pipeline)

(The v1 scripts `bake_texture.py` / `export_fragment.py` still work for fragments without an UNSCANNED vertex group.)

> Manual export alternative if the script fails:  
> **GLB**: File → Export → glTF 2.0 · Format = Binary (.glb) · ✓ UVs · ✓ Normals · ✓ Materials  
> **PNG**: Image Editor → Image → Save As → `FRAG-S1-###_texture.png`

> **Git:** commit after Blender exports:  
> `git commit -m "feat: add processed mesh FRAG-S1-FS-001"`  
> Note: GLB and PNG are tracked by git-lfs (see `.gitattributes`).

---

## Step 3 — Run the Python pipeline

**First time setup — create and activate the virtual environment:**
```powershell
python -m venv env\venv
env\venv\Scripts\activate
pip install -r env/requirements.txt
```

**Every subsequent session — activate before running anything:**
```powershell
env\venv\Scripts\activate
```

**Run the full pipeline** (geometry + AI classification):
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-001
```

Geometry only (faster, no API key needed):
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-001 --geometry-only
```

Output: `05_output/descriptors/FRAG-S1-FS-001_geometry.json` + HTML report  
The terminal prints OBB dimensions, mass estimate, planar regions, and AI feature labels.

If a `_scan_coverage.json` sidecar exists, the pipeline automatically flags matching RANSAC planes `scan_reliable: false` and excludes UNSCANNED texture cells from AI classification. Batch mode: `python 03_src/run_pipeline.py --batch`. View reports: `python 03_src/run_pipeline.py --serve`.

Requires `env/.env` with `OPENAI_API_KEY` for AI classification (copy `env/.env.example` → `env/.env`).

> **Git:** commit after running:  
> `git commit -m "data: descriptors FRAG-S1-FS-001"`

---

## Step 4 — Human annotation (review AI output)

Open the JSON file directly:
```
05_output/descriptors/FRAG-S1-FS-001_geometry.json
```
For each AI-classified field, fill in `human_value` and `human_notes`, set `data_status` to `"human_reviewed"`.

> **When to upgrade to the GH annotator:**  
> Once you have more than 3–4 fragments, or when a supervisor / collaborator  
> needs to review without opening JSON files — build `02_gh/annotate.gh`.  
> The data model does not change; only the interface changes.

> **Git:** commit after reviewing:  
> `git commit -m "annotation: human review FRAG-S1-FS-001"`

---

## Step 5 — Review in the viewer

```powershell
python 03_src/run_pipeline.py --serve
```
Opens the inventory (`05_output/descriptors/index.html`) over HTTP; per-fragment reports include the 3D viewer with planar regions, feature labels, and UNSCANNED overlay.

> The earlier Rhino / Grasshopper step (`02_gh/inventory_query.gh`) is superseded and unused.

---

## Upgrade triggers

| Condition | Action |
|---|---|
| > 3 fragments to annotate | Build `annotate.gh` instead of editing JSON |
| Supervisor / collaborator reviewing | Build `annotate.gh` with Gradio fallback |
| Phase 3 AI results look weak | Switch `VISION_PROVIDER` in `.env` to `gemini` or `ollama` |
| open3d fails inside Rhino runtime | Run `run_pipeline.py` as external subprocess from GH |
| > 10 fragments | Add `run_pipeline.py --batch` mode |

---

## Git commit conventions

```
feat: add / implement something new
fix: correct a bug or wrong output
refactor: restructure without changing behaviour
annotation: human review of AI output
data: add scan / mesh / texture files
docs: update plan, workflow, or schema
```
