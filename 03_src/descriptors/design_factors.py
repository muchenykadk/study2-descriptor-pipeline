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

def use_suggestions(descriptors: dict, factors: dict) -> list:
    """Combine face and fragment conditions into candidate uses.

    Unlike the per-face factors, a use suggestion needs several conditions to
    hold at once, some on a face (area, flatness, surface character) and some
    on the whole fragment (thickness, mass, convexity, proportion, curvature).
    A suggestion is offered when the fragment satisfies `requires_fragment` and
    at least one face satisfies `requires_face`; the qualifying faces are named
    so the reasoning can be checked against the geometry.

    A rule may instead declare `requires_no_face`, which fires when *no* face
    meets the given conditions.  That is how the cut candidate is expressed:
    the fragment is substantial but offers no usable flat face, so one would
    have to be created by sawing.
    """
    cfg = factors.get("use_suggestions") or {}
    bounding = descriptors.get("bounding", {}) or {}
    faces    = descriptors.get("planarity", []) or []
    curv     = descriptors.get("curvature", {}) or {}

    dims      = sorted(bounding.get("obb_dims_mm") or [])
    thickness = dims[0] if dims else None
    longest   = dims[-1] if dims else None
    aspect    = (longest / thickness) if (thickness and thickness > 0) else None
    mass      = bounding.get("mass_kg_est")
    convexity = bounding.get("convexity")
    fine_curv = (curv.get("fine_mm") or {}).get("mean_rad")

    def _frag_ok(req: dict) -> bool:
        checks = [
            ("min_thickness_mm", thickness, lambda v, t: v is not None and v >= t),
            ("max_thickness_mm", thickness, lambda v, t: v is not None and v <= t),
            ("min_mass_kg",      mass,      lambda v, t: v is not None and v >= t),
            ("max_mass_kg",      mass,      lambda v, t: v is not None and v <= t),
            ("min_convexity",    convexity, lambda v, t: v is not None and v >= t),
            ("max_convexity",    convexity, lambda v, t: v is not None and v <= t),
            ("min_aspect_ratio", aspect,    lambda v, t: v is not None and v >= t),
            ("min_fine_curvature_rad", fine_curv, lambda v, t: v is not None and v >= t),
            ("max_fine_curvature_rad", fine_curv, lambda v, t: v is not None and v <= t),
        ]
        # Height band: a fragment can be laid to present any of its three
        # bounding dimensions as height, so the band matches if any dimension
        # falls inside it. Which orientation is actually stable is not computed.
        if "height_band_mm" in req:
            lo, hi = req["height_band_mm"]
            if not any(lo <= d <= hi for d in dims):
                return False
        for key, value, test in checks:
            if key in req and not test(value, req[key]):
                return False
        return True

    def _faces_matching(fr: dict) -> list:
        out = []
        for i, face in enumerate(faces):
            a, r = face.get("area_m2_est"), face.get("fit_rms_mm")
            if "min_area_m2" in fr and not (a is not None and a >= fr["min_area_m2"]):
                continue
            if "max_fit_rms_mm" in fr and not (r is not None and r <= fr["max_fit_rms_mm"]):
                continue
            if "labels" in fr and face.get("surface_label") not in fr["labels"]:
                continue
            if "exclude_labels" in fr and face.get("surface_label") in fr["exclude_labels"]:
                continue
            if "requires_anomaly" in fr:
                want = fr["requires_anomaly"]
                want = want if isinstance(want, list) else [want]
                found = {a.get("label") for a in (face.get("anomalies") or [])}
                if not (found & set(want)):
                    continue
            if ("scan_reliable" in fr
                    and bool(face.get("scan_reliable", True)) != fr["scan_reliable"]):
                continue
            out.append(i)
        return out

    out = []
    for rule in cfg.get("rules", []):
        if not _frag_ok(rule.get("requires_fragment") or {}):
            continue

        if "requires_no_face" in rule:
            if _faces_matching(rule["requires_no_face"]):
                continue          # such a face exists, so the rule does not apply
            matched = []
        else:
            matched = _faces_matching(rule.get("requires_face") or {})
            if not matched:
                continue

        out.append({
            "id":     rule["id"],
            "label":  rule.get("label", rule["id"]),
            "faces":  matched,
            "note":   rule.get("note", ""),
            "caveat": rule.get("caveat"),
        })
    return out


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

    uses = use_suggestions(descriptors, factors)

    block = {
        "handling_class": handling,
        "use_suggestions": uses,
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
