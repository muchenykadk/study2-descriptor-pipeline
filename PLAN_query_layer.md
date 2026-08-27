# Plan — Query layer over the fragment records

Status: **planned, not implemented.** Decided 2026-08-14. Paper text must not claim
results from this until it runs.

## 1. Why

The evaluation in §5.2 encodes each documented Study 1 decision as a query over the
descriptors. Without a query layer those queries exist only as ad-hoc scripts, which
makes the evaluation unreproducible and leaves the paper claiming records are
"structured so they can be queried" without showing it. A small, honest query layer
turns that into a demonstrated capability and gives §5.2 a defensible instrument.

## 2. Scope

**In scope**
- Structured predicates over explicit fields of the per-fragment JSON records.
- Fragment-level and face-level predicates, combined with AND.
- Ranking by a numeric field, top-k.
- A geometry-only mode that withholds surface fields, for the §5.2 baseline.
- A filter UI on the existing inventory page, reading the same records.

**Out of scope (state this in the paper)**
- Natural-language querying, LLM-in-the-loop retrieval, embeddings, RAG.
- Cross-fragment reasoning (assembly, sequencing, mutual support).
- Persistence beyond the JSON files; no database, no server-side index.
- Any coupling to a live design environment.

## 3. Query capabilities, mapped to the §5.2 categories

| Cat | Competency | Predicate support needed |
|---|---|---|
| A | attribute filtering | `has_label(l)`, `face.surface_label == l` |
| B | multi-criteria ranking | numeric filters on `mass_kg_est`, `obb_dims_mm`, `area_m2_est`, `fit_rms_mm`; sort + top-k |
| C | linked query | face-level conjunction: `area > X AND surface_label == Y AND scan_reliable` |
| D | control | queries that cannot be expressed; documented as unsupported, not silently failing |

Category D matters: the query layer must *refuse* what it cannot express rather than
return a plausible wrong answer. Unsupported predicates raise, and the ledger records
the refusal.

## 4. Components

1. **`03_src/query.py`** — loads all `*_geometry.json`, exposes
   `select(filters, rank_by, top_k, geometry_only=False)`; returns ranked rows with the
   fields that satisfied each predicate. Pure Python over the JSON, no new dependency.
2. **CLI** — `python 03_src/query.py --label formwork_imprint --min-area 0.3 --max-mass 500 --rank area`
   for reproducible, frozen evaluation runs.
3. **Query file** — the §5.2 queries stored as a YAML/JSON list, frozen before ranking,
   so the evaluation is re-runnable and auditable.
4. **Inventory filter UI** — filter controls on `05_output/descriptors/index.html`
   (label checkboxes, mass and area sliders) filtering the fragment cards live. Same
   records, no server. Gives a figure for the paper.

## 5. Effect on the paper

- **§3.1 objective 2**: "...extracts geometric and surface descriptors and structures
  them, with registry data, under a schema derived from those requirements, and makes
  them queryable."
- **§5.1**: add a short paragraph describing the query layer, its predicates, and the
  geometry-only mode.
- **§5.2**: replace "no query interface or retrieval system is contributed here" with a
  statement that queries run through the layer in §5.1, which is what makes the
  evaluation reproducible.
- **§6.3 scope paragraph**: change from "contributes no query interface" to "contributes
  a structured query layer over the records; natural-language querying and coupling to
  a design environment remain outside scope."
- **Contribution triad**: fold into the instrument, no fourth claim — "a working
  pipeline that extracts, structures, and makes fragment descriptors queryable".
- **Fig. 2**: output box becomes records → query layer → viewer.
- **Honest caveat to keep**: six fragments demonstrate the mechanism, not performance at
  inventory scale.

## 5b. Related: execute the derivation rules — **DONE 2026-08-14**

§5.2 now includes a second reading of the evaluation: what the record adds beyond the
choice, i.e. the implications attached to each descriptor. That requires the derivation
rules (`connection_strategy`, `handling_class`, `design_assignment`) to be **run**, not
just specified. They are simple predicates over fields already computed:

- `handling_class` ← `mass_kg_est` + `obb_dims_mm`
- `connection_strategy` ← per-face `area_m2_est`, `fit_rms_mm`, `surface_label`, `scan_reliable`
- `design_assignment` ← per-face `surface_label` + orientation

**Circularity warning, to be stated in the paper:** the rules were drawn in part from
Study 1 experience, so agreement with Study 1 decisions is expected and is not
validation. The paper reports this as a demonstration of the linkage, with disagreements
treated as the informative cases.

Scope: run on all six fragments, present the comparison for two. Output written into the
`procedural` block of each record with `data_status: proposed`.

## 6. Sequence

1. Finish the paper text with the query layer described as part of the instrument.
2. Re-run FS-002 (currently point-cloud path), FS-003, FS-004, FS-005 so all six records
   are produced by the same method and unit-correct.
3. Build `query.py` + CLI + frozen query file.
3b. ~~Execute the derivation rules into the `procedural` block~~ — done; `03_src/descriptors/design_factors.py` + `env/design_factors.json`.
4. Fill the decision ledger; run §5.2 twice per query (full, geometry-only).
5. Add the inventory filter UI; screenshot for the figure.
6. Write results into §5.2 and update Table 2.

Steps 3–5 are roughly a day. Step 2 blocks everything and should go first.
