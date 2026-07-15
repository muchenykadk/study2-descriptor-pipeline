"""
Phase 3 — Vision model feature extraction.

Sends the fragment texture map to a vision API and returns structured surface
descriptors using a fixed taxonomy. Results are cached by image MD5 so the
same image never hits the API twice. Runs 3× and takes majority label for
reproducibility (GPT-4o and Claude are non-deterministic even at temperature=0).

Supported providers (set in env/.env):
    openai    → gpt-4o, gpt-4o-mini
    anthropic → claude-sonnet-4-6, claude-opus-4-8
    gemini    → gemini-2.5-pro
    ollama    → any local multimodal model (llava, pixtral, qwen-vl)

Usage (called automatically by run_pipeline.py --phase3):
    from ai.vision_client import classify_texture
    result = classify_texture(texture_path)
"""

import base64
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from .taxonomy import TAXONOMY, LABEL_SUBTYPES  # noqa: F401 — re-exported for importers

CACHE_DIR = Path(__file__).resolve().parents[2] / "05_output" / "ai_cache"

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a materials scientist specialising in demolition concrete characterisation
for architectural upcycling research. You analyse texture images of concrete
fragment surfaces and return structured descriptors in JSON format only.\
"""

def _build_taxonomy_block() -> str:
    """Build the taxonomy section of the prompt, including subtype options per label."""
    lines = []
    for label in TAXONOMY:
        subtypes = LABEL_SUBTYPES.get(label, ["unknown"])
        lines.append(f"  - {label}  [{' | '.join(subtypes)}]")
    return "\n".join(lines)


_USER_TEMPLATE = """\
The attached image is a UV texture map of a demolition concrete fragment.
It may show multiple surface patches arranged across the image area.

Analyse every visible surface patch and return a JSON object with EXACTLY
this structure — no extra keys, no markdown, no explanation:

{{
  "dominant_label": "<one label from the taxonomy>",
  "labels_present": ["<label>", ...],
  "label_coverage": {{
    "<label>": <0-100 integer percent of visible surface>
  }},
  "label_details": {{
    "<label_from_labels_present>": {{
      "subtype": "<one value from that label's subtype list>",
      "notes": "<one concise sentence: specific material, colour, condition, approximate size if visible>"
    }}
  }},
  "cracks": {{
    "present": <true|false>,
    "pattern": "<none | linear | branching | network>",
    "coverage_pct": <0-100>
  }},
  "aggregate": {{
    "visible": <true|false>,
    "estimated_size": "<fine | medium | coarse | unknown>"
  }},
  "surface_condition": "<good | moderate | poor>",
  "color_notes": "<brief description of dominant colours, staining, carbonation>",
  "reuse_notes": "<1-2 sentences on implications for cascading reuse>",
  "confidence": "<high | medium | low>"
}}

Rules:
- label_details must contain an entry for every label in labels_present.
- subtype must be chosen from the options listed for that label below.
- If the subtype cannot be determined from the image, use "unknown".

