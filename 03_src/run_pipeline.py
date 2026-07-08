#!/usr/bin/env python3
"""
Study 2 Descriptor Pipeline — main entry point.

Usage
-----
Phase 2 (geometry only — run after every Blender export):
    python 03_src/run_pipeline.py FRAG-S1-001

Phase 3 (geometry + AI classification — run after Phase 2 looks correct):
    python 03_src/run_pipeline.py FRAG-S1-001 --phase3

See WORKFLOW.md for when to run each phase.

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
import trimesh
from descriptors.geometry import bounding_descriptors, planar_regions, curvature_stats
from report import generate_report, open_report


# ── helpers ──────────────────────────────────────────────────────────────────

def load_mesh(frag_id: str, processed_dir: Path) -> trimesh.Trimesh:
    obj_path = processed_dir / frag_id / f"{frag_id}.obj"
    if not obj_path.exists():
        print(f"\n  ERROR: mesh not found at {obj_path}")
        print(f"  Expected after Blender export — see WORKFLOW.md Step 2.")
        sys.exit(1)
    mesh = trimesh.load(str(obj_path), force="mesh")
    print(f"  Loaded:    {len(mesh.vertices):,} vertices · {len(mesh.faces):,} faces")
    print(f"  Watertight: {mesh.is_watertight}")
    return mesh


def run_phase2(frag_id: str, mesh: trimesh.Trimesh) -> dict:
    print("\n  ── Phase 2: geometric descriptors ──")

    print("  Computing bounding geometry ...", end=" ", flush=True)
    bounding = bounding_descriptors(mesh)
    dims = [f"{d:.1f}" for d in bounding["obb_dims_mm"]]
    print(f"OBB {' × '.join(dims)} mm  |  mass est. {bounding['mass_kg_est']} kg")

    print("  Running RANSAC plane segmentation ...", end=" ", flush=True)
    planes = planar_regions(mesh)
    print(f"{len(planes)} region(s) found")
    for i, r in enumerate(planes):
        area = f"{r['area_m2_est']:.4f} m²" if r.get("area_m2_est") else "area unknown"
        print(f"    Region {i+1}: {area}  RMS {r['fit_rms_mm']} mm  "
              f"inliers {r['inlier_fraction']:.0%}")

    print("  Computing curvature ...", end=" ", flush=True)
    curv = curvature_stats(mesh)
    if "fine_mm" in curv:
        print(f"fine mean {curv['fine_mm']['mean_rad']:.4f} rad  "
              f"coarse mean {curv['coarse_mm']['mean_rad']:.4f} rad")
    else:
        print("done")

    return {
        "fragment_id": frag_id,
        "pipeline_version": "v0.2",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "bounding": bounding,
        "planarity": planes,
        "curvature": curv,
    }


def build_viewer_data(mesh: trimesh.Trimesh, planes: list, n_points: int = 2000) -> dict:
    """
    Sample mesh surface and assign each point to its nearest planar region.
    Returns compact structure for the Three.js viewer embedded in the HTML report.
    Points normalised to [-1, 1] for stable camera setup.
    """
    if not planes:
        return {"points": [], "n_regions": 0}

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

    centroid = points.mean(axis=0)
    pts_c    = points - centroid
    scale    = float(np.abs(pts_c).max()) or 1.0
    pts_n    = pts_c / scale

    return {
        "points":    [[round(float(x), 4), round(float(y), 4), round(float(z), 4), int(r)]
                      for (x, y, z), r in zip(pts_n, region_ids)],
        "n_regions": len(planes),
        "scale_mm":  round(scale, 1),
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
  python 03_src/run_pipeline.py FRAG-S1-001
  python 03_src/run_pipeline.py FRAG-S1-001 --phase3
        """
    )
    parser.add_argument("frag_id", help="Fragment ID, e.g. FRAG-S1-001")
    parser.add_argument(
        "--phase3", action="store_true",
        help="Also run Phase 3 AI classification (requires ANTHROPIC_API_KEY in env/.env)"
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
    args = parser.parse_args()

    processed_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    print(f"\n{'='*50}")
    print(f"  Fragment: {args.frag_id}")
    print(f"{'='*50}")

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    print("\n  Loading mesh ...")
    mesh = load_mesh(args.frag_id, processed_dir)
    descriptors = run_phase2(args.frag_id, mesh)

    # ── Phase 3 (optional) ───────────────────────────────────────────────────
    if args.phase3:
        print("\n  ── Phase 3: AI classification ──")
        print("  (not yet implemented — run after Phase 2 output looks correct)")

    # ── Save ─────────────────────────────────────────────────────────────────
    out_path = save_output(args.frag_id, descriptors, output_dir)
    print(f"\n  Saved → {out_path.relative_to(REPO_ROOT)}")

    # ── Report ───────────────────────────────────────────────────────────────
    print("  Building viewer data ...", end=" ", flush=True)
    viewer_data = build_viewer_data(mesh, descriptors.get("planarity", []))
    print(f"{len(viewer_data['points'])} points assigned")

    report_path = generate_report(descriptors, output_dir, viewer_data)
    print(f"  Report → {report_path.relative_to(REPO_ROOT)}")
    open_report(report_path)

    print(f"\n  Next step: verify numbers in the report,")
    print(f"  then commit: git commit -m 'data: geometry descriptors {args.frag_id}'")
    print()


if __name__ == "__main__":
    main()
