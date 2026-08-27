# Study 1 Decisions — Validation Ledger

Protocol: `../paper_draft/paper_validation_method_draft.md`. Validates **assignment** and **face-use** decisions among the scanned fragments (twelve processed to date). Initial selection from the stock is out of scope (rejected material was not scanned).

**Workflow:** fill Table A from contemporaneous Study 1 records (photos, notes, IASS doc) → assign a competency (A–D) → encode each query in Table B and freeze it → run over pipeline output twice, full descriptor set and geometry-only → record candidate set size, whether it contains the documented choice, outcome, diagnosis.

**Scope: seven decisions total.** Six across competencies A–C, plus one in D. Prefer face-use decisions: twelve fragments give 84 candidate faces, which discriminates far better than a pool of twelve fragments. One well-evidenced decision beats three hand-waved ones; every row needs a contemporaneous artifact.

**Reporting is set-based, not rank-based.** With twelve fragments a rank is close to meaningless. Report instead: how many candidates the query returned, and whether the documented choice is among them, under both conditions. A smaller set still containing the choice = sharper discrimination.

**D3 reports differently, revised 2026-08-27, before any query was encoded or run.** The prototype used timber connections on many fragments, so D3 holds every instance rather than one. Its pool is the 84 faces of the corpus, of which the documented connection faces are the positives and every other face is a negative. It therefore reports precision and recall rather than set containment.

Two conditions on reading it. The negatives are real only at face level: if most fragments took a connection somewhere, the fragment-level criterion has nothing to separate. And the row must be scored against the null query that returns every face, which by construction reaches recall 1.0 at precision equal to the positive rate. A result near that baseline is a null result, not a pass.

Recorded so the revision is not read as result-driven: at the time it was made, `connection_strategy` was already known to return `direct_bolt` on 65 of 79 faces, so the revision was expected to make the row harder to pass, not easier.

---

## Query competencies (after Mitropoulou et al. 2026)

| Cat | Competency | Example decision type |
|---|---|---|
| A | Attribute filtering: fragments/faces carrying a given surface condition | show-face selection, feature reuse |
| B | Multi-criteria selection: geometry + surface + mass together | leaning fragment, stable base |
| C | Linked query: a surface condition located on a specific face | connection zone on a clean planar face |
| D | Documented but inexpressible: ground truth known, descriptors cannot state the criterion | mutual-support nesting, site-improvised choices |

Category D tests failure behaviour: the query should be refused as inexpressible, not answered with an unfounded ranking. It also keeps the query set from being limited to cases the pipeline can win.

## Ground-truth notation

Faces carry no ID. They exist only as positions in the `planarity` array of
`05_output/descriptors/FRAG-S1-FS-###_geometry.json`.

**Write the number the 3D viewer shows on hover, unconverted.** The viewer labels faces
"Region N" and builds that panel by iterating `planarity`, so it points at the right object,
but it displays `i + 1` over a zero-based array. **Viewer "Region 4" is `planarity[3]`.**
The ledger stores the viewer number; the analysis script subtracts one. Do not subtract by
hand.

Format: `FS-###` abbreviating `FRAG-S1-FS-###`, brackets holding viewer Region numbers.
**Commas group the fits covering one physical surface. Semicolons separate distinct
decisions.**

| case | write |
|---|---|
| one face | `FS-011[4]` |
| one physical surface split across several plane fits | `FS-011[1,4,5]` |
| several instances in one row (D3) | `FS-002[4]; FS-004[2,6]; FS-006[3]` |
| two separate instances on the same fragment | `FS-011[1,3]; FS-011[6]` |
| surface exists in the photo, no plane fit lands on it | `none` |
| face exists in the record but has too few sampled points to identify | `unresolvable` |

The comma and semicolon rows matter for scoring. `FS-011[1,3,6]` is one positive found by
any of three indices; `FS-011[1,3]; FS-011[6]` is two positives. Collapsing the second into
the first silently loses a positive from the D3 recall count.

