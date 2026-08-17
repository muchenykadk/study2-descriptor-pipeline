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

**Process and open in one command** — `--serve` acts as a modifier when a fragment ID or `--batch` is given:
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-006 --force --serve
python 03_src/run_pipeline.py --batch --force --serve
```

**Custom RANSAC threshold** (default 3.0 mm — increase for noisier scans):
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-003 --ransac-threshold 5.0
```

---

**Re-apply scan-coverage flags** (auto-runs inside the pipeline when a `_scan_coverage.json` sidecar exists; standalone re-annotation only):
```powershell
python 03_src/scan_coverage.py FRAG-S1-FS-003
```

---

## Query the records

Structured filters over the per-fragment JSON. No natural language: the descriptors are
already symbolic, so selection is exact filtering.

**By intended design use:**
```powershell
python 03_src/query.py --list-uses
python 03_src/query.py --use bench_top --rank mass
python 03_src/query.py --use bar_table_stand
python 03_src/query.py --use seat_block --max-mass 400 --handling two_person
```

**By surface condition or anomaly:**
```powershell
python 03_src/query.py --label formwork_imprint --min-face-area 0.3
python 03_src/query.py --anomaly opening
```

**Evaluation baseline** — withhold the surface descriptors and re-derive, so the
difference between the two runs isolates what surface characterization contributes:
```powershell
python 03_src/query.py --use bench_top --geometry-only
```

Unsupported predicates exit with code 2 and an explanation, instead of returning a
plausible wrong answer.

---

## Blender export

Use the **v2 scripts** (they also write the UNSCANNED `_scan_coverage.json` sidecar): open `02_blender/bake_texture_v2.py` (remesh + bake + export) or `02_blender/export_fragment_v2.py` (export only) in the Blender Scripting tab.  
Set `FRAG_ID = "FRAG-S1-{ARCHETYPE}-{###}"` at the top, select the mesh, click ▶ Run Script. Assign the `UNSCANNED` vertex group to the manually closed ground-contact faces *before* running (see `HANDOVER.md` §5–6).

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

| ID | Archetype | Status (2026-08-10) |
|---|---|---|
| FRAG-S1-FS-001 | Floor Slab | geometry-only descriptors (no AI run yet) |
| FRAG-S1-FS-002 | Floor Slab | processed — descriptors + feature map |
| FRAG-S1-FS-003 | Floor Slab | processed — descriptors + feature map; UNSCANNED sidecar |
| FRAG-S1-FS-004 | Floor Slab | processed — descriptors + feature map |
| FRAG-S1-FS-005 | Floor Slab | processed — descriptors + feature map |
| FRAG-S1-FS-006 | Floor Slab | processed — descriptors + feature map; UNSCANNED verified |
