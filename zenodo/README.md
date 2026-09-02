# Twelve scanned demolition concrete fragments: meshes and textures

Full-resolution 3D scans of twelve reinforced concrete fragments recovered from the
deconstruction of an early twentieth-century building, used to build and evaluate the
fragment descriptor pipeline reported in the accompanying paper.

The fragments were selected on site, digitised with LiDAR-assisted photogrammetry
(Scaniverse, iPad), then remeshed at 2 mm, UV unwrapped and texture-rebaked in Blender.
Twelve of them were built into a public urban-furniture installation, which is where the
design decisions used to evaluate the pipeline come from.

## Contents

24 files, 1.27 GB.

- `FRAG-S1-FS-0NN.glb` — cleaned mesh with UV layout, 0.9 to 5.7 million faces
- `FRAG-S1-FS-0NN_texture.png` — baked colour texture, 4096 px

`MANIFEST.md` lists sizes and abbreviated checksums; `checksums.sha256` has them in full,
so a download can be verified against what the paper used.

## What is *not* here, and where it is

The code, the per-fragment JSON records, the descriptor schema, both blind-sampled tile
sets with their hand labels, and a browsable web viewer are in the repository:

**https://github.com/muchenykadk/study2-descriptor-pipeline**

Only the large meshes are deposited here, because they exceed what a git repository can
reasonably carry. Everything needed to read the results, repeat the evaluation or inspect
the records is in the repository and needs no download from this record.

## Coordinate frame and units

Millimetres. Each fragment is in its own local frame with no shared datum, since the
pieces were scanned individually rather than in situ.

## The unscanned face

Every fragment was scanned resting on the ground, so its contact face was never captured
and is reconstructed as patched geometry. Those faces are marked during preparation and
the pipeline excludes them from surface classification, flagging any plane within 25° of
their normal as unreliable.

This matters when reusing the meshes: **the reconstructed underside is invented geometry**,
not measurement. In the corpus, 14 of 87 fitted faces are flagged on this test, and six of
those would otherwise meet the pipeline's bearing-face condition. Capturing each fragment
in two orientations would recover them, and is the obvious improvement to this dataset.

## Provenance and status

Mass is estimated from mesh volume at an assumed density of 2500 kg/m³ and is not
weighed. Concrete strength, reinforcement layout and centre of mass were not measured.
Surface feature labels in the repository records come from a vision-language model and
are marked `provisional`; the evaluation reported in the paper finds they do not exceed a
null baseline. Geometry computed from these meshes is deterministic and verified.

## Citation

Cite the paper for the method and this record for the data. If you use only the scans,
this record alone is sufficient.

## Licence

CC BY 4.0. Attribution requested for both the paper and this record.