`none` and `unresolvable` are different findings and must not be merged. Leave a cell blank
only while it is still unfilled.

Assign every index from the photograph and the viewer's shape alone, and write it down before
opening the JSON. Reading `area_m2_est`, `fit_rms_mm`, `scan_reliable` or the `procedural`
block first would select the answer using the same data the query is tested on.

Two limits of the viewer for this task. The point cloud is a 2,000-point sample, so a face
holding a few dozen points cannot be identified by eye: that is the `unresolvable` case. And
on FS-003 roughly half the sampled points belong to no face at all, so `none` will come up.

Face counts per fragment, for checking an index is in range:

| FS-001 | FS-002 | FS-003 | FS-004 | FS-005 | FS-006 | FS-007 | FS-008 | FS-009 | FS-010 | FS-011 | FS-012 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 8 | 8 | 6 | 5 | 6 | 8 | 6 | 8 | 8 | 8 | 8 |

87 faces in total, as of the FS-001 re-run on 2026-08-27. FS-001 previously held a stale
record from 2026-08-19 with 5 faces and the retired vocabulary; any index recorded against it
before that re-run must be re-checked.

## Table A — Decision reconstruction (fill from records)

| ID | Cat | Type (assignment / face-use) | Description | Ground truth (FRAG-ID / face) | Evidence source (photo, note, IASS ref) | Stated reason | Implicit criterion |
|---|---|---|---|---|---|---|---|
| D1 | B | assignment + face-use | Fragment inclined as leaning back-rest | FS-002 | | usable lean angle; stable in public | large planar face at lean angle in resting pose; mass resists displacement |
| D2 | B | assignment | Heavy fragment positioned as stable base, resisting informal displacement | FS-003; FS-006; FS-004 | | too heavy to move | mass above a threshold; broad bearing face |
| D3 | B | face-use, all instances | Every face selected as a timber-connection zone across the prototype | FS-011[1,3,6]; FS-003[3,6]; FS-006[6]; FS-002[5,7] | | flat, stable bearing for a fixing | face area and flatness within the direct-bolt band; scan_reliable |
| D4 | B | assignment | Fragment chosen to carry a horizontal timber platform for seating | FS-003; FS-011 | | right height, stayed put | height band; mass; a flat enough top face |
| D5 | B | face-use | Within one fragment, which face was chosen as the upward face | | | it was the flattest, largest side of that piece | greatest face area among faces meeting a flatness threshold, scan_reliable = true |
| D6 | A | face-use | Fragment with visible cast character or prior-use trace placed as show face outward | FS-010; FS-002; FS-008 | | the piece had a story worth showing | a formation or inclusion feature on a face |
| D7 | D | face-use | Former pipe penetration reused as integrated planter | FS-001[1,3,6]; FS-002[5,7]; FS-002[4,2] **flagged, see below** | | the opening was already there | a through-void of usable depth on the piece |

**Declared negatives for D3.** Fragments that took no timber connection: FS-007, FS-012.
The remaining six (FS-001, FS-004, FS-005, FS-008, FS-009, FS-010) are unrecorded either way,
so the precision figure rests on two confirmed negatives only.

### Data-quality flags, 2026-08-27

- **D7 is usable. An earlier note here called it unusable and was wrong on both grounds.**
  `FS-001[6]` was out of range against a 5-face record; the re-bake gave FS-001 8 faces, so it
  is valid. And the repeated bracket patterns across D3 and D7 are not evidence of copying: a
  fragment can carry both a connection zone and an opening. Corrected 2026-08-27.

  Ground truth that the pipeline fails to match is what a Category D row is for. D7 now
  carries two distinct mechanisms, which is stronger than one. On FS-001 the opening is
  visible in the atlas and never reaches the model, because the smear gate discards its whole
  region. On FS-002 the model **does** report `pipe_opening`, on region 8, and it evaporates
  because that region is a cluster with `plane_index: None`, so no face carries the label and
  `planter_void`, which requires one, cannot fire. The descriptor exists, the model produced
  it, the vocabulary contains it, and the query still cannot be expressed.
