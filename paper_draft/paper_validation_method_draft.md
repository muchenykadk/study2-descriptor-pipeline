# Paper §7 — Validation Method: Recovering Study 1 Decisions (design + draft)
*Working design, 2026-07-23. This is both the §7 method and the protocol for filling `06_validation/study1_decisions.md`. No em-dashes; no "rather than" constructions.*

---

## 1. What is validated, and what is not

The claim under test: the descriptors the pipeline computes, combined by an explicit query, recover the fragment and face decisions the designer made in Study 1 through direct material handling.

**Testable:** assignment decisions (which kept fragment took which position or role in the built work) and face-use decisions (which face of a fragment served as seat, lean, connection, show, or ground surface). Both have a real candidate pool in the pipeline output: the ten scanned fragments, and the faces of each.

**Not testable here:** initial selection from the demolition stock. The fragments the designer rejected on site were never scanned, so there is no candidate pool against which to test why one fragment was kept and another discarded. This boundary is stated openly in the paper; validating selection would require scanning rejected material in a future study.

## 2. Unit of analysis

One row per documented decision. Each decision is one of two types:
- **assignment**: a fragment placed in a specific position or structural role.
- **face-use**: a specific face of a fragment used for a specific purpose.

Each decision is tagged with the axis it exercises, so recovery can be summarized per axis and fed back to the §6 gap table:
- **aesthetic** (surface-label descriptors): show-face and feature-reuse decisions.
- **geometric** (planarity, OBB, orientation): seating, leaning, connection-face decisions.
- **mass** (mass_est, OBB): handling and stability decisions.
- **mixed**: decisions drawing on more than one axis.

## 3. Query encoding and the circularity safeguard

Because the designer is also the researcher, the encoding step is where bias can enter. Three safeguards:

1. **Ground each decision in a contemporaneous record**, not memory: a project photo, a design note, or the IASS documentation. Record the artifact in the "evidence source" column. A decision with no contemporaneous record is logged but marked non-evidential.
2. **Encode the query from the stated or recorded reason**, before looking at how it ranks. The query expresses the design criterion as a filter and sort over descriptors; it is not tuned until it produces the right answer.
3. **Distinguish a criterion that was formalizable from one recovered only by hand-tuning.** The first is a genuine recovery; the second is reported as weak and flagged as tacit knowledge.

The query operates on the raw computed descriptors (planarity, orientation, mass_est, surface labels, scan_reliable). The combination rule applied by hand is exactly the logic the proposed `connection_strategy` / `handling_class` / `design_assignment` rules would automate, so each query result is also evidence for or against that proposed rule.

## 4. Workflow

1. **Reconstruct** each decision from Study 1 records into Table A: type, axis, ground-truth fragment or face, evidence source, stated reason, implicit criterion.
2. **Encode** each decision as a descriptor query (Table B), frozen before ranking.
3. **Mark testability** given the descriptors actually computed. A decision needing a descriptor the pipeline does not produce is marked partial or untestable; that itself is a §6 finding.
4. **Run** each query over the pipeline output for the ten fragments.
5. **Record** where the ground-truth choice falls in the pipeline's ranking (top-1, top-3, or not surfaced).
6. **Classify** the outcome: match, partial, or divergence.
7. **Diagnose** every partial and divergence: missing descriptor (criterion not captured by any descriptor), wrong value (descriptor computed but ranking wrong), or tacit knowledge (criterion not formalizable).
8. **Aggregate** per axis into a recovery summary that feeds §6 and the §7 narrative.

## 5. Scoring

- **Match**: the ground-truth choice is the pipeline's top recommendation, or within the top few for a small pool.
- **Partial**: the choice ranks plausibly but not top, or the query captures only part of the criterion.
- **Divergence**: the pipeline would not have surfaced the choice.

