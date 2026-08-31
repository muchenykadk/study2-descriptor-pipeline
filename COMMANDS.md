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

## Pre-flight

Validates a Blender export before the pipeline spends time or API credit on it. Runs
**automatically** at the start of every `run_pipeline.py` run and stops on a failure.

```powershell
python 03_src/preflight.py FRAG-S1-FS-007    # check one export
python 03_src/preflight.py --all             # check every fragment
```

Checks, each added after something got through without it:

| check | catches |
|---|---|
| remesh resolution | FS-003 exported at 3,016 faces, ~0.5% of expected. Usually a Blender unit mismatch |
| UV coordinates | texture cannot be mapped to faces |
| volume source | GLB seam splitting makes a solid mesh look open, so mass falls back to the convex hull and overstates by 17–90% |
| texture present, resolution | — |
| bake margin | `margin_type` left on the default, leaving black hard against every island edge |
| featureless patch | an unmarked unscanned face, baked as a flat wash |
| UNSCANNED marked | the vertex group missing entirely |
| sidecar normal | Blender Z-up to glTF Y-up conversion not coming out vertical, so the filter matches nothing |
| UNSCANNED located | the group present but covering the wrong faces |
| same mesh as another fragment | one mesh under two IDs, either a duplicate export or `FRAG_ID` left unchanged in the Blender script |

To process a known-bad mesh anyway: `python 03_src/run_pipeline.py FRAG-S1-FS-003 --skip-preflight`

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

## Managing the taxonomy

Adding a label means two entries that must agree, one in `labels` and one in
`_decision_order`. Forgetting the second means the label exists but never reaches the
prompt, so the model cannot choose it and nothing says so. This writes both, or neither.

```powershell
python 03_src/taxonomy_tool.py list      # labels, precedence, exemplar counts
python 03_src/taxonomy_tool.py check     # do labels and _decision_order agree?
python 03_src/taxonomy_tool.py folders   # one drop-folder per label
python 03_src/taxonomy_tool.py add       # asks for what it needs
python 03_src/taxonomy_tool.py add --id embedded_metal --after rebar_visible --rule "Steel that is not reinforcement: a fixing, angle or plate cast in."
```

`add` writes both entries, picks an unused colour, and creates
`01_input/reference_surfaces/<id>/` for the exemplars. `folders` does the same for every
existing label, so the set to be filled is visible rather than remembered; it is safe to
re-run and never touches a folder that already exists.

Neither creates anything under `_candidates/`. Those folders are written by
`build_reference_set.py` as it saves each crop, and are named after labels the model has
already assigned, so an empty one has nothing that could go in it. A new label has no
candidates until a run produces some; crop its first exemplars from an atlas by hand.

Only `id` and `decision_rule`, ordered by `_decision_order`, reach the vision model.
`description` is the report legend, `subtypes` only the legacy `--grid-legacy` prompt,
`color` only the report and feature map. Keys starting with `_` are notes for humans.

**Retiring or removing a label:**
```powershell
python 03_src/taxonomy_tool.py remove --id original_finish   # only if nothing uses it
python 03_src/taxonomy_tool.py retire --id original_finish   # always safe
python 03_src/taxonomy_tool.py retire --id original_finish --undo
```

`remove` deletes the label outright and **refuses** unless nothing references it: not
assigned in any record, its feature_id absent from every viewer JSON, and no higher
feature_id in use, since deleting an entry renumbers everything after it.

`retire` is the answer when `remove` refuses. The id and its position stay, so every
feature_id already written keeps its meaning, but the label drops out of the prompt and out
of the report legend, chips and filters. Nothing new can be assigned to it; anything already
assigned still renders. Reversible with `--undo`.

**Adding, retiring or removing a label changes the prompt, so the API cache is invalidated
and every fragment needs `--force` to stay comparable.** Never rename an id.

---

## Calibrating the feature labels

The model applies a verbal definition of "formwork imprint" or "fracture surface" and
interprets it alone, which is why the standard drifts between fragments. Since every
fragment comes from one building, the standard can be shown instead: labelled exemplar
crops sent ahead of the regions on every call.

```powershell
python 03_src/build_reference_set.py              # export candidates from all fragments
python 03_src/build_reference_set.py FRAG-S1-FS-006
```

Crops land in `01_input/reference_surfaces/_candidates/<current_label>/`. These are whole-region
cut-outs for **browsing**, so they carry magenta. Use them to find good source material, then
crop a clean rectangle of surface, 256 to 512 px with no magenta, no black and no
transparency, from `05_output/descriptors/<fragment>_texture.png`, and save it into
`01_input/reference_surfaces/<label>/`. That is where the pipeline reads.

Anything left in `_candidates/` is ignored, and an empty set leaves the pipeline unchanged.

```powershell
python 03_src/build_reference_set.py --check      # validate a hand-made set
```

Only the folder name and the image bytes are sent; the filename never leaves the machine,
so name files for your own provenance.

**The control run:**
```powershell
python 03_src/run_pipeline.py FRAG-S1-FS-006 --force --no-references
```
Classifies uncalibrated. Compare against the calibrated run: a label that holds only when
its own fragment supplied the exemplar is leakage, not recognition. The reference signature
is part of the cache key, so the two runs cannot collide.

Every reference is sent with every call, so keep the set small. Swapping an exemplar
changes the standard and correctly invalidates the API cache.

See `04_schema/TAXONOMY_REVIEW.md` for why, and for the circularity this introduces.

---

## Validating the classifier

**Everything above tunes the classifier. This measures it.** Results and what they license
you to claim are in `04_schema/CLASSIFIER_BEHAVIOUR.md`.

### Build a held-out test set

