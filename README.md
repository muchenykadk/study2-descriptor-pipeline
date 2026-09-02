# Fragment Descriptor Pipeline

Extracts geometric and surface descriptors from 3D scans of demolition concrete fragments and
structures them into one queryable record per fragment. Built for Study 2 of a PhD on cascading
reuse of demolition concrete, and demonstrated on twelve scanned fragments from a built public
installation.

Blender handles mesh cleaning, UV unwrap, texture bake and unscanned-face marking. Python does
the geometry (trimesh, Open3D) and the surface classification (a vision-language model). An
HTML and Three.js report renders each record.

## Read this before trusting the surface labels

**The surface classifier does not exceed a null model.** It was scored on two sets of tiles
sampled blind from the baked textures and labelled by hand, against a model that answers the
two commonest features unconditionally and looks at nothing:

| set | tiles | null model | classifier |
|---|---:|---|---|
| A | 26 | 80% recall / 75% precision | 80% / 66% |
| B | 23 | 75% recall / 52% precision | 78% / 51% |

On set B the classifier returned `broken_face` on 22 of 23 tiles where 9 carry it. What it does
recover is rare and distinctive: efflorescence on one of five tiles carrying it, rust staining
on the single tile carrying it, both without a false positive.

**The geometric half is verified.** Bounding box, volume and mass recompute from the mesh, and
every derived factor traces to measured values.

**Exemplar calibration is not used.** Sending labelled crops from the same building ahead of the
regions cost twelve points of recall and seven of precision, roughly five times the variation
between repeat runs. `01_input/reference_surfaces/` still holds the exemplars and
`--no-references` is the default behaviour of the evaluation scripts.

**`rebar_visible` is a detection floor, not a rate.** It is reported on 2 of 148 regions.
Photogrammetry cannot reconstruct a bar thinner than its point spacing, so a protruding bar is
missing from the mesh while visible in the source photographs; the classifier also missed the
only two human-confirmed instances in the labelled sets. Treat a negative as absent evidence,
never as evidence of absence.

**Two design factors are held back.** `drill_zone` and `finishing_requirement` both read
`rebar_visible`. Drilling guidance resting on an untested negative has no place in an output.
`drill_zone` is absent from the records; `finishing_requirement` is written as `null`.

Full evidence: `04_schema/CLASSIFIER_BEHAVIOUR.md`.

## Browse the records

The twelve records are published as a static site, no install needed:

**https://muchenykadk.github.io/study2-descriptor-pipeline/**

Each fragment opens a 3D viewer with per-region surface features, measured and derived
values on hover, and the reason a region was rejected where one applies.

Those models are decimated to roughly 45,000 faces with a 1024 px texture so they load
in a browser, about 51 MB for the whole site. The full-resolution meshes stay in
`05_output/descriptors/`. Rebuild the site with `python 03_src/build_web.py` after any
pipeline run.

## Install

Python 3.10 or later.

```bash
python -m venv env/venv
env/venv/Scripts/activate          # Windows
source env/venv/bin/activate       # macOS / Linux
pip install -r env/requirements.txt
```

Classification calls a hosted vision-language model. Put your key in `env/.env`, which is
gitignored:

```
OPENAI_API_KEY=sk-...
VISION_PROVIDER=openai
VISION_MODEL=gpt-4o
```

Everything except classification runs without a key. Use `--geometry-only` to skip it.

## Run

```bash
# one fragment, end to end
python 03_src/run_pipeline.py FRAG-S1-FS-002

# every fragment in 01_input/meshes/processed/
python 03_src/run_pipeline.py --batch

# geometry only, no API calls
python 03_src/run_pipeline.py --batch --geometry-only

# query across the records
python 03_src/query.py --use seat_block
python 03_src/query.py --min-thickness 500 --rank mass
python 03_src/query.py --connection direct_bolt --reliable-only
python 03_src/query.py --list-uses
```

`--geometry-only` on `query.py` withholds the surface descriptors, which is how the ablation in
the paper was run.

Input meshes go in `01_input/meshes/processed/<FRAGMENT_ID>/`, prepared by the Blender scripts
in `02_blender/`. See `WORKFLOW.md` for the capture and preparation steps and `COMMANDS.md` for
the full command reference.

