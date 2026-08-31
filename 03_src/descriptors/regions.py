"""
Mesh surface-region segmentation for region-based feature classification.

Groups mesh faces into coherent surface regions:
  1. RANSAC planar regions (from Phase 2 planarity results) — faces within
     distance + normal tolerance of a plane, assigned to the nearest match.
  2. Leftover faces → connected components ("fracture clusters"); components
     below min_cluster_frac are pooled into one residual region.

UNSCANNED (patched) faces are excluded before segmentation.

Units: mesh must be in mm (auto-scaled in load_input).
"""

import numpy as np
import trimesh


def segment_regions(mesh: trimesh.Trimesh,
                    planes: list,
                    unscanned_idx: "np.ndarray | None" = None,
                    dist_mm: float = 8.0,
                    angle_deg: float = 30.0,
                    min_cluster_frac: float = 0.01) -> list:
    """
    Returns a list of region dicts, largest first:
        {
          "region_id":   int,
          "kind":        "plane" | "cluster" | "residual",
          "plane_index": int | None,     # index into `planes` for kind=plane
          "face_idx":    np.ndarray,     # mesh face indices
          "area_frac":   float,          # fraction of analysed surface area
        }
    """
    n_faces   = len(mesh.faces)
    centroids = mesh.vertices[mesh.faces].mean(axis=1)      # (F, 3)
    normals   = mesh.face_normals                           # (F, 3)
    areas     = mesh.area_faces                             # (F,)

    valid = np.ones(n_faces, dtype=bool)
    if unscanned_idx is not None and len(unscanned_idx):
        valid[unscanned_idx] = False

    cos_lim = np.cos(np.radians(angle_deg))

    # ── 1. Assign faces to nearest qualifying RANSAC plane ───────────────────
    best_plane = np.full(n_faces, -1, dtype=int)
    best_dist  = np.full(n_faces, np.inf)
    for pi, plane in enumerate(planes):
        a, b, c, d = plane["plane_abcd"]
        n = np.array([a, b, c], dtype=float)
        n_len = np.linalg.norm(n)
        if n_len < 1e-9:
            continue
        n = n / n_len
        dist  = np.abs(centroids @ n + d / n_len)
        align = np.abs(normals @ n) >= cos_lim
        cand  = valid & align & (dist < dist_mm) & (dist < best_dist)
        best_plane[cand] = pi
        best_dist[cand]  = dist[cand]

    regions = []
    rid = 0
    for pi in range(len(planes)):
        idx = np.where(best_plane == pi)[0]
        if len(idx) == 0:
            continue
        regions.append({"region_id": rid, "kind": "plane",
                        "plane_index": pi, "face_idx": idx})
        rid += 1

    # ── 2. Leftover faces → connected components ─────────────────────────────
    leftover = valid & (best_plane == -1)
    leftover_idx = np.where(leftover)[0]
    if len(leftover_idx):
        # adjacency restricted to leftover faces
        adj  = mesh.face_adjacency                          # (E, 2)
        keep = leftover[adj].all(axis=1)
        comps = trimesh.graph.connected_components(
            adj[keep], nodes=leftover_idx)
        min_faces = max(int(n_faces * min_cluster_frac), 50)
        residual: list = []
        for comp in comps:
            comp = np.asarray(comp)
            if len(comp) >= min_faces:
                regions.append({"region_id": rid, "kind": "cluster",
                                "plane_index": None, "face_idx": comp})
                rid += 1
            else:
                residual.append(comp)
        if residual:
            res = np.concatenate(residual)
            regions.append({"region_id": rid, "kind": "residual",
                            "plane_index": None, "face_idx": res})
            rid += 1

    # ── 3. Area fractions ────────────────────────────────────────────────────
    total_area = float(areas[valid].sum()) or 1.0
    adj_all = mesh.face_adjacency
    for r in regions:
        r["area_frac"] = round(float(areas[r["face_idx"]].sum()) / total_area, 4)
        # Absolute area as well as the fraction. Use rules state their area
        # thresholds in m² (`min_area_m2`), so a rule that evaluates over
        # regions rather than only planar faces needs the same unit to compare
        # against. Mesh is in mm, so mm² → m².
        r["area_m2"] = round(float(areas[r["face_idx"]].sum()) / 1e6, 4)

        # The area of the largest *connected* part of the region.
        #
        # A plane region is every triangle within tolerance of one plane
        # equation, whether or not those triangles touch. On fractured material
        # they mostly do not: measured over this corpus a plane region holds a
        # median of 390 disconnected patches and up to 40,224, because a cast surface survives
        # demolition only as pieces between the breaks. Both `area_m2` above and
        # `area_m2_est` in the Phase 2 record sum or span those pieces, and
        # `area_m2_est`, a convex hull, overstates the real surface by a median
        # factor of 6.05 and up to 43.7.
        #
        # A rule that asks for a bearing face, somewhere to bolt a bracket or
        # rest a plate, needs one continuous piece of surface. That is this
        # number, and it is the honest input to those rules.
        sel = np.zeros(n_faces, dtype=bool)
        sel[r["face_idx"]] = True
        keep_e = sel[adj_all].all(axis=1)
        if keep_e.any():
            comps = trimesh.graph.connected_components(
                adj_all[keep_e], nodes=np.asarray(r["face_idx"]))
            biggest = max((float(areas[np.asarray(c)].sum()) for c in comps),
                          default=0.0)
        else:
            biggest = 0.0
        r["contiguous_area_m2"] = round(biggest / 1e6, 4)
        r["n_patches"] = int(len(comps)) if keep_e.any() else 0

    # ── 4. Merge tiny regions (< min_region_frac) into one residual ─────────
    # Keeps the vision batch small (~10 crops); tiny slivers are unreliable
    # to classify individually anyway.
    min_region_frac = 0.02
    keep  = [r for r in regions if r["area_frac"] >= min_region_frac]
    small = [r for r in regions if r["area_frac"] < min_region_frac]
    if small:
        res_faces = np.concatenate([r["face_idx"] for r in small])
        existing_res = next((r for r in keep if r["kind"] == "residual"), None)
        if existing_res is not None:
            existing_res["face_idx"] = np.concatenate(
                [existing_res["face_idx"], res_faces])
            _a = float(areas[existing_res["face_idx"]].sum())
            existing_res["area_frac"] = round(_a / total_area, 4)
            existing_res["area_m2"]   = round(_a / 1e6, 4)
        else:
            _a = float(areas[res_faces].sum())
            keep.append({"region_id": -1, "kind": "residual",
                         "plane_index": None, "face_idx": res_faces,
                         "area_frac": round(_a / total_area, 4),
                         "area_m2":   round(_a / 1e6, 4)})
    regions = keep

    regions.sort(key=lambda r: -r["area_frac"])
    for new_id, r in enumerate(regions):
        r["region_id"] = new_id
    return regions


