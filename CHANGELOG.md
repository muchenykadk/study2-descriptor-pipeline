# Changelog

Format: `[version] YYYY-MM-DD — description`  
Versions: `v0.x` = pre-release development, `v1.0` = first full fragment processed end-to-end.

---

## [v2.0.6] 2026-08-27 — Face area is now a surface, not a hull

**Every area rule was reading a number that overstated the surface by a median factor of
six.** `area_m2_est` is the convex hull of a RANSAC plane's inliers. On fractured material
those inliers are not a surface: a plane region holds a median of 390 disconnected patches and up to 40,224, because
an original cast face survives demolition only as pieces between the breaks. The hull spans the
gaps. Measured against the true surface of the same plane the overstatement runs to 43.7x at
worst, and 39 of the 71 faces that own any surface are overstated more than
fivefold, 25 of them more than tenfold.

**And 16 of 87 faces own no mesh surface at all.** Segmentation assigns each triangle to its
nearest qualifying plane, so a weak fit can end up with none of them. Those faces reported
hull areas summing to 10.8 m² for surface that does not exist, and passed area thresholds on it.

Every rule that reads an area is asking whether something can sit on the face, which needs one
continuous piece. `regions.segment_regions` now computes `contiguous_area_m2`, the largest
connected patch, and `n_patches`. `design_factors.usable_area_m2()` prefers it, falling back to
the hull only for records written earlier. Faces owning no surface are written as zero rather
than falling back. Every area predicate in `design_factors.py` and `query.py` reads through it.

No threshold was changed. The rules are as they were; the value they are given is now the one
they always meant.

Effect on the frozen evaluation:

| row | before | after |
|---|---|---|
| D1 leaning back-rest | 12 of 12, recall 1/1 | **5 of 12, recall 1/1** |
| D3 connection face | 68 of 87, recall 7/8 | **26 of 87, recall 6/8** |
| D4 seating platform | 4 of 12, recall 1/2 | **3 of 12, recall 1/2** |
| D2, D6, D7 | | unchanged |

`direct_bolt` fell from 70 faces to 26, `adaptive_bracket` rose from 3 to 15, `gravity_only`
from 14 to 46, and `cut_candidate` began firing on the two fragments that genuinely have no
usable bearing face. All six rows now narrow the field while keeping part of the documented
answer, against two at the start of the day.

**The cost is real and is recorded: D3's recall fell from 7 of 8 to 6 of 8.** Two documented
connection faces are no longer returned. 68 candidates at 0.88 against 26 at 0.75 is the better
shortlisting tool, and it is not a free improvement.

Known inconsistency: `report.py` still displays `area_m2_est`, so the interface shows the hull
while the rules use the contiguous area. Aligning it is outstanding.

No re-classification and no API calls: `segment_regions` reads plane equations, not areas, so
the partition and the crops are untouched.

---

## [v2.0.5] 2026-08-27 — Features read on fracture surfaces are now retrievable

**Three quarters of successful classifications reached nothing.** A feature is classified on a
surface region; a design rule and `--label` both read planar faces. Cluster regions carry no
`plane_index`, so 49 of 65 classifications were unreachable. On FS-010 the model read
`brick_inclusion` correctly and `--label brick_inclusion` returned nothing.

**Two changes, deliberately separate.**

*Rules that make no demand on flatness now evaluate over regions.* `exposed_face`,
`rough_feature` and `planter_void` specify no `max_fit_rms_mm`: they ask about surface
character, which a fracture surface answers as well as a cast one. `rough_feature` asks for
`broken_face` and `exposed_aggregate` and could not fire on a broken face. The eight rules that
put a load or a body on a surface still require a plane, because flatness is their function.
Show-face recall went from 1 of 3 to 2 of 3, and the planter reuse became expressible.

*Faces now record the fracture surfaces they meet.* Moving a cluster's features onto the
nearest plane was tried and rejected: the clusters sit 27 to 323 mm away at 35° to 141°, so it
would record a condition on a surface that does not have it. Adjacency is the honest relation,
so `adjacent_features` records that two surfaces meet, weighted by shared boundary, with a face
claiming a region only above a 50% share. 17 of 25 linked clusters touch more than one face, up
to six. `--label` retrieval rose from 17 of 39 observations to 32 of 39. **No design rule reads
the new field**, `features` still means "observed on this face", and the frozen query results
are unchanged.

Supporting additions: `regions.area_m2` so region-evaluated rules can compare against
thresholds stated in m²; `regions.adjacent_faces()`; `query._face_matches(include_adjacent=)`,
off by default and reported separately so a face match and an adjacency match are never
confused.

**A cache guard, found while doing this.** The region cache key covers the texture, the
partition and the prompt, but not how many regions passed the texture gates, and the crops are
numbered over those that did. The smear-mask fix in v2.0.4 could therefore change that count
while the key still reported a match, and cached answers would be read against the wrong
regions, silently. `classify_regions` now compares the count and re-classifies on disagreement.

**A bug in the migration, worth recording because it nearly shipped.** `backfill_regions.py`
first segmented without excluding the patched ground-contact face, while the pipeline excludes
it. That produced a different partition with different region ids, so every value written was
attached to the wrong region, across all twelve records. It surfaced only because a pipe
opening known to exist on FS-002 failed to link. The fields were stripped and rewritten, and
the script now refuses to write unless the fresh partition reproduces the saved one on kind and
area for every region.

---

## [v2.0.4] 2026-08-27 — Texture gates were masking pixels they never measured

**`directional_smear` and `featureless_fill` dilated past their own `valid` mask.** Both apply
`& valid` when building the mask, then run a morphological close, and `directional_smear`
additionally fills holes. Neither clipped back afterwards, so the mask spilled onto pixels
outside the surface it was measured against. On FS-001 the smear mask covered 105% of the real
surface atlas-wide, and the spilled pixels were charged to the region as unusable.

Every smear and featureless fraction recorded before this date is therefore overstated, and
regions were being withheld on inflated numbers. Both functions now clip to `valid` on return.
Blobs are still kept whole, which was the reason the close was there.

Related but separate: an earlier fix this month corrected the *reported fraction* to be measured
on-mask, after a face printed "109% of the face is unusable texture". That addressed the
arithmetic and left the mask itself growing, which is the cause fixed here.

**No fragment has been re-run.** The region cache keys on the region partition and the prompt,
not on the crop images, so a re-run would replay old answers against new crops. All twelve
records still carry the inflated figures and are at least consistent with each other.

Found while tracing why a pipe opening plainly visible in FS-001's atlas is never classified.
It is not the cause of that: the opening's own texture passes every gate, and it is discarded
because the smear gate drops whole regions and it shares one with a smeared area. See
`06_validation/deferred_defects_2026-08-27.md`.

---

## [v2.0.3] 2026-08-27 — The geometry-only baseline was never withholding anything

**`query.strip_surface` leaked the surface classification into the control condition.** It
removed `surface_label` and `anomalies` from each face but not `features`. The design rules
migrated to the multi-label `features` set on 2026-08-20 and the baseline was not updated with
them, so `design_assignment` still returned `show_face` under `--geometry-only`. Every
geometry-only run before this date was answered with the vision output in place, and any
full-versus-baseline comparison drawn from one is void.

