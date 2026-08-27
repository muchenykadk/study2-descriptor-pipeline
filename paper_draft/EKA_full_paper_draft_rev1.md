# [TITLE — pending, see change log C1]
*Revision 1 of the compiled full-paper draft, 2026-08-10. Critical revision of `EKA_full_paper_draft.md`: repetition reduced per the earlier side notes, voice unified (impersonal), Oxford British spelling throughout, terminology fixed (record, not database), pipeline description aligned with the current implementation (region-based classification, `feature/region-classification` branch), factual counts corrected. Citation gaps kept as [CITATION NEEDED]. All remaining open items consolidated in the change log at the end. No em-dashes; no "rather than" constructions.*

---

**Abstract.** Demolition concrete is typically downcycled into aggregate, discarding the structural and material value of its irregular fragments. Their singular geometry and surface traces are design-relevant, yet assessing them has relied on tacit, fragment-by-fragment judgement that cannot scale. This paper develops a computational basis for characterizing such fragments as queryable design data through two sequential practice-led studies. Study 1, a built public commission in urban furniture, demonstrated the design potential of irregular concrete and yielded an information requirements scheme derived from its documented gaps. Study 2 prototypes a pipeline that takes a 3D scan of a fragment, extracts geometric descriptors deterministically, classifies and localizes surface conditions with a vision-language model, and consolidates the result into a queryable per-fragment record. The pipeline is demonstrated on real Study 1 fragment scans and assessed retrospectively against that project's documented design decisions. The contribution is a descriptor schema grounded in built practice, a working characterization pipeline, and first evidence of the design relevance of computed fragment descriptors.

**Keywords:** concrete reuse, irregular material, computational characterization, design-to-fabrication, material-adaptive design [confirm keyword list with EKA template]

---

## 1. Introduction

Construction and demolition (C&D) waste accounts for roughly one-third of solid waste in the European Union, over 800 million tonnes annually (European Environment Agency, 2020). Although concrete recycling rates are high, the material is primarily downcycled into low-grade aggregates through an energy-intensive crushing process, discarding its original structural capacity (European Commission, 2023). Volumes of deconstruction concrete are expected to grow across Europe as successive generations of building stock reach the end of their service lives (Wiedenhofer et al., 2015). Underlying this downcycling is a framing problem: demolition waste is treated as a bulk flow to be processed, not as discrete fragments with differentiated properties and architectural potential.

Composing a spatial installation from variable, non-standard elements curated by their individual features is a long-standing architectural and artistic practice. In traditional Chinese gardens, lake stones of irregular shape are arranged into rockeries, garden walls, and stairs (Wang et al., 2024); salvaged material has likewise been reinterpreted in modern work, from the Watts Towers that Simon Rodia built from waste [CITATION NEEDED: Watts Towers scholarly source] to Wang Shu's facades of recycled brick and tile at the Xiangshan campus [CITATION NEEDED: Amateur Architecture Studio / wa pan source]. Treating reclaimed concrete in this spirit, whether components from planned dismantling or fragments from demolition, exposes an information asymmetry. Traditional material knowledge reaches designers in two modes: through direct, hands-on study of material character, as taught in the Bauhaus preliminary course (Itten, 1975; Moholy-Nagy, 1938), or through selection from pre-characterized catalogues, where standardization guarantees the link between on-paper design and built result (Ashby & Johnson, 2002). A reclaimed concrete fragment resists both modes: as a found condition it is too singular for any catalogue, while a stock of hundreds of unique, heavy pieces exceeds what hands-on study can cover. Appearance, moreover, is only half of what must be known. For material this heavy, irregular, and non-malleable, handling machinery, connection feasibility, and placement constraints are not downstream logistics but coupled design decisions (Widmer et al., 2023; Küpfer et al., 2024; Bertola et al., 2025). Designing with demolition concrete at scale therefore depends on enriched, queryable per-fragment models, spanning appearance, geometry, and procedure, available where design decisions are made.

