# [TITLE — pending, see side note N1]
*Compiled full-paper draft, 2026-07-23. Assembled from the section drafts in `paper_draft/`. Placeholders kept for pending data. Citation gaps marked inline as [CITATION NEEDED] or [citation]. Revision opinions collected in "Revision Notes" at the end. No em-dashes; no "rather than" constructions.*

---

**Abstract.** Demolition concrete is typically downcycled into aggregate, discarding the structural and material value of its irregular fragments. Their singular geometry and surface traces are design-relevant, yet assessing them has relied on tacit, fragment-by-fragment judgment that cannot scale. This paper develops a computational basis for characterizing such fragments as queryable design data, through two sequential practice-led studies. Study 1, a built public commission in urban furniture, demonstrated the design potential of irregular concrete and derived an information requirements scheme from its documented gaps. Study 2 prototypes a pipeline that takes a 3D scan of a fragment, extracts geometric and surface descriptors, classifies surface conditions with a vision-language model and localizes them on the geometry, and organizes the result into a queryable record. Demonstrated on real Study 1 fragment scans and assessed against that project's documented design decisions, the work provides the groundwork for material-adaptive design with reclaimed concrete at scale.

**Keywords:** concrete reuse, irregular material, computational characterization, design-to-fabrication, material-adaptive design [confirm keyword list with EKA template]

---

## 1. Introduction

Construction and demolition (C&D) waste accounts for roughly one-third of solid waste in the European Union, over 800 million tonnes annually (European Environment Agency, 2020). Although concrete recycling rates are high, the material is primarily downcycled into low-grade aggregates through an energy-intensive crushing process, discarding its original structural capacity (European Commission, 2023). Volumes of deconstruction concrete are expected to grow across Europe as successive generations of building stock reach the end of their service lives (Wiedenhofer et al., 2015). Underlying this downcycling is a framing problem: demolition waste is treated as a bulk flow to be processed, not as discrete fragments with differentiated properties and architectural potential.

Composing a spatial installation from variable, non-standard elements curated by their individual features is a long-standing architectural and artistic practice. In traditional Chinese gardens, lake stones of irregular shape are arranged into rockeries, garden walls, and stairs (Wang et al., 2024); the reuse of salvaged material has likewise been reinterpreted in modern work, from the Watts Towers that Simon Rodia built from waste [CITATION NEEDED: Watts Towers scholarly source] to Wang Shu's facades of recycled brick and tile at the Xiangshan campus [CITATION NEEDED: Amateur Architecture Studio / wa pan source]. Treating reclaimed concrete, whether components from planned dismantling or fragments from demolition, as a design resource in this spirit exposes an information asymmetry. Traditional material knowledge reaches designers in two modes: through direct, hands-on study of material character, as taught in the Bauhaus preliminary course (Itten, 1975; Moholy-Nagy, 1938), or, in industrialized practice, through selection from pre-characterized catalogues, where standardization guarantees the link between on-paper design and built result (Ashby & Johnson, 2002). A reclaimed concrete fragment resists both modes: as a found condition it is too singular for any catalogue, while a stock of hundreds of unique, heavy pieces exceeds what hands-on study can cover. Appearance, moreover, is only half of what must be known. For material this heavy, irregular, and non-malleable, handling machinery, connection feasibility, and placement constraints are not downstream logistics but coupled design decisions (Widmer et al., 2023; Küpfer et al., 2024; Bertola et al., 2025). Designing with demolition concrete at scale therefore depends on enriched, queryable per-fragment models, spanning appearance, geometry, and procedure, available where design decisions are made.

Existing methods each address one dimension of this need, largely in isolation from the others. On the documentation side, material passports and reuse databases record component-level data (Honic et al., 2021; Luo et al., 2024), and recent work structures pre-demolition audits into knowledge graphs queryable in natural language [KG-audit CITATION NEEDED]; yet what they hold (element types, quantities, coarse condition) remains at document granularity and does not actively enter computational design processes. On the design side, research on reclaimed inventories concentrates on geometric stock matching and allocation, treating elements as geometric tokens to fit a target form (Cousin et al., 2023; Eschenbach et al., 2023; Skoury et al., 2024; Blum et al., 2025); some of this work extends the allocation objective beyond geometry to environmental accounting, incorporating life cycle assessment and embodied carbon for reclaimed steel elements (Brütting et al., 2020) and cut concrete blocks (Önalan et al., 2025). Across these approaches, however, the element model remains geometric and quantitative; surface and condition stay outside it, leaving the material potential of each element's singularity unexplored as design data. For surface characterization itself, construction-inspection computer vision detects defects reliably (Dorafshan et al., 2018; Niklaus et al., 2023) but over closed categories that cannot describe the open-ended vocabulary of demolition surfaces; vision-language models lift this restriction, classifying against any user-defined taxonomy without retraining (OpenAI, 2024), yet stop at image-level labels that never locate a condition on the geometry governing structural role. Workflows that do operationalize the appearance of found objects computationally, from digitized garden rockery stones (Wang et al., 2024) to vision-based matching of scanned industrial scrap (Certain Measures, 2016), remain small-to-medium scale and object-specific. Semantic frameworks could bind such characterization into queryable knowledge (Rossi et al., 2026; Elshani et al., 2025; Elshani et al., 2024), but presuppose properties already recorded elsewhere, whether by laboratory testing, factory measurement, or audit documentation. No existing pipeline takes scan geometry and vision-based surface classification as primary input, integrating open-vocabulary classification, spatial localization, morphological analysis, and inventory structuring for demolition concrete.

