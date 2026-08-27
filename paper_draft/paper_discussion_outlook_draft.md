# Paper §7 — Discussion and Outlook (draft)
*Working draft, 2026-07-23. Section number provisional (Discussion follows Results and Validation; §6 gap-table was cut). Evaluation subsection is a FRAMEWORK with [PENDING] placeholders until the retrospective validation is run (see `paper_validation_method_draft.md` and `06_validation/study1_decisions.md`). No em-dashes; no "rather than" constructions.*

---

## Discussion and Outlook

### Contribution

The two studies together advance a material-adaptive approach to reclaimed concrete that moves beyond geometric matching. Study 1, a built public installation, verified the design-to-construction workflow and surfaced its information requirements; Study 2 provides the digital infrastructure that moves the characterization of irregular concrete from tacit, one-by-one judgment toward a computable, queryable form.

The contribution is twofold. Conceptually, the work shows that rough, highly variable construction waste can drive the design and construction of a public installation at landscape and urban-furniture scale through a computational workflow, while keeping the process design- and material-driven. Technically, Study 2 demonstrates the feasibility of combining geometric computation with vision models to characterize irregular fragments automatically into a queryable record, with surface conditions located on the 3D geometry; practical steps, such as preparing photogrammetry meshes and raw point clouds into clean, computable data and flagging reconstructed surfaces, were addressed and may benefit similar projects. The 3D visualization of located features is a first step toward integrating the enriched records into a design interface, the design-environment integration set as this research's overarching aim.

### Design implications

Making these descriptors computable and queryable changes how design with reclaimed concrete can proceed. A designer can interrogate a fragment stock by geometry, surface character, and procedural constraint together, so selection and assignment become reproducible, multi-criteria queries, no longer bound to one person's memory of the pile. Aesthetic and material-history properties, previously accessible only by handling each piece, become searchable, allowing the spolia sensibility of Study 1 to operate at the scale of a demolition stock. Bringing handling and connection constraints into the same query surface lets them shape design decisions at the point those decisions are made.

### Evaluation

*[FRAMEWORK — results PENDING the retrospective validation run; see protocol in `paper_validation_method_draft.md`.]*

The pipeline is assessed by whether its descriptors, queried, recover the assignment and face-use decisions documented in Study 1 (initial selection is out of scope, as rejected material was not scanned). Each decision is encoded as a descriptor query, frozen before ranking, and the pipeline's ranking is compared with the designer's actual choice; matches indicate the criterion was captured, divergences indicate a missing descriptor or still-tacit knowledge.

- **Overall recovery:** [PENDING: X of N documented decisions recovered across the ten fragments.]
- **Aesthetic axis** (surface labels vs. show-face and feature-reuse decisions): [PENDING result]. Expected to be the strongest axis, since surface classification is the pipeline's central contribution.
- **Geometric axis** (planarity, orientation vs. seating, leaning, connection faces): [PENDING result]. Anticipated partial result at the resting-pose step: the pipeline reports planar faces and normals in scan coordinates, but the orientation a face presents once the fragment is placed is not yet computed. [Confirm whether this surfaces as a divergence once run.]
- **Mass axis** (mass estimate vs. handling and stability decisions): [PENDING result].
- **Divergences as findings:** [PENDING: list each divergence and its diagnosis — missing descriptor, wrong value, or tacit knowledge.]

This is proof-of-principle within a single project, and the decisions serving as ground truth were made by the same designers who conducted the research; it is first evidence of design relevance, not independent validation.

### Limitations

The evaluation basis is small and single-case (see Methodology). Beyond that, three boundaries are intrinsic to the current prototype, and the schema marks each with an explicit data-status flag, so it is reported as a placeholder or an assumption and not as verified data. The procedural design-factor layer is a placeholder that demonstrates the schema's linkage structure and is not a validated knowledge base. The derived rules that would compute connection strategy, handling class, and design assignment are specified but not executed, so those conclusions are proposed, not demonstrated. And the structural attributes that resist scan-based measurement, concrete strength, reinforcement layout and direction, and centre of mass, remain assumptions carried as flagged pseudo entries. The subtype taxonomy is likewise a target design, reported only at the seven-class level that the demonstration supports. The vision-based classification is also not yet benchmarked: its accuracy has been examined on individual worked examples and has not been measured against an annotated reference set. Establishing such a benchmark, particularly for structurally consequential conditions such as exposed reinforcement and cracking, is needed before the AI cataloguing of surface features can be relied upon.