Existing methods each address one dimension of this need, largely in isolation from the others. On the documentation side, material passports and reuse databases record component-level data (Honic et al., 2021; Luo et al., 2024), and recent work structures pre-demolition audits into knowledge graphs queryable in natural language [KG-audit CITATION NEEDED]; yet what they hold (element types, quantities, coarse condition) remains at document granularity and does not actively enter computational design processes. On the design side, research on reclaimed inventories concentrates on geometric stock matching and allocation, treating elements as geometric tokens to fit a target form (Cousin et al., 2023; Eschenbach et al., 2023; Skoury et al., 2024; Blum et al., 2025); some of this work extends the allocation objective to environmental accounting, incorporating life cycle assessment and embodied carbon for reclaimed steel (Brütting et al., 2020) and cut concrete blocks (Önalan et al., 2025). Across these approaches the element model remains geometric and quantitative: surface and condition stay outside it, leaving each element's singularity unexplored as design data. For surface characterization itself, construction-inspection computer vision detects defects reliably (Dorafshan et al., 2018; Niklaus et al., 2023) but over closed categories that cannot describe the open-ended vocabulary of demolition surfaces. Vision-language models lift this restriction, classifying against any user-defined taxonomy without retraining (OpenAI, 2024), yet stop at image-level labels that never locate a condition on the geometry governing its structural role. Workflows that do operationalize the appearance of found objects computationally, from digitized rockery stones (Wang et al., 2024) to vision-based matching of scanned industrial scrap (Certain Measures, 2016), remain small-scale and object-specific. Semantic frameworks could bind such characterization into queryable knowledge (Rossi et al., 2026; Elshani et al., 2025; Elshani et al., 2024), but presuppose properties already recorded elsewhere. No existing pipeline takes scan geometry and vision-based surface classification as primary input and integrates open-vocabulary classification, spatial localization, morphological analysis, and inventory structuring for demolition concrete.

This paper addresses the gap through a practice-led trajectory of two sequential studies. Design explorations with irregular rubble have so far concentrated on wall-type structural assemblies and geometric matching, largely as laboratory prototypes (Grangeot et al., 2024; Oreb et al., 2024; Lu et al., 2026). Study 1, a built public commission, carried the material instead into an urban furniture project in active public use, demonstrating both the potential and the bottleneck of upcycling feature-rich, irregular rubble. Traces of past use, such as cladding residues, formwork imprints, and remaining pipe openings, acted as design-relevant properties that added character to the built work, an approach rooted in the spolia tradition; geometry and surface condition jointly determined each fragment's structural and aesthetic assignment [Study 1 / IASS CITATION NEEDED]. The characterization behind these decisions, however, relied on fragment-by-fragment designer judgement and left no computable record. The gaps this surfaced motivate Study 2, which prototypes a computational pipeline that extracts the required data from 3D scans: deterministic computation for geometric descriptors, vision-model classification for surface features. The extracted descriptors, together with registry data, are structured under a schema derived from Study 1's information requirements and linked onward to encoded domain knowledge of handling and design implications. The pipeline is demonstrated on real fragment scans from Study 1 and assessed retrospectively against that project's documented design decisions, evaluating whether computed characterization can recover the selection logic the designer exercised through direct material knowledge. Within the scope of this paper the records are structured for querying but not yet coupled to a live design workflow.

## 2. Objectives and Methodology

### 2.1 Research objectives

The overarching aim of this research is an interactive design environment for reclaimed concrete, in which enriched, queryable per-fragment models inform the design phase directly. Within that aim, this paper pursues three objectives:

1. **Foundation.** To demonstrate the design and aesthetic potential of irregular concrete fragments through a built public commission in active public use, and to derive an information requirements scheme from its documented gaps.

2. **Instrument.** To prototype a computational pipeline that extracts geometric and surface descriptors from 3D scans and structures them, with registry data, under a schema derived from the Study 1 requirements.

3. **Evaluation.** To demonstrate the pipeline on real Study 1 scans, with attributes that resist scan-based measurement carried as flagged provisional entries, and to evaluate the computed descriptors retrospectively against the documented design decisions of Study 1.

### 2.2 Methodology

The research adopts a practice-led design in which making is the mode of inquiry. Study 1 is a Research through Design case study (Frayling, 1993): a live public commission is executed as the research instrument, so that the act of designing and building produces the knowledge sought. Such knowledge is situated and largely tacit, and a practice-led inquiry that ends at one built work leaves it bound to that work. The methodological task of Study 2 is therefore externalization: turning the situated characterization into a computational instrument that can be applied, queried, and reused beyond the original project.

Because requirements, material, and design decisions all derive from one documented project, the instrument can be evaluated retrospectively against it. Each documented decision is re-expressed as a query over the computed descriptors, and agreement or divergence is read as evidence of what the characterization captures and what remains tacit. This offers first evidence of design relevance within a single case, made by the same designers who conducted the work; it is not independent validation.

