"""
Blender export script — Study 2 Descriptor Pipeline
====================================================
Exports OBJ, GLB, and texture PNG for one fragment in one run.

How to use
----------
1. Open Blender Scripting workspace (top menu: Scripting tab)
2. Open this file: Text Editor → Open → browse to this file
3. Change FRAG_ID below to match the fragment you are exporting
4. Select the cleaned mesh object in the viewport
5. Click Run Script (▶)

Files created
-------------
01_input/meshes/processed/FRAG-S1-XXX/
    FRAG-S1-XXX.obj          ← geometry for Python pipeline
    FRAG-S1-XXX.glb          ← Rhino import (texture embedded)
    FRAG-S1-XXX_texture.png  ← texture for AI vision analysis

After export
------------
Run the pipeline from PowerShell:
    env\\venv\\Scripts\\activate
    python 03_src/run_pipeline.py FRAG-S1-XXX
"""

import bpy
import os

# ── Configuration — change this for each new fragment ────────────────────────

FRAG_ID = "FRAG-S1-002"

REPO_ROOT = r"C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"

# ── Setup ─────────────────────────────────────────────────────────────────────

out_dir = os.path.join(REPO_ROOT, "01_input", "meshes", "processed", FRAG_ID)
os.makedirs(out_dir, exist_ok=True)

obj_active = bpy.context.active_object
if obj_active is None or obj_active.type != 'MESH':
    raise RuntimeError("No mesh selected. Select the fragment mesh in the viewport first.")

# ── Unit scale → mm conversion ────────────────────────────────────────────────
# Pipeline expects OBJ coordinates in millimetres.
# This script detects the scene unit scale and converts automatically —
# no need to change the scene units or rescale your objects.
#
# unit_scale meaning:  1.0 = metres | 0.01 = centimetres | 0.001 = millimetres
unit_scale = bpy.context.scene.unit_settings.scale_length
scale_to_mm = unit_scale * 1000.0   # e.g. metres→mm: 1.0×1000=1000

print(f"\n── Exporting {FRAG_ID} ──────────────────────────────")
print(f"   Object    : {obj_active.name}")
print(f"   Unit scale: {unit_scale}  →  export scale ×{scale_to_mm:.1f} (to mm)")
print(f"   To        : {out_dir}\n")

# ── 1. Export OBJ (geometry for Python pipeline) ──────────────────────────────

obj_path = os.path.join(out_dir, f"{FRAG_ID}.obj")
try:
    # Blender 3.3+ new exporter
    bpy.ops.wm.obj_export(
        filepath=obj_path,
        export_selected_objects=True,
        export_uv=True,
        export_normals=True,
        export_triangulated_mesh=True,
        forward_axis='NEGATIVE_Z',
        up_axis='Y',
        global_scale=scale_to_mm,
    )
except AttributeError:
    # Blender < 3.3 legacy exporter
    bpy.ops.export_scene.obj(
        filepath=obj_path,
        use_selection=True,
        use_uvs=True,
        use_normals=True,
        use_triangles=True,
        axis_forward='-Z',
        axis_up='Y',
        global_scale=scale_to_mm,
    )
print(f"✓ OBJ     → {obj_path}")

# ── 2. Export GLB (Rhino import, texture embedded) ────────────────────────────

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
print(f"✓ GLB     → {glb_path}")

# ── 3. Save texture PNG (AI vision analysis) ──────────────────────────────────
#
# Searches all nodes including inside node groups (e.g. Blender's BASE COLOR
# group). Picks the image with the largest pixel count if multiple are found
# — that's almost always the baked texture rather than a small utility image.

def _collect_images(node_tree):
    """Recursively collect all (image, node_name) from a node tree."""
    found = []
    for node in node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            found.append((node.image, node.name))
        elif node.type == 'GROUP' and node.node_tree:
            found.extend(_collect_images(node.node_tree))
    return found

def _save_image(image, path):
    """Save a Blender image to disk regardless of whether it has a filepath."""
    orig_format   = image.file_format
    orig_filepath = image.filepath_raw
    image.file_format  = 'PNG'
    image.filepath_raw = path
    try:
        image.save()
    except Exception:
        # Fallback for freshly-baked in-memory images
        image.save_render(path, scene=bpy.context.scene)
    image.file_format  = orig_format
    image.filepath_raw = orig_filepath

tex_image = None
all_images = []
for slot in obj_active.material_slots:
    mat = slot.material
    if mat and mat.use_nodes:
        all_images.extend(_collect_images(mat.node_tree))

if all_images:
    if len(all_images) == 1:
        tex_image = all_images[0][0]
    else:
        # Pick the largest image (baked texture is usually biggest)
        tex_image = max(all_images, key=lambda x: x[0].size[0] * x[0].size[1])[0]
    print(f"   Texture found: '{tex_image.name}'  ({tex_image.size[0]}×{tex_image.size[1]})")

if tex_image:
    png_path = os.path.join(out_dir, f"{FRAG_ID}_texture.png")
    _save_image(tex_image, png_path)
    print(f"✓ Texture → {png_path}")
else:
    print("⚠ No image texture found in material — PNG not saved.")
    print("  Make sure the material has an Image Texture node (or BASE COLOR group).")

print(f"\n── Done. Next step ──────────────────────────────────")
print(f"   In PowerShell:")
print(f'   env\\venv\\Scripts\\activate')
print(f"   python 03_src/run_pipeline.py {FRAG_ID}")
