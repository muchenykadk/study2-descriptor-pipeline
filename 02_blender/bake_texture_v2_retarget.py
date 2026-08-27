"""
bake_texture_v2_retarget.py — Study 2 Descriptor Pipeline
Re-bake a texture onto a remesh that already exists, skipping the voxel remesh.

WHY THIS EXISTS
---------------
FRAG-S1-FS-001 is 2841 mm across. At VOXEL_SIZE = 0.002 m that asks Blender for
2.9 billion voxels, roughly six times the worst other fragment in the corpus, and
the remesh falls back to a coarser voxel and trips the 20% sanity check in
`bake_texture_v2.py`. Raising VOXEL_SIZE would produce a mesh coarser than the
rest of the corpus and is explicitly warned against there.

None of that is necessary. A good remesh of FS-001 already exists: the GLB in
`01_input/meshes/processed/FRAG-S1-FS-001/` carries 5,654,800 triangles, which is
93% of the ~6.05M the v2 check expects, so it is at corpus parity. It was
produced on 2026-08-19 by `bake_texture.py` (v1), whose `BAKE_RES` was 1080. The
rest of the corpus was baked on 2026-08-24 with v2 at 4096.

So FS-001's atlas is coarse because of a bake setting, not because of its source.
The pipeline measured it at 0.20 px per mm against roughly 1.4 elsewhere, and
`CALIB_PX_PER_MM = 0.46` is the density the region gates were tuned at. This
script re-bakes at 4096 onto the mesh that already exists, which should bring it
to about 0.76 px per mm.

WHAT IT DOES NOT DO
-------------------
No remesh, no hole filling, no mesh cleanup, and no UNSCANNED detection. The
UNSCANNED ground-contact face was already recorded in
`FRAG-S1-FS-001_scan_coverage.json` by the v2 run, and that sidecar is left
untouched. Re-deriving it here would risk overwriting a good record with a worse
one.

USAGE
-----
  1. Open Blender. Import the Polycam export of the fragment.
  2. Select it. It must have a material with its texture, or there is nothing
     to bake from.
  3. Set FRAG_ID below and run.

The script imports the existing remesh from the repo itself, so the Polycam
export is the only thing you need to bring in.

  4. python 03_src/run_pipeline.py FRAG-S1-FS-001 --force --no-browser

KEEP_UVS
--------
True  keeps the UV layout already in the GLB. Only texel density changes, so the
      RANSAC faces and the region partition come out identical and the run is a
      controlled comparison against the 1080 result. Regions that failed on
      `sparse_uv` at 1 to 3% UV fill will still fail: that is a packing problem
      and more pixels do not fix it.
False re-runs Smart UV Project. May fix the packing and recover those regions,
      but the partition changes, so the result is a new run rather than a
      comparison.

Start with True.
"""

import bpy
import os
import shutil
from datetime import datetime
from mathutils import Vector

# ── Configuration ──────────────────────────────────────────────────────────────

FRAG_ID     = "FRAG-S1-FS-001"
BAKE_RES    = 4096    # px. v1 used 1080; the rest of the corpus is at 4096.
EXTRUSION   = 0.05    # m. Cage distance. Raise to 0.10 if the bake has black patches.
BAKE_MARGIN = 32      # px of edge bleed into the empty atlas
KEEP_UVS    = True    # see docstring
ALIGN_MODE  = "anchor"  # "none" | "anchor" | "center" | "center_and_scale"
                        # "anchor" is the right default for this workflow. It
                        #   matches the two meshes on each axis at whichever end
                        #   they agree, rather than at their centres. On FS-001
                        #   the target's ground-contact face was closed by hand
                        #   while the Polycam source still has its open bottom
                        #   hanging 64 mm lower, so matching centres would have
                        #   shifted every other surface by 32 mm.
                        # "center" moves the source so its bounding-box centre
                        #   sits on the target's. Fixes a pure translation, which
                        #   is what a fresh import usually needs.
                        # "center_and_scale" additionally scales the source to
                        #   match the target's dimensions. Only correct when the
                        #   difference really is scale, e.g. an export in
                        #   centimetres. If the two meshes differ in shape rather
                        #   than size this will distort the source and smear the
                        #   bake, so read the per-axis report before using it.