### Outlook and future work

Several directions extend the work. Descriptor combinations could support the inference of higher-order and sequential design behaviours: the interaction of mass, planarity, and surface condition across fragments bears on assembly order, stacking sequence, and rules where the placement of one fragment constrains the next, which a per-fragment record does not yet express. The record could then be integrated into a live design system, coupling the queryable descriptors to a CAD or parametric environment so that inventory search, algorithmic matching, and optimization operate directly on the enriched model. This coupling is the design-environment integration named as the overarching aim of the research and is the step this groundwork prepares.

Nearer-term development would close the boundaries above: grounding the procedural knowledge in verified domain expertise through expert elicitation; executing and testing the derived rules; adding a resting-pose estimate to close the geometric-axis gap; binding surface labels to individual faces so surface condition becomes queryable per face; and expanding the fragment set beyond the current ten. Subtype classification would need higher-resolution capture, a human-in-the-loop step, or a fine-tuned model before it could be claimed, and an unconstrained vision pass could propose labels beyond the fixed taxonomy for a designer to curate, letting the taxonomy evolve.

Finally, although the pipeline is demonstrated on fragmented, undocumented rubble, its applicability is anticipated for documented and future deconstruction stock. Applied to a standing element scheduled for deconstruction, the extracted visual and geometric descriptors could be synthesized with documented attributes, where records survive, to enrich the pre-demolition audit inventory and support design with buildings before they are taken down. In-situ scans of standing elements have more unscannable faces than a fragment lying on the ground, and the scan-reliability machinery introduced here is what makes such partial-coverage scans usable, with the reconstructed regions explicitly flagged.

## Conclusion

This paper has developed a computational basis for characterizing irregular demolition concrete as queryable design data, grounded in a built public commission and demonstrated on real fragment scans. Study 1 established the design potential of feature-rich rubble and the information its reuse requires; Study 2 turned those requirements into a working pipeline that extracts geometric and surface descriptors, locates surface conditions on the 3D geometry, and consolidates them into a per-fragment record.

The contribution is bounded honestly by three limits intrinsic to the current prototype, each marked in the schema with an explicit data-status flag. First, the procedural design-factor layer is a placeholder that demonstrates the schema's linkage structure and is not a validated knowledge base. Second, the rules that would derive connection strategy, handling class, and design assignment from the descriptors are specified but not yet executed, so those conclusions are proposed. Third, the structural attributes that resist scan-based measurement, namely concrete strength, reinforcement layout and direction, and centre of mass, remain assumptions carried as flagged pseudo entries. Within these bounds, the work provides the schema and the instrument on which design-stage integration can build, and points toward a material-adaptive design environment for reclaimed concrete and toward enriching the pre-demolition audit of standing structures.

---

## Notes / flags

- **Evaluation subsection is a framework with [PENDING] placeholders.** Fill from the validation run once the ten fragments are processed and `study1_decisions.md` is reconstructed. Do not present any recovery claim until the run exists.
- **Section numbering:** provisional. After §6 (gap table) cut, order is Results, Validation, Discussion and Outlook, Conclusion. Renumber consistently at assembly.
- **Consistency with earlier sections:** the three-tier data honesty (real scans / pseudo attributes / placeholder procedural knowledge) here must match §4 and §5. The "proposed not executed" rule status must match §4. The pre-demolition outlook matches the outline §9 plan; keep the UNSCANNED-as-enabler hook.
- **Overarching aim callback:** the "integrate into a live design system" paragraph deliberately echoes the Objectives aim (material-adaptive design environment); keep the wording aligned with the objectives draft.
- **"Sequential behaviours" future-work point** is Muchen's; articulated here as feature-combination → assembly/sequence inference. Refine if a more specific meaning was intended.
- Limitations here overlap Methodology (single-case, designer-as-researcher) intentionally at summary level; keep this brief and reference back rather than re-arguing.
- **Conclusion added 2026-07-23**: specifies the three intrinsic boundaries (procedural placeholder / rules proposed-not-executed / structural pseudo) as the honest-scope statement (Muchen's request). Three boundaries now appear in both Limitations and Conclusion by design; if heavy on full read, compress Limitations, keep Conclusion as final word. This file now holds Discussion, Outlook, and Conclusion.