Found while running the first query validation over the Study 1 decision ledger: all six
queries returned identical sets under both conditions, which is not a plausible result.

**Fixed at source.** The surface-derived face keys are now declared once as
`descriptors.design_factors.SURFACE_FACE_KEYS`, beside the rules that read them, and
`strip_surface` iterates that list rather than naming keys itself. A rule that starts reading
a new surface key has to add it there or the baseline leaks it. After the fix, D6
(`--assignment show_face`) drops from 2 fragments to 0 under `--geometry-only` and the other
five queries are unchanged, so surface characterization alters the outcome of one query in six
on this corpus.

Results in `06_validation/query_validation_2026-08-27.md`.

---

## [v2.0.2] 2026-08-25 — First clean corpus run; three root-cause fixes it exposed

The 2026-08-25 batch completed on all eleven textured fragments with the new taxonomy reaching
every pass. Result: 135 regions segmented, 59 classified, 52% of segmented area held back by
the gates. `broken_face` on 58 regions and `exposed_aggregate` on 54, both across all eleven;
`brick_inclusion` on 5 regions across 4 fragments; `paste_dominant` 5, `tile_remnant` 2,
`pipe_opening` and `formwork_face` 1 each; reinforcement on none.

**Phase 3A now speaks the current vocabulary.** The v2.0.1 fixes worked: no retired label
appears in any of the eleven records.

**And the two passes disagree.** The whole-atlas pass reports `rebar_visible` on 4 of 11
fragments; the region pass reports it on none. Same model, same vocabulary, same fragment,
different framing, opposite answers on the one category with a safety consequence. This is
now the strongest evidence for the framing finding, and it is written into §5.1, §6.2 and
§6.4 of `EKA_full_paper_draft_rev2.md`.

### Three fixes

**1. The plane search was never seeded** (`descriptors/geometry.py`). `segment_plane(seed=...)`
was wrapped in `try/except TypeError`, and no Open3D release accepts that keyword. 0.19 signs
it `(distance_threshold, ransac_n, num_iterations, probability)`. Every call raised and fell
through to the unseeded path, so `RANSAC_SEED` had no effect on plane fitting from the day it
was added. Three runs of FS-002 on identical input gave first-plane areas of 0.9995, 1.1011
and 1.0909 m². Shifting planes shift region ids, which invalidates the classification cache
and re-bills every API call. Fixed by seeding Open3D's global RNG through
`o3d.utility.random.seed`, which is the actual entry point and has existed since 0.16. The
2026-08-24 advice to upgrade Open3D was wrong; 0.19 was already installed and the version was
never the problem.

**2. `n_label_votes` stored the wrong number** (`ai/region_classification.py`). It held
`features[0]["votes"]`, the vote count of whichever feature sorted first. That read correctly
only while precedence put the commonest feature first, since it almost always polled 3 of 3.
Reordering precedence rarest-first in v2.0.1 made `features[0]` a rare feature, and this run
printed `exposed_aggregate(3/2)` on eight regions: three votes out of a denominator of two.
The vote counts were always right; the denominator was never the number of runs. Now stores
`n_runs`.

**3. Confirmed fixed from v2.0.1.** No unusable-texture percentage above 100 (highest 79%),
and no `Mean of empty slice` warning.

**4. The withholding is now real** (`descriptors/design_factors.py`, `report.py`). Until today
`drill_zone` and `finishing_requirement` were called "withheld" in the paper while the
pipeline computed and stored both in full. FS-010 carried `"rule": "no bars visible, but the
section is deep enough for a steel-free core..."` in a record described as holding neither.
`derive()` now writes a `_WITHHELD` block in their place, carrying `value: null`,
`data_status: "withheld"`, and the reason. The keys stay so that a reader sees the field
exists and why it is empty, and the functions that compute them stay, so re-enabling means
calling them again once the reinforcement reading is trustworthy. The report shows the reason
where the value used to be.

Confirmed on the user's machine: `o3d.utility.random.seed` is present in the installed 0.19.

**5. Concrete density corrected to 2500 kg/m³** (`descriptors/geometry.py`, now
`CONCRETE_DENSITY_KG_M3`). EN 1991-1-1 Annex A Table A.1 gives 24 kN/m³ for plain concrete and
25 kN/m³ for concrete with a normal percentage of reinforcement. These fragments come from a
reinforced building, the taxonomy carries `rebar_visible`, and `drill_zone` assumes a
reinforcement mat, so the reinforced value applies. The pipeline used the plain figure and
understated every mass by about 4%. No handling class changes, since all eleven fragments
already exceed the 800 mm dimension threshold. `preflight.py`, `report.py` and both schema docs
updated. The value now has a standard behind it instead of none.

Two other thresholds checked against standards at the same time. `max_mass_kg: 25` matches the
ISO 11228-1 reference mass for the general working population, though that is a figure for
*ideal* conditions which the standard requires to be reduced for grip and posture, and a
demolition fragment has neither. The 20 mm cover assumed in `drill_zone` needs an exposure
class attached: EN 1992-1-1 Table 4.4N, structural class S4, gives 15 mm for XC1 and 25 mm for
XC2/XC3, so the note claiming it sits below current minima holds outdoors and not indoors. The
50 kg two-person threshold has no source in either standard and looks optimistic; common
guidance puts a team lift near two-thirds of the sum of individual capacities, which would be
about 33 kg.

### Found, not yet fixed: the design-factor layer is starved by the schema

Segmentation produces RANSAC planes and fracture clusters. Only planes have an entry in
`planarity[]`, and `run_pipeline` skips any region whose `plane_index` is `None`. Across the
corpus, 57 regions were classified, 43 of them clusters. **Three quarters of successful
classifications are discarded before the design rules run.** Fourteen of 82 faces carry a
surface label; the rest default. That is why `design_assignment` returns `unassigned` on 63 of
82 and `show_face` exactly once, and it means classifier improvements would change almost
nothing until cluster regions can reach a face.

**6. Every derived outcome now records the same four things** (`descriptors/design_factors.py`,
new `_trace`). The three factors previously stored different things under the same key.
`handling_class` put an identifier in `rule` and the triggering measurement in `reason`;
`connection_strategy` and `design_assignment` put the rule's prose note in `rule` and recorded
no measurement at all. A reader could see why a fragment was excavator-handled and could not
see why a face got a direct bolt.

All four now return `value`, `rule` as `factor#n`, `note` as the rationale from the
configuration file, and `reason` as the measured values that satisfied the conditions:

```
connection_strategy#2   "area 0.451 m2 >= 0.1; RMS 1.53 mm <= 5.0"
design_assignment#2     "feature brick_inclusion"
handling_class#0        "longest dimension 1630 mm exceeds 800 mm"
```

The `factor#n` identifiers index the rule table in
`paper_draft/figures/derivation_rules_table_condensed.md`, so a record cross-references the
paper directly. This is what makes the traceability claim in §4 true rather than aspirational.

### Found, not yet fixed: face area is not the area of a surface

