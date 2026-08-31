"""
scan_coverage.py — Study 2 Descriptor Pipeline
===============================================
Post-processing annotator for unscanned face flagging.

Run AFTER run_pipeline.py has completed for the fragment.
Does NOT modify run_pipeline.py, geometry.py, or any existing script.

Usage
-----
    python 03_src/scan_coverage.py FRAG-S1-FS-001

What it does
------------
1. Reads  01_input/meshes/processed/{FRAG_ID}/{FRAG_ID}_scan_coverage.json
   (written by bake_texture_v2.py from the UNSCANNED vertex group on the
   original photogrammetry mesh, before voxel remesh destroys topology)

2. Reads  05_output/descriptors/{FRAG_ID}_geometry.json
   (written by run_pipeline.py)

3. Compares the unscanned face average normal against each RANSAC plane normal.
   Planes whose normal is within ANGLE_THRESHOLD_DEG of the unscanned normal
   are flagged:  scan_reliable: false

4. Adds a top-level "scan_coverage" block to the geometry JSON documenting
   the unscanned region.

5. Re-saves the geometry JSON in-place with these additions.

Why a separate script
---------------------
The voxel remesh in bake_texture.py creates entirely new topology — face-level
information from the original mesh cannot be carried forward. bake_texture_v2.py
captures the unscanned normal before remesh and writes a sidecar. This script
applies that sidecar to annotate the pipeline output without touching any
existing pipeline code.

If no sidecar exists (fragment processed with original bake_texture.py, or no
UNSCANNED vertex group was assigned), the script prints a warning and exits
without modifying anything.

Output additions to _geometry.json
------------------------------------
Each entry in "planarity" gains two new fields:
    scan_reliable: bool         — false if plane matches unscanned normal
    angle_to_unscanned_deg: float

Top-level "scan_coverage" block is added:
    has_unscanned_face: bool
    unscanned_avg_normal: [x, y, z]
    unscanned_avg_center: [x, y, z]
    unscanned_face_count_original: int
    angle_threshold_deg: float
    data_status: "annotated"
"""

import json
import sys
import numpy as np
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]

# Planes whose normal falls within this angle of the unscanned normal are flagged.
# 25° is a reasonable default — the unscanned face is relatively flat and the
# RANSAC plane normal should align closely. Increase if fragments rest at an angle.
ANGLE_THRESHOLD_DEG: float = 25.0


# ── Helpers ────────────────────────────────────────────────────────────────────

def read_sidecar(frag_id: str, processed_dir: Path) -> dict | None:
    """Read _scan_coverage.json sidecar written by bake_texture_v2.py."""
    path = processed_dir / frag_id / f"{frag_id}_scan_coverage.json"
    if not path.exists():
        print(f"  ⚠  No scan coverage sidecar found.")
        print(f"     Expected: {path}")
        print(f"     Use bake_texture_v2.py with an 'UNSCANNED' vertex group assigned")
        print(f"     to the manually-closed ground-contact faces before running the script.")
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    n = data.get("avg_normal", [])
    print(f"  ✓  Sidecar loaded: {path.name}")
    print(f"     Unscanned face count : {data.get('face_count', '?')} (on original mesh)")
    print(f"     Avg normal           : [{', '.join(f'{x:.3f}' for x in n)}]")
    return data


