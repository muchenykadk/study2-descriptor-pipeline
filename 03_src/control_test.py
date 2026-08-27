#!/usr/bin/env python3
"""
Control test: does the classifier discriminate at all?

On the 2026-08-20 corpus every legible region came back `fracture_surface` +
`exposed_aggregate`, including regions sent in separate API calls, so this is
not batch anchoring. Two explanations remain and they call for opposite
responses:

  A. The answer is right. These are broken chunks and nearly every legible
     region really is a fracture surface showing aggregate. The descriptor set
     does not discriminate on this material, which is a finding.
  B. The model is not looking, and returns a plausible constant for anything
     concrete-textured.

The reference exemplars separate the two. They are hand-cropped and filed by
Muchen, so the folder each one sits in is a human label. Sent through the same
prompt as ordinary regions, a discriminating classifier returns the feature the
image was filed under.

    python 03_src/control_test.py              # every exemplar, one pass
    python 03_src/control_test.py --votes 3    # three, as the pipeline does

IMPORTANT: this is a weak test and must be reported as one. The exemplars are
also what CALIBRATES the classifier, so it is being asked about images it has
already been shown. That biases strongly toward success. A failure here is
therefore decisive and a success proves very little: if the model cannot label
its own reference images, explanation B holds.

Set --no-references to remove that circularity, at the cost of testing an
uncalibrated classifier.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

from PIL import Image                                              # noqa: E402
import ai.region_classification as rc                              # noqa: E402


def load_exemplars() -> list:
    """[(true_label, PIL image, filename)] from reference_surfaces/<label>/."""
    out = []
    if not rc.REFERENCE_DIR.is_dir():
        return out
    for folder in sorted(rc.REFERENCE_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            img = Image.open(p).convert("RGB")
            if max(img.size) > rc.CROP_MAX_SIDE:
                img.thumbnail((rc.CROP_MAX_SIDE, rc.CROP_MAX_SIDE))
            out.append((folder.name, img, p.name))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--votes", type=int, default=1)
    ap.add_argument("--no-references", action="store_true",
                    help="remove the circularity: classify without the exemplar set")
    args = ap.parse_args()

    if args.no_references:
        rc.USE_REFERENCES = False

    items = load_exemplars()
    if not items:
        print("\n  No exemplars found.\n")
        return
    print(f"\n  {len(items)} exemplars, "
          f"{len(set(i[0] for i in items))} distinct labels, "
          f"{args.votes} vote(s)"
          f"{', references OFF' if args.no_references else ''}\n")

    # Present each exemplar as if it were a region crop.
    crops = [{"region_id": i, "image": img, "bbox": None, "mask": None,
              "coherence": 1.0, "skipped": None}
             for i, (_lab, img, _n) in enumerate(items)]

    # classify_regions() normally does this; calling _call_vision directly
    # skips it, so the key never reaches the environment.
    import os
    rc._load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model    = os.environ.get("VISION_MODEL", "gpt-4o")
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n  OPENAI_API_KEY not found. Expected in env/.env or the "
              "environment.\n")
        sys.exit(1)

    runs = []
    for v in range(args.votes):
        print(f"    vote {v+1}/{args.votes} ...", end=" ", flush=True)
        result: dict = {}
        offset = 0
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

    hit = 0
    print(f"\n  {'filed as':<20} {'returned':<46} ok")
    for (true_lab, _img, name), m in zip(items, merged):
        got = [f["id"] for f in m["features"]]
        ok = true_lab in got
        hit += ok
        print(f"  {true_lab:<20} {', '.join(got) or '(nothing)':<46} "
              f"{'YES' if ok else 'no'}   {name[:28]}")

    print(f"\n  filed label recovered on {hit}/{len(items)} exemplars "
          f"({hit/len(items):.0%})")

    combos = collections.Counter(frozenset(f["id"] for f in m["features"])
                                 for m in merged)
    print(f"  {len(combos)} distinct answers across {len(items)} images")
    for c, n in combos.most_common():
        print(f"     {n:>3}x  {', '.join(sorted(c)) or '(nothing)'}")
    if len(combos) == 1:
        print("\n  One answer for every image, including images a human filed "
              "as different\n  features. That is explanation B: the classifier "
              "is not discriminating.")


if __name__ == "__main__":
    main()
