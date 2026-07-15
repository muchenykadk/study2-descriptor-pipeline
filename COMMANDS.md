# Quick Commands — Study 2 Descriptor Pipeline

Open this file when starting a work session.

---

## Environment

**Activate virtualenv** (required before every pipeline run):
```powershell
cd "C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"
env\venv\Scripts\activate
```

**First-time setup** (once only):
```powershell
python -m venv env\venv
env\venv\Scripts\activate
pip install -r env/requirements.txt
```

---

## Pipeline

**Run full pipeline** — geometry + AI classification:
```powershell
python 03_src/run_pipeline.py FRAG-S1-001
```

**Geometry only** — skip AI (no API key needed, faster):
```powershell
python 03_src/run_pipeline.py FRAG-S1-001 --geometry-only
```

**Open existing report** — serve without recalculating (GLB + feature textures require HTTP, not file://):
```powershell
python 03_src/run_pipeline.py FRAG-S1-002 --serve
```

**Custom RANSAC threshold** (default 3.0 mm — increase for noisier scans):
```powershell
python 03_src/run_pipeline.py FRAG-S1-001 --ransac-threshold 5.0
```

---

## Blender export

Open `02_blender/export_fragment.py` in the Blender Scripting tab.  
Set `FRAG_ID = "FRAG-S1-###"` at the top, select the mesh, click ▶ Run Script.

Outputs:
- `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###.glb`
- `01_input/meshes/processed/FRAG-S1-###/FRAG-S1-###_texture.png`

---

## Git

**Commit new scan (raw export):**
```powershell
git add 01_input/photogrammetry/raw_exports/FRAG-S1-###/
git commit -m "data: add raw scan FRAG-S1-###"
```

**Commit processed mesh (after Blender export):**
```powershell
git add 01_input/meshes/processed/FRAG-S1-###/
git commit -m "data: add processed mesh FRAG-S1-###"
```

**Commit descriptor output (after pipeline run):**
```powershell
git add 05_output/
git commit -m "data: descriptors FRAG-S1-###"
```

**Commit code/doc changes:**
```powershell
git add -A
git commit -m "refactor: ..."
```

**Check status:**
```powershell
git status
git log --oneline -10
```

---

## Fragment IDs so far

| ID | Status |
|---|---|
| FRAG-S1-001 | raw scan only (no Blender processing) |
| FRAG-S1-002 | processed — descriptors complete |
