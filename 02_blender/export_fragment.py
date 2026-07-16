"""
Blender export script — Study 2 Descriptor Pipeline
====================================================
Exports GLB and texture PNG for one fragment in one run.

How to use
----------
1. Open Blender Scripting workspace (top menu: Scripting tab)
2. Open this file: Text Editor → Open → browse to this file
3. Change FRAG_ID below to match the fragment you are exporting
4. Select the cleaned mesh object in the viewport
5. Click Run Script (▶)

Fragment ID format
------------------
FRAG-S1-{ARCHETYPE}-{###}

Archetype codes (assigned at physical inspection):
    FS  Floor Slab        RS  Roof Slab        BM  Beam
    CO  Column            WL  Load-bearing Wall WP  Partition Wall
    LT  Lintel            ST  Stair             BL  Balcony
    FP  Facade Panel      FD  Foundation        UN  Unidentified

Examples: FRAG-S1-FS-003, FRAG-S1-CO-001, FRAG-S1-BM-001

Files created
-------------
01_input/meshes/processed/FRAG-S1-{ARCHETYPE}-{###}/
    FRAG-S1-{ARCHETYPE}-{###}.glb          ← mesh + UV (geometry input + 3D viewer)
    FRAG-S1-{ARCHETYPE}-{###}_texture.png  ← rebaked albedo (AI vision analysis)

After export
------------
Run the pipeline from PowerShell:
    env\\venv\\Scripts\\activate
    python 03_src/run_pipeline.py FRAG-S1-FS-003
"""

import bpy
import os

# ── Configuration — change this for each new fragment ────────────────────────
# Format: FRAG-S1-{ARCHETYPE}-{###}
# Assign archetype at physical inspection (see docstring for codes).
FRAG_ID = "FRAG-S1-FS-003"

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

# ── 1. Export GLB (pipeline geometry input + 3D viewer) ──────────────────────

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

# ── 2. Save texture PNG (AI vision analysis) ──────────────────────────────────
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

def _find_base_color_image(mat):
    """
    Return the image plugged into Base Color of the Principled BSDF, if any.
    This avoids accidentally exporting a normal map or roughness texture.
    """
    if not (mat and mat.use_nodes):
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bc_input = node.inputs.get("Base Color")
            if bc_input and bc_input.is_linked:
                linked = bc_input.links[0].from_node
                if linked.type == 'TEX_IMAGE' and linked.image:
                    return linked.image
                # Handle node groups (e.g. BASE COLOR group)
                if linked.type == 'GROUP' and linked.node_tree:
                    imgs = _collect_images(linked.node_tree)
                    if imgs:
                        return max(imgs, key=lambda x: x[0].size[0] * x[0].size[1])[0]
    return None

tex_image = None
all_images = []
for slot in obj_active.material_slots:
    mat = slot.material
    # Prefer the image connected to Base Color — avoids normal/roughness maps
    tex_image = _find_base_color_image(mat)
    if tex_image:
        break
    if mat and mat.use_nodes:
        all_images.extend(_collect_images(mat.node_tree))

if not tex_image and all_images:
    if len(all_images) == 1:
        tex_image = all_images[0][0]
    else:
        # Fallback: pick the largest image
        tex_image = max(all_images, key=lambda x: x[0].size[0] * x[0].size[1])[0]
    print(f"   ⚠ No Base Color connection found — using largest image as fallback")

if tex_image:
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
