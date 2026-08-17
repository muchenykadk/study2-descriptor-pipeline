"""
Design factors: what a descriptor value implies for making.

Design factors are encoded statements linking a computed descriptor to its
consequence for handling, connection, and design assignment.  This module
executes them, producing the `procedural` block of the fragment record:

    handling_class      ← mass and bounding dimensions      (per fragment)
    connection_strategy ← planarity, surface label, scan reliability (per face)
    design_assignment   ← surface label, planarity, scan reliability (per face)

The factors themselves live in `env/design_factors.json` so they can be revised
without touching code, in the same way as the surface taxonomy.

IMPORTANT — status of the output.  The factors are provisional: they were drawn
from Study 1 site experience and general practice, and have not been verified
with domain experts.  Every value produced here carries
`data_status: "proposed"`, and each records the rule that produced it so the
reasoning is inspectable.  Agreement with Study 1 decisions is expected, because
the thresholds were informed by that project, and is therefore not validation.
"""

import json
from pathlib import Path

_FACTORS_PATH = Path(__file__).resolve().parents[2] / "env" / "design_factors.json"


def load_factors(path: Path | None = None) -> dict:
    """Load the encoded design factors."""
    return json.loads((path or _FACTORS_PATH).read_text(encoding="utf-8"))


# ── individual factors ───────────────────────────────────────────────────────

def handling_class(mass_kg: float | None, obb_dims_mm: list | None,
                   factors: dict) -> dict:
    """Machine or manual handling, from mass with a dimension override."""
    cfg = factors["handling_class"]
    if mass_kg is None:
        return {"value": None, "rule": None, "reason": "mass not available"}

    if obb_dims_mm and max(obb_dims_mm) > cfg["max_manual_dim_mm"]:
        return {"value": "excavator", "rule": "max_dim",
                "reason": f"longest dimension {max(obb_dims_mm):.0f} mm exceeds "
                          f"{cfg['max_manual_dim_mm']} mm"}

    for rule in cfg["rules"]:
        limit = rule["max_mass_kg"]
        if limit is None or mass_kg <= limit:
            return {"value": rule["class"], "rule": rule["note"],
                    "reason": f"estimated mass {mass_kg:.1f} kg"}
    return {"value": None, "rule": None, "reason": "no rule matched"}


def connection_strategy(face: dict, factors: dict) -> dict:
    """Feasible fixing for one planar face."""
    label   = face.get("surface_label")
    rms     = face.get("fit_rms_mm")
    area    = face.get("area_m2_est")
    reliable = face.get("scan_reliable", True)

    for rule in factors["connection_strategy"]["rules"]:
        if "if_label" in rule and label != rule["if_label"]:
            continue
        if "if_scan_reliable" in rule and bool(reliable) != rule["if_scan_reliable"]:
            continue
        if "max_fit_rms_mm" in rule and not (rms is not None
                                             and rms <= rule["max_fit_rms_mm"]):
            continue
        if "min_area_m2" in rule and not (area is not None
                                          and area >= rule["min_area_m2"]):
            continue
        return {"value": rule["strategy"], "rule": rule["note"]}
    return {"value": None, "rule": None}


def design_assignment(face: dict, factors: dict) -> dict:
    """Whether a face is a candidate to expose, to seat on, or to bury."""
    label    = face.get("surface_label")
    rms      = face.get("fit_rms_mm")
    area     = face.get("area_m2_est")
    reliable = face.get("scan_reliable", True)

    for rule in factors["design_assignment"]["rules"]:
        if "if_scan_reliable" in rule and bool(reliable) != rule["if_scan_reliable"]:
            continue
        if "if_label" in rule:
            want = rule["if_label"]
            want = want if isinstance(want, list) else [want]
            if label not in want:
                continue
        if "max_fit_rms_mm" in rule and not (rms is not None
                                             and rms <= rule["max_fit_rms_mm"]):
            continue
        if "min_area_m2" in rule and not (area is not None
                                          and area >= rule["min_area_m2"]):
            continue
        return {"value": rule["assignment"], "rule": rule["note"]}
    return {"value": None, "rule": None}


# ── entry point ──────────────────────────────────────────────────────────────

def derive(descriptors: dict, factors: dict | None = None) -> dict:
    """Run all design factors over one fragment record, in place.

    Adds `descriptors["procedural"]` (fragment level) and a `procedural` block
    on each entry of `descriptors["planarity"]` (face level).  Returns the
    procedural block for convenience.
    """
    factors = factors or load_factors()
    bounding = descriptors.get("bounding", {}) or {}

    handling = handling_class(bounding.get("mass_kg_est"),
                              bounding.get("obb_dims_mm"), factors)

    faces = descriptors.get("planarity", []) or []
    for face in faces:
        face["procedural"] = {
            "connection_strategy": connection_strategy(face, factors),
            "design_assignment":   design_assignment(face, factors),
            "data_status": "proposed",
        }

    block = {
        "handling_class": handling,
        "faces_evaluated": len(faces),
        "data_status": "proposed",
        "basis": factors.get("_status"),
        "note": ("Derived from the encoded design factors in "
                 "env/design_factors.json. Provisional: the factors are drawn "
                 "from Study 1 experience and general practice and are not "
                 "expert-verified."),
    }
    descriptors["procedural"] = block
    return block
