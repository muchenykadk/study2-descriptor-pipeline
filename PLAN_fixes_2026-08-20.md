# Fix plan — issues found after the 12-fragment run

Status 2026-08-20. Evidence in `04_schema/CLASSIFIER_BEHAVIOUR.md`.

Ordered by impact, not by effort. P1 invalidates the API cache, so it should land before the
corpus is re-run, or the credit is spent twice.

---

## P1 — 44% of surface area never reaches the classifier

**The problem.** Across seven fragments, 44 of 83 regions were dropped before the model saw
them: 21 `fragmented_uv` (24% of area), 19 `sparse_uv` (15%), 4 `unreliable_texture` (5%).
This is upstream of everything else. When `cast_in_brick` is visibly present on FS-010 and
only one region reports it, the reason is that 10 of that fragment's 13 regions were
dropped. It is also the most likely reason `formwork_imprint` and `rebar_visible` are absent
corpus-wide.

**The cause.** Regions are geometric. `segment_regions` groups faces by plane and normal;
Smart UV Project then packs those faces by available space rather than by position on the
fragment. A region's UV footprint is therefore a scatter of thin slivers, and the bounding
box that gets cropped is mostly other regions and empty sheet. Both gates are measuring that
scatter correctly — `uv_coherence` for how broken it is, `uv_fill` for how much of the crop
is real surface. Neither is wrong. The crop is.

**The fix.** Crop the largest connected component of the mask instead of the bounding box of
the whole scattered footprint.

In `build_region_crops`, after rasterising:

1. Label connected components of the mask.
2. If `fill < FILL_MIN` or `coherence < COHERENCE_MIN`, take the largest component and
   recompute the bbox, fill and coherence from it alone.
3. Skip only if the largest component *still* fails.
4. Record `blob_area_frac`: what share of the region's total mask the classified blob
   represents.

**Step 4 is not optional.** Cropping to one blob means the label is read from part of a
region and then applied to all of it. That is an extrapolation, and it has to be visible in
the record and in the report, or the coverage figure becomes dishonest in the other
direction. A region classified from 40% of its own footprint should say so.

**Expected effect.** Targets both gates, so up to 39% of surface area. Unknown how much is
recoverable until it runs — some regions are genuinely shredded and will still fail.

**Effort.** Small. One function, plus a column in the report.

**Test.** Re-run FS-010 with `--geometry-only` first: the gate messages print without
spending credit, so the new classified/dropped split is visible for free.

---

## P2 — The five `crack` detections are probably reinforcement

**The problem.** Zero `rebar_visible` across 39 regions, despite three exemplars. Five
`crack` detections, all boxed. `PLAN_texture_quality.md` §2b predicts exactly this: a
protruding bar is too thin for photogrammetry to reconstruct, so it is absent from the mesh,
fully present in the photographs, and baked onto the geometry behind it as a dark line on a
flat face. One feature, two errors.

This matters more than its share of the corpus. The two labels have opposite design
consequences: a crack says the piece may fail; exposed steel says it needs cutting back and
sealing and cannot be drilled freely.

**Fix, step 1 — look at them.** Crop the five boxes from their atlases and inspect. Free,
and it settles whether this is theory or fact. If they are bars, the corpus currently has
five false cracks and five missed bars.

**Fix, step 2 — a colour test, if step 1 confirms it.** Ferrous colour is the one cue that
separates them, and the hints already say so. A crack is a shadow: desaturated, the same hue
as the surrounding concrete, and it wanders. A flattened bar carries rust orange-brown or
steel grey, runs straight, and holds constant width. Measure saturation and hue inside the
box against the region median and reclassify, or at minimum flag the detection as ambiguous.

Concrete is close to neutral, so a saturated warm hue inside a thin dark feature is a strong
and simple signal. This is the tractable option named in §2b and never attempted.

**Effort.** Step 1 trivial. Step 2 small, contained in `region_classification.py`.

**Do not** simply raise the bar for `crack`. At 1.5 px/mm a crack is 0.5–3 px wide and
mostly unresolvable, so a stricter threshold would suppress the symptom without recovering
the bars.

---

## P3 — `exposed_aggregate` fires on 38 of 38 regions

**The problem.** It is a constant. A descriptor that is always true cannot separate one
fragment from another, cannot support a query, and never wins display precedence — which is
why it shows in the legend and never in the combined viewer.

**Two explanations, and they need separating before anything is claimed.**

*It is true.* These are broken fragments of one concrete and every break exposes the same
aggregate. Then the finding is that aggregate exposure does not vary in this stock, and the
descriptor belongs at fragment level, reported once.

*The model is anchoring.* `fracture_surface`'s rule ends "Nearly always co-occurs with
exposed_aggregate; report both." That sentence was added to stop the old schema suppressing
aggregate. It may now be producing the pair as a unit rather than two judgements.

**The test.** One fragment, one prompt variant with that sentence removed, three runs. If
aggregate still returns on every region, it is real. If it drops out, the co-occurrence was
instructed rather than observed.

**Effort.** Tiny — one config flag and 3 API calls. Highest value per unit of work in this
document, because it decides what §5 is allowed to say.

---

## P4 — Re-run the five stale fragments

FS-001, 002, 003, 004 and 007 still carry pre-multi-label records. Nothing corpus-wide can
be quoted until they match.

FS-001 and FS-007 are also still 1080 atlases at roughly 0.24 px/mm and should be re-baked in
Blender at 4096 before they are worth classifying at all.

**Order:** land P1 first, then re-run all twelve in one pass. P1 changes the crops, which
changes the cache key, so re-running before it means paying twice.

---

## P5 — The viewer's point-cloud mode is single-label

**The problem.** Two feature views exist. The **Feature Map** chips swap in the per-feature
`_feat_*.png` and work correctly — clicking `exposed aggregate` will show it. The **Feature
Labels** toggle colours each point from `p[4]`, one integer per point, so a point can only
carry the feature that wins display precedence. Aggregate can never appear there.

**The fix.** Store a bitmask alongside the winning id: sixteen active features fit in a
single integer. `p[4]` stays as it is so nothing existing breaks; a new element carries the
set. The point view can then isolate any feature by testing a bit, and the default combined
view keeps using precedence.

**Effort.** Medium, and it is presentation only — no descriptor changes, no re-run, no API
cost. Lowest priority for that reason: it changes what you can see, not what is true.

---

## Suggested order

| | task | cost | why here |
|---|---|---|---|
| 1 | P2 step 1: inspect the five crack boxes | free | settles a correctness question with existing data |
| 2 | P3: the anchoring test | 3 calls | decides what §5 can claim; cheapest real answer |
| 3 | P1: largest-blob cropping | no calls to test | biggest effect, and must precede any re-run |
| 4 | P4: re-bake FS-001/007, then re-run all twelve | full corpus | one pass, after P1 |
| 5 | P2 step 2: ferrous colour test | small | only if step 1 confirms |
| 6 | P5: viewer bitmask | none | presentation only |