def propagate_labels(mesh, face_label: "np.ndarray", n_labels: int = 8,
                     max_rounds: int = 12) -> "tuple[np.ndarray, np.ndarray]":
    """Fill unlabeled faces from their labelled neighbours.

    Regions too fragmented in UV to classify (pooled slivers, thin transition
    zones) leave gaps in the face labelling.  Rather than leave them blank or
    guess a label from a fragmented crop, each unlabeled face adopts the
    dominant label among its adjacent faces, applied iteratively until no
    face changes.  Faces filled this way are reported as inferred, not
    classified, so the distinction stays visible in the record.

    Vectorised over the face-adjacency graph: these meshes carry millions of
    faces, so votes are tallied with bincount rather than per-edge iteration.

    Returns (face_label, inferred_mask).
    """
    face_label = face_label.copy()
    inferred   = np.zeros(len(face_label), dtype=bool)
    adj = mesh.face_adjacency
    if len(adj) == 0:
        return face_label, inferred

    src = np.concatenate([adj[:, 0], adj[:, 1]])
    dst = np.concatenate([adj[:, 1], adj[:, 0]])

    for _ in range(max_rounds):
        gaps = np.where(face_label < 0)[0]
        if len(gaps) == 0:
            break
        gap_pos = np.full(len(face_label), -1, dtype=np.int64)
        gap_pos[gaps] = np.arange(len(gaps))

        m = (face_label[src] >= 0) & (face_label[dst] < 0)
        if not m.any():
            break
        d = gap_pos[dst[m]]
        l = face_label[src[m]]
        counts = np.bincount(d * n_labels + l,
                             minlength=len(gaps) * n_labels
                             ).reshape(len(gaps), n_labels)
        has  = counts.sum(axis=1) > 0
        best = counts.argmax(axis=1)
        face_label[gaps[has]] = best[has]
        inferred[gaps[has]]   = True
    return face_label, inferred



# ── Which face does a non-planar region meet? ─────────────────────────────────