- **D3's reading is unconfirmed.** The comma convention above was not in the file when the row
  was filled. Read as 8 independent faces it scores 7 of 8; read as 4 surfaces it scores 3 of 4.
- **D1, D2, D4, D6 hold fragment IDs only.** D1 and D6 are typed as face-use and need a face
  index before they can be scored at face level.
- **Evidence column is empty on every row.** No row is reportable until it carries a
  contemporaneous artefact.

## Table B — Query and result (freeze query before running)

**Frozen 2026-08-27.** No threshold below was chosen for this evaluation. Each row maps the
Implicit criterion in Table A onto a rule already in `env/design_factors.json`, and both of
those predate the evaluation: the criteria were written before any decision was reconstructed,
and the rules before the corpus was run. The mapping itself was written after the queries had
been run once, which is stated here rather than concealed. The runs are deterministic, so
re-running changes nothing; what the late drafting could bias is the *choice* of rule, and
citing an existing rule per row rather than composing predicates is what limits that.

### Encoding

| ID | Query | Thresholds it carries | Expressible? |
|---|---|---|---|
| D1 | `--use leaning_support --rank area` | face ≥0.2 m², rms ≤15 mm, scan_reliable; ≥150 kg | reported by rank: every fragment clears every threshold |
| D2 | `--min-thickness 500` | see note below | yes, on the corrected criterion |
| D3 | `--connection direct_bolt --reliable-only` | the direct-bolt area and flatness band, scan_reliable | yes |
| D4 | `--use seat_block` | face ≥0.1 m², rms ≤10 mm, scan_reliable; height 380–520 mm; ≥50 kg | yes |
| D5 | faces of one fragment, ranked by area under a flatness and reliability filter | as D3 | yes, ground truth unfilled |
| D6 | `--use exposed_face` | a formation or inclusion feature on a surface ≥0.1 m² | yes |
| D7 | `--use planter_void` | surface labelled `pipe_opening`; thickness ≥100 mm | yes |

**D1 reports a rank, not a set.** `leaning_support` needs a face ≥0.2 m² at rms ≤15 mm and
mass ≥150 kg. Every fragment has a face between 0.32 and 1.78 m² at rms ≤1.8 mm, and the
lightest is 181 kg, so all twelve clear every bar by a wide margin. That is a finding about the
thresholds against this corpus. Tightening them now, with the documented answer visible, would
be fitting, so the row reports where FS-002 falls when the corpus is ranked by largest usable
face.

**D2's criterion was corrected on 2026-08-27, before re-encoding.** Table A recorded it as
"too heavy to move". That is wrong: an excavator moves every piece in this corpus, and
`handling_class` returns `excavator` for all twelve, correctly, since EN 474-5 and ISO 8643
set thresholds above which extra equipment is required and no upper bound on mass. The real
criterion is thickness and integrity, a piece substantial enough to stay put and not fragile
enough to break. The correction comes from the author's design knowledge, not from the data.

The 500 mm threshold sits inside a 142 mm discontinuity in the corpus, 596 mm then 454 mm.
Anything from 460 to 590 returns the same seven fragments, so the result does not depend on
the value chosen. Recorded because the encoding was written after the queries had been run
once.

### Result

Pool is twelve fragments and 87 faces. Recall is reported with the size of the set it came
from, since the ledger holds confirmed positives and almost no confirmed negatives, and
precision needs negatives. A query returning everything scores recall 1.0, so the set size is
what makes the figure mean anything.

