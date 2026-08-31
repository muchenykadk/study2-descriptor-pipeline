"""
Create feature-coloured texture images for 3D viewer overlay.

Two outputs per fragment:
  1. Combined feature map  — all detected labels coloured simultaneously
  2. Per-label highlight   — one image per label: that label bright, rest dark/grey

Applying any of these to the same UV-mapped GLB mesh in Three.js shows exactly
WHERE each surface feature sits on the 3D object.

Usage (called automatically by run_pipeline.py):
    from descriptors.feature_texture import build_feature_textures
    result = build_feature_textures(texture_path, grid_n, cells, output_dir, frag_id)
    # result = {
    #   "all": Path(..._feature_map.png),
    #   "fracture_surface": Path(..._feat_fracture_surface.png),
    #   ...
    # }
"""

from pathlib import Path

import numpy as np
from PIL import Image

# Label → RGB, derived from the taxonomy so a new label needs no code change.
# This used to be a hardcoded table that had to be kept in step with
# env/taxonomy.json and report.py by hand, which meant a label added to the
# taxonomy would silently have no colour here and vanish from the feature map.
def _hex_to_rgb(value: str) -> tuple:
    v = value.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


try:
    from ai.taxonomy import LABEL_COLORS as _HEX
except ImportError:                      # standalone use without the package path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from ai.taxonomy import LABEL_COLORS as _HEX

_FALLBACK_RGB = (156, 163, 175)          # grey, for a label with no colour set
_LABEL_RGB = {k: _hex_to_rgb(v) for k, v in _HEX.items()}
# Stable integer code per label, for the per-pixel map. Taxonomy order, so the
# codes match the feature_id already stored in every viewer JSON.
_LABELS = list(_HEX)
_LABEL_CODE = {lab: i for i, lab in enumerate(_LABELS)}

_BG_THRESHOLD  = 18     # pixel max below this → no UV content (background)
_COMBINED_BLEND = 0.72  # feature colour weight in combined map
_HIGHLIGHT_BLEND = 0.88 # feature colour weight for the highlighted label
_DIM_FACTOR      = 0.18 # brightness fraction for non-highlighted labels


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_image(image_path: Path):
    """Return (original float32 array, h, w)."""
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    return arr, h, w


def _surface_mask(orig_cell: np.ndarray) -> np.ndarray:
    """Boolean mask: True where the pixel has actual UV content (not background)."""
    return np.any(orig_cell > _BG_THRESHOLD, axis=2)


def _blend(orig_cell: np.ndarray, rgb: tuple, alpha: float) -> np.ndarray:
    """Blend original texture with a flat colour. alpha = feature weight."""
    feat    = np.array(rgb, dtype=np.float32)
    blended = (1.0 - alpha) * orig_cell + alpha * feat
    return np.clip(blended, 0, 255)


def _cell_slice(h: int, w: int, row: int, col: int, grid_n: int):
    r0 = row * h // grid_n;  r1 = (row + 1) * h // grid_n
    c0 = col * w // grid_n;  c1 = (col + 1) * w // grid_n
    return r0, r1, c0, c1


def _save(arr: np.ndarray, path: Path, label: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8)).save(path)
    tag = f" ({label})" if label else ""
    h, w = arr.shape[:2]
    print(f"  Feature texture{tag} → {path.name}  ({w}×{h} px)")


# ── Label map: one label per PIXEL, from the region masks ────────────────────
#
# The grid path below colours whole 16x16 atlas cells, each won outright by
# whichever region covers the most pixels in it. Measured on FS-002, that put
# the right label on 65.5% of the surface: 14.7% carried a neighbouring
# region's label and 19.8% was on regions the pipeline had explicitly declined
# to classify and coloured them anyway. The region masks are exact and were
# already computed, so there is no reason to quantise them.


