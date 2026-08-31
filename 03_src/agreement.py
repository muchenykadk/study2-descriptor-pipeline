#!/usr/bin/env python3
"""
Inter-run agreement for the region classifier, from the cached votes.

Every region batch is sent to the model N_VOTES times and each run is cached
separately, so repeatability can be measured after the fact without spending a
single additional call. This reads those caches and reports, per feature, how
often the runs agreed.

    python 03_src/agreement.py
    python 03_src/agreement.py --md          # markdown table for the paper

WHAT THIS NUMBER IS, AND WHAT IT IS NOT

It is the stability of the classifier under repetition: same images, same
prompt, same model, three independent calls. It says whether the pipeline
returns the same answer twice.

It is NOT accuracy. Nothing here compares the model against a human, so a
feature can be reported unanimously and still be wrong. High agreement on a
near-constant output is close to guaranteed and means very little: if the model
returns the same two features on every region, the runs cannot easily disagree.
Report agreement alongside how many distinct features actually occur, or the
number will flatter the method.

Both figures are printed below for exactly that reason.
"""

import argparse
import collections
import glob
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "05_output" / "ai_cache"


def load_runs() -> dict:
    """{batch_signature: {run_number: parsed_response}} for region batches."""
    runs: dict = collections.defaultdict(dict)
    for p in glob.glob(str(CACHE_DIR / "reg_*_run*.json")):
        m = re.match(r"reg_(.+)_run(\d)_", os.path.basename(p))
        if not m:
            continue
        try:
            runs[m.group(1)][int(m.group(2))] = json.loads(
                Path(p).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return runs


def _features(entry: dict) -> set:
    out = set()
    for f in (entry or {}).get("features") or []:
        fid = f.get("id") if isinstance(f, dict) else f
        if fid:
            out.add(fid)
    return out


def _is_multilabel(group: dict) -> bool:
    """True if these cached runs came from the multi-label prompt.

    The cache holds answers to two different questions. Before 2026-08-20 the
    model was asked for ONE label per region and returned `label`; after, it is
    asked for every feature and returns `features`. Agreement means something
    different in each case, and mixing them inflates the figure: a one-of-eight
    choice repeated three times agrees far less often than a list does, so the
    old batches drag the average down while looking like the same measurement.
    Count only the current schema, and say how many were set aside.
    """
    for run in group.values():
        for entry in run.values():
            if isinstance(entry, dict) and "features" in entry:
                return True
    return False


def measure(runs: dict) -> tuple:
    with_all_runs = [g for g in runs.values() if len(g) >= 3]
    complete = [g for g in with_all_runs if _is_multilabel(g)]
    skipped  = len(with_all_runs) - len(complete)
    per_feat = collections.defaultdict(lambda: collections.Counter())
    n_obs = 0
    per_region_sets = []
    for g in complete:
        n_runs = len(g)
        for key in set().union(*[set(r) for r in g.values()]):
            seen = collections.Counter()
            for r in g.values():
                for fid in _features(r.get(key)):
                    seen[fid] += 1
            if not seen:
                continue
            n_obs += 1
            per_region_sets.append(frozenset(
                f for f, c in seen.items() if c > n_runs // 2))
            for fid, c in seen.items():
                per_feat[fid][c] += 1
    return complete, per_feat, n_obs, per_region_sets, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", action="store_true", help="markdown table")
    args = ap.parse_args()

    runs = load_runs()
    complete, per_feat, n_obs, region_sets, skipped = measure(runs)
    if not complete:
        print("\n  No region batch has three cached runs yet.\n")
        return

    rows = []
    for fid, c in sorted(per_feat.items(), key=lambda kv: -sum(kv[1].values())):
        t = sum(c.values())
        rows.append((fid, c[3], c[2], c[1], c[3] / t))
    tot3 = sum(r[1] for r in rows)
    tot2 = sum(r[2] for r in rows)
    tot1 = sum(r[3] for r in rows)
    tot = tot3 + tot2 + tot1

    if args.md:
        print("\n| feature | 3/3 | 2/3 | 1/3 | unanimous |")
        print("|---|---:|---:|---:|---:|")
        for fid, a, b, c, u in rows:
            print(f"| `{fid}` | {a} | {b} | {c} | {u:.0%} |")
        print(f"| **all** | **{tot3}** | **{tot2}** | **{tot1}** | "
              f"**{tot3/tot:.0%}** |")
    else:
        print(f"\n  {len(complete)} region batches with 3 cached runs, "
              f"{n_obs} region observations")
        if skipped:
            print(f"  ({skipped} older batch(es) set aside: single-label prompt, "
                  f"not the same measurement)")
        print()
        print(f"  {'feature':<20} {'3/3':>5} {'2/3':>5} {'1/3':>5}   unanimous")
        for fid, a, b, c, u in rows:
            print(f"    {fid:<18} {a:>5} {b:>5} {c:>5}   {u:>6.0%}")
        print(f"\n    {'ALL':<18} {tot3:>5} {tot2:>5} {tot1:>5}   "
              f"{tot3/tot:>6.0%} unanimous, "
              f"{(tot3+tot2)/tot:.0%} survive the 2-of-3 threshold")

    # The context without which the agreement figure is misleading.
    distinct = len(per_feat)
    combos = collections.Counter(region_sets)
    print(f"\n  Diversity, for reading the figure above honestly:")
    print(f"    {distinct} distinct features occur across {n_obs} regions")
    print(f"    {len(combos)} distinct feature COMBINATIONS:")
    for combo, n in combos.most_common():
        print(f"      {n:>3}x  {', '.join(sorted(combo)) or '(none)'}")
    top = combos.most_common(1)[0]
    print(f"\n    {top[1]/n_obs:.0%} of regions return the same combination. "
          f"Agreement is high partly\n    because the output varies little; it "
          f"measures repeatability, not accuracy.")


if __name__ == "__main__":
    main()