| ID | Set returned | Recall | Geometry-only | Reads as |
|---|---|---|---|---|
| D1 | 12 of 12, FS-002 at rank 4 | 1 of 1 | same | no reduction; thresholds below the corpus range |
| D2 | **7 of 12**, 42% reduction | **3 of 3** | same | full recall at a real reduction |
| D3 | 68 of 87 faces, 22% reduction | 0.88 | same | **below the null**: loses 12% of the answers to remove 22% of the field |
| D4 | 4 of 12, 67% reduction | 1 of 2 | same | selects; misses FS-003 on the height band |
| D6 | **5 of 12**, 58% reduction | **2 of 3** | 0 of 12 | misses FS-008, which carries no inclusion label anywhere |
| D7 | **2 of 12**, 83% reduction | **1 of 2** | 0 of 12 | misses FS-001, whose opening is gated out before classification |

**Four of six rows now narrow the field while keeping part of the documented answer**, against
two before the 2026-08-27 changes. **Two rows depend on the surface descriptors**, D6 and D7,
both collapsing to nothing under `--geometry-only`, against one before.

D3 is the remaining failure and its cause is known: `area_m2_est` is the convex hull of a
plane's inliers, and those inliers form 51 to 372 disconnected patches, so the rule reads a
bearing area that does not exist as a contiguous surface.

Full diagnosis in `query_validation_2026-08-27.md` and `where_the_queries_fail_2026-08-27.md`.
`dry_run_2026-08-27.md` is superseded.

## Candidate decisions to reconstruct (from IASS paper, confirm against records)

- Fragment(s) inclined for leaning; horizontal timber platforms for seating (assignment, geometric + mass).
- Former pipe penetration reused as integrated planter (face-use, aesthetic / feature reuse).
- Heavy fragments positioned as stable base, resisting informal displacement (assignment, mass).
- Faces selected as timber-connection zones, chosen for flat, stable bearing (face-use, geometric).
- Fragments with visible cast character or prior-use traces placed as show faces outward (face-use, aesthetic).
- Irregular fragments nested for mutual support in self-stabilising assembly (assignment, geometric + mass; may be hard to encode as a per-fragment query, candidate for "tacit").

## Target and allocation, revised 2026-08-27

Seven decisions over twelve fragments and 84 faces. Allocation follows what the frozen corpus
can discriminate, set out in `evaluation_allocation_2026-08-27.md` and fixed before any
decision was reconstructed.

**B, five decisions.** The only category exercising values marked `measured`. Mass spans
181 to 2562 kg, longest dimension 737 to 2882 mm, and every fragment has five to eight faces
with varying area and flatness.

D5 differs from the rest of B in two ways worth stating. Its pool is the faces of a single
fragment rather than the whole corpus, so mass is constant across the candidates and drops out
of the criterion. And it is the one B decision independent of resting pose: the face was
selected on its own properties and the piece was then rotated to bring it up, so the query
asks about face area and flatness and never about orientation. D1 is only partial for the
opposite reason.

D5 should not be extended to all twelve pieces. D1 fixes orientation by setting the lean angle
and D4 fixes it by requiring a flat surface for the platform, so a D5 covering everything would
make those two rows subsets of itself. It applies only where a rejected alternative can be
named.

**A, one decision.** Twelve of 79 faces carry any feature, and the only distinctive attribute
query available is `--label brick_inclusion`, returning two faces. Five active features reach
no face at all.

**C, folded into A.** A condition on a specific face is possible only for brick, on FS-002 or
FS-004, so it would duplicate D6.

**D, one decision.** D7's descriptor exists, on two non-planar regions, and no face carries
it, so `planter_void` cannot fire and the query cannot be expressed.

**D8 removed 2026-08-27.** It held the mutual-support nesting case: irregular fragments
resting against each other in a self-stabilising assembly. Removed at the author's decision on
the grounds that no descriptor leads to that conclusion. Recorded here because that is also
the qualifying condition for Category D, so the removal narrows what the ledger tests: the
record describes fragments independently and holds no inter-fragment relation, and the ledger
no longer carries a row stating so. The limitation itself is still worth stating in the
discussion. Total falls from eight decisions to seven, D from two to one.

Every row needs a contemporaneous artefact: a photo, a design note, or an IASS reference.
Fill Table A completely before Table B is encoded, and encode Table B before running anything.
