# Provenance audit: does every feature come from a real model read?

Asked on 2026-08-27. Checked the code paths that can write a feature and the cache
files behind each of the twelve records.

## Verdict

**No path fabricates a feature.** Features are written only from parsed API responses,
filtered to `ACTIVE`, and kept only on a majority of runs. There is no default label, no
text-derived label, and no synthesis from `reuse_notes` or any other prose field. A failed
call yields absence, not invention.

Three gaps qualify that, one of which affects a record now in the corpus.

## What was verified

**Merging is clean.** `_merge_votes` reads `features` only from run responses, drops any id
not in `ACTIVE`, and requires `n_runs // 2 + 1` votes. A region can return nothing, which is
recorded as a real answer.

**All twelve whole-atlas passes were live calls on 2026-08-27.** Each record's cache file
under the current prompt signature `512082` was written within seconds of the record itself.

**Cache keys are correctly scoped for the question.** The region pass hashes texture bytes,
the region partition, `TAXONOMY`, `ACTIVE`, `LABEL_RULES`, `LOCALIZED`, `_GROUPED` and
`reference_signature()` together, so a changed taxonomy, prompt or reference set cannot
return an old answer. The whole-atlas pass gained its prompt signature after the 2026-08-24
incident where pre-rename answers were replayed into eleven records.

## Gap 1: FS-012's region pass replayed a 2026-08-25 cache

Region-cache files by fragment show eleven fragments with entries written on 2026-08-27 and
one without:

| fragment | latest region-cache date |
|---|---|
| FS-001 | 2026-08-27 |
| FS-002 … FS-011 | 2026-08-27 |
| **FS-012** | **2026-08-25** |

Under the current key that is a legitimate hit: same texture, same partition, same prompt,
same references. The answer is a real model read, taken two days earlier. It becomes a
problem only in combination with Gap 2.

## Gap 2: the cache key does not cover the crop images

`reg_sig` hashes `[[first_face_idx, len(face_idx)] for r in regions]`, which is the region
partition, not the images sent. Nothing in the key reflects `build_region_crops`: the smear
and flat masking, `MASK_FILL`, or crop sizing.

Crop construction changed in this working session, when the smear and flat fractions were
corrected to be measured on-mask. A replay from before that change answers for images that
differ from the ones the pipeline would send today, while the key reports a match.

FS-012 is the one record where this is live.

## Gap 3: a failed batch is cached as a valid empty answer

`_call_vision` returns `{}` when the response will not parse as JSON. The caller merges that
into `result` and writes it to the cache regardless. A parse failure is therefore stored and
replayed afterwards as a legitimate "no features seen", indistinguishable from a real
negative.

## Not a gap, but worth stating in the paper

**Inferred face labels are not model reads.** `propagate_labels` fills unlabelled faces from
the dominant label of their neighbours. On FS-001 that is 97,282 faces against 2,433,392
classified and 3,124,126 left unlabelled. The count is recorded as `inferred_faces` and the
record says so, but any figure quoted as "classified" must exclude it.

**Two features are reported with no exemplar at all.** `paste_dominant` on 4 regions and
`biological_growth` on 1 come from the verbal decision rule alone, since their reference
folders are empty. That is a different basis from the exemplar-matched features and should
not be reported as the same thing.

## Recommended, in order

1. Clear FS-012's region cache and re-run it, so no record depends on a pre-fix crop.
2. Add a crop signature to the region cache key: hash the bytes of the crops actually sent.
   This closes Gap 2 at source rather than by remembering to clear the cache.
3. Do not write a cache entry for a run in which any batch returned empty.
