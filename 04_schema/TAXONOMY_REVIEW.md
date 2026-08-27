# Review of the surface feature taxonomy

Status 2026-08-18. Prompted by two observations from Muchen: that the standard applied
varies from fragment to fragment, and that "fracture surface" is an ambiguous term.

Both are correct. This document sets out the evidence, the two mechanisms behind it, where
the categories actually come from, and what to do.

---

## 1. The evidence

Labels assigned across the corpus:

| fragment | regions | labels |
|---|---|---|
| FS-004 | 16 | 9 weathered, 4 formwork_imprint, 1 exposed_aggregate, **0 fracture_surface** |
| FS-005 | 13 | 8 fracture_surface, 3 rebar_visible, **0 weathered, 0 formwork_imprint** |
| FS-006 | 8 | 2 fracture_surface, 2 exposed_aggregate, 1 weathered |
| FS-007 | 12 | 5 fracture_surface, 7 unclassified |

FS-004 and FS-005 come from the same demolition and the same material. They share not one
label. That is not material variation.

## 2. Mechanism one: the taxonomy conflates three questions

Sorted by what each label actually answers:

| axis | question | labels |
|---|---|---|
| **origin** | how the surface came to be | formwork_imprint, fracture_surface, original_finish |
| **exposure** | what is visible in it | exposed_aggregate, rebar_visible |
| **condition** | what has happened since | weathered, staining |

The three are independent, so the labels are not mutually exclusive, yet the schema demands
exactly one. A fracture surface nearly always shows exposed aggregate. A cast face on a
demolished building is nearly always weathered. Both are true at once, and which one gets
returned is arbitrary.

FS-004 was read on the condition axis. FS-005 was read on the origin axis. That is the whole
of the difference.

**This is also why `fracture_surface` is ambiguous.** Its definition, "internal concrete
exposed by demolition break; rough", makes a genesis claim, a roughness claim and a
composition claim in one line. Its subtypes confirm the confusion: `matrix_fracture`,
`aggregate_pullout`, `aggregate_split` and `bond_failure` are fracture-mechanics
distinctions about the interfacial transition zone. They are not resolvable at scan
resolution and they do not change any reuse decision.

## 3. Mechanism two: batch anchoring

`_call_vision()` sends every region of a fragment as numbered images in a single request.
The model labels them relative to one another rather than against an absolute standard, so
it settles on a reading per fragment and carries it across the batch. This is independent of
the taxonomy and would produce inconsistency even with perfectly disjoint labels.

## 4. Where the categories come from

Honestly: before this review, nowhere citable. `taxonomy.json` carried no basis field and no
source. For the paper that is the weak point, and it should be fixed by argument rather than
by finding a standard that happens to contain seven similar words.

Grounding exists, but per axis rather than for the list as a whole:

- **Condition** has established vocabulary in concrete inspection practice. ACI 201.1R on
  visual inspection of concrete in service, and the EN 1504 family on repair, define
  spalling, scaling, efflorescence, exposed reinforcement and staining as terms of art.
  Verify the exact scope of each before citing; do not cite clause contents from memory.
- **Origin** maps onto fabrication and demolition process, which the project's own
  literature review documents well: cast, saw-cut, selectively cut, broken. This is the
  axis the reuse literature actually supports.
- **Exposure** answers the research question rather than any standard, and should be argued
  as such in the paper: it is what a designer needs to know to decide whether a face can be
  drilled, sat on, or shown.

### Citable prior art, found 2026-08-19

The condition axis is no longer ungrounded. Two benchmarks cover almost exactly the
categories arrived at here, independently.

**Mundt, Majumder, Murali, Panetsos and Ramesh (2019), "Meta-learning Convolutional Neural
Architectures for Multi-target Concrete Defect Classification with the COncrete DEfect
BRidge IMage Dataset", CVPR.** arXiv:1904.08486. CODEBRIM: 7,729 patches from 30 bridges,
classes crack, spallation, efflorescence, exposed bars, corrosion stain, and non-defective
background.

Two things it gives this project.

