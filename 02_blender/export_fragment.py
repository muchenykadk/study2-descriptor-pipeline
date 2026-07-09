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

print(f"\n── Exporting {FRAG_ID} ──────────────────────────────")
print(f"   Object : {obj_active.name}")
print(f"   To     : {out_dir}\n")

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

tex_image = None
for slot in obj_active.material_slots:
    mat = slot.material
    if mat and mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                tex_image = node.image
                break
    if tex_image:
        break

if tex_image:
    png_path = os.path.join(out_dir, f"{FRAG_ID}_texture.png")
    # Save without changing the image's internal state permanently
    orig_format   = tex_image.file_format
    orig_filepath = tex_image.filepath_raw
    tex_image.file_format  = 'PNG'
    tex_image.filepath_raw = png_path
    tex_image.save()
    tex_image.file_format  = orig_format
    tex_image.filepath_raw = orig_filepath
    print(f"✓ Texture → {png_path}")
else:
    print("⚠ No image texture found in material — PNG not saved.")
    print("  Make sure the material has an Image Texture node connected.")

print(f"\n── Done. Next step ──────────────────────────────────")
print(f"   In PowerShell:")
print(f'   env\\venv\\Scripts\\activate')
print(f"   python 03_src/run_pipeline.py {FRAG_ID}")
