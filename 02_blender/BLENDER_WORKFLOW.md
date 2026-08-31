# Blender Workflow — Fragment Processing
Study 2 Descriptor Pipeline

Complete step-by-step workflow from Scaniverse export to pipeline-ready GLB + texture.

> **Use the script, not the manual stages.** `02_blender/bake_texture_v2.py` does Stages 3
> and 4 in one run and writes the `UNSCANNED` sidecar. Stages 3–4 below are the manual
> fallback and the explanation of what the script does. The parts you still do by hand are
> **Stage 2 (clean)** and **Stage 2.5 (mark UNSCANNED)**.

---

## Stage 0 — Check the export before you use it

```powershell
python 03_src/preflight.py FRAG-S1-{ARCHETYPE}-{###}
```

This runs automatically at the start of every pipeline run, but run it yourself straight
after the Blender export: it takes seconds and tells you whether to go back into Blender
before anything else happens.

**`FRAG_ID` is the one to watch.** It is hand-edited before every bake and nothing
downstream can verify it. Leaving it unchanged from the previous fragment silently
overwrites that fragment's export, which is how FS-003's mesh was lost and how a 1630 mm
slab ended up in FS-002's folder. Both of those exports were internally perfect and every
check passed, because the checks ask whether the mesh is good, not whether it is the right
mesh. `preflight` now also compares the export's oriented bounding box against the record
and warns above 15% drift, but that only works while the record still describes the right
piece: once a wrong export has been processed, the record agrees with it.

The things it checks that you can also see by eye:

**1. Units before remesh.** Blender's Voxel Size is in scene units. `VOXEL_SIZE = 0.002`
means 2 mm only if the object measures ~1.6 *units*, not ~1600. Press **N** and read
Dimensions. If it shows hundreds or thousands, the object is in millimetres and the voxel
size is wrong by 1000×.

**2. Face count after remesh.** Expect roughly `3 × (longest_dimension / voxel_size)²`.
A 1.6 m fragment at 2 mm voxels gives about 2 million faces. FRAG-S1-FS-003 came out at
**3,016** and was exported anyway; it produced planes matching under 4% of its geometry and
no surface classification at all. `bake_texture_v2.py` now raises below 20% of expected,
but check the number yourself in the Statistics overlay.

**3. Texel density in the finished atlas.** Not the atlas resolution: pixels of atlas per
millimetre of real surface, which is what decides whether the model can see anything. Two
settings starve it independently. `BAKE_RES` must be **4096**, and the Smart UV Project
island margin must be **0.002**, because that value is a *fraction of the sheet*, not a
pixel count: at 0.02 only 20% of the atlas carried any UV at all and the rest was packing
waste. Below about 0.5 px/mm an island of a few faces averages to one colour and the bake
margin bleeds it into a flat diamond, which is the mottled texture seen on FS-001 and
FS-002. Both values are set in the script; `preflight` reports the resulting density and
fails below 0.50.

**4. Mark UNSCANNED before you fill the hole and move on.** See Stage 2.5.

---

## Stage 1 — Scan (Scaniverse on iPhone/iPad)

1. Open Scaniverse → tap **New Scan**
2. Scan the fragment from all angles — top, all four sides, bottom if accessible. Aim for 2–3 slow passes.
3. Tap stop → Scaniverse processes the scan (LiDAR + photogrammetry fusion)
4. Tap **Export → GLB** → Share → Files → save to iCloud Drive or AirDrop to PC
5. Place the file in the project:
   ```
   01_input/photogrammetry/raw_exports/FRAG-S1-{ARCHETYPE}-{###}/
   ```
   Never rename or overwrite this file — it is the permanent archive.

---

## Stage 2 — Blender: Import and Clean

**Open Blender.**

### Import
1. **File → Import → glTF 2.0 (.glb/.gltf)**
2. Select the GLB from `01_input/photogrammetry/raw_exports/FRAG-S1-{ARCHETYPE}-{###}/`
3. The mesh appears with the Scaniverse texture already applied.

