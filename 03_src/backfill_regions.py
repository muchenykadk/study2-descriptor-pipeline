#!/usr/bin/env python3
"""
One-off migration for records written before 2026-08-27. Adds two things that
later runs produce for themselves:

  1. `area_m2` and `contiguous_area_m2` on each region.
  2. `contiguous_area_m2` on each planar face, which is what the area rules
     should have been testing all along.
  3. `adjacent_features` on each planar face.

Why. `use_suggestions` now evaluates the rules that make no demand on flatness
over surface regions as well as planar faces, because a rule asking about
surface character is answered by a fracture surface as well as a cast one.
Those rules state their thresholds in m² (`min_area_m2`), and regions carried
only `area_frac`, so there was nothing to compare against.

Second, a feature read on a fracture cluster reached nothing. Clusters carry no
`plane_index`, so `--label brick_inclusion` returned nothing on FS-010 while the
model had read the brick correctly. Moving the feature onto the nearest plane
would be false, since the clusters sit 27 to 323 mm away at 35° to 141°. What is
true is that the two surfaces meet, so the adjacency is recorded on the face in
its own field. `features` still means "observed on this face" and no bearing
rule reads the new one.

Both are supplied here for the records already on disk; the pipeline writes them
from now on.

What it does NOT do: no API call, no re-classification, no change to any
feature, label, vote or gate result. Region segmentation is deterministic given
the mesh and the plane set, both already in the record, so re-running it
reproduces the same partition and this only reads areas off it.

    python 03_src/backfill_region_area.py             # write
    python 03_src/backfill_region_area.py --dry-run   # report only

Then rebuild the derived layer, which is also free:

    python 03_src/refresh_factors.py
"""

import argparse
import gc
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

import trimesh
import numpy as np
from descriptors.regions import (segment_regions, unscanned_face_idx,
                                 link_adjacent_features)
from scan_coverage import read_sidecar


DEFAULT_DIR = REPO_ROOT / "05_output" / "descriptors"
MESH_DIR    = REPO_ROOT / "01_input" / "meshes" / "processed"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records-dir", default=str(DEFAULT_DIR))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records = sorted(Path(args.records_dir).glob("*_geometry.json"))
    if not records:
        print(f"  No records in {args.records_dir}")
        return 1

    n_written = 0
    for path in records:
        rec = json.loads(path.read_text(encoding="utf-8"))
        frag_id = rec.get("fragment_id") or path.name[:-len("_geometry.json")]
        regions = ((rec.get("vision") or {}).get("regions") or [])
        if not regions:
            print(f"  {frag_id:<18} no regions, skipped")
            continue
        glb = MESH_DIR / frag_id / f"{frag_id}.glb"
        if not glb.is_file():
            print(f"  {frag_id:<18} mesh not found: {glb}")
            continue

        mesh = trimesh.load(str(glb), force="mesh")
        if float(max(mesh.bounding_box.primitive.extents)) < 10.0:
            mesh.apply_scale(1000.0)          # metres → mm, as load_input does

        planes = rec.get("planarity", []) or []
        # The pipeline segments with the patched ground-contact face excluded.
        # Segmenting without it produces a different partition and different
        # region ids, so the fresh regions would not correspond to the saved
        # ones and every value written here would belong to the wrong region.
        sidecar = read_sidecar(frag_id, MESH_DIR)
        us_idx = unscanned_face_idx(mesh, sidecar) if sidecar is not None else None
        seg = segment_regions(mesh, planes, unscanned_idx=us_idx)

        # Refuse to write if the partitions still disagree: the ids are the only
        # thing tying a saved classification to a fresh geometric region.
        fresh_sig = {r["region_id"]: (r["kind"], r["area_frac"]) for r in seg}
        bad = [r.get("region_id") for r in regions
               if r.get("region_id") not in fresh_sig
               or fresh_sig[r["region_id"]][0] != r.get("kind")
               or abs((fresh_sig[r["region_id"]][1] or 0)
                      - (r.get("area_frac") or 0)) > 0.005]
        if bad:
            print(f"  {frag_id:<18} partition does not reproduce "
                  f"(ids {bad[:6]}{'...' if len(bad) > 6 else ''}) — SKIPPED")
            del mesh, seg
            gc.collect()
            continue
        by_id = {r["region_id"]: r.get("area_m2") for r in seg}

        hit = 0
        by_contig = {r["region_id"]: r.get("contiguous_area_m2") for r in seg}
        for r in regions:
            a = by_id.get(r.get("region_id"))
            if a is not None:
                r["area_m2"] = a
                r["contiguous_area_m2"] = by_contig.get(r.get("region_id"))
                hit += 1

        # The largest continuous piece of each plane, which is what a rule
        # asking for a bearing surface needs. `area_m2_est` is the convex hull
        # of the plane's inliers and spans the gaps between a median of 390
        # disconnected patches, overstating the real surface by a median factor
        # of 6.05.
        n_area = 0
        by_plane = {r["plane_index"]: r for r in seg
                    if r.get("plane_index") is not None}
        for pi, face in enumerate(planes):
            r = by_plane.get(pi)
            if r is not None:
                face["contiguous_area_m2"] = r.get("contiguous_area_m2") or 0.0
                face["n_patches"] = r.get("n_patches")
            else:
                # A plane equation that owns no mesh surface. Segmentation
                # assigns each triangle to its nearest qualifying plane, so a
                # weak fit can end up with none of them: 16 of 87 faces across
                # this corpus, claiming 10.8 m2 of hull area between them that
                # corresponds to no surface. Zero, not the hull, or a face with
                # nothing on it keeps passing area thresholds.
                face["contiguous_area_m2"] = 0.0
                face["n_patches"] = 0
            n_area += 1

        n_adj = link_adjacent_features(mesh, seg, regions, planes)

        print(f"  {frag_id:<18} {hit}/{len(regions)} regions, {n_area} face area(s), "
              f"{n_adj} adjacency link(s)"
              + ("" if hit == len(regions) else "   <-- partial, check partition"))

        if not args.dry_run and (hit or n_adj or n_area):
            path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            n_written += 1

        # These meshes run to millions of faces and `segment_regions` builds
        # per-face arrays over them. Held across the loop, twelve fragments'
        # worth is enough to exhaust memory and be killed mid-run, which would
        # leave the corpus half migrated.
        del mesh, seg, by_id
        gc.collect()

    print(f"\n  {'would write' if args.dry_run else 'wrote'} {n_written} record(s)")
    if not args.dry_run:
        print(f"  Next:  python 03_src/refresh_factors.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
