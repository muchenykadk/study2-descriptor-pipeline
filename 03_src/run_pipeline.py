#!/usr/bin/env python3
"""
Study 2 Descriptor Pipeline — main entry point.

Usage
-----
Full pipeline — geometry + AI classification (default):
    python 03_src/run_pipeline.py FRAG-S1-001

Geometry only — skip AI (faster, no API key needed):
    python 03_src/run_pipeline.py FRAG-S1-001 --geometry-only

See WORKFLOW.md for full workflow instructions.

Output
------
05_output/descriptors/FRAG-S1-001_geometry.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── path setup ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

import numpy as np
import open3d as o3d
import trimesh
from descriptors.geometry import (bounding_descriptors, bounding_descriptors_pcd,
                                   planar_regions, curvature_stats)
from descriptors.feature_texture import build_feature_textures
from report import generate_report, open_report, update_inventory
from ai.vision_client import classify_texture
from ai.texture_segmentation import classify_texture_grid


# ── helpers ──────────────────────────────────────────────────────────────────

def _scale_check(max_dim_mm: float) -> None:
    if max_dim_mm < 50:
        print(f"\n  ⚠ SCALE WARNING: largest dimension {max_dim_mm:.1f} mm — too small.")
        print(f"  Likely metres or cm units. Check export scale settings.\n")
    elif max_dim_mm > 5000:
        print(f"\n  ⚠ SCALE WARNING: largest dimension {max_dim_mm:.1f} mm — too large.\n")


def load_input(frag_id: str, processed_dir: Path):
    """
    Load geometry for analysis. Priority: PLY → GLB → OBJ (fallback).
    PLY is preferred for point-cloud-based scanners.
    GLB is the primary Blender export and is preferred over OBJ.
    Returns (source, input_type) where input_type is 'mesh' or 'point_cloud'.
    """
    frag_dir  = processed_dir / frag_id
    ply_path  = frag_dir / f"{frag_id}.ply"
    glb_path  = frag_dir / f"{frag_id}.glb"
    obj_path  = frag_dir / f"{frag_id}.obj"

    if ply_path.exists():
        pcd = o3d.io.read_point_cloud(str(ply_path))
        n   = len(pcd.points)
        if n == 0:
            print(f"\n  ERROR: PLY loaded but contains no points: {ply_path}")
            sys.exit(1)
        print(f"  Loaded PLY: {n:,} points  |  colors: {pcd.has_colors()}")
        obb     = pcd.get_oriented_bounding_box()
        max_dim = float(max(obb.extent))
        # Auto-scale: Scaniverse exports in metres; pipeline expects mm.
        # If largest dimension < 10, it's almost certainly in metres (a concrete
        # fragment is never < 10 mm). Scale × 1000 to convert to mm.
        if max_dim < 10.0:
            print(f"  ⚠ PLY largest dim = {max_dim:.4f} — looks like metres. "
                  f"Auto-scaling ×1000 to mm.")
            pcd.scale(1000.0, center=pcd.get_center())
            obb     = pcd.get_oriented_bounding_box()
            max_dim = float(max(obb.extent))
            print(f"  After scaling: largest dim = {max_dim:.1f} mm")
        _scale_check(max_dim)
        return pcd, "point_cloud"

    elif glb_path.exists():
        mesh = trimesh.load(str(glb_path), force="mesh")
        print(f"  Loaded GLB: {len(mesh.vertices):,} vertices · {len(mesh.faces):,} faces")
        print(f"  Watertight: {mesh.is_watertight}")
        max_dim = float(max(mesh.bounding_box_oriented.primitive.extents))
        _scale_check(max_dim)
        return mesh, "mesh"

    elif obj_path.exists():
        mesh = trimesh.load(str(obj_path), force="mesh")
        print(f"  Loaded OBJ: {len(mesh.vertices):,} vertices · {len(mesh.faces):,} faces")
        print(f"  Watertight: {mesh.is_watertight}")
        max_dim = float(max(mesh.bounding_box_oriented.primitive.extents))
        _scale_check(max_dim)
        return mesh, "mesh"

    else:
        print(f"\n  ERROR: no input found in {frag_dir}")
        print(f"  Expected: {frag_id}.ply  or  {frag_id}.glb")
        sys.exit(1)


def _print_phase2_summary(bounding: dict, planes: list, curv: dict) -> None:
    dims = [f"{d:.1f}" for d in bounding["obb_dims_mm"]]
    print(f"OBB {' × '.join(dims)} mm  |  mass est. {bounding['mass_kg_est']} kg")
    print(f"  Running RANSAC plane segmentation ...", end=" ", flush=True)
    print(f"{len(planes)} region(s) found")
    for i, r in enumerate(planes):
        area = f"{r['area_m2_est']:.4f} m²" if r.get("area_m2_est") else "area unknown"
        print(f"    Region {i+1}: {area}  RMS {r['fit_rms_mm']} mm  "
              f"inliers {r['inlier_fraction']:.0%}")
    if "fine_mm" in curv:
        print(f"  Curvature: fine mean {curv['fine_mm']['mean_rad']:.4f} rad  "
              f"coarse mean {curv['coarse_mm']['mean_rad']:.4f} rad")


def run_phase2(frag_id: str, mesh: trimesh.Trimesh,
               ransac_threshold: float = 3.0) -> dict:
    print("\n  ── Phase 2: geometric descriptors (mesh) ──")
    print("  Computing bounding geometry ...", end=" ", flush=True)
    bounding = bounding_descriptors(mesh)
    planes = planar_regions(mesh, distance_threshold_mm=ransac_threshold)
    print("  Computing curvature ...", end=" ", flush=True)
    curv = curvature_stats(mesh)
    print("done")
    _print_phase2_summary(bounding, planes, curv)
    return {
        "fragment_id":      frag_id,
        "input_type":       "mesh",
        "pipeline_version": "v0.2",
        "computed_at":      datetime.now(timezone.utc).isoformat(),
        "ransac_threshold_mm": ransac_threshold,
        "bounding":         bounding,
        "planarity":        planes,
        "curvature":        curv,
    }


def run_phase2_pcd(frag_id: str, pcd: o3d.geometry.PointCloud,
                   ransac_threshold: float = 3.0) -> dict:
    print("\n  ── Phase 2: geometric descriptors (point cloud) ──")
    print("  Computing bounding geometry ...", end=" ", flush=True)
    bounding = bounding_descriptors_pcd(pcd)
    print("  Running RANSAC plane segmentation ...", end=" ", flush=True)
    planes = planar_regions(pcd, distance_threshold_mm=ransac_threshold)
    print(f"{len(planes)} region(s) found")
    print("  Computing curvature ...", end=" ", flush=True)
    curv = curvature_stats(pcd)
    print("done")
    _print_phase2_summary(bounding, planes, curv)
    return {
        "fragment_id":      frag_id,
        "input_type":       "point_cloud",
        "pipeline_version": "v0.2",
        "computed_at":      datetime.now(timezone.utc).isoformat(),
        "ransac_threshold_mm": ransac_threshold,
        "bounding":         bounding,
        "planarity":        planes,
        "curvature":        curv,
    }


def _normalize_points(points: np.ndarray):
    """Centre and scale points to [-1, 1]. Returns (pts_n, scale_mm)."""
    centroid = points.mean(axis=0)
    pts_c    = points - centroid
    scale    = float(np.abs(pts_c).max()) or 1.0
    return pts_c / scale, scale


def build_viewer_data(mesh: trimesh.Trimesh, planes: list, n_points: int = 2000) -> dict:
    """Sample mesh surface, assign region IDs. Points in [-1, 1]."""
    if not planes:
        return {"points": [], "n_regions": 0, "color_mode": "region"}

    points, _ = trimesh.sample.sample_surface(mesh, n_points)
    region_ids = np.full(len(points), -1, dtype=int)
    best_dist  = np.full(len(points), np.inf)

    for i, plane in enumerate(planes):
        a, b, c, d = plane["plane_abcd"]
        normal    = np.array([a, b, c], dtype=float)
        distances = np.abs(points @ normal + d)
        mask = (distances < 5.0) & (distances < best_dist)
        region_ids[mask] = i
        best_dist[mask]  = distances[mask]

    pts_n, scale = _normalize_points(points)
    return {
        "color_mode": "region",
        "points":     [[round(float(x), 4), round(float(y), 4), round(float(z), 4), int(r)]
                       for (x, y, z), r in zip(pts_n, region_ids)],
        "n_regions":  len(planes),
        "scale_mm":   round(scale, 1),
    }


def build_viewer_data_pcd(pcd: o3d.geometry.PointCloud, planes: list,
                           n_points: int = 2000) -> dict:
    """
    Subsample PLY point cloud for viewer.
    Uses actual scan RGB colors (color_mode='scan').
    Also assigns region IDs for optional overlay.
    Each point: [x, y, z, r_id, R, G, B]  (R/G/B in 0–1 float)
    """
    pts_all = np.asarray(pcd.points)
    has_col = pcd.has_colors()
    col_all = np.asarray(pcd.colors) if has_col else None   # 0–1 float

    # Subsample
    n = len(pts_all)
    if n > n_points:
        idx  = np.random.choice(n, n_points, replace=False)
        pts  = pts_all[idx]
        cols = col_all[idx] if has_col else None
    else:
        pts  = pts_all
        cols = col_all

    # Assign region IDs
    region_ids = np.full(len(pts), -1, dtype=int)
    best_dist  = np.full(len(pts), np.inf)
    for i, plane in enumerate(planes):
        a, b, c, d = plane["plane_abcd"]
        normal    = np.array([a, b, c], dtype=float)
        distances = np.abs(pts @ normal + d)
        mask = (distances < 5.0) & (distances < best_dist)
        region_ids[mask] = i
        best_dist[mask]  = distances[mask]

    pts_n, scale = _normalize_points(pts)

    packed = []
    for i, ((x, y, z), r_id) in enumerate(zip(pts_n, region_ids)):
        if has_col:
            R, G, B = float(cols[i][0]), float(cols[i][1]), float(cols[i][2])
        else:
            R, G, B = 0.7, 0.7, 0.7
        packed.append([round(float(x), 4), round(float(y), 4), round(float(z), 4),
                       int(r_id), round(R, 3), round(G, 3), round(B, 3)])

    return {
        "color_mode": "scan" if has_col else "region",
        "points":     packed,
        "n_regions":  len(planes),
        "scale_mm":   round(scale, 1),
    }


def save_output(frag_id: str, data: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{frag_id}_geometry.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return out_path


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Study 2 Descriptor Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 03_src/run_pipeline.py FRAG-S1-001                    # full pipeline
  python 03_src/run_pipeline.py FRAG-S1-001 --geometry-only    # geometry only, no AI
        """
    )
    parser.add_argument("frag_id", help="Fragment ID, e.g. FRAG-S1-001")
    parser.add_argument(
        "--geometry-only", action="store_true",
        help="Skip Phase 3 AI classification — geometry descriptors only"
    )
    parser.add_argument(
        "--input-dir",
        default=str(REPO_ROOT / "01_input" / "meshes" / "processed"),
        help="Path to processed meshes folder"
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "05_output" / "descriptors"),
        help="Path to output descriptors folder"
    )
    parser.add_argument(
        "--ransac-threshold", type=float, default=3.0,
        metavar="MM",
        help="RANSAC inlier distance threshold in mm (default: 3.0). "
             "Increase for noisier scans; decrease for cleaner meshes."
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="Skip all calculations — just open the existing report in the browser."
    )
    args = parser.parse_args()
    # Phase 3 runs by default unless --geometry-only is set
    args.phase3 = not args.geometry_only

    # ── Serve-only shortcut ───────────────────────────────────────────────────
    if args.serve:
        output_dir = Path(args.output_dir)
        report_path = output_dir / f"{args.frag_id}_report.html"
        index_path  = output_dir / "index.html"
        if not report_path.exists():
            print(f"\n  No report found at {report_path}")
            print(f"  Run without --serve first to generate it.")
            sys.exit(1)
        # Open the inventory (main page) via HTTP so all links inside it
        # also resolve to http:// — GLB and feature textures load correctly.
        entry = index_path if index_path.exists() else report_path
        print(f"\n  Serving inventory at http://127.0.0.1:PORT/{entry.name} ...")
        print(f"  (Click 'Open 3D Report' for {args.frag_id} from there)")
        open_report(entry)
        return

    processed_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    print(f"\n{'='*50}")
    print(f"  Fragment: {args.frag_id}")
    print(f"{'='*50}")

    # ── Load ─────────────────────────────────────────────────────────────────
    print("\n  Loading input ...")
    source, input_type = load_input(args.frag_id, processed_dir)

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    print(f"  RANSAC threshold: {args.ransac_threshold} mm")
    if input_type == "point_cloud":
        descriptors = run_phase2_pcd(args.frag_id, source, args.ransac_threshold)
    else:
        descriptors = run_phase2(args.frag_id, source, args.ransac_threshold)

    # ── Phase 3 (optional) ───────────────────────────────────────────────────
    if args.phase3:
        print("\n  ── Phase 3: vision feature extraction ──")
        texture_path = processed_dir / args.frag_id / f"{args.frag_id}_texture.png"
        if not texture_path.exists():
            # try JPG fallback
            texture_path = processed_dir / args.frag_id / f"{args.frag_id}_texture.jpg"
        if texture_path.exists():
            print(f"  Texture: {texture_path.name}")
            vision = classify_texture(texture_path, n_votes=3)
            descriptors["vision"] = vision
            print(f"  Dominant label : {vision.get('dominant_label', '?')}")
            print(f"  Labels present : {', '.join(vision.get('labels_present', []))}")
            print(f"  Surface cond.  : {vision.get('surface_condition', '?')}")
            print(f"  Confidence     : {vision.get('confidence', '?')}")
        else:
            print(f"  ⚠ No texture PNG found at {texture_path}")
            print(f"  Run Blender export script first, then re-run with --phase3")

    # ── Phase 3B: spatial feature localization ───────────────────────────────
    feature_texture_paths: dict = {}   # {"all": Path, "staining": Path, ...}
    if args.phase3 and descriptors.get("vision"):
        texture_path_3b = processed_dir / args.frag_id / f"{args.frag_id}_texture.png"
        if texture_path_3b.exists():
            print("\n  ── Phase 3B: spatial feature localization ──")
            grid_data = classify_texture_grid(texture_path_3b)
            descriptors["vision"]["grid_classification"] = grid_data
            feature_texture_paths = build_feature_textures(
                texture_path_3b,
                grid_data["grid_n"],
                grid_data["cells"],
                output_dir,
                args.frag_id,
            )
        else:
            print("  ⚠ Phase 3B skipped: texture PNG not found")

    # ── Save ─────────────────────────────────────────────────────────────────
    out_path = save_output(args.frag_id, descriptors, output_dir)
    print(f"\n  Saved → {out_path.relative_to(REPO_ROOT)}")

    # ── Report ───────────────────────────────────────────────────────────────
    print("  Building viewer data ...", end=" ", flush=True)
    planes = descriptors.get("planarity", [])
    if input_type == "point_cloud":
        viewer_data = build_viewer_data_pcd(source, planes)
    else:
        viewer_data = build_viewer_data(source, planes)
    print(f"{len(viewer_data['points'])} points packed  ({viewer_data['color_mode']} colors)")

    # Save viewer data separately so index.html can embed it
    viewer_json_path = output_dir / f"{args.frag_id}_viewer.json"
    with open(viewer_json_path, "w", encoding="utf-8") as f:
        json.dump(viewer_data, f)

    import shutil as _shutil
    frag_input_dir = processed_dir / args.frag_id
    texture_path   = frag_input_dir / f"{args.frag_id}_texture.png"

    # Copy GLB into output_dir so the HTML and the mesh are same-origin.
    # Browsers block file:// requests that cross directories, so a relative
    # path like ../../01_input/... silently fails in Chrome.
    glb_src  = frag_input_dir / f"{args.frag_id}.glb"
    glb_path = None
    if glb_src.exists():
        glb_copy = output_dir / glb_src.name
        if not glb_copy.exists() or glb_copy.stat().st_mtime < glb_src.stat().st_mtime:
            _shutil.copy2(glb_src, glb_copy)
            print(f"  Copied GLB → {glb_copy.relative_to(REPO_ROOT)}")
        glb_path = glb_copy

    # Copy texture PNG into output_dir so it is same-origin as the report.
    # The original lives in 01_input/... which is unreachable when the server
    # is rooted at 05_output/descriptors/.
    texture_copy = None
    if texture_path.exists():
        tex_dest = output_dir / texture_path.name
        if not tex_dest.exists() or tex_dest.stat().st_mtime < texture_path.stat().st_mtime:
            _shutil.copy2(texture_path, tex_dest)
            print(f"  Copied texture → {tex_dest.relative_to(REPO_ROOT)}")
        texture_copy = tex_dest

    report_path = generate_report(
        descriptors, output_dir, viewer_data,
        glb_path=glb_path,
        texture_path=texture_copy,
        feature_texture_paths=feature_texture_paths,
    )
    print(f"  Report → {report_path.relative_to(REPO_ROOT)}")

    index_path = update_inventory(output_dir, highlight_id=args.frag_id)
    print(f"  Index  → {index_path.relative_to(REPO_ROOT)}")
    open_report(index_path)

    print(f"\n  Next step: verify output in the inventory,")
    print(f"  then commit: git commit -m 'data: descriptors {args.frag_id}'")
    print()


if __name__ == "__main__":
    main()
