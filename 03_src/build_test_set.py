#!/usr/bin/env python3
"""
Sample a HELD-OUT test set of surface tiles for human labelling.

Why this exists: the 2026-08-20 control test scored the classifier on the
reference exemplars, which are also what calibrates it. That is circular — the
model was asked about images it had just been shown, and no result from it can
separate recognition from recall. Muchen's point, and it applies to every
feature, not only the two whose exemplars came from one surface.

This samples tiles from the fragment atlases instead. They are never sent as
references, so a classifier scored on them is being asked about surfaces it has
not seen.

    python 03_src/build_test_set.py                 # 30 tiles, all fragments
    python 03_src/build_test_set.py --n 40 --seed 7

Writes:
    01_input/test_tiles/<fragment>_<x>_<y>.png      the tiles
    01_input/test_tiles/_contact_sheet.png          all of them, numbered
    05_output/test_set_labels.csv                   one row per tile, to fill in

Then label every tile in the CSV — multiple features per tile, comma separated,
or `none` where nothing named applies. `none` is a real answer and the set needs
some: it measures how often the classifier invents a feature on plain concrete.

Sampling is deliberately blind. Tiles are taken at random positions on real
surface, not chosen for being interesting, so the label distribution reflects
what the corpus actually contains. Hand-picking tiles that show clear features
would measure the classifier on its best case and report it as its average.
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

INPUT_DIR = REPO_ROOT / "01_input" / "meshes" / "processed"
OUT_DIR   = REPO_ROOT / "01_input" / "test_tiles"
CSV_PATH  = REPO_ROOT / "05_output" / "test_set_labels.csv"

TILE_MM      = 250     # real surface per tile; matches the exemplar scale
MIN_SURFACE  = 0.90    # tile must be at least this much real texture
MAX_TRIES    = 4000


def texel_density(frag: str, size: int) -> float | None:
    """px per mm of real surface, measured from the mesh.

    The first version read `area_m2` from the descriptor record. That key does
    not exist, so every fragment silently fell back to an assumed 1.5 px/mm.
    On FS-001 and FS-007, which sit near 0.24, a 375 px tile then covered about
    1.5 m of real surface — the whole fragment rather than a patch, which is
    what Muchen saw on tiles 22 and 23. Measure it instead.
    """
    # Cached per fragment. Measuring means loading a 100 MB+ GLB, and doing
    # that for every fragment in one process exhausts memory on a modest
    # machine. The mesh is freed as soon as the number is out.
    import json as _json
    cache_p = OUT_DIR / "_texel_density.json"
    try:
        cache = _json.loads(cache_p.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    if frag in cache:
        return cache[frag] or None

    import gc
    import warnings
    warnings.filterwarnings("ignore")
    try:
        import trimesh
        glb = INPUT_DIR / frag / f"{frag}.glb"
        m = trimesh.load(glb, force="mesh", process=False)
        uv = np.asarray(m.visual.uv)[m.faces]
        e1, e2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
        uv_frac = float(np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum() * 0.5)
        area_mm2 = float(m.area)
        if max(m.bounding_box.primitive.extents) < 10.0:
            area_mm2 *= 1e6
        ppm = (float(np.sqrt(uv_frac * size * size / area_mm2))
               if area_mm2 > 0 and uv_frac > 0 else None)
        del m, uv, e1, e2
        gc.collect()
    except Exception:
        ppm = None
    cache[frag] = ppm
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        cache_p.write_text(_json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        pass
    return ppm


def sample(frag_dir: Path, n: int, rng) -> list:
    frag = frag_dir.name
    tex_p = frag_dir / f"{frag}_texture.png"
    if not tex_p.exists():
        return []
    a = np.array(Image.open(tex_p).convert("RGB"))
    lit = a.max(axis=2) > 18
    size = a.shape[0]

    # Tile side in pixels. Fall back to a measured density when the record has
    # no area, so tiles cover a comparable patch of real surface on every
    # fragment rather than a comparable number of pixels.
    ppm = texel_density(frag, size) or 1.5
    side = int(np.clip(TILE_MM * ppm, 120, 640))

    out = []
    tries = 0
    while len(out) < n and tries < MAX_TRIES:
        tries += 1
        x = int(rng.integers(0, size - side))
        y = int(rng.integers(0, size - side))
        if lit[y:y + side, x:x + side].mean() < MIN_SURFACE:
            continue
        if any(abs(x - px) < side // 2 and abs(y - py) < side // 2
               for px, py, _ in out):
            continue                       # keep tiles from overlapping
        out.append((x, y, Image.fromarray(a[y:y + side, x:x + side])))
    return [(frag, x, y, im) for x, y, im in out]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=30, help="total tiles (default 30)")
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--add", action="store_true",
                    help="keep tiles already labelled and top the set up to --n. "
                         "Labelling is expensive; regenerating from scratch throws "
                         "it away.")
    ap.add_argument("--exclude", default="",
                    help="comma-separated fragments to skip, e.g. FRAG-S1-FS-001. "
                         "Use for atlases too coarse to tile: at 0.20 px/mm a tile "
                         "covers 600 mm and shows nothing.")
    args = ap.parse_args()
    excluded = {x.strip() for x in args.exclude.split(",") if x.strip()}

    frags = sorted(d for d in INPUT_DIR.iterdir()
                   if d.is_dir() and (d / f"{d.name}_texture.png").exists()
                   and d.name not in excluded)
    for x in sorted(excluded):
        print(f"  {x}: excluded")

    # Rows already labelled with something usable are carried through untouched:
    # same file, same number, same label. Only the shortfall is sampled.
    kept: list = []
    if args.add and CSV_PATH.exists():
        import csv as _csv
        for r in _csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")):
            tf = (r.get("true_features") or "").replace("，", ",").strip()
            labs = [x.strip() for x in tf.split(",") if x.strip()]
            if labs and "unusable" not in labs and (OUT_DIR / r["tile"]).exists():
                kept.append(r)
        print(f"  keeping {len(kept)} already-labelled tile(s)")
    if not frags:
        print("\n  No fragment textures found.\n")
        return

    rng = np.random.default_rng(args.seed if not args.add else args.seed + 1)
    need = max(0, args.n - len(kept))
    per = max(1, need // max(len(frags), 1))
    tiles = []
    for d in frags:
        got = sample(d, per, rng)
        tiles.extend(got)
        print(f"  {d.name}: {len(got)} tile(s)")
    rng.shuffle(tiles)
    tiles = tiles[:need]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keep_files = {r["tile"] for r in kept}
    for p in OUT_DIR.glob("*.png"):
        if p.name not in keep_files:
            p.unlink()

    rows = list(kept)
    start = max((int(r["#"]) for r in kept), default=0) + 1
    for i, (frag, x, y, im) in enumerate(tiles, start):
        name = f"{i:02d}_{frag}_{x}_{y}.png"
        im.save(OUT_DIR / name)
        rows.append({"#": i, "tile": name, "fragment": frag,
                     "atlas_x": x, "atlas_y": y,
                     "true_features": "", "notes": ""})

    # contact sheet, numbered to match the CSV
    cols, TH = 6, 190
    rowsn = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (TH + 6), rowsn * (TH + 24)), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows):
        im = Image.open(OUT_DIR / r["tile"]).convert("RGB")
        t = im.copy(); t.thumbnail((TH, TH))
        cx, cy = (i % cols) * (TH + 6), (i // cols) * (TH + 24)
        sheet.paste(t, (cx, cy + 18))
        done = bool((r.get("true_features") or "").strip())
        d.text((cx + 3, cy + 3),
               f"{r['#']:>2}  {r['fragment'][-6:]}{'  (labelled)' if done else ''}",
               fill=(120, 170, 120) if done else (210, 215, 230))
    sheet.save(OUT_DIR / "_contact_sheet.png")

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    print(f"\n  {len(rows)} tiles ({len(kept)} already labelled, "
          f"{len(tiles)} new)  -> {OUT_DIR.relative_to(REPO_ROOT)}")
    print(f"  contact sheet -> {(OUT_DIR / '_contact_sheet.png').relative_to(REPO_ROOT)}")
    print(f"  label them in -> {CSV_PATH.relative_to(REPO_ROOT)}")
    print(f"\n  In `true_features`, list every feature you can see, comma "
          f"separated, or `none`.")
    print(f"  `none` matters: it is how the false-positive rate on plain "
          f"concrete gets measured.\n")


if __name__ == "__main__":
    main()
