"""
Design factors: what a descriptor value implies for making.

Design factors are encoded statements linking a computed descriptor to its
consequence for handling, connection, and design assignment.  This module
executes them, producing the `procedural` block of the fragment record:

    handling_class        ← mass and bounding dimensions            (per fragment)
    drill_zone            ← section depth and exposed reinforcement  (per fragment)
    connection_strategy   ← planarity, area, scan reliability        (per face)
    design_assignment     ← surface label, planarity, scan reliability (per face)
    finishing_requirement ← surface label, anomalies, curvature      (per face)

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

import numpy as np

_FACTORS_PATH = Path(__file__).resolve().parents[2] / "env" / "design_factors.json"

# What `drill_zone` and `finishing_requirement` write instead of a value.
# The functions that compute them are kept and tested; re-enable by calling
# them again in `derive()` once the reinforcement reading is trustworthy.
_WITHHELD = {
    "value": None,
    "data_status": "withheld",
    "reason": ("Depends on rebar_visible. On the 2026-08-27 corpus the region "
               "pass reports it on 2 of 134 regions and on no planar face, so "
               "no face-level rule can read it, and the classifier producing "
               "it does not exceed a null baseline. Drilling and finishing "
               "guidance resting on that would be unsafe. See "
               "04_schema/CLASSIFIER_BEHAVIOUR.md §7. Withheld 2026-08-25."),
}


def load_factors(path: Path | None = None) -> dict:
    """Load the encoded design factors."""
    return json.loads((path or _FACTORS_PATH).read_text(encoding="utf-8"))


# ── individual factors ───────────────────────────────────────────────────────

def _trace(factor: str, idx: int, rule: dict, vals: dict) -> dict:
    """The uniform record every derived outcome carries.

    Until 2026-08-25 the three factors stored different things under the same
    key. `handling_class` put a rule identifier in `rule` and the triggering
    measurement in `reason`; `connection_strategy` and `design_assignment` put
    the rule's prose note in `rule` and recorded no measurement at all. So a
    reader opening a record could see why a fragment was excavator-handled and
    could not see why a face got a direct bolt.

    The paper claims each conclusion traces to the value that produced it, and
    that claim is only true if every factor records the same four things:

        value   the outcome
        rule    which rule fired, as `factor#n` against the rule table
        note    the rationale written in the configuration file
        reason  the measured values that satisfied the conditions

    `vals` supplies whatever descriptors were in scope; only the ones the rule
    actually tested are reported, so the reason names the evidence and not the
    whole record.
    """
    tested = []
    for key, fmt in (("min_area_m2",           "area {area:.3f} m2 >= {t}"),
                     ("max_fit_rms_mm",        "RMS {rms:.2f} mm <= {t}"),
                     ("min_fine_curvature_rad", "fine curvature {curv:.3f} rad >= {t}"),
                     ("max_mass_kg",           "mass {mass:.1f} kg <= {t}"),
                     ("if_scan_reliable",      "face scan_reliable = {t}"),
                     ("if_assignment",         "assignment = {t}")):
        if key in rule and rule[key] is not None:
            try:
                tested.append(fmt.format(t=rule[key], **vals))
            except (KeyError, ValueError, TypeError):
                tested.append(f"{key} = {rule[key]}")
    if "if_label" in rule and vals.get("label") is not None:
        tested.append(f"feature {vals['label']}")
    return {"rule": f"{factor}#{idx}", "note": rule.get("note", ""),
            "reason": "; ".join(tested) or "default rule, no condition tested"}


def face_features(face: dict) -> set:
    """Every feature on a face, not just the one that wins display precedence.

    `surface_label` holds a single id chosen by `_display_precedence` so that a
    viewer can pick one colour per face. Reading it in a rule makes a rendering
    preference decide a design question: on FS-002 face 6, which carries
    brick_inclusion, exposed_aggregate and broken_face, the assignment rule
    returns `show_face` when brick wins precedence and `seat_face` when
    broken_face does. Reordering precedence on 2026-08-25 flipped it, on
    identical classification.

    `finishing_requirement` was migrated to the full set on 2026-08-20;
    `design_assignment` and `use_suggestions` were not, and are migrated here.
    `surface_label` is still folded in so that records written before the
    multi-label taxonomy stay readable.
    """
    out = set(face.get("features") or [])
    if face.get("surface_label"):
        out.add(face["surface_label"])
    return out


def usable_area_m2(face: dict) -> float | None:
    """The area a rule should test: one continuous piece of surface.

    `area_m2_est` is the convex hull of a RANSAC plane's inliers. On fractured
    material those inliers are not a surface: measured over this corpus a plane
    region holds a median of 390 disconnected patches and up to 40,224, because an original cast face
    survives demolition only as pieces between the breaks. The hull spans the
    gaps between them and overstates the real surface by a median factor of 6.05
    and up to 43.7, with 39 of the 71 faces that own any surface overstated more
    than fivefold.

    Every rule that reads an area is asking whether something can sit on the
    face, be it a fixing plate, a timber deck or a person. That needs one
    continuous piece, which is `contiguous_area_m2`. It is preferred wherever
    present, with the hull kept as a fallback so records written before
    2026-08-27 still evaluate.
    """
    v = face.get("contiguous_area_m2")
    return v if v is not None else face.get("area_m2_est")


#: Every key on a face that carries something the vision model contributed.
#: The geometry-only baseline in `query.strip_surface` removes exactly these, so
#: a rule that starts reading a new surface-derived key must add it here or the
#: baseline will leak that key. Listed beside the rules that read them for that
#: reason: on 2026-08-27 the baseline was found to be withholding
#: `surface_label` while the rules had already migrated to `features`, so
#: `design_assignment` still returned `show_face` with the surface descriptors
#: supposedly withheld and the two evaluation conditions were identical.
SURFACE_FACE_KEYS = ("surface_label", "features", "anomalies")


def handling_class(mass_kg: float | None, obb_dims_mm: list | None,
                   factors: dict) -> dict:
    """Machine or manual handling, from mass with a dimension override."""
    cfg = factors["handling_class"]
    if mass_kg is None:
        return {"value": None, "rule": None, "note": "",
                "reason": "mass not available"}

    if obb_dims_mm and max(obb_dims_mm) > cfg["max_manual_dim_mm"]:
        return {"value": "excavator", "rule": "handling_class#0",
                "note": cfg.get("max_dim_note", ""),
                "reason": f"longest dimension {max(obb_dims_mm):.0f} mm exceeds "
                          f"{cfg['max_manual_dim_mm']} mm"}

    for i, rule in enumerate(cfg["rules"], 1):
        limit = rule["max_mass_kg"]
        if limit is None or mass_kg <= limit:
            out = {"value": rule["class"]}
            out.update(_trace("handling_class", i, rule, {"mass": mass_kg}))
            if limit is None:
                out["reason"] = f"estimated mass {mass_kg:.1f} kg, above every band"
            return out
    return {"value": None, "rule": None, "note": "", "reason": "no rule matched"}


def connection_strategy(face: dict, factors: dict) -> dict:
    """Feasible fixing for one planar face."""
    label   = face.get("surface_label")
    rms     = face.get("fit_rms_mm")
    area    = usable_area_m2(face)
    reliable = face.get("scan_reliable", True)

    _vals = {"rms": rms, "area": area, "label": label}
    for i, rule in enumerate(factors["connection_strategy"]["rules"], 1):
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
        out = {"value": rule["strategy"]}
        out.update(_trace("connection_strategy", i, rule, _vals))
        return out
    return {"value": None, "rule": None, "note": "", "reason": "no rule matched"}


def design_assignment(face: dict, factors: dict) -> dict:
    """Whether a face is a candidate to expose, to seat on, or to bury."""
    labels   = face_features(face)
    rms      = face.get("fit_rms_mm")
    area     = usable_area_m2(face)
    reliable = face.get("scan_reliable", True)

    _vals = {"rms": rms, "area": area,
             "label": ", ".join(sorted(labels)) if labels else None}
    for i, rule in enumerate(factors["design_assignment"]["rules"], 1):
        if "if_scan_reliable" in rule and bool(reliable) != rule["if_scan_reliable"]:
            continue
        if "if_label" in rule:
            want = rule["if_label"]
            want = want if isinstance(want, list) else [want]
            if not (labels & set(want)):
                continue
        if "max_fit_rms_mm" in rule and not (rms is not None
                                             and rms <= rule["max_fit_rms_mm"]):
            continue
        if "min_area_m2" in rule and not (area is not None
                                          and area >= rule["min_area_m2"]):
            continue
        out = {"value": rule["assignment"]}
        out.update(_trace("design_assignment", i, rule, _vals))
        return out
    return {"value": None, "rule": None, "note": "", "reason": "no rule matched"}


# ── entry point ──────────────────────────────────────────────────────────────

def finishing_requirement(face: dict, assignment: str | None,
                          curv: dict, factors: dict) -> dict:
    """What must be done to a face before it is exposed or handled.

    Safety and durability rather than geometry: exposed reinforcement cut back
    and sealed, sharp arrises eased where people reach, staining assessed for
    contamination.  Grounded in Study 1 site practice for a public installation;
    the reuse literature reviewed covers cutting, lifting and reconnection but
    does not specify surface treatment, so these entries are project-derived.
    """
    cfg = factors.get("finishing_requirement") or {}
    reliable = face.get("scan_reliable", True)
    anoms    = {a.get("label") for a in (face.get("anomalies") or [])}
    fine     = (curv.get("fine_mm") or {}).get("mean_rad")

    # Match against EVERY feature on the face, not just `surface_label`.
    #
    # Since the taxonomy went multi-label, `surface_label` is only the feature
    # that wins display precedence. A face that is a fracture surface AND
    # carries a tile remnant stores `fracture_surface` there, so a rule keyed on
    # tile_remnant would never have fired and the treatment would have been
    # silently dropped. Treatment is decided per feature, so the test has to see
    # all of them.
    labels = set(face.get("features") or [])
    if face.get("surface_label"):
        labels.add(face["surface_label"])

    for rule in cfg.get("rules", []):
        if "if_scan_reliable" in rule and bool(reliable) != rule["if_scan_reliable"]:
            continue
        if "if_label" in rule:
            want = rule["if_label"]
            want = want if isinstance(want, list) else [want]
            if not labels.intersection(want):
                continue
        # An anomaly is a feature that came back with a box, so a rule keyed on
        # one also matches a face carrying it unboxed.
        if "if_anomaly" in rule and rule["if_anomaly"] not in (anoms | labels):
            continue
        if "if_assignment" in rule and assignment != rule["if_assignment"]:
            continue
        if "min_fine_curvature_rad" in rule and not (
                fine is not None and fine >= rule["min_fine_curvature_rad"]):
            continue
        return {"value": rule["requirement"], "rule": rule["note"]}
    return {"value": None, "rule": None}


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
    regions  = ((descriptors.get("vision") or {}).get("regions") or [])

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
            a, r = usable_area_m2(face), face.get("fit_rms_mm")
            if "min_area_m2" in fr and not (a is not None and a >= fr["min_area_m2"]):
                continue
            if "max_fit_rms_mm" in fr and not (r is not None and r <= fr["max_fit_rms_mm"]):
                continue
            if "labels" in fr and not (face_features(face) & set(fr["labels"])):
                continue
            if "exclude_labels" in fr and (face_features(face)
                                           & set(fr["exclude_labels"])):
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

    def _regions_matching(fr: dict) -> list:
        """Region ids satisfying a rule that makes no demand on flatness.

        A face here is a RANSAC plane's inlier set. Measured over the twelve
        fragment corpus those sets are not surfaces: they hold a median of 390
        disconnected patches, their UV footprint scatters across the atlas, and
        77% are withheld before classification for a median fill of 0.11.
        Cluster regions are single connected patches, fill 0.41, and 75% are
        classified, but they carry no `plane_index` and so reached no rule at
        all. 49 of 65 successful classifications were discarded that way.

        A rule that specifies `max_fit_rms_mm` is asking for a flat surface,
        because something rests or bears on it, and only a plane will do. A rule
        that specifies none is asking about surface character, and a fracture
        surface answers it as well as a cast one. `rough_feature` is the clearest
        case: it asks for `broken_face` and `exposed_aggregate` and could not
        fire on a broken face.

        This does not move a feature onto a surface that lacks it. The
        classification stays on the region the model was shown, and the rule
        reads it there.
        """
        out = []
        for r in regions:
            feats = {f["id"] if isinstance(f, dict) else f
                     for f in (r.get("features") or [])}
            if not feats:
                continue
            if "labels" in fr and not (feats & set(fr["labels"])):
                continue
            if "exclude_labels" in fr and (feats & set(fr["exclude_labels"])):
                continue
            if "min_area_m2" in fr:
                a = r.get("area_m2")
                if a is None or a < fr["min_area_m2"]:
                    continue
            out.append(r.get("region_id"))
        return out

    out = []
    for rule in cfg.get("rules", []):
        if not _frag_ok(rule.get("requires_fragment") or {}):
            continue

        matched_regions = []
        if "requires_no_face" in rule:
            if _faces_matching(rule["requires_no_face"]):
                continue          # such a face exists, so the rule does not apply
            matched = []
        else:
            fr = rule.get("requires_face") or {}
            matched = _faces_matching(fr)
            # No flatness requirement means the rule is about surface character,
            # so a non-planar region can satisfy it too.
            if "max_fit_rms_mm" not in fr:
                matched_regions = _regions_matching(fr)
            if not matched and not matched_regions:
                continue

        entry = {
            "id":     rule["id"],
            "label":  rule.get("label", rule["id"]),
            "faces":  matched,
            "note":   rule.get("note", ""),
            "caveat": rule.get("caveat"),
        }
        if matched_regions:
            # Kept separate from `faces` so a reader can always tell whether the
            # evidence sits on a planar face or on a fracture surface.
            entry["regions"] = matched_regions
        out.append(entry)
    return out


def _edge_faces(faces: list, bounding: dict, tol_deg: float) -> list:
    """Faces that cut across the section, and so open onto the steel-free core.

    The mat lies parallel to the two broad faces, meaning perpendicular to the
    box's thinnest axis.  A face whose normal is perpendicular to that axis is
    a broken or sawn edge, and a hole entering it at mid-thickness runs between
    the two layers.  Returns face indices, or an empty list if the record
    predates the stored box axes.
    """
    axes = bounding.get("obb_axes_xyz")
    dims = bounding.get("obb_dims_mm")
    if not axes or not dims or len(axes) != len(dims):
        return []
    thin = np.asarray(axes[int(np.argmin(dims))], dtype=float)
    limit = np.cos(np.radians(90.0 - tol_deg))
    out = []
    for i, f in enumerate(faces):
        n = f.get("normal_xyz")
        if not n:
            continue
        n = np.asarray(n, dtype=float)
        nn = np.linalg.norm(n)
        if nn == 0:
            continue
        if abs(float(thin @ (n / nn))) <= limit:
            out.append(i)
    return out


def drill_zone(faces: list, bounding: dict, factors: dict) -> dict:
    """Where a fixing can be drilled, given what the scan reveals of the mat.

    Reinforcement is laid as a grid at roughly constant cover and spacing, so a
    slab section is mostly steel-free.  Exposed reinforcement is therefore
    information rather than a prohibition: a fracture face that cuts the mat
    shows its spacing, direction and cover, and those can be projected across
    the fragment to set holes out between the bars.  Where nothing is exposed,
    the fallback is the steel-free core between the two mats, reachable only by
    entering a broken edge at mid-thickness.
    """
    cfg = factors.get("drill_zone") or {}
    if not cfg.get("rules"):
        return {"value": None, "rule": None}

    labels = {f.get("surface_label") for f in faces}
    labels |= {a.get("label") for f in faces for a in (f.get("anomalies") or [])}

    dims  = sorted(bounding.get("obb_dims_mm") or [])
    thick = dims[0] if dims else None
    cover = cfg.get("cover_mm_assumed", 20)
    dia   = cfg.get("bar_dia_mm_assumed", 12)
    core  = (thick - 2 * (cover + dia)) if thick is not None else None

    for rule in cfg["rules"]:
        if "if_any_face_label" in rule and rule["if_any_face_label"] not in labels:
            continue
        if "min_clear_core_mm" in rule and not (
                core is not None and core >= rule["min_clear_core_mm"]):
            continue
        out = {"value": rule["zone"], "rule": rule["note"],
               "clear_core_mm_est": round(core, 1) if core is not None else None,
               "cover_mm_assumed": cover}
        if rule["zone"] == "edge_mid_depth":
            out["entry_faces"] = _edge_faces(faces, bounding,
                                             cfg.get("edge_normal_tol_deg", 35))
        return out
    return {"value": None, "rule": None}


def derive(descriptors: dict, factors: dict | None = None) -> dict:
    """Run all design factors over one fragment record, in place.

    Adds `descriptors["procedural"]` (fragment level) and a `procedural` block
    on each entry of `descriptors["planarity"]` (face level).  Returns the
    procedural block for convenience.
    """
    factors = factors or load_factors()
    bounding = descriptors.get("bounding", {}) or {}

    # Both factors below read exposed reinforcement, and neither may be
    # published while that reading is untrustworthy.
    #
    # The region pass has never reported `rebar_visible` on any fragment, so
    # `drill_zone` was deriving "no bars visible, but the section is deep
    # enough for a steel-free core" from a negative nothing has tested. Since
    # 2026-08-25 the whole-atlas pass reports `rebar_visible` on 4 of 11
    # fragments, so one record can now assert reinforcement at fragment level
    # and deny it at face level.
    #
    # Until 2026-08-25 this was handled by writing "withheld" in the paper
    # while the pipeline kept computing and storing both values in full. The
    # withholding now happens here, where the record is built, so the artefact
    # and the claim agree. The keys stay, carrying a null value and the reason,
    # because a reader needs to see that the field exists and why it is empty.

    handling = handling_class(bounding.get("mass_kg_est"),
                              bounding.get("obb_dims_mm"), factors)

    faces = descriptors.get("planarity", []) or []
    curv  = descriptors.get("curvature", {}) or {}
    for face in faces:
        assignment = design_assignment(face, factors)
        face["procedural"] = {
            "connection_strategy":   connection_strategy(face, factors),
            "design_assignment":     assignment,
            "finishing_requirement": _WITHHELD,
            "data_status": "proposed",
        }

    uses = use_suggestions(descriptors, factors)

    block = {
        "handling_class": handling,
        "drill_zone": _WITHHELD,
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
