# Paper Introduction — Study 2 Draft
*Working draft, 2026-07-14. Citations in author-year format; full references at end of file.*

---

## Introduction

Construction and demolition (C&D) waste constitutes approximately one-third of total solid waste generated in the European Union, amounting to over 800 million tonnes annually (European Environment Agency, 2020). While recycling rates for concrete rubble exceed 80 percent across many member states, the overwhelming majority is processed into low-grade aggregate for road base and fill, a form of downcycling that forfeits the material quality and embodied carbon invested in original production (European Commission, 2023; Economidou et al., 2020). Austria alone generates an estimated 26 million tonnes of C&D waste per year, of which concrete accounts for the largest material fraction (Statistik Austria, 2023). This discrepancy between headline recycling rates and actual material recovery quality reflects a structural limitation in how demolition waste is currently framed: as a bulk flow to be processed, rather than as a collection of discrete fragments with differentiated physical properties and architectural potential. Advancing concrete reuse beyond aggregate recycling requires methods that can characterize individual fragments at a level of specificity sufficient to support design decisions about placement, structural role, and surface expression.

Study 1 of this paper pursued this challenge through a Research through Design (RtD) approach, developing a design methodology for the direct, non-remanufactured reuse of demolition concrete fragments as architectural elements in a built installation [Study 1 citation]. The case study established a framework for selecting and assigning fragments based on geometric properties, including planarity, mass, and bounding dimensions, as well as surface condition, encompassing texture character, visible material history, and colour. The methodology demonstrated that these two descriptor classes jointly determine both the structural and aesthetic suitability of a fragment for a given position in an assembly. A key finding, however, was that while geometric properties can be assessed through direct measurement and photogrammetric reconstruction, surface condition assessment lacked systematic methods: designers relied on qualitative judgement applied fragment by fragment, a process that cannot scale to larger demolition stocks and cannot be formalized into queryable design criteria. This surface condition gap forms the primary motivation for Study 2.

The closest body of prior work is computer vision research for construction inspection, where convolutional neural networks have achieved strong results on image-based defect detection, including crack segmentation and deterioration mapping in concrete structures (Dorafshan et al., 2018; Niklaus et al., 2023). These methods, however, operate over a fixed set of defect categories defined during training and are designed to detect anomalies against a known baseline condition. They cannot characterize the open-ended surface vocabulary of demolition fragments, where conditions such as formwork imprint, exposed aggregate, or weathering patina are not defects but design-relevant properties with no fixed visual signature and no single correct appearance. Vision-language models (VLMs) resolve this limitation by enabling classification against an arbitrary, user-defined taxonomy rather than a pretrained defect set (OpenAI, 2024): a system can be instructed to identify any surface condition that a designer names, without retraining. But open-vocabulary classification at the image level still does not establish where a given surface condition occurs on the fragment, or how its spatial distribution relates to the three-dimensional geometry that governs structural role and tectonic assignment. Geometric computation methods for non-standard reclaimed elements provide this spatial and morphological dimension. Methods developed for computational timber reuse and irregular masonry include principal-component-based bounding geometry, iterative RANSAC plane segmentation for usable face identification, and geometry-to-role allocation algorithms that match element shape to structural position (Knippers et al., 2021; Skoury et al., 2024; Blum et al., 2025). These approaches establish how fragment geometry can be formalized as design data, but they treat elements as geometric objects and do not incorporate surface appearance as a descriptor class. With both surface labels and geometric descriptors in principle available, the remaining gap is one of integration and knowledge linkage: structuring the combined characterization as queryable, design-stage inventory data. Semantic database frameworks for non-standard reclaimed materials have addressed this structuring problem in adjacent domains, proposing knowledge-graph architectures that link material characterization, fabrication constraints, and life cycle assessment for bio-based and waste-sourced material streams (Rossi et al., 2026; Elshani et al., 2025), and material passport approaches that encode component-level data for circular economy workflows (Honic et al., 2021; Luo et al., 2024; Elshani et al., 2024). These frameworks, however, have been developed for materials whose properties are established through laboratory testing or factory measurement; none addresses 3D scan geometry and vision-based surface classification as the primary characterization input, and none has been applied to demolition concrete. No existing pipeline integrates open-vocabulary surface classification, spatial feature localization, geometric morphological analysis, and structured inventory querying into a unified descriptor workflow for this material stream.

Study 2 proposes such a pipeline. It processes 3D scans of demolition concrete fragments to produce two classes of per-fragment descriptor: morphological descriptors (oriented bounding box dimensions and volume, convexity ratio, planar regions identified via iterative RANSAC segmentation, and multi-scale surface curvature), computed deterministically from scan geometry; and surface condition descriptors, classified probabilistically using a vision-language model (GPT-4o) against a seven-class surface taxonomy developed from the RtD criteria established in Study 1. A two-stage vision pass first identifies which surface conditions are present at the image level through majority voting across independent runs, then localizes each detected condition spatially through a grid-based segmentation pass over the UV texture space, reprojecting the result onto the 3D geometry for visualization. All descriptors are consolidated into a per-fragment JSON database structured to support design-stage inventory queries. The pipeline is intended as a scalable instrument for building design-relevant digital inventories of demolition concrete stocks, and as a foundation for linking automatically extracted material characterization to domain knowledge about reuse constraints and architectural opportunities.

