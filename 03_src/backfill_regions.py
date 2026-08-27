#!/usr/bin/env python3
"""
One-off migration for records written before 2026-08-27. Adds two things that
later runs produce for themselves:

  1. `area_m2` on each region.
  2. `adjacent_features` on each planar face.

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
from descriptors.regions import segment_regions, adjacent_faces
from scan_coverage import read_sidecar

# Copied from run_pipeline rather than imported, so this migration does not pull
# in the whole pipeline entry point and its heavier dependencies. Kept in step
# with the constants there; if those change, the partition here stops matching
# and the guard below refuses to write.
UNSCANNED_ANGLE_DEG = 20.0
UNSCANNED_Y_MARGIN  = 80.0


def unscanned_face_idx(mesh, sidecar):
    """Faces of the patched ground-contact surface, as run_pipeline computes them.

    Sidecar avg_normal is Blender Z-up; GLB is Y-up: gltf = [bx, bz, -by].
    """
    bx, by, bz = sidecar["avg_normal"]
    n = np.array([bx, bz, -by], dtype=float)
    n /= np.linalg.norm(n)
    normal_mask = np.abs(mesh.face_normals @ n) >= np.cos(np.radians(UNSCANNED_ANGLE_DEG))
    if not normal_mask.any():
        return None
    cent = mesh.vertices[mesh.faces].mean(axis=1)
    y_bottom = float(cent[normal_mask][:, 1].min())
    idx = np.where(normal_mask & (cent[:, 1] < y_bottom + UNSCANNED_Y_MARGIN))[0]
    return idx if len(idx) else None

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
        for r in regions:
            a = by_id.get(r.get("region_id"))
            if a is not None:
                r["area_m2"] = a
                hit += 1

        # Clear any previous pass before rebuilding, so re-running cannot
        # accumulate duplicates.
        for f in planes:
            f.pop("adjacent_features", None)
            f.pop("adjacent_sources", None)

        links = adjacent_faces(mesh, seg)
        by_region = {r.get("region_id"): r for r in regions}
        n_adj = 0
        for rid, link in links.items():
            src = by_region.get(rid) or {}
            feats = [x["id"] if isinstance(x, dict) else x
                     for x in (src.get("features") or [])]
            if not feats or link["face"] >= len(planes):
                continue
            face = planes[link["face"]]
            own = set(face.get("features") or [])
            new = [f for f in feats if f not in own]
            if not new:
                continue
            face.setdefault("adjacent_features", [])
            face["adjacent_features"] += [f for f in new
                                          if f not in face["adjacent_features"]]
            face.setdefault("adjacent_sources", []).append(
                {"region_id": rid, "kind": src.get("kind"),
                 "boundary_share": link["share"],
                 "faces_touched": link["faces_touched"], "features": new})
            n_adj += 1

        print(f"  {frag_id:<18} {hit}/{len(regions)} regions given an area, "
              f"{n_adj} adjacency link(s)"
              + ("" if hit == len(regions) else "   <-- partial, check partition"))

        if not args.dry_run and (hit or n_adj):
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
