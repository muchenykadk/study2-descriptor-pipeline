"""
Phase 3B — Spatial feature classification on texture map.

Divides the texture into an NxN numbered grid, asks the vision model to
classify each cell, and returns a 2D label grid. Results are cached by
image MD5 + grid_n so the API call is only made once per texture.

Usage (called automatically by run_pipeline.py --phase3):
    from ai.texture_segmentation import classify_texture_grid
    grid = classify_texture_grid(texture_path)
    # grid["cells"][row][col] -> label string or None
"""

import base64
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .vision_client import TAXONOMY, CACHE_DIR, _load_dotenv

GRID_N = 8   # 8×8 = 64 cells

_SYSTEM = (
    "You are a materials scientist classifying demolition concrete surface texture. "
    "Return JSON only — no explanation, no markdown."
)


# ── Grid image generation ─────────────────────────────────────────────────────

def _make_grid_image(image_path: Path, grid_n: int) -> bytes:
    """Overlay a numbered NxN grid on the texture and return PNG bytes."""
    img  = Image.open(image_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    cell_w = w // grid_n
    cell_h = h // grid_n
    font_size = max(cell_h // 5, 14)

    # Try to load a bold system font; fall back to PIL default
    font = None
    for fp in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            pass

    for row in range(grid_n):
        for col in range(grid_n):
            cell_num = row * grid_n + col + 1
            x0, y0 = col * cell_w, row * cell_h
            x1, y1 = x0 + cell_w - 1, y0 + cell_h - 1
            draw.rectangle([x0, y0, x1, y1], outline=(255, 220, 0), width=2)
            # Number with dark background for contrast
            label = str(cell_num)
            tx, ty = x0 + 5, y0 + 4
            bg_w = font_size * len(label) // 2 + 10
            draw.rectangle([tx - 3, ty - 2, tx + bg_w, ty + font_size + 2],
                           fill=(0, 0, 0))
            if font:
                draw.text((tx, ty), label, fill=(255, 220, 0), font=font)
            else:
                draw.text((tx, ty), label, fill=(255, 220, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Empty cell detection ──────────────────────────────────────────────────────

def _cell_is_empty(img_array: np.ndarray, row: int, col: int, grid_n: int,
                   threshold: int = 15, min_black_frac: float = 0.90) -> bool:
    """Return True if ≥ min_black_frac of the cell has no UV content (near-black)."""
    h, w = img_array.shape[:2]
    r0, r1 = row * h // grid_n, (row + 1) * h // grid_n
    c0, c1 = col * w // grid_n, (col + 1) * w // grid_n
    cell     = img_array[r0:r1, c0:c1]
    is_black = np.all(cell < threshold, axis=2)
    return float(is_black.mean()) >= min_black_frac


# ── Cache ─────────────────────────────────────────────────────────────────────

def _seg_cache_path(image_path: Path, grid_n: int, provider: str, model: str) -> Path:
    with open(image_path, "rb") as f:
        h = hashlib.md5(f.read()).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"seg_{h}_g{grid_n}_{provider}_{model.replace('/', '-')}.json"


# ── Main entry point ──────────────────────────────────────────────────────────

def classify_texture_grid(image_path: Path, grid_n: int = GRID_N) -> dict:
    """
    Classify each grid cell in the texture.

    Parameters
    ----------
    image_path : Path to the texture PNG.
    grid_n     : Grid dimension (grid_n × grid_n cells).

    Returns
    -------
    dict with keys:
        "grid_n" : int
        "cells"  : list[list[str|None]]  — [row][col], row 0 = top of image
    """
    _load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model    = os.environ.get("VISION_MODEL", "gpt-4o")

    cache_p = _seg_cache_path(image_path, grid_n, provider, model)
    if cache_p.exists():
        print(f"    grid classification ({grid_n}×{grid_n}) — cache hit")
        return json.loads(cache_p.read_text(encoding="utf-8"))

    print(f"    grid classification ({grid_n}×{grid_n}) — calling {provider}/{model} ...",
          end=" ", flush=True)

    img_array = np.array(Image.open(image_path).convert("RGB"))
    total     = grid_n * grid_n

    # Tell the model which cells have content (so it doesn't guess on empties)
    non_empty = [
        row * grid_n + col + 1
        for row in range(grid_n)
        for col in range(grid_n)
        if not _cell_is_empty(img_array, row, col, grid_n)
    ]
    empty_count = total - len(non_empty)

    grid_png = _make_grid_image(image_path, grid_n)
    b64      = base64.b64encode(grid_png).decode("utf-8")

    prompt = (
        f"The texture has a {grid_n}×{grid_n} numbered grid (cells 1–{total}).\n"
        f"Cells with surface texture: {non_empty}\n"
        f"Cells that are black/empty ({empty_count} total): assign null.\n\n"
        f"Return ONLY a flat JSON object with all {total} cells:\n"
        f'  {{"1": "label", "2": null, "3": "label", ...}}\n\n'
        f"Labels (use ONLY these, or null for empty/background):\n"
        + "\n".join(f"  - {t}" for t in TAXONOMY)
    )

    if provider == "openai":
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model=model, temperature=0, max_tokens=1400,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}",
                                   "detail": "high"}},
                ]},
            ],
        )
        raw = resp.choices[0].message.content.strip()
    else:
        raise NotImplementedError(
            f"Grid segmentation not yet implemented for provider '{provider}'. "
            f"Set VISION_PROVIDER=openai in env/.env"
        )

    # Parse JSON (tolerate markdown fences)
    cell_labels: dict = {}
    text = raw
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                cell_labels = json.loads(part)
                break
            except json.JSONDecodeError:
                continue
    else:
        try:
            cell_labels = json.loads(text)
        except json.JSONDecodeError:
            print(f"PARSE ERROR — raw: {raw[:80]}")

    # Reshape to 2D [row][col]
    cells = []
    for row in range(grid_n):
        row_labels = []
        for col in range(grid_n):
            key   = str(row * grid_n + col + 1)
            label = cell_labels.get(key)
            row_labels.append(label if label in TAXONOMY else None)
        cells.append(row_labels)

    result = {"grid_n": grid_n, "cells": cells}
    cache_p.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("OK")
    return result
