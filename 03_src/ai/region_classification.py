"""
Region-based surface classification (replaces per-cell grid classification).

Each coherent mesh surface region (RANSAC plane / fracture cluster, from
descriptors.regions) is cropped out of the texture atlas at full resolution
and all crops are batched into ONE vision call per vote:

  - one taxonomy label per region ("what is this surface?"), plus
  - localized anomalies (rebar_visible / staining / ...) as bounding boxes
    in crop-percent coordinates.

Rationale: fragments are piecewise-homogeneous per face; a VLM judges a whole
coherent surface with context far more reliably than isolated texture tiles
(per-cell grids collapse to one label per image — verified on FS-006).

The results are written back both per-region (descriptors, schema) and as a
backfilled 16×16 grid so the existing UV→face mapping, feature textures and
3D viewer stay unchanged.

V convention: trimesh UVs are OpenGL (v=0 bottom); all rasterization here
flips to image space (row 0 top) to match the texture PNG.
"""

import base64
import hashlib
import io
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .vision_client import TAXONOMY, CACHE_DIR, _load_dotenv
from .taxonomy import (TAXONOMY, ACTIVE, LABEL_RULES, LOCALIZED,
                       DISPLAY_PRECEDENCE, features_by_group)

_GROUPED = features_by_group()

GRID_N        = 16     # backfill grid resolution (kept for viewer/report)
COHERENCE_MIN = 0.5

# Share of its own bounding box a region's UV footprint must cover.
#
# COHERENCE_MIN is not enough and does not measure this.  Coherence is the
# largest connected blob over the whole mask, so a thin winding ribbon scores
# 1.0 while filling almost none of the box it is cropped to.  Everything
# outside the mask is painted magenta, so what the model receives is a mostly
# magenta rectangle with a few shreds of concrete in it, and it still has to
# return one label for the region.
#
# Measured on FS-002: region #2 covers 10.9% of the fragment at coherence 0.97
# and fill 10%, region #5 at coherence 0.84 and fill 7%.  Both were classified.
# A label from a crop that is nine-tenths magenta is a guess from the shape of
# the fragments, not a reading of the surface.
#
# The threshold is set low deliberately.  0.35 was tried first and classified 2
# of 10 regions on FS-002, covering 23% of the surface: it removes the bad
# labels by removing the fragment.  0.20 drops the four regions that are
# indefensible (7 to 18% fill) and keeps four covering 39%.  That is still a
# large loss and it is a real finding rather than a tuning choice: a geometric
# region is scattered across the atlas by Smart UV Project, so its bounding box
# is mostly other regions and empty sheet.  `uv_fill` is now recorded on every
# region, classified or not, so the weak labels can be discounted when reading
# results instead of being silently trusted.
#
# The proper fix is to crop each region's largest connected blob rather than the
# bounding box of its whole scattered footprint, which would raise fill without
# discarding regions.  Not attempted here; noted in PLAN_texture_quality.md.
FILL_MIN = 0.20
SMEAR_COH_MIN = 0.65   # structure-tensor coherence above which a patch is a smear
SMEAR_MIN_FRAC= 0.02   # ignore flagged blobs smaller than this share of the face
FLAT_SD_MAX   = 3.0    # luminance sd below which a patch carries no surface detail
REFERENCE_DIR = Path(__file__).resolve().parents[2] / "01_input" / "reference_surfaces"
USE_REFERENCES = True   # set False to classify uncalibrated; see run_pipeline --no-references
REF_MAX_SIDE  = 512    # references are for comparison, not inspection
SMEAR_SKIP    = 0.50   # skip the region if this share of it is smeared
BATCH_SIZE    = 3      # regions per API call; see the note in classify_regions

# ── Localisation: off by default, with the guard rails already built ─────────
#
# Until 2026-08-20 the schema demanded a bounding box for any localized feature
# and gave the model no way to decline. Every box it returned was a stock value:
# 68 of 68 coordinates exact multiples of 10, 17 detections drawn from 7 distinct
# boxes, [40,40,60,60] six times across different fragments AND different
# features. Three of those checked pointed mostly at masked-out non-material.
#
# The usual reading is that the model invented coordinates. The more accurate one
# is that we asked a question with no honest answer available: a required field
# and no "I cannot tell" option. A model will fill it. Stock coordinates are what
# "I don't know" looks like when the schema forbids saying so.
#
# So localisation is not deleted, it is disabled with its validation in place:
#
#   1. the prompt states that null is a valid and PREFERRED answer when position
#      cannot be determined, so declining is available;
#   2. any box returned is checked against the region mask and rejected if it
#      mostly covers non-material;
#   3. stock-coordinate patterns are detected and rejected;
#   4. every feature records how its position was arrived at, so a reader can
#      tell a validated box from an absent one.
#
# Turn it on when capture quality supports it — higher texel density, or crops
# tight enough that a box is meaningful. The gates below decide whether the
# answers are usable; they do not need rewriting first.
ALLOW_LOCALISATION = False
BOX_MIN_ON_MASK    = 0.50   # a box must be at least this much real surface
BOX_MIN_IOU        = 0.30   # agreement between runs for a box to survive


def _is_stock_box(box: list) -> bool:
    """True for coordinates that look chosen rather than measured.

    Every fabricated box in the 2026-08-20 corpus was a multiple of 10 on all
    four coordinates, and most were centred. Real localisation does not land on
    a 10% grid 68 times running. This is a weak test on its own, which is why it
    is one of three.
    """
    if not (isinstance(box, list) and len(box) == 4):
        return True
    if not all(float(v) % 10 == 0 for v in box):
        return False
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return abs(cx - 50) <= 10 and abs(cy - 50) <= 20