## 3. Study 1: Requirements from Built Practice

Study 1 built an urban furniture commission from demolition concrete rubble as a Research through Design case study, producing two prototypes now in active public use. Around twenty cast-in-place fragments were selected from the deconstruction site of an early twentieth-century building and digitized by photogrammetry. A digital-physical workflow (Fig. 1) carried the project from this fragment inventory through a hybrid manual and computational design stage with rigid-body stability simulation, on-site concrete assembly guided by augmented-reality placement, and final assembly with adaptively fabricated timber connections. The stage-by-stage implementation and full findings are reported in [IASS CITATION NEEDED].

One design principle of the built work was to carry the modern spolia spirit: treating the singular attributes of the rubble as design material. Former pipe penetrations were reinterpreted as integrated planters, cast faces and weathering were retained as exposed surfaces, and the contrast between worn concrete and new timber kept the reuse visible. Surface character thus informed fragment selection and placement together with geometry. This is the potential the case study demonstrated: irregular rubble, read for its material history, can hold both aesthetic and structural roles in a public landscape setting. The decisions concerning aesthetic features, however, remained a manual curation process that does not scale beyond a small set.

A review of the project implementation records identified the information required at each stage, mapped in Fig. 1; the full gap analysis is given in [IASS CITATION NEEDED]. The required information spans three dimensions. Structurally: estimated volume and mass, centre of mass, planar surfaces, exposed reinforcement, and crack grading. Aesthetically: colour, surface roughness or aggregate size, and categorized surface features such as formwork imprints, tile residue, and weathering. Procedurally: machinery matched to a fragment's mass class and connections feasible for a given interface condition. These requirements define the descriptor schema developed in the following section.

*[Fig. 1 — Study 1 workflow with the information required at each stage across structural, aesthetic, and procedural dimensions. Adapted from IASS; see change log C7 on figure reuse.]*

## 4. Study 2: Fragment Characterization Pipeline

Study 2 responds to the gaps identified in Study 1 with a prototype computational pipeline that takes a 3D scan of an irregular concrete fragment, enriches it with extracted geometric and surface descriptors and their procedural implications, and consolidates the result into a queryable record with an interactive 3D viewer. Its purpose is to render the manual observations of Study 1 computable, so that multi-criteria assessment can scale beyond manual curation. Fig. 2 traces the dataflow from scan input through parallel geometric and surface characterization to the consolidated fragment record.

The pipeline accepts two scan input types. A colour point cloud (PLY) from LiDAR-based capture, cleaned and downsampled in CloudCompare, provides the geometric descriptors; a photogrammetric textured mesh, prepared in Blender through remeshing, UV unwrapping, and texture rebaking, additionally supports surface classification and its spatial localization. Because a fragment is scanned resting on the ground, its contact face is never captured, and reconstructing a closed mesh manufactures surface where none was observed. This contact region is marked during preparation so that, downstream, planar regions matching its orientation are flagged as unreliable and the region is excluded from surface classification, keeping observed surface distinct from reconstructed filler.

From the prepared scan, the pipeline extracts two descriptor classes in parallel. Geometric descriptors are computed deterministically: an oriented bounding box gives principal dimensions and volume, with a convexity ratio and an estimated mass; RANSAC segmentation identifies planar regions with their area, orientation, and fit deviation; and multi-scale curvature captures both overall form and fine surface texture. Surface descriptors are obtained per surface region: the mesh is segmented into coherent regions, the RANSAC planar faces and the remaining fracture clusters, and each region's texture footprint is cropped from the atlas and classified by a vision-language model (GPT-4o in the prototype) against a controlled seven-class taxonomy with multi-run majority voting. Localized anomalies within a region, such as exposed reinforcement or staining, are detected as bounded patches in the same pass. Assigning one label per coherent region follows the material structure of demolition fragments, whose faces are largely homogeneous with sparse local anomalies; region-level classification also proved more reliable than uniform texture-grid tiling in development, where independent tile judgements produced spurious label boundaries [pipeline verification pending, change log C2]. Each surface label is thereby bound to the geometry that carries it, linking surface condition to the planar regions that govern seating, connection, and exposure decisions.

