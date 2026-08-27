# Plan — Texture quality and vision-model inference

> **Superseded in part, 2026-08-24.** The texture-quality work below is still current and
> its measurements hold. What changed is the conclusion it was serving: the classifier was
> subsequently validated on held-out data and does not exceed a null model, so improving the
> texture does not by itself make the surface labels usable. See
> `04_schema/CLASSIFIER_BEHAVIOUR.md`. The taxonomy referenced in these sections was also
> rebuilt: `fracture_surface` is now `broken_face`, `spalling`, `crack` and `weathered` are
> retired, and bounding boxes were removed. `CHANGELOG.md` v2.0 has the mapping.

Status 2026-08-17. Owner: Muchen. Context: false `opening` and metal-like labels on FS-006.

---

## 1. What the problem turned out to be

The working assumption was that gaps in the texture atlas were reaching the vision model
and being read as voids. Measured on FS-006, that is not what is happening.

Everything outside a region's mask is overwritten with the fill colour before the crop is
sent. Residual black inside a finished crop is **0.00–0.28%**. The atlas gaps never arrive.

What does arrive is **smeared texture**. Where the scan saw a surface only at a grazing
angle, the bake drags one texel along the surface and produces strong parallel striping.
On FS-006 region #0 this covers roughly a third of the face. It looks like corrugated
metal or a row of bars, which is the most plausible source of a false `rebar_visible`
or `opening`.

Measurements that ruled out the alternatives:

| hypothesis | result |
|---|---|
| other regions' islands contaminate the crop | 0.2–1.5%, not the ~31% previously claimed |
| pinholes from mask rasterisation | closing changes crop fill by 0.2% |
| bbox waste from diagonal islands | islands already sit at 88–92°; rotation makes it worse |
| UV stretch (low texel density) causes the smear | region #0 is under-sampled overall, but a density threshold does not isolate the band |
| **directional smear from grazing-angle bake** | **confirmed; structure-tensor coherence isolates it** |

Corrected crop composition, FS-006 regions 0–2: own region 70–80%, other regions'
islands 0.2–1.5%, empty atlas 13–18%, unassigned slivers 7–13%. The last three are all
masked out.

## 2. What is implemented

**Fill colour.** `MASK_FILL` is magenta `(255, 0, 255)`, named in the prompt. Black read
as a void and produced the planter label; mid grey is close enough to concrete to read as
smooth cast surface. Magenta is neither. Roughly a quarter of every crop is fill, which is
too large a share for the colour to be arbitrary.

**Smear detection.** `directional_smear()` in `03_src/ai/region_classification.py`.
Structure-tensor coherence per pixel, near 1 where the local gradient has a single
orientation and near 0 where it has none. Concrete texture is directionless at this scale;
a smear is not.

```
SMEAR_COH_MIN  = 0.65   # coherence above which a patch is a smear
SMEAR_WIN      = 9      # px, structure-tensor averaging window
SMEAR_MIN_FRAC = 0.02   # ignore flagged blobs below this share of the face
SMEAR_SKIP     = 0.50   # skip the region entirely above this share
```

The mask is opened (5 px) to drop speckle, closed (25 px), hole-filled, then reduced to
blobs above `SMEAR_MIN_FRAC`. **The band must be taken whole.** A partly masked band is
worse than none: the ragged remainder reads as perforation, which is the failure mode
being avoided. This was observed directly at a higher threshold and is why the
consolidation steps are there.

**Featureless fill.** `featureless_fill()`, local luminance sd below `FLAT_SD_MAX = 3.0` in
a 15 px window. Where the scan never saw a face at all, the bake has nothing to sample and
fills it with an even wash of colour. The opposite signature to a smear: no direction
because there is no structure of any kind.

This is the case neither other check reaches, which is why it needed its own gate. On
FS-007 the unscanned underside measures 0.04 directional coherence against the smear gate's
0.65 threshold, and local detail sd 0.08 against 13.03 for the atlas as a whole. Geometry is
no help either: a manually filled hole is the flattest, cleanest plane on the fragment and
RANSAC ranks it as the best bolting surface the piece has.

**Marking `UNSCANNED` in Blender remains the proper fix**, because it declares the geometry
invented as well as the texture. This gate is the net for when that marking was missed, as
it was on FS-001, FS-002, FS-004, FS-005 and FS-007.

`smear_frac` and `flat_frac` are recorded per region and shown in the report's Masked
column, so a face that was only partly assessed says so.