def validate_box(box: list, mask: np.ndarray, bbox: tuple) -> tuple:
    """(ok, reason). Checks a box against the region it claims to sit in."""
    if not (isinstance(box, list) and len(box) == 4):
        return False, "malformed"
    if _is_stock_box(box):
        return False, "stock_coordinates"
    if mask is None or not bbox:
        return True, "unverified_no_mask"
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    px0 = int(x0 + min(box[0], box[2]) / 100.0 * bw)
    px1 = int(x0 + max(box[0], box[2]) / 100.0 * bw)
    py0 = int(y0 + min(box[1], box[3]) / 100.0 * bh)
    py1 = int(y0 + max(box[1], box[3]) / 100.0 * bh)
    sub = mask[max(py0, 0):py1, max(px0, 0):px1]
    if sub.size == 0:
        return False, "outside_region"
    on = float(sub.mean())
    if on < BOX_MIN_ON_MASK:
        return False, f"only_{on:.0%}_on_material"
    return True, f"{on:.0%}_on_material"

# ── Window sizes are in MILLIMETRES OF SURFACE, not pixels ──────────────────
#
# These gates were tuned on FS-006 at a 1080 atlas, which resolves 0.46 px per
# mm.  A 9 px structure-tensor window was therefore asking "is this patch of
# concrete about 20 mm across directional?", which is the right question: it
# spans a few aggregate particles, and real concrete is directionless at that
# scale while a grazing-angle smear is not.
#
# Raising the bake to 4096 changed what those same 9 px mean.  At 1.45 px/mm a
# 9 px window covers 6 mm, which is *inside* a single aggregate particle, where
# the texture genuinely does have one dominant orientation.  Measured on the
# 4096 FS-002 atlas the gate then flags 75% of the textured area as smear
# against 24% at the equivalent real-world window, so nearly every region would
# be skipped as unusable and the fragment would come back unclassified.  The
# gate would have been reporting the resolution increase as damage.
#
# So the windows are declared in millimetres and converted per fragment using
# the atlas's measured texel density.  Any future change to BAKE_RES or to the
# UV island margin is then absorbed automatically.
CALIB_PX_PER_MM = 0.46   # FS-006 at 1080; the density these numbers were tuned at
SMEAR_WIN_MM      = 20.0   # structure-tensor averaging window
SMEAR_OPEN_MM     = 11.0   # drop speckle
SMEAR_CLOSE_MM    = 54.0   # join a broken band into one blob
FLAT_WIN_MM       = 33.0   # local detail window
FLAT_OPEN_MM      = 20.0
FLAT_CLOSE_MM     = 46.0

# Retained so a caller that cannot supply a density behaves exactly as before.
SMEAR_WIN     = 9
FLAT_WIN      = 15


def _open_sq(mask: np.ndarray, n: int) -> np.ndarray:
    """Binary opening with an n x n square, done as two 1-D passes.

    A square structuring element is separable, so eroding by (n,1) then (1,n) is
    identical to eroding by (n,n) and costs O(n) instead of O(n^2).  This stops
    mattering at 1080 and starts mattering a lot at 4096, where the windows are
    four times wider: the 2-D form did not finish in two minutes on a full
    atlas.
    """
    from scipy import ndimage
    if n <= 1:
        return mask
    v, h = np.ones((n, 1), bool), np.ones((1, n), bool)
    m = ndimage.binary_erosion(ndimage.binary_erosion(mask, v), h)
    return ndimage.binary_dilation(ndimage.binary_dilation(m, v), h)


def _close_sq(mask: np.ndarray, n: int) -> np.ndarray:
    """Binary closing with an n x n square, separable. See _open_sq."""
    from scipy import ndimage
    if n <= 1:
        return mask
    v, h = np.ones((n, 1), bool), np.ones((1, n), bool)
    m = ndimage.binary_dilation(ndimage.binary_dilation(mask, v), h)
    return ndimage.binary_erosion(ndimage.binary_erosion(m, v), h)


def _win_px(mm: float, px_per_mm: float | None, fallback: int) -> int:
    """Convert a window in millimetres of surface to an odd pixel count."""
    if not px_per_mm or px_per_mm <= 0:
        return fallback
    n = max(3, int(round(mm * px_per_mm)))
    return n + 1 if n % 2 == 0 else n


def texel_density(mesh, texture_size: int) -> float | None:
    """Pixels of atlas per millimetre of real surface, or None if unmeasurable.

    This is the number that decides what every window above actually means, and
    it is not the atlas resolution: the UV island margin can throw most of the
    sheet away.  Measured on FS-002, a 4096 atlas at island_margin 0.02 carried
    UV on 20% of its area and delivered the texel density of an 1830 one.
    """
    uv = getattr(getattr(mesh, "visual", None), "uv", None)
    if uv is None:
        return None
    try:
        tri = np.asarray(uv)[mesh.faces]
        e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        uv_frac = float(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum() * 0.5)
        area_mm2 = float(mesh.area)
        if max(mesh.bounding_box.primitive.extents) < 10.0:   # metres, not mm
            area_mm2 *= 1e6
        if area_mm2 <= 0 or uv_frac <= 0:
            return None
        return float(np.sqrt(uv_frac * texture_size * texture_size / area_mm2))
    except Exception:
        return None
