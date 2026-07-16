# Quick Commands — Study 2 Descriptor Pipeline

Open this file when starting a work session.

---

## Fragment ID format

```
FRAG-S1-{ARCHETYPE}-{###}
```

Archetype is assigned manually at physical inspection. The sequential counter `###` resets per archetype type.

| Code | Archetype | Code | Archetype |
|---|---|---|---|
| `FS` | Floor Slab | `RS` | Roof Slab |
| `BM` | Beam | `CO` | Column |
| `WL` | Load-bearing Wall | `WP` | Partition Wall |
| `LT` | Lintel | `ST` | Stair |
| `BL` | Balcony | `FP` | Facade Panel |
| `FD` | Foundation | `UN` | Unidentified |

Examples: `FRAG-S1-FS-003`, `FRAG-S1-CO-001`, `FRAG-S1-BM-001`

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
python 03_src/run_pipeline.py FRAG-S1-FS-003
```

**Batch mode** — process all unanalyzed fragments automatically (skips any with existing output):
```powershell
python 03_src/run_pipeline.py --batch
```

**Force re-run** — re-analyze even if output already exists (e.g. after clearing AI cache):
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-002 --force
python 03_src/run_pipeline.py --batch --force
```

**Geometry only** — skip AI (no API key needed, faster):
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-003 --geometry-only
python 03_src/run_pipeline.py --batch --geometry-only
```

**Open existing report** — serve without recalculating (GLB + feature textures require HTTP, not file://):
```powershell
python 03_src/run_pipeline.py --serve
```

**Custom RANSAC threshold** (default 3.0 mm — increase for noisier scans):
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-003 --ransac-threshold 5.0
```

---

## Blender export

Open `02_blender/export_fragment.py` in the Blender Scripting tab.  
Set `FRAG_ID = "FRAG-S1-{ARCHETYPE}-{###}"` at the top, select the mesh, click ▶ Run Script.

Outputs:
- `01_input/meshes/processed/FRAG-S1-{ARCHETYPE}-{###}/FRAG-S1-{ARCHETYPE}-{###}.glb`
- `01_input/meshes/processed/FRAG-S1-{ARCHETYPE}-{###}/FRAG-S1-{ARCHETYPE}-{###}_texture.png`

---

## Git

**Commit new scan (raw export):**
```powershell
git add 01_input/photogrammetry/raw_exports/FRAG-S1-{ARCHETYPE}-{###}/
git commit -m "data: add raw scan FRAG-S1-{ARCHETYPE}-{###}"
```

**Commit processed mesh (after Blender export):**
```powershell
git add 01_input/meshes/processed/FRAG-S1-{ARCHETYPE}-{###}/
git commit -m "data: add processed mesh FRAG-S1-{ARCHETYPE}-{###}"
```

**Commit descriptor output (after pipeline run):**
```powershell
git add 05_output/
git commit -m "data: descriptors FRAG-S1-{ARCHETYPE}-{###}"
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

## Fragment registry

| ID | Archetype | Status |
|---|---|---|
| FRAG-S1-FS-001 | Floor Slab | raw scan only (no Blender processing) |
| FRAG-S1-FS-002 | Floor Slab | processed — descriptors complete |
