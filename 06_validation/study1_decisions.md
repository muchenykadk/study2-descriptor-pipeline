# Study 1 Decisions — Validation Ledger

Protocol: `../paper_draft/paper_validation_method_draft.md`. Validates **assignment** and **face-use** decisions among the ten scanned fragments. Initial selection from the stock is out of scope (rejected material was not scanned).

**Workflow:** fill Table A from contemporaneous Study 1 records (photos, notes, IASS doc) → encode each query in Table B and freeze it before ranking → run over pipeline output → record rank, outcome, diagnosis.

---

## Table A — Decision reconstruction (fill from records)

| ID | Type (assignment / face-use) | Axis (aesthetic / geometric / mass / mixed) | Description | Ground truth (FRAG-ID / face) | Evidence source (photo, note, IASS ref) | Stated reason | Implicit criterion |
|---|---|---|---|---|---|---|---|
| D1 | assignment + face-use | geometric + mass | Fragment inclined as leaning back-rest | | | usable lean angle; stable in public | large planar face at lean angle in resting pose; mass resists displacement |
| D2 | | | | | | | |
| D3 | | | | | | | |

## Table B — Query and result (freeze query before ranking)

| ID | Query encoding (descriptors + filter/sort) | Candidate pool | Testable now (yes / partial / no) | Rank of ground-truth choice | Outcome (match / partial / divergence) | Diagnosis (missing descriptor / wrong value / tacit) |
|---|---|---|---|---|---|---|
| D1 | rank fragments by planar-region area > T with normal 60–80° from horizontal in resting pose; mass_est > safety T; scan_reliable = true | 10 fragments | partial (resting-pose not computed) | | | |
| D2 | | | | | | |
| D3 | | | | | | |

---

## Candidate decisions to reconstruct (from IASS paper, confirm against records)

- Fragment(s) inclined for leaning; horizontal timber platforms for seating (assignment, geometric + mass).
- Former pipe penetration reused as integrated planter (face-use, aesthetic / feature reuse).
- Heavy fragments positioned as stable base, resisting informal displacement (assignment, mass).
- Faces selected as timber-connection zones, chosen for flat, stable bearing (face-use, geometric).
- Fragments with visible cast character or prior-use traces placed as show faces outward (face-use, aesthetic).
- Irregular fragments nested for mutual support in self-stabilising assembly (assignment, geometric + mass; may be hard to encode as a per-fragment query, candidate for "tacit").

## Target

Roughly 8–12 decisions across the four axes. Aesthetic and geometric axes are best represented in the pipeline; mass axis testable via mass_est; structural inference remains weakest. Every row grounded in a contemporaneous artifact.
