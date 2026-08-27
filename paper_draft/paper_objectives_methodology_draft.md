# Paper Objectives & Methodology — EKA Full Paper Draft
*Working draft v1, 2026-07-22. Target length ~0.5 pp. Follows the revised objective set in `paper_outline_EKA.md` §2; companion to `paper_introduction_draft.md` (intro ¶5 contribution framing). No em-dashes.*

---

## Research Objectives

The overarching aim of this research is an interactive design environment for reclaimed concrete, in which enriched, queryable per-fragment models support a fully material-adaptive design process with extended knowledge of geometry, surface character, and procedure informing the design phase directly. Within the scope of this paper, the contribution is the foundation and the instrument on which such a design method can build. Three specific objectives are pursued:

1. **Foundation.** To demonstrate the design and aesthetic potential of irregular concrete fragments through a built public commission in active public use, and to derive an information requirements scheme from its documented gaps.

2. **Instrument.** To prototype a computational pipeline that extracts geometric and surface descriptors from 3D scans and structures them, with registry data, under a schema derived from the Study 1 requirements and linked to encoded domain knowledge of handling and design implications.

3. **Evaluation.** To demonstrate the pipeline through a proof-of-concept workflow using real scans from Study 1 and unvalidated material performance data, and to retrospectively evaluate its application in a design task.

## Methodology

The research adopts a practice-led design in which the act of building is itself the mode of inquiry. Study 1 was conducted as Research through Design [Frayling, 1993]: the design and construction of a live public commission was used to encounter the constraints that real structural loads, machinery, public-use requirements, and construction tolerances impose, and to surface the information those constraints demand [Study 1 / IASS citation]. The knowledge this produced was situated and largely tacit, held in the designer's judgment and the project's records, with no transferable form. Study 2 follows from this condition directly. A practice-led inquiry that ends at a single built work leaves its knowledge bound to that work, so the methodological task is to externalize the situated characterization into a computational instrument that can be applied, queried, and reused beyond the original project. Study 2 is that externalization step: it develops the descriptor schema and pipeline against the requirements Study 1 produced and applies them to the same fragments, turning knowledge that was exercised once, by hand, into a form that can be repeated.

Because requirements, fragments, and design decisions all derive from one documented project, the instrument can be assessed retrospectively against it: each documented selection is re-expressed as a descriptor query and the pipeline's ranking compared with the designer's actual choice, with divergences read as missing descriptors or still-tacit knowledge. This offers first evidence of design relevance within a single case, made by the same designers who conducted the work; it is not independent validation.

---

## Notes / flags

- Objectives (v3, Muchen 2026-07-23): three, cleaner split — O1 Foundation (Study 1, = abstract's old 1–3), O2 Instrument = build only (extract + structure + link), O3 Evaluation = demonstrate + retrospectively evaluate. Supersede the abstract's four. Watchlist: no "CAD interface", no "multi-model AI integration".
- **Polish applied to Muchen's rewrite**: added "an" (O1), "real" before scans (O3 — the reviewer-facing word, keep it), tense parallelism (O3 "to demonstrate... and to retrospectively evaluate"), label O3 "Evaluation".
- **Two consistency calls to confirm**: (1) kept O2's "linked to encoded domain knowledge of handling and design implications" — Muchen's rewrite dropped it, but it's in intro contribution + diagram + §4; removing from O2 alone would under-represent. Confirm keep. (2) Objective-level status detail (pseudo/provisional/reviewer-response) now REMOVED from objectives; O3's "unvalidated material performance data" carries the honesty flag compactly. Full three-tier detail + the pseudo-to-real reviewer-response point now must live in §5 Results. Do not lose it there.
- Objective 3's reviewer-response sentence assumes the final paper may openly reference the review process; if EKA prefers not to, drop the final clause ("responding directly to reviewer feedback") and keep the factual upgrade statement.
- Cross-check: contribution list here must stay synchronized with intro ¶5 and with the Conclusion's claims. Update all three together if any objective shifts.
- Designer-as-researcher circularity is acknowledged in the Methodology paragraph; §8 Limitations can reference back rather than repeat.
- **Methodology revised 2026-07-23 (v2)**: rebalanced per Muchen — practice-led/RtD framing expanded to carry the section and to ARGUE why Study 2 exists (RtD produces situated tacit knowledge bound to one project → methodological task is to externalize it into a reusable instrument → Study 2 is that step). Evaluation compressed from a full paragraph to 2 sentences (thin content). Coupling rationale folded into the evaluation setup rather than standing alone.
- **Frayling (1993) citation ADDED as RtD anchor**: Frayling, C. (1993). Research in Art and Design. *Royal College of Art Research Papers*, 1(1). VERIFY exact vol/issue before submission. Appropriate for EKA (art academy venue). Alternatives/additions if wanted: Cross (2001) Designerly Ways of Knowing; Zimmerman et al. (2007) RtD as a method. IASS already labeled the method "Research through Design" — consistent.
- **"Externalization" argument** now the spine of the methodology; consistent with intro's tacit/no-computable-record thread. Keep in sync if intro changes.
- **DEPENDENCY for §7**: `06_validation/study1_decisions.md` is still an empty template (one blank row as of 2026-07-23). The methodology describes the evaluation *procedure*; §7 cannot report results until this table is reconstructed from Study 1 project records. This is the reviewers' key ask — highest-priority content blocker. Fill it (decision, fragment, position/role, stated reason, implicit criterion, query encoding) for the processed fragments before drafting §7.
- **Tense check**: methodology uses present tense to describe the evaluation as a procedure (standard). Ensure §7 does not inherit present tense as if results exist; §7 reports what the filled table yields.
