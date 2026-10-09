#!/usr/bin/env python3
"""
Build a static site for GitHub Pages from the per-fragment records.

Why this exists: the reports in 05_output/descriptors/ already run in a browser,
but they cannot be published as they stand, for two independent reasons.

  1. The .glb and _texture.png are tracked by Git LFS, and GitHub Pages does not
     resolve LFS. It serves the pointer file, so the viewer would fetch ~130
     bytes of text instead of a mesh.
  2. The twelve meshes and textures come to about 1.2 GB, against a 1 GB limit
     on a published Pages site, and a single fragment is 205 MB, which is not a
     reasonable download for a web viewer.

So this writes web-sized copies into docs/, which is NOT LFS-tracked (see
docs/.gitattributes). The report HTML is copied unchanged: it references its two
assets by relative filename, so replacing them with smaller files of the same
name is all that is required.

How a web mesh is made. The source mesh cannot simply be decimated and keep its
texture, for two reasons that were both visible on the published site as torn,
faceted models with texture smeared along long triangles:

  The source atlases are fragmented. A fragment has 300 to 3,000 UV islands, and
  FRAG-S1-FS-001 has 172,685, most of them one to four triangles. Every island
  edge is a seam where vertices are split. Decimating the split mesh tears the
  seams open (3,669 open edges on FS-002, a mesh that is watertight once
  welded), and the vertices left along a torn seam pick up texture coordinates
  from the far side of the atlas. No decimator can keep 172,685 islands intact
  at 45,000 faces, so the source atlas cannot be kept at all.

  fast_simplification, used before, also fails on the welded mesh. To reach the
  face target it collapsed FS-002 into triangles spanning up to 81% of the
  fragment, several centimetres off the surface, covering 82% of its area.

So each fragment is welded, decimated with Open3D's quadric decimation (surface
within 0.03% of the bounding box at p99 on FS-002), given a new atlas by
UVAtlas, and its colour and normal maps are baked from the full-resolution
source by projecting every texel onto it. The normal map carries the detail
that decimation removes, so the web model shades like the local one.

The report's Feature Map puts the pipeline's feature textures on the mesh in
place of its colour map, so those are re-baked into the new atlas the same way
and published under their original names. Its fallback for records without
feature textures looks each vertex up in a grid laid over the *source* atlas,
so each web vertex also carries the source-atlas coordinate of the point it
sits on, as the attribute _FEATURE_UV, which the report reads before the uv.

The landing page is the pipeline's own Material Inventory, copied from
05_output/descriptors/index.html. The published site and the local tool show the
same interface; the only edit is to strip absolute local paths out of the
records the page embeds.

The full-resolution meshes and textures stay in 05_output/ as the research data.
The site is a viewer, not the dataset.

    python 03_src/build_web.py
    python 03_src/build_web.py --only FRAG-S1-FS-002
    python 03_src/build_web.py --faces 60000 --texture 4096
"""

import argparse
import gc
import io
import json
import re
import struct
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "05_output" / "descriptors"
DOCS = REPO_ROOT / "docs"

TARGET_FACES = 45_000     # web-viewer fidelity; the source meshes run to ~5.7 M
TEXTURE_PX = 2048         # baked colour and normal maps, square
PREVIEW_PX = 1024         # the source atlas the report shows as "Texture atlas"
FEATURE_PX = 1024         # feature map and per-feature highlights, re-baked
COLOR_QUALITY = 88        # JPEG; a photogrammetry texture is noise to PNG
NORMAL_QUALITY = 92       # JPEG; higher, since block artefacts read as relief
CANDIDATE_TRIS = 12       # nearest source triangles tested per projected point.
                          # Twelve is well past the point where the winner stops
                          # changing; 64 gives identical distances on FS-002.
QUERY_CHUNK = 200_000     # points projected per pass; bounds the candidate arrays
CENTROID_CHUNK = 500_000  # faces per pass when building the centroid array; the
                          # largest fragment is 5.7 M faces and doing it at once
                          # allocates 407 MB.
ATLAS_GUTTER = 4.0        # px between UV islands, at TEXTURE_PX


# ── Source ───────────────────────────────────────────────────────────────────

