#!/usr/bin/env python3
"""
Rebuild the interface from existing records, without re-running the pipeline.

Re-derives the design factors, regenerates every per-fragment HTML report, and
rebuilds the inventory page. Nothing is recomputed from the mesh and no API call
is made: geometry, vision results and viewer data are read from what the
pipeline already wrote.

Use it after editing `env/design_factors.json` (thresholds, candidate uses) or
after changing anything in `report.py` (layout, what the interface shows).

    python 03_src/refresh_factors.py             # factors + reports + inventory
    python 03_src/refresh_factors.py --dry-run   # show what would change
    python 03_src/refresh_factors.py --reports-only   # skip re-deriving factors
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

from descriptors.design_factors import derive as derive_design_factors
from report import generate_report, update_inventory

DEFAULT_DIR = REPO_ROOT / "05_output" / "descriptors"


def _regenerate_report(rec: dict, records_dir: Path) -> None:
    """Rebuild one fragment's HTML from artifacts the pipeline already wrote."""
    frag_id = rec.get("fragment_id", "")
    viewer_p = records_dir / f"{frag_id}_viewer.json"
    viewer = None
    if viewer_p.exists():
        try:
            viewer = json.loads(viewer_p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    glb  = records_dir / f"{frag_id}.glb"
    tex  = records_dir / f"{frag_id}_texture.png"
    feats = {p.stem.replace(f"{frag_id}_feat_", ""): p
             for p in records_dir.glob(f"{frag_id}_feat_*.png")}
    fmap = records_dir / f"{frag_id}_feature_map.png"
    if fmap.exists():
        feats["all"] = fmap
    generate_report(rec, records_dir, viewer_data=viewer,
                    glb_path=glb if glb.exists() else None,
                    texture_path=tex if tex.exists() else None,
                    feature_texture_paths=feats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records-dir", default=str(DEFAULT_DIR))
    ap.add_argument("--dry-run", action="store_true",
                    help="report the change without writing anything")
    ap.add_argument("--reports-only", action="store_true",
                    help="regenerate the HTML only, leave the records untouched")
    args = ap.parse_args()

    records_dir = Path(args.records_dir)
    paths = sorted(records_dir.glob("*_geometry.json"))
    if not paths:
        print(f"\n  No records in {records_dir}. Run the pipeline first.\n")
        sys.exit(1)

    print()
    for p in paths:
        rec = json.loads(p.read_text(encoding="utf-8"))
        before = {u["id"] for u in
                  ((rec.get("procedural") or {}).get("use_suggestions") or [])}
        if args.reports_only:
            proc, after = rec.get("procedural") or {}, before
        else:
            proc  = derive_design_factors(rec)
            after = {u["id"] for u in proc.get("use_suggestions", [])}

        added, gone = sorted(after - before), sorted(before - after)
        change = ""
        if added:
            change += "  +" + ", +".join(added)
        if gone:
            change += "  -" + ", -".join(gone)
        if not before and not after:
            change = "  no candidate use"

        handling = (proc.get("handling_class") or {}).get("value") or "?"
        print(f"  {rec.get('fragment_id','?'):<18} {len(after)} use(s), "
              f"handling {handling}{change}")

        if not args.dry_run:
            if not args.reports_only:
                p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            _regenerate_report(rec, records_dir)

    if args.dry_run:
        print("\n  dry run: nothing written.\n")
        return

    index = update_inventory(records_dir)
    try:
        shown = index.relative_to(REPO_ROOT)
    except ValueError:
        shown = index
    what = "reports + inventory" if args.reports_only else "records + reports + inventory"
    print(f"\n  {len(paths)} fragment(s): {what} rebuilt.")
    print(f"  Inventory: {shown}")
    print(f"  View: python 03_src/run_pipeline.py --serve\n")


if __name__ == "__main__":
    main()
