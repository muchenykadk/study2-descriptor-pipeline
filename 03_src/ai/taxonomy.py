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
    {"id": "formwork_imprint",  "color": "#60a5fa", "description": "Original cast face; smooth, shows mould texture or release agent"},
    {"id": "fracture_surface",  "color": "#f87171", "description": "Internal concrete exposed by demolition break; rough"},
    {"id": "exposed_aggregate", "color": "#fbbf24", "description": "Coarse aggregate (gravel/stone) visible at surface"},
    {"id": "rebar_visible",     "color": "#f97316", "description": "Steel reinforcement bar exposed"},
    {"id": "weathered",         "color": "#a3e635", "description": "Carbonated, eroded, or surface-degraded concrete"},
    {"id": "staining",          "color": "#c084fc", "description": "Rust, moss, oil, paint, or other contamination"},
    {"id": "original_finish",   "color": "#34d399", "description": "Intentional architectural finish (tile, plaster, render)"},
]


def load_taxonomy() -> list[dict]:
    """
    Load taxonomy from env/taxonomy.json.
    Falls back to built-in defaults if the file is missing.

    Returns list of dicts: [{"id": str, "color": str, "description": str}, ...]
    """
    if _TAXONOMY_JSON.exists():
        with open(_TAXONOMY_JSON, encoding="utf-8") as f:
            data = json.load(f)
        labels = data.get("labels", _DEFAULTS)
        if not labels:
            print(f"  ⚠ taxonomy.json has no labels — using defaults")
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
