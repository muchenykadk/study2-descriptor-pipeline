# Query validation, 2026-08-27

Seven decisions in `study1_decisions.md`, six of them runnable. Each query was run twice
through `03_src/query.py`, once with the full record and once with `--geometry-only`.

**Status: provisional.** Table B was not encoded and frozen before running, and the mapping
from each ledger row to a query was chosen with the descriptors visible. The evidence column
in Table A is empty, so the ground truth is unverified. D5 is unfilled and D7's indices are
flagged as unusable. These results show where the pipeline stands; they are not yet a
validation result.

## A bug found in the process

`query.strip_surface`, which builds the geometry-only baseline, removed `surface_label` and
`anomalies` from each face but not `features`. The design rules had been migrated to the
multi-label `features` set on 2026-08-20 and the baseline was never updated, so
`design_assignment` still returned `show_face` with the surface descriptors supposedly
withheld.

**Every geometry-only run before this date was answered with the surface classification still
in place**, and any comparison drawn from one is void.

Repaired at source rather than by adding a third `pop`: the surface-derived face keys are now
declared once, as `design_factors.SURFACE_FACE_KEYS`, beside the rules that read them, and
`strip_surface` iterates that list. A rule that starts reading a new surface key must add it
there or the baseline leaks it.

## Result

Run after FS-001 was re-processed, so the pool is twelve fragments and 87 faces.

| row | query | full | contains | geometry-only | contains | verdict |
|---|---|---:|---|---:|---|---|
| D1 | `--use leaning_support` | 12 of 12 | 1 of 1 | 12 of 12 | 1 of 1 | returns everything |
| D2 | `--handling excavator` | 12 of 12 | 3 of 3 | 12 of 12 | 3 of 3 | returns everything |
| D3 | `--connection direct_bolt --reliable-only` | 12 of 12 | 4 of 4 | 12 of 12 | 4 of 4 | returns everything |
| D4 | `--use seat_block` | 4 of 12 | 1 of 2 | 4 of 12 | 1 of 2 | selects; misses FS-003 |
| D6 | `--assignment show_face` | 2 of 12 | 1 of 3 | 0 of 12 | 0 of 3 | selects; misses FS-008, FS-010 |
| D7 | `--use planter_void` | 0 | empty | 0 | empty | correctly returns nothing |

Containment is trivially satisfied wherever the query returns all twelve fragments, so it
should not be read as a success on D1, D2 or D3.

### D3 at face level

`query.py` reports fragments. Scored directly against the 84 faces, with the documented
positives being the eight indices in the D3 row:

| | value |
|---|---|
| pool | 84 faces |
| documented positives | 8 |
| returned | 68 |
| recall | 0.88 |
| precision | 0.10 |
| null query returning every face | recall 1.00, precision 0.10 |

The rule is worse than returning everything: lower recall at identical precision. It also
returns 6 of 8 faces on FS-007 and 6 of 8 on FS-012, the two fragments recorded as having
taken no timber connection.

## What this shows

**Surface characterization changes the outcome of one query in six.** D6 is the only row where
withholding it alters the result. D1, D2, D3, D4 and D7 return identical sets with the vision
output removed, so on this corpus they are answered from geometry alone.

**Three of six queries return all twelve fragments.** `leaning_support` and
`pedestal_support` admit every face of every fragment and carry the caveat "orientation
unverified": the resting pose is not computed, so the rule cannot test the angle it exists to
test and therefore excludes nothing. `handling_class` returns `excavator` for all twelve
because its threshold is 800 mm and the shortest fragment is 957 mm at its longest dimension.
That rule is sound and the corpus simply sits entirely on one side of it.

**`connection_strategy` does not discriminate at face level.** The cause is known:
`area_m2_est` is the convex hull of the plane inliers rather than a contiguous bearing
surface, so the area test admits faces with no continuous area to bolt to.

**The show-face decision is partly unreachable.** FS-008 and FS-010 carry no feature on any
face, so no query can return them. This is the face-label gap: features are classified on
regions, most regions are non-planar, and only planar faces reach the design rules.

**D7 behaves as Category D requires**, and for two different reasons, which is the most
substantive result here.

On FS-001 the opening is plainly visible in the atlas, its own texture passes every gate, and
it never reaches the model because the smear gate discards its whole region.

On FS-002 the model finds it. Region 8 returns `pipe_opening` alongside `rebar_visible`,
`exposed_aggregate` and `broken_face`. It then disappears, because region 8 is a cluster with
`plane_index: None`, and `planter_void` requires `requires_face: {labels: ['pipe_opening'],
scan_reliable: true}`. A feature classified on a non-planar region has no face to attach to,
so no query over faces can ever return it.

That is the face-versus-region gap with a consequence attached. It is not that the descriptor
is missing, nor that the vocabulary lacks the category, nor that the model failed. The record
holds the observation and the query language cannot reach it, because the two are indexed
differently.

## FS-001 re-processed, and what it showed