Measured on FS-006: region #0 29%, #2 2%, #4 21%, #1 0%. Visual check confirms the
streaked band is removed and the remaining surface is clean.

**Bake margin.** `BAKE_MARGIN = 32` with `margin_type = 'EXTEND'` in
`02_blender/bake_texture_v2.py`. Blender's default bleeds only across shared UV edges,
leaving ~30% of the atlas pure black. This is a rim fix only, since the black is masked
out anyway, but it is free and correct.

Confirmed working on FS-007: black within 1 px of texture fell from 4.4% (FS-006,
pre-margin) to 1.1%, and within 32 px from 79% to 28%. **Black remains in the atlas and is
expected to.** `EXTEND` bleeds a fixed 32 px and cannot fill the whole sheet; it does not
need to, because everything outside a region's mask is overwritten before the model sees it.

**Volume from the mesh.** `bounding_descriptors()` merges vertices before judging closure
and prefers the mesh volume, with `volume_source: mesh_nearly_closed` for the common case.
A voxel remesh is closed in Blender, but GLB export splits vertices along UV seams, so
trimesh reported an open mesh and the pipeline fell back to the convex hull, which wraps
every concave break face. The hull ran 17% high on FS-006, 26% on FS-007 and roughly 90% on
FS-003, and that error propagated straight into `mass_kg_est` and the handling class.
FS-007 now reports 231 kg rather than 291 kg, matching Blender's own 0.0963 m³ reading.

**Remesh guard.** `bake_texture_v2.py` raises below 20% of the expected face count,
`3 × (longest_dim / voxel_size)²`. The previous fixed floor of 100 faces let FS-003 through
at 3,016. Almost always a unit mismatch: Voxel Size is in scene units, so `0.002` means 2 mm
only if the object measures ~1.6 units, not ~1600.

## 2b. Protruding reinforcement read as cracking (Muchen, 2026-08-19)

A third failure mode, distinct from the two above and **not fixed**, recorded because it
bears directly on the two labels that matter most for safety.

Photogrammetry cannot reconstruct an element thinner than roughly its point spacing. A
reinforcing bar protruding from a fragment is therefore missing from the mesh, while
remaining fully visible in the source photographs. The bake projects it onto whatever
geometry lies behind it, and it arrives in the atlas as **a dark line on a flat face**,
which is exactly what a crack looks like.

**One feature, two errors.** `crack` is over-reported and `rebar_visible` under-reported,
from the same cause. That is worth stating plainly, because the two labels have opposite
design consequences: a crack says the piece may fail, exposed steel says the piece needs
cutting back and sealing and cannot be drilled freely.

**Geometry cannot arbitrate.** A real crack at this resolution is a surface with no
measurable depth, and a missing bar is also a flat surface. Both are geometrically absent,
so the mesh offers no way to tell them apart.

**Partial mitigation taken, in the hints only.** Colour separates them where relief cannot.
A crack is a shadow: desaturated, the same hue as the surrounding concrete, and it wanders.
A flattened bar carries ferrous colour, rust orange-brown or steel grey, runs straight, and
holds constant width. Both anomaly hints now say so. This is a prompt-level hint and not a
solution.

**Proper fixes, none attempted.** Scan the bar-bearing faces at closer range so the bars
resolve; photograph protruding bars separately and record them as a manual annotation; or
detect the colour signature directly in the atlas as the smear and featureless-fill gates
do. The last is the most tractable, since ferrous hue in an otherwise grey-scale material is
a strong and simple signal.

## 2c. Texel starvation, and the diamond field (2026-08-20)

The single-colour patches on FS-001 and FS-002 are not a smear, not a coarse remesh and not
a masking artefact. The atlas simply had too few pixels per millimetre of surface.

Two settings caused it, and neither is visible in the atlas resolution alone:

- `BAKE_RES = 1080` in `bake_texture_v2.py`, while `BLENDER_WORKFLOW.md` steps 32 and 41
  have always specified 4096.
- `smart_project(island_margin=0.02)`. **The island margin is a fraction of the atlas, not
  a pixel count.** 0.02 leaves 2% of the sheet width between every pair of islands.

Measured on FS-002, same mesh (3,304,908 faces, 4.695 m²), before and after:

| | before | after |
|---|---|---|
| atlas | 1080 | 4096 |
| share of sheet carrying UV | 20.4% | 59.1% |
| px per mm of real surface | 0.24 | 1.57 |
| px per face | 0.07 | 2.83 |

