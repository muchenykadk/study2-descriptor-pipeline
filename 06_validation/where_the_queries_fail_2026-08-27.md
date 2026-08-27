# Where the queries fail: a stage-by-stage trace

The evaluation showed six queries, two of which selected anything. This traces each loss to the
stage that caused it. The finding is that almost nothing is lost in the vision model, and
almost everything is lost in the two layers on either side of it.

## The funnel

| stage | count | retained |
|---|---:|---:|
| regions segmented across twelve fragments | 148 | |
| classified by the model | 65 | 44% |
| of those, attached to a planar face | 16 | 25% |
| faces carrying any feature, of 87 | 16 | 18% |

**Eleven percent of segmented regions produce a usable face label.** The model answered 65
times; 49 of those answers were discarded by the record structure afterwards.

## Loss 1: UV layout, before the model sees anything

83 regions were never shown to the classifier.

| gate | regions | share of an average fragment's area |
|---|---:|---:|
| `sparse_uv` | 44 | 21% |
| `fragmented_uv` | 31 | 27% |
| `unreliable_texture` | 8 | 5% |

**90% of this loss is UV layout, not texture quality.** Only 8 regions of 148 were rejected
for the texture actually being bad. The other 75 were rejected because their faces are scattered
across the atlas: a region's crop is the bounding box of its whole UV footprint, so a region
whose faces sit in many small islands yields a box that is mostly empty, and it is discarded
before a single pixel is judged.

Roughly 53% of the average fragment's surface is lost here.

## Loss 2: region and face are different things

Of the 65 regions the model did classify, 49 attach to no face. **Every one of them is of kind
`cluster`.** Clusters carry `plane_index: None` by construction, so no cluster classification
can ever reach a design rule, however confident or correct it is.

Four fragments have classified regions and no labelled faces at all: FS-006, FS-008, FS-009 and
FS-010. Everything the model found on them was found on clusters.

This is the mechanism behind D7. On FS-002 the model reports `pipe_opening` correctly, on
region 8, a cluster. `planter_void` requires the label on a face. The observation is in the
record and the query cannot reach it.

## The two losses are the same loss, seen from opposite ends

Loss 1 and Loss 2 are not independent. Split by region kind:

| kind | n | median UV fill | withheld | classified |
|---|---:|---:|---:|---:|
| plane | 71 | 0.11 | 77% | 23% |
| cluster | 65 | 0.41 | 25% | 75% |
| residual | 12 | 0.06 | 100% | 0% |

The `sparse_uv` gate cuts at 0.20. Planes fall below it and clusters above it, and this follows
from their construction. A plane region is the inlier set of a RANSAC fit: points sharing a
plane equation, which may be scattered across the fragment and are therefore scattered across
the atlas, so the bounding box that defines its crop is mostly empty. A cluster region is a
connected patch of adjoining triangles, so it occupies one compact UV island.

**A region can be readable or attachable, and seldom both.** Planes carry a `plane_index` and
so can reach a design rule, but 77% are too scattered to be looked at. Clusters are readable
and 75% are classified, but they carry `plane_index: None` and reach nothing.

The arithmetic closes: 71 planes at 23% classified is 16, which is exactly the number of faces
in the corpus carrying any feature. Every face label in this project arrived through the one
narrow path where a plane happened to pack compactly.

FS-010 is the clean illustration. Region 4 returns `brick_inclusion`, `exposed_aggregate` and
`broken_face` at UV fill 0.71 and smear 0.00, among the cleanest crops in the corpus. It is a
cluster. FS-010 is a documented show face and carries no feature on any face.

## Per-decision divergence

**D4, carrier for a seating platform.** Documented: FS-003 and FS-011. Returned: FS-009,
FS-010, FS-011, FS-012. FS-011 is recovered. FS-003 fails the `seat_block` height band, at
645 mm against 380 to 520 mm.

This one is partly my encoding, and it should be resolved before the row is reported. D4's
description is "carry a horizontal timber platform", which is what `pedestal_support` describes.
Its Implicit criterion says "height band", which is what `seat_block` carries. I chose
`seat_block` for the height band. If the platform rests on the fragment and people sit on the
platform, then the fragment top should sit near 400 mm and FS-003 at 645 mm is genuinely too
tall, so the miss is real. If FS-003 carried something else, the ground truth needs revisiting.
`pedestal_support` returns all twelve, so it would recover FS-003 while discriminating nothing.