N_VOTES       = 3
CROP_MARGIN   = 16     # px context margin around region bbox
CROP_MAX_SIDE = 1024   # downscale crops larger than this
MASK_FILL     = (255, 0, 255)   # magenta: area outside the region
# Roughly a quarter of every crop is fill, because a region's UV island is an
# organic blob inside a rectangular crop. That share is too large for the fill
# colour to be arbitrary. Black reads as a void and produced spurious "opening"
# labels; mid grey is close enough to concrete to read as smooth cast surface.
# Magenta occurs in neither concrete nor shadow, so it can be read as neither.
# Anomaly labels and their hints now live in env/taxonomy.json alongside the
# surface labels, so the condition axis can be revised without a code change.
# See ai/taxonomy.py for why the two axes differ.

_SYSTEM = (
    "You are a materials scientist analysing demolition concrete surfaces. "
    "Return JSON only — no explanation, no markdown."
)


# ── UV rasterization (image space, V flipped) ────────────────────────────────

def rasterize_region_mask(mesh, face_idx, size: int) -> np.ndarray:
    """Boolean (size, size) mask of the region's UV footprint, image space.

    Photogrammetry meshes have millions of sub-pixel triangles, so per-face
    polygon rasterization is prohibitively slow.  Instead: scatter the
    region's vertices into the pixel grid and dilate (5 px) — equivalent
    coverage at this texture resolution, and runs in C via PIL.
    """
    from PIL import ImageFilter
    uv    = np.clip(np.asarray(mesh.visual.uv), 0.0, 1.0)
    verts = np.unique(mesh.faces[face_idx].ravel())
    cols  = np.clip((uv[verts, 0] * size).astype(int), 0, size - 1)
    rows  = np.clip(((1.0 - uv[verts, 1]) * size).astype(int), 0, size - 1)
    arr = np.zeros((size, size), dtype=np.uint8)
    arr[rows, cols] = 255
    # Dilate to join neighbouring samples, then CLOSE the result: scattered
    # vertices leave pinholes inside the footprint, and an unclosed mask
    # punches dark gaps into the crop that a vision model reads as voids in
    # the concrete. Closing removes the artifact without growing the outline.
    img = Image.fromarray(arr).filter(ImageFilter.MaxFilter(5))
    img = img.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    return np.array(img) > 0


def uv_coherence(mask: np.ndarray) -> float:
    """Share of the region's UV footprint that lies in its largest island.

    Smart UV Project keeps a real planar face as essentially one island, so a
    coherent region scores near 1.0.  A pooled residual of slivers scatters
    into hundreds of islands and scores low; its crop is not a view of one
    surface and must not be classified as if it were.
    """
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    if n == 0:
        return 0.0
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return float(sizes.max() / mask.sum())


def directional_smear(crop: np.ndarray, valid: np.ndarray,
                      px_per_mm: float | None = None) -> np.ndarray:
    """Pixels where the bake has smeared the texture into parallel streaks.

    Where the scan saw a surface only at a grazing angle, the projection drags
    one texel along the surface and the bake comes out as strong parallel
    striping.  It looks like corrugated metal or a row of bars, and a vision
    model reports it as exposed reinforcement.  Concrete has no such structure:
    its texture is directionless at this scale.  The structure tensor separates
    the two, being near 1 where the local gradient has a single orientation and
    near 0 where it has none.
    """
    from scipy import ndimage
    win   = _win_px(SMEAR_WIN_MM, px_per_mm, SMEAR_WIN)
    op    = _win_px(SMEAR_OPEN_MM, px_per_mm, 5)
    close = _win_px(SMEAR_CLOSE_MM, px_per_mm, 25)
    g  = crop.astype(float).mean(axis=2)
    gx, gy = ndimage.sobel(g, axis=1), ndimage.sobel(g, axis=0)
    Jxx = ndimage.uniform_filter(gx * gx, win)
    Jyy = ndimage.uniform_filter(gy * gy, win)
    Jxy = ndimage.uniform_filter(gx * gy, win)
    root = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2)
    tr   = Jxx + Jyy
    coh  = np.where(tr > 1e-6, root / (tr + 1e-9), 0.0)

    smear = (coh > SMEAR_COH_MIN) & valid
    smear = _open_sq(smear, op)      # drop speckle
    smear = _close_sq(smear, close)  # join the band
    smear = ndimage.binary_fill_holes(smear)
    # A partly masked band is worse than none: the ragged remainder reads as
    # perforation. Keep only blobs large enough to be a band, and take them whole.
    lab, n = ndimage.label(smear)
    if n:
        sizes = ndimage.sum(smear, lab, range(1, n + 1))
        keep  = 1 + np.where(sizes > SMEAR_MIN_FRAC * max(valid.sum(), 1))[0]
        smear = np.isin(lab, keep)
    # `& valid` on the way in is not enough: the close and the hole fill both
    # dilate, so the mask spills past the surface it was measured against. On
    # FS-001 that came to 105% of the real surface atlas-wide, and the spilled
    # pixels are charged to the region as unusable, inflating every smear
    # fraction in the corpus. Blobs stay whole; only the overspill is trimmed.
    return smear & valid