At 0.07 px per face, an island of a few faces averages to a single colour and the 32 px
`EXTEND` margin bleeds it outward into a flat diamond. **The label failures follow from
this**: two FS-002 regions covering 36% of the surface returned `label: null` because the
model was shown bled flat colour and correctly declined to name it.

**The ceiling is the scan.** The Scaniverse source for FS-002 is an 8192 atlas over 132,693
triangles and resolves 2.75 px/mm. 4096 recovers roughly 57% of that in linear terms;
raising `BAKE_RES` to 8192 would pass the source and buy nothing but file size.

For scale, FS-006, the fragment that has been treated as the best record in the corpus,
resolves **0.46 px/mm**. Every fragment processed before this date is texel-starved, and
the whole corpus needs re-baking, not only FS-001 and FS-002.

`preflight._check_texel_density` now measures this directly and fails below 0.50 px/mm.

### The gates had to move with it

Both texture gates run on the full-resolution crop and every window in them was a pixel
count tuned on FS-006 at 1080, i.e. at 0.46 px/mm. Those windows encode a question about
*surface*, not about pixels: 9 px was "is this 20 mm of concrete directional?", which spans
several aggregate particles. At 1.45 px/mm the same 9 px covers 6 mm, inside a single
particle, where concrete is directional.

Measured on the new FS-002 atlas: 75% flagged as smear at the old 9 px, 29% at the
equivalent 29 px. `SMEAR_SKIP` is 0.50, so at 75% every region would have been dropped as
`unreliable_texture` and the fragment would have come back completely unclassified. **The
better bake would have looked worse than the bad one**, and for a reason that has nothing
to do with the texture.

Windows are now declared in millimetres and sized per fragment from
`texel_density(mesh, atlas_size)`. At 0.46 px/mm they resolve to the original constants
exactly, so the fragments already processed are unaffected.

This is the general lesson for the paper's method section: every threshold in this pipeline
that is expressed in pixels is silently a function of the bake settings. The ones expressed
in millimetres of surface, or as a share of a region, are not.

### What the smear gate is actually contributing (2026-08-20, measured on FS-002 at 4096)

Muchen's question: the smeared area is the ground-contact face, which is already marked
`UNSCANNED`, so is the smear gate doing anything, and is it right when it does?

`segment_regions()` sets `valid[unscanned_idx] = False`, so UNSCANNED faces never form a
region and never reach the model. Everything below is therefore about the *remainder*.

| | share of textured atlas |
|---|---|
| UNSCANNED UV footprint | 22.7% |
| flagged as smear | 28.5% |
| ...of which inside UNSCANNED | 78.3% |
| ...of which on genuinely scanned faces | 21.7% (**6.2% of the atlas**) |
| smear gate's coverage of the UNSCANNED footprint | **98.2%** |
| featureless-fill gate's coverage of it | 0.0% |

Two things follow.

**The two mechanisms agree almost exactly.** The gate recovers 98.2% of the hand-marked
face without being told where it is. That is worth reporting: the manual annotation and the
automatic detection are independent and they converge.

**But that also means most of what the gate flags is redundant.** The honest claim is not
"the gate masks 28.5% of unusable texture", it is "the gate masks 6.2% of the atlas that
`UNSCANNED` does not cover". The earlier claim in §2 that the smear gate earns its place
rests on that 6.2%, not on the headline number.

**Note the signature changed.** On FS-007 the unscanned face baked as a *featureless wash*,
sd 0.08, which is what `featureless_fill()` was written for. Here it bakes as a *smear* and
the flat gate finds none of it, because the hole was closed by hand and the bake then
projected neighbouring grazing-angle texture across the patch instead of leaving it blank.
Both gates are needed; neither generalises alone.

**Accuracy, checked by eye and not validated.** Sampling 70 mm tiles from the gate's own
positives outside UNSCANNED: 4 of 4 are unambiguous parallel streaking with no aggregate
structure. Sampling its negatives: 3 of 4 are usable surface, 1 is arguably missed smear.
So precision looks high and recall imperfect, which is the bias to want: over-flagging
leaves a ragged remainder that reads as perforation, which is the failure mode §2 records.
Eight tiles is an impression, not a measurement, and should be described as such if it
appears in the paper at all.

## 2d. Fragment identity is unverifiable downstream (2026-08-20)

`FRAG_ID` is hand-edited in the Blender script before every bake. Nothing downstream can
check it, and it has now produced two silent corpus errors: FRAG007 written into FS-003's
folder, and a 1630 × 934 × 706 mm slab written into FS-002's, whose own Scaniverse scan
measures 858 × 737 × 501 mm.