First, **it independently reaches the conclusion of section 2.** Its six classes are
explicitly *mutually non-exclusive*, and the task is defined as multi-target: identify all
defects present rather than assume one. The reason given is that concrete defects overlap.
That is the same finding as the origin / exposure / condition analysis here, arrived at from
a machine-learning direction, and it is a citable authority for the faceted schema in
section 8 rather than an argument this project has to make alone.

Second, **its class list is close to the anomaly set adopted in section 7d**: crack,
spallation and exposed bars correspond to `crack`, `spalling` and `rebar_visible`;
corrosion stain corresponds to `staining`. Two categories suggested and not adopted,
`efflorescence` and `rust_staining`, are both in CODEBRIM, which is an argument for adding
them.

Verified against the full text (arXiv:1904.08486v1, 18 pp.):

- Six mutually non-exclusive classes: crack, spallation, efflorescence, exposed bars,
  corrosion (stains), non-defective background. Five defects plus background.
- The multi-target formulation is justified on structural grounds, not convenience:
  "overlapping defects are more severe with respect to the structural safety."
- **Literature CNN baselines reach 63.05 to 64.93% best-validation multi-target accuracy**
  (Alexnet 63.05, T-CNN 64.30, VGG-A 64.93, VGG-D 64.00), with best-validation test
  accuracies of 66.98 to 70.61%. Meta-learned architectures are equivalent or better with
  fewer parameters and layers.
- The authors note that ImageNet gains do not transfer: Alexnet 81.8% to VGG-D 92.8% top-5
  on ImageNet produces no comparable improvement on CODEBRIM. **General visual recognition
  progress does not carry over to concrete material defect recognition.**

That accuracy range is the single most useful figure for this project. A purpose-built,
fully supervised, architecture-searched CNN on 7,729 expert-annotated patches reaches
roughly 65 to 70%. The task is hard and unsolved with full supervision, which is the correct
context for reporting a zero-shot vision-language result rather than an excuse for one.

**Flotzinger, Rösch and Braml (2024), "dacl10k: Benchmark for Semantic Bridge Damage
Segmentation", WACV.** arXiv:2309.00460. 9,920 images from real bridge inspections, 12
damage classes plus 6 bridge components, for multi-label semantic segmentation.

Its most useful number is a limitation, not a capability: **the best model reaches a mean
IoU of 0.42 on the test set.** That is a purpose-built supervised model, on ten thousand
annotated images, on the same problem. It is the right calibration for what a general
vision-language model with three exemplars and no training should be expected to achieve,
and it makes a modest claim in §5.1 defensible rather than apologetic.

**What is still thin, and is itself worth reporting.** Peer-reviewed evaluation of
*vision-language* models specifically, as opposed to trained CNNs, on concrete condition is
sparse. What exists suggests the failure mode seen in this project: a reported tendency to
over-predict cracks, high recall with low specificity, consistent with the spurious
`opening` on FS-006. Verify those figures against the primary source before citing them; the
search that surfaced them did not identify the paper unambiguously.

The honest claim for §5.1 is therefore narrower than "no source exists". The condition axis
can now cite CODEBRIM and dacl10k. The origin axis remains grounded in the fabrication and
demolition literature. The exposure axis, including `tile_remnant`, `cast_in_brick` and
`embedded_metal`, answers the reuse question rather than any standard, and should be argued
as such.

## 5. What has been done now

Two changes that do not commit to a schema change:

**A precedence order.** `_decision_order` in `env/taxonomy.json`, forcing one reading:

```
rebar_visible > original_finish > formwork_imprint > fracture_surface
              > exposed_aggregate > weathered > staining
```

Origin ranks above condition because origin is permanent and design-relevant. A cast face
is the show face, a break is unique geometry, and neither can be undone. Weathering and
staining are superficial, can be cleaned, and frequently obscure an origin that is still
readable. Ranking condition first is precisely what produced the all-weathered reading of
FS-004.

**A decision rule per label**, written to be discriminating rather than descriptive. The
prompt previously sent bare label IDs with no definitions at all, even though
`LABEL_DESCRIPTIONS` already existed and was unused. Each rule now says when *not* to use
the label as well as when to use it, for example that `exposed_aggregate` must not be
chosen merely because aggregate is present, since it is present on most fracture surfaces.