This paper addresses this gap through a practice-led trajectory of two sequential studies, moving from situated design practice toward a computational instrument. Design explorations with irregular rubble itself have so far concentrated on wall-type structural assemblies and geometric matching, largely as laboratory prototypes (Grangeot et al., 2024; Oreb et al., 2024; Lu et al., 2026). Study 1, a built public commission, carried the material instead into an urban furniture project in active public use, demonstrating both the potential and the bottleneck of upcycling feature-rich, irregular rubble. Traces of past use, such as cladding residues, formwork imprints, and remaining pipe openings, acted as design-relevant properties that added character to the built work, an approach rooted in the spolia tradition; geometry and surface condition jointly determined each fragment's structural and aesthetic assignment [Study 1 / IASS CITATION NEEDED]. Yet the characterization behind these decisions relied on tacit, fragment-by-fragment designer judgment and left no computable record. The gaps this surfaced, in object-level characterization and procedural requirements, motivate Study 2.

Study 2 responds to the gaps argued above. It prototypes a computational pipeline that extracts required data from 3D scans, with both deterministic computation for geometric data and vision-model classification for surface features. The extracted descriptors, together with registry data, are structured under a schema derived from Study 1's information requirements and linked onward to encoded domain knowledge of handling and design implications. The pipeline is demonstrated on real fragment scans from Study 1 and assessed retrospectively against that project's documented design decisions, evaluating whether computed characterization can recover the selection logic the designer exercised through direct material knowledge. Within the scope of this paper, the records are structured for querying but not yet coupled to a live design workflow. The contribution lies in the descriptor schema grounded in built practice and a working digital pipeline that extracts and structures fragment descriptors, with first evidence of their design relevance, laying the groundwork on which design-stage integration can build.

## 2. Objectives and Methodology

### 2.1 Research objectives

The overarching aim of this research is an interactive design environment for reclaimed concrete, in which enriched, queryable per-fragment models support a fully material-adaptive design process with extended knowledge of geometry, surface character, and procedure informing the design phase directly. Within the scope of this paper, it contributes the foundation and the instrument on which such a design method can build. Three specific objectives are pursued:

1. **Foundation.** To demonstrate the design and aesthetic potential of irregular concrete fragments through a built public commission in active public use, and to derive an information requirements scheme from its documented gaps.

2. **Instrument.** To prototype a computational pipeline that extracts geometric and surface descriptors from 3D scans and structures them, with registry data, under a schema derived from the Study 1 requirements.

3. **Evaluation.** To demonstrate the pipeline through a proof-of-concept workflow using real scans from Study 1 and unvalidated material performance data, and to retrospectively evaluate its application in a design task.

### 2.2 Methodology

The research adopts a practice-led design in which making is the mode of inquiry. Study 1 is a Research through Design case study (Frayling, 1993): a live public commission is executed as the research instrument, so that the act of designing and building is what produces the knowledge sought. Such knowledge is situated and largely tacit, and a practice-led inquiry that ends at one built work leaves it bound to that work. The methodological task of Study 2 is therefore externalization: to turn the situated characterization into a computational instrument that can be applied, queried, and reused beyond the original project.

Because requirements, material, and design decisions all derive from that one documented project, the instrument can be evaluated retrospectively against it. Each documented decision is re-expressed as a query over the computed descriptors, and agreement or divergence is read as evidence of what the characterization captures and what remains tacit. This offers first evidence of design relevance within a single case, made by the same designers who conducted the work; it is not independent validation.

## 3. Study 1: Requirements from Built Practice