def label_map_from_regions(results: list, crops: list, size: int,
                           unscanned_mask: "np.ndarray | None" = None) -> np.ndarray:
    """Per-pixel label codes over the atlas: index into _LABELS, or -1.

    Integer codes rather than label strings: at 4096 the atlas is 16.7 million
    pixels, and an object array of that size costs a Python-level pass for
    every operation on it. int16 keeps the whole map at 33 MB and every
    downstream test a vectorised comparison.

    `results` and `crops` come from classify_regions() and are ordered largest
    region first. They are painted in that order so a small region drawn later
    is not swallowed by a large one; the rasterised masks are dilated and
    closed, so they overlap slightly at region boundaries even though the face
    sets themselves are disjoint.
    """
    out = np.full((size, size), -1, dtype=np.int16)

    for res, crop in zip(results, crops):
        if crop.get("image") is None or not res.get("label"):
            continue                       # unclassified regions stay unpainted
        code = _LABEL_CODE.get(res["label"])
        if code is None:
            continue
        m = crop["mask"]
        if m is None or m.shape != (size, size):
            continue
        out[m] = code

    # Localized anomalies override the region label inside their box, so a
    # patch of exposed steel on a formwork face reads as steel rather than
    # disappearing into the face it sits on. Only within that region's own
    # mask: the box is in crop coordinates and says nothing about its
    # neighbours.
    for res, crop in zip(results, crops):
        if crop.get("image") is None or not crop.get("bbox"):
            continue
        x0, y0, x1, y1 = crop["bbox"]
        bw, bh = (x1 - x0), (y1 - y0)
        m = crop["mask"]
        for a in res.get("anomalies", []):
            code = _LABEL_CODE.get(a.get("label"))
            if code is None:
                continue                   # no colour: not drawable on this map
            bx0 = int(x0 + a["box_pct"][0] / 100.0 * bw)
            by0 = int(y0 + a["box_pct"][1] / 100.0 * bh)
            bx1 = int(x0 + a["box_pct"][2] / 100.0 * bw)
            by1 = int(y0 + a["box_pct"][3] / 100.0 * bh)
            bx0, bx1 = max(0, min(bx0, bx1)), min(size, max(bx0, bx1))
            by0, by1 = max(0, min(by0, by1)), min(size, max(by0, by1))
            if bx1 <= bx0 or by1 <= by0:
                continue
            sub = out[by0:by1, bx0:bx1]
            sub[m[by0:by1, bx0:bx1]] = code

    if unscanned_mask is not None and unscanned_mask.shape == (size, size):
        out[unscanned_mask.astype(bool)] = -1

    return out


def masks_by_feature(results: list, crops: list, size: int,
                     unscanned_mask: "np.ndarray | None" = None) -> dict:
    """One boolean mask per feature: every region that carries it.

    The combined map can only show one colour per pixel, so it draws the
    highest-precedence feature. The per-feature highlights have no such limit
    and must not inherit it: a region that is both `fracture_surface` and
    `exposed_aggregate` has to appear under BOTH, or clicking a feature chip
    would show only the features that happen to win precedence and the rest
    would look absent.
    """
    out: dict = {}
    for res, crop in zip(results, crops):
        if crop.get("image") is None:
            continue
        m = crop.get("mask")
        if m is None or m.shape != (size, size):
            continue
        feats = res.get("features")
        if not feats:                                   # pre-2026-08-20 record
            feats = [{"id": res.get("label")}] if res.get("label") else []
        for f in feats:
            fid = f.get("id") if isinstance(f, dict) else f
            if fid not in _LABEL_RGB:
                continue
            acc = out.get(fid)
            out[fid] = m.copy() if acc is None else (acc | m)

    if unscanned_mask is not None and unscanned_mask.shape == (size, size):
        us = unscanned_mask.astype(bool)
        for fid in out:
            out[fid] &= ~us
    return {k: v for k, v in out.items() if v.any()}