**Both exports passed every check.** Correct topology, clean UVs, valid sidecar, sensible
volume. The checks ask whether the mesh is good; none asked whether it was the right mesh.
`_check_duplicate` cannot catch it either, since a genuinely different fragment has a
genuinely different signature.

`preflight._check_identity` compares the export's oriented bounding box against the one on
record and warns above 15% drift. The oriented box is the cheapest thing that separates two
fragments and, unlike the volume signature, it survives a re-remesh of the same piece.

Note the limit: the check is only as good as the record it compares against. If a wrong
export has already been processed, the record now describes the wrong piece and the check
will agree with it. Restore the record from git before trusting it.

**Resolution for this case (Muchen, 2026-08-20): the id was reassigned and the July piece
was dropped.** That scan existed to test the workflow and will not be used, so it is not a
corpus fragment and there is nothing to preserve. Deleted from the working tree:

- `05_output/descriptors/` — its four feature maps and a stray texture copy. Two of the
  four were for labels since retired (`weathered`, `staining`).
- `01_input/photogrammetry/raw_exports/FRAG-S1-FS-002/` — the 2026-07-08 Scaniverse GLB and
  PLY.

Both were tracked, and the GLB and PLY are LFS objects, so `git status` shows the deletions
but the blobs stay in history and in LFS storage until it is rewritten. Not worth rewriting
history over 24 MB; noted so the repo size is not a surprise later.

**Left in place: four exemplars cropped from that atlas** on 2026-08-19, renamed to
`FRAG-S1-FS-002-july-piece_texture.png`. They are the only exemplar `embedded_metal` has,
and one of two for `cast_in_brick`, `tile_remnant` and `pipe_opening`. Deleting them would
empty one label's calibration set and halve three others, which is a bigger loss than
keeping images from a fragment that is otherwise out of the corpus. The features they show
are real and from the same building, which is the only claim a calibration exemplar makes.

Two caveats to carry into the paper if they stay. Their provenance is a piece that appears
nowhere in the results, so the reference-set table has to name it rather than cite FS-002.
And they were cut from a 1080 atlas at roughly 0.24 px/mm against the 1.45 px/mm the model
now sees, so exemplars and working images are no longer drawn at the same texel density.
Re-cropping from re-baked atlases once the corpus is re-exported removes both problems.

## 2e. Why the labels land in the wrong place (2026-08-20)

Muchen: the pipe openings are unmistakable black holes, and the `pipe_opening` colour sits
somewhere with no openings in it. Three separate causes, all structural.

**Regions are geometric and the model is asked to name them anyway.** `segment_regions()`
never sees the texture. It assigns faces to the nearest RANSAC plane within 8 mm and 30°,
clusters the remainder by connectivity, and calls the rest residual. A region is a set of
faces sharing an orientation, not a contiguous visual patch, and Smart UV Project then
scatters those faces across the atlas. The crop sent to the model is the bounding box of
that scattered footprint with everything outside it painted magenta.

**`uv_coherence` does not measure the thing that matters.** It is the largest connected blob
over the total mask, so a thin winding ribbon scores 1.0 while filling almost none of its
own bounding box. FS-002, at 4096:

| reg | area | label returned | coherence | **fill** |
|---|---|---|---|---|
| 1 | 16.8% | tile_remnant | 1.00 | **80%** |
| 6 | 6.5% | tile_remnant | 1.00 | 36% |
| 4 | 9.7% | pipe_opening | 1.00 | 33% |
| 7 | 5.9% | pipe_opening | 0.99 | 29% |
| 8 | 5.0% | fracture_surface | 0.54 | 18% |
| 2 | 10.9% | tile_remnant | 0.97 | 10% |
| 9 | 5.0% | — | 1.00 | 9% |
| 5 | 6.6% | embedded_metal | 0.84 | 7% |

Region #1 is the only healthy crop, and **it is the one containing the actual openings**.
The model read it as `tile_remnant`, which for the region as a whole is defensible: the
combed adhesive pattern dominates its area. Regions #4 and #7 contain no openings; the model
was shown two-thirds magenta with disconnected fragments and dark cavities among them, and
`pipe_opening` was the nearest thing in the vocabulary.

`FILL_MIN = 0.20` now gates on this and `uv_fill` is recorded on every region. 0.35 was
tried first and left 2 of 10 regions covering 23% of the surface, which removes the bad
labels by removing the fragment. 0.20 keeps four regions covering 39%. **That is still a
large loss and it is a finding, not a tuning choice**: it says the UV layout, not the
classifier, is what limits how much of a fragment can be read.