def _load_source(glb):
    """Vertices, faces, glTF-convention UVs, and the colour and normal images.

    trimesh flips V on load (v_trimesh = 1 - v_gltf). The report's grid lookup
    and the baked atlas are both in glTF convention, so the flip is undone here
    and everything below works in that one convention.

    The images are read from the GLB's own material rather than the loose
    _texture.png, so the bake starts from exactly what the local viewer shows.
    """
    import numpy as np
    import trimesh
    from PIL import Image

    raw = glb.read_bytes()
    json_len = struct.unpack("<I", raw[12:16])[0]
    gltf = json.loads(raw[20:20 + json_len])
    bin_start = 20 + json_len + 8

    def image(ref):
        if ref is None:
            return None
        img = gltf["images"][gltf["textures"][ref["index"]]["source"]]
        view = gltf["bufferViews"][img["bufferView"]]
        o = bin_start + view.get("byteOffset", 0)
        return Image.open(io.BytesIO(raw[o:o + view["byteLength"]])).convert("RGB")

    prim = gltf["meshes"][0]["primitives"][0]
    mat = gltf["materials"][prim.get("material", 0)]
    color = image(mat.get("pbrMetallicRoughness", {}).get("baseColorTexture"))
    normal = image(mat.get("normalTexture"))
    del raw

    mesh = trimesh.load(glb, force="mesh", process=False)
    V = np.asarray(mesh.vertices, dtype=np.float64)
    F = np.asarray(mesh.faces, dtype=np.int64)
    UV = np.asarray(mesh.visual.uv, dtype=np.float64).copy()
    UV[:, 1] = 1.0 - UV[:, 1]
    return V, F, UV, color, normal


def _weld(V, F, tol):
    """Merge the vertices split along UV seams. Returns (V, F, old->new index).

    The source is watertight once welded; split, every seam is an open edge
    that the decimator treats as a boundary and tears.
    """
    import numpy as np
    key = np.round(V / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    Fw = inv[F]
    keep = (Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2])
    return V[first], Fw[keep], inv


def _vertex_normals(V, F):
    """Area-weighted smooth normals."""
    import numpy as np
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return _unit(N)


def _unit(a):
    import numpy as np
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-30)


class _SourceSurface:
    """Closest-point queries onto the full-resolution source surface.

    trimesh.proximity.closest_point would do this, but it builds an rtree over
    every triangle, which on the 5.7 M face fragment costs more than ten
    minutes. A KD-tree of triangle centroids gives the same answer in seconds:
    take the nearest few triangles as candidates, test those exactly, keep the
    closest. Centroids are built in chunks and kept in float32, and only the
    candidate triangles are ever materialised.
    """

    def __init__(self, V, F):
        import numpy as np
        from scipy.spatial import cKDTree
        self.V, self.F = V, F
        cen = np.empty((len(F), 3), np.float32)
        self.fn = np.empty((len(F), 3), np.float32)
        for s in range(0, len(F), CENTROID_CHUNK):
            t = V[F[s:s + CENTROID_CHUNK]]
            cen[s:s + len(t)] = t.mean(axis=1)
            self.fn[s:s + len(t)] = _unit(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]))
        self.tree = cKDTree(cen, balanced_tree=False, compact_nodes=False)

    def project(self, P, N):
        """(source triangle, barycentric, distance) for each point.

        A candidate facing away from the point's normal is passed over unless no
        candidate faces the same way: across a thin edge the opposite sheet can
        be the nearer one, and its texture belongs to the other side.
        """
        import numpy as np
        from trimesh.triangles import closest_point, points_to_barycentric
        tri = np.empty(len(P), np.int64)
        bary = np.empty((len(P), 3))
        dist = np.empty(len(P))
        for s in range(0, len(P), QUERY_CHUNK):
            p, n = P[s:s + QUERY_CHUNK], N[s:s + QUERY_CHUNK]
            cand = self.tree.query(p, k=CANDIDATE_TRIS, workers=-1)[1]
            best = np.full((len(p), 2), np.inf)          # [facing, any]
            pt = np.zeros((len(p), 2, 3))
            tid = np.zeros((len(p), 2), np.int64)
            for j in range(cand.shape[1]):
                t = cand[:, j]
                q = closest_point(self.V[self.F[t]], p)
                d = np.linalg.norm(q - p, axis=1)
                facing = np.einsum("ij,ij->i", self.fn[t], n) > 0.0
                for slot, ok in ((0, facing), (1, True)):
                    take = ok & (d < best[:, slot])
                    best[take, slot], pt[take, slot], tid[take, slot] = d[take], q[take], t[take]
            use = np.where(np.isfinite(best[:, 0]), 0, 1)
            r = np.arange(len(p))
            tri[s:s + len(p)] = tid[r, use]
            dist[s:s + len(p)] = best[r, use]
            bary[s:s + len(p)] = points_to_barycentric(self.V[self.F[tid[r, use]]], pt[r, use])
        return tri, np.clip(bary, 0.0, 1.0), dist


