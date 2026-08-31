#!/usr/bin/env python3
"""
Pre-flight checks on a fragment's Blender export, before the pipeline spends time
or API credit on it.

Every check here exists because something got through without it:

    face count       FRAG-S1-FS-003 exported at 3,016 faces, roughly a thousandth
                     of what a mesh its size should carry. Its planes matched
                     under 4% of its geometry and it produced no surface labels
                     at all. Nothing downstream reported a problem.
    UNSCANNED        Five of seven fragments were exported without the vertex
                     group. The underside then bakes as a flat wash, which the
                     smear gate cannot see and which RANSAC reads as the
                     cleanest plane on the fragment.
    sidecar normal   The sidecar is Blender Z-up, the GLB is Y-up. If the
                     conversion does not come out near-vertical the filter
                     silently matches nothing.
    volume source    GLB export splits vertices along UV seams, so a solid mesh
                     reports as open and the volume falls back to the convex
                     hull, which wraps every concave break face and overstates
                     mass by 17 to 90%.
    duplicate        FS-005 and FS-006 are the same mesh exported twice. Identical
                     face count and volume, different files.
    identity         The export's oriented box against the one already on record.
                     FRAG_ID is hand-edited in the Blender script and nothing
                     downstream can verify it, so a bake under the wrong name is
                     otherwise invisible: it has already put FRAG007 into FS-003's
                     folder and a 1630 mm slab into FS-002's.
    texel density    Pixels of atlas per millimetre of real surface. Below about
                     0.5 the bake averages small islands to one colour and the
                     margin bleeds each into a flat diamond.
    bake margin      Without margin_type EXTEND the atlas is pure black right up
                     to each island edge.

Run standalone to check an export before committing to it:

    python 03_src/preflight.py FRAG-S1-FS-007
    python 03_src/preflight.py --all

`run_pipeline.py` calls `preflight()` automatically at the start of every run and
stops on a FAIL. Use `--skip-preflight` to override, which you should only need
when deliberately processing a known-bad mesh.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPO_ROOT / "01_input" / "meshes" / "processed"
RECORD_DIR = REPO_ROOT / "05_output" / "descriptors"

VOXEL_SIZE_M      = 0.002   # must match BAKE_MARGIN's neighbour in bake_texture_v2.py
FACE_COUNT_MIN    = 0.20    # fraction of expected below which the remesh is broken
UNSCANNED_ANGLE   = 20.0
UNSCANNED_Y_MARGIN = 80.0
FLAT_SD_MAX       = 3.0


class Finding:
    __slots__ = ("level", "title", "detail")

    def __init__(self, level: str, title: str, detail: str = ""):
        self.level, self.title, self.detail = level, title, detail

    def __str__(self) -> str:
        mark = {"fail": "  ✗", "warn": "  !", "ok": "  ✓"}[self.level]
        line = f"{mark}  {self.title}"
        return f"{line}\n       {self.detail}" if self.detail else line


def _autoscale(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    if float(max(mesh.bounding_box.primitive.extents)) < 10.0:
        mesh.apply_scale(1000.0)
    return mesh


def _check_mesh(mesh: trimesh.Trimesh, out: list) -> None:
    dims = sorted(mesh.bounding_box_oriented.primitive.extents.tolist(), reverse=True)
    dim_s = " x ".join(f"{d:.0f}" for d in dims)

    across   = (max(dims) / 1000.0) / VOXEL_SIZE_M
    expected = 3.0 * across ** 2          # calibrated on FS-006: 831 across → 2.1M faces
    ratio    = len(mesh.faces) / max(expected, 1.0)
    msg = (f"{len(mesh.faces):,} faces, {ratio:.0%} of the ~{int(expected):,} expected "
           f"for a {dim_s} mm mesh at {VOXEL_SIZE_M * 1000:.0f} mm voxels")
    if ratio < FACE_COUNT_MIN:
        out.append(Finding("fail", "Remesh far too coarse", msg +
                           ". Almost always a unit mismatch in Blender: Voxel Size is in "
                           "scene units, so 0.002 means 2 mm only if the object measures "
                           "~1.6 units, not ~1600. Re-export before going further."))
    else:
        out.append(Finding("ok", "Remesh resolution", msg))

    has_uv = getattr(mesh.visual, "uv", None) is not None
    out.append(Finding("ok" if has_uv else "fail", "UV coordinates",
                       "present" if has_uv else
                       "missing. The texture cannot be mapped to faces; re-export with "
                       "Smart UV Project applied to the remesh."))

    mesh.merge_vertices()
    hull = float(mesh.convex_hull.volume)
    mv   = abs(float(mesh.volume))
    if hull > 0 and mesh.is_winding_consistent and 0.2 <= mv / hull <= 1.0:
        out.append(Finding("ok", "Volume from the mesh",
                           f"{mv * 1e-9:.4f} m3, {mv * 1e-9 * 2500:.0f} kg. The convex hull "
                           f"would have said {hull * 1e-9 * 2500:.0f} kg, "
                           f"{hull / mv - 1:.0%} high."))
    else:
        out.append(Finding("warn", "Volume falls back to the convex hull",
                           f"{hull * 1e-9:.4f} m3, {hull * 1e-9 * 2500:.0f} kg. The hull "
                           f"wraps every concave break face, so mass is overstated. "
                           f"Check the mesh is closed in Blender."))


# Texel density the atlas resolves, in pixels per millimetre of real surface.
# This, not the atlas resolution, is what decides whether a feature is visible.
# Coarse aggregate runs 8 to 32 mm and needs several pixels across to read as a
# particle; a crack is a few millimetres wide and needs the same. Measured on
# FS-002 before the fix: 0.24 px/mm, at which every island of a few faces
# averaged to one colour and the bake margin bled each into a flat diamond.
# After the fix: 1.57 px/mm. The Scaniverse source for that fragment resolves
# 2.75 px/mm, which is the ceiling no bake setting can pass.
TEXEL_PX_PER_MM_FAIL = 0.50
TEXEL_PX_PER_MM_WARN = 1.00


def _check_texel_density(mesh: trimesh.Trimesh, tex_path: Path, out: list) -> None:
    """How much atlas each square millimetre of surface actually gets.

    Two settings starve this independently, and neither shows up in the atlas
    resolution alone: BAKE_RES, and the Smart UV Project island margin, which is
    a fraction of the sheet rather than a pixel count. At island_margin=0.02
    only 20% of the atlas carried any UV at all, so a 4096 sheet would still
    have delivered the texel density of a 1830 one.
    """
    uv = getattr(mesh.visual, "uv", None)
    if uv is None or not tex_path.exists():
        return
    try:
        with Image.open(tex_path) as im:
            w, h = im.size
    except OSError:
        return

    t = np.asarray(uv)[mesh.faces]
    e1, e2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    uv_frac = float(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum() * 0.5)

    area_mm2 = float(mesh.area)          # mesh is already in millimetres here
    if area_mm2 <= 0:
        return
    px_per_mm = float(np.sqrt(uv_frac * w * h / area_mm2))
    msg = (f"{px_per_mm:.2f} px per mm of surface: a {w}x{h} atlas of which "
           f"{uv_frac:.0%} carries UV, over {area_mm2 * 1e-6:.2f} m2 "
           f"({uv_frac * w * h / max(len(mesh.faces), 1):.1f} px per face)")
    if px_per_mm < TEXEL_PX_PER_MM_FAIL:
        out.append(Finding("fail", "Texture is starved of texels", msg +
                           ". Islands of a few faces average to a single colour and the "
                           "bake margin bleeds each into a flat patch, which is the "
                           "diamond field seen on FS-001 and FS-002. In "
                           "bake_texture_v2.py set BAKE_RES = 4096 and "
                           "smart_project(island_margin=0.002), then re-bake."))
    elif px_per_mm < TEXEL_PX_PER_MM_WARN:
        out.append(Finding("warn", "Texture is thin on texels", msg +
                           ". Aggregate will read, a crack of a few millimetres may not."))
    else:
        out.append(Finding("ok", "Texel density", msg))


def _check_texture(tex_path: Path, out: list) -> None:
    if not tex_path.exists():
        out.append(Finding("fail", "Texture missing", str(tex_path)))
        return
    from scipy import ndimage
    a = np.array(Image.open(tex_path).convert("RGB"))
    dark = a.max(axis=2) < 12
    out.append(Finding("ok", "Texture", f"{a.shape[1]}x{a.shape[0]}, "
                                        f"{dark.mean():.0%} of the atlas is empty"))

    # Bake margin: with margin_type EXTEND, colour is bled outward and black no
    # longer sits hard against island edges.
    if dark.any() and not dark.all():
        d = ndimage.distance_transform_edt(dark)
        hug = ((d > 0) & (d <= 1)).sum() / dark.sum()
        if hug > 0.03:
            out.append(Finding("warn", "Bake margin looks unset",
                               f"{hug:.1%} of empty atlas sits within 1 px of texture. "
                               f"Set Margin 32 px, Type Extend. Cosmetic only: the empty "
                               f"atlas is masked out before the vision model sees it."))
        else:
            out.append(Finding("ok", "Bake margin", f"colour bled outward, only {hug:.1%} of "
                                                    f"empty atlas hugs an island edge"))

    # Featureless fill: an unmarked unscanned face bakes as an even wash.
    g   = a.astype(float).mean(axis=2)
    lit = a.max(axis=2) >= 12
    mu  = ndimage.uniform_filter(g, 15)
    sd  = np.sqrt(np.maximum(ndimage.uniform_filter(g * g, 15) - mu * mu, 0.0))
    flat = ndimage.binary_opening((sd < FLAT_SD_MAX) & lit, np.ones((9, 9)))
    flat = ndimage.binary_closing(flat, np.ones((21, 21)))
    share = flat.sum() / max(lit.sum(), 1)
    if share > 0.02:
        out.append(Finding("warn", "Featureless patch in the texture",
                           f"{share:.1%} of the textured atlas carries no surface detail. "
                           f"Usually the underside, baked flat because the scan never saw "
                           f"it. Harmless if UNSCANNED is marked; otherwise it will be "
                           f"classified as real surface."))


def _check_sidecar(mesh: trimesh.Trimesh, sidecar: Path, out: list) -> None:
    if not sidecar.exists():
        out.append(Finding("warn", "UNSCANNED not marked",
                           "No _scan_coverage.json. The ground-contact face will be treated "
                           "as measured surface: RANSAC sees a manually filled hole as the "
                           "flattest plane on the fragment and the design factors may "
                           "propose it as a bench top. Mark the vertex group in Blender and "
                           "re-run bake_texture_v2.py."))
        return
    sc = json.loads(sidecar.read_text(encoding="utf-8"))
    if not sc.get("has_unscanned_face"):
        out.append(Finding("warn", "Sidecar present but empty",
                           "has_unscanned_face is false."))
        return
    if not sc.get("face_count"):
        out.append(Finding("fail", "UNSCANNED vertex group was empty",
                           "The sidecar records face_count 0, so the group existed but "
                           "nothing was assigned to it, and the stored normal is the "
                           "average of nothing. Re-mark the group in Blender: select the "
                           "filled patch, then Object Data > Vertex Groups > Assign. The "
                           "Assign button is the step that is easy to miss."))
        return

    bx, by, bz = sc["avg_normal"]
    u = np.array([bx, bz, -by], dtype=float)      # Blender Z-up → glTF Y-up
    u /= np.linalg.norm(u)
    # unscanned_face_idx() matches on |cos|, so either sign is usable: it takes
    # every near-vertical face and then keeps the lowest ones. Only a normal
    # that is not vertical at all is a real problem.
    if abs(u[1]) < 0.8:
        out.append(Finding("fail", "Sidecar normal is not vertical",
                           f"converts to {np.round(u, 3).tolist()} in glTF space. A "
                           f"ground-contact face should be near-vertical in Y. The filter "
                           f"will match the wrong faces or nothing at all, which usually "
                           f"means the sidecar and the mesh are from different exports."))
        return
    if u[1] > 0:
        out.append(Finding("warn", "Sidecar normal points up",
                           f"converts to {np.round(u, 3).tolist()}, +Y rather than -Y. "
                           f"Harmless, the filter matches on absolute angle and then keeps "
                           f"the lowest faces, but it means the patch normal was stored "
                           f"flipped relative to the other fragments."))

    cos = np.abs(mesh.face_normals @ u)
    nm  = cos >= np.cos(np.radians(UNSCANNED_ANGLE))
    if not nm.any():
        out.append(Finding("fail", "UNSCANNED matches no faces",
                           f"no face lies within {UNSCANNED_ANGLE:.0f} deg of the sidecar "
                           f"normal."))
        return
    fc = mesh.vertices[mesh.faces].mean(axis=1)
    pos = fc[:, 1] < (float(fc[nm][:, 1].min()) + UNSCANNED_Y_MARGIN)
    idx = np.where(nm & pos)[0]
    area = mesh.area_faces[idx].sum() / max(mesh.area, 1e-9)
    lvl = "ok" if 0.02 <= area <= 0.60 else "warn"
    out.append(Finding(lvl, "UNSCANNED face located",
                       f"{len(idx):,} faces, {area:.1%} of surface area "
                       f"({sc.get('face_count')} marked in Blender before the remesh)"
                       + ("" if lvl == "ok" else
                          ". That share looks off for a ground-contact face; check the "
                          "vertex group covers the patch and only the patch.")))


SIG_CACHE = RECORD_DIR / "mesh_signatures.json"


def _signature(mesh: trimesh.Trimesh) -> list:
    """Cheap identity for a mesh: face count and volume to the cubic millimetre.

    Two exports of the same physical fragment differ byte for byte, because each
    Smart UV Project run splits a different number of seam vertices, but they
    agree exactly on both of these.
    """
    return [len(mesh.faces), round(abs(float(mesh.volume)), 3)]


def _check_duplicate(frag_id: str, mesh: trimesh.Trimesh, out: list) -> None:
    """Catch one mesh living under two fragment ids.

    FS-005 and FS-006 were the same mesh exported twice and nothing noticed for
    weeks.  FRAG007 was then exported into FS-003's folder because FRAG_ID was
    left unchanged in the Blender script, overwriting a different fragment's
    export.  Both are invisible to every other check.
    """
    sig = _signature(mesh)
    try:
        cache = json.loads(SIG_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}

    for other, other_sig in cache.items():
        if other != frag_id and other_sig == sig:
            out.append(Finding("warn", "Same mesh as another fragment",
                               f"identical face count ({sig[0]:,}) and volume to {other}. "
                               f"Either this is the same physical piece exported twice, or "
                               f"FRAG_ID was left unchanged in the Blender script and this "
                               f"export overwrote the wrong folder."))
            break

    cache[frag_id] = sig
    try:
        SIG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SIG_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        pass


# A re-export of the same physical fragment moves its measured dimensions a
# little: a different voxel alignment, a hole closed by hand, a stray face
# deleted. It does not move them by half. Calibrated against FS-006 re-exported
# twice, whose oriented box agreed to within 0.1%.
IDENTITY_TOL = 0.15


def _check_identity(frag_id: str, mesh: trimesh.Trimesh, out: list) -> None:
    """Is this export still the same physical piece the record was built from?

    FRAG_ID is hand-edited in the Blender script before every bake, and it is the
    one input nothing downstream can verify. Leaving it unchanged has already
    written FRAG007 into FS-003's folder, and written a 1630 mm slab into
    FS-002's, whose own scan measures 858 mm. Both exports were internally
    perfect: correct topology, clean UVs, valid sidecar. Every other check
    passes, because every other check asks whether the mesh is good rather than
    whether it is the right mesh.

    The oriented bounding box is the cheapest thing that distinguishes two
    fragments, and unlike the volume signature it survives a re-remesh.
    """
    rec = RECORD_DIR / f"{frag_id}_geometry.json"
    if not rec.exists():
        return
    try:
        prev = json.loads(rec.read_text(encoding="utf-8"))["bounding"]["obb_dims_mm"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return

    now = sorted(mesh.bounding_box_oriented.primitive.extents.tolist(), reverse=True)
    prev = sorted(float(d) for d in prev)[::-1]
    if len(prev) != 3:
        return
    drift = max(abs(n - p) / max(p, 1.0) for n, p in zip(now, prev))
    fmt = lambda d: " x ".join(f"{v:.0f}" for v in d)
    if drift > IDENTITY_TOL:
        out.append(Finding("warn", "Export does not match the stored record",
                           f"{fmt(now)} mm now, {fmt(prev)} mm on record, "
                           f"{drift:.0%} apart on the worst axis. Either this is a "
                           f"different fragment baked under {frag_id}'s name, which means "
                           f"FRAG_ID was left unchanged in bake_texture_v2.py, or the "
                           f"piece was re-scanned. If it was re-scanned, say so and this "
                           f"check will pass once the record is rebuilt."))
    else:
        out.append(Finding("ok", "Matches the stored record",
                           f"{fmt(now)} mm, within {drift:.0%} of {fmt(prev)} mm"))


def preflight(frag_id: str, mesh: trimesh.Trimesh | None = None) -> list:
    """Run every check for one fragment. Returns findings, worst first."""
    out: list = []
    folder = INPUT_DIR / frag_id
    glb = folder / f"{frag_id}.glb"

    if mesh is None:
        if not glb.exists():
            return [Finding("fail", "Mesh missing", str(glb))]
        mesh = _autoscale(trimesh.load(glb, force="mesh", process=False))

    _check_mesh(mesh, out)
    _check_texel_density(mesh, folder / f"{frag_id}_texture.png", out)
    _check_texture(folder / f"{frag_id}_texture.png", out)
    _check_sidecar(mesh, folder / f"{frag_id}_scan_coverage.json", out)
    _check_identity(frag_id, mesh, out)
    _check_duplicate(frag_id, mesh, out)

    rank = {"fail": 0, "warn": 1, "ok": 2}
    return sorted(out, key=lambda f: rank[f.level])


def report(frag_id: str, findings: list) -> bool:
    """Print findings. Returns True if any check failed."""
    failed = [f for f in findings if f.level == "fail"]
    warned = [f for f in findings if f.level == "warn"]
    print(f"\n  ── Pre-flight: {frag_id} ─────────────────────────────")
    for f in findings:
        print(f)
    if failed:
        print(f"\n  {len(failed)} check(s) failed. Fix the export before processing.\n")
    elif warned:
        print(f"\n  {len(warned)} warning(s). Processing can continue.\n")
    else:
        print("\n  All checks passed.\n")
    return bool(failed)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fragment_id", nargs="?")
    ap.add_argument("--all", action="store_true", help="check every exported fragment")
    args = ap.parse_args()

    if args.all:
        ids = sorted(p.name for p in INPUT_DIR.iterdir() if p.is_dir())
    elif args.fragment_id:
        ids = [args.fragment_id]
    else:
        ap.error("give a fragment id or --all")

    any_failed = False
    for fid in ids:
        any_failed |= report(fid, preflight(fid))
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
