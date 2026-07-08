# Study 2 — Descriptor Extraction Pipeline

Computational pipeline prototype (Rhino 8 + Grasshopper + CPython, cloud vision APIs) extracting geometric, surface character, and composite descriptors from Study 1 concrete fragment scans, linked to procedural/performance attributes. Proof-of-concept with pseudo data.

See `PLAN_Study2.md` for the full plan and folder conventions.

Fragment ID convention: `FRAG-S1-###` (zero-padded). One subfolder per fragment under `01_input/photogrammetry/raw_exports/` (untouched scans), `01_input/meshes/processed/` (cleaned analysis meshes), and `01_input/photos/`.

Setup: open `env/requirements.txt` packages via `# r:` lines in Rhino 8 ScriptEditor components, or install into the Rhino CPython runtime. Copy `env/.env.example` → `env/.env` and add API keys (gitignored).
