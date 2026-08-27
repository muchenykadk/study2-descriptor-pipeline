#!/usr/bin/env python3
"""
Export region crops as candidate reference exemplars, grouped by their current label.

The vision model is asked to apply a verbal definition of "formwork imprint" or
"fracture surface" and interpret it alone, which is why the standard drifts from
fragment to fragment.  Every fragment here comes from one building: one mix, one
formwork system, one demolition method.  So the standard can be shown instead of
described, by giving the model labelled exemplars from this same material before
it sees anything else.

This script produces the candidates.  It does not choose them: it writes every
region crop into a folder named for the label it currently carries, and you pick
the ones that genuinely represent each category.

    python 03_src/build_reference_set.py            # all processed fragments
    python 03_src/build_reference_set.py FRAG-S1-FS-006
    python 03_src/build_reference_set.py --check    # validate a hand-made set

Output:

    01_input/reference_surfaces/_candidates/{label}/{fragment}_r{region}.png

Then move the good ones up one level, into
`01_input/reference_surfaces/{label}/`, which is where the pipeline reads them.
Anything left in `_candidates/` is ignored.

Two or three clear exemplars per label is plenty; every reference image is sent
with every call, so a large set costs tokens on every fragment.

Note for the paper: exemplars chosen by eye make the classifier agree with
whoever chose them.  That is a legitimate operational definition of the
categories, and it is not validation.  It has to be reported as such, in the
same terms as the design factors drawn from Study 1.
"""

import argparse
import json
import sys
from pathlib import Path

import trimesh
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

from ai.region_classification import build_region_crops, REFERENCE_DIR  # noqa: E402
from descriptors.regions import segment_regions                        # noqa: E402

RECORD_DIR = REPO_ROOT / "05_output" / "descriptors"
CANDIDATE_DIR = REFERENCE_DIR / "_candidates"


def _labels_by_region(record: dict) -> dict:
    return {r.get("region_id"): r.get("label")
            for r in ((record.get("vision") or {}).get("regions") or [])}


def export(frag_id: str) -> int:
    """Write one fragment's region crops into per-label candidate folders."""
    glb = RECORD_DIR / f"{frag_id}.glb"
    tex = RECORD_DIR / f"{frag_id}_texture.png"
    rec_p = RECORD_DIR / f"{frag_id}_geometry.json"
    if not (glb.exists() and tex.exists() and rec_p.exists()):
        print(f"  {frag_id}: not processed, skipping")
        return 0

    record = json.loads(rec_p.read_text(encoding="utf-8"))
    mesh = trimesh.load(glb, force="mesh", process=False)
    if float(max(mesh.bounding_box.primitive.extents)) < 10.0:
        mesh.apply_scale(1000.0)

    planes = [{"plane_abcd": f["plane_abcd"], "normal_xyz": f["normal_xyz"]}
              for f in record.get("planarity", [])]
    regions = segment_regions(mesh, planes)
    labels = _labels_by_region(record)

    written = 0
    for crop in build_region_crops(Image.open(tex), mesh, regions):
        if crop["image"] is None:
            continue
        label = labels.get(crop["region_id"]) or "_unlabelled"
        folder = CANDIDATE_DIR / label
        folder.mkdir(parents=True, exist_ok=True)
        crop["image"].save(folder / f"{frag_id}_r{crop['region_id']}.png")
        written += 1
    print(f"  {frag_id}: {written} crop(s)")
    return written


# What matters is how much REAL SURFACE a crop covers, not its pixel count.
# Measured across this corpus the atlas resolves 0.2 to 0.6 px per mm, so a
# 100 px crop covers 160 to 460 mm depending on the fragment. Coarse aggregate
# runs 8 to 32 mm, and a surface needs several particles visible to be
# characterised, so the useful range is roughly 150 to 350 mm of surface.
# At these densities that is about 70 to 220 px. Below ~100 px you are looking
# at too few particles at any density; above 512 px is wasted, because the API
# downscales reference images to 512 at detail: low.
MIN_SIDE      = 100     # px; see above, this is a floor not a target
MAX_SIDE      = 512     # px; beyond this the API downscales anyway
MAX_FILLER    = 0.10    # magenta or empty-atlas black; see below
MIN_DETAIL_SD = 4.0     # below this it is a flat wash, not a surface
PER_LABEL_MAX = 4       # every reference rides on every call