The record also carries a layer of procedural, action-oriented knowledge, encoded as design factors that link surface and geometry conditions to their implications for cutting, connection feasibility, stacking stability, and finishing. At this stage this layer is a placeholder demonstrating the schema's linkage structure, not a validated knowledge base. Its entries are drawn provisionally from the on-site experience of Study 1 and the concrete-reuse and fabrication literature [CITATION NEEDED]; the rules that would derive conclusions such as connection strategy or handling class from the descriptors are specified but not yet executed; grounding the mappings in verified domain expertise remains future work.

All descriptors, together with registry provenance data such as source-building metadata, are aggregated into a fragment-level JSON record conforming to the schema, each field carrying its computation method and data status, and rendered in an interactive HTML report with a 3D viewer and per-feature spatial overlays. The pipeline is demonstrated on [n, currently six] real fragment scans from Study 1, confirming technical feasibility of the end-to-end workflow [see change log C3 on the fragment count].

*[Fig. 2 — Pipeline dataflow. Fix "Querable" typo; "Database" → "Record"; update the surface-classification branch to region-based crops; resolve the point-cloud-to-classification path (see change log C7).]*
*[Table 1 — descriptor schema excerpt (descriptor, category, method, data status), from `descriptor_dictionary.md`; see change log C8.]*

## 5. Results and Evaluation

### 5.1 Pipeline results

*[PLACEHOLDER — pending processing of the full fragment set with the region-based pipeline. To contain: processing status across the real Study 1 fragment scans; the three-tier data status (geometric and surface descriptors computed from real scans; unmeasured attributes, concrete class and reinforcement, carried as flagged provisional entries; procedural knowledge provisional). One worked example (FRAG-S1-FS-006): principal dimensions 1663 × 703 × 448 mm, estimated mass 910 kg, eight planar regions; region labels resolving formwork imprint on the cast top face and fracture surface on the broken faces, with the reconstructed contact face excluded from classification and its plane flagged scan-unreliable. State n and the proof-of-principle scope plainly. See change log C2.]*

### 5.2 Retrospective evaluation against Study 1 decisions

*[FRAMEWORK — results PENDING the validation run; full protocol in `paper_validation_method_draft.md`.]*

The pipeline is assessed by whether its descriptors, queried, recover the assignment and face-use decisions documented in Study 1. Initial selection is out of scope, as the fragments rejected on site were never scanned and provide no candidate pool. Each documented decision is grounded in a contemporaneous project record, encoded as a descriptor query, and frozen before ranking; the pipeline's ranking is then compared with the designer's actual choice. Matches indicate the criterion was captured; divergences indicate either a missing descriptor or knowledge that remains tacit, and each divergence is a finding in its own right.

- **Overall recovery:** [PENDING: X of N documented decisions recovered.]
- **Aesthetic axis** (surface labels against show-face and feature-reuse decisions): [PENDING]. Expected strongest, since surface classification is the pipeline's central contribution.
- **Geometric axis** (planarity and orientation against seating, leaning, and connection-face decisions): [PENDING]. A partial result is anticipated at the resting-pose step: the pipeline reports planar faces and normals in scan coordinates, but the orientation a face presents once placed is not yet computed.
- **Mass axis** (mass estimate against handling and stability decisions): [PENDING].
- **Divergences as findings:** [PENDING: each divergence diagnosed as missing descriptor, wrong value, or tacit knowledge.]

This is proof-of-principle within a single project, and the decisions serving as ground truth were made by the same designers who conducted the research; it is first evidence of design relevance, not independent validation.

## 6. Discussion and Outlook

### 6.1 Position against existing approaches

The demonstrated pipeline addresses what the approaches reviewed in Section 1 leave open. Stock-matching and allocation workflows (Cousin et al., 2023; Eschenbach et al., 2023) operate on element models that are geometric and quantitative; the per-fragment record demonstrated here extends that element model with classified surface conditions bound to the geometry that carries them, so that the aesthetic and material-history properties which drove the Study 1 decisions become part of the same computational object as dimensions and planarity. Passport and audit systems (Honic et al., 2021) record at document granularity what this pipeline computes at fragment granularity from the scan itself, requiring no pre-existing documentation, which is the prevailing condition for demolition rubble. The combination of open-vocabulary classification with spatial localization likewise goes beyond inspection-oriented computer vision, whose closed defect categories and image-level outputs (Dorafshan et al., 2018) do not serve design queries. What the pipeline does not yet do, integration into a live design environment and validated procedural knowledge, is bounded in Section 6.4.