def create_highlight_from_mask(image_path: Path, mask: np.ndarray,
                               others: np.ndarray, target_label: str,
                               output_path: Path) -> None:
    """One feature vivid, every other classified pixel dimmed."""
    original, h, w = _load_image(image_path)
    out = np.full((h, w, 3), 14.0, dtype=np.float32)
    rgb = _LABEL_RGB.get(target_label)
    if rgb is None:
        _save(out, output_path, target_label)
        return
    surface = _surface_mask(original)
    target  = mask & surface
    dim     = (others & surface) & ~target
    grey = np.repeat(original.mean(axis=2, keepdims=True) * _DIM_FACTOR, 3, axis=2)
    out[dim]    = np.clip(grey, 0, 255)[dim]
    out[target] = np.clip(_blend(original, rgb, _HIGHLIGHT_BLEND), 0, 255)[target]
    _save(out, output_path, target_label)


def labels_in_map(label_map: np.ndarray) -> list:
    """Label names present in a code map, in taxonomy order."""
    codes = np.unique(label_map)
    return [_LABELS[c] for c in codes if c >= 0]


def create_feature_texture_from_map(image_path: Path, label_map: np.ndarray,
                                    output_path: Path) -> None:
    """Combined feature map, coloured per pixel from the region masks."""
    original, h, w = _load_image(image_path)
    out = np.full((h, w, 3), 14.0, dtype=np.float32)
    surface = _surface_mask(original)

    for label in labels_in_map(label_map):
        rgb = _LABEL_RGB.get(label)
        if rgb is None:
            continue
        sel = (label_map == _LABEL_CODE[label]) & surface
        if sel.any():
            out[sel] = _blend(original, rgb, _COMBINED_BLEND)[sel]

    _save(out, output_path)


def create_highlight_texture_from_map(image_path: Path, label_map: np.ndarray,
                                      target_label: str,
                                      output_path: Path) -> None:
    """One label vivid, every other labelled pixel dimmed to grey."""
    original, h, w = _load_image(image_path)
    out = np.full((h, w, 3), 14.0, dtype=np.float32)
    rgb = _LABEL_RGB.get(target_label)
    if rgb is None:
        _save(out, output_path, target_label)
        return

    surface  = _surface_mask(original)
    labelled = (label_map >= 0) & surface
    target   = (label_map == _LABEL_CODE[target_label]) & surface

    grey  = np.repeat(original.mean(axis=2, keepdims=True) * _DIM_FACTOR, 3, axis=2)
    other = labelled & ~target
    out[other]  = np.clip(grey, 0, 255)[other]
    out[target] = np.clip(_blend(original, rgb, _HIGHLIGHT_BLEND), 0, 255)[target]

    _save(out, output_path, target_label)


# ── Public API ────────────────────────────────────────────────────────────────

def create_feature_texture(image_path: Path, grid_n: int, cells: list,
                            output_path: Path) -> None:
    """Combined feature map: all detected labels coloured simultaneously."""
    original, h, w = _load_image(image_path)
    out = np.full((h, w, 3), 14.0, dtype=np.float32)

    for row in range(grid_n):
        for col in range(grid_n):
            label = cells[row][col]
            rgb   = _LABEL_RGB.get(label) if label else None
            if rgb is None:
                continue
            r0, r1, c0, c1 = _cell_slice(h, w, row, col, grid_n)
            orig_cell = original[r0:r1, c0:c1]
            mask = _surface_mask(orig_cell)
            blended = _blend(orig_cell, rgb, _COMBINED_BLEND)
            out[r0:r1, c0:c1][mask] = blended[mask]

    _save(out, output_path)