def featureless_fill(crop: np.ndarray, valid: np.ndarray,
                     px_per_mm: float | None = None) -> np.ndarray:
    """Pixels the bake filled with a flat tone carrying no surface detail.

    Where the scan never saw a face at all, typically the underside the
    fragment was resting on, the projection has nothing to sample and the bake
    comes out as an even wash of colour.  It is the opposite signature to a
    smear: no direction because there is no structure of any kind.

    This is the case neither other check can reach.  The smear gate looks for
    a dominant gradient orientation and finds none; the geometry sees a
    manually filled hole as the flattest, cleanest plane on the fragment and
    will happily propose it as a bench top.  Marking the `UNSCANNED` vertex
    group in Blender is the proper fix, since it declares the geometry
    invented as well as the texture.  This is the safety net for when that
    marking was missed.
    """
    from scipy import ndimage
    win   = _win_px(FLAT_WIN_MM, px_per_mm, FLAT_WIN)
    op    = _win_px(FLAT_OPEN_MM, px_per_mm, 9)
    close = _win_px(FLAT_CLOSE_MM, px_per_mm, 21)
    g   = crop.astype(float).mean(axis=2)
    mu  = ndimage.uniform_filter(g, win)
    mu2 = ndimage.uniform_filter(g * g, win)
    sd  = np.sqrt(np.maximum(mu2 - mu * mu, 0.0))

    flat = (sd < FLAT_SD_MAX) & valid
    flat = _open_sq(flat, op)
    flat = _close_sq(flat, close)
    lab, n = ndimage.label(flat)
    if n:
        sizes = ndimage.sum(flat, lab, range(1, n + 1))
        keep  = 1 + np.where(sizes > SMEAR_MIN_FRAC * max(valid.sum(), 1))[0]
        flat  = np.isin(lab, keep)
    return flat & valid          # the close dilates past `valid`; see directional_smear


def region_colour_entropy(texture_img: Image.Image, crops: list) -> dict:
    """Shannon entropy of each region's colour distribution, in bits.

    Colour was a Study 1 requirement that the pipeline answered only through
    the whole-atlas pass, as a free-text `color_notes` sentence at fragment
    level. A fragment-level sentence cannot drive a face-level design rule, so
    the requirement was effectively unmet. This measures it per region instead,
    deterministically, from the mask each crop already carries.

    Every region has a mask, including the ones declined for classification,
    so this is defined wherever the region has any real texture at all.

    RGB is quantised to 4 levels per channel, 64 bins, giving a range of 0 to 6
    bits. A single flat colour scores 0. Broken concrete with mixed aggregate
    sits high. `MASK_FILL` pixels are excluded so that a region's score does not
    depend on how much of its bounding box is padding.
    """
    tex = np.array(texture_img.convert("RGB"))
    out: dict = {}
    for crop in crops:
        m = crop.get("mask")
        if m is None or not m.any():
            out[crop["region_id"]] = None
            continue
        px = tex[m]
        keep = ~np.all(px == MASK_FILL, axis=1)
        px = px[keep]
        if len(px) < 64:
            out[crop["region_id"]] = None
            continue
        q = (px.astype(int) >> 6)                      # 4 levels per channel
        idx = q[:, 0] * 16 + q[:, 1] * 4 + q[:, 2]     # 64 bins
        counts = np.bincount(idx, minlength=64).astype(float)
        p = counts / counts.sum()
        p = p[p > 0]
        out[crop["region_id"]] = round(abs(float(-(p * np.log2(p)).sum())), 3)
    return out


