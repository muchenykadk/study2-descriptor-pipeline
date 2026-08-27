# Classifier behaviour and validation

Status 2026-08-24. Written for §5.1 and §6.2. Scope consequences in
`paper_draft/SCOPE_REVISION_2026-08-20.md`.

Regenerate:

```powershell
python 03_src/agreement.py --md        # inter-run agreement, from cached votes
python 03_src/score_test_set.py        # multi-label, against held-out tiles
python 03_src/binary_probe.py          # one yes/no question per feature
```

---

## 0. Method: calibrating and verifying on twelve fragments

The published datasets contain nothing of three-dimensionally scanned demolition fragments
with annotated surfaces (§7 of the paper draft), so every reference value here was produced
inside the study. That shaped the method. With ground truth this scarce, the useful question
is which claims the evidence can support, and each device below answers that for one layer.

**Recompute the deterministic half independently.** Oriented bounding box, volume and mass
were recomputed straight from the GLB on three fragments spanning the size range and compared
against the stored records (§7). This needs no labels, which is why the geometric layer is the
one that carries the retrospective evaluation.

**Seed every random step.** The plane search and the surface sampling are seeded, so two runs
differ only where the input differs. Seeding is what turns run-to-run variation into a
measurement. See `RANSAC_SEED` in `descriptors/geometry.py`.

**Calibrate by example.** Labelled crops from the same building go ahead of the regions, so
samples of the material define each category. Twelve fragments are too few for training and
enough for definition by example.

**Let the capture bound the vocabulary.** A category is admitted only where its defining
evidence exceeds the sampling window at the achieved texel density. This settles, before any
classification runs, a question that is otherwise unanswerable: whether the classifier is
wrong or the feature is invisible. Sixteen candidates reduced to eleven; retirements and
reasons in `env/taxonomy.json`.

**Ask whether the category is the right output type at all.** `crack` is the case that
exposed this. An unseparated crack has almost no aperture, the two faces stay in contact, so
the reconstructed surface runs straight across it. Geometry cannot reach it at any scan
resolution, and the triangle edge across all eleven fragments is 1.74 to 1.89 mm, which is the
2 mm remesh voxel rather than the scan; the Scaniverse source carries about 130k triangles,
roughly 4.5 mm per triangle on FS-012, so the remesh upsampled about sixfold and added no
detail. Cracks live in texture, at 1.3 to 2.5 px for a 1 mm opening. At that width the
instrument is a line filter and the output is a length, a width and an orientation. Asking a
vision-language model for a category was the wrong tool producing the wrong kind of answer,
and no prompt would have fixed it. Retiring the category was right; the missing half was
naming where the information should come from instead.

**Sample the test set at random, and keep it out of calibration.** Random positions on real
surface, never sent as references. Tiles curated for showing clear features would measure the
best case and report it as the average. This replaced an earlier circular attempt that scored
the model on its own exemplars (§1).

**Score against a null model.** With two features covering most of the fragment set, answering
them unconditionally produces a plausible recall figure. The null baseline is what makes the
headline number readable, and it is what showed the classifier adds nothing (§2).

**Change one thing and ask again.** The binary probe puts the identical images to the model
one question at a time. Holding the images fixed and changing only the framing isolates the
effect of the question, which an accuracy number alone would hide (§4).

**Audit the output for structure as well as correctness.** The localisation finding came from
noticing that all 68 coordinates were multiples of ten, a property of the output distribution
that needs no ground truth at all (§5). Cheap, and available on any dataset.

**Report coverage alongside every rate.** 33% of sampled tiles unreadable, 44% of region area
declined before classification. A classification result on this material is readable only
together with the share of surface that could be classified.

The limits of this method: it gives no accuracy figure that generalises beyond these twelve
fragments, and no conclusion about a category with one or two labelled instances. §9 states
them in full.

## 1. The validation set

26 tiles, sampled **blind** from the fragment atlases at random positions on real surface,
~250 mm of surface each, and labelled by hand. They are never sent as reference images, so
the classifier is scored on surfaces it has not been shown.

This replaced an earlier attempt that scored the classifier on the reference exemplars
themselves. That was circular: the model was being asked about pictures it had just been
given as calibration, and no result from it could separate recognition from recall.

Sampling was deliberately blind rather than curated. Choosing tiles that show clear features
would measure the best case and report it as the average.

**39 tiles were sampled; 13 were unreadable** (smear, blur, black atlas) and are excluded.
That 33% is itself a measurement of what the capture delivers, and it sits alongside the 44%
of region area the UV gates drop before classification.

Ground truth, after the taxonomy revision:

| feature | tiles | share |
|---|---:|---:|
| `broken_face` | 21 | 81% |
| `exposed_aggregate` | 18 | 69% |
| `brick_inclusion` | 5 | 19% |
| `formwork_face` | 2 | 8% |
| `rebar_visible` | 1 | 4% |
| `pipe_opening` | 1 | 4% |