`area_m2_est` projects a plane's RANSAC inliers and takes their convex hull, so it measures the
extent over which the plane equation holds. A plane is unbounded, so those inliers can be
scattered, or lie on two parallel surfaces on opposite sides of the fragment. On FS-002 the
three largest faces (1.09, 1.02, 0.78 m²) have no connected patch of surface behind them:
segmentation, which works on adjoining triangles, found nothing there large enough to keep. The
flattest face of the eight, at 0.91 mm RMS, is one of them.

`connection_strategy` tests that figure against `min_area_m2` to decide whether a fixing plate
can be seated, and returns `direct_bolt` on 68 of 82 faces corpus-wide. The rule asks about a
contiguous bearing surface; the number describes a point set. Recomputing area from the region's
own triangles would fix it, and would also give the same figure to faces and regions, which
currently disagree. Written into §5.1 as a caveat on the connection result.

This is the same class of problem as the cluster gap: two steps that mean different things by
"a flat part of the fragment", with one step's output read as though it were the other's.

### Still open

The 2026-08-25 numbers were produced before the seeding fix, so the region count, the 44%
classified share, and the 52% declined area will shift on a seeded re-run. Per-feature counts
follow the surfaces and should move less. Regenerate before the paper is submitted.

---

## [v2.0.1] 2026-08-25 — Viewer showed one colour; two display bugs, no change to any recorded label

The corpus run of 2026-08-24 produced a 3D viewer that was uniformly `broken_face` red on
every fragment. The classification underneath was correct throughout. Two separate display
faults, both fixed, and the records themselves are untouched.

**1. `_display_precedence` was ordered rarest-last** (`env/taxonomy.json`). A face can hold
several features but can only be painted one colour, and precedence decides which. With
`broken_face` at rank 2 of 11 it won **61 of 72 classified regions across the corpus**, so
the map showed the one thing true nearly everywhere and hid everything else. FS-010 region 4
recorded `brick_inclusion` and still rendered as `broken_face`. Reordered rarest-first, so
inclusions now win the colour. Rendering only: no stored feature, vote or record changes, and
`prompt_sig` does not include this list, so the API cache stays valid and the re-run is free.

**2. The feature chip row was grouped by names that no longer existed** (`03_src/report.py`).
`_order` was hard-coded to `("manufacture", "inclusion", "defect")`, which the 2026-08-20
rebuild replaced with formation / composition / inclusion / colour. Only `inclusion` matched,
so every other chip was dropped without warning. On FS-010 the panel offered `brick_inclusion`
alone, and the two features actually covering the piece had no chip and no colour key, which
is why the red had no legend. Group names are now read from the taxonomy.

**3. The whole-atlas pass (Phase 3A) never received the new taxonomy** (`03_src/ai/vision_client.py`).
Two independent faults, found in the 2026-08-24 corpus log:

- The prompt was built from `TAXONOMY` instead of `ACTIVE`. `TAXONOMY` keeps retired ids so
  that stored `feature_id` positions stay valid, so the model was still being offered
  `weathered`, `crack`, `spalling`, `efflorescence` and `original_finish`. FS-007, the only
  fragment that made a live call, returned `weathered` and `discolouration`.
- `_cache_path` keyed on the image alone, with no prompt signature, so the 2026-08-20 rename
  never invalidated anything. Eleven of twelve records were written from answers cached before
  it and carry `fracture_surface` and `staining`, ids that no longer exist. Region
  classification has had a `prompt_sig` since it was written; this pass simply lacked one.

Both fixed. The Phase 3A cache is now invalid by construction, so the next run costs 36 fresh
whole-atlas calls. The region-classification cache is unaffected.

**4. Texture-quality fractions were measured against a grown mask**
(`03_src/ai/region_classification.py`). `directional_smear` and `featureless_fill` deliberately
reach past the region mask, so that a partly masked band is removed whole rather than left
ragged as perforation. Dividing that grown mask by the region's own pixel count reported
fractions above 100%, printed on 2026-08-24 as *"109% of the face is unusable texture"* on
FS-010 region 5, and skipped regions that were mostly sound. The fractions are now measured
on-mask; the masking behaviour is unchanged. Expect slightly more area to survive the gates.

**5. `cells_from_regions` warned and silently declined to clear UNSCANNED cells** when
`grid_n` does not divide the atlas evenly. The empty slice gave `nan`, `nan >= 0.3` is
`False`, so the cell stayed labelled. Guarded on `cell.size`.

**Corpus result on `brick_inclusion`**, the thing the taxonomy rebuild was meant to move:
found on FS-002 (3 regions), FS-004 (2) and FS-010 (1), against one detection across the
whole corpus before. Recorded correctly on 2026-08-24; only the display hid it.

Standing limitation, not a bug: with a multi-label vocabulary, an "All features" view that
paints one colour per face cannot show `broken_face` and `exposed_aggregate` together, and
they co-occur on nearly every classified region. The per-feature chips are the honest view.

---

## [v2.0] 2026-08-24 — Validated against held-out data; taxonomy rebuilt around what the capture resolves

The first version whose surface-descriptor claims rest on a measurement rather than on
inspection. Evidence in `04_schema/CLASSIFIER_BEHAVIOUR.md`, paper consequences in
`paper_draft/SCOPE_REVISION_2026-08-20.md`.

### The result that drove everything else
On 26 blind-sampled, hand-labelled held-out tiles, against a null model that answers
`broken_face, exposed_aggregate` and looks at nothing:

| | TP | FP | FN | recall | precision |
|---|---:|---:|---:|---:|---:|
| null model | 39 | 13 | 10 | 80% | **75%** |
| multi-label classifier | 39 | 20 | 10 | 80% | **66%** |
| one binary question per feature | 33 | 11 | 15 | 69% | **75%** |

The classifier does not exceed the null model. `broken_face` and `exposed_aggregate` are
recovered at rates a constant guess already achieves; every distinctive feature failed under
multi-label. Binary framing moved `brick_inclusion` from 0 of 5 to 2 of 5, the only evidence
that the model can identify a distinctive inclusion at all.

### Taxonomy rebuilt: 16 features to 11
Built from what a 250 mm tile at ~1.5 px/mm can resolve, not from inspection practice.

Retired with reasons recorded in `env/taxonomy.json`: `crack` (0.5–3 px wide at corpus texel
density, and every corpus detection was a false positive), `spalling` (its defining lip
against sound surface is larger than the sampling window), `weathered` (needs a fresh
reference never in frame), `efflorescence` (absent from 26 blind tiles),
`discolouration` (predicted on 8 tiles where truth was 1; 12% precision, and it was the whole
precision gap against the null model).

Renamed in place, so every stored `feature_id` still resolves: `formwork_imprint` →
`formwork_face`, `fracture_surface` → `broken_face`, `staining` → `discolouration` (then
retired), `cast_in_brick` → `brick_inclusion`. `saw_cut` added and removed after Muchen
confirmed no sawn faces exist in the corpus, which is itself an observation about the
demolition method.

`fracture_surface` and `spalling` merged into `broken_face`: separating them needs the
boundary against sound surface and the age of the exposed faces, and an expert annotator
could not apply the distinction to these tiles either.

