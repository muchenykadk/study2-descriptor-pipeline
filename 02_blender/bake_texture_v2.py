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
BAKE_RES   = 1080     # texture resolution (pixels)
EXTRUSION  = 0.05     # metres — increase to 0.10 if bake has black patches
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
    bpy.ops.uv.smart_project(island_margin=0.02, angle_limit=89)
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

if obj.scale.x != 1.0 or obj.scale.y != 1.0 or obj.scale.z != 1.0:
    print(f"  ⚠  UNAPPLIED SCALE detected — apply before baking:")
    print(f"     Object Mode → Ctrl+A → Apply → Scale")

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


# ── 2: Duplicate → rename → hide (becomes bake source) ────────────────────────

set_active(obj)
bpy.ops.object.duplicate()
source = bpy.context.active_object    # duplicate is now active
source.name          = f"{FRAG_ID}_source"
source.hide_viewport = True
source.hide_render   = False          # must remain renderable for baking
print(f"\n  ✓  Bake source: '{source.name}'  (hidden)")

# Switch back to original → this becomes the remesh target
set_active(obj)
obj.name = f"{FRAG_ID}_remesh"
print(f"  ✓  Remesh target: '{obj.name}'")


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

print(f"\n  ── Voxel remesh ─────────────────────────────────────────")
print(f"     Voxel size : {VOXEL_SIZE * 1000:.1f} mm  ({VOXEL_SIZE} m)")
print(f"     Mesh size  : {max_dim_m * 1000:.0f} mm  →  ~{int(max_dim_m / VOXEL_SIZE)} voxels across longest axis")

mod              = obj.modifiers.new(name="Remesh", type='REMESH')
mod.mode         = 'VOXEL'
mod.voxel_size   = VOXEL_SIZE
mod.use_smooth_shade = True
_apply_result = bpy.ops.object.modifier_apply(modifier=mod.name)
print(f"     modifier_apply returned: {_apply_result}")

# Sanity check — catch point cloud or empty remesh
_poly_count = len(obj.data.polygons)
_vert_count = len(obj.data.vertices)
_dims_after = obj.dimensions
print(f"     After remesh: {_vert_count:,} vertices  {_poly_count:,} faces")
print(f"     Dimensions  : X={_dims_after.x:.4f}  Y={_dims_after.y:.4f}  Z={_dims_after.z:.4f}")

if _poly_count == 0:
    raise RuntimeError(
        f"Voxel remesh produced 0 faces (point cloud). "
        f"VOXEL_SIZE={VOXEL_SIZE} may be wrong for this mesh. "
        f"Try VOXEL_SIZE = {max_dim_m / 200:.4f} (1/200th of max dim)."
    )
elif _poly_count < 100:
    print(f"  ⚠  Only {_poly_count} faces — remesh is very coarse. "
          f"VOXEL_SIZE may be too large for this mesh scale.")
else:
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

source.hide_viewport = True   # tidy up

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