def flag_unscanned_planes(
    planes: list[dict],
    meta: dict,
    threshold_deg: float = ANGLE_THRESHOLD_DEG,
) -> list[dict]:
    """
    For each RANSAC plane, compute the angle between its normal and the
    unscanned face normal. Flag the plane scan_reliable=False if within threshold.

    Uses the absolute dot product so that anti-parallel normals (same plane,
    opposite facing) are treated as equivalent.

    Returns a new list — originals are not mutated.
    """
    u_normal = np.array(meta["avg_normal"], dtype=float)
    u_normal /= np.linalg.norm(u_normal)
    threshold_cos = np.cos(np.radians(threshold_deg))

    flagged = []
    for plane in planes:
        p = dict(plane)
        p_normal = np.array(p["normal_xyz"], dtype=float)
        p_normal /= (np.linalg.norm(p_normal) or 1.0)

        cos_angle = float(abs(np.dot(p_normal, u_normal)))
        cos_angle = float(np.clip(cos_angle, 0.0, 1.0))
        angle_deg = float(np.degrees(np.arccos(cos_angle)))

        p["angle_to_unscanned_deg"] = round(angle_deg, 1)
        p["scan_reliable"] = bool(cos_angle < threshold_cos)
        flagged.append(p)

    return flagged


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python 03_src/scan_coverage.py FRAG-S1-FS-001")
        sys.exit(1)

    frag_id       = sys.argv[1]
    processed_dir = REPO_ROOT / "01_input" / "meshes" / "processed"
    output_dir    = REPO_ROOT / "05_output" / "descriptors"
    geom_path     = output_dir / f"{frag_id}_geometry.json"

    print(f"\n{'='*56}")
    print(f"  scan_coverage.py  —  {frag_id}")
    print(f"{'='*56}\n")

    # ── 1: Load sidecar ───────────────────────────────────────────────────────
    meta = read_sidecar(frag_id, processed_dir)
    if meta is None:
        sys.exit(0)   # nothing to annotate — exit cleanly

    # ── 2: Load geometry JSON ─────────────────────────────────────────────────
    if not geom_path.exists():
        print(f"  ERROR: geometry JSON not found.")
        print(f"  Expected: {geom_path}")
        print(f"  Run run_pipeline.py first, then re-run this script.")
        sys.exit(1)

    with open(geom_path, encoding="utf-8") as f:
        geom = json.load(f)
    print(f"  ✓  Geometry JSON loaded: {geom_path.name}")

    # Warn if already annotated
    if "scan_coverage" in geom:
        print(f"  ⚠  scan_coverage block already present — overwriting")

    # ── 3: Flag RANSAC planes ─────────────────────────────────────────────────
    planes = geom.get("planarity", [])
    if planes:
        flagged = flag_unscanned_planes(planes, meta, ANGLE_THRESHOLD_DEG)
        geom["planarity"] = flagged

        n_unreliable = sum(1 for p in flagged if not p.get("scan_reliable", True))
        print(f"\n  Planarity regions: {len(flagged)} total, "
              f"{n_unreliable} flagged as unscanned  "
              f"(threshold {ANGLE_THRESHOLD_DEG}°)")

        for i, p in enumerate(flagged):
            status = "UNSCANNED ⚠" if not p.get("scan_reliable", True) else "reliable  ✓"
            area   = f"{p['area_m2_est']:.4f} m²" if p.get("area_m2_est") else "area unknown"
            print(f"    Region {i+1}: {status}  "
                  f"angle {p['angle_to_unscanned_deg']}°  {area}")
    else:
        print(f"  ⚠  No planarity regions in geometry JSON — nothing to flag")

    # ── 4: Add scan_coverage block ────────────────────────────────────────────
    geom["scan_coverage"] = {
        "has_unscanned_face":            meta.get("has_unscanned_face", True),
        "unscanned_avg_normal":          meta["avg_normal"],
        "unscanned_avg_center":          meta.get("avg_center"),
        "unscanned_face_count_original": meta.get("face_count"),
        "angle_threshold_deg":           ANGLE_THRESHOLD_DEG,
        "notes": (
            "Ground-contact face not captured during photogrammetry scanning. "
            "Descriptor values derived from reliable faces only. "
            "Planarity regions within angle_threshold_deg of unscanned normal "
            "are flagged scan_reliable: false and excluded from connection "
            "feasibility assessment."
        ),
        "data_status": "annotated",
    }

    # ── 5: Re-save geometry JSON ──────────────────────────────────────────────
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(geom, f, indent=2)

    print(f"\n  ✓  Geometry JSON updated → {geom_path.relative_to(REPO_ROOT)}")
    print(f"\n{'='*56}")
    print(f"  Done.")
    print(f"  Note: run_pipeline.py now applies scan coverage automatically.")
    print(f"  This script is only needed to manually re-annotate an existing JSON.")
    print(f"{'='*56}\n")


if __name__ == "__main__":
    main()