Groups are now formation / composition / inclusion / colour, for reporting and citation only.

### Bounding boxes removed
Every box in the corpus was a stock value: 68 of 68 coordinates exact multiples of 10, 17
detections drawn from 7 distinct boxes, `[40,40,60,60]` six times across different fragments
*and* different features. Three of those checked pointed mostly at masked-out non-material.

The accurate reading is not that the model invented coordinates but that the schema demanded
a value it could not compute and offered no way to decline. Localisation is therefore
**disabled with its validation already built** (`ALLOW_LOCALISATION = False`): the prompt
states that null is a valid and preferred answer, `validate_box()` rejects a box that is less
than 50% on real material, `_is_stock_box()` rejects round centred coordinates, and a box
needs cross-run agreement at IoU 0.30. Turn it on when capture quality supports it.

### Prompt and call structure
Presence-only reporting, no coordinates. Reference block reworded: the exemplars are "a guide
to appearance, NOT a menu to choose from", after the calibrated run was observed returning
`pipe_opening` and `tile_remnant` alone and suppressing co-occurring features. `BATCH_SIZE = 3`
replaced whole-fragment batching; note that this did **not** fix the constant-answer
behaviour, since regions in separate calls still returned identical answers.

### Added — validation tooling
- `03_src/build_test_set.py` — blind-samples tiles at a fixed ~250 mm of real surface, with
  per-fragment texel density measured from the mesh. `--add` keeps already-labelled tiles.
- `03_src/score_test_set.py` — scores the classifier against the labelled tiles.
- `03_src/binary_probe.py` — one yes/no question per feature instead of a list.
- `03_src/agreement.py` — inter-run agreement from the cached votes, free, and it prints
  output diversity alongside so the figure cannot be read as accuracy.
- `03_src/control_test.py` — the earlier exemplar-based test, kept because its circularity is
  itself worth reporting.

### Design factors remapped, one rule deleted
`env/design_factors.json` rules keyed on renamed features were migrated; `assess_section_loss`
and `assess_contamination` were removed because their only triggers were retired.
`finishing_requirement()` now matches on the whole feature set rather than `surface_label`
alone, which was silently dropping every rule keyed on a non-winning feature.

### Corpus
FS-007 re-baked at 4096: 0.59 → **2.30 px/mm**, now the highest in the corpus. FS-002
re-exported with no change (already correct). FS-001 remains at 0.20 px/mm and is excluded
from texture claims: at 8.42 m² it is the largest fragment and a fixed atlas budget cannot
give it comparable density. Its geometry is unaffected and it stays in the geometric corpus.

---

## [v1.7] 2026-08-20 — Texel starvation fixed; two pre-flight checks for what the others could not see

### Fixed — the bake was starving the atlas of texels
`BAKE_RES` was `1080` in `bake_texture_v2.py` while `BLENDER_WORKFLOW.md` steps 32 and 41
have always specified 4096, and `smart_project(island_margin=0.02)` set the gap between
islands to **2% of the sheet width**, not 2 pixels. Measured on FS-002, the two together
left 20.4% of the atlas carrying any UV at all: 80% was margin and packing waste.

| | before | after |
|---|---|---|
| atlas | 1080 | 4096 |
| share of sheet carrying UV | 20.4% | 59.1% |
| px per mm of real surface | 0.24 | 1.57 |
| px per face | 0.07 | 2.83 |

At 0.07 px per face an island of a few faces averages to one colour, and the 32 px `EXTEND`
margin then bleeds that colour outward. **That is the whole mechanism behind the flat
diamond field** on FS-001 and FS-002, and it is why regions came back unlabelled: the model
was shown bled flat colour and correctly declined to call it anything.

The ceiling is the scan, not the bake. The Scaniverse source for FS-002 is a 8192 atlas over
132,693 triangles and resolves **2.75 px/mm**, so 4096 recovers about 57% of what the scan
holds in linear terms. Raising `BAKE_RES` to 8192 would pass the source and buy nothing.

### Fixed — the diagnostic fields never reached the record
`run_pipeline.py` filtered each region dict to a hardcoded key list, dropping
`uv_coherence`, `smear_frac`, `flat_frac` and `skipped`. The texture-quality gates ran and
recorded nothing, so an unlabelled region stored no reason and the report's Masked column
was always empty. This is why the FS-002 diagnosis had to be done by hand.

### Fixed — the 3D feature map read its labels back out of the atlas grid
Reported by Muchen: on FS-002 the pipe openings are unmistakable black holes, and the
`pipe_opening` colour in the viewer sat somewhere else entirely.

The region classification was right. Every region carried a sensible label with 3 of 3
votes. What was wrong was how the viewer recovered those labels: `build_viewer_data()` threw
away region membership and re-derived each face's label from whichever cell of a **16x16
grid over the atlas** its UV centroid landed in. Cells are won outright by whichever region
covers the most pixels in them, and Smart UV Project packs islands for space rather than by
position on the fragment, so a single cell routinely straddles islands from opposite ends of
the piece and hands them all one label.

Measured on FS-002, per face:

| | share of the faces the map coloured |
|---|---|
| correct | 65.5% |
| carrying another region's label | 14.7% |
| **invented** on a region the pipeline had declined to classify | 19.8% |

The last row is the worst of the three. Regions #0, #3 and #9 were left unlabelled on
purpose (fragmented UV, unreliable texture) and covered 38% of the surface. The grid handed
them a neighbour's label anyway, so the map asserted things the pipeline had explicitly
refused to say.

For `pipe_opening` specifically: 309,852 faces correct, 108,166 truly pipe openings shown as
something else, and **199,561 faces coloured as pipe openings that are not** — 39% of the
teal on screen.

`build_viewer_data()` now takes `face_labels`, the per-face taxonomy index that
`classify_regions` already produced and that the record has always reported under
`vision.face_labels`. The grid path is kept only as the fallback for `--grid-legacy` and
point clouds. No new API calls: the fix is downstream of classification, so a plain re-run
reuses the cache.

### Removed — bounding boxes. Every one in the corpus was fabricated.
Audit of all 17 localised detections across 12 fragments:

- **68 of 68 box coordinates were exact multiples of 10.**
- 17 detections used **7 distinct boxes**. `[40,40,60,60]` — dead centre — appeared six
  times, across different fragments *and* different features.
- Three of the boxes checked pointed mostly at magenta mask fill rather than material:
  `crack` on FS-005 #1 at 82% fill, #8 at 73%, and `pipe_opening` on FS-005 #9 at **85%**.
- Visual inspection of all five `crack` boxes: none contains a crack. They contain mask
  fill, directional smear and blurred wash.

The model fills the field whenever the schema asks for it, whether or not it can locate
anything. This is not a threshold problem — a validator that rejects a fabricated box would
have rejected all of them.

The prompt now asks for presence only: naming a feature means it appears somewhere in the
region, with no claim about where. `_merge_votes` drops box consensus, `anomalies` is kept as
an empty list so existing consumers do not break, and the report's "Boxed" column is replaced
by a feature count. **Nothing changes in the reference-exemplar workflow**: exemplars
calibrate what a feature looks like, not where it is.

