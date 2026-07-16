"""
bake_texture.py — Study 2 Descriptor Pipeline
==============================================
Automates Stage 3 + 4 of the Blender workflow:
  scale check → duplicate → remesh → UV → bake → save texture → export GLB

Manual step BEFORE:
  1. Clean the mesh (delete floor plane, stray artifacts)

Manual step AFTER:
  2. Verify result: press Z → Material Preview in viewport
  3. Run the pipeline: python 03_src/run_pipeline.py FRAG-S1-{ARCHETYPE}-{###}

How to use
----------
1. Set FRAG_ID below
2. Clean the mesh manually (floor, artifacts)
3. Select the cleaned mesh in the viewport
4. Click ▶ Run Script

SELF_BAKE flag
--------------
  False (default) — one bake pass: source → remesh. Fast.
                    Use for clean Scaniverse exports.
  True  — two bake passes: self-bake source to clean UV first,
          then bake to remesh. Slower but fixes messy/overlapping
          Scaniverse UV islands.
"""

import bpy
import os

# ── Configuration ──────────────────────────────────────────────────────────────
FRAG_ID    = "FRAG-S1-FS-003"
VOXEL_SIZE = 0.002    # metres — 2 mm; increase for noisy scans
BAKE_RES   = 1080     # texture resolution (pixels)
EXTRUSION  = 0.05     # metres — increase to 0.10 if bake has black patches
SELF_BAKE  = True    # True = fix messy Scaniverse UV first (slower)
REPO_ROOT  = r"C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"


# ── Helpers ────────────────────────────────────────────────────────────────────

def deselect_all():
    bpy.ops.object.select_all(action='DESELECT')

