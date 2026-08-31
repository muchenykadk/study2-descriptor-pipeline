"""
bake_texture_v2.py — Study 2 Descriptor Pipeline
=================================================
Extended version of bake_texture.py that additionally:

  Step 2.5 — Detects the unscanned ground-contact face automatically from
    the open boundary loop and writes a sidecar JSON for scan_coverage.py,
    WITHOUT needing a manual vertex group or hole-closing.
    Falls back to a manual "UNSCANNED" vertex group if present.

  Step 2.6 — Fills ALL open boundary loops on the remesh target so the
    voxel remesh gets a clean closed mesh. Scaniverse exports with many
    scan holes otherwise produce ~1,500 faces instead of ~100,000+.

  Step 2.8 — Merges duplicate vertices (remove_doubles) before remesh.

Manual step BEFORE (minimal):
  1. Import the Scaniverse OBJ or GLB into Blender
  2. Delete the floor plane and stray objects
  3. Select the fragment mesh → Run Script
  (No hole-closing or vertex group needed)

Manual step AFTER:
  4. Verify: Z → Material Preview in viewport
  5. python 03_src/run_pipeline.py FRAG-S1-{ARCHETYPE}-{###}
  6. python 03_src/scan_coverage.py FRAG-S1-{ARCHETYPE}-{###}
"""

import bpy
import bmesh
import json
import os
import mathutils

# ── Configuration ──────────────────────────────────────────────────────────────
FRAG_ID    = "FRAG-S1-FS-003"
VOXEL_SIZE = 0.002    # metres — 2 mm; increase to 0.005 for very noisy scans
BAKE_RES   = 4096     # texture resolution (px). Measured on FS-002: at 1080 the
                      # atlas gives 0.07 px per face, so islands of a few faces
                      # average to one colour and the bake margin bleeds each into
                      # a flat diamond. 4096 gives 1.03 px per face. The manual
                      # workflow always specified 4096; the script did not.
EXTRUSION  = 0.05     # metres — increase to 0.10 if bake has black patches
BAKE_MARGIN = 32      # px of edge bleed into the empty atlas (see set_bake_mode)
REPO_ROOT  = r"C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"


# ── Helpers ────────────────────────────────────────────────────────────────────

def deselect_all():
    bpy.ops.object.select_all(action='DESELECT')

def set_active(obj):
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def smart_uv_project(obj):
    """Apply Smart UV Project to all faces of obj.

    angle_limit=89 groups faces whose normals differ by up to 89° into the same
    UV island. The default (66°) fragments rough voxel-remesh surfaces into
    hundreds of tiny islands, causing the 8×8 grid classifier to produce
    horizontal stripe artefacts. 89° keeps each contiguous surface region in
    one island while still separating top/bottom/side faces (~90° apart).
    """
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    # island_margin is a FRACTION OF THE ATLAS, not pixels. 0.02 leaves 2% of the
    # sheet width between every pair of islands, and measured on FS-002 that left
    # only 20% of the atlas carrying any UV at all: 80% was margin and packing
    # waste, which the bake margin then filled with flat bled colour.
    bpy.ops.uv.smart_project(island_margin=0.002, angle_limit=89)
    bpy.ops.object.mode_set(mode='OBJECT')

def add_blank_image_node(mat, name, location=(0, 0)):
    """
    Add an Image Texture node to mat with a new blank image.
    The node is left unconnected but selected — Blender bakes into it.
    Returns (node, image).
    """
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
    # Bleed each island's edge colour outward into the empty atlas.  Blender's
    # default margin type only bleeds across shared UV edges, which leaves the
    # space between islands pure black.  The descriptor pipeline crops a region
    # out of this atlas, so that black lands inside the crop and a vision model
    # reads it as voids in the concrete.  EXTEND fills it with real surface
    # colour instead.
    bake.margin      = BAKE_MARGIN
    bake.margin_type = 'EXTEND'
    if selected_to_active:
        bake.cage_extrusion = EXTRUSION

