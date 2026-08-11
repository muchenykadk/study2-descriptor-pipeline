#!/usr/bin/env python3
"""
Study 2 Descriptor Pipeline — main entry point.

Usage
-----
Full pipeline — geometry + AI classification (default):
    python 03_src/run_pipeline.py FRAG-S1-FS-001

Geometry only — skip AI (faster, no API key needed):
    python 03_src/run_pipeline.py FRAG-S1-FS-001 --geometry-only

Batch — process all unanalyzed fragments automatically:
    python 03_src/run_pipeline.py --batch

Batch geometry only:
    python 03_src/run_pipeline.py --batch --geometry-only

Force re-run even if output already exists:
    python 03_src/run_pipeline.py FRAG-S1-FS-002 --force
    python 03_src/run_pipeline.py --batch --force

Fragment ID format: FRAG-S1-{ARCHETYPE}-{###}
    Archetype codes: FS=Floor Slab  RS=Roof Slab  BM=Beam  CO=Column
                     WL=Load-bearing Wall  WP=Partition Wall  LT=Lintel
                     ST=Stair  BL=Balcony  FP=Facade Panel  FD=Foundation  UN=Unidentified

See WORKFLOW.md for full workflow instructions.

Output
------
05_output/descriptors/FRAG-S1-FS-001_geometry.json
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
from ai.region_classification import (classify_regions, cells_from_regions,
                                      GRID_N as REGION_GRID_N)
from ai.taxonomy import TAXONOMY as _TAXONOMY
from descriptors.regions import segment_regions
from scan_coverage import read_sidecar, flag_unscanned_planes, ANGLE_THRESHOLD_DEG


# ── helpers ──────────────────────────────────────────────────────────────────

_ARCHETYPE_LABELS: dict[str, str] = {
    "FS": "Floor Slab",
    "RS": "Roof Slab",
    "BM": "Beam",
    "CO": "Column",
    "WL": "Load-bearing Wall",
    "WP": "Partition Wall",
    "LT": "Lintel",
    "ST": "Stair",
    "BL": "Balcony",
    "FP": "Facade Panel",
    "FD": "Foundation",
    "UN": "Unidentified",
}

def _parse_archetype(frag_id: str) -> tuple[str, str]:
    """
    Parse archetype code and label from FRAG-S1-{ARCHETYPE}-{###}.
    Returns (code, label), e.g. ("FS", "Floor Slab").
    Falls back to ("UN", "Unidentified") for legacy 3-part IDs.
    """
    parts = frag_id.split("-")
    code  = parts[2] if len(parts) == 4 else "UN"
    label = _ARCHETYPE_LABELS.get(code, "Unidentified")
    return code, label


def _scale_check(max_dim_mm: float) -> None:
    if max_dim_mm < 50:
        print(f"\n  ⚠ SCALE WARNING: largest dimension {max_dim_mm:.1f} mm — too small.")
        print(f"  Likely metres or cm units. Check export scale settings.\n")
    elif max_dim_mm > 5000:
        print(f"\n  ⚠ SCALE WARNING: largest dimension {max_dim_mm:.1f} mm — too large.\n")


def _autoscale_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Blender/Scaniverse GLB exports are in metres; the pipeline expects mm.

    Same heuristic as the PLY path: a concrete fragment is never < 10 mm, so
    a max dimension < 10 means metres → scale ×1000.  Without this, RANSAC's
    3 mm threshold spans the whole fragment (one giant 'plane') and mass /
    area estimates are off by 1e9.
    """
    max_dim = float(max(mesh.bounding_box.primitive.extents))
    if max_dim < 10.0:
        print(f"  ⚠ Mesh largest dim = {max_dim:.4f} — looks like metres. "
              f"Auto-scaling ×1000 to mm.")
        mesh.apply_scale(1000.0)
    return mesh


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
        mesh    = _autoscale_mesh(mesh)
        max_dim = float(max(mesh.bounding_box_oriented.primitive.extents))
        _scale_check(max_dim)
        return mesh, "mesh"

    elif obj_path.exists():
        mesh = trimesh.load(str(obj_path), force="mesh")
        print(f"  Loaded OBJ: {len(mesh.vertices):,} vertices · {len(mesh.faces):,} faces")
        print(f"  Watertight: {mesh.is_watertight}")
        mesh    = _autoscale_mesh(mesh)
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
    arch_code, arch_label = _parse_archetype(frag_id)
    return {
        "fragment_id":      frag_id,
        "archetype":        arch_code,
        "archetype_label":  arch_label,
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
    arch_code, arch_label = _parse_archetype(frag_id)
    return {
        "fragment_id":      frag_id,
        "archetype":        arch_code,
        "archetype_label":  arch_label,
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


VIEWER_UNSCANNED_ID = 100  # sentinel region_id for UNSCANNED points in the viewer

UNSCANNED_ANGLE_DEG = 20.0   # face normal within this angle of sidecar normal
UNSCANNED_Y_MARGIN  = 80.0   # mm above the bottom face still counted
                             # (mesh is auto-scaled to mm in load_input)


def unscanned_face_idx(mesh: trimesh.Trimesh,
                       unscanned_sidecar: dict) -> np.ndarray | None:
    """Return indices of mesh faces belonging to the UNSCANNED (patched) bottom
    face, or None if the sidecar normal matches nothing.

    Single source of truth for the normal + position filter used by the
    texture mask, the viewer point cloud, and the per-face feature labels.
    Sidecar avg_normal is Blender Z-up; GLB is Y-up: gltf = [bx, bz, -by].
    """
    bx, by, bz = unscanned_sidecar["avg_normal"]
    u_normal  = np.array([bx, bz, -by], dtype=float)
    u_normal /= np.linalg.norm(u_normal)

    cos_angles  = np.abs(mesh.face_normals @ u_normal)
    normal_mask = cos_angles >= np.cos(np.radians(UNSCANNED_ANGLE_DEG))
    if not normal_mask.any():
        return None

    # Sidecar avg_center is Blender LOCAL space; GLB is world — derive the
    # bottom-face height from the normal-matching faces instead.
    face_centroids = mesh.vertices[mesh.faces].mean(axis=1)
    y_bottom = float(face_centroids[normal_mask][:, 1].min())
    pos_mask = face_centroids[:, 1] < (y_bottom + UNSCANNED_Y_MARGIN)

    idx = np.where(normal_mask & pos_mask)[0]
    return idx if len(idx) else None


def build_viewer_data(mesh: trimesh.Trimesh, planes: list, n_points: int = 2000,
                      unscanned_sidecar: dict | None = None,
                      grid_data: dict | None = None,
                      texture_path: "Path | None" = None) -> dict:
    """Sample mesh surface, assign region IDs. Points in [-1, 1].

    If unscanned_sidecar is provided, points whose face normal is within 20° of
    the recorded UNSCANNED normal are assigned VIEWER_UNSCANNED_ID (100) and
    rendered grey in the viewer — bypassing RANSAC entirely.

    If grid_data is provided, per-point feature_ids are derived per mesh face:
    the face's UV centroid selects its grid cell → label → TAXONOMY index, and
    each sampled point inherits the label of the face it was sampled from.
    Labels therefore follow the actual texture locations on the 3D surface
    (no spatial-grid smearing).
    """
    if not planes:
        return {"points": [], "n_regions": 0, "color_mode": "region"}

    points, face_indices = trimesh.sample.sample_surface(mesh, n_points)
    region_ids = np.full(len(points), -1, dtype=int)
    best_dist  = np.full(len(points), np.inf)

    for i, plane in enumerate(planes):
        a, b, c, d = plane["plane_abcd"]
        normal    = np.array([a, b, c], dtype=float)
        distances = np.abs(points @ normal + d)
        mask = (distances < 5.0) & (distances < best_dist)
        region_ids[mask] = i
        best_dist[mask]  = distances[mask]

    # UNSCANNED overlay — sampled points inherit membership from their source
    # face via the shared unscanned_face_idx() helper (normal + position
    # filter on mesh faces).  One face set drives the texture mask, the point
    # cloud, the per-face feature labels, and the viewer's mesh overlay.
    has_unscanned  = False
    us_face_set    = None      # np bool array over faces, or None
    us_params      = None      # dict passed to the JS viewer for the 3D test
    if unscanned_sidecar is not None:
        us_idx = unscanned_face_idx(mesh, unscanned_sidecar)
        if us_idx is not None:
            us_face_set = np.zeros(len(mesh.faces), dtype=bool)
            us_face_set[us_idx] = True

            unscanned_mask = us_face_set[face_indices]
            if unscanned_mask.any():
                region_ids[unscanned_mask] = VIEWER_UNSCANNED_ID
                has_unscanned = True
                print(f"  (UNSCANNED: {unscanned_mask.sum()} / {len(points)} sampled points marked)")

            # Parameters for the same test in the viewer JS.
            #
            # FRAME-INVARIANT: the GLB may carry node transforms (FS-006 has a
            # node translation), and the viewer scales/centres the model, so an
            # absolute Y threshold is meaningless in JS.  We therefore ship the
            # cut height as a FRACTION of the mesh's vertical extent; the JS
            # evaluates positions/normals in world space via matrixWorld, where
            # translation + uniform scale preserve the fraction and directions.
            bx, by, bz = unscanned_sidecar["avg_normal"]
            u_n = np.array([bx, bz, -by], dtype=float)
            u_n /= np.linalg.norm(u_n)
            fc  = mesh.vertices[mesh.faces].mean(axis=1)
            vmin_y = float(mesh.vertices[:, 1].min())
            vmax_y = float(mesh.vertices[:, 1].max())
            y_cut  = float(fc[us_idx][:, 1].min()) + UNSCANNED_Y_MARGIN
            y_frac = (y_cut - vmin_y) / max(vmax_y - vmin_y, 1e-9)
            us_params = {
                "normal":    [round(float(v), 4) for v in u_n],
                "cos_angle": round(float(np.cos(np.radians(UNSCANNED_ANGLE_DEG))), 4),
                "y_frac":    round(float(np.clip(y_frac, 0.0, 1.0)), 4),
            }

    # Per-point feature labels via per-face UV lookup.
    #
    # Each mesh face's UV centroid selects its grid cell → label.  Sampled
    # points inherit the label of the face they were sampled from, so labels
    # sit exactly where the classified texture sits on the 3D surface.  The
    # earlier XZ spatial majority-vote is gone: it collapsed the vertical
    # axis (side faces were overwritten by the dominant top-surface label)
    # and rendered bbox-aligned blocks that ignored real surface boundaries.
    #
    # UNSCANNED handling: their UV cells are cleared to None in Phase 3B, so
    # faces landing in those cells stay unlabeled; UNSCANNED sampled points
    # are additionally forced to -1 below.
    feature_ids  = np.full(len(points), -1, dtype=int)
    has_features = False
    if grid_data is not None:
        vis = getattr(mesh, "visual", None)
        if vis is not None and hasattr(vis, "uv") and vis.uv is not None:
            grid_n   = grid_data["grid_n"]
            cells    = grid_data["cells"]
            _t_index = {lbl: i for i, lbl in enumerate(_TAXONOMY)}

            # ── Step 1: label every mesh face from its UV centroid ──────────
            # NOTE V-FLIP: trimesh converts GLB UVs to OpenGL convention
            # (v = 0 at image BOTTOM), while grid cells are in image space
            # (row 0 = image TOP, as classified).  Rows must use (1 - v).
            # The JS viewer needs NO flip: Three.js keeps glTF convention,
            # which already matches image space.
            v_uvs     = np.clip(np.asarray(vis.uv, dtype=float), 0.0, 1.0)  # (V, 2)
            face_uvs  = v_uvs[mesh.faces].mean(axis=1)                      # (F, 2)
            f_ugc     = (face_uvs[:, 0] * grid_n).astype(int).clip(0, grid_n - 1)
            f_ugr     = ((1.0 - face_uvs[:, 1]) * grid_n).astype(int).clip(0, grid_n - 1)
            face_fid  = np.full(len(mesh.faces), -1, dtype=int)
            for fi in range(len(mesh.faces)):
                lbl = cells[f_ugr[fi]][f_ugc[fi]]
                if lbl and lbl in _t_index:
                    face_fid[fi] = _t_index[lbl]

            # UNSCANNED faces → never labeled, regardless of UV cell.  This is
            # the authoritative opt-out: the patched bottom face scatters into
            # many UV cells at trace coverage, so cell-clearing alone cannot
            # exclude it.
            if us_face_set is not None:
                face_fid[us_face_set] = -1

            # ── Step 2: sampled points inherit their source face's label ────
            feature_ids = face_fid[face_indices]

            n_labeled = int((feature_ids >= 0).sum())
            has_features = n_labeled > 0
            print(f"  (Feature labels: {n_labeled}/{len(points)} points labeled "
                  f"from {int((face_fid >= 0).sum())}/{len(face_fid)} labeled faces)")

    # Scan colours: sample the texture at each point's face-UV centroid so the
    # inventory / report viewers can toggle photo colours ↔ region colours
    # ("Show Regions" button appears only when scan colours exist).
    rgb = None
    vis = getattr(mesh, "visual", None)
    if (texture_path is not None and texture_path.exists()
            and vis is not None and hasattr(vis, "uv") and vis.uv is not None):
        from PIL import Image as _PILImage
        tex   = np.asarray(_PILImage.open(texture_path).convert("RGB"),
                           dtype=np.float32) / 255.0
        H, W  = tex.shape[:2]
        v_uvs = np.clip(np.asarray(vis.uv, dtype=float), 0.0, 1.0)
        f_uv  = v_uvs[mesh.faces].mean(axis=1)[face_indices]     # (N, 2)
        px    = np.clip((f_uv[:, 0] * W).astype(int), 0, W - 1)
        # V-FLIP: trimesh UVs are OpenGL convention (v = 0 at image bottom)
        py    = np.clip(((1.0 - f_uv[:, 1]) * H).astype(int), 0, H - 1)
        rgb   = tex[py, px]                                       # (N, 3)

    pts_n, scale = _normalize_points(points)
    if rgb is not None:
        # 8-element points: [x, y, z, region_id, feature_id, r, g, b]
        pts_out = [[round(float(x), 4), round(float(y), 4), round(float(z), 4),
                    int(r), int(f),
                    round(float(cr), 3), round(float(cg), 3), round(float(cb), 3)]
                   for (x, y, z), r, f, (cr, cg, cb)
                   in zip(pts_n, region_ids, feature_ids, rgb)]
    else:
        pts_out = [[round(float(x), 4), round(float(y), 4), round(float(z), 4),
                    int(r), int(f)]
                   for (x, y, z), r, f in zip(pts_n, region_ids, feature_ids)]
    return {
        "color_mode":    "scan" if rgb is not None else "region",
        "points":        pts_out,
        "n_regions":     len(planes),
        "has_unscanned": has_unscanned,
        "has_features":  has_features,
        "unscanned_3d":  us_params,
        "scale_mm":      round(scale, 1),
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


def build_unscanned_texture_mask(
    mesh: trimesh.Trimesh,
    unscanned_sidecar: dict,
    texture_size: int = 1080,
) -> "np.ndarray | None":
    """
    Return a boolean (H, W) mask where True = pixel belongs to UNSCANNED faces.

    Identifies UNSCANNED faces on the already-loaded GLB mesh using the same
    normal + position filter as build_viewer_data, then rasterises their UV
    triangles into texture space.

    Used to zero out fake bottom-face pixels before the 8×8 grid classifier
    sends cells to the vision API — preventing the AI from assigning surface
    feature labels to a synthetically filled face.

    glTF UV convention: (0, 0) = top-left, V increases downward → same as PIL,
    so no V-flip is needed when converting UV → pixel coordinates.
    """
    if unscanned_sidecar is None:
        return None
    vis = getattr(mesh, "visual", None)
    if vis is None or not hasattr(vis, "uv") or vis.uv is None:
        print("  (UNSCANNED texture mask: mesh has no UV — skipping)")
        return None

    # Identify UNSCANNED faces (shared helper — same filter everywhere)
    us_idx = unscanned_face_idx(mesh, unscanned_sidecar)
    if us_idx is None:
        print("  (UNSCANNED texture mask: no matching faces — skipping)")
        return None

    # Rasterise UV triangles of the UNSCANNED faces into a binary mask
    from PIL import Image as _PILImage, ImageDraw as _PILDraw
    img  = _PILImage.new("L", (texture_size, texture_size), 0)
    draw = _PILDraw.Draw(img)

    uv    = mesh.visual.uv   # (N_split_verts, 2) — u,v ∈ [0, 1]
    faces = mesh.faces        # (N_faces, 3) — indices into split-vert array
    W = H = texture_size

    # NOTE V-FLIP: trimesh UVs are OpenGL convention (v = 0 at image bottom);
    # the mask must be in image space (row 0 = top) → rasterise at (1 - v).
    for fi in us_idx:
        tri_uv = uv[faces[fi]]                              # (3, 2)
        px = [(int(float(np.clip(u, 0, 1)) * W),
               int(float(1.0 - np.clip(v, 0, 1)) * H))
              for u, v in tri_uv]
        draw.polygon(px, fill=255)

    mask = np.array(img) > 0
    print(f"  (UNSCANNED texture mask: {mask.sum()} px "
          f"[{mask.mean()*100:.1f}%] from {len(us_idx)} faces)")
    return mask


def _mask_to_excluded_cells(mask: np.ndarray, grid_n: int,
                            threshold: float = 0.3) -> set:
    """
    Return the set of (row, col) grid cells where ≥ threshold of pixels are
    masked as UNSCANNED.  These cells are majority reconstructed-patch texture:
    they are named as such in the classifier prompt and cleared from the grid.

    Cells with only trace patch coverage are NOT excluded — their real texture
    dominates, and patch faces are opted out per-face in 3D anyway.
    """
    H, W = mask.shape
    excluded: set = set()
    for row in range(grid_n):
        for col in range(grid_n):
            r0, r1 = row * H // grid_n, (row + 1) * H // grid_n
            c0, c1 = col * W // grid_n, (col + 1) * W // grid_n
            if mask[r0:r1, c0:c1].mean() >= threshold:
                excluded.add((row, col))
    return excluded


def save_output(frag_id: str, data: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{frag_id}_geometry.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return out_path


# ── single-fragment runner ────────────────────────────────────────────────────

def run_single(frag_id: str, args: argparse.Namespace,
               processed_dir: Path, output_dir: Path,
               open_browser: bool = True) -> None:
    """Run the full pipeline for one fragment."""
    import shutil as _shutil

    print(f"\n{'='*50}")
    print(f"  Fragment: {frag_id}")
    print(f"{'='*50}")

    # ── Load ─────────────────────────────────────────────────────────────────
    print("\n  Loading input ...")
    source, input_type = load_input(frag_id, processed_dir)

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    print(f"  RANSAC threshold: {args.ransac_threshold} mm")
    if input_type == "point_cloud":
        descriptors = run_phase2_pcd(frag_id, source, args.ransac_threshold)
    else:
        descriptors = run_phase2(frag_id, source, args.ransac_threshold)

    # ── Phase 3 (optional) ───────────────────────────────────────────────────
    if args.phase3:
        print("\n  ── Phase 3: vision feature extraction ──")
        texture_path = processed_dir / frag_id / f"{frag_id}_texture.png"
        if not texture_path.exists():
            texture_path = processed_dir / frag_id / f"{frag_id}_texture.jpg"
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

    # ── Read scan coverage sidecar early ─────────────────────────────────────
    # Needed here (before Phase 3B) so the UNSCANNED texture mask can be built
    # and applied before the vision API call.  Also used for RANSAC flagging
    # and scan_coverage block below.  scan_coverage.py still works as a
    # standalone re-annotator when needed.
    _sidecar = read_sidecar(frag_id, processed_dir)

    # ── Phase 3B: spatial feature localization ───────────────────────────────
    grid_data: dict | None = None      # set below if Phase 3B classification runs
    feature_texture_paths: dict = {}
    if args.phase3 and descriptors.get("vision"):
        texture_path_3b = processed_dir / frag_id / f"{frag_id}_texture.png"
        if texture_path_3b.exists():
            print("\n  ── Phase 3B: spatial feature localization ──")

            _tex_mask = None
            if _sidecar is not None and input_type != "point_cloud":
                _tex_mask = build_unscanned_texture_mask(source, _sidecar)

            if input_type == "mesh" and not args.grid_legacy:
                # ── Region-based classification (default) ────────────────────
                # Segment the mesh into coherent surface regions (RANSAC
                # planes + fracture clusters), classify each region from its
                # own full-res texture crop (one batched call per vote), then
                # backfill the 16×16 grid so viewer/report stay unchanged.
                _us_idx = (unscanned_face_idx(source, _sidecar)
                           if _sidecar is not None else None)
                _regions = segment_regions(source,
                                           descriptors.get("planarity", []),
                                           unscanned_idx=_us_idx)
                print(f"  Regions: " + ", ".join(
                    f"#{r['region_id']} {r['kind']}"
                    f"({r['area_frac']*100:.0f}%)" for r in _regions))
                _results, _crops = classify_regions(texture_path_3b, source,
                                                    _regions)
                for _res in _results:
                    if _res["label"]:
                        _an = (f" +{len(_res['anomalies'])} anomalies"
                               if _res["anomalies"] else "")
                        print(f"    region #{_res['region_id']} "
                              f"({_res['kind']}, {_res['area_frac']*100:.0f}%)"
                              f" → {_res['label']}{_an}")
                from PIL import Image as _PIL
                _tex_size = _PIL.open(texture_path_3b).size[0]
                _cells = cells_from_regions(_results, _crops, _tex_size,
                                            unscanned_mask=_tex_mask)
                grid_data = {"grid_n": REGION_GRID_N, "cells": _cells,
                             "method": "region"}
                # per-region results into descriptors + planarity linkage
                descriptors["vision"]["regions"] = [
                    {k: r[k] for k in ("region_id", "kind", "plane_index",
                                       "area_frac", "label", "anomalies",
                                       "n_label_votes")}
                    for r in _results
                ]
                for _res in _results:
                    if _res["plane_index"] is not None and _res["label"]:
                        descriptors["planarity"][_res["plane_index"]][
                            "surface_label"] = _res["label"]
            else:
                # ── Legacy grid classification (--grid-legacy / point cloud) ─
                _excl: set = set()
                if _tex_mask is not None:
                    from ai.texture_segmentation import GRID_N as _SEG_GRID_N
                    _excl = _mask_to_excluded_cells(_tex_mask, _SEG_GRID_N)
                    if _excl:
                        print(f"  (UNSCANNED: {len(_excl)} grid cell(s) flagged "
                              f"as reconstructed patch)")
                grid_data = classify_texture_grid(texture_path_3b,
                                                  excluded_cells=_excl)
                for _row, _col in _excl:
                    grid_data["cells"][_row][_col] = None

            descriptors["vision"]["grid_classification"] = grid_data
            feature_texture_paths = build_feature_textures(
                texture_path_3b,
                grid_data["grid_n"],
                grid_data["cells"],
                output_dir,
                frag_id,
            )
        else:
            print("  ⚠ Phase 3B skipped: texture PNG not found")

    # ── Scan coverage: flag RANSAC planes + add block ─────────────────────────
    if _sidecar is not None:
        _planes = descriptors.get("planarity", [])
        if _planes:
            descriptors["planarity"] = flag_unscanned_planes(
                _planes, _sidecar, ANGLE_THRESHOLD_DEG
            )
            _n_unreliable = sum(
                1 for p in descriptors["planarity"] if not p.get("scan_reliable", True)
            )
            print(f"  ✓  Scan coverage: {_n_unreliable}/{len(_planes)} plane(s) flagged as unscanned")
        descriptors["scan_coverage"] = {
            "has_unscanned_face":            _sidecar.get("has_unscanned_face", True),
            "unscanned_avg_normal":          _sidecar["avg_normal"],
            "unscanned_avg_center":          _sidecar.get("avg_center"),
            "unscanned_face_count_original": _sidecar.get("face_count"),
            "angle_threshold_deg":           ANGLE_THRESHOLD_DEG,
            "notes": (
                "Ground-contact face not captured during photogrammetry scanning. "
                "Descriptor values derived from reliable faces only. "
                "Planarity regions within angle_threshold_deg of unscanned normal "
                "are flagged scan_reliable: false and excluded from connection "
                "feasibility assessment."
            ),
            "data_status": "annotated",
        }

    # ── Save ─────────────────────────────────────────────────────────────────
    out_path = save_output(frag_id, descriptors, output_dir)
    print(f"\n  Saved → {out_path.relative_to(REPO_ROOT)}")

    # ── Report ───────────────────────────────────────────────────────────────
    print("  Building viewer data ...", end=" ", flush=True)
    planes = descriptors.get("planarity", [])
    if input_type == "point_cloud":
        viewer_data = build_viewer_data_pcd(source, planes)
    else:
        viewer_data = build_viewer_data(
            source, planes, unscanned_sidecar=_sidecar, grid_data=grid_data,
            texture_path=processed_dir / frag_id / f"{frag_id}_texture.png")
    print(f"{len(viewer_data['points'])} points packed  ({viewer_data['color_mode']} colors)")

    viewer_json_path = output_dir / f"{frag_id}_viewer.json"
    with open(viewer_json_path, "w", encoding="utf-8") as f:
        json.dump(viewer_data, f)

    frag_input_dir = processed_dir / frag_id
    texture_path   = frag_input_dir / f"{frag_id}_texture.png"

    glb_src  = frag_input_dir / f"{frag_id}.glb"
    glb_path = None
    if glb_src.exists():
        glb_copy = output_dir / glb_src.name
        if not glb_copy.exists() or glb_copy.stat().st_mtime < glb_src.stat().st_mtime:
            _shutil.copy2(glb_src, glb_copy)
            print(f"  Copied GLB → {glb_copy.relative_to(REPO_ROOT)}")
        glb_path = glb_copy

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

    index_path = update_inventory(output_dir, highlight_id=frag_id)
    print(f"  Index  → {index_path.relative_to(REPO_ROOT)}")

    if open_browser:
        open_report(index_path)
        print(f"\n  Next step: verify output in the inventory,")
        print(f"  then commit: git commit -m 'data: descriptors {frag_id}'")
        print()


def _discover_fragments(processed_dir: Path) -> list[str]:
    """Return sorted list of fragment IDs that have at least one input file."""
    _EXTENSIONS = {".ply", ".glb", ".obj"}
    ids = []
    if not processed_dir.exists():
        return ids
    for frag_dir in sorted(processed_dir.iterdir()):
        if not frag_dir.is_dir():
            continue
        frag_id = frag_dir.name
        has_input = any((frag_dir / f"{frag_id}{ext}").exists() for ext in _EXTENSIONS)
        if has_input:
            ids.append(frag_id)
    return ids


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Study 2 Descriptor Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 03_src/run_pipeline.py FRAG-S1-FS-001                    # full pipeline
  python 03_src/run_pipeline.py FRAG-S1-FS-001 --geometry-only    # geometry only, no AI
  python 03_src/run_pipeline.py --batch                           # all unanalyzed fragments
  python 03_src/run_pipeline.py --batch --force                   # re-run all fragments
  python 03_src/run_pipeline.py FRAG-S1-FS-002 --force            # re-run one fragment

Fragment ID format: FRAG-S1-{ARCHETYPE}-{###}
  FS=Floor Slab  RS=Roof Slab  BM=Beam  CO=Column
  WL=Load-bearing Wall  WP=Partition Wall  LT=Lintel
  ST=Stair  BL=Balcony  FP=Facade Panel  FD=Foundation  UN=Unidentified
        """
    )
    parser.add_argument(
        "frag_id", nargs="?",
        help="Fragment ID, e.g. FRAG-S1-FS-001. Omit when using --batch."
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Process all fragments in the input directory that have not yet been analyzed."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run even if _geometry.json already exists (useful after clearing cache)."
    )
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
    parser.add_argument(
        "--grid-legacy", action="store_true",
        help="Use the legacy per-cell grid classification instead of "
             "region-based classification."
    )
    args = parser.parse_args()
    args.phase3 = not args.geometry_only

    # ── Validation ────────────────────────────────────────────────────────────
    if args.batch and args.frag_id:
        parser.error("Provide either a fragment ID or --batch, not both.")
    if not args.batch and not args.frag_id and not args.serve:
        parser.error("Provide a fragment ID or use --batch.")

    # ── Serve-only shortcut ───────────────────────────────────────────────────
    if args.serve:
        output_dir = Path(args.output_dir)
        frag_id    = args.frag_id or ""
        report_path = output_dir / f"{frag_id}_report.html"
        index_path  = output_dir / "index.html"
        if frag_id and not report_path.exists():
            print(f"\n  No report found at {report_path}")
            print(f"  Run without --serve first to generate it.")
            sys.exit(1)
        entry = index_path if index_path.exists() else report_path
        print(f"\n  Serving inventory at http://127.0.0.1:PORT/{entry.name} ...")
        if frag_id:
            print(f"  (Click 'Open 3D Report' for {frag_id} from there)")
        open_report(entry)
        return

    processed_dir = Path(args.input_dir)
    output_dir    = Path(args.output_dir)

    # ── Batch mode ────────────────────────────────────────────────────────────
    if args.batch:
        all_frags = _discover_fragments(processed_dir)
        if not all_frags:
            print(f"\n  No fragments found in {processed_dir}")
            sys.exit(0)

        if args.force:
            queue = all_frags
        else:
            queue = [
                fid for fid in all_frags
                if not (output_dir / f"{fid}_geometry.json").exists()
            ]

        if not queue:
            print(f"\n  All {len(all_frags)} fragment(s) already analyzed.")
            print(f"  Use --force to re-run them.")
            sys.exit(0)

        skipped = [f for f in all_frags if f not in queue]
        print(f"\n  Batch mode: {len(queue)} fragment(s) to process"
              + (f"  ({len(skipped)} already done, skipping)" if skipped else ""))
        for fid in skipped:
            print(f"    skip  {fid}  (output exists)")
        for fid in queue:
            print(f"    queue {fid}")

        last_fid = queue[-1]
        for fid in queue:
            run_single(fid, args, processed_dir, output_dir,
                       open_browser=(fid == last_fid))

        print(f"\n  Batch complete. {len(queue)} fragment(s) processed.")
        print(f"  Commit: git add 05_output/ && git commit -m 'data: batch descriptors'")
        print()
        return

    # ── Single fragment ───────────────────────────────────────────────────────
    run_single(args.frag_id, args, processed_dir, output_dir, open_browser=True)


if __name__ == "__main__":
    main()