Study 1 built an urban furniture commission from demolition concrete rubble as a Research through Design case study, producing two prototypes now in active public use. Around twenty cast-in-place fragments were selected from the deconstruction site of an early twentieth-century building and digitized by photogrammetry. A digital-physical workflow (Fig. 1) then carried the project from this fragment inventory through a hybrid manual and computational design stage with rigid-body stability simulation, on-site concrete assembly guided by augmented-reality placement, and final assembly with adaptively fabricated timber connections. The stage-by-stage implementation and the full findings are reported in [IASS CITATION NEEDED].

One design principle of the built work was to carry the modern spolia spirit: treating the singular attributes in the rubble as design material. Former pipe penetrations were reinterpreted as integrated planters, cast faces and weathering were retained as exposed surfaces, and the contrast between the worn concrete and the new timber kept the reuse visible. Surface character thus informed fragment selection and placement together with geometry. This is the potential the case study demonstrated: irregular rubble, read for its material history, can hold both aesthetic and structural roles in a public landscape setting. In this study, however, the decisions regarding aesthetic features remained a manual curation process, which does not scale beyond a small set.

By reviewing the project implementation records, we identified the information required at each stage, mapped in Fig. 1; the full gap analysis is given in [IASS CITATION NEEDED]. Beyond the aesthetic features discussed above, structural and procedural gaps are also bottlenecks to scaling and streamlining the design-to-construction approach. In summary, the required information includes: structurally, estimated volume and mass, centre of mass, planar surfaces, exposed reinforcement, and crack grading; aesthetically, colour, surface roughness or aggregate size, and categorized surface features such as formwork imprints, tile residue, and weathering; and procedurally, machinery matched to a fragment's mass class and connections feasible for a given interface condition. These requirements define the descriptor schema developed in the following section.

*[Fig. 1 — Study 1 workflow with the information/attributes required at each stage across structural, aesthetic, and procedural dimensions. Adapted from IASS. See side note N7 on figure reuse.]*

## 4. Study 2: Fragment Characterization Pipeline

Study 2 responds to the gaps identified in Study 1 by developing a prototype computational pipeline that takes a 3D scan of an irregular concrete fragment, enriches it with extracted geometric and surface descriptors and their procedural and design implications, and organizes the result into a queryable record with an interactive 3D viewer. Its aim is to render the manual observations of Study 1 computable, preparing per-fragment records in a queryable form so that multi-criteria assessment can scale beyond manual curation. Fig. 2 traces the pipeline dataflow, from scan input through parallel geometric and surface characterization to the consolidated fragment record.

The pipeline accepts two scan input types. A colour point cloud (PLY) from LiDAR-based capture, cleaned and downsampled in CloudCompare, provides the geometric descriptors; a photogrammetric textured mesh, prepared in Blender through remeshing, UV unwrapping, and texture rebaking, additionally supports surface classification and its spatial localization. Because a fragment is scanned resting on the ground, its contact face is never captured, and reconstructing a closed mesh manufactures surface where none was observed. This contact region is marked during preparation so that, downstream, planes matching its orientation are flagged as unreliable and the region is masked out of surface classification, keeping observed surface distinct from reconstructed filler.

From the prepared scan, the pipeline extracts two descriptor classes in parallel. Geometric descriptors are computed deterministically: an oriented bounding box gives principal dimensions and volume, with a convexity ratio and an estimated mass; RANSAC segmentation identifies planar regions with their area, orientation, and fit deviation; and multi-scale curvature captures both overall form and fine surface texture. Surface descriptors are obtained from the texture: a vision-language model (GPT-4o in the prototype) classifies surface conditions against a controlled seven-class taxonomy with multi-run majority voting, and an 8×8 grid over the texture localizes each label and reprojects it onto the mesh through a spatial majority vote over surface regions.

The record also carries a layer of procedural, action-oriented knowledge, encoded as design factors that link surface and geometry conditions to their implications for cutting, connection feasibility, stacking stability, and finishing. At this stage this layer is a placeholder that demonstrates the schema's linkage structure, not a validated knowledge base. Its entries are drawn provisionally from the on-site experience of Study 1 and the concrete-reuse and fabrication literature [CITATION NEEDED: key concrete-reuse/fabrication sources for the design factors]; the rules that would derive conclusions such as connection strategy or handling class from the descriptors are specified but not yet executed; and grounding the mappings in verified domain expertise remains future work.

All descriptors, together with registry provenance data such as source-building metadata, are aggregated into a fragment-level JSON record conforming to the schema, each field carrying its computation method and data status, and rendered in an interactive HTML report with a 3D viewer and per-feature spatial overlays. The pipeline is demonstrated on ten real fragment scans from Study 1, confirming technical feasibility of the end-to-end workflow and positioning the instrument as the material audit layer of the broader feature-aware reuse framework [self-reference to the PhD framework; add citation or reword, side note N8].

