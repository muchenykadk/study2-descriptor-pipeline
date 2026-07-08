"""Cloud vision API client for texture classification / semantic annotation.

Fixed taxonomy prompt, structured JSON output, response caching by image hash
(05_output/ai_cache/). Fix model version + temperature for reproducibility;
run 3x, take majority label (Phase 3).
"""

import hashlib
import json
import os
from pathlib import Path

TAXONOMY = [
    "formwork_imprint", "fracture_surface", "weathered",
    "exposed_aggregate", "rebar_visible", "staining", "original_finish",
]

CACHE_DIR = Path(__file__).resolve().parents[2] / "05_output" / "ai_cache"


def classify_view(image_path: str) -> dict:
    """Classify one rendered view. TODO: implement API call + cache (Phase 3)."""
    raise NotImplementedError