def set_active(obj):
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def smart_uv_project(obj):
    """Apply Smart UV Project to all faces of obj."""
    set_active(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

def add_blank_image_node(mat, name, location=(0, 0)):
    """
    Add an Image Texture node to mat with a new blank 4096×4096 image.
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

def find_base_color_tex_node(mat):
    """Return the Image Texture node at Base Color of Principled BSDF, or None."""
    nodes = mat.node_tree.nodes
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        return None
    bc_links = principled.inputs['Base Color'].links
    if not bc_links:
        return None
    candidate = bc_links[0].from_node
    if candidate.type == 'TEX_IMAGE':
        return candidate
    if candidate.type == 'GROUP':
        # Search inside the node group
        for n in candidate.node_tree.nodes:
            if n.type == 'TEX_IMAGE':
                return n
    return None

def set_bake_mode(selected_to_active):
    bpy.context.scene.render.engine = 'CYCLES'
    bake = bpy.context.scene.render.bake
    bake.use_pass_direct        = False
    bake.use_pass_indirect      = False
    bake.use_pass_color         = True
    bake.use_selected_to_active = selected_to_active
    if selected_to_active:
        bake.cage_extrusion = EXTRUSION


# ── 0: Validate active object ──────────────────────────────────────────────────

obj = bpy.context.active_object
if obj is None or obj.type != 'MESH':
    raise RuntimeError("No mesh selected. Select the cleaned mesh and run again.")
if not obj.material_slots or not obj.material_slots[0].material:
    raise RuntimeError(f"'{obj.name}' has no material. Import the GLB with texture first.")

print(f"\n{'='*56}")
print(f"  bake_texture.py  —  {FRAG_ID}")
print(f"{'='*56}")
print(f"  Mesh : {obj.name}")


# ── 1: Scale check ─────────────────────────────────────────────────────────────

max_dim = max(obj.dimensions)
print(f"  Max dim: {max_dim:.4f}  ({max_dim*1000:.1f} mm if in metres)")

if max_dim < 0.01:
    raise RuntimeError(
        f"Max dimension {max_dim:.4f} is extremely small. "
        "Apply scale manually: S → 1000 → Enter → Object → Apply → Scale."
    )
elif max_dim < 0.05:
    print(f"  ⚠  Very small — check scale before continuing.")
elif max_dim > 5.0:
    print(f"  ⚠  Very large — check if units are set correctly.")
else:
    print(f"  ✓  Scale OK")


# ── 2: Duplicate → rename → hide (becomes bake source) ────────────────────────

set_active(obj)
bpy.ops.object.duplicate()
source = bpy.context.active_object    # duplicate is now active
source.name          = f"{FRAG_ID}_source"
source.hide_viewport = True
source.hide_render   = False          # must remain renderable for baking
print(f"\n  ✓  Bake source: '{source.name}'  (hidden)")

# Switch back to original → this becomes the remesh
set_active(obj)
obj.name = f"{FRAG_ID}_remesh"
print(f"  ✓  Remesh target: '{obj.name}'")


# ── 3: Voxel remesh ───────────────────────────────────────────────────────────

mod              = obj.modifiers.new(name="Remesh", type='REMESH')
mod.mode         = 'VOXEL'
mod.voxel_size   = VOXEL_SIZE
mod.use_smooth_shade = True
bpy.ops.object.modifier_apply(modifier=mod.name)
print(f"  ✓  Voxel remesh applied  ({VOXEL_SIZE * 1000:.0f} mm voxels)")


# ── 4: Make remesh material independent ───────────────────────────────────────

mat_orig          = obj.material_slots[0].material
mat_remesh        = mat_orig.copy()
mat_remesh.name   = f"{FRAG_ID}_mat"
obj.material_slots[0].material = mat_remesh
print(f"  ✓  Material copy: '{mat_remesh.name}'")


# ── 5: Smart UV on remesh ─────────────────────────────────────────────────────

smart_uv_project(obj)
print(f"  ✓  Smart UV on remesh")


# ── 6: Self-bake (optional) ───────────────────────────────────────────────────
# Fixes messy/overlapping Scaniverse UVs before the main bake.
# Only needed when the Scaniverse UV is broken (overlapping islands, wrong seams).

if SELF_BAKE:
    print(f"\n  ── Self-bake  (SELF_BAKE = True) ──────────────────────")
    source.hide_viewport = False

    # Store original UV name before adding CleanUV
    orig_uv_name = source.data.uv_layers[0].name
    print(f"     Original UV: '{orig_uv_name}'")

    # Add CleanUV and apply Smart UV
    set_active(source)
    clean_uv = source.data.uv_layers.new(name="CleanUV")
    source.data.uv_layers.active = clean_uv
    smart_uv_project(source)
    set_active(source)

    # Set CleanUV as the render-active UV (bake writes here)
    for uv in source.data.uv_layers:
        uv.active_render = (uv.name == "CleanUV")

    # Pin existing texture to original UV in the shader
    src_mat   = source.material_slots[0].material
    src_nodes = src_mat.node_tree.nodes
    src_links = src_mat.node_tree.links
    tex_node  = find_base_color_tex_node(src_mat)

    if tex_node:
        uv_node          = src_nodes.new('ShaderNodeUVMap')
        uv_node.uv_map   = orig_uv_name
        uv_node.location = (tex_node.location[0] - 250, tex_node.location[1] - 100)
        src_links.new(uv_node.outputs['UV'], tex_node.inputs['Vector'])
        print(f"     UV Map node pinned to '{orig_uv_name}'")
    else:
        print(f"     ⚠  Texture node not found — UV pin skipped")

    # Add blank self-bake target image node (unconnected, selected)
    sb_node, sb_img = add_blank_image_node(
        src_mat, f"{FRAG_ID}_cleanbake", location=(-200, -400)
    )

    # Run self-bake
    set_bake_mode(selected_to_active=False)
    set_active(source)
    print(f"     Baking (self)...  [{BAKE_RES}×{BAKE_RES}]")
    bpy.ops.object.bake(type='DIFFUSE')
    print(f"     ✓  Self-bake done")

    source.hide_viewport = True


# ── 7: Main bake — source → remesh ────────────────────────────────────────────

print(f"\n  ── Main bake  (source → remesh) ────────────────────────")
source.hide_viewport = False
source.hide_render   = False

# Add blank bake target node on remesh material (unconnected, selected)
bake_node, bake_img = add_blank_image_node(
    mat_remesh, f"{FRAG_ID}_bake", location=(-200, 300)
)

# Selection: source selected but NOT active; remesh = active (target)
deselect_all()
source.select_set(True)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

set_bake_mode(selected_to_active=True)
print(f"  Baking...  [{BAKE_RES}×{BAKE_RES}, extrusion {EXTRUSION * 1000:.0f} mm]")
bpy.ops.object.bake(type='DIFFUSE')
print(f"  ✓  Bake done")


# ── 8: Save texture ───────────────────────────────────────────────────────────

out_dir  = os.path.join(REPO_ROOT, "01_input", "meshes", "processed", FRAG_ID)
os.makedirs(out_dir, exist_ok=True)
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

set_active(obj)   # remesh must be the active selected object for use_selection=True

glb_path = os.path.join(out_dir, f"{FRAG_ID}.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_path,
    export_format='GLB',
    use_selection=True,
    export_texcoords=True,
    export_normals=True,
    export_materials='EXPORT',
    export_image_format='AUTO',
)
print(f"  ✓  GLB saved → {glb_path}")


# ── Done ──────────────────────────────────────────────────────────────────────

source.hide_viewport = True   # tidy up

print(f"\n{'='*56}")
print(f"  Done!")
print(f"  Outputs:")
print(f"    {FRAG_ID}.glb")
print(f"    {FRAG_ID}_texture.png")
print(f"  Verify: Z → Material Preview")
print(f"  If black patches: set EXTRUSION = 0.10 and re-run")
print(f"  Next: run the pipeline")
print(f"    python 03_src/run_pipeline.py {FRAG_ID}")
print(f"{'='*56}\n")