*[Fig. 2 — Pipeline dataflow: a fragment is digitized as a point cloud or textured mesh and prepared in scan-prep; geometric and surface-condition descriptors are extracted in parallel; outputs are consolidated with encoded domain knowledge and registry data into the fragment record that drives the queryable viewer. Fix figure typo "Querable" and reconsider "Database" vs "Record"; see side note N7.]*
*[Table 1 — descriptor schema excerpt (descriptor, category, method, data status): consider adding from `descriptor_dictionary.md`; side note N9.]*

## 5. Results and Evaluation

### 5.1 Pipeline results

*[PLACEHOLDER — pending processing of the ten fragments. To contain: processing status across the ten real Study 1 fragment scans; the three-tier data status (geometric and surface descriptors computed from real scans; unmeasured attribute values, concrete class and reinforcement, carried as flagged pseudo entries; procedural knowledge provisional). One worked example (FRAG-S1-FS-006): the 8×8 grid resolving to formwork_imprint on the cast top face and exposed_aggregate on the fracture faces, with the unscanned contact cells correctly excluded; and verification that scan-reliability flagging fires on the reconstructed plane. State n and the proof-of-principle scope plainly. See side note N4.]*

### 5.2 Retrospective evaluation against Study 1 decisions

*[FRAMEWORK — results PENDING the validation run; full protocol in `paper_validation_method_draft.md`.]*

The pipeline is assessed by whether its descriptors, queried, recover the assignment and face-use decisions documented in Study 1. Initial selection is out of scope, as the fragments rejected on site were never scanned and provide no candidate pool. Each documented decision is grounded in a contemporaneous project record, encoded as a descriptor query, and frozen before ranking; the pipeline's ranking is then compared with the designer's actual choice. Matches indicate the criterion was captured; divergences indicate either a missing descriptor or knowledge that remains tacit, and each divergence is a finding in its own right.

- **Overall recovery:** [PENDING: X of N documented decisions recovered across the ten fragments.]
- **Aesthetic axis** (surface labels against show-face and feature-reuse decisions): [PENDING result]. Expected strongest, since surface classification is the pipeline's central contribution.
- **Geometric axis** (planarity and orientation against seating, leaning, and connection-face decisions): [PENDING result]. A partial result is anticipated at the resting-pose step: the pipeline reports planar faces and normals in scan coordinates, but the orientation a face presents once the fragment is placed is not yet computed.
- **Mass axis** (mass estimate against handling and stability decisions): [PENDING result].
- **Divergences as findings:** [PENDING: list each divergence and its diagnosis, missing descriptor / wrong value / tacit knowledge.]

This is proof-of-principle within a single project, and the decisions serving as ground truth were made by the same designers who conducted the research; it is first evidence of design relevance, not independent validation.

## 6. Discussion and Outlook

### 6.1 Contribution

The two studies together advance a material-adaptive design approach with reclaimed concrete, moving beyond geometric matching. Study 1, a built public installation, verified the design-to-construction workflow and surfaced its information requirements; Study 2 prototyped the digital infrastructure that moves the characterization of irregular concrete from tacit, one-by-one judgment toward a computable, queryable form.

The contribution is twofold. Conceptually, the work shows that rough, highly variable construction waste can drive the design and construction of a public installation at landscape and urban-furniture scale through a computational workflow, while keeping the process design- and material-driven. Technically, Study 1 verified and adapted 3D scanning, rigid-body simulation, and augmented-reality tools for a design-to-construction project in concrete rubble, revealing the issues specific to this material system, while Study 2 demonstrates the feasibility of combining geometric computation with vision models to characterize irregular fragments semi-automatically into a queryable record, with surface conditions located on the 3D geometry. Practical steps, such as preparing photogrammetry meshes and raw point clouds into clean, computable data and flagging reconstructed surfaces, were addressed and may benefit similar projects. The 3D visualization of located features is a first step toward integrating the enriched records into a design interface, the design-environment integration set as this research's overarching aim.

### 6.2 Design implications

Making these descriptors computable and queryable changes how design with reclaimed concrete can proceed. A designer can interrogate a fragment stock by geometry, surface character, and procedural constraint together, so selection and assignment become reproducible, multi-criteria queries, no longer bound to one person's memory of the pile. Aesthetic and material-history properties, previously accessible only by handling each piece, become searchable, allowing the spolia sensibility of Study 1 to operate at the scale of a demolition stock. Bringing handling and connection constraints into the same query surface lets them shape design decisions at the point those decisions are made. At scale, and kept under tracking within a digital-twin system, this could support the feature-curated assembly of variable elements that traditions such as the Chinese garden achieved by hand (Wang et al., 2024).