def create_highlight_texture(image_path: Path, grid_n: int, cells: list,
                              target_label: str, output_path: Path) -> None:
    """
    Highlight texture for a single label.
    Target label: vivid feature colour.
    Other labelled cells: dark grey (shape visible, dimmed).
    Background: near-black.
    """
    original, h, w = _load_image(image_path)
    out = np.full((h, w, 3), 14.0, dtype=np.float32)
    rgb = _LABEL_RGB.get(target_label)
    if rgb is None:
        _save(out, output_path, target_label)
        return

    for row in range(grid_n):
        for col in range(grid_n):
            label = cells[row][col]
            if label is None:
                continue
            r0, r1, c0, c1 = _cell_slice(h, w, row, col, grid_n)
            orig_cell = original[r0:r1, c0:c1]
            mask = _surface_mask(orig_cell)

            if label == target_label:
                blended = _blend(orig_cell, rgb, _HIGHLIGHT_BLEND)
            else:
                # Grey-dim: show fragment shape but suppress other features
                grey = orig_cell.mean(axis=2, keepdims=True) * _DIM_FACTOR
                blended = np.repeat(grey, 3, axis=2)

            blended = np.clip(blended, 0, 255)
            out[r0:r1, c0:c1][mask] = blended[mask]

    _save(out, output_path, target_label)


def build_feature_textures(image_path: Path, grid_n: int, cells: list,
                            output_dir: Path, frag_id: str,
                            label_map: "np.ndarray | None" = None,
                            feature_masks: "dict | None" = None) -> dict:
    """
    Generate all feature textures for a fragment and return their paths.

    `label_map` is the per-pixel path and is preferred: build it with
    label_map_from_regions(). `grid_n` and `cells` are the fallback for
    --grid-legacy and point clouds, which have no regions to draw from.

    Returns
    -------
    dict with:
        "all"              : Path to combined feature map
        "<label_name>"     : Path to per-label highlight texture (one per detected label)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clear this fragment's previous highlights before writing the new set.
    #
    # One PNG is written per feature currently detected, and nothing removed the
    # ones for features that are no longer found, so they accumulated across
    # runs. By 2026-08-25 the output folder held 26 highlights, 44 MB, for
    # features absent from the records beside them: `fracture_surface` and
    # `cast_in_brick` from before the rename, `crack` from before its
    # retirement, and eleven for active features a re-run had stopped
    # detecting. That last group is the harmful one, because
    # `refresh_factors.py` builds the report's feature chips by globbing these
    # files, so a stale highlight puts a chip for `rebar_visible` on a fragment
    # whose record has no reinforcement.
    #
    # The feature map itself needs no clearing; it is a single file, overwritten
    # each run.
    for stale in output_dir.glob(f"{frag_id}_feat_*.png"):
        stale.unlink()

    paths: dict = {}
    all_path = output_dir / f"{frag_id}_feature_map.png"

    if label_map is not None:
        create_feature_texture_from_map(image_path, label_map, all_path)
        paths["all"] = all_path
        if feature_masks:
            # Multi-label: a region appears under every feature it carries.
            union = None
            for m in feature_masks.values():
                union = m.copy() if union is None else (union | m)
            for label, m in feature_masks.items():
                lbl_path = output_dir / f"{frag_id}_feat_{label}.png"
                create_highlight_from_mask(image_path, m, union, label, lbl_path)
                paths[label] = lbl_path
        else:
            for label in [l for l in labels_in_map(label_map) if l in _LABEL_RGB]:
                lbl_path = output_dir / f"{frag_id}_feat_{label}.png"
                create_highlight_texture_from_map(image_path, label_map, label, lbl_path)
                paths[label] = lbl_path
        return paths

    # Collect labels present in the grid
    labels_present = sorted({
        cells[r][c]
        for r in range(grid_n) for c in range(grid_n)
        if cells[r][c] and cells[r][c] in _LABEL_RGB
    })

    # Combined map
    create_feature_texture(image_path, grid_n, cells, all_path)
    paths["all"] = all_path

    # Per-label highlight
    for label in labels_present:
        lbl_path = output_dir / f"{frag_id}_feat_{label}.png"
        create_highlight_texture(image_path, grid_n, cells, label, lbl_path)
        paths[label] = lbl_path

    return paths
