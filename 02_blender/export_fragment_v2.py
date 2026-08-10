"""
export_fragment_v2.py — Study 2 Descriptor Pipeline
=====================================================
Exports GLB and texture PNG for one fragment in one run.

Changes from export_fragment.py
---------------------------------
  Step 0.5 (NEW): Before export, reads the "UNSCANNED" vertex group from
  the mesh if it exists. Extracts the average face normal and centroid of
  those faces and writes them to a sidecar JSON:
      01_input/meshes/processed/{FRAG_ID}/{FRAG_ID}_scan_coverage.json

  Unlike bake_texture_v2.py, there is no remesh step here — the mesh
  topology is intact, so the vertex group can be read at any point.
  The sidecar is read by scan_coverage.py after run_pipeline.py finishes.

  Original export_fragment.py is unchanged and still works for all
  existing fragments.

How to use
----------
1. Open Blender Scripting workspace (top menu: Scripting tab)
2. Open this file: Text Editor → Open → browse to this file
3. Change FRAG_ID below to match the fragment you are exporting
4. (NEW) Assign "UNSCANNED" vertex group to manually-closed faces:
       Edit Mode → select ground-contact faces (Shift+G → Normal)
       → Object Data Properties → Vertex Groups → + → name "UNSCANNED" → Assign
5. Select the cleaned mesh object in the viewport
6. Click Run Script (▶)

After export
------------
Run the pipeline from PowerShell:
    env\\venv\\Scripts\\activate
    python 03_src/run_pipeline.py FRAG-S1-FS-003
    python 03_src/scan_coverage.py FRAG-S1-FS-003   ← NEW: annotate unscanned face

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
    FRAG-S1-{ARCHETYPE}-{###}.glb               ← mesh + UV
    FRAG-S1-{ARCHETYPE}-{###}_texture.png        ← albedo for AI vision
    FRAG-S1-{ARCHETYPE}-{###}_scan_coverage.json ← NEW: unscanned face metadata
"""

import bpy
import json
import os
import mathutils

# ── Configuration — change this for each new fragment ────────────────────────
FRAG_ID = "FRAG-S1-FS-003"

REPO_ROOT = r"C:\Users\muche\Documents\Austria\Research\Research Concrete upcycling\Study2_Descriptor_Pipeline"

# ── Setup ─────────────────────────────────────────────────────────────────────

out_dir = os.path.join(REPO_ROOT, "01_input", "meshes", "processed", FRAG_ID)
os.makedirs(out_dir, exist_ok=True)

obj_active = bpy.context.active_object
if obj_active is None or obj_active.type != 'MESH':
    raise RuntimeError("No mesh selected. Select the fragment mesh in the viewport first.")

print(f"\n── export_fragment_v2.py  {FRAG_ID} ─────────────────────")
print(f"   Object : {obj_active.name}")
print(f"   To     : {out_dir}\n")


# ── 0.5: Read UNSCANNED vertex group (NEW in v2) ──────────────────────────────
# Unlike bake_texture_v2.py, there is no remesh step here, so the vertex group
# can be read at any point. We do it first so the sidecar is always written
# even if the export step fails.

vg = obj_active.vertex_groups.get("UNSCANNED")
unscanned_written = False

if vg:
    vg_idx = vg.index
    normals, centers = [], []
    for face in obj_active.data.polygons:
        in_group = any(
            any(g.group == vg_idx for g in obj_active.data.vertices[v].groups)
            for v in face.vertices
        )
        if in_group:
            normals.append(face.normal.copy())
            centers.append(face.center.copy())

    if normals:
        avg_n = sum(normals, mathutils.Vector()) / len(normals)
        avg_c = sum(centers, mathutils.Vector()) / len(centers)
        avg_n = avg_n.normalized()

        sidecar = {
            "has_unscanned_face": True,
            "avg_normal": [round(float(x), 4) for x in avg_n],
            "avg_center": [round(float(x), 4) for x in avg_c],
            "face_count": len(normals),
            "notes": "Ground-contact face — manually closed hole from photogrammetry scan",
        }
        sidecar_path = os.path.join(out_dir, f"{FRAG_ID}_scan_coverage.json")
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2)

        unscanned_written = True
        print(f"✓ Scan coverage → {FRAG_ID}_scan_coverage.json")
        print(f"  {len(normals)} faces  |  avg normal "
              f"[{avg_n.x:.3f}, {avg_n.y:.3f}, {avg_n.z:.3f}]")
    else:
        print(f"⚠ 'UNSCANNED' vertex group found but contains no faces — sidecar skipped")
else:
    print(f"─  No 'UNSCANNED' vertex group found — scan coverage not recorded")
    print(f"   (Select ground-contact faces → Vertex Groups → UNSCANNED → Assign)")


# ── Unit scale → mm conversion ────────────────────────────────────────────────

unit_scale = bpy.context.scene.unit_settings.scale_length
scale_to_mm = unit_scale * 1000.0

print(f"\n   Unit scale: {unit_scale}  →  export scale ×{scale_to_mm:.1f} (to mm)")


# ── 1. Export GLB ─────────────────────────────────────────────────────────────

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


# ── 2. Save texture PNG ────────────────────────────────────────────────────────

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
        image.save_render(path, scene=bpy.context.scene)
    image.file_format  = orig_format
    image.filepath_raw = orig_filepath

def _find_base_color_image(mat):
    """Return the image plugged into Base Color of Principled BSDF, if any."""
    if not (mat and mat.use_nodes):
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bc_input = node.inputs.get("Base Color")
            if bc_input and bc_input.is_linked:
                linked = bc_input.links[0].from_node
                if linked.type == 'TEX_IMAGE' and linked.image:
                    return linked.image
                if linked.type == 'GROUP' and linked.node_tree:
                    imgs = _collect_images(linked.node_tree)
                    if imgs:
                        return max(imgs, key=lambda x: x[0].size[0] * x[0].size[1])[0]
    return None

tex_image = None
all_images = []
for slot in obj_active.material_slots:
    mat = slot.material
    tex_image = _find_base_color_image(mat)
    if tex_image:
        break
    if mat and mat.use_nodes:
        all_images.extend(_collect_images(mat.node_tree))

if not tex_image and all_images:
    if len(all_images) == 1:
        tex_image = all_images[0][0]
    else:
        tex_image = max(all_images, key=lambda x: x[0].size[0] * x[0].size[1])[0]
    print(f"   ⚠ No Base Color connection found — using largest image as fallback")

if tex_image:
    print(f"   Texture: '{tex_image.name}'  ({tex_image.size[0]}×{tex_image.size[1]})")
    png_path = os.path.join(out_dir, f"{FRAG_ID}_texture.png")
    _save_image(tex_image, png_path)
    print(f"✓ Texture → {png_path}")
else:
    print("⚠ No image texture found in material — PNG not saved.")
    print("  Make sure the material has an Image Texture node.")


# ── Done ──────────────────────────────────────────────────────────────────────

print(f"\n── Done. Next steps ─────────────────────────────────")
print(f"   In PowerShell:")
print(f"   env\\venv\\Scripts\\activate")
print(f"   python 03_src/run_pipeline.py {FRAG_ID}")
if unscanned_written:
    print(f"   python 03_src/scan_coverage.py {FRAG_ID}   ← annotate unscanned face")