### 6.3 Limitations

The evaluation basis is small and single-case (see Section 2.2). Beyond that, three boundaries are intrinsic to the current prototype, and the schema marks each with an explicit data-status flag, so it is reported as a placeholder or an assumption and not as verified data. The procedural design-factor layer is a placeholder that demonstrates the schema's linkage structure and is not a validated knowledge base. The derived rules that would compute connection strategy, handling class, and design assignment are specified but not executed, so those conclusions are proposed, not demonstrated. And the structural attributes that resist scan-based measurement, concrete strength, reinforcement layout and direction, and centre of mass, remain assumptions carried as flagged pseudo entries. The subtype taxonomy is likewise a target design, reported only at the seven-class level that the demonstration supports. The vision-based classification is also not yet benchmarked: its accuracy has been examined on individual worked examples and has not been measured against an annotated reference set. Establishing such a benchmark, particularly for structurally consequential conditions such as exposed reinforcement and cracking, is needed before the AI cataloguing of surface features can be relied upon.

### 6.4 Outlook and future work

Several directions extend the work. Descriptor combinations could inform higher-order and sequential behaviours, such as assembly order and rules where one fragment's placement constrains the next, which a per-fragment record does not yet express. Nearer-term development would close the boundaries above: grounding the procedural knowledge in expert input, executing and benchmarking the derived rules, adding a resting-pose estimate, binding labels to individual faces, and expanding the fragment set. Beyond the demonstrated case, the same pipeline is anticipated for documented and standing stock: applied to an element scheduled for deconstruction, its descriptors could enrich a pre-demolition audit, with the scan-reliability machinery making the partial-coverage scans of standing elements usable.

## 7. Conclusion

This paper has developed a computational basis for characterizing irregular demolition concrete as queryable design data, grounded in a built public commission and demonstrated on real fragment scans. Study 1 established the design potential of feature-rich rubble and the information its reuse requires; Study 2 turned those requirements into a working pipeline that extracts geometric and surface descriptors, locates surface conditions on the 3D geometry, and consolidates them into a per-fragment record.

The contribution is bounded honestly by three limits intrinsic to the current prototype, each marked in the schema with an explicit data-status flag. First, the procedural design-factor layer is a placeholder that demonstrates the schema's linkage structure and is not a validated knowledge base. Second, the rules that would derive connection strategy, handling class, and design assignment from the descriptors are specified but not yet executed, so those conclusions are proposed. Third, the structural attributes that resist scan-based measurement, namely concrete strength, reinforcement layout and direction, and centre of mass, remain assumptions carried as flagged pseudo entries. Within these bounds, the work provides the schema and the instrument on which design-stage integration can build, and points toward a material-adaptive design environment for reclaimed concrete and toward enriching the pre-demolition audit of standing structures.

## References

*[Compiled from the section drafts. Verify all flagged entries before submission. IASS self-citation to be inserted throughout where marked.]*

Ashby, M., & Johnson, K. (2002). *Materials and Design: The Art and Science of Material Selection in Product Design*. Butterworth-Heinemann.

Bertola, N., Küpfer, C., Bastien-Masse, M., & Fivet, C. (2025). Design, construction and assessment of FLO:RE: The prototype of a low-carbon building floor made of reused concrete elements and steel profiles. *Architecture, Structures and Construction*. https://doi.org/10.1007/s44150-025-00138-2

Blum, C., Marsillo, L., & Muñoz Guerrero, G. (2025). Reclaimed Design: Development of an Availability-Oriented Framework for Reclaimed Lumber. *ACADIA 2025: Computing for Resilience*, 2.

Brütting, J., Vandervaeren, C., Senatore, G., De Temmerman, N., & Fivet, C. (2020). Environmental impact minimization of reticular structures made of reused and new elements through life cycle assessment and mixed-integer linear programming. *Energy and Buildings*, 215, 109827. https://doi.org/10.1016/j.enbuild.2020.109827 [VERIFY journal/volume]

Certain Measures (Nolte, T., & Witt, A.). (2016). *Mine the Scrap* [project]. https://www.certainmeasures.com/projects/mine-the-scrap [FIND citable form]