The prompt also now instructs the model to judge each image on its own and not to make the
regions agree.

## 6. Calibration by exemplar (Muchen, 2026-08-18)

A better answer to section 4 than the one section 4 gives.

Every fragment comes from one building: one mix, one formwork system, one demolition
method. So what a formwork imprint looks like *here* is stable, and can be shown rather
than defined. Giving the model labelled exemplar crops from this same material, ahead of
the regions on every call, replaces an abstract definitional problem with a visual
comparison, which is what these models are good at.

This is the reference-specimen approach from materials characterisation: the instrument is
calibrated against known samples. It gives the taxonomy an empirical anchor, and for the
paper it is a far stronger provenance claim than assembling categories from three
traditions. **The categories become operationally defined by exemplars from the donor
building.**

Implemented:

- `01_input/reference_surfaces/<label>/*.png` — the set. Empty by default, so the pipeline
  is unchanged until it is populated.
- `03_src/build_reference_set.py` — exports every region crop into
  `_candidates/<current_label>/` for picking.
- References are sent at `detail: low` ahead of the regions, and hashed into the API cache
  key, so swapping an exemplar correctly invalidates cached answers.

Two limits worth stating plainly:

1. **It is an operational definition, not validation.** Exemplars chosen by eye make the
   classifier agree with whoever chose them. This is the same circularity already noted for
   the design factors drawn from Study 1, and it should be reported in the same terms.
2. **It fixes the standard, not the structure.** An exemplar for `weathered` and one for
   `fracture_surface` still cannot tell the model what to do with a weathered fracture,
   because the two labels answer different questions. Exemplars and the precedence order in
   section 5 are complementary: one sets where the boundary lies, the other decides which
   question gets asked first. The three-axis problem in section 2 survives both.

## 7. Protocol for preparing exemplars by hand

Rules in the order they matter. The first is the one that is easy to get wrong.

**1. Source them from the baked atlas, never from a photograph.** The model compares
exemplars against masked UV crops of a baked diffuse texture: no shading, no perspective,
fixed resolution, a particular colour cast from the bake. A phone photograph of the same
surface differs in lighting, scale, focus and colour, and calibrating with it teaches the
boundary between *photograph and bake* rather than between two surface types. Crop from
`05_output/descriptors/<fragment>_texture.png`, or from what
`build_reference_set.py` exports.

**2. Crop a clean rectangle of material: no magenta, no black.** Aim for 256 to 512 px
square, taken from inside an island on the atlas.

The magenta on the exporter's output is not a convention to follow. Those are whole-region
cut-outs, useful for browsing to find good source material, and they are not finished
references. The atlas PNGs in `05_output/descriptors/` have a black background rather than
magenta, and that is the file to crop from.

Neither filler belongs in a reference image. The prompt already tells the model that magenta
is not material, so it carries no information about what the label means. Worse, with only
two or three exemplars per label, a difference in filler share between labels can become a
spurious cue for the label itself. A clean rectangle removes the variable. Shape is not what
defines a category either, so the region outline is no loss.

**A transparent background is fine as a source**, and slightly better than black, since the
boundary between material and nothing is unambiguous while dark aggregate can be mistaken
for empty atlas. It changes nothing about the method: the crop comes from inside an island,
so the background never enters it.

But **do not leave transparency in a finished exemplar**. The API flattens alpha before the
model sees it, usually onto black and not dependably, so a crop containing transparent
pixels is one whose appearance is decided downstream rather than by you. Flatten to RGB, or
crop where there is none. `--check` now reports transparency separately, since a crop can be
a third invisible while looking perfectly good in a viewer.

**3. Only unambiguous instances.** Pick cases you would defend to an examiner. A borderline
example teaches a blurred boundary, which is worse than no example. If you cannot find one
clear instance of a label in this building, that label may not belong in the taxonomy for
this study, and saying so is a finding.

**4. Choose contrast pairs across the hard boundaries, not distant typical cases.** The
boundaries that actually fail are formwork against fracture, and weathered against
everything. Two exemplars that look similar but sit on opposite sides of a boundary define
it far more sharply than two that look nothing alike. A weathered cast face labelled
`formwork_imprint` next to a weathered break labelled `fracture_surface` teaches both the
boundary and the precedence rule at once.

