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

GRID_N        = 16     # backfill grid resolution (kept for viewer/report)
COHERENCE_MIN = 0.5    # min share of a region's UV footprint in one island
N_VOTES       = 3
CROP_MARGIN   = 16     # px context margin around region bbox
CROP_MAX_SIDE = 1024   # downscale crops larger than this
ANOMALY_LABELS = ["rebar_visible", "staining", "weathered", "opening"]

# Short descriptions so the model knows what to look for. "opening" matters
# because photogrammetry cannot reconstruct a void it never saw into: a pipe
# penetration is closed or mangled in the mesh, but remains plainly visible in
# the texture. Detecting it from the image recovers a feature the geometry
# cannot supply.
ANOMALY_HINTS = {
    "rebar_visible": "exposed steel bar or mesh",
    "staining":      "rust, moss, oil, paint or other discolouration",
    "weathered":     "locally eroded or carbonated patch",
    "opening":       "a hole through or into the fragment, typically a former "
                     "pipe or conduit penetration: a dark round or oval region, "
                     "often with a rim, a mortar collar, or pipe remnants",
}

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
    img = Image.fromarray(arr).filter(ImageFilter.MaxFilter(5))
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
        crop = tex[y0:y1, x0:x1].copy()
        crop[~mask[y0:y1, x0:x1]] = 0          # black out other regions
        img = Image.fromarray(crop)
        if max(img.size) > CROP_MAX_SIDE:
            img.thumbnail((CROP_MAX_SIDE, CROP_MAX_SIDE))
        out.append({"region_id": reg["region_id"], "image": img,
                    "bbox": (int(x0), int(y0), int(x1), int(y1)),
                    "mask": mask, "coherence": round(coh, 3), "skipped": None})
    return out


# ── Vision call ──────────────────────────────────────────────────────────────

def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_vision(crops: list, provider: str, model: str) -> dict:
    """One API call: all region crops numbered; returns parsed dict."""
    numbered = [c for c in crops if c["image"] is not None]
    prompt = (
        f"You receive {len(numbered)} numbered images. Each is one coherent "
        f"surface region of a single demolition concrete fragment, cut out of "
        f"its texture atlas (black = outside the region).\n\n"
        f"For EACH image i return:\n"
        f'  "i": {{"label": <surface label>, '
        f'"anomalies": [{{"label": <anomaly label>, '
        f'"box_pct": [x0, y0, x1, y1]}}, ...]}}\n\n'
        f"Surface labels (choose exactly one per region):\n"
        + "\n".join(f"  - {t}" for t in TAXONOMY) +
        f"\n\nAnomalies: small distinct patches WITHIN the region that differ "
        f"from its overall character. Use only these:\n"
        + "\n".join(f"  - {k}: {v}" for k, v in ANOMALY_HINTS.items())
        + f"\nGive box_pct in % of the image (0-100); empty list if none.\n"
        f"Return ONLY a JSON object with keys 1..{len(numbered)}."
    )
    content = [{"type": "text", "text": prompt}]
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
    """Majority label per region; anomalies kept if matched in ≥2 runs."""
    merged = []
    for i in range(1, n_regions + 1):
        entries = [r.get(str(i)) or {} for r in runs]
        labels  = [e.get("label") for e in entries if e.get("label") in TAXONOMY]
        label   = Counter(labels).most_common(1)[0][0] if labels else None

        # anomaly consensus: a box counts if ≥2 runs contain a same-label box
        # with IoU ≥ 0.3
        all_anoms = []
        for ri, e in enumerate(entries):
            for a in (e.get("anomalies") or []):
                if (a.get("label") in ANOMALY_LABELS
                        and isinstance(a.get("box_pct"), list)
                        and len(a["box_pct"]) == 4):
                    all_anoms.append((ri, a["label"], [float(v) for v in a["box_pct"]]))
        kept = []
        for ri, lbl, box in all_anoms:
            support = {ri}
            for rj, lbl2, box2 in all_anoms:
                if rj != ri and lbl2 == lbl and _iou(box, box2) >= 0.3:
                    support.add(rj)
            if len(support) >= 2 and not any(
                    k["label"] == lbl and _iou(k["box_pct"], box) >= 0.3
                    for k in kept):
                kept.append({"label": lbl, "box_pct": box})
        merged.append({"label": label, "anomalies": kept,
                       "n_label_votes": len(labels)})
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

    print(f"    region classification: {len(numbered)} regions, "
          f"{n_votes} votes — {provider}/{model}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for run in range(1, n_votes + 1):
        cache_p = (CACHE_DIR / f"reg_{tex_hash}_{reg_sig}_run{run}_"
                               f"{provider}_{model.replace('/', '-')}.json")
        if cache_p.exists():
            runs.append(json.loads(cache_p.read_text(encoding="utf-8")))
            continue
        print(f"      run {run}/{n_votes} ...", end=" ", flush=True)
        result = _call_vision(crops, provider, model)
        cache_p.write_text(json.dumps(result, indent=2), encoding="utf-8")
        runs.append(result)
        print("OK")

    merged = _merge_votes(runs, len(numbered))

    # align back to full regions list (regions without UV footprint → None)
    results = []
    mi = 0
    for reg, crop in zip(regions, crops):
        if crop["image"] is None:
            results.append({**_region_meta(reg), "label": None,
                            "anomalies": [], "n_label_votes": 0,
                            "uv_coherence": crop.get("coherence"),
                            "skipped": crop.get("skipped")})
        else:
            results.append({**_region_meta(reg), **merged[mi],
                            "uv_coherence": crop.get("coherence"),
                            "skipped": None})
            mi += 1
    return results, crops


def _region_meta(reg: dict) -> dict:
    return {"region_id": reg["region_id"], "kind": reg["kind"],
            "plane_index": reg["plane_index"], "area_frac": reg["area_frac"]}


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
                if cell.mean() >= 0.3:
                    cell_owner[r][c] = None
    return cell_owner