Cousin, T., Marshall, D., Pearl, N., Alkhayat, L., & Mueller, C. (2023). Integrating irregular inventories: Accessible technologies to design and build with nonstandard materials in architecture. *Journal of Physics: Conference Series*, 2600, 192004. https://doi.org/10.1088/1742-6596/2600/19/192004

Dorafshan, S., Thomas, R. J., & Maguire, M. (2018). Comparison of deep convolutional neural networks and edge detectors for image-based crack detection in concrete. *Construction and Building Materials*, 186, 1031–1045. https://doi.org/10.1016/j.conbuildmat.2018.08.011

Elshani, D., Dervishaj, A., Hernández, D., Gudmundsson, K., Staab, S., & Wortmann, T. (2024). An Ontology for the Reuse and Tracking of Prefabricated Building Components. [complete proceedings details or drop]

Elshani, D., Lombardi, A., Hernandez, D., Staab, S., Fisher, A., & Wortmann, T. (2025). AEC Co-design workflow for cross-domain querying and reasoning using Semantic Web Technologies. *Automation in Construction*, 176. https://doi.org/10.1016/j.autcon.2025.106226

Eschenbach, M. B., Wagner, A.-K., Ledderose, L., Böhret, T., Wohlfeld, D., Gille-Sepehri, M., Kuhn, C., Kloft, H., & Tessmann, O. (2023). Matter as Met: Towards a Computational Workflow for Architectural Design with Reused Concrete Components. In *Towards Radical Regeneration* (pp. 442–455). Springer. https://doi.org/10.1007/978-3-031-13249-0_35

European Commission. (2023). *A Green Deal Industrial Plan for the Net-Zero Age*. https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A52023DC0062

European Environment Agency. (2020). *Construction and Demolition Waste: Challenges and Opportunities in a Circular Economy*. EEA Report. [VERIFY 800 Mt figure]

Frayling, C. (1993). Research in Art and Design. *Royal College of Art Research Papers*, 1(1). [VERIFY vol/issue]

Grangeot, M., Wang, Q., Beyer, K., Fivet, C., & Parascho, S. (2024). Structural Concrete Rubble Arrangements. In P. Eversmann, C. Gengnagel, J. Lienhard, M. Ramsgaard Thomsen, & J. Wurm (Eds.), *Scalable Disruptors* (pp. 15–27). Springer.

Honic, M., Kovacic, I., & Rechberger, H. (2021). Improving the recycling potential of buildings through Material Passports (MP): An Austrian case study. *Journal of Cleaner Production*, 279, 123536. https://doi.org/10.1016/j.jclepro.2020.123536

Itten, J. (1975). *Design and Form: The Basic Course at the Bauhaus and Later* (Rev. ed.). Van Nostrand Reinhold. [VERIFY edition/year]

Küpfer, C., Bastien-Masse, M., Grangeot, M., Meier, C., Graulich, L., Pathé, J., & Fivet, C. (2024). From soon-to-be demolished mushroom column slabs to reused reinforced concrete saw-cut assemblies: The case of the rebuiLT pavilion. *IOP Conference Series: Earth and Environmental Science*, 1363, 012052. https://doi.org/10.1088/1755-1315/1363/1/012052

Lu, C.-L., Zhu, Z., Perutxet Olesti, G., Scully, P., & Devadass, P. (2026). Computational design and robotic fabrication of dry-stacked non-standard spanning limestone assemblies. *Construction Robotics*, 10, 6. https://doi.org/10.1007/s41693-026-00180-6

Luo, J., Zadeh, P., & Staub-French, S. (2024). Ontology-Based Design Features for Representing Constructability in Architectural Design: Toward BIM in Off-Site Construction. *Journal of Construction Engineering and Management*, 150(10), 05024010. https://doi.org/10.1061/JCEMD4.COENG-14764

Moholy-Nagy, L. (1938). *The New Vision: Fundamentals of Design, Painting, Sculpture, Architecture*. W. W. Norton. [VERIFY edition]

Niklaus, M., Koch, C., König, M., & Teizer, J. (2023). BIM- and machine-learning-based visual site monitoring using 360-degree images. *Journal of Construction Engineering and Management*, 149(5). https://doi.org/10.1061/JCEMD4.COENG-12934

Önalan, B., et al. (2025). Deep Neural Network-Based Design Exploration with Concrete Cutting Waste. *Technology|Architecture + Design*. https://doi.org/10.1080/24751448.2025.2534788 [COMPLETE author list]

OpenAI. (2024). GPT-4 Technical Report. *arXiv*, 2303.08774. https://doi.org/10.48550/arXiv.2303.08774

