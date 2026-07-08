# Study 2 — Pipeline Workflow

Source of truth for **when to do what**, what to run, and when to upgrade.  
Keep this open alongside Blender and Rhino during active work sessions.

---

## Tool map

```
Polycam / Metashape / RealityCapture   → raw scan (.obj + texture PNG)
Blender                                → clean mesh, re-bake texture, export
Python (run_pipeline.py)               → geometry + AI descriptors → JSON
Rhino / Grasshopper                    → design queries, annotation (annotate.gh), figures
```

---

## Step 1 — Photogrammetry capture (on site)

Use **Polycam** (iOS, LiDAR recommended), Metashape, or RealityCapture.

Export as: `.obj` + texture PNG (or `.glb` — both work).  
Save the raw export untouched to:
```
01_input/photogrammetry/raw_exports/FRAG-S1-###/
```
Naming: keep the original export filename here. Do not rename raw files.

> **Git:** after dropping in a new raw export, run `git add` and commit:  
> `git commit -m "feat: add raw scan FRAG-S1-001"`

---

## Step 2 — Blender: clean mesh + export

Open the raw `.obj` from `raw_exports/FRAG-S1-###/`.

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

### Export — run all three exports from Blender

**1. OBJ** (for Python analysis):
File → Export → Wavefront (.obj)  
Settings: Forward = -Z, Up = Y · Scale = 1.0 · ✓ UVs · ✓ Normals · ✓ Triangulate  
Save to: `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###.obj`

**2. GLB** (for Rhino):
File → Export → glTF 2.0 (.glb)  
Format = Binary (.glb) · ✓ UVs · ✓ Normals · ✓ Materials · ✓ Images (include)  
Save to: `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###.glb`

**3. Texture PNG** (for vision API):
Image Editor → Image → Save As  
Save to: `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###_texture.png`

> **Git:** commit after Blender exports:  
> `git commit -m "feat: add processed mesh FRAG-S1-001"`  
> Note: GLB and PNG are tracked by git-lfs (see `.gitattributes`).

---

## Step 3 — Run the Python pipeline (Phase 2: geometry)

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

Then run the pipeline:
```powershell
python 03_src/run_pipeline.py FRAG-S1-001
```

Output: `05_output/descriptors/FRAG-S1-001_geometry.json`

The terminal prints a summary (OBB dimensions, mass estimate, planar regions found).  
Check the numbers look physically plausible before continuing.

> **Git:** commit new descriptor output:  
> `git commit -m "feat: add geometry descriptors FRAG-S1-001"`

---

## Step 4 — Run Phase 3: AI classification (vision API)

Requires `.env` with `ANTHROPIC_API_KEY` set (copy `env/.env.example` → `env/.env`).

```bash
python 03_src/run_pipeline.py FRAG-S1-001 --phase3
```

Output: adds AI fields to `05_output/descriptors/FRAG-S1-001_geometry.json`  
AI fields include: `rebar`, `surface_origin_type`, `defect_presence`, `weathering_severity`  
Each field contains `ai_value`, `ai_reasoning`, `human_value` (null until reviewed), `data_status`.

---

## Step 5 — Human annotation (review AI output)

Open the JSON file directly:
```
05_output/descriptors/FRAG-S1-001_geometry.json
```
For each AI-classified field, fill in `human_value` and `human_notes`, set `data_status` to `"human_reviewed"`.

> **When to upgrade to the GH annotator:**  
> Once you have more than 3–4 fragments, or when a supervisor / collaborator  
> needs to review without opening JSON files — build `02_gh/annotate.gh`.  
> The data model does not change; only the interface changes.

> **Git:** commit after reviewing:  
> `git commit -m "annotation: human review FRAG-S1-001"`

---

## Step 6 — Rhino / Grasshopper

Import the GLB: `_Import` → select `FRAG-S1-###.glb`  
Open `02_gh/inventory_query.gh` to query the descriptor inventory.

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
