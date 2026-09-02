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

The full-resolution meshes and textures stay in 05_output/ as the research data.
The site is a viewer, not the dataset.

    python 03_src/build_web.py
    python 03_src/build_web.py --faces 60000 --texture 2048
"""

import argparse
import gc
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "05_output" / "descriptors"
DOCS = REPO_ROOT / "docs"

TARGET_FACES = 45_000     # web-viewer fidelity; the source meshes run to ~1.9 M
TEXTURE_MAX = 1024        # px on the long side


def build_fragment(frag: str, target_faces: int, tex_max: int) -> dict:
    """Write one web-sized GLB + texture + report. Returns a summary dict."""
    import numpy as np
    import trimesh
    import fast_simplification as fs
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
        # UVs are per-vertex. Decimation makes new vertices, so each one takes
        # the UV of the nearest original vertex. Approximate, and indetectable
        # at this face count and texture size.
        UVd = UV[cKDTree(V).query(Vd, k=1)[1]]
    else:
        Vd, Fd, UVd = V, F, UV

    img = Image.open(tex_in).convert("RGB")
    img.thumbnail((tex_max, tex_max), Image.LANCZOS)

    out = trimesh.Trimesh(
        vertices=Vd, faces=Fd, process=False,
        visual=trimesh.visual.TextureVisuals(uv=UVd, image=img))
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


def read_record(frag: str) -> dict:
    """Pull the few fields the index page shows, straight from the record."""
    p = SRC / f"{frag}_geometry.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    b = d.get("bounding", {})
    dims = b.get("obb_dims_mm") or []
    feats = sorted({f["id"] if isinstance(f, dict) else f
                    for r in (d.get("vision", {}).get("regions") or [])
                    for f in (r.get("features") or [])})
    uses = sorted({(u.get("use") if isinstance(u, dict) else u)
                   for p_ in d.get("planarity", [])
                   for u in ((p_.get("procedural") or {}).get("use_suggestions") or [])
                   if u})
    return {
        "dims_mm": [round(x) for x in dims],
        "mass_kg": round(b.get("mass_kg_est", 0)),
        "n_faces": len(d.get("planarity", [])),
        "features": feats,
        "uses": uses,
        "archetype": d.get("archetype_label", ""),
    }


def write_index(rows: list) -> None:
    cards = []
    for r in rows:
        m = r.get("meta", {})
        dims = " × ".join(str(x) for x in m.get("dims_mm", [])) or "—"
        feats = ", ".join(f"<span class=f>{x}</span>" for x in m.get("features", [])) or "<span class=n>none recorded</span>"
        cards.append(f"""
    <a class="card" href="{r['fragment']}_report.html">
      <h2>{r['fragment']}</h2>
      <dl>
        <dt>bounding box</dt><dd>{dims} mm</dd>
        <dt>mass (assumed density)</dt><dd>{m.get('mass_kg','—')} kg</dd>
        <dt>fitted faces</dt><dd>{m.get('n_faces','—')}</dd>
      </dl>
      <p class="feats">{feats}</p>
      <p class="sz">{r.get('glb_mb','?')} MB model · {r.get('faces_out',0):,} faces</p>
    </a>""")

    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fragment Descriptor Records</title>
<style>
 :root {{ --ink:#1a1a2e; --mut:#5b6478; --line:#dfe3ec; --bg:#fbfbfd; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--ink);
        font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif }}
 header {{ max-width:1100px; margin:0 auto; padding:48px 24px 8px }}
 h1 {{ font-size:26px; margin:0 0 6px }}
 .sub {{ color:var(--mut); max-width:70ch; margin:0 0 18px }}
 .warn {{ max-width:70ch; border-left:3px solid #c98a2e; background:#fdf7ec;
          padding:12px 16px; margin:0 0 8px; font-size:13.5px; color:#5a4a2e }}
 main {{ max-width:1100px; margin:0 auto; padding:16px 24px 64px;
         display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)) }}
 .card {{ display:block; text-decoration:none; color:inherit; background:#fff;
          border:1px solid var(--line); border-radius:10px; padding:18px 20px;
          transition:border-color .15s, transform .15s }}
 .card:hover {{ border-color:#9aa8c8; transform:translateY(-2px) }}
 .card h2 {{ font-size:15px; margin:0 0 12px; letter-spacing:.02em }}
 dl {{ display:grid; grid-template-columns:auto 1fr; gap:2px 12px; margin:0 0 12px; font-size:13px }}
 dt {{ color:var(--mut) }} dd {{ margin:0; text-align:right }}
 .feats {{ margin:0 0 10px; font-size:12px; line-height:1.9 }}
 .f {{ background:#eef2fb; border:1px solid #d8e0f2; border-radius:4px;
       padding:2px 7px; margin-right:4px; white-space:nowrap }}
 .n {{ color:var(--mut); font-style:italic }}
 .sz {{ margin:0; font-size:12px; color:var(--mut) }}
 footer {{ max-width:1100px; margin:0 auto; padding:0 24px 64px;
           color:var(--mut); font-size:13px; max-width:70ch }}
 code {{ background:#eef0f5; padding:1px 5px; border-radius:3px; font-size:12.5px }}
</style>
<header>
  <h1>Fragment descriptor records</h1>
  <p class="sub">Twelve demolition concrete fragments from a built urban-furniture
  commission, scanned and characterised into one queryable record each. Every field
  carries the method that produced it and a data status. Open a fragment for the 3D
  viewer, per-region surface features, and the derived actions and design implications.</p>
  <p class="warn"><strong>Surface labels are provisional.</strong> The classifier does not
  exceed a null model that answers the two commonest features and looks at nothing.
  Geometry is computed deterministically and is verified. A <code>rebar_visible</code>
  negative is absent evidence, not evidence of absence, and must not be read as drilling
  guidance. See the repository README for the evaluation.</p>
</header>
<main>{''.join(cards)}
</main>
<footer>
  Models here are decimated to about {TARGET_FACES:,} faces with a {TEXTURE_MAX} px
  texture so they load in a browser. The full-resolution meshes are in the repository
  under <code>05_output/descriptors/</code>. Built by <code>03_src/build_web.py</code>.
</footer>
</html>"""
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
        r["meta"] = read_record(f)
        rows.append(r)
        print(f"  [{i}/{len(frags)}] {f}: {r['faces_in']:,} → {r['faces_out']:,} faces, "
              f"{r['src_mb']} → {r['glb_mb']} MB  ({time.time()-t:.0f}s)")

    write_index(rows)
    total = sum(p.stat().st_size for p in DOCS.rglob("*") if p.is_file())
    print(f"\n  {len(rows)} fragments -> {DOCS.relative_to(REPO_ROOT)}/  "
          f"{total/1e6:.0f} MB total, {time.time()-t0:.0f}s")
    print(f"  index: docs/index.html")


if __name__ == "__main__":
    main()