Oreb, J., Curić, H., Tomić, I., & Beyer, K. (2024). Masonry walls from reclaimed concrete demolition waste. *MATEC Web of Conferences*, 403, 06004. https://doi.org/10.1051/matecconf/202440306004

Rossi, G., Marsillo, L., Akbar, Z., Tamke, M., Wortmann, T., & Ramsgaard Thomsen, M. (2026). Towards an integrated Semantic-based Resource-driven modelling framework for design to fabrication of bio-based and waste-source materials in AEC using knowledge graph. *GNI Symposium on Artificial Intelligence for the Built World*, TU Munich.

Wang, Z., Song, P., Zhang, Q., Wei, T., & Pan, B. (2024). Digital improvements in the design and construction process of classical Chinese garden rockeries: A study based on material digitization. *Heritage Science*, 12, 327. https://doi.org/10.1186/s40494-024-01445-5

Widmer, N., Bastien-Masse, M., & Fivet, C. (2023). Building structures made of reused cut reinforced concrete slabs and walls: A case study. In F. Biondini & D. M. Frangopol (Eds.), *Life-Cycle of Structures and Infrastructure Systems*. CRC Press. https://doi.org/10.1201/9781003323020-18

Wiedenhofer, D., Steinberger, J. K., Eisenmenger, N., & Haas, W. (2015). Maintenance and expansion: Modeling material stocks and flows for residential buildings and transportation networks in the EU25. *Journal of Industrial Ecology*, 19(4), 538–551. https://doi.org/10.1111/jiec.12216

**Citations still to add:** IASS 2026 self-citation (Yan, Rutzinger & Schinegger, "Rubble Reimagined", Proc. IASS-IWSS 2026) — used throughout as [Study 1 / IASS]; KG-audit source (¶2 intro); Watts Towers scholarly source; Wang Shu / Amateur Architecture Studio / wa pan source; concrete-reuse/fabrication sources grounding the design-factor layer (§4).

---

# Revision Notes (side notes)

## A. Structure and logic flow

- **N1 — Title.** Not yet set. Working options: (1) "From 3D Scan to Queryable Design Data: Computational Characterization of Irregular Concrete Fragments"; (2) "Material Traces as Design Data: Characterizing Demolition Concrete for Material-Adaptive Design"; (3) "Beyond Geometric Matching: Linking Surface, Shape, and Procedure for Concrete Reuse." Section 4 heading now uses "Characterization" (not "Descriptor Extraction"); keep the title consistent with that.
- **N2 — Evaluation moved out of Discussion.** In the section drafts, the evaluation framework sat inside Discussion. In this compile it is placed in Section 5 (Results and Evaluation), which is the correct home; Discussion now interprets rather than presents it. Confirm you want this structure. It also removes the earlier Discussion/Validation overlap.
- **N3 — Methodology placement.** Methodology is folded under Section 2 with Objectives. Fine for a short paper. If the venue expects a standalone Methods section, split 2.2 out as Section 3 and renumber.
- **N4 — Results (5.1) is a placeholder.** Needs the ten fragments processed. Keep the three-tier data-status statement here (it was moved out of the objectives); it is the reviewers' "real data" answer. State n and proof-of-principle scope plainly.
- **N5 — Evaluation (5.2) is a framework with [PENDING] placeholders.** Depends on `study1_decisions.md` being reconstructed and the fragments processed. This is the reviewers' key ask; highest-priority content still missing.

## B. Over-repetition to reduce

- **N6a — The tacit-to-computable thesis recurs five times** (intro ¶4, Methodology, Study 1 §3 para 2, Discussion 6.1, Conclusion). It is the paper's spine, so some recurrence is expected, but five near-identical statements is heavy. Keep it sharp in the Methodology (where it is argued) and the Conclusion (final word); soften the echoes in 6.1 Contribution and the Study 1 recap.
- **N6b — "Material-adaptive design / beyond geometric matching"** appears in the Objectives aim, Discussion 6.1, and Conclusion. Contribution (6.1) restates the intro's positioning most directly; trim it there.
- **N6c — "Design-environment integration as overarching aim"** recurs in the Objectives aim, 6.1, 6.4, and Conclusion (four times). Keep in the aim (where defined) and 6.4 (where developed); the mentions in 6.1 and Conclusion can be lighter.
- **N6d — The three-tier data honesty / three boundaries** appears in §4 (design-factor para + aggregation), §5.1 (planned), 6.3 Limitations, and Conclusion. Intentional, but 6.3 and the Conclusion state the three boundaries in nearly the same words. Compress 6.3 and let the Conclusion carry the final honest-scope statement, or vice versa.
- **N6e — Spolia** appears in intro ¶4, Study 1 §3 para 2, and Discussion 6.2 ("spolia sensibility"). Acceptable, but three is the ceiling; do not add more.
- **N6f — Study 1 workflow** is sketched in intro ¶4 and delivered in §3 para 1. Standard preview/deliver; if trimming for length, thin the intro ¶4 workflow mention since §3 owns it.

