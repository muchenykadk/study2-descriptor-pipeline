#!/usr/bin/env python3
"""
Ask one yes/no question per feature instead of a multi-label list.

The multi-label prompt gives the model eleven features and asks which apply. On
the held-out set it answered `broken_face, exposed_aggregate` on 25 of 26 tiles
and found none of the nine distinctive features present, scoring no better than
a model that always guesses those two. That is what a safe default looks like:
when a list is offered, naming the two commonest is never badly wrong.

A binary question removes the retreat. "Does this image show brick or masonry
cast into the concrete?" has no safe answer — yes and no are equally exposed.
If the model can see a brick at all, this is the framing that reveals it.

    python 03_src/binary_probe.py                        # every feature
    python 03_src/binary_probe.py --features brick_inclusion,rebar_visible
    python 03_src/binary_probe.py --no-references

One call per feature per batch of tiles, so the whole 26-tile set costs about
one call per feature. Compare the output against score_test_set.py, which used
the same tiles and the same ground truth.
"""

import argparse
import base64
import collections
import csv
import io
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

from PIL import Image                                              # noqa: E402
import ai.region_classification as rc                              # noqa: E402
from ai.taxonomy import ACTIVE, LABEL_RULES                        # noqa: E402
from score_test_set import load_set                                # noqa: E402

TILES_PER_CALL = 8


def _b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def ask(feature: str, imgs: list, provider: str, model: str) -> list:
    """One yes/no per image for a single feature. Returns list of bool."""
    import openai
    rule = LABEL_RULES.get(feature, feature)
    prompt = (
        f"You are looking at {len(imgs)} numbered photographs of demolition "
        f"concrete surfaces.\n\n"
        f"For EACH image, answer ONE question:\n\n"
        f"    Does this image show {feature.replace('_', ' ')}?\n\n"
        f"What counts as {feature.replace('_', ' ')}:\n  {rule}\n\n"
        f"Answer only about what is VISIBLE in that image. Do not consider what "
        f"is likely for demolition concrete in general, and do not let one image "
        f"influence another.\n\n"
        f'Return ONLY JSON: {{"1": true/false, "2": true/false, ...}} for images '
        f"1..{len(imgs)}."
    )
    content = [{"type": "text", "text": prompt}]
    if rc.USE_REFERENCES:
        for lab, ref in rc.load_reference_set():
            if lab != feature:
                continue
            content.append({"type": "text",
                            "text": f"Reference: this IS {feature}."})
            content.append({"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{_b64(ref)}", "detail": "low"}})
    for i, im in enumerate(imgs, 1):
        content.append({"type": "text", "text": f"Image {i}:"})
        content.append({"type": "image_url", "image_url": {
            "url": f"data:image/png;base64,{_b64(im)}", "detail": "high"}})

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"}, temperature=0)
    d = json.loads(r.choices[0].message.content)
    return [bool(d.get(str(i), False)) for i in range(1, len(imgs) + 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--features", default="", help="comma separated; default all active")
    ap.add_argument("--no-references", action="store_true")
    args = ap.parse_args()
    if args.no_references:
        rc.USE_REFERENCES = False

    items = load_set()
    if not items:
        print("\n  No labelled tiles.\n"); return
    feats = ([f.strip() for f in args.features.split(",") if f.strip()]
             or list(ACTIVE))

    rc._load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model = os.environ.get("VISION_MODEL", "gpt-4o")
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n  OPENAI_API_KEY not found.\n"); sys.exit(1)

    print(f"\n  {len(items)} tiles x {len(feats)} feature(s), "
          f"{-(-len(items)//TILES_PER_CALL)} call(s) each"
          f"{', references OFF' if args.no_references else ''}\n")

    rows = []
    for f in feats:
        truth = [f in it["truth"] for it in items]
        if not any(truth):
            print(f"  {f:<20} not present in any tile — skipped")
            continue
        pred = []
        print(f"  {f:<20}", end=" ", flush=True)
        for i in range(0, len(items), TILES_PER_CALL):
            batch = [it["img"] for it in items[i:i + TILES_PER_CALL]]
            try:
                pred += ask(f, batch, provider, model)
            except Exception as e:
                print(f"  ERROR {e}"); pred += [False] * len(batch)
            print(".", end="", flush=True)
        tp = sum(1 for t, p in zip(truth, pred) if t and p)
        fp = sum(1 for t, p in zip(truth, pred) if not t and p)
        fn = sum(1 for t, p in zip(truth, pred) if t and not p)
        rec = tp / (tp + fn) if tp + fn else float("nan")
        pre = tp / (tp + fp) if tp + fp else float("nan")
        print(f"  truth {tp+fn:>2}  TP {tp:>2}  FP {fp:>2}  FN {fn:>2}   "
              f"recall {rec:>4.0%}  precision {pre:>4.0%}"
              if tp + fp else
              f"  truth {tp+fn:>2}  TP {tp:>2}  FP {fp:>2}  FN {fn:>2}   "
              f"recall {rec:>4.0%}  precision    -")
        rows.append((f, tp + fn, tp, fp, fn))

    if rows:
        TP = sum(r[2] for r in rows); FP = sum(r[3] for r in rows)
        FN = sum(r[4] for r in rows)
        print(f"\n  micro-average: recall {TP/(TP+FN) if TP+FN else 0:.0%}, "
              f"precision {TP/(TP+FP) if TP+FP else 0:.0%}  "
              f"(TP {TP}, FP {FP}, FN {FN})")
        print(f"\n  Compare with the multi-label prompt on the same tiles:")
        print(f"    multi-label   recall 80%  precision 66%")
        print(f"    null model    recall 80%  precision 75%")
        print(f"\n  The question that matters is not the micro-average. It is "
              f"whether any\n  distinctive feature moved off zero — those failed "
              f"0 of 9 under multi-label.\n")


if __name__ == "__main__":
    main()