With ten fragments and roughly eight to twelve decisions, this is a qualitative, proof-of-principle comparison. Report a simple recovery count (for example, "eight of eleven decisions recovered") and treat every divergence as a finding. Make no statistical claim; state n and the single-project, single-designer basis plainly.

## 6. The three axes as query patterns

**Aesthetic (show-face / feature reuse).** Criterion: an exposed face carries a valued cast or finish quality. Query: rank faces by presence of `formwork_imprint` or `original_finish` on an outward-facing region; for feature reuse (pipe opening as planter), filter for the feature label on an up-facing region. Tests whether surface-label descriptors recover the faces the designer chose to expose.

**Geometric (seat / lean / connection).** Criterion: a face flat and stable enough to seat, lean against, or connect to. Query: rank faces by planar-region area with low fit_rms and an orientation, in the fragment's resting pose, in the target angle band; require scan_reliable = true. Tests whether planarity and orientation recover the faces actually used. Known likely limitation: the pipeline gives planar faces and normals in scan coordinates, but the resting pose when placed is not computed, so orientation-to-placement mapping may surface as a partial result and a real gap.

**Mass (handling / stability).** Criterion: heavy enough to resist displacement in public use, or within a handling class. Query: filter mass_est against the safety or handling threshold; combine with OBB dimensions. Tests whether the mass estimate recovers the handling and stability decisions.

## 7. Worked example (template, to be run)

- **Decision**: fragment placed at an incline as a leaning back-rest.
- **Type / axis**: assignment + face-use / geometric + mass.
- **Ground truth**: [FRAG-ID], from IASS Fig. 3 / project photo [ref].
- **Stated reason**: usable lean angle; stable in a public setting.
- **Implicit criterion**: a large planar face presenting a comfortable lean angle in the resting pose; mass sufficient to resist displacement.
- **Query**: among the ten fragments, rank by planar-region area above threshold whose normal falls in a 60–80° band from horizontal in resting pose; require mass_est above the public-safety threshold and scan_reliable = true.
- **Candidate pool**: ten scanned fragments.
- **Testable now**: partial (planarity, orientation, mass_est, scan_reliable computed; resting-pose estimation not computed).
- **Result / outcome / diagnosis**: [fill after running].

## 8. How results feed the paper

- Per-axis recovery updates the **status column of the §6 gap table** (computed and recovered / computed but divergent / open).
- Divergences populate **§8 discussion**: each is either a descriptor to add or a tacit criterion to acknowledge.
- The aesthetic axis is expected strongest (surface labels are the pipeline's novel contribution); the geometric axis will likely expose the resting-pose gap; the structural side stays weakest, consistent with the intro and §6.

## 9. Limits (for §7 and §8)

- Ten fragments, one project, one designer who is also the researcher: proof-of-principle, not independent validation.
- Selection from the full stock is out of scope (rejected material unscanned).
- Query encodings are hand-specified; the proposed derived rules are tested by proxy, not executed automatically.

---

## Notes / flags

- **Fills the §7 blocker**: `06_validation/study1_decisions.md` template restructured to match this protocol (Table A reconstruction + Table B query/result). Next action for Muchen: populate Table A from Study 1 records (photos, notes, IASS doc), grounding each row in a contemporaneous artifact.
- **Depends on**: the ten fragments processed through the pipeline (currently 2 confirmed complete). Cannot run queries until pipeline output exists for the candidate pool.
- **Resting-pose gap**: the geometric axis likely surfaces a real limitation (scan-frame normals vs. placement orientation). This is a genuine finding, not a failure. Consider whether a simple stable-pose estimate (largest downward-facing planar region as ground) is worth adding before submission to strengthen the geometric axis.
- **Selection-not-testable** boundary must appear in §7 and be consistent with any claim in the abstract/intro that could imply selection was validated. Check intro wording does not overclaim.
- This protocol makes the validation "cannot fail uninformatively": every outcome (match, partial, divergence) is a reportable result. Keep that framing in §7 prose.