```powershell
python 03_src/build_test_set.py --n 45 --exclude FRAG-S1-FS-001
python 03_src/build_test_set.py --add --n 60        # keep what is labelled, top up
```

Samples tiles **blind** from the fragment atlases at random positions, each covering ~250 mm
of real surface. Tile size is computed per fragment from measured texel density, so a tile
shows the same amount of material on a 1.3 px/mm fragment as on a 2.5 px/mm one.

These tiles are never sent as reference images, which is the whole point: the earlier version
of this test scored the classifier on the exemplars that calibrate it, and could not separate
recognition from recall.

Label `05_output/test_set_labels.csv`, column `true_features`, comma separated. Two special
values matter:

- `none` — readable concrete, nothing in the vocabulary applies. This is how invention on
  plain surface gets measured.
- `unusable` — smear, blur or black atlas. Excluded from scoring, because neither you nor the
  model has anything to read. The *count* is a result: 13 of 39 tiles on this corpus.

Do not hand-pick interesting tiles. That measures the best case and reports it as the average.

### Score it

```powershell
python 03_src/score_test_set.py                  # calibrated
python 03_src/score_test_set.py --no-references   # the ablation
python 03_src/binary_probe.py                     # one yes/no question per feature
```

`score_test_set.py` gives per-feature recall and precision plus a micro-average.
**Compare it against a null model that always answers the two commonest features**, or the
numbers will look like performance when they are base rate. On this corpus the null model
scored 80% recall and 75% precision; the classifier scored 80% and 66%.

`binary_probe.py` asks one feature at a time. Multi-label prompting lets the model retreat to
a safe subset; a yes/no question does not. This is what moved `brick_inclusion` from 0 of 5
to 2 of 5.

### Repeatability, free

```powershell
python 03_src/agreement.py
python 03_src/agreement.py --md        # markdown table for the paper
```

Each region batch is classified three times and each run is cached separately, so agreement
is measurable after the fact with no additional calls. It prints output **diversity**
alongside the agreement figure on purpose: 98% unanimity means little when 82% of regions
return the identical answer. It measures stability, not correctness.

Batches answering the older single-label prompt are set aside and counted, because agreement
on a one-of-eight choice is not the same measurement as agreement on a list.

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

**By procedural factor:**
```powershell
python 03_src/query.py --handling two_person
python 03_src/query.py --drill-zone between_bars
python 03_src/query.py --connection direct_bolt --assignment show_face
```

`--drill-zone` values:

| value | meaning |
|---|---|
| `between_bars` | reinforcement exposed somewhere on the fragment, so the mat's spacing, direction and cover can be read off it and projected across the piece; holes set out in the middle of a grid opening |
| `edge_mid_depth` | no bars visible, but the section is deep enough for a steel-free core between the two mats; enter a broken edge at mid-thickness |
| `verify_gpr` | layout unobservable and the section too thin for a reliable core; scan before drilling, or fix without drilling |

**Evaluation baseline** — withhold the surface descriptors and re-derive, so the
difference between the two runs isolates what surface characterization contributes:
```powershell
python 03_src/query.py --use bench_top --geometry-only
```

Unsupported predicates exit with code 2 and an explanation, instead of returning a
plausible wrong answer.

**Rebuild the interface** after editing `env/design_factors.json` or anything in
`report.py` — re-derives the factors, regenerates every fragment report, and rebuilds
the inventory. No geometry recomputed, no API calls:
```powershell
python 03_src/refresh_factors.py --dry-run       # show what would change
python 03_src/refresh_factors.py                 # factors + reports + inventory
python 03_src/refresh_factors.py --reports-only  # HTML only, records untouched
python 03_src/run_pipeline.py --serve            # then view
```

**Which command for which kind of change:**

| what changed | command | cost |
|---|---|---|
| `env/design_factors.json`, `report.py` | `refresh_factors.py` | free |
| `geometry.py`, RANSAC settings | `run_pipeline.py --batch --force --geometry-only` | free, slow |
| taxonomy, vision prompt, crop construction | `run_pipeline.py --batch --force` | **API credit** |
| Blender bake settings | re-bake in Blender, then `--batch --force` | **API credit** |

Editing the vision prompt or the anomaly hints changes `prompt_sig`, which is part of the
API cache key. Cached answers are then correctly ignored and every region is re-sent.

---

## Blender export

Use the **v2 scripts** (they also write the UNSCANNED `_scan_coverage.json` sidecar): open `02_blender/bake_texture_v2.py` (remesh + bake + export) or `02_blender/export_fragment_v2.py` (export only) in the Blender Scripting tab.  
Set `FRAG_ID = "FRAG-S1-{ARCHETYPE}-{###}"` at the top, select the mesh, click ▶ Run Script. Assign the `UNSCANNED` vertex group to the manually closed ground-contact faces *before* running (see `WORKFLOW.md`).

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

| ID | Archetype | Faces | Status (2026-08-17) |
|---|---|---|---|
| FRAG-S1-FS-001 | Floor Slab | 47,292 | coarse export; geometry-only, no AI run |
| FRAG-S1-FS-002 | Floor Slab | 23,220 | point-cloud path; record describes the PLY, not the GLB — **re-run through the mesh path** |
| FRAG-S1-FS-003 | Floor Slab | 3,016 | **too coarse to use**; nothing classified. Its UNSCANNED group is also empty (`face_count: 0`), so re-mark it when re-exporting |
| FRAG-S1-FS-004 | Floor Slab | 3,361,768 | sound |
| FRAG-S1-FS-005 | Floor Slab | 2,132,300 | **duplicate of FS-006**, failed bake (90% smeared) — resolve before use |
| FRAG-S1-FS-006 | Floor Slab | 2,132,300 | sound; UNSCANNED verified |

Five distinct fragments, not six: FS-005 and FS-006 are the same piece exported twice.