ADJ_MIN_SHARE = 0.50   # a cluster attaches only where one face takes this share
                       # of its shared boundary, so a region straddling several
                       # faces evenly attaches to none


def adjacent_faces(mesh, regions) -> dict:
    """For each non-planar region, the face it meets along most of its boundary.

    Why adjacency and not proximity. An earlier attempt asked whether a cluster's
    triangles *lie on* a plane, by distance to the plane equation, and nothing
    qualified: measured across the corpus the clusters sit 27 to 323 mm from the
    nearest plane at 35° to 141°. That is the correct answer to the wrong
    question. A fracture surface is a different surface from the cast face beside
    it, so it does not lie on it. What it does do is meet it, along a shared
    edge in the mesh.

    A cluster can meet several faces. On FS-010, region 3 touches four. So the
    shared boundary is weighted and a face claims the region only if it takes
    `ADJ_MIN_SHARE` of it; a cluster split evenly across four faces attaches to
    none, which is the honest outcome. On the same fragment the region carrying
    `brick_inclusion` shares 100% of its boundary with one face.

    This records that two surfaces meet. It does not claim the face carries the
    feature: a broken surface meeting a formwork face does not make that face
    broken. The caller keeps the two apart.

    Returns {region_id: {"face": int, "share": float, "faces_touched": int}}
    for regions where one face is dominant.
    """
    import numpy as np

    owner = np.full(len(mesh.faces), -1, dtype=int)
    plane_of = {}
    for k, r in enumerate(regions):
        owner[np.asarray(r["face_idx"], dtype=int)] = k
        plane_of[k] = r["plane_index"]

    adj = mesh.face_adjacency
    if len(adj) == 0:
        return {}
    left, right = owner[adj[:, 0]], owner[adj[:, 1]]

    out = {}
    for k, r in enumerate(regions):
        if r["plane_index"] is not None:
            continue
        # neighbours across every edge where exactly one side is this region
        nb = np.concatenate([right[left == k], left[right == k]])
        nb = nb[(nb >= 0) & (nb != k)]
        if nb.size == 0:
            continue
        counts = {}
        for o in np.unique(nb):
            pi = plane_of.get(int(o))
            if pi is None:
                continue                      # neighbour is another cluster
            counts[pi] = counts.get(pi, 0) + int((nb == o).sum())
        total = sum(counts.values())
        if not total:
            continue
        face, n = max(counts.items(), key=lambda kv: kv[1])
        share = n / total
        if share >= ADJ_MIN_SHARE:
            out[r["region_id"]] = {"face": int(face),
                                   "share": round(float(share), 3),
                                   "faces_touched": len(counts)}
    return out


# ── The patched ground-contact face ──────────────────────────────────────────
#
# Single home for this. It lived in `run_pipeline` and was copied into
# `backfill_regions`, and on 2026-08-27 that copy segmented without it, giving a
# different partition, different region ids, and every migrated value attached
# to the wrong region across all twelve records. Two definitions of the same
# thing is what allowed the two to disagree, so there is now one.

UNSCANNED_ANGLE_DEG = 20.0   # face normal within this angle of sidecar normal
UNSCANNED_Y_MARGIN  = 80.0   # mm above the bottom face still counted
                             # (mesh is auto-scaled to mm in load_input)


def unscanned_face_idx(mesh: trimesh.Trimesh,
                       unscanned_sidecar: dict) -> "np.ndarray | None":
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


def link_adjacent_features(mesh, regions, results, planes) -> int:
    """Record on each face the features read on surfaces that meet it.

    One home for this. It was written twice, in `run_pipeline` and in
    `backfill_regions`, which is how the two came to disagree about whether the
    patched ground-contact face was excluded and put wrong values into every
    record. Same reason `unscanned_face_idx` now lives here.

    `results` supplies the classifications, keyed by `region_id`; `planes` is
    the record's `planarity` list, written in place. Previous output is cleared
    first so re-running cannot accumulate duplicates.

    Nothing here claims the face carries the feature. `features` keeps meaning
    "observed on this face" and no design rule reads `adjacent_features`; a
    broken surface meeting a formwork face does not make that face broken.

    Returns the number of links written.
    """
    for f in planes:
        f.pop("adjacent_features", None)
        f.pop("adjacent_sources", None)

    links = adjacent_faces(mesh, regions)
    by_id = {r.get("region_id"): r for r in results}
    n = 0
    for rid, link in links.items():
        src = by_id.get(rid) or {}
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
        n += 1
    return n
