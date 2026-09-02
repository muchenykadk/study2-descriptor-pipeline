"""
Phase 3B — Spatial feature classification on texture map.

Divides the texture into a 16×16 global grid, classified quadrant-by-quadrant:
the image is split into 2×2 quadrants, each sent to the vision model at full
resolution with its own 8×8 numbered overlay. This keeps every cell at ~135 px
for a 1080×1080 texture (a global 16×16 overlay in one image would halve that)
and reduces per-image clutter. Each quadrant is classified N_VOTES times and
the majority label per cell wins, so single misreads don't stick.

Results are cached per quadrant + run by image MD5, so the API is only hit
once per texture/quadrant/run.

Usage (called automatically by run_pipeline.py --phase3):
    from ai.texture_segmentation import classify_texture_grid
    grid = classify_texture_grid(texture_path)
    # grid["cells"][row][col] -> label string or None   (16×16, row 0 = top)
"""

import base64
import hashlib
import io
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .vision_client import CACHE_DIR, _load_dotenv
from .taxonomy import TAXONOMY

GRID_N   = 16   # global grid (16×16 = 256 cells)
QUAD     = 2    # split into QUAD×QUAD quadrant images
N_VOTES  = 3    # classification runs per quadrant (majority vote per cell)

_LOCAL_N = GRID_N // QUAD   # cells per quadrant edge (8)

_SYSTEM = (
    "You are a materials scientist classifying demolition concrete surface texture. "
    "Return JSON only — no explanation, no markdown."
)


# ── Grid image generation ─────────────────────────────────────────────────────

def _load_font(font_size: int):
    for fp in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(fp, font_size)
        except Exception:
            pass
    return None