### Orient the view
4. Press **Numpad 5** (toggle orthographic), **Numpad 1** (front view)

### Clean the mesh
5. Press **Tab** → Edit Mode. Press **A** to select all. Press **Alt+Z** to toggle X-ray.
6. Delete the floor plane if Scaniverse captured the ground:
   - **B** to box-select the floor geometry → **X → Faces**
7. Delete any floating scan artifacts:
   - Select stray vertices → **X → Vertices**
8. Press **Tab** → back to Object Mode

### Check scale
9. Press **N** → side panel → **Item** tab → check **Dimensions**
   - Should be in hundreds of mm (e.g. 350 × 220 × 150 mm)
   - If it shows 0.35 × 0.22 × 0.15 (metres): **S → 1000 → Enter** to scale up

---

## Stage 2.5 — Close the ground-contact hole and mark it UNSCANNED

The fragment was scanned lying on the ground, so its underside was never photographed. The
hole has to be closed, and the closed patch has to be labelled, because everything
downstream will otherwise treat invented geometry as measured surface.

10. **Tab** → Edit Mode → **Edge select mode (2)**
11. Hover over the boundary of the hole → **Alt+Click** to select the whole edge loop
12. **F** to fill it
13. **The filled faces are still selected. Do not click away.**
14. Properties → **Object Data (green triangle) → Vertex Groups → `+`**
15. Rename the group exactly `UNSCANNED` (capitals, no spaces) → click **Assign**
16. Verify: **Alt+A** to deselect all → select the `UNSCANNED` group → click **Select**.
    The patch should highlight and nothing else should.
17. **Tab** → Object Mode

`bake_texture_v2.py` reads this group *before* the voxel remesh, because the remesh destroys
all original topology, and writes `{FRAG_ID}_scan_coverage.json` recording the patch's
average normal, centroid and face count. `run_pipeline.py` picks the sidecar up
automatically.

### Is this still needed now that smeared texture is detected automatically?

Yes, and for a different reason than originally.

The smear gate is a *texture* safety net. It catches a bake that failed, which is what
happens on an unmarked patch, and on FRAG-S1-FS-005 it caught exactly that: 90% of one face
was marbled nonsense.

`UNSCANNED` does something the smear gate cannot. **A manually filled hole is perfectly
flat.** RANSAC finds an excellent plane there, with a better fit RMS than any real face on
the fragment, and it is often the largest. Without the flag it ranks as the best bolting
surface the piece has, and the design factors will happily propose it as a bench top. That
is a geometric error and no amount of texture analysis will catch it, because the mistake is
in the shape, not the image.

So the two are complementary: `UNSCANNED` declares the geometry invented, the smear gate
catches a bake that went wrong. Mark the group on every fragment. Only FS-003 and FS-006
currently have it.

---

## Stage 3 — Blender: Remesh + UV + Bake

This is the core stage. The Scaniverse mesh has irregular photogrammetry topology and messy UV coordinates. We remesh it into clean geometry and rebake the texture onto the new UV.

### A — Duplicate the mesh (preserve bake source)

10. Object Mode, mesh selected → **Shift+D → Esc** (duplicate in place)
    - You now have two objects: the original and a duplicate (duplicate is currently active)
11. Press **H** to hide the duplicate
    - The hidden duplicate = **bake source** (keeps the original Scaniverse texture intact)
    - The visible original = **remesh target** (you will apply Voxel Remesh to this)

### B — Remesh the visible mesh

12. Object Mode → **Properties panel (right side) → Modifier (wrench icon) → Add Modifier → Remesh**
13. Set mode to **Voxel**
14. Set **Voxel Size** to **0.002 m** (= 2 mm). Increase to 0.003 if too slow or too detailed.
15. Enable **Smooth Shading**
16. Click **Apply**
    - Result: clean, uniform, closed mesh topology

### C — Make the remesh material independent

17. Remesh still selected → **Properties → Material (sphere icon)**
18. Next to the material name, there is a number (e.g. **2**) — click it
    - Blender creates a copy of the material for the remesh only