The proper fix is to crop each region's largest connected blob rather than the bounding box
of its whole scattered footprint. Fill would rise without discarding regions. Not attempted.

**An opening could not be reported where it is.** On 2026-08-19 `pipe_opening` was added as a
surface label and the `opening` anomaly was retired in the same pass. A surface label is the
identity of an entire geometric region; only an anomaly carries a bounding box. So from that
moment the schema could say "this whole region is an opening" but not "there is an opening
here", and the box is exactly what a hole needs. Zero anomalies of any kind were reported on
FS-002.

Restored as the `pipe_opening` anomaly, sharing the id with the surface label the way
`rebar_visible` already does. The box is an approximate extent around the hole and its rim,
not an outline. `label_map_from_regions()` paints anomaly boxes for any label that has a
colour, so the hole now takes the teal inside region #1 while the region keeps
`tile_remnant` as its surface identity. Both statements are true and they are on different
axes.

## 3. Corpus integrity (found while validating the smear threshold)

Running the crop builder over all six fragments surfaced problems in the inputs themselves.
Only FS-004 and FS-006 are sound.

| fragment | faces | state |
|---|---|---|
| FS-001 | 47,292 | coarse export, ~70× below FS-004/006 |
| FS-002 | 23,220 | point-cloud path; recorded dims (976×920×724) do not match its own GLB (853×730×494) |
| FS-003 | 3,016 | **~1000× too coarse.** Recorded planes match under 4% of faces, UV coherence 0.01, nothing classified. This fragment currently contributes no surface labels at all |
| FS-004 | 3,361,768 | sound |
| FS-005 | 2,132,300 | **duplicate of FS-006** |
| FS-006 | 2,132,300 | sound; best record |

**FS-005 and FS-006 are the same physical fragment**, confirmed by Muchen as the same mesh
exported twice to test two versions of the Blender workflow. Identical face count
(2,132,300) and identical volume to six decimals (0.324468); the vertex counts differ
(1,086,229 vs 1,098,318) only because two Smart UV Project runs split a different number of
seam vertices.

The pair is useful as an A/B on the export itself. FS-006 carries the `_scan_coverage.json`
sidecar and bakes cleanly. FS-005 does not, and its bake failed almost completely: region #0
is 90% smeared, marbled rather than concrete. It was being sent to the vision model as real
surface until the smear gate caught it. That is direct evidence that the smear gate earns
its place, and that an unmarked ground-contact face is where a bake fails first.

For §5.2 the count still matters: five distinct fragments, not six.

**Everything is to be re-exported once the bugs are fixed** (Muchen, 2026-08-17). The
purpose of the list above is to fix the export, not to patch the records. Before that
re-export:

1. `bake_texture_v2.py` now raises if the remesh comes out under 20% of the expected face
   count. FS-003 at 3,016 faces passed the old fixed floor of 100 and should not have.
2. Mark `UNSCANNED` on every fragment, not only FS-003 and FS-006. See §5.
3. Bake margin 32 px, Extend.

Then `--batch --force`, and only then read the §5.2 results.

## 4. Open

- **Re-run to see the effect.** The prompt and the crop construction both changed, so the
  API cache is correctly invalidated. Needs `--batch --force`, which spends credit.
  Check afterwards whether FS-006 still returns `opening`.
- **Threshold is tuned on one fragment.** `SMEAR_COH_MIN = 0.65` was chosen by looking at
  FS-006 region #0. Confirm on FS-002 to FS-005 before treating it as settled.
- **The smear is a capture problem, not only a processing one.** The real fix is more
  photographs at that face during scanning. Worth noting in the paper as a limitation of
  handheld photogrammetry on a large fragment, and worth a line in the scanning protocol.
- **Patch sampling is shelved.** It would buy the last 20–30% of crop area and costs
  region shape and anomaly localisation. The argument for it rested on the contamination
  figure that did not reproduce.
- **Region #3 (residual) is never classified** on any fragment: UV coherence 0.05. That is
  correct behaviour, but it means a fifth of the surface area is unassessed. Decide
  whether to report that share explicitly in §5.2.

## 5. Commands

```powershell
env\venv\Scripts\activate

# see the smear detection without spending API credit
python 03_src/run_pipeline.py FRAG-S1-FS-006 --geometry-only

# re-classify with the new crops (spends credit, cache invalidated by the prompt change)
python 03_src/run_pipeline.py --batch --force --serve
```