FS-001's record was dated 2026-08-19 and carried the retired vocabulary (`fracture_surface`,
`staining`, `weathered`), because `--exclude` skips a fragment without clearing its existing
record. It was re-run on 2026-08-27 from the 5,654,800-triangle GLB already on disk. The
record is now current: 8 faces where the stale one had 5, 2,668 kg, and the corpus pool grows
from 84 faces to 87.

**The pipeline measured its atlas at 0.20 px per mm**, against `CALIB_PX_PER_MM = 0.46`, the
density the gates were tuned at. The gates did real work at that density: of 15 regions, 6
were withheld, three for UV fill between 1% and 3%, one for UV coherence 0.19, and two for
85% and 96% unusable texture.

**The nine surviving regions then returned the base rate.** Eight of nine came back as exactly
`exposed_aggregate` and `broken_face`, each at 3 votes of 3.

I expected this to demonstrate the observability bound: low density, gated classification,
category withheld. It does not, because FS-001 is not anomalous.

| | regions classified | returned exactly the two commonest features |
|---|---:|---:|
| FS-001 (0.20 px/mm) | 9 | 89% |
| corpus, all twelve | 65 | 80% |
| FS-003, 005, 006, 007, 008, 011 | 30 | 100% |

Six of twelve fragments returned nothing but `exposed_aggregate` and `broken_face` on every
region they classified, at full texture resolution. FS-001 at less than half the calibration
density sits nine points above the corpus mean and below three fragments that are at 100%.

**Resolution is not what separates an informative classification from an uninformative one on
this corpus.** The 80% figure matches the null model already on record, which answers the two
commonest features unconditionally and reaches 80% recall. At region level the classifier is
close to that null across the whole corpus, and unanimity does not indicate otherwise: every
one of those base-rate answers carried 3 votes of 3.

The five fragments that produced discriminating labels are FS-002 at 25%, FS-004 at 40%,
FS-012 at 43%, FS-009 at 67% and FS-010 at 80%, and those are the fragments carrying
`brick_inclusion`, `tile_remnant`, `rebar_visible`, `pipe_opening` and `biological_growth`.

## FS-001 re-baked at 2048, and why the pipe opening still fails

FS-001 was re-baked on 2026-08-27 from the Polycam export onto the existing 5,654,800-triangle
remesh, skipping the voxel remesh entirely (`02_blender/bake_texture_v2_retarget.py`). Texel
density rose from 0.20 to 0.38 px per mm, and the new atlas carries 1.39 times the
high-frequency energy of a Lanczos upscale of the old one, so this is recovered detail rather
than interpolation.

What it bought: base-rate answers fell from 89% to 67% of classified regions, and
`biological_growth` appeared on two regions, a feature the 1080 atlas never produced anywhere.
FS-001 also lost its `show_face` assignment, removing a false positive it had been
contributing to D6, which returns to two fragments.

**`pipe_opening` still does not appear, and the cause is now established rather than
inferred.** The opening is at roughly (1364, 1693) in the 2048 atlas. Its own texture is clean:
`directional_smear` does not mask it and `featureless_fill` flags 0% of that area. It is
plainly visible by eye. It fails because it sits inside a cluster region that the log reports
as 73% unusable texture, and the smear gate is all-or-nothing at region level, so the region is
discarded whole and the clean quarter containing the opening goes with it.

This rules out every earlier hypothesis. Not bake resolution: the opening was equally readable
at 1080. Not segmentation splitting the feature: it is intact. Not the featureless gate, not
the exemplar set, not the geometry. A readable, unambiguous, exemplar-matched feature never
reached the model because a neighbouring part of its region was smeared.

It gives D7 a much stronger reading than "no face carries `pipe_opening`". The feature is
physically present, visible in the atlas, and inside the classifier's vocabulary. What prevents
it being reported is a gate that discards regions wholesale.

**Fixed in passing:** `directional_smear` and `featureless_fill` both dilated past their own
`valid` mask via the morphological close and hole fill, so the mask spilled onto pixels it was
never measured against. Atlas-wide on FS-001 that reached 105% of the real surface. Both now
clip to `valid` on return. This inflated every smear fraction in the corpus, so the withheld
areas reported in every run before 2026-08-27 are overstated. It does not recover FS-001's
opening: that strip is genuinely 53% smeared either way.

**Not re-run after the fix.** The region cache keys on the region partition and the prompt, not
on the crop images, so a re-run would replay the old answers against new crops. No other
fragment has been re-run either, so the corpus stays internally consistent at pre-fix.

## Before this can be reported

1. Encode Table B and freeze it before re-running.
2. Fill the evidence column.
3. Re-fill D7 from the photograph: `FS-001[6]` is out of range on a 5-face fragment and the
   brackets repeat D3's patterns.
4. Fill D5, or drop it and re-state the allocation.
5. Confirm the D3 reading: 8 independent faces gives 7 of 8, four surfaces gives 3 of 4.
6. Decide whether FS-001 belongs in the pool. It is the heaviest fragment at 2,562 kg and
   appears in no documented decision.
7. Record whether the six fragments unlisted in D3 took a connection. Precision currently
   rests on two confirmed negatives.
