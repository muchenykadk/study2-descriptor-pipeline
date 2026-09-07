#!/usr/bin/env python3
"""
Build a static site for GitHub Pages from the per-fragment records.

Why this exists: the reports in 05_output/descriptors/ already run in a browser,
but they cannot be published as they stand, for two independent reasons.

  1. The .glb and _texture.png are tracked by Git LFS, and GitHub Pages does not
     resolve LFS. It serves the pointer file, so the viewer would fetch ~130
     bytes of text instead of a mesh.
  2. The twelve meshes and textures come to about 1.2 GB, against a 1 GB limit
     on a published Pages site, and a single fragment is 109 MB, which is not a
     reasonable download for a web viewer.

So this writes web-sized copies into docs/, which is NOT LFS-tracked (see
docs/.gitattributes). The report HTML is copied unchanged: it references its two
assets by relative filename, so replacing them with smaller files of the same
name is all that is required.

The landing page is the pipeline's own Material Inventory, copied from
05_output/descriptors/index.html. The published site and the local tool show the
same interface; the only edit is to strip absolute local paths out of the
records the page embeds.

The full-resolution meshes and textures stay in 05_output/ as the research data.
The site is a viewer, not the dataset.

    python 03_src/build_web.py
    python 03_src/build_web.py --faces 60000 --texture 2048
"""

import argparse
import gc
import re
import shutil
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "05_output" / "descriptors"
DOCS = REPO_ROOT / "docs"

TARGET_FACES = 45_000     # web-viewer fidelity; the source meshes run to ~5.7 M
TEXTURE_MAX = 1024        # px on the long side
CANDIDATE_TRIS = 12       # nearest source triangles tested per decimated vertex
                          # when rebuilding UVs. Twelve is well past the point
                          # where the winner stops changing.
CENTROID_CHUNK = 500_000  # faces per pass when building the centroid array; the
                          # largest fragment is 5.7 M faces and doing it at once
                          # allocates 407 MB.


def _web_material(src_mat, img, name):
    """Rebuild the source material around the downscaled texture.

    Passing `image=` to TextureVisuals and nothing else makes trimesh invent a
    material, and the invented one is wrong in two ways that compound:

      baseColorFactor defaults to 0.4 grey, and glTF multiplies the texture by it,
      so every texel is rendered at 40% brightness.

      metallicFactor is left unset, and the glTF default for it is 1.0, fully
      metallic. A metal with no environment map to reflect renders near black
      under ordinary directional lights.

    Together they made the published viewer far darker than the local one even
    though the report HTML is byte-identical. Anything the source material states
    is carried over; the fallbacks are the glTF values for a plain matt surface.
    """
    import trimesh

    def take(attr, fallback):
        v = getattr(src_mat, attr, None) if src_mat is not None else None
        return fallback if v is None else v

    return trimesh.visual.material.PBRMaterial(
        name=take("name", None) or f"{name}_material",
        baseColorTexture=img,
        baseColorFactor=take("baseColorFactor", [255, 255, 255, 255]),
        metallicFactor=take("metallicFactor", 0.0),
        roughnessFactor=take("roughnessFactor", 1.0),
        doubleSided=bool(take("doubleSided", False)),
    )