**5. Two or three per label, roughly balanced.** Counts act as a prior. Five formwork
exemplars against one fracture tilts the model toward formwork. Every reference is also
sent on every call, so a large set costs tokens on every fragment.

**6. Hold the calibration fragments out of the evaluation.** This is the one that matters
for §5.2. If an FS-006 crop defines `fracture_surface` and FS-006 is also in the evaluation
set, the evaluation is contaminated. Either take exemplars only from a fragment reserved for
calibration, or record which regions were used and exclude them from the reported results.
Decide before running, not after.

**6b. The filename is never sent.** Only the folder name, as the label, and the raw image
bytes. Verified by dumping the payload: a file called `FRAG-S1-FS-006_r0_northface.png`
reaches the model as `Reference 1: fracture_surface` plus pixels, and the filename appears
nowhere in the prompt. So naming is free, and there is no channel by which the model could
read the answer off the file.

The contamination that does exist is different, and worth stating precisely in the paper.
The model is *told* each reference's label; that is the mechanism, not a flaw. So the claim
is never "the model determined this category" but "the model matched this region against
surfaces declared to be that category." What could still go wrong is the model recognising
the *same physical surface* rather than the category, which is exactly what happens if an
exemplar is drawn from a fragment being evaluated.

`run_pipeline.py --no-references` is the control. Classify a fragment with and without the
set and compare. A label that holds only when its own fragment supplied the exemplar is
leakage; a label that survives is doing real work. The reference signature is part of the
API cache key, so the two runs cannot collide.

**7. Keep the provenance in the filename.** `FRAG-S1-FS-006_r0.png` says where it came from
and makes the set auditable. The paper should be able to state exactly which surfaces
defined which category.

**8. Freeze the set before the run.** Adjusting exemplars until the outputs look right is
fitting to the answer. Choose once, run, report. If the set changes, say so and say why.

**Cropping in Windows Photos is fine.** Open the atlas, Crop, Save as copy into the label
folder. Two things it does that matter:

- If the atlas has an alpha channel, Photos flattens it on save, usually to white. A crop
  that catches the edge of an island then carries a white band where the transparency was.
  `--check` catches this: it looks for any sizeable area with no surface detail, whatever
  colour it is, rather than for a list of known filler colours.
- Save as PNG if offered the choice. JPEG is accepted, and at this size the artefacts are
  minor, but there is no reason to introduce them.

Check the form of a hand-made set with:

```powershell
python 03_src/build_reference_set.py --check
```

It validates size, magenta share, local detail, per-label counts and balance. It cannot
judge whether an image is a good example of its category; that is the part only you can do,
and it is the whole point of preparing them by hand.

## 7b. Adding a new label

A folder in `reference_surfaces/` is **not** enough. The reference loader walks the
taxonomy, so a folder whose name is not a label is ignored; it now says so rather than
failing in silence. Everything derives from `env/taxonomy.json`, so that is the only file
to edit.

### What each field actually does

| field | reaches the vision model? | used by |
|---|---|---|
| `id` | **yes** | the label the model returns; the key everything else joins on |
| `decision_rule` | **yes** | the numbered list in the prompt, in `_decision_order` sequence |
| `_decision_order` | **yes** | sets both precedence and *which labels appear in the prompt at all* |
| `description` | no | the report legend only |
| `subtypes` | no | the legacy whole-image prompt (`--grid-legacy`) only, not the region path |
| `color` | no | report legend and feature-map PNG |
| `_comment`, `_note`, `_basis`, `_decision_order_rationale`, `_reference_set` | no | notes for humans; the underscore prefix means nothing parses them |

So the two fields that decide how the model behaves are `decision_rule` and
`_decision_order`. `description` is legacy: it predates the decision rules and now only
labels the legend. If a category is being confused, the fix is its `decision_rule` and its
position in `_decision_order`, not its description.

Add an entry to `labels`:

```json
{
  "id": "embedded_metal",
  "color": "#94a3b8",
  "description": "Non-reinforcement steel cast into the element: fixings, angles, plates",
  "subtypes": ["angle", "plate", "channel", "anchor", "conduit", "unknown"],
  "decision_rule": "Steel that is not reinforcement: a fixing, angle, plate or conduit cast
                    into the element. Distinguished from rebar_visible by being a discrete
                    component rather than a bar in a mat."
}
```

and place its id in `_decision_order` at the precedence it should take. Position is a real
decision, not bookkeeping: it decides what happens when the new label competes with an
existing one.

That is all. `TAXONOMY`, `LABEL_COLORS`, `LABEL_DESCRIPTIONS`, `LABEL_SUBTYPES`,
`LABEL_RULES` and `DECISION_ORDER` all derive from that file, the prompt is built from
`DECISION_ORDER` and `LABEL_RULES`, and the report and the feature map take their colour
from `color`.

One thing had to be fixed to make this true: `descriptors/feature_texture.py` carried its
own hardcoded colour table that had to be kept in step by hand, so a new label would have
had no colour and would have vanished from the feature map. It now derives from the
taxonomy.

### Two orders, which are not the same thing

`taxonomy.json` carries the label list twice and they do different jobs.

**The order of `labels`** is each label's integer `feature_id`. `TAXONOMY` follows this
array, and that index is written into every `*_viewer.json` point. FS-006 currently stores
id 2 meaning `exposed_aggregate`. Insert a label at position 2 and every later id shifts by
one, so every fragment already processed silently recolours in the viewer. **Always append
at the end.** `taxonomy_tool.py add` does, and will not offer to do otherwise.

**`_decision_order`** is the precedence the model applies when two labels both fit. It has
no effect on stored data and can be reordered freely, which is what `--after` and `--before`
control.

### Removing a label, and retiring one

`remove` deletes a label outright and refuses unless nothing references it: not assigned in
any record, its `feature_id` absent from every viewer JSON, and no higher `feature_id` in
use, since deleting an entry renumbers everything after it. Verified on `weathered`, which
is in FS-004 and FS-006, and correctly refused.

`retire` is the answer when `remove` refuses, and it is the honest one for a category that
was tried and found wanting. `"retired": true` keeps the id and its index, so every
`feature_id` already written still resolves, while the label drops out of the prompt and out
of the report legend, chips and filters. Nothing new can be assigned to it; anything already
assigned still renders. Reversible with `--undo`.

The distinction matters in `report.py`: the legend and chips build from `ACTIVE`, while the
colour and index arrays still cover the full `TAXONOMY`. Filtering both would shift the
JavaScript index and miscolour stored data, which is the same trap as deleting.

For the paper, retiring is worth preferring over removing. A retired label is a record that
the category was proposed and rejected, which is a finding about the material rather than an
absence.

**Adding, retiring or removing a label changes the prompt, so the API cache is invalidated
and every fragment needs `--force` to be comparable.** Do not change the taxonomy mid-corpus
and compare across the boundary. Renaming an id remains forbidden: it breaks comparability
with everything already processed, silently.

**When to add rather than stretch an existing label.** If a surface keeps being labelled
something that is nearly right, that is a missing category, and recording it is a finding
about the material. The steel angle visible in the FS-008 atlas is a case in point: it is
not reinforcement, so `rebar_visible` is wrong, and it is not a finish, so
`original_finish` is wrong. Either the taxonomy gains `embedded_metal` or the paper should
say the scheme has no term for cast-in fixings.

## 7c. What the taxonomy became (2026-08-19)

Muchen revised it against the material. Retired, in his words: `original_finish` because it
was too ambiguous, `weathered` because it is "probably happening everywhere", `staining` on
the same grounds. Added: `embedded_metal`, `tile_remnant`, `pipe_opening`, `cast_in_brick`.

| | before | after |
|---|---|---|
| origin | formwork_imprint, fracture_surface, original_finish | formwork_imprint, fracture_surface, pipe_opening |
| exposure | exposed_aggregate, rebar_visible | exposed_aggregate, rebar_visible, embedded_metal, tile_remnant, cast_in_brick |
| condition | weathered, staining | **none** |

**The condition axis was dropped entirely, and that is the most interesting outcome here.**
Section 2 argued the three axes were conflated and that condition was the one absorbing
ambiguity. Retiring both its labels removes that escape route: a face that cannot be read on
origin now goes unclassified rather than being called weathered, which reports uncertainty
instead of disguising it.