# An exemplar should be material and nothing else.  Rather than enumerate the
# colours filler happens to take, which turned out to be a losing game, look for
# what they have in common: a sizeable area carrying no surface detail.  That
# catches magenta from a whole-region cut-out, black from empty atlas, and the
# white or black an image editor leaves behind when it flattens transparency on
# save, which is the trap in cropping with Windows Photos.
#
# Why it matters: the prompt already tells the model magenta is not material, so
# filler carries no information about what a label means, and with only two or
# three exemplars per label a difference in filler share between labels can
# become a spurious cue for the label itself.  Transparency left in place is
# worse still, because the API flattens alpha before the model sees it, so the
# appearance is decided downstream rather than by you.


def check_set() -> int:
    """Validate a hand-picked reference set. Form only: a human judges content.

    Returns the number of problems found.
    """
    import numpy as np
    from scipy import ndimage
    sys.path.insert(0, str(REPO_ROOT / "03_src"))
    from ai.taxonomy import TAXONOMY

    if not REFERENCE_DIR.is_dir():
        print(f"\n  No reference set at {REFERENCE_DIR.relative_to(REPO_ROOT)}\n")
        return 0

    problems, counts = 0, {}
    print()
    for label in TAXONOMY:
        folder = REFERENCE_DIR / label
        imgs = ([p for p in sorted(folder.iterdir())
                 if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
                if folder.is_dir() else [])
        counts[label] = len(imgs)
        if not imgs:
            continue
        print(f"  {label}  ({len(imgs)})")
        if len(imgs) > PER_LABEL_MAX:
            print(f"      ! {len(imgs)} images; every one is sent on every call. "
                  f"Keep to {PER_LABEL_MAX} or fewer.")
            problems += 1
        for p in imgs:
            src = Image.open(p)
            alpha = (np.array(src.getchannel("A")) < 250
                     if "A" in src.getbands() else None)
            a = np.array(src.convert("RGB"))
            h, w = a.shape[:2]
            magenta = ((a[:, :, 0] > 250) & (a[:, :, 1] < 5) & (a[:, :, 2] > 250))
            black   = a.max(axis=2) < 12
            g = a.astype(float).mean(axis=2)
            mu = ndimage.uniform_filter(g, 15)
            sd_map = np.sqrt(np.maximum(
                ndimage.uniform_filter(g * g, 15) - mu * mu, 0.0))
            sd = float(sd_map.mean())

            # Any sizeable patch with no detail, whatever colour it happens to be.
            blank = ndimage.binary_opening(sd_map < 1.5, np.ones((9, 9)))
            blank = ndimage.binary_closing(blank, np.ones((15, 15)))
            filler = magenta | black | blank
            if alpha is not None:
                filler = filler | alpha
            mag = float(filler.mean())
            notes = []
            if alpha is not None and alpha.mean() > 0.005:
                notes.append(f"{alpha.mean():.1%} transparent; the API flattens alpha "
                             f"before the model sees it, so flatten to RGB yourself or "
                             f"crop where there is none")
            if min(h, w) < MIN_SIDE:
                notes.append(f"only {w}x{h} px. At this atlas resolution that is well "
                             f"under 150 mm of real surface, too few aggregate particles "
                             f"to characterise a texture")
            elif max(h, w) > MAX_SIDE:
                notes.append(f"{w}x{h} px; the API downscales references to {MAX_SIDE}, "
                             f"so the extra resolution is discarded")
            if mag > MAX_FILLER:
                what = []
                if magenta.mean() > 0.01: what.append("magenta")
                if black.mean()   > 0.01: what.append("empty atlas")
                if blank.mean()   > 0.01: what.append("flat area with no detail")
                notes.append(f"{mag:.0%} filler"
                             + (f" ({', '.join(what)})" if what else "")
                             + "; crop a clean rectangle of surface instead")
            if sd < MIN_DETAIL_SD:
                notes.append(f"local detail sd {sd:.1f}, this is a flat wash not a surface")
            if notes:
                problems += len(notes)
                print(f"      ! {p.name}: " + "; ".join(notes))
            else:
                print(f"      ✓ {p.name}  {w}x{h}, {mag:.0%} filler, detail sd {sd:.1f}")

    # Where an exemplar came from matters as much as what it shows. A crop taken
    # from an export that fails pre-flight teaches the category from a bad bake,
    # and the model has no way to know the difference.
    try:
        from preflight import preflight
        bad = set()
        for fid in {p.stem.replace("_geometry", "")
                    for p in (REPO_ROOT / "05_output" / "descriptors").glob("*_geometry.json")}:
            if any(f.level == "fail" for f in preflight(fid)):
                bad.add(fid)
        flagged = []
        for label in TAXONOMY:
            folder = REFERENCE_DIR / label
            if not folder.is_dir():
                continue
            for p in folder.iterdir():
                for fid in bad:
                    if p.name.startswith(fid):
                        flagged.append((label, p.name, fid))
        if flagged:
            print(f"\n  note: {len(flagged)} exemplar(s) come from an export that fails "
                  f"pre-flight:")
            for label, name, fid in flagged:
                print(f"      {label}/{name}  ({fid})")
            print(f"    Pre-flight failures on this corpus are GEOMETRIC (remesh too "
                  f"coarse). The texture\n    is baked at full resolution regardless, and "
                  f"a coarser mesh unwraps into fewer, larger\n    UV islands, so it can "
                  f"carry MORE texels per mm than a fine mesh. Measured on this\n    "
                  f"corpus, FS-002 has the sharpest texture of all seven. Judge the crop "
                  f"by eye,\n    not by its parent's pre-flight status.")
    except Exception:
        pass

    present = {k: v for k, v in counts.items() if v}
    if not present:
        print("  Empty set. The pipeline runs uncalibrated.\n")
        return problems
    lo, hi = min(present.values()), max(present.values())
    if hi >= 2 * lo and hi - lo >= 2:
        print(f"\n  ! Unbalanced: {hi} for one label against {lo} for another. "
              f"Counts act as a prior, so keep them roughly equal.")
        problems += 1
    try:
        from ai.taxonomy import RETIRED
        dead = [l for l in TAXONOMY if counts.get(l) and l in RETIRED]
        if dead:
            print(f"\n  ! exemplars for retired label(s): {', '.join(dead)}. They are sent "
                  f"to the model,\n    but the label is out of the prompt, so nothing can "
                  f"ever be classified as it.")
            problems += len(dead)
    except ImportError:
        pass

    missing = [l for l in TAXONOMY if not counts[l]]
    if missing:
        print(f"\n  Note: no exemplar for {', '.join(missing)}. Those labels stay "
              f"defined by their written rule alone, which is acceptable if the "
              f"category does not occur in this building.")

    print(f"\n  {problems} problem(s).\n" if problems else "\n  Set looks well formed.\n")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fragment_id", nargs="?", help="default: every processed fragment")
    ap.add_argument("--check", action="store_true",
                    help="validate the reference set instead of exporting candidates")
    args = ap.parse_args()

    if args.check:
        sys.exit(1 if check_set() else 0)

    ids = ([args.fragment_id] if args.fragment_id
           else sorted(p.stem.replace("_geometry", "")
                       for p in RECORD_DIR.glob("*_geometry.json")))
    if not ids:
        print("\n  Nothing processed yet. Run the pipeline first.\n")
        sys.exit(1)

    print()
    total = sum(export(fid) for fid in ids)
    if not total:
        print("\n  No crops written.\n")
        return

    try:
        shown = CANDIDATE_DIR.relative_to(REPO_ROOT)
    except ValueError:
        shown = CANDIDATE_DIR
    print(f"\n  {total} candidate(s) in {shown}")
    print(f"  Pick two or three per label and move them up one level, into")
    print(f"  {REFERENCE_DIR.relative_to(REPO_ROOT)}/<label>/ , then re-run the pipeline.\n")


if __name__ == "__main__":
    main()