def build_fragment(frag: str, target_faces: int, tex_max: int) -> dict:
    """Write one web-sized GLB + texture + report. Returns a summary dict."""
    import numpy as np
    import trimesh
    import fast_simplification as fs
    from trimesh import triangles as triangles_module
    from trimesh.triangles import points_to_barycentric
    from scipy.spatial import cKDTree
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    glb_in = SRC / f"{frag}.glb"
    tex_in = SRC / f"{frag}_texture.png"
    html_in = SRC / f"{frag}_report.html"
    if not (glb_in.exists() and tex_in.exists() and html_in.exists()):
        return {"fragment": frag, "skipped": "missing source files"}

    mesh = trimesh.load(glb_in, force="mesh", process=False)
    V = np.asarray(mesh.vertices)
    F = np.asarray(mesh.faces)
    UV = np.asarray(mesh.visual.uv)
    n_in = len(F)

    reduction = max(0.0, min(0.99, 1.0 - target_faces / n_in))
    if reduction > 0.01:
        Vd, Fd = fs.simplify(V, F, target_reduction=reduction)
        # UVs are per-vertex, and decimation creates vertices that did not exist
        # before, so their UVs must be derived from the original surface.
        #
        # Taking the nearest original *vertex* is wrong. A new vertex sitting near
        # a UV seam inherits a coordinate from the far side of the atlas, and the
        # triangle then samples unrelated texture. Measured on FRAG-S1-FS-012,
        # that put 5% of vertices more than 0.20 out in a 0..1 UV space and the
        # worst 0.94 out, which shows as smeared facets across the model.
        #
        # Project each new vertex onto the original surface instead, and read the
        # UV barycentrically from the triangle it lands in. Exact wherever the
        # decimated vertex lies on the original surface, which is almost always.
        #
        # trimesh.proximity.closest_point would do this, but it builds an rtree
        # over every triangle, which on the 5.7 M face fragment costs more than
        # ten minutes. A KD-tree of triangle centroids gives the same answer in
        # seconds: take the nearest few triangles as candidates, test those
        # exactly, keep the closest.
        #
        # The centroids are built in chunks and kept in float32, and only the
        # candidate triangles are ever materialised. Building the full V[F] array
        # for this fragment is 407 MB and exhausted memory outright.
        centroids = np.empty((len(F), 3), dtype=np.float32)
        for s in range(0, len(F), CENTROID_CHUNK):
            e = min(s + CENTROID_CHUNK, len(F))
            centroids[s:e] = V[F[s:e]].mean(axis=1)
        tree = cKDTree(centroids, balanced_tree=False, compact_nodes=False)
        cand = tree.query(Vd, k=CANDIDATE_TRIS, workers=-1)[1]
        del centroids, tree

        best_d = np.full(len(Vd), np.inf)
        best_pt = np.zeros((len(Vd), 3))
        best_tid = np.zeros(len(Vd), dtype=np.int64)
        for j in range(cand.shape[1]):
            tid = cand[:, j]
            pt = triangles_module.closest_point(V[F[tid]], Vd)
            d = np.linalg.norm(pt - Vd, axis=1)
            take = d < best_d
            best_d[take], best_pt[take], best_tid[take] = d[take], pt[take], tid[take]
        bary = points_to_barycentric(V[F[best_tid]], best_pt)
        UVd = (UV[F[best_tid]] * bary[:, :, None]).sum(axis=1)
        del cand, best_d, best_pt, best_tid
    else:
        Vd, Fd, UVd = V, F, UV

    img = Image.open(tex_in).convert("RGB")
    img.thumbnail((tex_max, tex_max), Image.LANCZOS)

    out = trimesh.Trimesh(
        vertices=Vd, faces=Fd, process=False,
        visual=trimesh.visual.TextureVisuals(
            uv=UVd, material=_web_material(
                getattr(mesh.visual, "material", None), img, frag)))
    out.export(DOCS / f"{frag}.glb")
    img.save(DOCS / f"{frag}_texture.png", optimize=True)
    shutil.copy2(html_in, DOCS / f"{frag}_report.html")

    # read the counts before freeing; these arrays are large
    n_out = len(Fd)
    del mesh, V, F, UV, Vd, Fd, UVd, out, img
    gc.collect()

    return {
        "fragment": frag,
        "faces_in": n_in,
        "faces_out": n_out,
        "glb_mb": round((DOCS / f"{frag}.glb").stat().st_size / 1e6, 2),
        "src_mb": round(glb_in.stat().st_size / 1e6, 1),
    }


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
    ap.add_argument("--texture", type=int, default=TEXTURE_MAX)
    ap.add_argument("--only", default="", help="one fragment id, for testing")
    args = ap.parse_args()

    DOCS.mkdir(exist_ok=True)
    # Undo the repository-wide LFS rules for this folder. GitHub Pages cannot
    # serve LFS objects, so everything here must be a real file in git.
    (DOCS / ".gitattributes").write_text(
        "# GitHub Pages does not resolve Git LFS, so these must be plain files.\n"
        "*.glb -filter -diff -merge text=auto\n"
        "*.png -filter -diff -merge text=auto\n"
        "*.glb binary\n*.png binary\n", encoding="utf-8")
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
        print(f"  [{i}/{len(frags)}] {f}: {r['faces_in']:,} → {r['faces_out']:,} faces, "
              f"{r['src_mb']} → {r['glb_mb']} MB  ({time.time()-t:.0f}s)")

    publish_inventory()
    total = sum(p.stat().st_size for p in DOCS.rglob("*") if p.is_file())
    print(f"\n  {len(rows)} fragments -> {DOCS.relative_to(REPO_ROOT)}/  "
          f"{total/1e6:.0f} MB total, {time.time()-t0:.0f}s")
    print("  index: docs/index.html")


if __name__ == "__main__":
    main()