Muchen's reason is the sharper form of the argument in section 2. **A label that applies to
everything carries no information.** Every fragment came off a building that stood for
decades. Weathering is a property of the corpus, not a way of telling one face from another.

Condition is not lost, it moved to the axis it belonged on. `weathered` and `staining`
remain **anomaly** labels, and an anomaly is localized and carries a bounding box. So
condition is now reported as a patch on a face, with a position, rather than as the identity
of the face. That is the faceted schema of section 8 arriving through the back door for one
axis, without a schema change.

The expansion on the exposure axis is a finding too: `tile_remnant`, `cast_in_brick` and
`embedded_metal` are all things the original seven had no term for, and all three were
visible in the atlases. The taxonomy contracted where it was vague and expanded where the
material was specific, which is the opposite of what a taxonomy fixed up front would do.

**Design factors updated in the same pass.** Three rules listed retired labels as
alternatives: `design_assignment` show_face, and the `bench_top` and `exposed_face` uses.
None were dead, since all still fired on `formwork_imprint`, but `exposed_face` had lost
three of its four labels and was collapsing into a duplicate of show_face. Its labels are
now formwork_imprint, tile_remnant and cast_in_brick, which is what "material history
visible" actually means once condition has moved to the anomaly axis. `finishing_requirement`
was untouched: it keys on `if_anomaly: staining`, a different axis, and still fires.

## 7d. Rebuilding condition on the anomaly axis

Retiring `weathered` and `staining` as surface labels emptied the condition axis. It was
refilled where condition belongs, as anomalies: `spalling`, `crack`, `biological_growth`,
alongside the rewritten `staining` and `weathered` hints.

The test each had to pass is the one that retired `weathered`: does it show in a baked
photogrammetry texture, does it discriminate rather than apply everywhere, and does it
change a decision.

| anomaly | what it changes |
|---|---|
| `spalling` | section loss and probable steel behind, so it bears on whether a face can carry load. Distinct from `fracture_surface`: spalling is loss FROM a face, a fracture IS the face |
| `crack` | where the piece breaks next, and whether it can span. Nothing previously captured it |
| `biological_growth` | identifies the face that was exposed to weather, which is design information, plus a cleaning requirement |

**`carbonation` was excluded deliberately, and the reason is worth a line in the paper.** It
was a subtype of the retired `weathered` and is not visually detectable at all: it requires a
phenolphthalein spray on a fresh break. It could never have been found by this method, so it
is a clean example of a descriptor the instrument cannot supply, as opposed to one it
supplies badly. `erosion` repeats the vagueness that retired its parent, and
`freeze_thaw_damage` is a cause rather than an appearance, presenting as spalling.

Also fixed here: `ANOMALY_LABELS` was hardcoded in `region_classification.py` while the
surface labels were fully config-driven. That asymmetry meant the condition axis became the
least manageable part of the schema at exactly the moment it became the only home for
condition. Anomalies now live in `env/taxonomy.json` with the same retire mechanism, and
carry no feature_id, so nothing renumbers.

## 8. The decision still open

Whether to split the schema into three independent fields:

```
origin     : cast_face | fracture | saw_cut | unreadable        (one)
exposure   : paste | aggregate | reinforcement | applied_finish (many)
condition  : sound | weathered | stained | spalled              (many)
```

**For:** it removes the ambiguity at the root rather than papering over it with a
precedence rule, it lets a face be both a fracture and weathered, which is the truth, and it
makes each axis independently citable.

**Against:** it is a schema change, a full reprocess, a rewrite of Table 1 in the paper, and
changes to every design factor that reads `surface_label`.

**Recommended sequence:** re-run FS-004 and FS-005 with the precedence order in place and
see how much disagreement survives. The prompt changed, so the API cache is already
invalidated. If the two fragments still share no labels, the taxonomy is at fault and the
split is justified. If they converge, the flat list is serviceable and the remaining work is
provenance, not structure.

A second run of the same fragment with the same prompt also gives a cheap repeatability
figure, which §5.2 currently lacks entirely.