def build_region_crops(texture_img: Image.Image, mesh, regions: list) -> list:
    """For each region: masked, bbox-cropped texture image + placement meta.

    Returns list of dicts (same order as regions):
        {"region_id", "image": PIL, "bbox": (x0, y0, x1, y1) in texture px,
         "mask": bool array, "coherence": float, "skipped": str|None}
    Regions with no UV footprint, or with a fragmented footprint, get
    image=None and are not sent to the vision model.
    """
    tex  = np.array(texture_img.convert("RGB"))
    size = tex.shape[0]
    # Measured once per fragment: every window in the two texture gates below is
    # declared in millimetres of surface and sized from this.
    px_per_mm = texel_density(mesh, size)
    if px_per_mm:
        print(f"      atlas resolves {px_per_mm:.2f} px per mm; smear window "
              f"{_win_px(SMEAR_WIN_MM, px_per_mm, SMEAR_WIN)} px")
    out  = []
    for reg in regions:
        mask = rasterize_region_mask(mesh, reg["face_idx"], size)
        if not mask.any():
            out.append({"region_id": reg["region_id"], "image": None,
                        "bbox": None, "mask": mask, "coherence": 0.0,
                        "skipped": "no_uv_footprint"})
            continue
        coh = uv_coherence(mask)
        if coh < COHERENCE_MIN:
            print(f"      region #{reg['region_id']} ({reg['kind']}): UV "
                  f"coherence {coh:.2f} < {COHERENCE_MIN}, not classified")
            out.append({"region_id": reg["region_id"], "image": None,
                        "bbox": None, "mask": mask, "coherence": round(coh, 3),
                        "skipped": "fragmented_uv"})
            continue
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        y0, y1 = max(rows[0] - CROP_MARGIN, 0), min(rows[-1] + CROP_MARGIN, size)
        x0, x1 = max(cols[0] - CROP_MARGIN, 0), min(cols[-1] + CROP_MARGIN, size)

        # How much of the crop is actually surface. See FILL_MIN.
        fill = float(mask.sum()) / max((y1 - y0) * (x1 - x0), 1)
        if fill < FILL_MIN:
            print(f"      region #{reg['region_id']} ({reg['kind']}): UV fill "
                  f"{fill:.0%} < {FILL_MIN:.0%}, the crop would be mostly mask "
                  f"fill, not classified")
            out.append({"region_id": reg["region_id"], "image": None,
                        "bbox": None, "mask": mask, "coherence": round(coh, 3),
                        "uv_fill": round(fill, 3), "skipped": "sparse_uv"})
            continue

        crop = tex[y0:y1, x0:x1].copy()
        # Fill outside the region, and over any smeared band inside it, with a flat mid grey, not black: a black fill
        # reads as a hole in the material, and the model reported those as
        # openings. A flat neutral tone is visibly "not surface" without
        # looking like a void.
        local = mask[y0:y1, x0:x1]
        smear = directional_smear(crop, local, px_per_mm)
        flat  = featureless_fill(crop, local, px_per_mm)
        # Both gates start on-mask but grow off it: the closing, the hole fill
        # and the take-the-blob-whole step all reach past `local` by design, so
        # that a partly masked band is removed entirely rather than left ragged.
        # That is right for masking and wrong for measuring. Counting the grown
        # mask against the region's own pixel count reported fractions above
        # 100% (FS-010 region 5 at "109% of the face is unusable texture" on
        # 2026-08-24) and skipped regions that were mostly sound. Mask before
        # measuring; the ungrown masks still do the masking.
        smear = smear | flat
        _n = max(int(local.sum()), 1)
        flat_frac  = float((flat  & local).sum() / _n)
        smear_frac = float((smear & local).sum() / _n)
        if flat_frac > 0:
            print(f"      region #{reg['region_id']} ({reg['kind']}): "
                  f"{flat_frac:.0%} featureless fill — mark UNSCANNED in Blender")
        if smear_frac >= SMEAR_SKIP:
            print(f"      region #{reg['region_id']} ({reg['kind']}): "
                  f"{smear_frac:.0%} of the face is unusable texture, not classified")
            out.append({"region_id": reg["region_id"], "image": None,
                        "bbox": None, "mask": mask, "coherence": round(coh, 3),
                        "uv_fill": round(fill, 3),
                        "smear_frac": round(smear_frac, 3),
                        "flat_frac": round(flat_frac, 3),
                        "skipped": "unreliable_texture"})
            continue
        if smear_frac > 0:
            print(f"      region #{reg['region_id']} ({reg['kind']}): "
                  f"{smear_frac:.0%} smeared texture masked out")
        crop[~local | smear] = MASK_FILL
        img = Image.fromarray(crop)
        if max(img.size) > CROP_MAX_SIDE:
            img.thumbnail((CROP_MAX_SIDE, CROP_MAX_SIDE))
        out.append({"region_id": reg["region_id"], "image": img,
                    "bbox": (int(x0), int(y0), int(x1), int(y1)),
                    "mask": mask, "coherence": round(coh, 3),
                    "uv_fill": round(fill, 3),
                    "smear_frac": round(smear_frac, 3),
                    "flat_frac": round(flat_frac, 3), "skipped": None})
    return out


# ── Vision call ──────────────────────────────────────────────────────────────