## What it extracts

**Geometric, computed deterministically.** Oriented bounding box from PCA, mesh volume,
convexity, estimated mass at an assumed 2500 kg/m³, seeded RANSAC planes at a 3 mm threshold
with area, fit RMS and normal, multi-scale curvature at 20 mm and 60 mm, and a `scan_reliable`
flag from the angle to the unscanned face.

Face area is the **largest connected patch**, not the convex hull of the plane's inliers. A cast
surface survives demolition only as pieces between the breaks, so the hull overstates the usable
surface by a median factor of 6, and 16 of 87 faces in the corpus own no continuous surface at
all. Every area rule asks whether something can sit on the face, which needs one continuous piece.

**Surface, classified per region.** Planes fitted in the geometry phase are reused, not refitted.
Each mesh triangle is assigned to a plane and the remaining surface is clustered by adjacency,
giving regions of kind `plane`, `cluster` or `residual`. Each region's UV footprint is cut from
the baked texture and classified on its own, three times, a feature kept on a majority. Nothing
competes: a region carries every feature that applies.

The vocabulary lives in `env/taxonomy.json` and is managed with `03_src/taxonomy_tool.py`. A
feature can be added or retired without touching code. Retirement is a flag, never a deletion,
because a feature's position in the array is its stored `feature_id`.

Two admission tests bound the vocabulary. A category is admitted only where its evidence is
larger than the texture resolves, which is why `crack` is retired and named as a loss rather
than offered as an unreliable answer. A category confirmed absent from the batch by inspection
is also retired, since it can only produce false positives.

**Scan coverage.** A fragment is scanned resting on the ground, so its contact face is never
captured and is reconstructed as patched geometry. Those faces are marked, excluded from
classification, and any plane sharing their orientation is flagged unreliable.

**Derived actions and implications**, from encoded rules in `env/design_factors.json`, all
carrying `data_status: proposed`. Handling class says how the piece must be moved, connection
strategy how a face can be joined, design assignment what a face is for, and candidate uses what
the piece could become. The thresholds come from site experience and general practice and are
not expert-verified.

## Records

One JSON per fragment in `05_output/descriptors/`, holding three levels: the whole fragment,
each fitted plane, and each region. Every field records the method that produced it and its data
status, one of `measured`, `derived`, `provisional` or `proposed`. Schema in
`04_schema/fragment_schema.json`, field-by-field description in
`04_schema/descriptor_dictionary.md`.

## Full-resolution meshes

The twelve source meshes and their 4096 px textures, 1.27 GB, are archived separately:

**Zenodo DOI: [PENDING — paste after publishing the deposit]**

They are not in this repository because 2.7 GB of Git LFS content exceeds GitHub's free
quota, and the same meshes were stored twice. Nothing here depends on them: the records,
the ground truth, the evaluation and the web viewer all work from what is in the repo.
Download them only to re-run the pipeline from scratch.

Place them under `01_input/meshes/processed/<FRAGMENT_ID>/` and `python
03_src/run_pipeline.py --batch` will pick them up. `zenodo/checksums.sha256` verifies a
download against what the paper used.

## Released data

`01_input/meshes/processed/` holds twelve fragment scans. `01_input/test_tiles/` and
`01_input/test_tiles_b/` hold the two blind-sampled tile sets, with hand labels in
`05_output/test_set_labels.csv` and `05_output/test_set_labels_b.csv`. Both sets and the
labelling protocol are released so the evaluation can be repeated.

Attributes that resist scan-based measurement, concrete strength, reinforcement layout and
centre of mass, are carried as flagged provisional entries or are out of scope.

## Layout

```
01_input/     fragment scans, blind-sampled tile sets, reference exemplars
02_blender/   mesh preparation and texture bake scripts
03_src/       the pipeline, the query tool, and the evaluation scripts
04_schema/    record schema, descriptor dictionary, classifier behaviour
05_output/    per-fragment records, HTML reports, ground-truth labels
env/          taxonomy, design rules, requirements
```

## Citing

Study 1, the built installation this pipeline serves, is reported separately. Cite that paper
for the design work and this repository for the pipeline. See `CHANGELOG.md` for version
history.