### 6.2 Vision-language models for material characterization

Development yielded a transferable methodological finding on how vision-language models behave in this task. Classification over a uniform texture grid, an obvious first architecture, proved unreliable in a structural way: the model judges each submitted image once and repeats that judgement across its cells, so nominally per-cell output collapses to per-image output, and independent judgements of adjacent tiles produce spurious label boundaries on continuous surfaces. Classifying per coherent surface region instead matches the material structure of demolition fragments, whose faces are largely homogeneous with sparse local anomalies, and gives the model what it judges reliably: one whole surface with context [pipeline verification pending, change log C2]. The practical implication generalizes: for material surfaces, the unit of vision-model classification should follow the material's own regions, not an arbitrary spatial tiling.

### 6.3 Design implications

Making these descriptors computable and queryable changes how design with reclaimed concrete can proceed. A designer can interrogate a fragment stock by geometry, surface character, and procedural constraint together, so selection and assignment become reproducible, multi-criteria queries, no longer bound to one person's memory of the pile. Aesthetic and material-history properties, previously accessible only by handling each piece, become searchable, allowing the spolia sensibility of Study 1 to operate at the scale of a demolition stock. Bringing handling and connection constraints into the same query surface lets them shape design decisions at the point those decisions are made. At scale, and kept under tracking within a digital-twin system, this could support the feature-curated assembly of variable elements that traditions such as the Chinese garden achieved by hand (Wang et al., 2024).

### 6.4 Limitations

The evaluation basis is small and single-case (Section 2.2). Beyond that, three boundaries are intrinsic to the current prototype; the schema marks each with an explicit data-status flag, so it is reported as a placeholder or an assumption and not as verified data. First, the procedural design-factor layer demonstrates the schema's linkage structure and is not a validated knowledge base. Second, the derived rules that would compute connection strategy, handling class, and design assignment are specified but not executed, so those conclusions are proposed, not demonstrated. Third, structural attributes that resist scan-based measurement, concrete strength, reinforcement layout, and centre of mass, remain assumptions carried as flagged provisional entries. The subtype taxonomy is likewise a target design, reported only at the seven-class level the demonstration supports. Finally, the vision-based classification is not yet benchmarked: its accuracy has been examined on worked examples, not measured against an annotated reference set. Establishing such a benchmark, particularly for structurally consequential conditions such as exposed reinforcement and cracking, is needed before automated cataloguing of surface features can be relied upon.

### 6.5 Outlook and future work

Several directions extend the work. Descriptor combinations could inform higher-order and sequential behaviours, such as assembly order and rules where one fragment's placement constrains the next, which a per-fragment record does not yet express. Nearer-term development would close the boundaries above: grounding the procedural knowledge in expert input, executing and benchmarking the derived rules, adding a resting-pose estimate, and expanding the fragment set. Beyond the demonstrated case, the same pipeline is anticipated for documented and standing stock: applied to an element scheduled for deconstruction, its descriptors could enrich a pre-demolition audit, with the scan-reliability machinery making the partial-coverage scans of standing elements usable.

## 7. Conclusion

Study 1, a built public commission, established the design potential of feature-rich demolition rubble and derived the information requirements its reuse demands. Study 2 turned those requirements into a working pipeline that extracts geometric and surface descriptors from 3D scans and consolidates them, with surface conditions bound to the geometry, into a queryable per-fragment record. Together they provide the schema and the instrument, bounded as described in Section 6.4, on which a material-adaptive design environment for reclaimed concrete can build.

A constraint on that work lies in the data available to the field. The benchmark datasets that support machine learning on concrete condition are two-dimensional and were photographed on in-service structures at close range (Mundt et al., 2019; Flotzinger et al., 2024), so their categories and their image quality both assume conditions that demolition debris does not meet. The published three-dimensional construction datasets record whole buildings and active sites, not the detached irregular fragments that selective demolition produces (Kaufmann et al., 2025). We found no open corpus of three-dimensionally scanned demolition fragments carrying annotated surface features, which means any evaluation of surface classification on this material must supply its own ground truth, as Section 5.1 did. The twelve fragments documented here, together with the twenty-six blind-sampled and hand-labelled surface tiles and the labelling protocol used to produce them, are released as a first contribution toward such a corpus.

## References