def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def load_reference_set() -> list:
    """Labelled exemplar crops that define each label for THIS material.

    Every fragment comes from one building: one mix, one formwork system, one
    demolition method. So what a formwork imprint looks like here is a stable
    thing that can be shown rather than defined in words, and a model asked to
    match against exemplars is on far firmer ground than one asked to apply a
    verbal definition it must interpret alone.

    Layout, one folder per label, any number of images in each:

        01_input/reference_surfaces/formwork_face/*.png
        01_input/reference_surfaces/broken_face/*.png

    Returns [(label, PIL.Image), ...] in taxonomy order. Empty list disables
    the whole mechanism, so the pipeline runs unchanged until the folder is
    populated.

    Note for the paper: exemplars chosen by eye make the classifier agree with
    whoever chose them. That is a legitimate operational definition and it is
    not validation. It has to be stated as such.
    """
    if not USE_REFERENCES or not REFERENCE_DIR.is_dir():
        return []

    # A folder whose name is not a taxonomy label used to be skipped in silence,
    # so "add a category by making a folder" looked like it worked and did
    # nothing. Say so instead.
    # Underscore-prefixed folders are bookkeeping, not labels: `_candidates`
    # from build_reference_set, `_retired` where exemplars of retired features
    # are parked. Warning about them is noise.
    known = set(TAXONOMY)
    for d in sorted(REFERENCE_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if d.name not in known:
            print(f"      ! reference folder '{d.name}' is not a taxonomy feature and is "
                  f"being ignored. Add it to env/taxonomy.json first: an entry in "
                  f"'features' with id, color, description, decision_rule and group.")
        elif d.name not in ACTIVE and any(
                p.suffix.lower() in {".png", ".jpg", ".jpeg"} for p in d.iterdir()):
            print(f"      ! reference folder '{d.name}' belongs to a RETIRED feature "
                  f"and is being ignored. Move it to _retired/ to silence this.")

    # ACTIVE, not TAXONOMY. TAXONOMY keeps every id ever used, retired included,
    # because the index is the stored feature_id. Iterating it here sent the
    # exemplars of a retired feature on every call, so retiring a feature took it
    # out of the prompt's label list while leaving its pictures in the prompt.
    out = []
    for label in ACTIVE:
        folder = REFERENCE_DIR / label
        if not folder.is_dir():
            continue
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            try:
                img = Image.open(p).convert("RGB")
            except OSError:
                print(f"      ! unreadable reference image: {p.name}")
                continue
            img.thumbnail((REF_MAX_SIDE, REF_MAX_SIDE))
            out.append((label, img))
    return out


def reference_signature() -> str:
    """Identity of the reference set, for the API cache key.

    Swapping an exemplar changes the standard the model is calibrated to, so
    cached answers from a different set must not be reused.
    """
    if not USE_REFERENCES or not REFERENCE_DIR.is_dir():
        return "none"
    h = hashlib.sha256()
    for label in ACTIVE:            # must match what load_reference_set actually sends
        folder = REFERENCE_DIR / label
        if not folder.is_dir():
            continue
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                h.update(label.encode())
                h.update(p.name.encode())
                h.update(str(p.stat().st_size).encode())
    return h.hexdigest()[:16]


def _call_vision(crops: list, provider: str, model: str) -> dict:
    """One API call: all region crops numbered; returns parsed dict."""
    numbered = [c for c in crops if c["image"] is not None]
    refs = load_reference_set()

    ref_block = ""
    if refs:
        # The wording matters more than it looks.
        #
        # This block used to read "They define what each label means for this
        # material. Judge the regions against these" — which the model took as
        # an instruction to find the closest reference and answer with it. In
        # the 2026-08-20 control test the calibrated run returned `pipe_opening`
        # ALONE and `tile_remnant` ALONE, suppressing the fracture surface and
        # exposed aggregate that Muchen confirmed were also present. Matching
        # behaviour defeats the point of a multi-label schema: the references
        # are there to fix what each feature LOOKS LIKE, not to reduce the
        # answer to one of them.
        ref_block = (
            f"First come {len(refs)} REFERENCE images from the same building as "
            f"the fragments, each labelled below. Use them to calibrate what "
            f"each feature looks like IN THIS MATERIAL, rather than concrete in "
            f"general.\n"
            + "\n".join(f"  Reference {i}: {lab}"
                        for i, (lab, _) in enumerate(refs, 1))
            + f"\n\nThey are a guide to appearance, NOT a menu to choose from. "
            f"Recognising one feature from a reference does not exclude any "
            f"other: a region that matches the tile reference may also be a "
            f"fracture surface showing aggregate, and all of that must be "
            f"reported. A feature with no reference image is not less likely — "
            f"report it on the same evidence you would use for any other.\n\n"
            f"The {len(numbered)} images after them are the regions to label.\n\n")

    prompt = (
        ref_block +
        f"You receive {len(numbered)} numbered region images. Each is one coherent "
        f"surface region of a single demolition concrete fragment, cut out of "
        f"its texture atlas. Magenta areas are outside the region and are "
        f"not part of the material: never report them as holes, voids or "
        f"openings.\n\n"
        + (f"For EACH image i return EVERY feature you can see in it:\n"
           f'  "i": {{"features": [{{"id": <feature id>, '
           f'"box_pct": [x0,y0,x1,y1] or null}}, ...]}}\n\n'
           f"About box_pct: give it ONLY if you can point at where the feature "
           f"is. **null is a valid and preferred answer.** Use null whenever the "
           f"feature is spread across the region, or you can see it but cannot "
           f"say where, or you are unsure. A null costs nothing; a guessed box "
           f"is worse than no box, because it will be read as a measurement. "
           f"Do not produce round or centred coordinates to fill the field.\n\n"
           if ALLOW_LOCALISATION else
           f"For EACH image i return EVERY feature you can see in it:\n"
           f'  "i": {{"features": [<feature id>, <feature id>, ...]}}\n\n')
        + f"Judge each image on its own. Regions of one fragment may carry the "
        f"same features or different ones; do not make them agree, and do not "
        f"let one image set the reading for the rest.\n\n"
        f"THESE FEATURES DO NOT COMPETE. Report all that apply. A broken face "
        f"showing aggregate is BOTH broken_face AND exposed_aggregate. A "
        f"formwork face with rust on it is BOTH formwork_face AND "
        f"discolouration. "
        f"Never leave one out because another fits better: there is no "
        f"'best' answer, only a complete one. Return an empty list only if "
        f"none applies.\n\n"
        + "\n\n".join(
            f"{grp.upper()} — " + {
                "formation":   "how this surface came to be",
                "composition": "what the concrete itself looks like here",
                "inclusion":   "something embedded in or attached to the face",
                "colour":      "colouring that is not the concrete's own",
            }.get(grp, grp) + ":\n"
            + "\n".join(f"  - {fid}: {LABEL_RULES.get(fid) or fid}" for fid in fids)
            for grp, fids in _GROUPED.items())
        # Bounding boxes were requested until 2026-08-20 and every one of them
        # was fabricated: 68 of 68 coordinates were exact multiples of 10, and
        # 17 detections used 7 distinct boxes with [40,40,60,60] appearing six
        # times across different fragments AND different features. Three of the
        # boxes checked pointed mostly at magenta mask fill. The model fills the
        # field whether or not it can locate anything, so the request was
        # manufacturing false precision. Asking for presence only is what it can
        # actually support.
        + f"\n\nReport PRESENCE only. Do not give coordinates or describe "
        f"position: naming a feature means it appears somewhere in this "
        f"region.\n"
        f"Return ONLY a JSON object with keys 1..{len(numbered)}."
    )
    content = [{"type": "text", "text": prompt}]
    for _lab, img in refs:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_b64(img)}",
                                      "detail": "low"}})   # for comparison, not inspection
    for c in numbered:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_b64(c['image'])}",
                                      "detail": "high"}})

    if provider == "openai":
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model=model, temperature=0.2, max_tokens=1500,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": content}])
        raw = resp.choices[0].message.content.strip()
    else:
        raise NotImplementedError(
            f"Region classification not implemented for provider '{provider}'.")

    text = raw
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"    PARSE ERROR — raw: {raw[:80]}")
        return {}


