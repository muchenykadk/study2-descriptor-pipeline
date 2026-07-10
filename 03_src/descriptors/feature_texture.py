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

# Label → RGB — must match report.py _LABEL_COLORS
_LABEL_RGB = {
    "formwork_imprint":  (96,  165, 250),   # #60a5fa  blue
    "fracture_surface":  (248, 113, 113),   # #f87171  red
    "exposed_aggregate": (251, 191,  36),   # #fbbf24  amber
    "rebar_visible":     (249, 115,  22),   # #f97316  orange
    "weathered":         (163, 230,  53),   # #a3e635  lime
    "staining":          (192, 132, 252),   # #c084fc  purple
    "original_finish":   (52,  211, 153),   # #34d399  emerald
}

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
                            output_dir: Path, frag_id: str) -> dict:
    """
    Generate all feature textures for a fragment and return their paths.

    Returns
    -------
    dict with:
        "all"              : Path to combined feature map
        "<label_name>"     : Path to per-label highlight texture (one per detected label)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect labels present in the grid
    labels_present = sorted({
        cells[r][c]
        for r in range(grid_n) for c in range(grid_n)
        if cells[r][c] and cells[r][c] in _LABEL_RGB
    })

    paths: dict = {}

    # Combined map
    all_path = output_dir / f"{frag_id}_feature_map.png"
    create_feature_texture(image_path, grid_n, cells, all_path)
    paths["all"] = all_path

    # Per-label highlight
    for label in labels_present:
        lbl_path = output_dir / f"{frag_id}_feat_{label}.png"
        create_highlight_texture(image_path, grid_n, cells, label, lbl_path)
        paths[label] = lbl_path

    return paths