The pipeline itself was recording faithfully throughout — the cached API responses contain
exactly what the model returned. The fabrication was the model's.

### Changed — regions are sent in small batches, not all at once
`BATCH_SIZE = 3` in `region_classification.py`. Sending a whole fragment in one request let
the model compare its regions against each other and settle on one reading for the batch:
**4 of 7 calls returned the identical feature set for every image in the request**, and
`exposed_aggregate` came back on 38 of 38 regions. `TAXONOMY_REVIEW.md` §3 named this
mechanism and it was never acted on.

Batch indices are reassembled to global region numbering, and `BATCH_SIZE` is part of the
cache key. Cost goes from ~3 calls per fragment to ~6. Set it to 1 for full independence at
~17 calls per fragment.

### Verified — the geometric half of the pipeline is sound
Recomputed independently from the GLB for FS-005, FS-010 and FS-012: oriented bounding box,
volume and mass all match the stored records exactly. `handling_class` traces to `max_dim`
and mass. Geometry, planarity, texel density and the texture gates are measured, not
inferred.

**One contaminated output, deliberately left for later:** `drill_zone` reads
`rebar_visible` from the face labels and reports "no bars visible, but the section is deep
enough for a steel-free core". The model has never once reported rebar, so this derives
drilling guidance from an untested negative. `finishing_requirement` has the same dependency.
Both are on hold until the classifier is trustworthy.

### Added — exposure, a second axis reported alongside the surface label
Muchen, on FS-004: the pipe openings map correctly now, but every legible region returns
`fracture_surface` and the obvious exposed aggregate is nowhere.

Nothing was misfiring. The two labels were competing for one slot per region, and
`exposed_aggregate`'s own decision rule surrendered: *"neither a cast face nor a break can be
read... do not use it merely because aggregate is present: it is present on most fracture
surfaces."* With `fracture_surface` at position 6 and `exposed_aggregate` at 8 under
first-match-wins, aggregate exposure could only be reported on a face whose origin was
unreadable. On a demolition fragment that is nearly no face at all. All four FS-004 regions
came back 3/3 votes: the model was consistent, the schema was wrong.

This is the origin/exposure conflation in `TAXONOMY_REVIEW.md` §2 arriving in the results.
The two are independent claims about the same face and both are true. CODEBRIM (Mundt et al.
2019) defines its classes as mutually non-exclusive for the same reason.

`exposure` is now its own section in `env/taxonomy.json` (`exposed_aggregate`,
`paste_dominant`), returned per region beside the surface label, voted independently across
the three runs, and recorded as `exposure` / `n_exposure_votes`. It is also carried onto the
planarity face so `design_factors.py` and `query.py` can read it. The prompt states
explicitly that it must not change the surface label.

Deliberately kept to two values. This is a descriptor a designer acts on, not a taxonomy to
defend.

**Open:** `exposed_aggregate` still exists as a surface label as well. It is now redundant
there and will keep losing to `fracture_surface`; retiring it would leave the two exemplars
in `reference_surfaces/exposed_aggregate/` calibrating the exposure axis instead. Not
changed without Muchen's call, since it affects the paper's Table 1.

### Fixed — `pipe_opening` restored as an anomaly, so a hole can be marked where it is
On 2026-08-19 `pipe_opening` was added as a surface label and the `opening` anomaly retired
in the same pass. A surface label is the identity of a whole geometric region; only an
anomaly carries a bounding box. From that moment the schema could say "this entire region is
an opening" but not "there is an opening here". Zero anomalies of any kind were reported on
FS-002, which has four obvious holes.

`pipe_opening` now exists on both axes, sharing an id the way `rebar_visible` already does.
`label_map_from_regions()` paints anomaly boxes for any label with a colour, so a hole takes
the teal inside region #1 while that region keeps `tile_remnant` as its surface identity.

### Added — `FILL_MIN`, a gate on how much of a crop is actually surface
`uv_coherence` is the largest connected blob over the total mask, so a thin winding ribbon
scores 1.0 while filling almost none of its bounding box. Everything outside the mask is
magenta, so the model was being asked to name regions from crops that were nine-tenths fill.
On FS-002: region #2 at coherence 0.97 and **10% fill**, region #5 at 0.84 and **7%**. Both
were classified. The two regions labelled `pipe_opening` sat at 33% and 29% fill and contain
no openings; region #1, at 80% fill, is the one that does.

`uv_fill` is now recorded on every region and gated at 0.20. **0.35 was tried first and left
2 of 10 regions covering 23% of the surface** — that removes the bad labels by removing the
fragment. 0.20 keeps four covering 39%. The remaining loss is a finding rather than a tuning
choice: it says the UV layout limits how much of a fragment can be read, not the classifier.

### Fixed — the report's atlas overlays, same cause
`build_feature_textures()` drew from the same 16x16 cells, so `_feature_map.png` and every
`_feat_*.png` carried the error too. The report was contradicting itself: its region table
read from `surface_label` and was right, its overlay images were not, on the same page.

`label_map_from_regions()` now paints one label per **pixel** from `crop["mask"]`, the exact
UV footprint each region was classified from. Regions are painted largest first so a small
one drawn later is not swallowed; anomaly boxes still override, clipped to their own
region's mask. Measured over the textured atlas on FS-002:

| | grid cells | region masks |
|---|---|---|
| share of atlas painted | 58.8% | 43.8% |
| ...of which the two agree | 79.9% | — |
| painted where the masks say nothing | **25.6% of everything the grid drew** | 0 |
| `pipe_opening` area | 14.0% of atlas | 10.7% |
| ...not actually pipe_opening | **45.2%** | 0 |

The map paints *less* now, which is the point: the grid was colouring 25.6% of its own
output over regions that were never classified.

Codes are int16 rather than label strings. At 4096 the atlas is 16.7 million pixels and an
object array costs a Python-level pass per operation; int16 keeps the map at 33 MB and every
test vectorised.

`grid_n`/`cells` remain the fallback for `--grid-legacy` and point clouds, which have no
regions to draw from.

**Not regenerable by `refresh_factors.py`.** It re-attaches existing `_feat_*.png` by glob
rather than rebuilding them, so the overlays only update on a real pipeline run.

### Fixed — the texture gates were tuned in pixels and broke at 4096
`directional_smear()` and `featureless_fill()` run on the full-resolution crop, and every
window in them was a pixel count tuned on FS-006 at a 1080 atlas, which resolves 0.46 px/mm.
A 9 px structure-tensor window was asking "is this ~20 mm of concrete directional?", which
is the right question: it spans a few aggregate particles, and concrete is directionless at
that scale while a grazing-angle smear is not.

At 1.45 px/mm those same 9 px cover 6 mm, which is *inside* a single aggregate particle,
where the texture genuinely does have one dominant orientation. Measured on the new FS-002
atlas:

| smear window | real-world span | flagged as smear |
|---|---|---|
| 9 px (old constant) | 6 mm | **75%** |
| 29 px (20 mm, scaled) | 20 mm | **29%** |