# ── Vote merging ─────────────────────────────────────────────────────────────

def _iou(a, b) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def _merge_votes(runs: list, n_regions: int) -> list:
    """Vote each feature independently; keep those seen in a majority of runs.

    Multi-label changes what a vote means. Previously the runs competed for one
    slot and the plurality won, so a region always got a label even when the
    runs disagreed three ways. Now each feature is its own yes/no question and
    is kept only if a majority of runs saw it. A region can therefore come back
    with none, which is a real answer rather than a failure.
    """
    n_runs = max(len(runs), 1)
    keep_min = n_runs // 2 + 1          # 2 of 3
    merged = []
    for i in range(1, n_regions + 1):
        entries = [r.get(str(i)) or {} for r in runs]

        # per-feature support. `features` is a list of bare ids since
        # 2026-08-20; older cached runs hold dicts with a fabricated box_pct,
        # which is read for the id and otherwise ignored.
        support: dict = {}
        for ri, e in enumerate(entries):
            seen = set()
            for f in (e.get("features") or []):
                fid = f.get("id") if isinstance(f, dict) else f
                if fid not in ACTIVE or fid in seen:
                    continue
                seen.add(fid)
                support[fid] = support.get(fid, 0) + 1

        features = []
        for fid, n in sorted(support.items(),
                             key=lambda kv: DISPLAY_PRECEDENCE.index(kv[0])
                             if kv[0] in DISPLAY_PRECEDENCE else 999):
            if n < keep_min:
                continue
            features.append({"id": fid, "votes": n})

        # `label` is kept for the viewer, the feature map and every existing
        # consumer that can only carry one value per face. It is now purely a
        # display choice: the highest-precedence feature present.
        label = features[0]["id"] if features else None

        # `anomalies` is retained as an empty list only so that consumers
        # written against it do not need changing. There are no boxes any more:
        # a feature is reported as present in the region, without a position.
        # How many runs the region was put to, which is the denominator every
        # per-feature vote count is out of.
        #
        # This used to store features[0]["votes"], the vote count of whichever
        # feature sorted first. That read correctly only while the precedence
        # list put the commonest feature first, since it almost always polled
        # 3 of 3. Reordering precedence rarest-first on 2026-08-25 made
        # features[0] a rare feature, and the run of that date printed
        # "exposed_aggregate(3/2)" on eight regions: three votes out of a
        # denominator of two. The counts were right and the denominator was
        # never the number of runs.
        merged.append({"label": label, "features": features, "anomalies": [],
                       "n_label_votes": n_runs,
                       "n_features": len(features)})
    return merged


# ── Main entry point ─────────────────────────────────────────────────────────