ALIGN_TOL   = 0.05    # max fractional dimension disagreement after alignment
REPO_ROOT   = r"C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"


# ── Helpers (identical to bake_texture_v2.py) ─────────────────────────────────

def deselect_all():
    bpy.ops.object.select_all(action='DESELECT')

def set_active(obj):
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def smart_uv_project(obj):
    """Apply Smart UV Project to all faces of obj.

    angle_limit=89 groups faces whose normals differ by up to 89° into the same
    UV island. island_margin 0.002 rather than 0.02: on FS-002 the larger value
    left only 20% of the atlas carrying any UV at all.
    """
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.002, angle_limit=89)
    bpy.ops.object.mode_set(mode='OBJECT')

def add_blank_image_node(mat, name, location=(0, 0)):
    """Add an Image Texture node with a new blank image. Blender bakes into it."""
    img = bpy.data.images.new(name=name, width=BAKE_RES, height=BAKE_RES)
    nodes = mat.node_tree.nodes
    for n in nodes:
        n.select = False
    node = nodes.new('ShaderNodeTexImage')
    node.image    = img
    node.location = location
    node.select   = True
    nodes.active  = node
    return node, img

def wire_to_base_color(mat, img_node):
    """Disconnect current Base Color link and connect img_node → Base Color."""
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        return False
    for lnk in list(principled.inputs['Base Color'].links):
        links.remove(lnk)
    links.new(img_node.outputs['Color'], principled.inputs['Base Color'])
    return True

def set_bake_mode(selected_to_active):
    bpy.context.scene.render.engine = 'CYCLES'
    bake = bpy.context.scene.render.bake
    bake.use_pass_direct        = False
    bake.use_pass_indirect      = False
    bake.use_pass_color         = True
    bake.use_selected_to_active = selected_to_active
    bake.margin      = BAKE_MARGIN
    bake.margin_type = 'EXTEND'
    if selected_to_active:
        bake.cage_extrusion = EXTRUSION

def _backup(path):
    """Rename an existing output aside rather than overwriting it.

    The 1080 atlas is the baseline this run is meant to be compared against, so
    losing it would destroy the comparison the whole exercise is for.
    """
    if not os.path.isfile(path):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root, ext = os.path.splitext(path)
    dest = f"{root}.pre-retarget-{stamp}{ext}"
    shutil.move(path, dest)
    return dest


# ── 0: Validate the selected object as the bake source ────────────────────────

source = bpy.context.active_object
if source is None or source.type != 'MESH':
    raise RuntimeError("No mesh selected. Select the Polycam export and run again.")
if not source.material_slots or not source.material_slots[0].material:
    raise RuntimeError(
        f"'{source.name}' has no material, so there is nothing to bake from. "
        f"Import the Polycam export with its texture."
    )

print(f"\n{'=' * 56}")
print(f"  bake_texture_v2_retarget.py  —  {FRAG_ID}")
print(f"{'=' * 56}")
print(f"  Source : {source.name}   (Polycam export, bake source)")

out_dir  = os.path.join(REPO_ROOT, "01_input", "meshes", "processed", FRAG_ID)
glb_path = os.path.join(out_dir, f"{FRAG_ID}.glb")
tex_path = os.path.join(out_dir, f"{FRAG_ID}_texture.png")

if not os.path.isfile(glb_path):
    raise RuntimeError(
        f"No existing remesh to bake onto:\n    {glb_path}\n"
        f"This script re-bakes an existing remesh. If there is none, run "
        f"bake_texture_v2.py instead."
    )


# ── 1: Import the existing remesh as the bake target ──────────────────────────

print(f"\n  ── Import existing remesh ──────────────────────────────")
_before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=glb_path)
_new = [o for o in bpy.data.objects if o not in _before and o.type == 'MESH']
if not _new:
    raise RuntimeError(f"GLB imported no mesh object: {glb_path}")
target = max(_new, key=lambda o: len(o.data.polygons))
target.name = f"{FRAG_ID}_remesh"
print(f"     Target : {target.name}")
print(f"     {len(target.data.vertices):,} vertices  {len(target.data.polygons):,} faces")