---

## References (for this introduction)

Blum, C., Marsillo, L., & Muñoz Guerrero, G. (2025). Reclaimed Design: Development of an Availability-Oriented Framework for Reclaimed Lumber. *ACADIA 2025: Computing for Resilience*, 2.

Dorafshan, S., Thomas, R. J., & Maguire, M. (2018). Comparison of deep convolutional neural networks and edge detectors for image-based crack detection in concrete. *Construction and Building Materials*, 186, 1031–1045. https://doi.org/10.1016/j.conbuildmat.2018.08.011

Economidou, M., Todeschi, V., Bertoldi, P., D'Agostino, D., Zangheri, P., & Castellazzi, L. (2020). Review of 50 years of EU energy efficiency policies for buildings. *Energy and Buildings*, 225, 110322. https://doi.org/10.1016/j.enbuild.2020.110322

Elshani, D., Dervishaj, A., Hernández, D., Gudmundsson, K., Staab, S., & Wortmann, T. (2024). An Ontology for the Reuse and Tracking of Prefabricated Building Components. *(conference proceedings, no DOI available)*

Elshani, D., Lombardi, A., Hernandez, D., Staab, S., Fisher, A., & Wortmann, T. (2025). AEC Co-design workflow for cross-domain querying and reasoning using Semantic Web Technologies. *Automation in Construction*, 176. https://doi.org/10.1016/j.autcon.2025.106226

European Commission. (2023). *A Green Deal Industrial Plan for the Net-Zero Age*. https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A52023DC0062

European Environment Agency. (2020). *Construction and Demolition Waste: Challenges and Opportunities in a Circular Economy*. EEA Report. https://www.eea.europa.eu/publications/construction-and-demolition-waste-challenges

Feretzakis, G., et al. (2024). [placeholder — confirm peer-reviewed VLM/AEC paper before submitting]

Honic, M., Kovacic, I., & Rechberger, H. (2021). Improving the recycling potential of buildings through Material Passports (MP): An Austrian case study. *Journal of Cleaner Production*, 279, 123536. https://doi.org/10.1016/j.jclepro.2020.123536

Knippers, J., Kropp, C., Menges, A., Sawodny, O., & Weiskopf, D. (2021). Integrative computational design and construction: Rethinking architecture digitally. *Civil Engineering Design*, 3(4), 123–135. https://doi.org/10.1002/cend.202100027

Luo, J., Zadeh, P., & Staub-French, S. (2024). Ontology-Based Design Features for Representing Constructability in Architectural Design: Toward BIM in Off-Site Construction. *Journal of Construction Engineering and Management*, 150(10), 05024010. https://doi.org/10.1061/JCEMD4.COENG-14764

Niklaus, M., Koch, C., König, M., & Teizer, J. (2023). BIM- and machine-learning-based visual site monitoring using 360-degree images. *Journal of Construction Engineering and Management*, 149(5). https://doi.org/10.1061/JCEMD4.COENG-12934

OpenAI. (2024). GPT-4 Technical Report. *arXiv*, 2303.08774. https://doi.org/10.48550/arXiv.2303.08774

Rossi, G., Marsillo, L., Akbar, Z., Tamke, M., Wortmann, T., & Ramsgaard Thomsen, M. (2026). Towards an integrated Semantic-based Resource-driven modelling framework for design to fabrication of bio-based and waste-source materials in AEC using knowledge graph. *GNI Symposium on Artificial Intelligence for the Built World*, TU Munich.

Skoury, L., Treml, S., Opgenorth, N., Amtsberg, F., Wagner, H. J., Menges, A., & Wortmann, T. (2024). Towards data-informed co-design in digital fabrication. *Automation in Construction*, 158, 105229. https://doi.org/10.1016/j.autcon.2024.105229

Statistik Austria. (2023). *Abfallstatistik: Bau- und Abbruchabfälle*. https://www.statistik.at/statistiken/energie-und-umwelt/umwelt/abfallstatistik

---

## Notes / flags before submission

- **[Study 1 citation]**: Insert the actual IASS paper citation once finalised.
- **Feretzakis et al. (2024)**: This placeholder for a VLM-in-AEC paper needs a confirmed peer-reviewed source. Remove or replace if not found.
- **Niklaus et al. (2023)**: Verify DOI is correct for the 2023 paper. If the journal entry is different, update.
- **Statistik Austria (2023)**: Confirm the exact URL and report title from the Austrian statistics portal before submission.
- **EEA (2020)**: Verify the exact report URL is accessible and confirm the 800 Mt/year figure from this source. Alternative: cite Eurostat directly (https://ec.europa.eu/eurostat/statistics-explained/index.php/Waste_statistics).
- **Honic et al. (2021)**: This is an Austrian material passport paper, relevant and peer-reviewed.