def _boundary_loops(bm):
    """
    Return a list of boundary loops, each as an ordered list of
    mathutils.Vector positions.

    Uses boundary edge traversal — each edge is visited at most once,
    so there are no infinite loops even on complex meshes.
    """
    boundary_set = {e for e in bm.edges if e.is_boundary}
    if not boundary_set:
        return []

    loops = []
    remaining = set(boundary_set)

    while remaining:
        cur_edge = next(iter(remaining))
        cur_vert = cur_edge.verts[0]
        loop_coords = []

        while cur_edge in remaining:
            remaining.discard(cur_edge)
            loop_coords.append(cur_vert.co.copy())
            next_vert = cur_edge.other_vert(cur_vert)
            # Find the next boundary edge connected to next_vert
            next_edge = next(
                (e for e in next_vert.link_edges if e in remaining and e.is_boundary),
                None
            )
            if next_edge is None:
                break
            cur_vert = next_vert
            cur_edge = next_edge

        if loop_coords:
            loops.append(loop_coords)

    return loops

def _newell_normal(verts):
    """
    Compute the polygon normal from an ordered vertex list using Newell's method.
    Works for any planar or near-planar polygon regardless of orientation.
    Returns a normalised mathutils.Vector.
    """
    n = mathutils.Vector((0.0, 0.0, 0.0))
    count = len(verts)
    for i, v in enumerate(verts):
        vn = verts[(i + 1) % count]
        n.x += (v.y - vn.y) * (v.z + vn.z)
        n.y += (v.z - vn.z) * (v.x + vn.x)
        n.z += (v.x - vn.x) * (v.y + vn.y)
    length = n.length
    return n / length if length > 1e-8 else mathutils.Vector((0.0, 0.0, -1.0))


# ── 0: Validate active object ──────────────────────────────────────────────────

obj = bpy.context.active_object
if obj is None or obj.type != 'MESH':
    raise RuntimeError("No mesh selected. Select the cleaned mesh and run again.")
if not obj.material_slots or not obj.material_slots[0].material:
    raise RuntimeError(f"'{obj.name}' has no material. Import the GLB with texture first.")

print(f"\n{'='*56}")
print(f"  bake_texture_v2.py  —  {FRAG_ID}")
print(f"{'='*56}")
print(f"  Mesh : {obj.name}")


# ── Output dir (needed early for sidecar in step 2.5) ─────────────────────────

out_dir = os.path.join(REPO_ROOT, "01_input", "meshes", "processed", FRAG_ID)
os.makedirs(out_dir, exist_ok=True)


# ── 1: Scale check ─────────────────────────────────────────────────────────────

dims    = obj.dimensions          # in Blender scene units
max_dim = max(dims)
scene_unit_scale = bpy.context.scene.unit_settings.scale_length   # 1.0 = metres
max_dim_m = max_dim * scene_unit_scale   # always in metres regardless of scene units

print(f"  Dimensions  : X={dims.x:.4f}  Y={dims.y:.4f}  Z={dims.z:.4f}  (scene units)")
print(f"  Scene scale : {scene_unit_scale}  (1.0 = metres, 0.01 = centimetres)")
print(f"  Max dim     : {max_dim:.4f} units  =  {max_dim_m*1000:.1f} mm  =  {max_dim_m:.4f} m")
print(f"  Object scale: {obj.scale.x:.4f}, {obj.scale.y:.4f}, {obj.scale.z:.4f}  (should be 1,1,1)")
print(f"  Vertices    : {len(obj.data.vertices):,}   Faces: {len(obj.data.polygons):,}")