if not target.data.uv_layers:
    raise RuntimeError(
        f"'{target.name}' has no UV layer. Set KEEP_UVS = False so the script "
        f"generates one."
    )


# ── 2: Alignment check ────────────────────────────────────────────────────────
# Selected-to-active casts rays from the target surface toward the source. If the
# two are not in the same place at the same scale, every ray misses and the bake
# comes out blank or black. A fresh Polycam export will only line up with a
# remesh made from an earlier import if nothing moved it in between, so this is
# checked rather than assumed.

print(f"\n  ── Alignment ───────────────────────────────────────────")

def _bbox_center(o):
    """World-space centre of the object's bounding box.

    Not the same as the object origin, which for a scan export is often far from
    the geometry. Comparing origins is what reported a 295% offset on FS-001
    while the meshes may have been much closer than that.
    """
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return sum(pts, Vector()) / 8.0

def _report(tag):
    sd, td = source.dimensions, target.dimensions
    print(f"     {tag}")
    for ax, s, t in zip("XYZ", sd, td):
        print(f"       {ax}: source {s:8.4f}   target {t:8.4f}   "
              f"diff {abs(s - t) / max(t, 1e-9):6.1%}")
    d = (_bbox_center(source) - _bbox_center(target)).length
    print(f"       bbox centres apart: {d:.4f}  "
          f"({d / max(max(td), 1e-9):.1%} of size)")
    return max(abs(s - t) / max(t, 1e-9) for s, t in zip(sd, td)), \
           d / max(max(td), 1e-9)

