# Defects found and deliberately not fixed, 2026-08-27

Deferred at the author's decision to protect the paper timetable. Written down so that
deferring does not become losing. Each entry states the cause, not the symptom, and what the
correct repair is.

## Repaired since this list was written

**Rules demanding flatness they had no need for.** `exposed_face`, `rough_feature` and
`planter_void` specify no `max_fit_rms_mm` and were still restricted to planar faces. Now
evaluated over regions as well. Show-face recall 1 of 3 → 2 of 3; planter reuse became
expressible.

**Features on fracture surfaces unreachable by attribute query.** Faces now record the
surfaces they meet in `adjacent_features`, weighted by shared boundary above a 50% dominance
threshold. `--label` retrieval 44% → 82% of observations. No design rule reads the field.

**The region cache did not know how many regions it held.** `classify_regions` now compares
the cached region count against the current one and re-classifies on disagreement. This closes
the live half of the cache gap below.

**A migration bug caught before it reached the paper.** `backfill_regions.py` segmented
without excluding the patched ground-contact face while the pipeline excludes it, producing a
different partition, different region ids, and every value attached to the wrong region across
all twelve records. Found only because a pipe opening known to exist on FS-002 failed to link.
The script now refuses to write unless the fresh partition reproduces the saved one on kind and
area for every region. **The lesson is general: any script that re-derives a partition outside
the pipeline must reproduce the pipeline's inputs exactly, and prove it before writing.**

## Blocking a real result

**The smear gate is all-or-nothing at region level.** A region whose smear fraction exceeds
the threshold is discarded whole, including its clean areas. On FS-001 this discards a pipe
opening that is plainly visible in the atlas, whose own texture is unmasked and passes every
gate, because it shares a cluster region with an area reported at 73% unusable. Repair: gate
per tile, so clean sub-areas of a dirty region are still classified. Evidence and coordinates
in `query_validation_2026-08-27.md`.

**`build_region_crops` crops the bounding box of a region's whole UV footprint.** When a
region's faces are scattered across many small UV islands the box is mostly empty, and the
region is discarded as `sparse_uv`. FS-001 regions #3, #6 and #13 report UV fill of 1 to 2%
and hold 14% of the fragment's surface between them. Repair: crop the region's substantial
islands, one crop each, rather than one box around all of them.

## Provenance

**The region cache key does not cover the crop images.** `reg_sig` hashes the region
partition; nothing reflects `build_region_crops`. A replay can therefore answer for images the
pipeline would no longer send, while the key reports a match. This is live now: the smear mask
was corrected today, which changes the crops, and the cache does not know. Repair: hash the
bytes of the crops actually sent into the key.

**FS-012's region pass replays a 2026-08-25 cache.** Legitimate under the current key, and
combined with the above it is the one record answering for pre-fix crops. Repair: clear its
region cache and re-run.

**A failed batch is cached as a valid empty answer.** `_call_vision` returns `{}` when the
response will not parse, and the caller writes that to the cache regardless, so a parse failure
replays forever as a real negative. Repair: do not write a cache entry for a run in which any
batch returned empty.

## Calibration

**The reference set mixes two image domains.** `*_texture.png` exemplars are atlas crops of 79
to 262 px; `Screenshot*` exemplars are 3D viewport captures at several times that magnification,
with shading and perspective the atlas does not have. `rebar_visible` is defined by screenshots
only. `paste_dominant` and `biological_growth` have no exemplar at all yet are reported on five
regions between them, so those rest on the verbal decision rule rather than exemplar matching.
Note that exemplar presence does not predict detection: `embedded_metal` has a proper atlas crop
and is reported on none. Repair: rebuild the set at consistent scale from atlas crops.

**`load_reference_set` iterates `TAXONOMY` rather than `ACTIVE`.** Not traced. The
`_retired` folder is underscore-prefixed and skipped, so the effect may be nil, but the
inconsistency with `_build_taxonomy_block`, which was corrected to `ACTIVE`, is unexplained.

## Corpus consistency

**FS-001 is baked at 2048 while the other eleven are at 4096.** Its texel density is 0.38 px
per mm against roughly 1.4 elsewhere and `CALIB_PX_PER_MM = 0.46`. This must be stated wherever
the corpus is described.

**Every smear fraction recorded before 2026-08-27 is overstated.** `directional_smear` and
`featureless_fill` dilated past their own `valid` mask, reaching 105% of real surface on
FS-001. Fixed today, but no fragment has been re-run, so all twelve records still carry the
inflated figures. They are internally consistent with each other, which is why FS-001 was not
re-run alone.

## Tooling

**`bake_texture_v2.py` writes the scan-coverage sidecar before it can succeed.** The sidecar is
written at step 2.5 and the remesh that can fail is step 3, so a failed run still overwrites a
good record. On 2026-08-27 it replaced FS-001's hand-marked `manual_vertex_group` record, 934
faces with a normal 3.8° from vertical, with an `auto_boundary_loop` guess of zero faces at
13.9°. Restored from git. Repair: write the sidecar only on success, and refuse to downgrade
`manual_vertex_group` to `auto_boundary_loop`.

**The report's GLB is too large for a browser.** FS-001's is now 205 MB with 4.1M vertices
after UV seam splitting, and the viewer's loader fails and then hides the feature button with
no explanation. Repair: write a decimated viewer GLB alongside the full one, and have the error
handler say why the button is gone.

## Known before today, still open

`connection_strategy` tests `area_m2_est` as a bearing area when it is the convex hull of the
plane inliers. Resting pose is not computed, so `leaning_support` and `pedestal_support` admit
every face of every fragment. Features classified on non-planar regions never reach the design
rules.