# Unapplied scale is a hard stop, not a warning.
#
# The Remesh modifier works in the object's LOCAL space, but obj.dimensions
# reports the scaled size. So an object imported in millimetres and then scaled
# by 0.001 passes every check above — dimensions say 2.841 m — while the mesh
# data underneath is still 2841 units across. Voxelising that at VOXEL_SIZE
# asks for a thousand times too many voxels per axis, Blender clamps, and the
# result is a few thousand faces with no obvious cause.
#
# This cost an afternoon on FS-001, where the remesh returned 16,358 faces and
# the failure looked like a memory ceiling. The warning was printed and scrolled
# past. Stopping is the only thing that works.
_sc = obj.scale
if abs(_sc.x - 1.0) > 1e-6 or abs(_sc.y - 1.0) > 1e-6 or abs(_sc.z - 1.0) > 1e-6:
    _local = max(obj.data.vertices[i].co.length for i in
                 range(0, len(obj.data.vertices), max(1, len(obj.data.vertices)//1000))) * 2
    raise RuntimeError(
        f"UNAPPLIED SCALE: object scale is "
        f"({_sc.x:.4f}, {_sc.y:.4f}, {_sc.z:.4f}), not (1, 1, 1).\n"
        f"    Displayed dimensions are {max_dim_m*1000:.0f} mm, but the mesh data "
        f"underneath spans roughly {_local:.0f} local units.\n"
        f"    The Remesh modifier works in LOCAL space, so VOXEL_SIZE="
        f"{VOXEL_SIZE} would be applied to that number and Blender will clamp it "
        f"to something far coarser.\n\n"
        f"    Fix: Object Mode, select the mesh, Ctrl+A, Apply, Scale. Then run "
        f"again.\n"
    )

if max_dim_m < 0.01:
    raise RuntimeError(
        f"Fragment appears to be {max_dim_m*1000:.2f} mm — extremely small. "
        "Check units. Apply scale: Ctrl+A → Scale."
    )
elif max_dim_m < 0.05:
    print(f"  ⚠  Very small ({max_dim_m*1000:.1f} mm) — check scale before continuing.")
elif max_dim_m > 5.0:
    raise RuntimeError(
        f"Fragment appears to be {max_dim_m*1000:.0f} mm — suspiciously large. "
        f"The OBJ is likely in mm or cm, not metres. "
        f"Fix: Object Mode → Ctrl+A → Apply → Scale,  "
        f"then S → 0.001 → Enter (mm→m) or S → 0.01 → Enter (cm→m)."
    )
else:
    print(f"  ✓  Scale OK  ({max_dim_m*1000:.0f} mm)")


# ── 2: Duplicate → the COPY is remeshed, the import is kept ───────────────────
# The remesh is destructive: applying the modifier replaces the geometry.  It is
# therefore done on a duplicate, so the object that was imported survives intact
# and can be re-exported later without re-importing the scan.  It is hidden
# during the run because the bake needs it out of the viewport, and unhidden
# again at the end.

_imported_name = obj.name
set_active(obj)
bpy.ops.object.duplicate()
_dup = bpy.context.active_object      # duplicate is now active

source = obj                          # the import itself, kept as the bake source
source.name          = f"{FRAG_ID}_original"
source.hide_viewport = True
source.hide_render   = False          # must remain renderable for baking

obj = _dup                            # everything downstream works on the copy
obj.name = f"{FRAG_ID}_remesh"

print(f"\n  ✓  Kept intact : '{source.name}'  (was '{_imported_name}', hidden; "
      f"also serves as the bake source)")
print(f"  ✓  Remesh target: '{obj.name}'  (a copy; this is the one that gets "
      f"remeshed and exported)")


# ── 2.5: Detect UNSCANNED ground-contact face (NEW in v2) ────────────────────
# The fragment was scanned lying on the ground — the bottom face is always
# missing. We need to record its normal and centroid BEFORE the voxel remesh
# closes the hole, so scan_coverage.py can flag the corresponding RANSAC plane.
#
# Two detection paths (in priority order):
#   A. Manual "UNSCANNED" vertex group — if the user manually closed the hole
#      and assigned a vertex group, use that (highest precision).
#   B. Auto boundary detection — finds the open boundary loop on the raw mesh
#      and estimates the normal via Newell's method. No manual step needed.
#
# If the mesh is already watertight (e.g., hole was closed externally), no
# sidecar is written and behaviour is identical to bake_texture.py.

print(f"\n  ── UNSCANNED detection ─────────────────────────────────")

_sidecar_data  = None   # will hold the dict to write
_sidecar_path  = os.path.join(out_dir, f"{FRAG_ID}_scan_coverage.json")
_loops         = []     # boundary loops found in Path B (empty if Path A ran)

# Path A: manual vertex group
_vg = obj.vertex_groups.get("UNSCANNED")
if _vg:
    _vg_idx = _vg.index
    _vg_normals, _vg_centers = [], []
    for face in obj.data.polygons:
        in_group = any(
            any(g.group == _vg_idx for g in obj.data.vertices[v].groups)
            for v in face.vertices
        )
        if in_group:
            _vg_normals.append(face.normal.copy())
            _vg_centers.append(face.center.copy())

    if _vg_normals:
        # Convert to WORLD space so the sidecar matches GLB export coordinates.
        # GLB uses world-space vertices (object transform applied on export).
        _mw     = obj.matrix_world
        _mw_rot = _mw.to_3x3().normalized()
        _vg_normals = [(_mw_rot @ n).normalized() for n in _vg_normals]
        _vg_centers = [_mw @ c for c in _vg_centers]
        _avg_n = sum(_vg_normals, mathutils.Vector()) / len(_vg_normals)
        _avg_c = sum(_vg_centers, mathutils.Vector()) / len(_vg_centers)
        _avg_n = _avg_n.normalized()
        _sidecar_data = {
            "has_unscanned_face": True,
            "avg_normal":  [round(float(x), 4) for x in _avg_n],
            "avg_center":  [round(float(x), 4) for x in _avg_c],
            "face_count":  len(_vg_normals),
            "detection_method": "manual_vertex_group",
            "notes": "Ground-contact face — manually closed and marked with UNSCANNED vertex group.",
        }
        print(f"     Path A (vertex group): {len(_vg_normals)} faces  "
              f"normal [{_avg_n.x:.3f}, {_avg_n.y:.3f}, {_avg_n.z:.3f}]")
    else:
        print(f"     ⚠  UNSCANNED vertex group found but contains no faces — skipping")

# Path B: auto boundary detection (only if path A didn't succeed)
if _sidecar_data is None:
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    _bm = bmesh.from_edit_mesh(obj.data)
    _bm.edges.ensure_lookup_table()

    _loops = _boundary_loops(_bm)

    _bm.free()
    bpy.ops.object.mode_set(mode='OBJECT')

    if _loops:
        # Use the largest loop by vertex count = the ground-contact face
        _largest = max(_loops, key=len)
        _avg_n   = _newell_normal(_largest)
        _avg_c   = sum(_largest, mathutils.Vector()) / len(_largest)
        _sidecar_data = {
            "has_unscanned_face": True,
            "avg_normal":  [round(float(x), 4) for x in _avg_n],
            "avg_center":  [round(float(x), 4) for x in _avg_c],
            "face_count":  0,   # 0 = boundary loop, not filled faces
            "loop_vertex_count": len(_largest),
            "total_boundary_loops": len(_loops),
            "detection_method": "auto_boundary_loop",
            "notes": (
                "Ground-contact face not captured during photogrammetry scanning. "
                "Normal estimated from the largest open boundary loop (Newell method). "
                "The voxel remesh closes this hole automatically."
            ),
        }
        print(f"     Path B (auto): {len(_loops)} boundary loop(s)  "
              f"largest = {len(_largest)} verts  "
              f"normal [{_avg_n.x:.3f}, {_avg_n.y:.3f}, {_avg_n.z:.3f}]")
    else:
        print(f"     Mesh is watertight — no open boundary found")
        print(f"     Sidecar not written (no unscanned face to flag)")

# Write sidecar
if _sidecar_data:
    with open(_sidecar_path, "w", encoding="utf-8") as _f:
        json.dump(_sidecar_data, _f, indent=2)
    print(f"     ✓  Sidecar → {FRAG_ID}_scan_coverage.json")


# ── 2.6: Fill all open holes on the remesh target ─────────────────────────────
# The UNSCANNED ground-contact face was already recorded in step 2.5.
# Now fill ALL open boundary loops on obj so the voxel remesh gets a clean
# closed mesh. Without this, a Scaniverse export with many small holes produces
# only ~1,500 faces instead of ~100,000+.
#
# The SOURCE (duplicate from step 2) is untouched — the main bake still reads
# texture from the original Scaniverse mesh.

_n_boundary_loops = len(_loops) if _sidecar_data and _sidecar_data.get("detection_method") == "auto_boundary_loop" else 0

if _n_boundary_loops > 0:
    print(f"\n  ── Fill holes on remesh target ({_n_boundary_loops} loops) ─────────")
    _bm_fill = bmesh.new()
    _bm_fill.from_mesh(obj.data)
    _bm_fill.edges.ensure_lookup_table()

    _open_edges = [e for e in _bm_fill.edges if e.is_boundary]
    if _open_edges:
        _fill_result = bmesh.ops.triangle_fill(
            _bm_fill, use_beauty=True, edges=_open_edges
        )
        _n_filled_faces = len(_fill_result.get("faces", []))
        _bm_fill.to_mesh(obj.data)
        obj.data.update()
        # Verify: formerly boundary edges now have 2 adjacent faces → not boundary
        _still_open = [e for e in _bm_fill.edges if e.is_boundary]
        print(f"     ✓  Filled {_n_filled_faces} faces across {len(_open_edges)} boundary edges")
        print(f"        Open edges remaining after fill: {len(_still_open)}  (expect 0 for fully closed mesh)")
    else:
        print(f"     No open edges remaining — skipped")

    _bm_fill.free()


# ── 2.8: Mesh cleanup before remesh ──────────────────────────────────────────
# Raw Scaniverse exports often have duplicate vertices that cause the voxel
# remesh to produce 0 faces (point cloud). Merge duplicates only.
#
# NOTE: We intentionally do NOT call recalc_face_normals here. On an open
# Scaniverse mesh with many holes, Blender guesses the wrong "outward"
# direction and flips ALL normals inward → the exported GLB mesh is invisible
# (Three.js backface culling shows nothing) and the voxelizer produces a
# degraded result (~1,500 faces instead of ~100,000+).

print(f"\n  ── Mesh cleanup ─────────────────────────────────────────")
_v_before = len(obj.data.vertices)
_f_before = len(obj.data.polygons)
print(f"     Before: {_v_before:,} vertices  {_f_before:,} faces")

set_active(obj)
bpy.ops.object.mode_set(mode='EDIT')
_bm_clean = bmesh.from_edit_mesh(obj.data)
bmesh.ops.remove_doubles(_bm_clean, verts=_bm_clean.verts, dist=0.0001)
bmesh.update_edit_mesh(obj.data)
bpy.ops.object.mode_set(mode='OBJECT')

_v_after = len(obj.data.vertices)
_f_after = len(obj.data.polygons)
print(f"     After : {_v_after:,} vertices  {_f_after:,} faces")
print(f"     ✓  Removed {_v_before - _v_after:,} duplicate verts")


# ── 3: Voxel remesh ───────────────────────────────────────────────────────────
# The remesh closes any open holes automatically (including the ground-contact
# face detected above). If this step produces 0 faces (point cloud), try
# increasing VOXEL_SIZE to 0.005 at the top of the script.

# VOXEL_SIZE is written in METRES, but mod.voxel_size is in BLENDER UNITS, and
# the two are only the same when the scene unit scale is 1.0.
#
# FS-001 lives in a .blend whose unit scale is 0.001, so its mesh is 2841 units
# across and displays as 2841 mm. Object scale was a clean (1, 1, 1) and every
# check passed, because obj.dimensions is unit-aware. Passing 0.002 straight
# through then asked for a voxel of 0.002 UNITS on a 2841-unit mesh: 1.4 million
# voxels per axis, which Blender clamped to roughly 32 mm, giving 23,646 faces
# where 6 million were expected.
#
# Converting here makes the script work in any scene unit setting, which is the
# real fix. Checking object scale is not enough: scale can be applied and the
# mesh still be in millimetres.
_voxel_units = VOXEL_SIZE / scene_unit_scale
_across_calc = max_dim / _voxel_units

print(f"\n  ── Voxel remesh ─────────────────────────────────────────")
print(f"     Voxel size : {VOXEL_SIZE * 1000:.1f} mm  ({_voxel_units:g} Blender units "
      f"at scene scale {scene_unit_scale:g})")
print(f"     Mesh size  : {max_dim_m * 1000:.0f} mm  ({max_dim:g} units)  →  "
      f"~{int(_across_calc)} voxels across longest axis")
if scene_unit_scale != 1.0:
    print(f"     NOTE: scene is not in metres; VOXEL_SIZE converted "
          f"{VOXEL_SIZE} m → {_voxel_units:g} units")

mod              = obj.modifiers.new(name="Remesh", type='REMESH')
mod.mode         = 'VOXEL'
mod.voxel_size   = _voxel_units
mod.use_smooth_shade = True
_apply_result = bpy.ops.object.modifier_apply(modifier=mod.name)
print(f"     modifier_apply returned: {_apply_result}")

# Sanity check — catch point cloud or empty remesh
_poly_count = len(obj.data.polygons)
_vert_count = len(obj.data.vertices)
_dims_after = obj.dimensions
print(f"     After remesh: {_vert_count:,} vertices  {_poly_count:,} faces")
print(f"     Dimensions  : X={_dims_after.x:.4f}  Y={_dims_after.y:.4f}  Z={_dims_after.z:.4f}")

# A fixed floor of 100 faces is not a useful test: FRAG-S1-FS-003 came out at
# 3,016 faces and passed it, then produced planes matching under 4% of its
# geometry and no surface classification at all.  The check has to scale with
# the mesh, because the expected face count is set by how many voxels span it.
_across   = max_dim_m / VOXEL_SIZE
_expected = 3.0 * _across ** 2          # calibrated on FS-006: 831 across → 2.1M faces
_ratio    = _poly_count / max(_expected, 1.0)
print(f"     Expected    : ~{int(_expected):,} faces for {int(_across)} voxels across "
      f"→ got {_ratio:.0%}")

if _poly_count == 0:
    raise RuntimeError(
        f"Voxel remesh produced 0 faces (point cloud). "
        f"VOXEL_SIZE={VOXEL_SIZE} may be wrong for this mesh. "
        f"Try VOXEL_SIZE = {max_dim_m / 400:.4f} (1/400th of max dim)."
    )
if _ratio < 0.20:
    # Two causes produce this, and the message used to assert the first one.
    # That sent Muchen looking for a unit error on FS-001 when the scale check
    # had already passed and the object really was in metres.
    _voxels = _across ** 3
    _unit_suspect = max_dim > 100.0        # scene units, not metres
    raise RuntimeError(
        f"Voxel remesh produced {_poly_count:,} faces, only {_ratio:.0%} of the "
        f"~{int(_expected):,} expected for a {max_dim_m * 1000:.0f} mm mesh at "
        f"VOXEL_SIZE={VOXEL_SIZE} m ({int(_across)} voxels across, "
        f"{_voxels / 1e9:.1f} billion voxels).\n\n"
        + (f"    LIKELY A UNIT MISMATCH. The object measures {max_dim:.0f} Blender "
           f"units, so it is in millimetres while VOXEL_SIZE is written in metres.\n"
           f"    Fix: Object Mode, S, 0.001, Enter, then Ctrl+A, Apply, Scale.\n"
           if _unit_suspect else
           f"    NOT a unit mismatch: the object measures {max_dim:.3f} Blender "
           f"units, which is metres, and the scale check passed.\n"
           f"    The mesh is simply too large to voxelise at this size. Blender ran\n"
           f"    out of headroom and fell back to a coarser voxel. A typical\n"
           f"    fragment here asks for 0.05 to 0.5 billion voxels; this one asks\n"
           f"    for {_voxels / 1e9:.1f} billion.\n"
           f"    Options: close other applications and retry, or raise VOXEL_SIZE\n"
           f"    for this fragment. VOXEL_SIZE = {max_dim_m / 500:.4f} gives 500 voxels\n"
           f"    across and about 750,000 faces, which is coarser than the rest of\n"
           f"    the corpus and makes this fragment's geometry not directly\n"
           f"    comparable. Record that if you use it.\n")
        + f"\n    Do not continue as-is: this mesh is too coarse for region "
        f"segmentation or surface classification."
    )
print(f"  ✓  Voxel remesh OK  ({_poly_count:,} faces)")


# ── 4: Make remesh material independent ───────────────────────────────────────

mat_orig          = obj.material_slots[0].material
mat_remesh        = mat_orig.copy()
mat_remesh.name   = f"{FRAG_ID}_mat"
obj.material_slots[0].material = mat_remesh
print(f"  ✓  Material copy: '{mat_remesh.name}'")


# ── 5: Smart UV on remesh ─────────────────────────────────────────────────────

smart_uv_project(obj)
print(f"  ✓  Smart UV on remesh  (angle_limit=89°)")


# ── 6: Bake — source → remesh ─────────────────────────────────────────────────
# "Selected to Active" bake: casts rays from remesh surface toward source and
# reads the source colour at each ray-hit point via the source shader.
#
# Colour is read by shader evaluation at a specific 3D surface point — not by
# UV lookup from the target. This means overlapping Scaniverse UV does NOT cause
# wrong colour output. Self-bake is therefore not needed and is omitted to avoid
# the active_render UV mismatch bug it introduced (setting active_render=CleanUV
# before confirming tex_node was found caused wrong UV sampling on all meshes
# where find_base_color_tex_node returned None).

print(f"\n  ── Bake  (source → remesh) ─────────────────────────────")
source.hide_viewport = False
source.hide_render   = False

bake_node, bake_img = add_blank_image_node(
    mat_remesh, f"{FRAG_ID}_bake", location=(-200, 300)
)

deselect_all()
source.select_set(True)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

set_bake_mode(selected_to_active=True)
print(f"  Baking...  [{BAKE_RES}×{BAKE_RES}, extrusion {EXTRUSION * 1000:.0f} mm]")
bpy.ops.object.bake(type='DIFFUSE')
print(f"  ✓  Bake done")


# ── 8: Save texture ───────────────────────────────────────────────────────────

tex_path = os.path.join(out_dir, f"{FRAG_ID}_texture.png")
bake_img.file_format  = 'PNG'
bake_img.filepath_raw = tex_path
bake_img.save()
print(f"  ✓  Texture saved → {tex_path}")


# ── 9: Wire baked texture to Base Color ───────────────────────────────────────

set_active(obj)
if wire_to_base_color(mat_remesh, bake_node):
    print(f"  ✓  Baked texture wired to Base Color")
else:
    print(f"  ⚠  Principled BSDF not found — wire to Base Color manually")


# ── 10: Export GLB ────────────────────────────────────────────────────────────

set_active(obj)

glb_path = os.path.join(out_dir, f"{FRAG_ID}.glb")
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
    _glb_size_kb = os.path.getsize(glb_path) / 1024
    print(f"  ✓  GLB saved → {glb_path}")
    print(f"     File size: {_glb_size_kb:.1f} KB")
    if _glb_size_kb < 10:
        print(f"  ⚠  GLB is very small ({_glb_size_kb:.1f} KB) — mesh data may be missing")
else:
    print(f"  ✗  GLB export FAILED (operator returned {result})")
    raise RuntimeError("GLB export failed — check System Console for details")


# ── Done ──────────────────────────────────────────────────────────────────────

# Leave the untouched import visible at the end: it is the thing to go back to
# for a re-export, and a hidden object is easy to forget you still have.
source.hide_viewport = False
obj.hide_viewport    = True    # hide the remesh so the two do not overlap in view
print(f"\n  The original import is back in the viewport as '{source.name}'.")
print(f"  The remeshed copy '{obj.name}' is hidden; unhide it with Alt+H if needed.")

print(f"\n{'='*56}")
print(f"  Done!")
print(f"  Outputs in 01_input/meshes/processed/{FRAG_ID}/:")
print(f"    {FRAG_ID}.glb")
print(f"    {FRAG_ID}_texture.png")
if _sidecar_data:
    print(f"    {FRAG_ID}_scan_coverage.json  ← UNSCANNED face recorded")
print(f"  Verify: Z → Material Preview")
print(f"  If black patches: set EXTRUSION = 0.10 and re-run")
print(f"  If point cloud:   set VOXEL_SIZE = 0.005 and re-run")
print(f"  Next steps:")
print(f"    python 03_src/run_pipeline.py {FRAG_ID}")
if _sidecar_data:
    print(f"    python 03_src/scan_coverage.py {FRAG_ID}  ← annotate unscanned face")
print(f"{'='*56}\n")