Taxonomy with subtype options (use ONLY these labels and subtypes):
{taxonomy}
""".format(taxonomy=_build_taxonomy_block())


# ── Image encoding ────────────────────────────────────────────────────────────

def _encode_image(image_path: Path) -> tuple[str, str]:
    """Return (base64_string, media_type)."""
    ext = image_path.suffix.lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), media_type


def _image_hash(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path(image_path: Path, provider: str, model: str, run: int) -> Path:
    h = _image_hash(image_path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{h}_{provider}_{model.replace('/', '-')}_run{run}.json"


def _load_cache(cache_path: Path) -> dict | None:
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(cache_path: Path, result: dict) -> None:
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


# ── Provider calls ────────────────────────────────────────────────────────────

def _call_openai(b64: str, media_type: str, model: str) -> dict:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=1000,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_TEMPLATE},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{media_type};base64,{b64}",
                        "detail": "high",
                    }},
                ],
            },
        ],
    )
    return response.choices[0].message.content.strip()


def _call_anthropic(b64: str, media_type: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": b64,
                }},
                {"type": "text", "text": _USER_TEMPLATE},
            ],
        }],
    )
    return response.content[0].text.strip()


def _call_gemini(b64: str, media_type: str, model: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    import PIL.Image, io, base64 as _b64
    img = PIL.Image.open(io.BytesIO(_b64.b64decode(b64)))
    m = genai.GenerativeModel(model, system_instruction=_SYSTEM)
    response = m.generate_content([_USER_TEMPLATE, img])
    return response.text.strip()


def _call_ollama(b64: str, media_type: str, model: str) -> str:
    import requests
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    payload = {
        "model": model,
        "prompt": f"{_SYSTEM}\n\n{_USER_TEMPLATE}",
        "images": [b64],
        "stream": False,
    }
    r = requests.post(f"{base_url}/api/generate", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["response"].strip()


_PROVIDERS = {
    "openai":    _call_openai,
    "anthropic": _call_anthropic,
    "gemini":    _call_gemini,
    "ollama":    _call_ollama,
}


# ── JSON parsing ──────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """Extract JSON from raw model output, tolerating markdown fences."""
    text = raw
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": raw, "parse_error": True}


# ── Majority vote across runs ─────────────────────────────────────────────────

def _majority_label(results: list[dict]) -> str:
    """Return the dominant_label that appears most across N runs."""
    labels = [r.get("dominant_label", "unknown") for r in results
              if not r.get("parse_error")]
    if not labels:
        return "unknown"
    return Counter(labels).most_common(1)[0][0]


def _merge_runs(results: list[dict]) -> dict:
    """
    Merge N independent run results into one consensus dict.
    Numeric fields are averaged; dominant_label and subtypes use majority vote.
    """
    valid = [r for r in results if not r.get("parse_error")]
    if not valid:
        return results[0] if results else {"parse_error": True}

    merged = dict(valid[0])  # start with first run as base

    # Majority vote on dominant label
    merged["dominant_label"] = _majority_label(valid)

    # Union of all labels present
    all_labels = set()
    for r in valid:
        all_labels.update(r.get("labels_present", []))
    merged["labels_present"] = sorted(all_labels)

    # Average coverage values
    coverage_sum: dict[str, list[int]] = {}
    for r in valid:
        for label, pct in r.get("label_coverage", {}).items():
            coverage_sum.setdefault(label, []).append(pct)
    merged["label_coverage"] = {
        k: round(sum(v) / len(v)) for k, v in coverage_sum.items()
    }

    # Average crack coverage
    crack_pcts = [r.get("cracks", {}).get("coverage_pct", 0) for r in valid]
    if "cracks" in merged:
        merged["cracks"]["coverage_pct"] = round(sum(crack_pcts) / len(crack_pcts))

    # Merge label_details: majority vote on subtype, first-run notes
    merged_details: dict[str, dict] = {}
    for label in merged["labels_present"]:
        subtype_votes = []
        first_notes = ""
        for r in valid:
            detail = r.get("label_details", {}).get(label, {})
            st = detail.get("subtype", "unknown")
            if st:
                subtype_votes.append(st)
            if not first_notes:
                first_notes = detail.get("notes", "")
        majority_subtype = (
            Counter(subtype_votes).most_common(1)[0][0]
            if subtype_votes else "unknown"
        )
        merged_details[label] = {
            "subtype": majority_subtype,
            "notes":   first_notes,
        }
    merged["label_details"] = merged_details

    merged["n_runs"]  = len(valid)
    merged["n_total"] = len(results)
    return merged


# ── Public API ────────────────────────────────────────────────────────────────

def classify_texture(image_path: Path, n_votes: int = 3) -> dict:
    """
    Classify the surface texture visible in image_path.

    Runs the vision model n_votes times, caching each run, then merges into
    one consensus result. Returns a dict with surface descriptors.

    Parameters
    ----------
    image_path : Path
        Path to texture PNG (or JPEG).
    n_votes : int
        Number of independent API calls to make. 3 is recommended.

    Returns
    -------
    dict with keys: dominant_label, labels_present, label_coverage,
                    cracks, aggregate, surface_condition, color_notes,
                    reuse_notes, confidence, n_runs, provider, model.
    """
    # Load provider + model from env (with sensible defaults)
    _load_dotenv()
    provider = os.environ.get("VISION_PROVIDER", "openai").lower()
    model    = os.environ.get("VISION_MODEL", "gpt-4o")

    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown VISION_PROVIDER '{provider}'. "
                         f"Options: {list(_PROVIDERS)}")

    call_fn = _PROVIDERS[provider]
    b64, media_type = _encode_image(image_path)

    run_results = []
    for run in range(1, n_votes + 1):
        cache_p = _cache_path(image_path, provider, model, run)
        cached  = _load_cache(cache_p)
        if cached:
            print(f"    run {run}/{n_votes} — cache hit")
            run_results.append(cached)
            continue

        print(f"    run {run}/{n_votes} — calling {provider}/{model} ...",
              end=" ", flush=True)
        raw    = call_fn(b64, media_type, model)
        result = _parse_response(raw)
        _save_cache(cache_p, result)
        status = "OK" if not result.get("parse_error") else "PARSE ERROR"
        print(status)
        run_results.append(result)

    merged = _merge_runs(run_results)
    merged["provider"]     = provider
    merged["model"]        = model
    merged["image_path"]   = str(image_path)
    merged["data_status"]  = "computed"
    return merged


def _load_dotenv() -> None:
    """Load env/.env if present (python-dotenv)."""
    try:
        from dotenv import load_dotenv
        env_file = Path(__file__).resolve().parents[2] / "env" / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
    except ImportError:
        pass