**D6, show face.** Documented: FS-002, FS-008, FS-010. Returned: FS-002, FS-004. FS-002 is
recovered on a face carrying `brick_inclusion`, `exposed_aggregate` and `broken_face`. FS-008
and FS-010 carry **no feature on any face**, so no query over faces can return them. Both have
classified regions; all of them are clusters. This is Loss 2, not a classifier failure.

**D1 and D2** return all twelve because the rules they use test an orientation that is never
computed, so the test cannot run and excludes nothing.

**D3** returns 68 of 87 faces because face area is the convex hull of the plane inliers and the
rule reads it as a contiguous bearing area.

## Attaching clusters to nearby faces was tried and rejected

The obvious repair is to attach a cluster's features to the plane face it sits on. It was
implemented on 2026-08-27, measured, and reverted.

`segment_regions` already claims every triangle within 8 mm and 30° of a plane for that
plane's region. A cluster is therefore, by construction, the surface that is **not** on any
plane, and attaching one is asking to reverse a decision the segmentation has already made.

Measured, the clusters are not marginal cases:

| fragment | cluster | median distance to nearest plane | normal angle |
|---|---|---:|---:|
| FS-008 | region 2 | 323 mm | 92° |
| FS-008 | region 3 | 230 mm | 77° |
| FS-008 | region 0 | 83 mm | 41° |
| FS-012 | region 0 | 84 mm | 84° |
| FS-012 | region 5 | 27 mm | 35° |

FS-008's region 2 lies a third of a metre from its closest plane and perpendicular to it.
Attaching its features would record that a flat face carries a condition observed on a
different surface facing another direction. That is a false entry in the record, and it would
corrupt the provenance the audit exists to protect.

**So the finding is not an indexing fault.** The features found on clusters are correctly
located on those clusters. There genuinely is no planar face carrying them. What the corpus
shows is a mismatch of a different kind: the design rules are written over planar bearing
faces, and most of a demolition fragment is not planar. Of 148 regions, 65 are clusters and 12
are residual, so roughly half the segmented surface is irregular by construction, and it is
also the readable half, since clusters are classified at 75% against 23% for planes.

### What did work: recording that the two surfaces meet

Proximity was the wrong relation. Adjacency is the right one, and it is available: two regions
sharing mesh edges are physically continuous, whatever their orientations.

A cluster can meet several faces, so the shared boundary is weighted and a face claims the
region only when it takes at least half of it. Measured over the corpus, 17 of the 25 linked
clusters touch more than one face, up to six, so the dominance test is doing real work. The
recorded shares run from 0.55 to 1.00 with a median of 0.82, so nothing sits marginally at the
threshold. On FS-010 the region carrying `brick_inclusion` shares its entire boundary with a
single face.

This is written to `adjacent_features` on the face, kept apart from `features`, which still
means "observed on this face". **No design rule reads the new field.** A broken surface meeting
a formwork face does not make that face broken, and the record does not say it does. The eight
bearing rules see exactly what they saw before, and the frozen query results are unchanged.

What it changes is retrieval:

| | |
|---|---:|
| classifications on non-planar regions | 49 |
| linked to the face they meet | 25 |
| faces carrying features of their own | 16 of 87 |
| faces carrying an adjacent feature | 19 of 87 |
| **`--label` retrieval before** | 17 of 39 observations, 44% |
| **`--label` retrieval after** | **32 of 39, 82%** |

`--label brick_inclusion` now returns FS-010 and reports the evidence as sitting on a surface
meeting a named face, rather than silently omitting the fragment. The seven observations still
unreachable are clusters straddling several faces without a dominant one, which the rule
declines to attach, and that is the correct outcome rather than a shortfall.

The pipeline can therefore describe irregular fracture surfaces and cannot act on them. That is
a limitation of the rule vocabulary, not of the descriptors, the classifier, or the record
structure. It generalises: any reuse framework that reasons through planar bearing faces will
systematically ignore what most distinguishes demolition material, which is its fracture
geometry.

## What this means for the paper

The two dominant failures are structural and sit either side of the model. The UV layout
decides what can be looked at, and the region-to-face indexing decides what can be acted on.
The classifier itself answered 65 of the 65 regions it was given.

Stated as a proportion: of 148 segmented regions, 56% are lost to how the texture is packed and
a further 33% to how the observation is indexed. The remaining 11% is what the design rules
ever see.