# ── Web mesh ─────────────────────────────────────────────────────────────────

def _decimate(V, F, target_faces):
    import numpy as np
    import open3d as o3d
    m = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(V),
                                  o3d.utility.Vector3iVector(F.astype(np.int32)))
    m = m.simplify_quadric_decimation(target_faces)
    m.remove_degenerate_triangles()
    m.remove_unreferenced_vertices()
    return np.asarray(m.vertices, np.float64), np.asarray(m.triangles, np.int64)


def _unwrap(V, F, tex_px):
    """New atlas with UVAtlas. Returns per-vertex (index into V, uv) and faces.

    UVAtlas gives one uv per face corner; a vertex is split wherever its
    corners disagree, which is along the new seams only. xatlas would do the
    same but its Windows wheel segfaults on any input.
    """
    import numpy as np
    import open3d as o3d
    m = o3d.t.geometry.TriangleMesh()
    m.vertex.positions = o3d.core.Tensor(V.astype(np.float32))
    m.triangle.indices = o3d.core.Tensor(F)
    m.compute_uvatlas(size=tex_px, gutter=ATLAS_GUTTER, max_stretch=1 / 6,
                      parallel_partitions=1)
    corner_uv = m.triangle.texture_uvs.numpy().astype(np.float64).reshape(-1, 2)
    key = np.concatenate([F.reshape(-1, 1).astype(np.float64), corner_uv], axis=1)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return F.reshape(-1)[first], corner_uv[first], inv.reshape(-1, 3).astype(np.int64)


