#!/usr/bin/env python3
"""
Query the fragment records.

Structured predicates over the explicit fields of the per-fragment JSON records
produced by `run_pipeline.py`.  No natural language, no embeddings: the
descriptors are already symbolic, so selection is exact filtering.

Usage
-----
    # by intended design use
    python 03_src/query.py --use bench_top
    python 03_src/query.py --use bar_table_stand --rank mass

    # by surface condition, on any face
    python 03_src/query.py --label formwork_imprint --min-face-area 0.3

    # combined, with a mass ceiling for two-person handling
    python 03_src/query.py --use seat_block --max-mass 400 --handling two_person

    # what uses can each fragment serve?
    python 03_src/query.py --list-uses

    # evaluation baseline: withhold the surface descriptors
    python 03_src/query.py --use bench_top --geometry-only

Unsupported predicates raise rather than return a plausible wrong answer, so a
query the descriptors cannot express fails openly.
"""

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "03_src"))

from descriptors.design_factors import derive as derive_design_factors, load_factors

DEFAULT_DIR = REPO_ROOT / "05_output" / "descriptors"


class UnsupportedQuery(Exception):
    """Raised when a predicate cannot be expressed over the descriptor set."""


# ── loading ──────────────────────────────────────────────────────────────────

def load_records(records_dir: Path = DEFAULT_DIR) -> list:
    """Load every *_geometry.json in the directory, sorted by fragment id."""
    out = []
    for p in sorted(records_dir.glob("*_geometry.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            print(f"  ! skipping unreadable record: {p.name}", file=sys.stderr)
    return out


def strip_surface(record: dict) -> dict:
    """Return a copy with the surface descriptors withheld.

    The geometry-only baseline for the evaluation: everything the vision model
    contributed is removed, and the design factors are re-derived from geometry
    alone, so the difference between the two runs isolates what surface
    characterization adds.
    """
    r = copy.deepcopy(record)
    r.pop("vision", None)
    for face in r.get("planarity", []) or []:
        face.pop("surface_label", None)
        face.pop("anomalies", None)
    derive_design_factors(r)
    return r


# ── predicates ───────────────────────────────────────────────────────────────

def _uses(record: dict) -> list:
    return (record.get("procedural") or {}).get("use_suggestions") or []


def _face_matches(record: dict, label=None, min_area=None,
                  max_rms=None, anomaly=None, reliable_only=False) -> list:
    """Indices of faces satisfying the given conditions."""
    hits = []
    for i, f in enumerate(record.get("planarity", []) or []):
        if label and label not in (set(f.get("features") or [])
                                   | ({f["surface_label"]}
                                      if f.get("surface_label") else set())):
            continue
        if min_area is not None and not (f.get("area_m2_est") or 0) >= min_area:
            continue
        if max_rms is not None and not (f.get("fit_rms_mm") or 1e9) <= max_rms:
            continue
        if anomaly and anomaly not in {a.get("label")
                                       for a in (f.get("anomalies") or [])}:
            continue
        if reliable_only and not f.get("scan_reliable", True):
            continue
        hits.append(i)
    return hits


def select(records: list, use=None, label=None, anomaly=None,
           min_face_area=None, max_face_rms=None, reliable_only=False,
           min_mass=None, max_mass=None, min_thickness=None, max_thickness=None,
           handling=None, connection=None, assignment=None, drill_zone=None,
           rank_by=None, top_k=None) -> list:
    """Filter and rank records. Returns [{record, why}] preserving order."""
    rank_fields = {"mass": lambda r: (r.get("bounding") or {}).get("mass_kg_est") or 0,
                   "area": lambda r: max([(f.get("area_m2_est") or 0)
                                          for f in (r.get("planarity") or [])] or [0]),
                   "thickness": lambda r: min((r.get("bounding") or {}).get("obb_dims_mm") or [0]),
                   "faces": lambda r: len(r.get("planarity") or [])}
    if rank_by and rank_by not in rank_fields:
        raise UnsupportedQuery(
            f"cannot rank by '{rank_by}'. Available: {', '.join(rank_fields)}")

    results = []
    for r in records:
        why = []
        b = r.get("bounding") or {}
        dims = sorted(b.get("obb_dims_mm") or [])
        mass = b.get("mass_kg_est")

        if use:
            ids = {u["id"] for u in _uses(r)}
            if use not in ids:
                continue
            u = next(x for x in _uses(r) if x["id"] == use)
            faces = ", ".join(f"region {i+1}" for i in u.get("faces", []))
            why.append(f"use {use}" + (f" via {faces}" if faces else ""))

        if label or anomaly or min_face_area or max_face_rms or reliable_only:
            hits = _face_matches(r, label, min_face_area, max_face_rms,
                                 anomaly, reliable_only)
            if not hits:
                continue
            why.append(", ".join(f"region {i+1}" for i in hits))

        if min_mass is not None and not (mass is not None and mass >= min_mass):
            continue
        if max_mass is not None and not (mass is not None and mass <= max_mass):
            continue
        if min_thickness is not None and not (dims and dims[0] >= min_thickness):
            continue
        if max_thickness is not None and not (dims and dims[0] <= max_thickness):
            continue
        if mass is not None and (min_mass is not None or max_mass is not None):
            why.append(f"{mass:.0f} kg")

        proc = r.get("procedural") or {}
        if handling and (proc.get("handling_class") or {}).get("value") != handling:
            continue
        if drill_zone and (proc.get("drill_zone") or {}).get("value") != drill_zone:
            continue
        if connection and not any(
                ((f.get("procedural") or {}).get("connection_strategy") or {}
                 ).get("value") == connection for f in r.get("planarity") or []):
            continue
        if assignment and not any(
                ((f.get("procedural") or {}).get("design_assignment") or {}
                 ).get("value") == assignment for f in r.get("planarity") or []):
            continue

        results.append({"record": r, "why": "; ".join(why)})

    if rank_by:
        results.sort(key=lambda x: rank_fields[rank_by](x["record"]), reverse=True)
    return results[:top_k] if top_k else results


# ── CLI ──────────────────────────────────────────────────────────────────────

def _print_results(results: list, total: int) -> None:
    if not results:
        print(f"\n  No fragment matched (of {total} in the inventory).\n")
        return
    print(f"\n  {len(results)} of {total} fragments matched\n")
    for row in results:
        r = row["record"]
        b = r.get("bounding") or {}
        dims = b.get("obb_dims_mm") or []
        dim_s = " x ".join(f"{d:.0f}" for d in dims) if dims else "?"
        mass = b.get("mass_kg_est")
        print(f"  {r.get('fragment_id','?'):<18} {dim_s:>22} mm  "
              f"{(f'{mass:.0f} kg' if mass else '? kg'):>9}")
        if row["why"]:
            print(f"    {row['why']}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Query the fragment records by descriptor or intended use.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--use", help="intended design use, e.g. bench_top, seat_block, "
                                  "bar_table_stand, shelf_slab, pedestal_support")
    ap.add_argument("--label", help="surface condition on any face")
    ap.add_argument("--anomaly", help="localized anomaly on any face, e.g. opening")
    ap.add_argument("--min-face-area", type=float, metavar="M2")
    ap.add_argument("--max-face-rms", type=float, metavar="MM")
    ap.add_argument("--reliable-only", action="store_true",
                    help="ignore faces flagged as not scan-reliable")
    ap.add_argument("--min-mass", type=float, metavar="KG")
    ap.add_argument("--max-mass", type=float, metavar="KG")
    ap.add_argument("--min-thickness", type=float, metavar="MM")
    ap.add_argument("--max-thickness", type=float, metavar="MM")
    ap.add_argument("--handling", help="manual | two_person | excavator")
    ap.add_argument("--drill-zone", dest="drill_zone",
                    help="between_bars | edge_mid_depth | verify_gpr")
    ap.add_argument("--connection", help="direct_bolt | adaptive_bracket | no_drill | gravity_only")
    ap.add_argument("--assignment", help="show_face | seat_face | buried | unassigned")
    ap.add_argument("--rank", dest="rank_by", help="mass | area | thickness | faces")
    ap.add_argument("--top", dest="top_k", type=int)
    ap.add_argument("--geometry-only", action="store_true",
                    help="withhold the surface descriptors (evaluation baseline)")
    ap.add_argument("--list-uses", action="store_true",
                    help="show which uses each fragment can serve, then exit")
    ap.add_argument("--records-dir", default=str(DEFAULT_DIR))
    args = ap.parse_args()

    records = load_records(Path(args.records_dir))
    if not records:
        print(f"\n  No records in {args.records_dir}. Run the pipeline first.\n")
        sys.exit(1)
    if args.geometry_only:
        records = [strip_surface(r) for r in records]
        print("  (geometry-only: surface descriptors withheld)")

    if args.list_uses:
        print()
        for r in records:
            ids = [u["label"] for u in _uses(r)]
            print(f"  {r.get('fragment_id','?'):<18} "
                  + (", ".join(ids) if ids else "no candidate use"))
        print()
        return

    known = {u["id"] for r in records for u in _uses(r)}
    if args.use and args.use not in known:
        valid = ", ".join(sorted(known)) or "none in this inventory"
        raise UnsupportedQuery(
            f"no fragment offers the use '{args.use}'. Present in this inventory: {valid}")

    results = select(records, use=args.use, label=args.label, anomaly=args.anomaly,
                     min_face_area=args.min_face_area, max_face_rms=args.max_face_rms,
                     reliable_only=args.reliable_only,
                     min_mass=args.min_mass, max_mass=args.max_mass,
                     min_thickness=args.min_thickness, max_thickness=args.max_thickness,
                     handling=args.handling, connection=args.connection,
                     drill_zone=args.drill_zone,
                     assignment=args.assignment,
                     rank_by=args.rank_by, top_k=args.top_k)
    _print_results(results, len(records))


if __name__ == "__main__":
    try:
        main()
    except UnsupportedQuery as e:
        print(f"\n  Query not supported: {e}\n", file=sys.stderr)
        sys.exit(2)