19. Click the material name field and rename it: `FRAG-S1-{ARCHETYPE}-{###}_remesh`
    - Now the two objects have separate materials and can be edited independently

### D — Add Smart UV to the remesh

20. Still on the remesh → **Tab** → Edit Mode → **A** to select all
21. **U → Smart UV Project** → Island Margin: 0.02 → **OK**
22. **Tab** → back to Object Mode

### E — Prepare the bake source (hidden duplicate)

23. Press **Alt+H** to unhide the duplicate (the bake source)
24. **Click the bake source** to select it (single click — deselect remesh first with Alt+A)

### F — Fix the bake source UV (self-bake to clean UV)

The Scaniverse UV is often messy — overlapping islands, wrong seams. We create a clean UV on the bake source and remap the texture onto it, so it works correctly as the source for the final bake.

25. Bake source selected → **Properties → Object Data (green triangle icon) → UV Maps → click +**
    - A new UV map appears in the list — rename it `CleanUV`
26. **Tab** → Edit Mode → **A** → **U → Smart UV Project → OK** → **Tab** → Object Mode
    - This writes a clean UV layout into the new `CleanUV` slot

27. Open the **Shader Editor** (change one panel's type to Shader Editor)
    - You should see the Scaniverse material with a BASE COLOR / Image Texture node connected to the Principled BSDF
28. **Shift+A → Input → UV Map** — a small UV Map node appears
29. In the UV Map node dropdown: select the **original Scaniverse UV** (not CleanUV — the one that was there before, usually called `UVMap` or `Texture`)
    - Check Properties → Object Data → UV Maps to see its name
30. Drag from the **UV output** of the UV Map node → to the **Vector input** (small purple dot, left side) of the BASE COLOR / Image Texture node
    - This pins the texture read to the old UV, so switching the active UV to CleanUV won't break the display

31. **Shift+A → Texture → Image Texture** — a new blank Image Texture node appears
32. In the node: click **New** → Name: `CleanBake` → Width: **4096** → Height: **4096** → **OK**
33. Leave this node **unconnected** to anything — just click it once to keep it **selected** (highlighted yellow)
    - This tells Blender: bake into this image

34. Properties → Object Data → UV Maps → click `CleanUV` → click the **camera icon** next to it to make it the active render UV

35. **Properties → Render (camera icon) → Render Engine → Cycles**
36. Scroll down to **Bake** section:
    - Bake Type: **Diffuse**
    - Contributions: uncheck **Direct**, uncheck **Indirect** — only **Color** checked
    - **Selected to Active: OFF** (this is a self-bake)
37. Click **Bake**
    - When done, the CleanBake image fills with the texture remapped to the clean UV

38. In Shader Editor → click the CleanBake Image Texture node → top menu **Image → Save As**
    - Save as `CleanBake_temp.png` anywhere (temporary file — only needed as intermediate)

### G — Bake from source to remesh

39. **Click the remesh** in the viewport to select it
40. Open the **Shader Editor** — confirm it shows the remesh material (`FRAG-S1-{ARCHETYPE}-{###}_remesh`)
41. **Shift+A → Texture → Image Texture** → click **New** → Name: `FRAG-S1-{ARCHETYPE}-{###}_bake` → 4096 × 4096 → **OK**
42. Leave it **unconnected**, keep it **selected** (highlighted yellow)

43. In the **3D Viewport**:
    - Click the **bake source** (hidden duplicate, now unhidden) → it turns orange (selected)
    - **Shift+click the remesh** → remesh turns bright orange (active object — bake target)
    - The bake source is selected but not active (darker orange)

44. Render Properties → Bake:
    - Bake Type: **Diffuse**
    - Contributions: **Color** only (Direct and Indirect unchecked)
    - **Selected to Active: ON**
    - Extrusion: **0.05 m** (increase to 0.1 m if you get black patches)
    - **Margin: 32 px**, Margin Type: **Extend**
45. Click **Bake**
    - Blender projects the texture from the bake source onto the remesh's UV

46. In Shader Editor → click the baked Image Texture node → **Image → Save As**
    - Save to: `01_input/meshes/processed/FRAG-S1-{ARCHETYPE}-{###}/FRAG-S1-{ARCHETYPE}-{###}_texture.png`

> **Why margin matters.** Blender's default margin type bleeds colour only across shared UV
> edges, so the space between islands stays pure black. Roughly 30% of the atlas is that
> black. The descriptor pipeline masks it out before the vision model sees it, so the effect
> is limited to the rim where the region mask overshoots its island by a few pixels, but
> Extend removes even that. `bake_texture_v2.py` sets this automatically (`BAKE_MARGIN`);
> the step above is for baking by hand.

### H — Wire up the remesh material

47. In the remesh's Shader Editor:
    - **Connect** the baked Image Texture node's **Color output → Base Color input** of Principled BSDF
48. **Delete** all other Image Texture nodes from the remesh material (normal map, roughness, original Scaniverse texture — not needed)
    - Select unwanted node → **X** to delete

### I — Verify

49. Press **Z → Material Preview** in the viewport to see the texture on the remesh — should look like the concrete fragment surface
50. Optional: drag the exported GLB to [gltf-viewer.donmccurdy.com](https://gltf-viewer.donmccurdy.com) to confirm it looks correct outside Blender

---

## Stage 4 — Blender: Export Script

51. Click the **Scripting** tab in the top menu bar
52. In the Text Editor (left panel): click **Open** → navigate to `02_blender/export_fragment.py`
53. At the top of the script, change:
    ```python
    FRAG_ID = "FRAG-S1-{ARCHETYPE}-{###}"   # e.g. FRAG-S1-FS-003
    ```
54. Go to the **Layout** tab → click the **remesh object** in the viewport to select it (orange outline)
55. Go back to **Scripting** tab → click **▶ Run Script**

Expected output in the Info bar / System Console:
```
── Exporting FRAG-S1-FS-003 ──────────────────────────────
   Object    : your_mesh_name
   Unit scale: 0.001  →  export scale ×1.0 (to mm)
   To        : ...01_input\meshes\processed\FRAG-S1-FS-003

✓ GLB     → ...FRAG-S1-FS-003.glb
   Texture found: 'FRAG-S1-FS-003_bake'  (4096×4096)
✓ Texture → ...FRAG-S1-FS-003_texture.png
```

---

## Stage 5 — Pipeline

In PowerShell from the project root:

```powershell
env\venv\Scripts\activate
python 03_src/run_pipeline.py FRAG-S1-{ARCHETYPE}-{###}
```

Or use batch mode to process all unanalyzed fragments:
```powershell
python 03_src/run_pipeline.py --batch
```

---

## Stage 6 — Git Commit

```powershell
git add 01_input/photogrammetry/raw_exports/FRAG-S1-{ARCHETYPE}-{###}/
git commit -m "data: add raw scan FRAG-S1-{ARCHETYPE}-{###}"

git add 01_input/meshes/processed/FRAG-S1-{ARCHETYPE}-{###}/
git commit -m "data: add processed mesh FRAG-S1-{ARCHETYPE}-{###}"

git add 05_output/
git commit -m "data: descriptors FRAG-S1-{ARCHETYPE}-{###}"
```

---

## Troubleshooting

**Black patches in bake** — Extrusion too small. Increase from 0.05 to 0.1 m and bake again.

**Bake produces wrong colors / scene colors** — Direct or Indirect contributions are checked. Uncheck both, leave only Color.

**Bake writes nothing / image stays black** — The Image Texture node on the target object is not selected (highlighted yellow). Click it and try again.

**Export script saves wrong texture (normal map / old texture)** — Delete all Image Texture nodes from the remesh material except the baked one, then re-run.

**Scale looks wrong after export** — Dimensions in Blender were in metres, not mm. Go back and scale × 1000, then re-export.

**Scaniverse UV is completely broken** — Run the self-bake step (Stage F above). The CleanBake replaces the source texture with a correctly mapped version before baking to the remesh.
