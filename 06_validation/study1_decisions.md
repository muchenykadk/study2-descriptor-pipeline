# Study 1 Decisions — Validation Ledger

Protocol: `../paper_draft/paper_validation_method_draft.md`. Validates **assignment** and **face-use** decisions among the scanned fragments (six processed to date). Initial selection from the stock is out of scope (rejected material was not scanned).

**Workflow:** fill Table A from contemporaneous Study 1 records (photos, notes, IASS doc) → assign a competency (A–D) → encode each query in Table B and freeze it → run over pipeline output twice, full descriptor set and geometry-only → record candidate set size, whether it contains the documented choice, outcome, diagnosis.

**Scope: eight decisions total.** Six across competencies A–C, plus two in D. Prefer face-use decisions: six fragments give roughly forty candidate faces, which discriminates far better than a pool of six fragments. One well-evidenced decision beats three hand-waved ones; every row needs a contemporaneous artifact.

**Reporting is set-based, not rank-based.** With six fragments a rank is close to meaningless (chance ≈ 3.5). Report instead: how many candidates the query returned, and whether the documented choice is among them, under both conditions. A smaller set still containing the choice = sharper discrimination.

---

## Query competencies (after Mitropoulou et al. 2026)

| Cat | Competency | Example decision type |
|---|---|---|
| A | Attribute filtering: fragments/faces carrying a given surface condition | show-face selection, feature reuse |
| B | Multi-criteria selection: geometry + surface + mass together | leaning fragment, stable base |
| C | Linked query: a surface condition located on a specific face | connection zone on a clean planar face |
| D | Documented but inexpressible: ground truth known, descriptors cannot state the criterion | mutual-support nesting, site-improvised choices |

Category D tests failure behaviour: the query should be refused as inexpressible, not answered with an unfounded ranking. It also keeps the query set from being limited to cases the pipeline can win.

## Table A — Decision reconstruction (fill from records)

| ID | Cat | Type (assignment / face-use) | Description | Ground truth (FRAG-ID / face) | Evidence source (photo, note, IASS ref) | Stated reason | Implicit criterion |
|---|---|---|---|---|---|---|---|
| D1 | B | assignment + face-use | Fragment inclined as leaning back-rest | | | usable lean angle; stable in public | large planar face at lean angle in resting pose; mass resists displacement |
| D2 | | | | | | | |
| D3 | | | | | | | |
| D4 | | | | | | | |
| D5 | | | | | | | |
| D6 | | | | | | | |
| D7 | D | | | | | | |
| D8 | D | | | | | | |

## Table B — Query and result (freeze query before running)

| ID | Cat | Query encoding (fields + predicates) | Pool | Testable now (yes / partial / no) | Full: set size | Full: contains choice | Geom-only: set size | Geom-only: contains choice | Outcome | Diagnosis |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | B | planar faces with area > T, normal 60–80° from horizontal in resting pose, scan_reliable = true; fragment mass_est > T | 6 frags | partial (resting pose not computed) | | | | | | |
| D2 | | | | | | | | | | |
| D3 | | | | | | | | | | |

## Candidate decisions to reconstruct (from IASS paper, confirm against records)

- Fragment(s) inclined for leaning; horizontal timber platforms for seating (assignment, geometric + mass).
- Former pipe penetration reused as integrated planter (face-use, aesthetic / feature reuse).
- Heavy fragments positioned as stable base, resisting informal displacement (assignment, mass).
- Faces selected as timber-connection zones, chosen for flat, stable bearing (face-use, geometric).
- Fragments with visible cast character or prior-use traces placed as show faces outward (face-use, aesthetic).
- Irregular fragments nested for mutual support in self-stabilising assembly (assignment, geometric + mass; may be hard to encode as a per-fragment query, candidate for "tacit").

## Target

Eight decisions: six across A–C, two in D. Aesthetic and geometric axes are best represented in the pipeline; mass axis testable via mass_est; structural inference remains weakest. Every row grounded in a contemporaneous artifact.