At 75% every region trips `SMEAR_SKIP = 0.50` and is dropped as `unreliable_texture`, so the
fragment would have come back entirely unclassified. **The gate would have reported the
resolution increase as damage**, and the failure would have looked exactly like the problem
the re-bake was meant to fix.

All six windows are now declared in millimetres of surface and sized per fragment from
`texel_density(mesh, atlas_size)`. At 0.46 px/mm they evaluate to 9, 5, 25, 15, 9, 21, which
are the original constants exactly, so nothing changes for the atlases already processed.

Morphology is now separable (`_open_sq`, `_close_sq`): a square structuring element erodes
as (n,1) then (1,n) for an identical result at O(n) instead of O(n²). At 4096 the windows
are four times wider and the 2-D form did not finish in two minutes on a full atlas.

### Changed (Muchen) — FS-003 to FS-006 cleared for re-scanning
All four are being re-scanned, so their inputs, descriptor records, reports, viewer JSON and
feature maps are removed rather than left to be silently compared against. Their entries in
`mesh_signatures.json` are dropped too: that cache is what `_check_duplicate` compares a new
export against, and a stale signature would either raise a false duplicate or mask a real
one. FS-001 and FS-007 are untouched.

**Four hand-picked exemplars were kept**, from FS-004 (`cast_in_brick`), FS-006
(`exposed_aggregate`, two) and FS-007 (`fracture_surface`). They are the only exemplars
those two labels have. The images are still valid calibration: same building, same features,
and an exemplar's claim is about what a label looks like in this material, not about a
fragment that appears in the results. Their filenames now name fragments whose records no
longer exist, which the paper's reference-set provenance column has to account for.

### Changed (Muchen) — FS-002 reassigned to a different physical piece
The export in FS-002's folder measures 1630 x 934 x 706 mm; the piece that held the id until
now measures 858 x 737 x 501 mm. Muchen kept the id on the new piece and dropped the old
one: that scan existed to test the workflow and will not be used, so it is not a corpus
fragment. Removed from the working tree: its 2026-07-08 Scaniverse GLB and PLY, its four
feature maps, and a stray texture copy. The binaries are LFS objects and remain in history.

Four hand-picked exemplars cropped from that atlas are **kept**, renamed to
`FRAG-S1-FS-002-july-piece_texture.png`. They are the only exemplar `embedded_metal` has and
one of two each for `cast_in_brick`, `tile_remnant` and `pipe_opening`; the features are
real and from the same building, which is all a calibration exemplar claims. Their
provenance is now a piece that appears nowhere in the results, so the reference-set table
must name it rather than cite FS-002.

### Added — `_check_texel_density` in `preflight.py`
Pixels of atlas per millimetre of real surface, which is the unit that decides whether a
feature is visible; the atlas resolution alone does not, because the island margin can
throw most of the sheet away. Fails below 0.50 px/mm, warns below 1.00.

### Added — `_check_identity` in `preflight.py`
Compares the export's oriented bounding box against the one already on record and warns
above 15% drift on any axis.

`FRAG_ID` is hand-edited in the Blender script before every bake and is the one input
nothing downstream can verify. It has now caused two silent corpus errors: FRAG007 written
into FS-003's folder, and a 1630 x 934 x 706 mm slab written into FS-002's, whose own
Scaniverse scan measures 858 x 737 x 501 mm. **Both exports were internally perfect** —
correct topology, clean UVs, valid sidecar, every existing check green. The checks all ask
whether the mesh is good; none asked whether it was the right mesh.

The oriented box is the cheapest thing that separates two fragments, and unlike the
`_check_duplicate` volume signature it survives a re-remesh of the same piece. Calibrated on
FS-006 exported twice, whose box agreed to within 0.1%.

---

## [v1.6] 2026-08-19 — Blender: the copy is remeshed, the import is kept

### Changed
- `bake_texture_v2.py` now remeshes the **duplicate** and leaves the imported object intact
  as `{FRAG_ID}_original`, visible at the end. Previously it renamed the import to
  `_remesh` and applied the destructive modifier to it, keeping the duplicate as the hidden
  `_source`. Nothing was ever lost, since `_source` held the original geometry, but the
  object you imported appeared to have been replaced and the copy you needed for a
  re-export was hidden under a name that did not suggest it.
- The remeshed copy is hidden at the end instead of the original, so the two do not overlap
  in the viewport, and both are named in the closing message.

---

## [v1.5] 2026-08-19 — Taxonomy revised against the material; condition axis retired

### Changed (Muchen)
- Retired as surface labels: `original_finish` (ambiguous), `weathered` and `staining`
  (apply to nearly every fragment, so they carry no discriminating information). Ids kept,
  so FS-004 and FS-006 still resolve their stored `weathered` regions.
- Added: `embedded_metal`, `tile_remnant`, `pipe_opening`, `cast_in_brick`, each with a
  decision rule and a precedence position. Nine active labels, three retired.
- **The condition axis is now empty.** `weathered` and `staining` survive as *anomaly*
  labels, which are localized and carry a bounding box, so condition is reported as a patch
  on a face rather than as the identity of the face. A face that cannot be read on origin
  now goes unclassified instead of defaulting to weathered.

### Added — the condition axis, rebuilt as anomalies
- `anomalies` section in `env/taxonomy.json`. `ANOMALY_LABELS` and `ANOMALY_HINTS` were
  hardcoded in `region_classification.py`, which made the condition axis the least
  manageable part of the schema at exactly the point it became the only home for condition.
  Now config-driven like the surface labels, retire flag included. Anomalies carry no
  feature_id, so retiring or removing one renumbers nothing.
- Three new anomalies: `spalling` (a dish of concrete lost from an otherwise intact face,
  usually over corroding steel: section loss, not appearance), `crack` (a line rather than a
  patch, and the strongest predictor of where a piece breaks next), `biological_growth`
  (identifies the face that was exposed to weather). Existing hints for `staining` and
  `weathered` rewritten to be discriminating rather than descriptive.
- `taxonomy_tool.py list` and `check` now cover both axes.
- `finishing_requirement` gained two rules: `spalling → assess_section_loss` and
  `biological_growth → clean_before_use`. Spalling is the one with a consequence beyond
  appearance, since it bears on whether a face can carry load.

### Not added, and why
- `carbonation` was a subtype of the retired `weathered` and is **not visually detectable**:
  it needs a phenolphthalein spray on a fresh break. It could never have been found by this
  method. Worth stating in the paper as a descriptor the instrument cannot supply.
- `erosion` and `freeze_thaw_damage`: the first repeats the vagueness that retired its
  parent, the second is a cause rather than an appearance and presents as spalling.
- `efflorescence`, `rust_staining`, `soot_or_burning`, `paint_residue` are defensible and
  were left out to keep the first pass small. `efflorescence` appeared under **both**
  `weathered` and `staining` in the old subtype lists, which is the overlap problem in
  miniature.

### Changed (follow-on)
- `env/design_factors.json`: three rules listed retired labels as alternatives. None were
  dead, all still fired on `formwork_imprint`, but `exposed_face` had lost three of its four
  labels and was collapsing into a duplicate of `design_assignment: show_face`. Its labels
  are now formwork_imprint, tile_remnant, cast_in_brick. `finishing_requirement` untouched:
  it keys on `if_anomaly: staining`, a different axis.