**Limitation, stated up front:** the annotator and the person who chose the exemplars are the
same. And only `broken_face`, `exposed_aggregate` and `brick_inclusion` have enough support
to carry a number. The zeros at n=1 and n=2 are not evidence of failure, only absence of
evidence.

## 2. The null model

The comparison that decides whether the classifier is doing anything: a model that looks at
nothing and always answers `broken_face, exposed_aggregate`.

| | TP | FP | FN | recall | precision | exact match |
|---|---:|---:|---:|---:|---:|---:|
| null model | 39 | 13 | 10 | 80% | **75%** | 11/26 |
| multi-label classifier | 39 | 20 | 10 | 80% | **66%** | 10/26 |
| one binary question per feature | 33 | 11 | 15 | 69% | **75%** | — |

**The multi-label classifier does not exceed the null model.** Identical recall, worse
precision, one fewer exact match. This is the headline result and it should be reported as
such.

## 3. Per feature, all three conditions

```
feature              n       null r/p      multi r/p     binary r/p
broken_face         21      100%/ 81%       95%/ 80%       95%/ 80%
exposed_aggregate   18      100%/ 69%      100%/ 72%       61%/ 92%
brick_inclusion      5        0%/  -         0%/  -        40%/ 67%
formwork_face        2        0%/  -         0%/  0%        0%/  0%
rebar_visible        1        0%/  -         0%/  -         0%/  -
pipe_opening         1        0%/  -         0%/  -         0%/  0%
```

Two frequent features are recovered at rates a constant guess already achieves. Every
distinctive feature fails under multi-label.

## 4. Question framing changes the answer

The multi-label prompt offers eleven features and asks which apply, so naming the two
commonest is never badly wrong. A binary question removes that retreat: *"Does this image
show brick or masonry cast into the concrete?"* has no safe answer.

Two effects, on identical images:

**`brick_inclusion` moved from 0 of 5 to 2 of 5**, with one false positive. The only evidence
in this study that the model can identify a distinctive inclusion at all.

**`exposed_aggregate` began discriminating rather than defaulting.** Recall fell 100%→61%,
precision rose 72%→92%. Under multi-label it said aggregate on everything; asked directly it
sometimes says no, and when it says yes it is usually right.

Nothing else moved. On the micro-average binary is worse (69% vs 80% recall), but that
average is dominated by the two features making up 39 of 49 true labels, so it mostly
measures willingness to answer yes.

**Reportable claim:** open-vocabulary classification of this material is sensitive to
question framing, and multi-label prompting suppresses exactly the distinctive features that
carry design information. Not that binary framing solves it — one feature moved, on n=5.

## 5. Localisation: stock coordinates for a question with no honest answer

Every bounding box the model produced was a stock value.

- **68 of 68 coordinates were exact multiples of 10.**
- 17 detections drew on **7 distinct boxes**; `[40,40,60,60]` — dead centre — appeared six
  times, across different fragments *and* different features.
- Three of the boxes checked pointed mostly at masked-out non-material: `crack` at 82% and
  73% mask fill, `pipe_opening` at 85%.
- Visual inspection of all five `crack` boxes: none contained a crack. They contained mask
  fill, directional smear and blurred wash.

**The fault is shared, and saying so matters for the fix.** The schema demanded a coordinate
and offered no way to decline. A model given a mandatory field will fill it, and stock
coordinates are what "I cannot tell" looks like when the schema forbids saying so. Reporting
this as invention alone would point the remedy at the wrong place.

Localisation is therefore **disabled with its validation built**, not deleted
(`ALLOW_LOCALISATION = False` in `region_classification.py`):

1. the prompt states that null is a valid and preferred answer, so declining is available;
2. `validate_box()` rejects a box less than 50% on real material, which would have caught the
   three worst above;
3. `_is_stock_box()` rejects round, centred coordinates, catching three of the four patterns
   found here;
4. a box needs cross-run agreement at IoU 0.30.

Enable it when capture quality supports it. **Untested against live output**, since it is off
and the gates have only been exercised on the recorded boxes.

**The pipeline recorded faithfully throughout** — the cached responses contain exactly what
the model returned.

## 6. Repeatability, and why it is not accuracy

Each region batch is classified three times and the runs are cached separately, so
repeatability is measurable at no extra cost.

**98% of feature observations were unanimous across three runs; 99% survived the 2-of-3
threshold.**

That figure must not appear without its companion: **82% of regions returned the identical
pair**, and six distinct features occurred across 39 regions in four combinations. Three runs
of a near-constant output can hardly disagree. It measures stability under repetition, not
correctness.

## 7. What is verified and sound