def _rasterize(uv, F, size):
    """Texels whose centre falls inside a triangle: (flat index, triangle, barycentric)."""
    import numpy as np
    t = (uv * size - 0.5)[F]
    lo = np.floor(t.min(axis=1)).astype(np.int64).clip(0, size - 1)
    hi = np.ceil(t.max(axis=1)).astype(np.int64).clip(0, size - 1)
    w, h = hi[:, 0] - lo[:, 0] + 1, hi[:, 1] - lo[:, 1] + 1
    n = w * h
    tri = np.repeat(np.arange(len(F)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    x, y = lo[tri, 0] + k % w[tri], lo[tri, 1] + k // w[tri]
    a = t[tri, 0]
    e1, e2 = t[tri, 1] - a, t[tri, 2] - a
    p = np.stack([x, y], axis=1) - a
    den = e1[:, 0] * e2[:, 1] - e2[:, 0] * e1[:, 1]
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    l1 = (p[:, 0] * e2[:, 1] - e2[:, 0] * p[:, 1]) / den
    l2 = (e1[:, 0] * p[:, 1] - p[:, 0] * e1[:, 1]) / den
    l0 = 1.0 - l1 - l2
    inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
    return (y * size + x)[inside], tri[inside], np.stack([l0, l1, l2], axis=1)[inside]


def _sample(img, uv):
    """Bilinear lookup of an HxWxC float image at glTF-convention uv."""
    import numpy as np
    H, W = img.shape[:2]
    x = (uv[:, 0] % 1.0) * W - 0.5
    y = (uv[:, 1] % 1.0) * H - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    xa, xb = x0.clip(0, W - 1), (x0 + 1).clip(0, W - 1)
    ya, yb = y0.clip(0, H - 1), (y0 + 1).clip(0, H - 1)
    return ((img[ya, xa] * (1 - fx) + img[ya, xb] * fx) * (1 - fy)
            + (img[yb, xa] * (1 - fx) + img[yb, xb] * fx) * fy)


def _shader_frame(V, UV, F, tri, N):
    """Tangent and bitangent as three.js r128 builds them for a normal map.

    The report loads three r128, whose perturbNormal2Arb derives T and B from
    screen-space derivatives of position and uv, takes them perpendicular to the
    shading normal, and divides both by the longer one. Triangle edges stand in
    for the derivatives here: on a front face the two differ by a positive
    factor, which that division removes. Matching the shader exactly is what
    lets a map baked here read back as the normal it was baked from.
    """
    import numpy as np
    f = F[tri]
    e1, e2 = V[f[:, 1]] - V[f[:, 0]], V[f[:, 2]] - V[f[:, 0]]
    d1, d2 = UV[f[:, 1]] - UV[f[:, 0]], UV[f[:, 2]] - UV[f[:, 0]]
    q1perp, q0perp = np.cross(e2, N), np.cross(N, e1)
    T = q1perp * d1[:, :1] + q0perp * d2[:, :1]
    B = q1perp * d1[:, 1:] + q0perp * d2[:, 1:]
    s = 1.0 / np.sqrt(np.maximum(np.maximum((T * T).sum(1), (B * B).sum(1)), 1e-30))
    return T * s[:, None], B * s[:, None]


def _bake(src, V, F, UV, Ns, color, normal, Po, No, UVo, Fo, tex_px):
    """Colour and tangent-space normal maps for the web mesh, from the source.

    Each texel of the new atlas is placed on the web surface, projected onto
    the source, and reads the source texture at the source uv there. Its normal
    is the one the local viewer shades with at that point: the smooth source
    normal perturbed by the source normal map. That is re-expressed in the web
    mesh's frame. GLTFLoader sets normalScale.y to -1, so green is stored
    negated, which is the glTF convention.

    Also returns `transfer`, which carries any other image drawn in the source
    atlas into the new one by the same texel correspondence.
    """
    import numpy as np
    from scipy.ndimage import distance_transform_edt

    lin, tri, bary = _rasterize(UVo, Fo, tex_px)
    P = (Po[Fo[tri]] * bary[:, :, None]).sum(axis=1)
    Nw = _unit((No[Fo[tri]] * bary[:, :, None]).sum(axis=1))
    stri, sbary, dist = src.project(P, Nw)
    suv = (UV[F[stri]] * sbary[:, :, None]).sum(axis=1)

    col = _sample(np.asarray(color, np.float32), suv)

    n = _unit((Ns[F[stri]] * sbary[:, :, None]).sum(axis=1))
    if normal is not None:
        m = _sample(np.asarray(normal, np.float32), suv) / 127.5 - 1.0
        T, B = _shader_frame(V, UV, F, stri, n)
        n = _unit(T * m[:, :1] - B * m[:, 1:2] + n * m[:, 2:3])
    T, B = _shader_frame(Po, UVo, Fo, tri, Nw)
    a = _unit(np.linalg.solve(np.stack([T, B, Nw], axis=2), n[:, :, None])[:, :, 0])
    a[:, 1] *= -1.0

    # Fill the gutters from the nearest baked texel, so neither bilinear
    # filtering nor the coarser mip levels pull in black at island edges.
    covered = np.zeros(tex_px * tex_px, bool)
    covered[lin] = True
    nearest = distance_transform_edt(~covered.reshape(tex_px, tex_px),
                                     return_distances=False, return_indices=True)

    def image(values):
        img = np.zeros((tex_px * tex_px, 3), np.float32)
        img[lin] = values
        img = img.reshape(tex_px, tex_px, 3)[nearest[0], nearest[1]]
        return img.clip(0, 255).astype(np.uint8)

    def transfer(img):
        return image(_sample(np.asarray(img, np.float32), suv))

    return image(col), image((a + 1.0) * 127.5), dist, transfer


def _jpeg(arr, quality):
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=quality, optimize=True, subsampling=0)
    return buf.getvalue()


def _write_glb(path, name, P, N, UV, FUV, F, color_jpg, normal_jpg):
    """One mesh, one material, two embedded JPEGs, written field by field.

    Written directly rather than through trimesh, whose exporter invents what it
    is not told: an earlier version of this script got a baseColorFactor of 0.4
    grey and, with metallicFactor left unset, glTF's default of fully metallic,
    and the published viewer rendered near black. Every value here is explicit.
    It also drops vertex normals unless they happen to be cached, and
    GLTFLoader then shades flat, which shows as a facet on every triangle.
    """
    import numpy as np
    blobs, views, accessors = [], [], []

    def view(data, target=None):
        v = {"buffer": 0, "byteOffset": sum(len(b) for b in blobs), "byteLength": len(data)}
        if target:
            v["target"] = target
        blobs.append(data + b"\0" * (-len(data) % 4))
        views.append(v)
        return len(views) - 1

    def accessor(arr, component, kind, target, bounds=False):
        a = {"bufferView": view(arr.tobytes(), target), "componentType": component,
             "count": len(arr), "type": kind}
        if bounds:
            a["min"], a["max"] = arr.min(axis=0).tolist(), arr.max(axis=0).tolist()
        accessors.append(a)
        return len(accessors) - 1

    def f32(a):
        return np.ascontiguousarray(a, np.float32)

    ARRAY, ELEMENTS, FLOAT = 34962, 34963, 5126
    attributes = {
        "POSITION": accessor(f32(P), FLOAT, "VEC3", ARRAY, bounds=True),
        "NORMAL": accessor(f32(N), FLOAT, "VEC3", ARRAY),
        "TEXCOORD_0": accessor(f32(UV), FLOAT, "VEC2", ARRAY),
        # Source-atlas coordinate for the report's feature grid; GLTFLoader
        # exposes it as geometry.attributes._feature_uv.
        "_FEATURE_UV": accessor(f32(FUV), FLOAT, "VEC2", ARRAY),
    }
    small = len(P) < 65536
    idx = np.ascontiguousarray(F.ravel(), np.uint16 if small else np.uint32)
    indices = accessor(idx, 5123 if small else 5125, "SCALAR", ELEMENTS)
    gltf = {
        "asset": {"version": "2.0", "generator": "Study2 03_src/build_web.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": [
            {"attributes": attributes, "indices": indices, "material": 0}]}],
        "materials": [{
            "name": f"{name}_web",
            "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                     "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                                     "metallicFactor": 0.0, "roughnessFactor": 1.0},
            "normalTexture": {"index": 1},
            "doubleSided": False,
        }],
        # linear / trilinear, clamp to edge
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"bufferView": view(color_jpg), "mimeType": "image/jpeg"},
                   {"bufferView": view(normal_jpg), "mimeType": "image/jpeg"}],
        "textures": [{"sampler": 0, "source": 0}, {"sampler": 0, "source": 1}],
        "accessors": accessors,
        "bufferViews": views,
    }
    binary = b"".join(blobs)
    gltf["buffers"] = [{"byteLength": len(binary)}]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    path.write_bytes(
        struct.pack("<4sII", b"glTF", 2, 28 + len(js) + len(binary))
        + struct.pack("<I4s", len(js), b"JSON") + js
        + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def build_fragment(frag: str, target_faces: int, tex_px: int) -> dict:
    """Write one web GLB, its feature textures, atlas preview and report."""
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    glb_in = SRC / f"{frag}.glb"
    tex_in = SRC / f"{frag}_texture.png"
    html_in = SRC / f"{frag}_report.html"
    if not (glb_in.exists() and tex_in.exists() and html_in.exists()):
        return {"fragment": frag, "skipped": "missing source files"}

    V, F, UV, color, normal = _load_source(glb_in)
    if color is None:
        return {"fragment": frag, "skipped": "source GLB has no base colour texture"}
    size = float(np.ptp(V, axis=0).max())

    Vw, Fw, weld_map = _weld(V, F, size * 1e-6)
    Vd, Fd = _decimate(Vw, Fw, target_faces)
    Nd = _vertex_normals(Vd, Fd)
    vmap, UVo, Fo = _unwrap(Vd, Fd, tex_px)
    Po, No = Vd[vmap], Nd[vmap]

    src = _SourceSurface(V, F)
    # Smooth source normals from the welded mesh, so they are continuous across
    # the source seams, mapped back to the split vertices the faces index.
    Ns = _vertex_normals(Vw, Fw)[weld_map]
    del Vw, Fw, weld_map

    vtri, vbary, _ = src.project(Po, No)
    FUV = (UV[F[vtri]] * vbary[:, :, None]).sum(axis=1)

    col, nrm, dist, transfer = _bake(src, V, F, UV, Ns, color, normal,
                                     Po, No, UVo, Fo, tex_px)
    _write_glb(DOCS / f"{frag}.glb", frag, Po, No, UVo, FUV, Fo,
               _jpeg(col, COLOR_QUALITY), _jpeg(nrm, NORMAL_QUALITY))

    # The report's Feature Map swaps these onto the mesh, so they must be in the
    # atlas of the GLB beside them. Same filenames, so the copied report finds
    # them. Highlights for features no longer detected are removed first, as
    # build_feature_textures() does for the source set.
    for stale in DOCS.glob(f"{frag}_feat_*.png"):
        stale.unlink()
    n_feat = 0
    for p in [SRC / f"{frag}_feature_map.png", *sorted(SRC.glob(f"{frag}_feat_*.png"))]:
        if p.exists():
            img = Image.fromarray(transfer(Image.open(p).convert("RGB")))
            img.resize((FEATURE_PX, FEATURE_PX), Image.LANCZOS).save(DOCS / p.name, optimize=True)
            n_feat += 1

    preview = Image.open(tex_in).convert("RGB")
    preview.thumbnail((PREVIEW_PX, PREVIEW_PX), Image.LANCZOS)
    preview.save(DOCS / f"{frag}_texture.png", optimize=True)
    html_out = DOCS / f"{frag}_report.html"
    html_out.write_bytes(html_in.read_bytes())

    summary = {
        "fragment": frag,
        "feature_textures": n_feat,
        "faces_in": len(F),
        "faces_out": len(Fo),
        # how far the web surface sits from the source, as a share of its size
        "dev_p99": float(np.percentile(dist, 99)) / size,
        "glb_mb": round((DOCS / f"{frag}.glb").stat().st_size / 1e6, 2),
        "src_mb": round(glb_in.stat().st_size / 1e6, 1),
    }
    del V, F, UV, Ns, src, Vd, Fd, Nd, Po, No, UVo, Fo, FUV, col, nrm, dist, color, normal
    del transfer
    gc.collect()
    return summary


def publish_inventory() -> None:
    """Publish the pipeline's own inventory page as the site landing page.

    The inventory that report.update_inventory() writes is the interface this
    project actually has: the fragment table, the filters, and the record fields.
    An earlier version of this function generated a substitute card grid instead,
    which silently dropped all of that and shipped a different, poorer page than
    the one running locally. The site must show the same interface as the tool.

    The page is published as generated. The only edit is to the embedded record
    paths, below.
    """
    src = SRC / "index.html"
    if not src.exists():
        raise SystemExit(
            f"\n  {src.relative_to(REPO_ROOT)} does not exist. Run the pipeline, or\n"
            "  python 03_src/refresh_factors.py --reports-only, to generate it.\n")

    html = src.read_text(encoding="utf-8")

    # The inventory embeds the records verbatim, and each region record carries an
    # `image_path` written as an absolute path on the machine that ran the pipeline.
    # That would publish the author's home directory on a public page. Cut the prefix
    # so the path reads from the repository root, which is what a reader can act on.
    # The records themselves still hold the absolute form; fixing that belongs where
    # image_path is written, not here.
    html, n = re.subn(r'[A-Za-z]:\\{1,2}[^"]*?Study2_Descriptor_Pipeline\\{1,2}', "", html)
    if n:
        print(f"  stripped {n} absolute local path(s) from the inventory")

    (DOCS / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--faces", type=int, default=TARGET_FACES)
    ap.add_argument("--texture", type=int, default=TEXTURE_PX,
                    help="side of the baked colour and normal maps, px")
    ap.add_argument("--only", default="", help="one fragment id, for testing")
    args = ap.parse_args()

    DOCS.mkdir(exist_ok=True)
    # Undo the repository-wide LFS rules for this folder. GitHub Pages cannot
    # serve LFS objects, so everything here must be a real file in git.
    (DOCS / ".gitattributes").write_text(
        "# GitHub Pages does not resolve Git LFS, so these must be plain files.\n"
        "*.glb -filter -diff -merge text=auto\n"
        "*.png -filter -diff -merge text=auto\n"
        "*.glb binary\n*.png binary\n", encoding="utf-8", newline="\n")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    frags = ([args.only] if args.only else
             sorted(p.stem for p in SRC.glob("FRAG-*.glb")))
    rows, t0 = [], time.time()
    for i, f in enumerate(frags, 1):
        t = time.time()
        r = build_fragment(f, args.faces, args.texture)
        if "skipped" in r:
            print(f"  [{i}/{len(frags)}] {f}: {r['skipped']}")
            continue
        rows.append(r)
        print(f"  [{i}/{len(frags)}] {f}: {r['faces_in']:,} -> {r['faces_out']:,} faces, "
              f"{r['src_mb']} -> {r['glb_mb']} MB, off-surface p99 "
              f"{100 * r['dev_p99']:.3f}% of size, {r['feature_textures']} feature "
              f"texture(s)  ({time.time()-t:.0f}s)", flush=True)

    publish_inventory()
    total = sum(p.stat().st_size for p in DOCS.rglob("*") if p.is_file())
    print(f"\n  {len(rows)} fragments -> {DOCS.relative_to(REPO_ROOT)}/  "
          f"{total/1e6:.0f} MB total, {time.time()-t0:.0f}s")
    print("  index: docs/index.html")


if __name__ == "__main__":
    main()