def _bounds(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    return lo, hi

_report("Before alignment:")

if ALIGN_MODE == "anchor":
    # Match each axis at the end where the two agree. Where the source is longer
    # because it still carries an open, unclosed face, that extra material is all
    # at one end; anchoring at the other end leaves every real surface coincident.
    slo, shi = _bounds(source)
    tlo, thi = _bounds(target)
    delta = Vector((0.0, 0.0, 0.0))
    for i, ax in enumerate("XYZ"):
        d_lo, d_hi = tlo[i] - slo[i], thi[i] - shi[i]
        delta[i] = d_lo if abs(d_lo) <= abs(d_hi) else d_hi
        print(f"       {ax}: anchoring at {'min' if abs(d_lo) <= abs(d_hi) else 'max'}"
              f"  (shift {delta[i]:+.4f}; other end would need {max(d_lo, d_hi, key=abs):+.4f})")
    source.location = source.location + delta
    bpy.context.view_layer.update()
    print(f"     Moved source by {delta.length:.4f}")
    _report("After alignment:")

elif ALIGN_MODE in ("center", "center_and_scale"):
    if ALIGN_MODE == "center_and_scale":
        sd, td = source.dimensions, target.dimensions
        f = sum(t / max(s, 1e-9) for s, t in zip(sd, td)) / 3.0
        source.scale = tuple(v * f for v in source.scale)
        bpy.context.view_layer.update()
        print(f"     Scaled source by {f:.4f}")
    delta = _bbox_center(target) - _bbox_center(source)
    source.location = source.location + delta
    bpy.context.view_layer.update()
    print(f"     Moved source by {delta.length:.4f}")
    _report("After alignment:")

# The test that matters is not whether the two bounding boxes are the same size.
# It is whether every part of the target lies inside the source, plus the cage,
# so that a ray cast from the target surface finds source geometry to sample.
# A source that is longer on one axis is harmless; a target that sticks out is
# not, because those faces bake black.
slo, shi = _bounds(source)
tlo, thi = _bounds(target)
_out = []
for i, ax in enumerate("XYZ"):
    under = slo[i] - EXTRUSION - tlo[i]
    over  = thi[i] - (shi[i] + EXTRUSION)
    if under > 0: _out.append(f"{ax} min by {under * 1000:.0f} mm")
    if over  > 0: _out.append(f"{ax} max by {over * 1000:.0f} mm")

print(f"     Cage: {EXTRUSION * 1000:.0f} mm")
if _out:
    raise RuntimeError(
        f"The target sticks out beyond the source plus cage: "
        f"{', '.join(_out)}.\n\n"
        f"    Those faces have no source geometry within reach and will bake "
        f"black.\n"
        f"    Either raise EXTRUSION to cover the overhang, or align the two "
        f"meshes by hand if they are genuinely different shapes.\n"
        f"    Check the per-axis report above: axes agreeing to 0.0% mean the "
        f"same capture, and a single axis differing usually means one mesh had "
        f"a face closed that the other still has open."
    )
print(f"     ✓  Target lies within the source plus cage on all axes")


# ── 3: Material and UV on the target ──────────────────────────────────────────

mat_orig   = target.material_slots[0].material if target.material_slots else None
if mat_orig is None:
    mat_orig = bpy.data.materials.new(name=f"{FRAG_ID}_mat")
    mat_orig.use_nodes = True
    target.data.materials.append(mat_orig)
mat_target      = mat_orig.copy()
mat_target.name = f"{FRAG_ID}_mat"
target.material_slots[0].material = mat_target
print(f"\n  ✓  Material copy: '{mat_target.name}'")

if KEEP_UVS:
    print(f"  ✓  Keeping the GLB's existing UV layout "
          f"('{target.data.uv_layers.active.name}') — controlled comparison")
else:
    smart_uv_project(target)
    print(f"  ✓  Smart UV re-projected (angle_limit=89°) — partition will change")


# ── 4: Bake — source → target ─────────────────────────────────────────────────

print(f"\n  ── Bake  (source → existing remesh) ────────────────────")
source.hide_viewport = False
source.hide_render   = False
target.hide_viewport = False

bake_node, bake_img = add_blank_image_node(
    mat_target, f"{FRAG_ID}_bake", location=(-200, 300)
)

deselect_all()
source.select_set(True)
target.select_set(True)
bpy.context.view_layer.objects.active = target

set_bake_mode(selected_to_active=True)
print(f"  Baking...  [{BAKE_RES}×{BAKE_RES}, extrusion {EXTRUSION * 1000:.0f} mm]")
print(f"  This is 14× the pixels of the 1080 bake. Expect it to take a while.")
bpy.ops.object.bake(type='DIFFUSE')
print(f"  ✓  Bake done")


# ── 5: Save texture, keeping the old one ──────────────────────────────────────

_old_tex = _backup(tex_path)
if _old_tex:
    print(f"\n  ✓  Previous atlas kept → {os.path.basename(_old_tex)}")

bake_img.file_format  = 'PNG'
bake_img.filepath_raw = tex_path
bake_img.save()
print(f"  ✓  Texture saved → {tex_path}")


# ── 6: Wire and export ────────────────────────────────────────────────────────

set_active(target)
if wire_to_base_color(mat_target, bake_node):
    print(f"  ✓  Baked texture wired to Base Color")
else:
    print(f"  ⚠  Principled BSDF not found — wire to Base Color manually")

_old_glb = _backup(glb_path)
if _old_glb:
    print(f"  ✓  Previous GLB kept → {os.path.basename(_old_glb)}")

set_active(target)
result = bpy.ops.export_scene.gltf(
    filepath=glb_path,
    export_format='GLB',
    use_selection=True,
    export_texcoords=True,
    export_normals=True,
    export_materials='EXPORT',
    export_image_format='AUTO',
)
if result == {'FINISHED'} and os.path.isfile(glb_path):
    print(f"  ✓  GLB saved → {glb_path}")
    print(f"     File size: {os.path.getsize(glb_path) / 1024 / 1024:.1f} MB")
else:
    raise RuntimeError(f"GLB export failed (operator returned {result})")


# ── Done ──────────────────────────────────────────────────────────────────────

print(f"\n{'=' * 56}")
print(f"  Done — {FRAG_ID} re-baked at {BAKE_RES}")
print(f"{'=' * 56}")
print(f"  The scan_coverage sidecar was not touched.")
print(f"\n  Next:")
print(f"    python 03_src/run_pipeline.py {FRAG_ID} --force --no-browser")
print(f"\n  Then check the reported texel density. The 1080 atlas measured")
print(f"  0.20 px per mm; at {BAKE_RES} it should read about 0.76, against")
print(f"  CALIB_PX_PER_MM = 0.46 and roughly 1.4 elsewhere in the corpus.")
print(f"  If pipe_opening now appears, texture resolution was the cause.")
