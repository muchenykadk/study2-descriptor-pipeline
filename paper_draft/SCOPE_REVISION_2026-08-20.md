# Study 2 scope revision

2026-08-20. Written after the held-out validation. Supersedes the surface-descriptor claims
in `EKA_full_paper_draft_rev1.md` §4, §5.1 and §6.2. Evidence in
`04_schema/CLASSIFIER_BEHAVIOUR.md` and `05_output/test_set_labels.csv`.

> **Status 2026-08-25: applied.** The edits in §4 below are carried into
> `EKA_full_paper_draft_rev2.md`. This file is kept as the reasoning behind them. The one
> item still open is the §5.2 retrospective evaluation, which has no results yet. The method
> behind the numbers is written up in `CLASSIFIER_BEHAVIOUR.md` §0.

---

## 1. What changed

The vision-language layer was measured against a human-labelled held-out set for the first
time, with a null-model baseline:

| | TP | FP | FN | recall | precision | exact match |
|---|---:|---:|---:|---:|---:|---:|
| null model — always answer `broken_face, exposed_aggregate` | 39 | 13 | 10 | 80% | 75% | 11/26 |
| the classifier | 39 | 20 | 10 | 80% | 66% | 10/26 |

**The classifier does not exceed a model that looks at nothing.** Identical recall, worse
precision, one fewer exact match. Per feature:

```
broken_face        95% recall, 80% precision     present on 81% of tiles
exposed_aggregate 100% recall, 72% precision     present on 69%
brick_inclusion     0 of 5
formwork_face       0 of 2
rebar_visible       0 of 1
pipe_opening        0 of 1
```

The two frequent features are recovered; every distinctive one fails. 25 of 26 tiles received
one of two answers.

This is not a tuning problem. It survived a taxonomy rebuilt around observability, exemplar
calibration, three-vote consensus, batch-size reduction and prompt revision.

## 2. What the objectives can still claim

**Objective 1, Foundation — unaffected.** Study 1 and the requirements scheme stand.

**Objective 2, Instrument — stands, with the vision layer rescoped.** The pipeline exists and
runs end to end. Its geometric half is sound and independently verified: oriented bounding
box, volume, mass and planarity recomputed from the GLB match the stored records exactly on
FS-005, FS-010 and FS-012. Handling class, drill zone and connection strategy derive
traceably from measured geometry. What cannot be claimed is that the surface-descriptor
layer works.

**Objective 3, Evaluation — strengthened, not weakened.** The objective was to *evaluate*
the descriptors against Study 1's decisions. An evaluation that returns a negative result
for one layer is an evaluation. The pipeline now has something most prototype papers lack:
a controlled measurement of its own limits.

## 3. What the paper should claim instead

Four contributions the evidence supports.

**A geometry-driven descriptor pipeline, verified.** Independently reproducible from the
mesh. This is the working instrument and should be the centre of §4.

**Capture resolution as the governing variable.** Texel density, pixels of atlas per
millimetre of real surface, decides what any downstream method can see, and it is set by
bake parameters nobody thinks of as data parameters. Raising `BAKE_RES` from 1080 to 4096
and the UV island margin from 0.02 to 0.002 moved the corpus from 0.24 to ~1.5 px/mm, a 42×
change in pixels per face. Measured consequences at the low setting: single-colour diamond
artefacts, regions unclassifiable, 62% of blind-sampled tiles unreadable. This is a
transferable methods finding for anyone doing photogrammetric material inventory.

**A resolution-bounded taxonomy method.** Categories derived from what the capture resolves
rather than from inspection practice. `crack` retired at 0.5–3 px wide; `spalling` retired
because its defining lip is larger than the sampling window; `weathered` retired for needing
an out-of-frame reference; `fracture_surface` and `spalling` merged into `broken_face`
because an expert annotator could not separate them either. ACI 201.1R, EN 1504, CODEBRIM
and dacl10k all assume in-service structures at close range; neither holds for demolition
debris under handheld photogrammetry, and their categories cannot transfer intact.

**A controlled negative result on open-vocabulary VLM classification.** With a null-model
baseline, a held-out set the model never saw, and a named failure structure. Two findings
inside it are individually citable:

- *Fabricated localisation.* Every bounding box the model produced was invented: 68 of 68
  coordinates exact multiples of 10, 17 detections drawn from 7 distinct boxes, `[40,40,60,60]`
  appearing six times across different fragments and different features. Three of the boxes
  checked pointed mostly at masked-out non-material. The model fills a coordinate field
  whenever asked, whether or not it can locate anything.
- *Default-answer behaviour.* Presented with a feature list, the model returns the
  statistically safe subset and does not report the distinctive features that are actually
  present. It reported `discolouration` on 8 of 26 tiles where the truth was 1, including
  reading the orange of a cast-in brick as staining.

Both belong in §6.2, which currently discusses VLMs for material characterisation in the
abstract and can now do so from measurement.

## 4. Concrete edits

| section | change |
|---|---|
| §2.1 obj. 2 | "extracts geometric and surface descriptors" → geometric descriptors, with surface descriptors as an evaluated and bounded component |
| §4 | lead with the geometric pipeline; present the vision layer as one stage with a stated validation outcome |
| §4 | add capture-resolution accounting: texel density per fragment, and what it admits |
| §5.1 | replace any accuracy claim with the null-model comparison table |
| §5.1 | report coverage honestly: 44% of region area never reaches the classifier; 33% of blind-sampled tiles unreadable |
| §5.2 | retrospective evaluation runs on geometric descriptors; surface descriptors enter only where validated |
| §6.2 | rewrite from measurement: null-model result, fabricated boxes, default-answer behaviour |
| §6.4 | limitations become findings with numbers rather than caveats |
| Table 1 | 11 active features, resolution-bounded, with the retired ones and their reasons |

## 5. What is NOT worth doing before the deadline

- Training or fine-tuning a detector. Weeks, and the corpus is 12 fragments.
- Rescanning at higher resolution. The capture campaign is finished.
- Chasing accuracy with prompt variants. Five have been tried; the failure is structural.

## 6. What IS worth doing, in order

**1. Test binary framing.** ~3 calls, on the existing 26 tiles.

The model is asked to choose from eleven features at once, and defaults to the safe pair.
Asking one yes/no question per feature removes that pressure entirely: *"Does this image show
brick or masonry cast into the concrete?"* has no safe answer to retreat to. This is the
single most likely thing to move `brick_inclusion` off 0 of 5, and it is cheap enough to try
before anything else. If it works, the finding changes from "VLMs cannot read this material"
to "VLMs cannot answer multi-label questions about it, but can answer targeted ones" — which
is more useful and still honest.

**2. Classify from the source atlas rather than the bake.** The Scaniverse export carries an
8192 texture over 133k triangles at ~2.75 px/mm, against ~1.5 after the bake. The bake is a
lossy intermediate that also introduces the directional smear. Worth one fragment's test.

**3. Largest-blob cropping.** Recovers part of the 44% of region area currently dropped, and
is independent of everything above. See `PLAN_fixes_2026-08-20.md` P1.

**4. Re-run the corpus once**, whatever the outcome, so the geometric records are consistent
and the paper's numbers come from one state of the code.

Steps 1 and 2 are experiments with a defined stopping point. If neither moves
`brick_inclusion` off zero, the negative result is the result, and §6.2 writes itself.