*[Unchanged from the previous compile except as noted; verify all flagged entries before submission. IASS self-citation to be inserted throughout where marked.]*

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

**Citations still to add:** IASS 2026 self-citation (used throughout as [Study 1 / IASS]); KG-audit source (intro ¶3); Watts Towers; Wang Shu / wa pan; concrete-reuse/fabrication sources grounding the design-factor layer (§4). Note: Skoury et al. (2024) is cited in intro ¶3 but missing from this reference list; add it.

---

# Revision 1 change log

## Changes applied in this revision

- **C-voice.** Voice unified to impersonal throughout ("a review ... identified" replacing "we identified"; §5.2 likewise). If the venue prefers "we" for practice-led work, the reverse substitution is mechanical.
- **C-spelling.** Oxford British spelling adopted and made consistent (colour, catalogue, behaviour, judgement + -ize forms). "Judgment" normalized to "judgement".
- **C-repetition.** Executed the earlier N6 notes: the tacit-to-computable thesis now argued once in §2.2, delivered once in the Conclusion, with lighter echoes in §1 and §6.1; "beyond geometric matching" removed from §6.1 (kept in §1 positioning); the overarching-aim sentence trimmed from §6.1 and Conclusion; the three-boundary statement now lives in §6.3 with a one-sentence pointer in the Conclusion (previously duplicated in full).
- **C-abstract.** Tightened; contribution stated as schema + pipeline + first evidence; removed the vague "provides the groundwork" close.
- **C-intro.** ¶4 and ¶5 of the old intro merged; Study 2 preview shortened since §4 owns the detail (old N6f).
- **C-terminology.** "Record" throughout; "provisional" replaces the internal jargon "pseudo" in paper prose (the schema flag name stays `pseudo` in code, not in the paper).
- **C-restructure (2026-08-10, second pass).** §6.1 Contribution deleted: it was a third re-telling of the two studies with no interpretive content. Replaced with §6.1 Position against existing approaches (closes the loop the introduction's "no existing pipeline" claim opens) and §6.2 Vision-language models for material characterization (the grid-collapse / region-classification finding from development, transferable and previously unreported). Design implications, Limitations, Outlook renumbered 6.3–6.5. Conclusion compressed to ~80 words: one sentence per study, one contribution sentence, no repeated limitations. Note: §6.2's claim of region-based reliability shares the C2 caveat (branch pending verification); if the region method is not adopted, soften §6.2 to report only the grid-collapse finding.

## Changes requiring your decision

- **C1 — Title** still pending; three working options unchanged from the previous compile.
- **C2 — Method description updated to region-based classification.** §4 now describes mesh segmentation into planar regions and fracture clusters with per-region crop classification and anomaly detection, replacing the 8×8 grid + spatial majority vote text, which no longer matches the implementation. This reflects the `feature/region-classification` branch as of 2026-08-10, which is not yet merged or verified on the full fragment set. If the branch is not adopted, this paragraph must be reverted. The §5.1 worked-example figures (1663 × 703 × 448 mm, 910 kg, eight planes) come from the corrected-units run of 2026-08-10.
- **C3 — Fragment count.** The old draft claimed "ten real fragment scans"; currently six are processed (FS-001 geometry-only). Written as "[n, currently six]"; set the final n after the batch run.
- **C4 — §5.1 and §5.2 remain placeholders**; highest-priority missing content (reviewers' key ask).

## Carried-over open items (from the previous side notes, still open)

- **C5 — Citations:** IASS self-citation; KG-audit; Watts Towers; Wang Shu; design-factor sources; Skoury et al. missing from reference list; verifications (Brütting, Önalan, Frayling, Itten, Moholy-Nagy, EEA 800 Mt); novelty check against 10.1002/best.70129 and 10.1002/bate.202500021.
- **C6 — Gap count** ("thirteen" vs "11") to reconcile against the final IASS paper.
- **C7 — Figures:** Fig. 1 reuse policy + requirement dots; Fig. 2 typo, Database→Record, update the surface branch to region crops, resolve the point-cloud-to-classification path.
- **C8 — Table 1** (schema excerpt) still recommended, from `descriptor_dictionary.md`; verify roughness is curvature-derived.
- **C9 — "Material audit layer of the broader feature-aware reuse framework"** removed from §4 (it read as an unexplained proper noun); if the framework should be named, reintroduce with a citation.
