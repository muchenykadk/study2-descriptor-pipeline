"""Geometric descriptors: OBB, volume, convexity, planarity (RANSAC), curvature.

Accepts either a trimesh.Trimesh (from OBJ) or an open3d.geometry.PointCloud
(from PLY color point cloud). All public functions handle both input types.

Dependencies: trimesh, open3d, numpy, scipy
Install: pip install trimesh open3d numpy scipy
"""

import numpy as np
import trimesh
import open3d as o3d
from scipy.spatial import ConvexHull


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_o3d_pcd(source, n_samples: int = 50_000) -> o3d.geometry.PointCloud:
    """
    Convert mesh to sampled PointCloud, or subsample an existing PointCloud.
    Preserves per-point colors when present (PLY input).
    """
    if isinstance(source, o3d.geometry.PointCloud):
        n = len(source.points)
        if n > n_samples:
            idx = np.random.choice(n, n_samples, replace=False)
            pcd = source.select_by_index(idx.tolist())
        else:
            pcd = source
        return pcd
    else:
        # trimesh.Trimesh
        points, _ = trimesh.sample.sample_surface(source, n_samples)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        return pcd


def _center_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Translate mesh centroid to origin (non-destructive copy)."""
    m = mesh.copy()
    m.apply_translation(-m.centroid)
    return m


def _center_pcd(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """Translate point cloud centroid to origin (non-destructive)."""
    pts = np.asarray(pcd.points)
    centroid = pts.mean(axis=0)
    out = o3d.geometry.PointCloud(pcd)
    out.points = o3d.utility.Vector3dVector(pts - centroid)
    return out


# ---------------------------------------------------------------------------
# Phase 2 descriptors
# ---------------------------------------------------------------------------

def bounding_descriptors(mesh: trimesh.Trimesh) -> dict:
    """
    Oriented bounding box, volume, convexity ratio, estimated mass.

    Convexity requires a watertight mesh — reported as None for open meshes.
    Volume falls back to convex hull when mesh is open; flagged via volume_source.
    Mass is pseudo until the fragment is physically weighed.
    """
    mesh = _center_mesh(mesh)
    obb = mesh.bounding_box_oriented
    watertight = bool(mesh.is_watertight)
    hull_vol = float(mesh.convex_hull.volume)

    if watertight:
        vol = float(mesh.volume)
        convexity = round(vol / hull_vol, 4) if hull_vol > 0 else None
        vol_source = "mesh"
    else:
        vol = hull_vol          # best available estimate for open mesh
        convexity = None        # meaningless when vol == hull_vol
        vol_source = "convex_hull"

    return {
        "obb_dims_mm": sorted(obb.primitive.extents.tolist(), reverse=True),
        "volume_mm3": round(vol, 1),
        "volume_m3": round(vol * 1e-9, 6),
        "volume_source": vol_source,
        "convexity": convexity,
        "mass_kg_est": round(vol * 1e-9 * 2400.0, 3),
        "mass_data_status": "pseudo",
        "watertight": watertight,
        "data_status": "computed",
    }


def bounding_descriptors_pcd(pcd: o3d.geometry.PointCloud) -> dict:
    """
    Oriented bounding box and mass estimate from a point cloud.

    Volume is convex hull only (no mesh surface available).
    Convexity and watertight are not applicable for point clouds.
    """
    pcd = _center_pcd(pcd)
    pts = np.asarray(pcd.points)

    obb  = pcd.get_oriented_bounding_box()
    dims = sorted(obb.extent.tolist(), reverse=True)

    try:
        hull     = ConvexHull(pts)
        hull_vol = float(hull.volume)
    except Exception:
        hull_vol = 0.0

    return {
        "obb_dims_mm":      [round(d, 1) for d in dims],
        "volume_mm3":       round(hull_vol, 1),
        "volume_m3":        round(hull_vol * 1e-9, 6),
        "volume_source":    "convex_hull",
        "convexity":        None,
        "mass_kg_est":      round(hull_vol * 1e-9 * 2400.0, 3),
        "mass_data_status": "pseudo",
        "watertight":       None,
        "input_type":       "point_cloud",
        "data_status":      "computed",
    }


def planar_regions(
    source,
    distance_threshold_mm: float = 3.0,
    min_inlier_fraction: float = 0.02,
    max_regions: int = 8,
    n_samples: int = 50_000,
) -> list:
    """
    Iterative RANSAC plane segmentation via Open3D.

    Returns list of region dicts sorted by estimated area (largest first).
    Each region includes the plane equation, normal, inlier count,
    estimated area, and fit RMS.

    Parameters
    ----------
    source : trimesh.Trimesh or o3d.geometry.PointCloud
    distance_threshold_mm : float
        Max distance from plane to count as inlier. 3 mm suits photogrammetry
        meshes of demolition concrete at fragment scale.
    min_inlier_fraction : float
        Stop when remaining inliers drop below this fraction of total samples.
    max_regions : int
        Hard cap on extracted planes.
    n_samples : int
        Surface sample count. 50k is sufficient for a ~300 mm fragment.
    """
    # Record the centroid used by centering so the fitted plane equations can
    # be reported back in the ORIGINAL source frame.  Downstream consumers
    # (viewer region overlay, region segmentation, scan-coverage flagging)
    # test original-frame coordinates against plane_abcd; a centred-frame d
    # made every such test miss once meshes stopped being manually moved to
    # the world origin in Blender.
    if isinstance(source, o3d.geometry.PointCloud):
        _centroid = np.asarray(source.points).mean(axis=0)
        source = _center_pcd(source)
    else:
        _centroid = np.asarray(source.centroid, dtype=float)
        source = _center_mesh(source)
    pcd = _to_o3d_pcd(source, n_samples)
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=20, max_nn=30)
    )

    min_inliers = int(n_samples * min_inlier_fraction)
    regions = []
    remaining = pcd

    for _ in range(max_regions):
        if len(remaining.points) < min_inliers:
            break

        plane_model, inliers = remaining.segment_plane(
            distance_threshold=distance_threshold_mm,
            ransac_n=3,
            num_iterations=1000,
        )
        if len(inliers) < min_inliers:
            break

        a, b, c, d = plane_model
        normal = np.array([a, b, c])
        normal /= np.linalg.norm(normal)

        inlier_pcd = remaining.select_by_index(inliers)
        remaining = remaining.select_by_index(inliers, invert=True)

        pts = np.asarray(inlier_pcd.points)
        fit_distances = np.abs(pts @ normal + d)
        rms_mm = float(np.sqrt(np.mean(fit_distances ** 2)))

        # Estimate planar area via 2D convex hull on projected points
        u = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u -= u.dot(normal) * normal
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        pts_2d = np.stack([pts @ u, pts @ v], axis=1)
        try:
            hull = ConvexHull(pts_2d)
            area_m2 = round(hull.volume * 1e-6, 6)  # mm² → m²
        except Exception:
            area_m2 = None

        # Convert the plane equation from the centred fit frame back to the
        # original frame:  n·(x − c) + d = 0  ⇒  n·x + (d − n·c) = 0
        d_world = float(d - normal @ _centroid)
        regions.append({
            "plane_abcd": [round(float(a), 6), round(float(b), 6),
                           round(float(c), 6), round(d_world, 6)],
            "normal_xyz": [round(float(x), 4) for x in normal.tolist()],
            "inlier_count": len(inliers),
            "inlier_fraction": round(len(inliers) / n_samples, 3),
            "area_m2_est": area_m2,
            "fit_rms_mm": round(rms_mm, 3),
            "data_status": "computed",
        })

    regions.sort(key=lambda r: r.get("area_m2_est") or 0, reverse=True)
    return regions


def curvature_stats(
    source,
    radius_mm: float = 20.0,
    n_samples: int = 10_000,
) -> dict:
    """
    Multi-scale curvature via local normal deviation.

    Accepts trimesh.Trimesh or o3d.geometry.PointCloud.
    Speed: uses scipy KDTree.query_ball_point() — one C call finds all
    neighbourhoods at once, vs. Open3D's per-point Python→C++ round-trip.

    Two scales:
      fine   (radius_mm)     — surface texture, roughness of concrete face
      coarse (radius_mm × 3) — overall form curvature of the fragment
    """
    from scipy.spatial import KDTree as _KDTree

    if isinstance(source, o3d.geometry.PointCloud):
        source = _center_pcd(source)
    else:
        source = _center_mesh(source)
    pcd  = _to_o3d_pcd(source, n_samples)

    # Estimate normals once at coarse radius (sufficient for both scales)
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=radius_mm * 3, max_nn=30)
    )
    pts     = np.asarray(pcd.points)
    normals = np.asarray(pcd.normals)

    # Build scipy KDTree once — reused for both radius queries
    tree = _KDTree(pts)

    results = {}
    for label, r in [("fine_mm", radius_mm), ("coarse_mm", radius_mm * 3)]:
        # Batch query: all neighbourhoods found in one C call
        neighbors_list = tree.query_ball_point(pts, r)

        curvs = []
        for idx in neighbors_list:
            if len(idx) < 3:
                continue
            local_n  = normals[idx]
            mean_n   = local_n.mean(axis=0)
            norm_len = np.linalg.norm(mean_n)
            if norm_len < 1e-8:
                continue
            mean_n /= norm_len
            cos_a = np.clip(local_n @ mean_n, -1.0, 1.0)
            curvs.append(float(np.std(np.arccos(cos_a))))

        if curvs:
            c = np.array(curvs)
            results[label] = {
                "mean_rad": round(float(c.mean()), 5),
                "std_rad":  round(float(c.std()),  5),
                "p25_rad":  round(float(np.percentile(c, 25)), 5),
                "p75_rad":  round(float(np.percentile(c, 75)), 5),
                "radius_mm": r,
            }
        else:
            results[label] = {"error": "insufficient points", "radius_mm": r}

    results["data_status"] = "computed"
    return results