def classify_regions(texture_path: Path, mesh, regions: list,
                     n_votes: int = N_VOTES) -> tuple:
    """
    Classify all regions of one fragment.

    Returns (results, crops):
        results : list aligned with `regions`:
            {"region_id", "kind", "plane_index", "area_frac",
             "label", "anomalies": [{"label", "box_pct"}], "n_label_votes"}
        crops   : list from build_region_crops (masks reused for backfill)
    """
    _load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model    = os.environ.get("VISION_MODEL", "gpt-4o")

    tex_img = Image.open(texture_path)
    crops   = build_region_crops(tex_img, mesh, regions)
    numbered = [c for c in crops if c["image"] is not None]

    tex_hash = hashlib.md5(texture_path.read_bytes()).hexdigest()
    reg_sig  = hashlib.md5(json.dumps(
        [[int(r["face_idx"][0]), len(r["face_idx"])] for r in regions]
    ).encode()).hexdigest()[:8]
    # The prompt is part of the cache identity: editing the taxonomy or the
    # anomaly hints must invalidate previous answers, or a changed question
    # silently returns the old answer.
    prompt_sig = hashlib.md5(
        json.dumps([TAXONOMY, ACTIVE, LABEL_RULES, sorted(LOCALIZED),
                    _GROUPED, reference_signature()],
                   sort_keys=True).encode()).hexdigest()[:6]

    print(f"    region classification: {len(numbered)} regions, "
          f"{n_votes} votes — {provider}/{model}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    # Regions go up in small batches, not all at once.
    #
    # Sending a whole fragment in one request let the model compare the regions
    # against each other and settle on a single reading for the batch. Measured
    # on the 2026-08-20 corpus: 4 of 7 calls returned the IDENTICAL feature set
    # for every image in the request, and `exposed_aggregate` came back on 38 of
    # 38 regions. TAXONOMY_REVIEW.md §3 named this mechanism months earlier.
    #
    # BATCH_SIZE trades calls against independence. 1 is fully independent and
    # costs one call per region per vote; the whole fragment is one call and is
    # what produced the anchoring. 3 keeps most of the independence at a
    # fraction of the cost, because the model no longer sees enough of the
    # fragment to form a house style.
    batches = [numbered[i:i + BATCH_SIZE]
               for i in range(0, len(numbered), BATCH_SIZE)] or [[]]
    for run in range(1, n_votes + 1):
        cache_p = (CACHE_DIR / f"reg_{tex_hash}_{reg_sig}_{prompt_sig}_run{run}_"
                               f"b{BATCH_SIZE}_"
                               f"{provider}_{model.replace('/', '-')}.json")
        if cache_p.exists():
            _cached = json.loads(cache_p.read_text(encoding="utf-8"))
            # The key covers the texture, the region partition and the prompt.
            # It does not cover which regions passed the texture gates, and the
            # crops are numbered 1..k over the regions that did. So a change in
            # gate behaviour, such as the smear-mask fix of 2026-08-27, alters k
            # while the key still reports a match, and the cached answers would
            # be read against the wrong regions. Silent, and it would corrupt
            # every downstream result. Check k before trusting the file.
            _want = {str(i) for i in range(1, len(numbered) + 1)}
            _have = {k for k in _cached if str(k).isdigit()}
            if _have and not _have <= _want:
                print(f"      run {run}/{n_votes}: cache holds {len(_have)} regions, "
                      f"this run has {len(numbered)} — re-classifying")
            else:
                runs.append(_cached)
                continue
        print(f"      run {run}/{n_votes}: {len(batches)} batch(es) ...",
              end=" ", flush=True)
        result: dict = {}
        offset = 0
        for batch in batches:
            part = _call_vision(batch, provider, model) if batch else {}
            # each batch numbers its images 1..k; shift back to global indices
            for k in sorted(part, key=lambda x: int(x) if str(x).isdigit() else 0):
                if str(k).isdigit():
                    result[str(offset + int(k))] = part[k]
            offset += len(batch)
            print(".", end="", flush=True)
        cache_p.write_text(json.dumps(result, indent=2), encoding="utf-8")
        runs.append(result)
        print(" OK")

    merged = _merge_votes(runs, len(numbered))

    # align back to full regions list (regions without UV footprint → None)
    results = []
    mi = 0
    for reg, crop in zip(regions, crops):
        if crop["image"] is None:
            results.append({**_region_meta(reg), "label": None,
                            "features": [], "n_features": 0,
                            "anomalies": [], "n_label_votes": 0,
                            "uv_coherence": crop.get("coherence"),
                            "uv_fill": crop.get("uv_fill"),
                            "smear_frac": crop.get("smear_frac"),
                            "skipped": crop.get("skipped")})
        else:
            results.append({**_region_meta(reg), **merged[mi],
                            "uv_coherence": crop.get("coherence"),
                            "uv_fill": crop.get("uv_fill"),
                            "smear_frac": crop.get("smear_frac"),
                            "skipped": None})
            mi += 1
    return results, crops


def _region_meta(reg: dict) -> dict:
    return {"region_id": reg["region_id"], "kind": reg["kind"],
            "plane_index": reg["plane_index"], "area_frac": reg["area_frac"],
            "area_m2": reg.get("area_m2")}


# ── Grid backfill (keeps viewer / feature-texture pipeline unchanged) ────────

def cells_from_regions(results: list, crops: list, texture_size: int,
                       grid_n: int = GRID_N,
                       unscanned_mask: "np.ndarray | None" = None) -> list:
    """
    Build a [row][col] label grid (image space) from region labels + anomalies.

    Per cell: dominant region by masked pixel count → its label.
    Anomaly boxes (crop-percent → texture px) override overlapped cells.
    Cells majority-covered by the UNSCANNED mask are None.
    """
    S = texture_size
    # pixel-count per (cell, region)
    cell_owner = [[None] * grid_n for _ in range(grid_n)]
    cell_count = np.zeros((grid_n, grid_n), dtype=int)
    for res, crop in zip(results, crops):
        if crop["image"] is None or not res["label"]:
            continue
        m = crop["mask"]
        for r in range(grid_n):
            for c in range(grid_n):
                cnt = int(m[r * S // grid_n:(r + 1) * S // grid_n,
                            c * S // grid_n:(c + 1) * S // grid_n].sum())
                if cnt > cell_count[r][c]:
                    cell_count[r][c] = cnt
                    cell_owner[r][c] = res["label"]

    # anomaly overrides
    for res, crop in zip(results, crops):
        if crop["image"] is None:
            continue
        x0, y0, x1, y1 = crop["bbox"]
        bw, bh = (x1 - x0), (y1 - y0)
        for a in res.get("anomalies", []):
            bx0 = x0 + a["box_pct"][0] / 100.0 * bw
            by0 = y0 + a["box_pct"][1] / 100.0 * bh
            bx1 = x0 + a["box_pct"][2] / 100.0 * bw
            by1 = y0 + a["box_pct"][3] / 100.0 * bh
            for r in range(grid_n):
                for c in range(grid_n):
                    cx0, cy0 = c * S / grid_n, r * S / grid_n
                    cx1, cy1 = cx0 + S / grid_n, cy0 + S / grid_n
                    ix = max(0.0, min(bx1, cx1) - max(bx0, cx0))
                    iy = max(0.0, min(by1, cy1) - max(by0, cy0))
                    if ix * iy >= 0.3 * (S / grid_n) ** 2:
                        cell_owner[r][c] = a["label"]

    # UNSCANNED clearing
    if unscanned_mask is not None:
        for r in range(grid_n):
            for c in range(grid_n):
                cell = unscanned_mask[r * S // grid_n:(r + 1) * S // grid_n,
                                      c * S // grid_n:(c + 1) * S // grid_n]
                # An empty slice means grid_n does not divide the atlas evenly.
                # np.mean on it warns and returns nan, nan >= 0.3 is False, so
                # the cell was quietly left uncleared instead of being reported.
                if cell.size and cell.mean() >= 0.3:
                    cell_owner[r][c] = None
    return cell_owner
