# Surface taxonomy provenance

Status 2026-08-25. Rewritten against the current schema. The previous version described a
two-axis scheme, `surface_label` plus an `anomalies[]` array carrying bounding boxes, and
used the identifiers `formwork_imprint`, `fracture_surface` and `cast_in_brick`. None of that
survives: the schema has been one multi-label axis since 2026-08-20, localisation is disabled
(`ALLOW_LOCALISATION = False`), and those three ids were renamed in place.

This file is the backing detail for one sentence after Table 1 in
`EKA_full_paper_draft_rev2.md`. It is not itself a table in the paper.

Citation keys assume LNCS numbered style; substitute your Zotero numbers.

- **[M]** Mundt, M., Majumder, S., Murali, S., Panetsos, P., Ramesh, V. (2019).
  Meta-learning Convolutional Neural Architectures for Multi-target Concrete Defect
  Classification with the COncrete DEfect BRidge IMage Dataset. *CVPR*.
  Six non-exclusive classes: crack, spallation, efflorescence, exposed bars, corrosion
  (stains), non-defective background. 7,729 patches, 30 bridges.
- **[F]** Flotzinger, J., Rösch, P.J., Braml, T. (2024). dacl10k: Benchmark for Semantic
  Bridge Damage Segmentation. *WACV*. 9,920 images; 13 damage classes (Crack, ACrack,
  Wetspot, Efflorescence, Rust, Rockpocket, Hollowareas, Cavity, Spalling, Graffiti,
  Weathering, Restformwork, ExposedRebars) plus 6 object classes.

Provenance is recorded at three levels:

- **adopted** — a direct correspondence with a benchmarked class
- **related** — a benchmarked class covers similar ground without being equivalent
- **project-defined** — no benchmark contains it, and none plausibly would

---

## The eleven active features

| Feature | Group | Description | Provenance |
|---|---|---|---|
| `rebar_visible` | inclusion | Exposed steel reinforcement | **adopted**: "exposed bars" [M]; "ExposedRebars" [F] |
| `broken_face` | formation | A break through the body of the concrete, any cause | **related**: "spallation" [M] and "Spalling" [F] describe material loss, but both assume an intact in-service face to lose it from |
| `exposed_aggregate` | composition | Coarse aggregate dominates the surface | **related**: "Rockpocket" [F] is honeycombing from poor compaction, a specific cause rather than the general appearance |
| `pipe_opening` | inclusion | Inner surface of a former pipe or conduit penetration | **related**: "Cavity" [F] covers voids, not a cast bore |
| `formwork_face` | formation | Cast face carrying mould evidence: board marks, panel joints, tie holes | project-defined. "Restformwork" [F] denotes formwork material left in place, a different observation |
| `embedded_metal` | inclusion | Non-reinforcement steel cast in: fixings, angles, plates, conduit | project-defined |
| `tile_remnant` | inclusion | Ceramic, stone or mosaic tile still adhering, including its bedding | project-defined |
| `brick_inclusion` | inclusion | Brick or masonry units cast into the concrete | project-defined |
| `paste_dominant` | composition | Cement paste dominates; little aggregate cut or exposed | project-defined |
| `biological_growth` | colour | Moss, algae or lichen | project-defined. "Weathering" [F] is erosion and scaling, a different observation |
| `trowelled_finish` | formation | Floated or trowelled top surface | project-defined |

**One adopted, three related, seven project-defined.**

## The retired categories

| Feature | Benchmark status | Why retired |
|---|---|---|
| `crack` | **adopted** [M], [F] | A crack that has not separated the piece has almost no aperture, so geometry cannot reach it at any scan resolution. In texture it is 1.3 to 2.5 px wide for a 1 mm opening. The instrument is a line filter returning a length and a width, not a classifier returning a category |
| `spalling` | **adopted** [M], [F] | Its defining evidence is the lip against sound surface, which is larger than the sampling window. Merged into `broken_face` |
| `efflorescence` | **adopted** [M], [F] | Absent from all 26 blind-sampled tiles |
| `discolouration` (was `staining`) | **adopted** [M], [F] | Predicted on 8 tiles where ground truth was 1. At 12% precision it was the entire precision gap against the null model |
| `weathered` | **adopted** [F] | Requires a fresh reference surface for comparison, which is never in frame on a demolition fragment |
| `original_finish` | project-defined | Bundled tile, plaster, render and screed into one label spanning materials with nothing in common beyond being applied. `tile_remnant` retained, remainder retired |

Identifiers are retained after retirement, because a feature's position in `env/taxonomy.json`
is its stored integer id and renumbering would silently recolour records already written.

---

## What this argues

**1. The categories that transfer are the ones this material cannot support.** Five of the six
retired categories have direct benchmark correspondence. One of the eleven retained ones does.
That inversion is the finding, and it is not an accident of what happened to be available.
The benchmarks label *deterioration of in-service structures photographed at close range*.
This corpus is *demolition debris scanned at arm's length*, where the dominant conditions are
formation and inclusion: how the piece was cast, how it was broken, and what was cast into it.
Those are the properties that carry design information here, and no bridge-inspection dataset
contains them.

**2. It bounds what a trained classifier could take over.** Labelled data exists for one of the
eleven. The other ten would need an open-vocabulary model or a corpus that does not exist. This
is the concrete form of the claim in §7 that any evaluation of surface classification on this
material must supply its own ground truth.

**3. It states the limit of the vocabulary's generality.** The eleven features are specific to
this stock: `brick_inclusion` exists because this building is a masonry composite,
`formwork_face` depends on the contractor's system. What transfers is the procedure that
produced the list, admitting a category only where its defining evidence exceeds the sampling
window at the achieved texel density. The list is local; the test is not.

**Do not claim comparability of results.** [M] classify patches of bridge photographs, [F]
segment inspection photographs, and this work classifies regions of a baked texture atlas on
scanned fragments. The category names are shared in one case out of eleven; the task is not
shared at all.
