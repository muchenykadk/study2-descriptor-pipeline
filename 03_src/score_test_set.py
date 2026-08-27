#!/usr/bin/env python3
"""
Score the classifier against the human-labelled held-out tiles.

The tiles in 01_input/test_tiles/ are sampled blind from the fragment atlases
and were never sent as reference images, so this is the first measurement in
the project that is not circular. Ground truth is Muchen's labelling in
05_output/test_set_labels.csv.

    python 03_src/score_test_set.py                  # calibrated
    python 03_src/score_test_set.py --no-references  # uncalibrated
    python 03_src/score_test_set.py --votes 3

Tiles marked `unusable` are excluded: neither the human nor the model has
anything to read, so scoring them measures the capture, not the classifier.
Tiles marked `none` ARE scored, and they matter most — they are the only way to
see how often a feature is invented on plain concrete.

Reported per feature:

    recall      of the tiles that truly have it, how many did the model find
    precision   of the tiles the model said have it, how many truly do

Both are needed. A model that reports `exposed_aggregate` on everything scores
perfect recall on it and tells you nothing.
"""

import argparse
import collections
import csv
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

from PIL import Image                                              # noqa: E402
import ai.region_classification as rc                              # noqa: E402

TILE_DIR = REPO_ROOT / "01_input" / "test_tiles"
CSV_PATH = REPO_ROOT / "05_output" / "test_set_labels.csv"


def parse_labels(s: str) -> list:
    """Split on ASCII or full-width commas; Excel on a CN locale writes U+FF0C."""
    s = (s or "").replace("，", ",").replace("、", ",").replace(";", ",")
    return [x.strip() for x in s.split(",") if x.strip()]


def load_set() -> list:
    if not CSV_PATH.exists():
        return []
    out = []
    for r in csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")):
        labs = parse_labels(r.get("true_features"))
        if not labs or "unusable" in labs:
            continue
        p = TILE_DIR / r["tile"]
        if not p.exists():
            continue
        img = Image.open(p).convert("RGB")
        if max(img.size) > rc.CROP_MAX_SIDE:
            img.thumbnail((rc.CROP_MAX_SIDE, rc.CROP_MAX_SIDE))
        truth = set() if labs == ["none"] else {l for l in labs if l != "none"}
        out.append({"n": r["#"], "tile": r["tile"], "frag": r["fragment"],
                    "truth": truth, "img": img})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--votes", type=int, default=1)
    ap.add_argument("--no-references", action="store_true")
    args = ap.parse_args()

    if args.no_references:
        rc.USE_REFERENCES = False

    items = load_set()
    if not items:
        print("\n  No usable labelled tiles. Fill `true_features` in "
              f"{CSV_PATH.relative_to(REPO_ROOT)} first.\n")
        return

    rc._load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model    = os.environ.get("VISION_MODEL", "gpt-4o")
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n  OPENAI_API_KEY not found.\n")
        sys.exit(1)

    print(f"\n  {len(items)} usable tiles, {args.votes} vote(s)"
          f"{', references OFF' if args.no_references else ', calibrated'}\n")

    crops = [{"region_id": i, "image": it["img"], "bbox": None, "mask": None,
              "coherence": 1.0, "skipped": None} for i, it in enumerate(items)]

    runs = []
    for v in range(args.votes):
        print(f"    vote {v+1}/{args.votes} ...", end=" ", flush=True)
        result, offset = {}, 0
        for i in range(0, len(crops), rc.BATCH_SIZE):
            batch = crops[i:i + rc.BATCH_SIZE]
            part = rc._call_vision(batch, provider, model)
            for k in sorted(part, key=lambda x: int(x) if str(x).isdigit() else 0):
                if str(k).isdigit():
                    result[str(offset + int(k))] = part[k]
            offset += len(batch)
            print(".", end="", flush=True)
        runs.append(result)
        print(" OK")

    merged = rc._merge_votes(runs, len(items))

    tp = collections.Counter(); fp = collections.Counter(); fn = collections.Counter()
    print(f"\n  {'#':>3} {'truth':<44} {'predicted':<44}")
    for it, m in zip(items, merged):
        pred = {f["id"] for f in m["features"]}
        for f in pred & it["truth"]:  tp[f] += 1
        for f in pred - it["truth"]:  fp[f] += 1
        for f in it["truth"] - pred:  fn[f] += 1
        print(f"  {it['n']:>3} {', '.join(sorted(it['truth'])) or '(none)':<44} "
              f"{', '.join(sorted(pred)) or '(none)':<44}")

    feats = sorted(set(tp) | set(fp) | set(fn))
    print(f"\n  {'feature':<20} {'truth':>6} {'pred':>6} {'TP':>4} {'FP':>4} "
          f"{'FN':>4} {'recall':>8} {'precision':>10}")
    for f in feats:
        t, p_ = tp[f] + fn[f], tp[f] + fp[f]
        rec = tp[f] / t if t else float("nan")
        pre = tp[f] / p_ if p_ else float("nan")
        print(f"  {f:<20} {t:>6} {p_:>6} {tp[f]:>4} {fp[f]:>4} {fn[f]:>4} "
              f"{rec:>7.0%} {pre:>10.0%}" if t or p_ else "")
    TP, FP, FN = sum(tp.values()), sum(fp.values()), sum(fn.values())
    print(f"\n  micro-average: recall {TP/(TP+FN) if TP+FN else 0:.0%}, "
          f"precision {TP/(TP+FP) if TP+FP else 0:.0%}  "
          f"(TP {TP}, FP {FP}, FN {FN})")
    exact = sum(1 for it, m in zip(items, merged)
                if {f["id"] for f in m["features"]} == it["truth"])
    print(f"  exact set match on {exact}/{len(items)} tiles\n")


if __name__ == "__main__":
    main()