## C. Language and style consistency

- **N7 — Spelling convention is mixed.** The draft uses UK forms (colour, behaviour, catalogue, cataloguing) alongside -ize/-ization forms (characterization, standardization, localizes, organizes, industrialized). This is internally consistent only under Oxford British spelling (-ize is valid there). Decide and state one convention; if Oxford British, confirm colour/behaviour/catalogue are intended and that no US -ize word slips to -ise or vice versa. EKA (Estonian venue) likely accepts British; check the template.
- **N8 — Voice inconsistency ("we" vs impersonal).** "We" appears in Section 3 (Study 1 recap: "we identified", "By reviewing... we identified") and Section 5.2, while most sections are impersonal ("the pipeline", "the study", "the research adopts"). Pick one voice for the whole paper. "We" is acceptable in practice-led design research but must be applied consistently.
- **N9 — Terminology to keep fixed:** "descriptors" for extracted values; "design factors" only for the procedural linkage layer; "registry data" for provenance/source metadata; "record" (not "database") for the demonstrated output. The Fig. 2 box still says "Database"; align it to "Record."
- **N10 — Number/format consistency:** "ten fragments" (spelled) is used; keep spelled numbers under ten-and-round consistent. "8×8" now uses the multiplication sign; ensure the figure and text match. "3D" throughout (not "three-dimensional").

## D. Figures and tables

- **N7 (fig) — Fig. 1** is adapted from the IASS workflow diagram. Confirm EKA self-plagiarism/figure-reuse policy; the redrawn workflow-plus-requirements version is the safer choice. Verify the per-stage requirement dots against IASS Table 2, and confirm the gap count (the "~thirteen" question) against the final IASS paper.
- **N7 (fig) — Fig. 2** pipeline diagram: fix the "Querable" typo to "Queryable"; change "Database" to "Record"; and resolve the point-cloud-to-classification path (the figure routes cleaned point cloud → rendered images → feature classification, but the text says the point cloud provides geometry and the mesh additionally supports classification; confirm whether rendered-image classification is implemented or planned, then align text and figure).
- **N9 (table) — Descriptor schema excerpt (Table 1).** Consider adding a compact table (descriptor, category, method, data status) from `descriptor_dictionary.md`. It substantiates §4 and gives the reader the schema at a glance. Verify "surface roughness" is represented as curvature-derived, not a separate computed descriptor.

## E. Citations to resolve (inline markers above)

- **IASS 2026 self-citation** — the single most-used missing reference; appears as [Study 1 / IASS] in the intro, Methodology, and Study 1 recap.
- **KG-audit source** (intro ¶2) — still not located; if not found, reword to "emerging work" and drop the bracket.
- **Watts Towers** and **Wang Shu / wa pan** (intro ¶2) — named works, add scholarly sources if the venue expects them.
- **Concrete-reuse/fabrication sources** grounding the §4 design-factor layer — currently unattributed ("the concrete-reuse and fabrication literature").
- **"Material audit layer of the broader feature-aware reuse framework"** (§4 end) — this is a forward reference to the PhD framework; either cite it or reword so it does not read as an unexplained proper noun (side note N8-fig relates).
- **Reference verifications:** Brütting (journal/volume), Önalan (author list), Frayling (vol/issue), Itten and Moholy-Nagy (editions), EEA (800 Mt figure). Knippers (2021) is not cited in the compiled text and has been left out of the reference list; confirm.
- **Novelty check:** two digital-ecosystem papers (10.1002/best.70129; 10.1002/bate.202500021) should be read before submission to confirm the "no existing pipeline" claim in intro ¶3 survives (expected: yes, scoped to irregular fragments + scan/vision input).

## F. Content accuracy to confirm before submission

- **Gap count** in §3 ("thirteen" in the source drafts; not stated numerically in this compile) versus HANDOVER's "11" — reconcile against the final IASS paper.
- **"~twenty fragments" (collected, §3) vs "ten" (processed, §4/§5)** — both correct, keep distinct.
- **Multi-run majority voting** and the **8×8 grid** are verified against the code; the **spatial-vote reprojection** wording in §4 now matches the implementation (not a naive UV lookup).
- **Point-cloud path capability** — the one open code-vs-text question (see N7 fig).