---

## [v1.4] 2026-08-18 — Feature taxonomy reviewed; calibration by exemplar

### Found
- The seven surface labels answer three independent questions and are therefore not
  mutually exclusive: **origin** (formwork_imprint, fracture_surface, original_finish),
  **exposure** (exposed_aggregate, rebar_visible), **condition** (weathered, staining).
  Forced to return one, the model picks an axis per fragment and holds it across the batch.
  FS-004 came back 9 of 16 weathered with no fracture at all; FS-005 came back 8 of 13
  fracture with no weathering. Same demolition, same material, not one shared label.
- The prompt sent bare label IDs with no definitions, although `LABEL_DESCRIPTIONS` had
  existed and gone unused since v0.2.

### Added
- `_decision_order` and a per-label `decision_rule` in `env/taxonomy.json`, forcing one
  reading: rebar_visible > original_finish > formwork_imprint > fracture_surface >
  exposed_aggregate > weathered > staining. Origin ranks above condition because origin is
  permanent and design-relevant while weathering is superficial and can be cleaned.
- Reference-set calibration (Muchen's proposal). `01_input/reference_surfaces/<label>/*.png`
  holds labelled exemplar crops from this same building, sent at `detail: low` ahead of the
  regions on every call. All fragments share one mix, one formwork system and one demolition
  method, so the standard can be shown rather than described. Empty by default, so the
  pipeline is unchanged until populated.
- `03_src/build_reference_set.py` — exports every region crop into
  `_candidates/<current_label>/` for picking.
- `04_schema/TAXONOMY_REVIEW.md` — the evidence, the two mechanisms, the provenance
  argument, and the open question of splitting the schema into three facets.
- `03_src/taxonomy_tool.py` — `list`, `check`, `folders`, `add`, `remove`, `retire`.
  `remove` refuses unless the label is unreferenced: absent from every record, its
  feature_id absent from every viewer JSON, and no higher feature_id in use, since deleting
  an entry renumbers the rest. `retire` handles the case `remove` refuses: the id and its
  index stay, so stored data still resolves, while the label leaves the prompt and the
  interface. `RETIRED` and `ACTIVE` in `taxonomy.py`; `report.py` builds the legend, chips
  and filters from `ACTIVE` but keeps the colour and index arrays over the full `TAXONOMY`
  so stored feature_ids still render. Adding a label requires paired entries
  in `labels` and `_decision_order`; a label present in the first but not the second never
  reached the prompt at all, so the model could not choose it and nothing reported it.
  `add` writes both or neither, picks an unused colour, and creates the reference folder.
  `_decision_order()` in `taxonomy.py` now appends anything missing, with a warning, since
  losing a category silently is worse than misplacing its precedence.

### Changed
- Prompt now instructs the model to judge each image independently and not to make the
  regions agree.
- `run_pipeline.py --no-references` classifies uncalibrated, as the control for a calibrated
  run. A label that holds only when its own fragment supplied the exemplar is leakage rather
  than recognition. `reference_signature()` returns "none" when disabled, so the two runs
  cannot share a cache entry.
- `descriptors/feature_texture.py` now derives its label colours from the taxonomy. It
  carried a hardcoded table that had to be kept in step by hand, so a label added to
  `taxonomy.json` would have had no colour and would have vanished from the feature map.
- Reference folders whose name is not a taxonomy label now print a warning naming the fix,
  instead of being skipped in silence.
- `--check` looks for any sizeable area carrying no surface detail rather than for a list of
  known filler colours, so it also catches the white band an image editor leaves when it
  flattens transparency on save.
- API cache key now includes `DECISION_ORDER`, `LABEL_RULES` and the reference-set
  signature, so changing the standard correctly invalidates cached answers.

---

## [v1.3] 2026-08-18 — Texture quality gates; volume from the mesh; pre-flight checks

### Added
- `03_src/preflight.py` — validates a Blender export before the pipeline spends time or API
  credit. Called automatically at the start of every `run_single()`, stops on a failure,
  overridable with `--skip-preflight`. Ten checks, each added after a bad export got through
  silently: remesh resolution, UVs, volume source, texture, bake margin, featureless patch,
  UNSCANNED marked, sidecar normal orientation, UNSCANNED face located, duplicate mesh.
- Mesh signature cache at `05_output/descriptors/mesh_signatures.json`. Face count plus
  volume identifies a mesh across exports, since two Smart UV runs differ byte for byte but
  agree on both. Caught FS-005/FS-006 and FS-003/FS-007.

### Found
- **FS-003's export was overwritten by FRAG007** on 2026-08-18 at 10:58, `FRAG_ID` left
  unchanged in `bake_texture_v2.py`. **Recovered the same day**: the copies the pipeline had
  written to `05_output/descriptors/` were verified sha256-identical to the LFS objects
  committed in `2657a3e7` and copied back. The sidecar was never touched.
- **FS-003's UNSCANNED vertex group was always empty.** The sidecar records
  `face_count: 0` with `has_unscanned_face: true`, so the stored normal is the average of
  nothing and converts to a horizontal direction. The group was created but never assigned.
  Both `COMMANDS.md` and `HANDOVER.md` claimed FS-003 had a working sidecar; it never did.
  Re-mark it when the fragment is re-exported.

### Fixed in preflight after first use
- Sidecar normal check accepted only -Y. `unscanned_face_idx()` matches on absolute angle
  and then keeps the lowest faces, so either sign works; only a non-vertical normal is a
  fault. Now fails on non-vertical, warns on +Y.
- Added an explicit `face_count: 0` check, which is what FS-003 actually suffers from and
  what the normal check was reporting obliquely.
- `directional_smear()` in `region_classification.py`: structure-tensor coherence per pixel.
  Where the scan saw a face only at a grazing angle, the bake drags one texel along the
  surface into parallel striping that looks like corrugated metal or a row of bars. Concrete
  texture is directionless at this scale, a smear is not. Masked out before the crop is sent.
- `featureless_fill()`: local luminance sd below `FLAT_SD_MAX`. Where the scan never saw a
  face at all, the bake fills it with an even wash. This is the case neither other check
  reaches: the smear gate measures 0.04 coherence on it against a 0.65 threshold, and
  geometry sees a filled hole as the flattest plane on the fragment. Marking the `UNSCANNED`
  vertex group remains the proper fix; this is the net for when it was missed.
- `smear_frac` and `flat_frac` per region, in the record and in the report's Masked column.
- Scale-relative face-count guard in `bake_texture_v2.py`: raises below 20% of
  `3 × (longest_dim / voxel_size)²`. The previous fixed floor of 100 faces let FS-003
  through at 3,016.

### Changed
- `bounding_descriptors()` now merges vertices before judging closure and prefers the mesh
  volume over the convex hull. A voxel remesh is closed in Blender, but GLB export splits
  vertices along UV seams, so trimesh reported `is_watertight == False` on a solid mesh and
  the pipeline fell to the hull. The hull wraps every concave break face: 17% high on FS-006,
  26% on FS-007, roughly 90% on FS-003. New `volume_source: mesh_nearly_closed` covers the
  case. FS-007 mass 291 kg → 231 kg, matching Blender's own 0.0963 m³ reading.
- Region skip reason `smeared_texture` → `unreliable_texture`, now covering both defects.

### Verified
- Bake margin took effect on FS-007: black within 1 px of texture fell from 4.4% (FS-006,
  pre-margin) to 1.1%, and within 32 px from 79% to 28%. Black remains in the atlas by
  design; it is masked out before the vision model sees it.
- FS-007 exported without the `UNSCANNED` group. The unscanned underside is 8.8% of the
  textured atlas at local detail sd 0.08 against 13.03 for the atlas as a whole.

---

## [v1.2] 2026-08-17 — Drill zone and finishing factors; crop fill measured and corrected

### Added
- `drill_zone` design factor (fragment level): `between_bars` | `edge_mid_depth` | `verify_gpr`.
  Reinforcement is a grid at roughly constant cover and spacing, so a section is mostly
  steel-free. Exposed reinforcement is treated as information (it reveals spacing, direction
  and cover, which can be projected across the piece) instead of as a reason not to drill.
  Reports the estimated steel-free core and, for `edge_mid_depth`, which regions the hole
  can enter through.
- `finishing_requirement` design factor (face level): `cut_back_and_seal` |
  `assess_contamination` | `ease_sharp_arrises` | `clean_only` | `none`.
- `obb_axes_xyz` in the bounding descriptor: each box dimension's own axis, so a broad face
  can be told from a broken edge. Requires reprocessing to appear on existing records.
- `--drill-zone` predicate in `query.py`.
- `BAKE_MARGIN = 32` with `margin_type = 'EXTEND'` in `bake_texture_v2.py`.

### Changed
- `connection_strategy` no longer returns `no_drill` when reinforcement is visible. That rule
  was structurally wrong: it treated a mat as solid steel. The factor now answers only whether
  a fixing can be SEATED on a face; whether it can be drilled is `drill_zone`.
- `MASK_FILL` grey → magenta `(255, 0, 255)`, with the prompt naming it. Black fill read as a
  void and produced spurious `opening` labels; mid grey is close enough to concrete to read as
  smooth cast surface. Changing the prompt invalidates the API cache.
- Planar Regions table gained a Finishing column; Design Factors panel gained Drill zone.

### Measured (corrections to earlier claims in this repo)
- Crop composition, FS-006 regions 0–2: own region 70–80%, other regions' islands 0.2–1.5%,
  empty atlas 13–18%, unassigned slivers 7–13%. An earlier note claiming ~31% contamination
  from other regions' islands does not reproduce.
- Morphological closing of the region mask changes crop fill by 0.2%, not the ~6% claimed.
- Rotating the crop to the island's principal axis does not help: islands already sit at
  88–92°.
- Residual black inside finished crops: 0.00–0.28%. Everything outside the mask is overwritten
  by `MASK_FILL` before the model sees it, so the bake margin fixes only the rim where the
  dilated vertex-scatter mask overshoots the island.

---

## [v1.1] 2026-08-14 — Design factors executed; query layer

### Added
- `env/design_factors.json` — encoded links from descriptor values to making implications,
  editable without touching code. All output carries `data_status: "proposed"`.
- `03_src/descriptors/design_factors.py` — executes them into the record's `procedural` block.
- `03_src/query.py` — structured predicates over the records, including `--geometry-only`
  for the evaluation baseline. Inexpressible queries exit 2 instead of guessing.
- `03_src/refresh_factors.py` — rebuild records, reports and inventory with no geometry
  recomputation and no API calls.
- Candidate uses restricted to landscape installation and urban furniture; shown per
  fragment, hidden as an inventory filter (`SHOW_USES_IN_INVENTORY = False`).

---

## [v1.0] 2026-08-10 — Six real fragments end-to-end; UNSCANNED handling; spatial feature map

### Added
- `02_blender/bake_texture_v2.py`, `export_fragment_v2.py` — write `_scan_coverage.json` sidecar from the `UNSCANNED` vertex group before remesh
- `03_src/scan_coverage.py` — flags RANSAC planes matching the unscanned face normal as `scan_reliable: false`; integrated into `run_pipeline.py` (auto-runs when a sidecar exists), kept as standalone re-annotator
- UNSCANNED texture-mask exclusion: masked grid cells removed before AI classification and spatial vote
- 3D spatial majority-vote feature map (8×8 XZ grid, vertex colours) replacing UV→cell mapping; per-point `feature_id` in viewer JSON (5-element points)
- Archetype system: `FRAG-S1-{ARCHETYPE}-{###}` IDs parsed and shown in reports
- `--batch`, `--force`, `--serve`, `--ransac-threshold` CLI flags; inventory `index.html` with 3D viewers
- `04_schema/feature_hierarchy.csv`
- Fragments FRAG-S1-FS-001 … 006 processed (001 geometry-only); UNSCANNED verified on FS-003/FS-006

### Changed
- Rhino / Grasshopper stage superseded; `02_gh/` unused
- Vision provider: GPT-4o with multi-run majority voting

### Removed
- `debug_unscanned.py` (temporary diagnostic)

---

## [v0.2] 2026-07-08 — Grill complete, pipeline scaffold updated

### Decided
- Mesh library: trimesh (bounding) + open3d (planarity, curvature)
- Architecture A: standalone Python scripts, no analysis inside Rhino runtime
- Blender → Rhino transfer via .glb (textures embedded)
- Texture source: photogrammetry PNG used directly, no re-rendering
- View strategy: UV crops per planar region (Phase 3), no Blender renders for analysis
- Vision API: Anthropic primary, switchable via `VISION_PROVIDER` in `.env`
- AI-classified features: rebar, surface_origin_type, defect_presence, weathering_severity
- Human annotation: direct JSON edit now, `annotate.gh` when > 3 fragments
- Pipeline trigger: manual CLI with documented trigger points (see WORKFLOW.md)

### Added
- `WORKFLOW.md` — step-by-step workflow with trigger points and git conventions
- `.gitignore`, `.gitattributes` (git-lfs for binary assets)
- `CHANGELOG.md`
- `__init__.py` in all `03_src` subpackages
- `open3d` added to `env/requirements.txt`
- `env/.env.example` with `VISION_PROVIDER` and `VISION_MODEL`
- `01_input/meshes/processed/FRAG-S1-001/` folder ready for Blender export
- `03_src/run_pipeline.py` — main entry point
- Implemented `geometry.py`: bounding_descriptors, planar_regions, curvature_stats

---

## [v0.1] 2026-06-12 — Initial scaffold

### Added
- Folder structure (01_input → 06_validation)
- `PLAN_Study2.md`, `README.md`
- `fragment_schema.json`, `descriptor_dictionary.md`
- `geometry.py`, `vision_client.py` stubs
- `fragments_manifest.csv`
- Photogrammetry folder structure (`raw_exports/`, `projects/`)
- First raw scan: `FRAG-S1-001/concrete_scan.obj`
