"""Geometric descriptors: OBB, volume, convexity, planarity (RANSAC), curvature.

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

def _to_o3d_pcd(mesh: trimesh.Trimesh, n_samples: int = 50_000) -> o3d.geometry.PointCloud:
    """Sample mesh surface → Open3D PointCloud for RANSAC and curvature."""
    points, _ = trimesh.sample.sample_surface(mesh, n_samples)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    return pcd


def _center_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Translate mesh centroid to origin (non-destructive copy)."""
    m = mesh.copy()
    m.apply_translation(-m.centroid)
    return m


# ---------------------------------------------------------------------------
# Phase 2 descriptors
# ---------------------------------------------------------------------------

def bounding_descriptors(mesh: trimesh.Trimesh) -> dict:
    """
    Oriented bounding box, volume, convexity ratio, estimated mass.

    Mass is pseudo until the fragment is physically weighed;
    flagged mass_data_status: 'pseudo' so real data can replace it.
    """
    mesh = _center_mesh(mesh)
    obb = mesh.bounding_box_oriented
    vol = float(mesh.volume) if mesh.is_watertight else float(mesh.convex_hull.volume)
    hull_vol = float(mesh.convex_hull.volume)

    return {
        "obb_dims_mm": sorted(obb.primitive.extents.tolist(), reverse=True),
        "volume_mm3": round(vol, 1),
        "volume_m3": round(vol * 1e-9, 6),
        "convexity": round(vol / hull_vol, 4) if hull_vol > 0 else None,
        "mass_kg_est": round(vol * 1e-9 * 2400.0, 3),
        "mass_data_status": "pseudo",
        "watertight": bool(mesh.is_watertight),
        "data_status": "computed",
    }


def planar_regions(
    mesh: trimesh.Trimesh,
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
    mesh = _center_mesh(mesh)
    pcd = _to_o3d_pcd(mesh, n_samples)
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

        regions.append({
            "plane_abcd": [round(float(x), 6) for x in plane_model],
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
    mesh: trimesh.Trimesh,
    radius_mm: float = 20.0,
    n_samples: int = 30_000,
) -> dict:
    """
    Multi-scale curvature via local normal deviation (Open3D).

    Two radii separate fine surface texture (radius_mm) from coarse
    fracture topology (radius_mm * 3). Returns percentile summary per scale.
    """
    mesh = _center_mesh(mesh)
    pcd = _to_o3d_pcd(mesh, n_samples)

    results = {}
    for label, r in [("fine_mm", radius_mm), ("coarse_mm", radius_mm * 3)]:
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=r, max_nn=30)
        )
        tree = o3d.geometry.KDTreeFlann(pcd)
        normals = np.asarray(pcd.normals)
        pts = np.asarray(pcd.points)
        curvs = []

        for i in range(len(pts)):
            k, idx, _ = tree.search_radius_vector_3d(pcd.points[i], r)
            if k < 3:
                continue
            local_n = normals[list(idx)]
            mean_n = local_n.mean(axis=0)
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
                "std_rad": round(float(c.std()), 5),
                "p25_rad": round(float(np.percentile(c, 25)), 5),
                "p75_rad": round(float(np.percentile(c, 75)), 5),
                "radius_mm": r,
            }
        else:
            results[label] = {"error": "insufficient points", "radius_mm": r}

    results["data_status"] = "computed"
    return results