Recomputed independently from the GLB on FS-005, FS-010 and FS-012: oriented bounding box,
volume and mass **match the stored records exactly**. `handling_class` traces to `max_dim`
and mass; `mass_kg_est` is volume × the density constant in every case checked. That constant moved from 2400 to 2500 kg/m³ on 2026-08-25, per EN 1991-1-1 Annex A Table A.1 for reinforced concrete, so the recomputation must be repeated after the next batch.

Geometry, planarity, texel density and the texture-quality gates are measured from the mesh
and the pixels, and are reproducible.

**One contaminated output, and it currently ships.** `drill_zone` reads `rebar_visible` from
the face labels and reports "no bars visible, but the section is deep enough for a steel-free
core". The **region** pass has never reported rebar on any fragment, so that guidance rests on
an untested negative. Worse, since 2026-08-25 the **whole-atlas** pass reports `rebar_visible`
on 4 of 11 fragments, so a single record can assert reinforcement at fragment level and deny
it at face level. `finishing_requirement` shares the dependency.

Both are described as withheld in the paper and both are present, computed and populated, in
every record on disk. Anyone opening `FRAG-S1-FS-010_geometry.json` gets the drilling text
above. **The withholding exists in the prose and not yet in the code**, and that has to be
fixed before any record is released.

## 8. Corpus resolution

| | atlas | px/mm | |
|---|---:|---:|---|
| FS-001 | 1080 | 0.20 | excluded from texture claims |
| FS-002 … FS-012 (11) | 4096 | 1.27 – 2.51 | usable |

FS-007 was re-baked on 2026-08-24 and moved from 0.59 to **2.30 px/mm**, the highest in the
corpus. Its earlier figure was the old bake settings, not a limit of the scan.

The 2× spread among the eleven is fragment size, not a defect: one 4096 sheet over 1.2 m² gives
2.51 px/mm, over 4.8 m² gives 1.27. Detectability is therefore **not uniform across the
corpus**, and any per-feature rate is conditional on which fragment a region came from.

FS-001 is excluded from texture-based claims, and the reason is provenance rather than
settings. It was digitised in an earlier campaign, and the raw export retained for it is a
**Rhino OBJ with 20,857 faces over 62,696 vertices and no accompanying material or texture**.
Every other fragment comes from a Scaniverse GLB carrying 130,000+ dense triangles and an
embedded 8192 texture.

That mesh is too sparse to voxel-remesh: the operation returns roughly the input's own face
count (23,646 at 2 mm, 16,358 at 2.8 mm) because there is no continuous surface to wrap. And
with no source texture there is nothing to bake from, so the existing 1080 atlas cannot be
improved by any parameter change.

Its size, 8.42 m², would also have made comparable texel density difficult, but that is
secondary: the fragment cannot be reprocessed at all without re-scanning. The existing
5.65M-face geometry is sound and verified, and it stays in the geometric corpus.

## 8b. One label per face is a display choice, and it hid the corpus result

Each classified region carries a set of features. The viewer, the feature map and every
consumer that can only hold one value per face read `label`, which is the highest-precedence
feature present. That is rendering, not classification.

Until 2026-08-25 the precedence list ran rarest-last, so `broken_face` outranked every
inclusion and won **61 of 72 classified regions**. The 2026-08-24 viewer was therefore a
single colour on every fragment, and FS-010 region 4 rendered as `broken_face` while its
record held `brick_inclusion`. The list is now ordered rarest-first.

Two consequences for the paper. Any figure taken from a viewer built before 2026-08-25
understates what was found and should be regenerated. And no single-colour map can show
`broken_face` and `exposed_aggregate` at once, since they co-occur on nearly every region, so
per-feature views are the ones to publish.

Corpus detections of `brick_inclusion` after the taxonomy rebuild: FS-002 (3 regions),
FS-004 (2), FS-010 (1). Before it, one across the whole corpus. This is a count of model
output, not an accuracy measurement; §1's held-out set is still the only scored evidence, and
there `brick_inclusion` was 0 of 5 under multi-label.

## 9. What to claim, and what not to

**Defensible:**

- The geometric descriptor pipeline is verified and reproducible.
- The multi-label classifier does not exceed a null model on held-out data (80%/66% against
  80%/75%).
- Question framing materially changes what is recovered: `brick_inclusion` 0/5 → 2/5.
- All localisation output was fabricated, with the evidence in §5.
- Capture resolution bounds the achievable descriptor set, with numbers.

**Not defensible:**

- Any accuracy claim for the surface-descriptor layer.
- Any conclusion about `rebar_visible`, `pipe_opening` or `formwork_face` — n = 1, 1, 2.
- The 98% repeatability figure without §6's second paragraph.
- `drill_zone` and `finishing_requirement` as working outputs.
- Anything texture-based computed on FS-001.