def _make_grid_image(img: Image.Image, grid_n: int) -> bytes:
    """Overlay a numbered NxN grid on a PIL image and return PNG bytes."""
    img  = img.convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    cell_w = w // grid_n
    cell_h = h // grid_n
    font_size = max(cell_h // 5, 14)
    font = _load_font(font_size)

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

def _image_md5(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _seg_cache_path(img_hash: str, qr: int, qc: int, run: int,
                    provider: str, model: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return (CACHE_DIR /
            f"seg_{img_hash}_g{GRID_N}_q{qr}{qc}_run{run}_"
            f"{provider}_{model.replace('/', '-')}.json")


# ── API call ──────────────────────────────────────────────────────────────────

def _make_context_thumb(img: Image.Image, size: int = 512) -> bytes:
    """Downscaled full-atlas thumbnail sent alongside each quadrant for
    global context (low detail — cheap)."""
    thumb = img.convert("RGB").copy()
    thumb.thumbnail((size, size))
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    return buf.getvalue()


def _classify_quadrant(quad_img: Image.Image, non_empty_local: list,
                       provider: str, model: str,
                       qr: int = 0, qc: int = 0,
                       patched_local: list | None = None,
                       context_thumb_b64: str | None = None) -> dict:
    """One API call: classify the 8×8 local grid of a single quadrant image.

    Returns {local_cell_number(str): label|None}.
    """
    total = _LOCAL_N * _LOCAL_N
    empty_count = total - len(non_empty_local)

    grid_png = _make_grid_image(quad_img, _LOCAL_N)
    b64      = base64.b64encode(grid_png).decode("utf-8")

    patched_note = ""
    if patched_local:
        patched_note = (
            f"Cells {sorted(patched_local)} are a digitally reconstructed patch "
            f"(the fragment's unscanned ground-contact face, filled by software) "
            f"— NOT real surface. Assign null to these cells.\n"
        )

    prompt = (
        f"The first image is the {['top','bottom'][qr]}-{['left','right'][qc]} "
        f"quadrant of a concrete-fragment texture atlas, with a "
        f"{_LOCAL_N}×{_LOCAL_N} numbered grid (cells 1–{total}).\n"
        + (f"The second image is the full atlas, for context only — classify "
           f"the quadrant.\n" if context_thumb_b64 else "")
        + f"Cells with surface texture: {non_empty_local}\n"
        f"Cells that are black/empty ({empty_count} total): assign null.\n"
        + patched_note +
        f"\nReturn ONLY a flat JSON object with all {total} cells:\n"
        f'  {{"1": "label", "2": null, "3": "label", ...}}\n\n'
        f"Labels (use ONLY these, or null for empty/background):\n"
        + "\n".join(f"  - {t}" for t in TAXONOMY)
    )

    if provider == "openai":
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}",
                           "detail": "high"}},
        ]
        if context_thumb_b64:
            content.append(
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{context_thumb_b64}",
                               "detail": "low"}})
        resp = client.chat.completions.create(
            model=model, temperature=0.2, max_tokens=1400,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": content},
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
    return cell_labels


# ── Main entry point ──────────────────────────────────────────────────────────

def classify_texture_grid(image_path: Path, grid_n: int = GRID_N,
                          excluded_cells: set | None = None) -> dict:
    """
    Classify each cell of a global grid_n × grid_n grid over the texture.

    The texture is split into QUAD×QUAD quadrants; each quadrant is classified
    N_VOTES times on a local 8×8 grid at full resolution, and the per-cell
    majority label is mapped back to global grid coordinates.  A downscaled
    full-atlas thumbnail is attached to every call for global context.

    excluded_cells : set of global (row, col) cells known to be reconstructed
    patch (UNSCANNED) — named as such in the prompt and never labeled.

    Returns
    -------
    dict with keys:
        "grid_n" : int
        "cells"  : list[list[str|None]]  — [row][col], row 0 = top of image
    """
    if grid_n != GRID_N:
        raise ValueError(f"grid_n is fixed at {GRID_N} (got {grid_n})")

    excluded_cells = excluded_cells or set()

    _load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model    = os.environ.get("VISION_MODEL", "gpt-4o")

    img      = Image.open(image_path).convert("RGB")
    img_arr  = np.array(img)
    img_hash = _image_md5(image_path)
    w, h     = img.size
    qw, qh   = w // QUAD, h // QUAD

    thumb_b64 = base64.b64encode(_make_context_thumb(img)).decode("utf-8")
    # excluded cells participate in the prompt → include them in the cache key
    excl_tag = hashlib.md5(
        json.dumps(sorted(excluded_cells)).encode()).hexdigest()[:8]

    cells = [[None] * GRID_N for _ in range(GRID_N)]

    print(f"    grid classification ({GRID_N}×{GRID_N} via {QUAD}×{QUAD} quadrants, "
          f"{N_VOTES} votes) — {provider}/{model}")

    for qr in range(QUAD):
        for qc in range(QUAD):
            # Local empty-cell map (computed on the quadrant crop)
            quad_arr = img_arr[qr * qh:(qr + 1) * qh, qc * qw:(qc + 1) * qw]
            non_empty_local = [
                lr * _LOCAL_N + lc + 1
                for lr in range(_LOCAL_N)
                for lc in range(_LOCAL_N)
                if not _cell_is_empty(quad_arr, lr, lc, _LOCAL_N)
            ]
            if not non_empty_local:
                continue    # fully empty quadrant — no API call needed

            # Global excluded cells falling in this quadrant → local numbering
            patched_local = [
                lr * _LOCAL_N + lc + 1
                for lr in range(_LOCAL_N)
                for lc in range(_LOCAL_N)
                if (qr * _LOCAL_N + lr, qc * _LOCAL_N + lc) in excluded_cells
            ]

            quad_img = img.crop((qc * qw, qr * qh, (qc + 1) * qw, (qr + 1) * qh))

            # N_VOTES runs (cached individually)
            runs: list[dict] = []
            for run in range(1, N_VOTES + 1):
                cache_p = _seg_cache_path(f"{img_hash}_{excl_tag}", qr, qc, run,
                                          provider, model)
                if cache_p.exists():
                    runs.append(json.loads(cache_p.read_text(encoding="utf-8")))
                    continue
                print(f"      quadrant ({qr},{qc}) run {run}/{N_VOTES} ...",
                      end=" ", flush=True)
                labels = _classify_quadrant(quad_img, non_empty_local,
                                            provider, model,
                                            qr=qr, qc=qc,
                                            patched_local=patched_local,
                                            context_thumb_b64=thumb_b64)
                cache_p.write_text(json.dumps(labels, indent=2), encoding="utf-8")
                runs.append(labels)
                print("OK")

            # Majority vote per local cell → global cell
            for lr in range(_LOCAL_N):
                for lc in range(_LOCAL_N):
                    gr, gc = qr * _LOCAL_N + lr, qc * _LOCAL_N + lc
                    if (gr, gc) in excluded_cells:
                        continue    # reconstructed patch — never labeled
                    key   = str(lr * _LOCAL_N + lc + 1)
                    votes = [r.get(key) for r in runs]
                    votes = [v for v in votes if v in TAXONOMY]
                    if not votes:
                        continue
                    label = Counter(votes).most_common(1)[0][0]
                    cells[gr][gc] = label

    return {"grid_n": GRID_N, "cells": cells}
