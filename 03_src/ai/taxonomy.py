"""
Shared taxonomy loader — single source of truth for feature labels.

Edit env/taxonomy.json to add, remove, or rename labels without touching
any Python code. Both vision_client.py and report.py import from here.

WARNING: Do not change label IDs between pipeline runs. Adding a new label
at the end is safe. Renaming requires reprocessing all existing fragments.
"""

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TAXONOMY_JSON = _REPO_ROOT / "env" / "taxonomy.json"

# Built-in defaults — used when taxonomy.json is missing
_DEFAULTS: list[dict] = [
    {"id": "formwork_face",     "color": "#60a5fa", "description": "Cast against formwork; mould evidence visible"},
    {"id": "broken_face",       "color": "#f87171", "description": "A break through the body of the concrete"},
    {"id": "exposed_aggregate", "color": "#fbbf24", "description": "Coarse aggregate a dominant part of the surface"},
    {"id": "rebar_visible",     "color": "#f97316", "description": "Steel reinforcement exposed"},
    {"id": "discolouration",    "color": "#c084fc", "description": "Rust, oil, paint or soot colouring"},
]


def _raw_taxonomy() -> dict:
    """The whole taxonomy file, including the fields that are not per-label."""
    if _TAXONOMY_JSON.exists():
        with open(_TAXONOMY_JSON, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_taxonomy() -> list[dict]:
    """
    Load taxonomy from env/taxonomy.json.
    Falls back to built-in defaults if the file is missing.

    Returns list of dicts: [{"id": str, "color": str, "description": str}, ...]
    """
    if _TAXONOMY_JSON.exists():
        with open(_TAXONOMY_JSON, encoding="utf-8") as f:
            data = json.load(f)
        # `features` since 2026-08-20, when the three competing axes collapsed
        # into one multi-label vocabulary. `labels` is still read so an older
        # taxonomy file, or a checkout from before that date, still loads.
        labels = data.get("features") or data.get("labels") or _DEFAULTS
        if not labels:
            print("  ⚠ taxonomy.json has no features — using defaults")
            return _DEFAULTS
        return labels
    return _DEFAULTS


# Module-level constants — computed once at import
_taxonomy_data: list[dict] = load_taxonomy()

TAXONOMY: list[str] = [t["id"] for t in _taxonomy_data]
LABEL_COLORS: dict[str, str] = {t["id"]: t["color"] for t in _taxonomy_data}
LABEL_DESCRIPTIONS: dict[str, str] = {t["id"]: t["description"] for t in _taxonomy_data}
LABEL_SUBTYPES: dict[str, list[str]] = {
    t["id"]: t.get("subtypes", ["unknown"]) for t in _taxonomy_data
}
LABEL_RULES: dict[str, str] = {
    t["id"]: t.get("decision_rule", "") for t in _taxonomy_data
}

# A feature can be retired but not deleted.  Its position in `features` is its
# integer feature_id, stored in every viewer JSON, so removing it renumbers
# everything after it and silently recolours output already written.  Retiring
# keeps the id, and therefore the stored data, while taking the feature out of
# both the prompt and the interface.
RETIRED: set = {t["id"] for t in _taxonomy_data if t.get("retired")}

# What the interface should offer. TAXONOMY keeps every id, retired included,
# because feature_id indexes into it.
ACTIVE: list[str] = [t for t in TAXONOMY if t not in RETIRED]

# ── One axis, multi-label ────────────────────────────────────────────────────
#
# Until 2026-08-20 there were three axes and the surface axis was competitive:
# the model worked down a precedence list and took the first match. That
# arbitrated between claims that are not alternatives. A fracture surface
# almost always exposes aggregate; a face can carry a crack and a tile remnant
# at once. Measured on FS-004, all four legible regions returned
# `fracture_surface` 3/3 and the aggregate dominating them went unrecorded,
# because `exposed_aggregate` sat two places lower and its own rule told the
# model to stand down.
#
# Nothing competes now. `_display_precedence` still exists but it is a
# RENDERING choice: the viewer and the combined feature map can only draw one
# colour per face, so it decides what goes on top. It is not a claim about what
# the surface is.
GROUPS: dict[str, str] = {t["id"]: t.get("group", "manufacture")
                          for t in _taxonomy_data}
LOCALIZED: set = {t["id"] for t in _taxonomy_data if t.get("localized")}


def features_by_group() -> dict:
    """Active features grouped for the prompt and the report legend."""
    out: dict = {}
    for fid in ACTIVE:
        out.setdefault(GROUPS.get(fid, "manufacture"), []).append(fid)
    return out


def _display_precedence() -> list[str]:
    """Rendering order only. Anything active but unlisted is appended."""
    stated = _raw_taxonomy().get("_display_precedence", [])
    order = [f for f in stated if f in TAXONOMY and f not in RETIRED]
    missing = [f for f in ACTIVE if f not in order]
    if missing and order:
        print(f"  ⚠ taxonomy.json: {', '.join(missing)} missing from "
              "_display_precedence; appended last. Affects only which colour "
              "is drawn on top, not the labels themselves.")
    return order + missing or list(ACTIVE)


DISPLAY_PRECEDENCE: list[str] = _display_precedence()

# Six aliases were kept here for callers written against the old three-axis
# loader: DECISION_ORDER, ANOMALY_LABELS, ANOMALY_HINTS, ANOMALIES_RETIRED,
# EXPOSURE_LABELS and EXPOSURE_HINTS. Removed 2026-08-25. Nothing outside this
# module referenced any of them, and two were permanently empty, so they
# described a schema the pipeline had already left behind. `LOCALIZED` stays:
# `region_classification` reads it for the localisation gates, which are built
# and switched off rather than deleted.
