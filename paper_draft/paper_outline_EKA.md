# EKA Full Paper — Working Outline
*Living doc. Created 2026-07-22. Deadline: 15 August 2026. Limit: 11 pages incl. references.*
*Companion to `paper_introduction_draft.md` (intro prose already drafted there).*

**Core rule:** the accepted IASS paper [1] owns Study 1 in full — six-stage workflow, gap-analysis table (IASS Table 2), data-requirements scheme (IASS Table 3). This paper cites, compresses, and never reproduces. The EKA paper's weight is Study 2.

**Reviewer mandate (scores 67, 71):** "Future work should focus on validating the computational pipeline with real project data and further demonstrating its applicability in practice." → real-fragment results and the validation section are the paper's success criteria.

---

## 1. Introduction (~1.5–2 pp)

- C&D-waste framing: one paragraph only (drafted in `paper_introduction_draft.md` ¶1).
- **NEW — materiality/features from a design-use perspective** (agreed 2026-07-22): do *not* re-derive the Ruskin/Pallasmaa/Frampton/spolia argument (that is IASS §3 — cite in one line). Instead spend the paragraph on the practice angle:
  - Features (formwork imprint, exposed aggregate, weathering patina) are design-relevant properties, not defects — position established in [1] via spolia criteria.
  - In current practice this recognition exists only as tacit designer judgment, fragment-by-fragment manual curation.
  - Study 1 documented that this is precisely what fails to scale ("curation impractical beyond small fragment sets" — one-line callback, no table).
  - Pivot: if surface features are design data, they must become computable → sets up the SOTA survey.
- Related work (already drafted): CV defect-detection (closed defect classes) → VLM open-vocabulary classification (arbitrary taxonomy, but no spatial localization) → geometric methods for reclaimed elements (shape without surface) → semantic-KG / material-passport frameworks (lab-measured inputs, never scan+vision). Gap: no integrated pipeline for demolition concrete.
- Repetition check: IASS intro covers postwar stock/downcycling in 2 paragraphs — keep overlap to ≤1 compressed paragraph with different statistics (EU/Austria figures already in draft).

**Agreed intro spine (2026-07-22, supersedes bullets above where they conflict):** single overarching gap = reclaimed materials lack design-environment-ready queryable models; materiality is its sharpest sub-case.
  1. C&D framing (1 ¶, de-emphasize postwar period — scope includes future deconstruction of later building stock).
  2. Data asymmetry: virgin materials enter design as machine-readable data (strength classes, datasheets, BIM objects); reclaimed fragments arrive undocumented. Passports/audits/databases = documentation infrastructure, stops short of design environment; design-side research = geometric tokens for stock matching. Neither delivers materiality-rich queryable models. Procedural complexity (handling, connection) = design parameters, not downstream logistics (Study 1 evidence).
  3. Study 1 + materiality: features as design-relevant properties (spolia, cite [1] one line); assessment currently tacit, fragment-by-fragment, unscalable.
  4. SOTA survey (as drafted — critiques input side: lab-measured, closed classes, no spatial localization).
  5. Integrated gap statement + Study 2 announcement (queryable per-fragment models in design environment).


## 2. Objectives & Methodology (~0.5 pp)

**Contribution framing (agreed 2026-07-22, mirrors intro ¶5):** paper = middle step of a three-step arc (practice-derived requirements → prototyped instrument → design-loop integration). Explicit non-claims: no live CAD/design-loop integration yet; validation retrospective within one project.

**REVISED OBJECTIVES (2026-07-22, supersede the EKA abstract's four).** Old objectives 1–3 were Study 1's and are achieved in [1]; old objective 4 promised pseudo data, descriptor-to-attribute linking (schema-only in reality), and a "CAD interface with multi-model AI integration" that no longer describes the implementation. New set:

- **Overarching aim (raised 2026-07-22, v2):** an interactive design environment for reclaimed concrete supporting a fully material-adaptive design process: extended knowledge (geometry, surface character, procedure) in the design phase, computational support from inventory search to algorithmic matching/optimization. No new-materials comparison here. Paper explicitly does NOT deliver this; contributes foundation + instrument. NOTE: IASS §3 coined "fully material-adapted" (feature level + tectonic level); consider matching that exact term so it carries its published definition — decide adaptive vs adapted.
- **O1 (foundation, established in [1], recapped in §3):** demonstrate the design and aesthetic potential of irregular concrete fragments through a built public commission, collect the procedural experience, and derive an information requirements scheme from documented gaps. One sentence + citation; no re-derivation.
- **O2 (schema):** operationalize Study 1's requirements scheme into a machine-readable descriptor schema (per-descriptor computation method, unit, provenance status; geometric, surface character, procedural linkage). Verb matters: IASS *formalized* the requirements (Table 3); this paper *operationalizes* them into an implemented data model. → delivered in §4.5/§6.
- **O3 (instrument):** prototype the extraction pipeline and demonstrate it on real Study 1 fragment scans: deterministic morphological descriptors + VLM surface classification with spatial localization, consolidated into per-fragment records. → §4/§5. Explicitly note the upgrade from the abstract's pseudo-data promise to real data (answers reviewer comment directly; say so).
- **O4 (design relevance):** retrospectively evaluate whether the computed characterization recovers the design logic documented in Study 1, and identify which requirement dimensions remain open (structural inference above all). → §6/§7.

**Methodology paragraph:** practice-led, two-study design; RtD case study as requirement generator, instrument prototyping as response; evaluation = retrospective single-case comparison against documented decisions (state its limits: small n, one project, designer-as-researcher bias worth one honest clause). Drop "multi-model AI integration" phrasing everywhere; describe as VLM-based surface classification integrated with deterministic geometric computation.

**Wording watchlist from abstract → paper:** "pseudo data" (gone, real data), "CAD interface" (now: records structured for design-stage querying; interface = future work), "multi-model" (now: single VLM + geometry pipeline).

## 3. Study 1 recap (~0.5–0.75 pp, 1 figure)

- One paragraph + workflow figure (Fig. 1 from IASS may be reused/adapted — check EKA copyright/self-plagiarism rules for figure reuse; consider redrawing simplified).
- Explicit pointer: "full gap analysis and data-requirements scheme in [1]."
- Carry forward only what Study 2 consumes: the three gap dimensions + the specific gaps the pipeline addresses.

## 4. Study 2 — Pipeline Architecture (~2.5–3 pp)

Describe the **actual implementation** (decision 2026-07-22): Blender (mesh prep, UNSCANNED vertex-group marking) + standalone Python (trimesh/open3d, GPT-4o vision) + HTML/Three.js report viewer. NOT Rhino/GH (02_gh is empty; original plan superseded).

- 4.1 Data acquisition & mesh prep: Scaniverse LiDAR-assisted photogrammetry → Blender clean/bake → GLB + texture + scan-coverage sidecar.
  - **Input modalities (decision 2026-07-22, kept OUT of intro):** state the mesh-vs-point-cloud asymmetry honestly here. Primary input = textured mesh (Scaniverse fuses LiDAR depth + photogrammetry imagery into ONE mesh — do not describe as two capture pathways); pipeline additionally accepts raw point clouds (build_viewer_data_pcd) but that path yields geometric descriptors only, no UV texture → no surface classification. Full schema instantiation requires the textured mesh.
- 4.2 Geometric descriptors: OBB/volume/convexity/mass-est; RANSAC planarity (area, fit_rms, normal); multi-scale curvature.
- 4.3 The UNSCANNED-face problem & solution: ground-contact face never scanned; vertex-group sidecar → scan_reliable flag on planes → texture-mask exclusion from AI classification. (Novel methodological detail — nothing like it in IASS; give it space.)
- 4.4 Surface descriptors: two-stage AI pass — (a) image-level 7-class taxonomy w/ majority voting, (b) 8×8 grid spatial localization over UV texture space, reprojected to 3D via XZ spatial majority-vote. Taxonomy derived from Study 1 spolia criteria (`env/taxonomy.json`).
  - **Open-vocabulary clarification (2026-07-22):** state explicitly — capability is open-vocabulary (user-defined taxonomy, no retraining; the advance over CNN defect detectors), deployment is a controlled practice-derived taxonomy fixed at run time. Rationale: inventory queryability requires controlled vocabulary; runtime-free labels cause synonym drift and break reproducibility (majority voting, caching, fixed model). Pre-empts "why only seven classes?"
- 4.5 Schema & composite layer: feature_hierarchy (domain→category→descriptor→subtype), links_to design conclusions. **Present connection_strategy / handling_class / design_assignment as PROPOSED rules with specified input logic — not demonstrated results** (audit 2026-07-22: they exist in 04_schema only, not in code; the face-to-label join needed for per-face conclusions does not exist yet).

## 5. Results (~1.5–2 pp)

Report only what is actually computed:
- Fragment status: **ten real Study 1 fragment scans** (set 2026-07-22). Verify before submission that all ten are registered in the manifest and processed through the pipeline (repo previously showed 5 registered / 2 complete); distinguish "scanned" from "processed" if any lag. Precision on the real-vs-pseudo claim (2026-07-22): three tiers, name each — (1) geometric + surface descriptors computed from REAL Study 1 scans (the upgrade reviewers asked for); (2) unmeasured attribute VALUES (concrete class/strength, rebar presence) = flagged pseudo entries; (3) encoded procedural KNOWLEDGE (machinery requirements, joinery/connection feasibility) = real content but provisional, unverified pending expert/field validation. "Pseudo" applies to tier 2 only; call tier 3 "provisional". Do not claim "no longer pseudo" wholesale.
- scan_reliable flagging verified on FS-006 (one sentence — closes the loop opened by §4.3; without it the UNSCANNED section reads as untested design).
- FRAG-S1-FS-006 worked example: 8×8 grid → formwork_imprint (top, cast face) / exposed_aggregate (fracture faces), UNSCANNED cells correctly excluded (3 cells, 455/2000 points). 2-label result physically correct for a floor slab.
- Honesty boundary: subtype layer (~40 classes in feature_hierarchy.csv) is target taxonomy, NOT validated — report AI results at 7-class level only; n=1..2 caveat stated plainly.

## 6. [CUT 2026-07-23] Mapping descriptors to Study 1 gaps

**Section dropped.** Fig. 1 already carries the requirements mapping (attributes × stages × dimension). A standalone gap→descriptor table would only add the status accounting (computed / ai-annotated / pseudo / proposed / open), which is better placed where it arises:
- §4 already marks the proposed-vs-computed split for the linkage layer (connection_strategy, handling_class, design_assignment = proposed, not computed).
- §5 Results states what is real vs pseudo across the ten fragments (three-tier data honesty).
- §8 Discussion carries the open residuals: CoM absent, rebar direction not sensed, concrete strength pseudo; connection-feasibility only PARTIAL (per-face class, not spatial drillable-zone map); registry/provenance out of extraction scope.
Saves ~0.75 pp against the 11-page limit. Renumber later sections (Validation, Discussion, Conclusion) accordingly. Source mapping (gap→feature→status) retained in chat 2026-07-23 if a compact table is ever wanted in §5.

## 7. Validation against Study 1 decisions (~1–1.5 pp)

Reviewers' key ask. Plan (time now allows, deadline 15 Aug):
- Fill `06_validation/study1_decisions.md` for at least FS-002 + FS-006 (+ FS-003/004 if processed in time).
- Three axes (from HANDOVER): surface labels ↔ aesthetic selection; planarity ↔ connection decisions; mass est ↔ handling records.
- Encode documented Study 1 decisions as queries over descriptors; report agreement/divergence. Divergences = findings (missing descriptor or tacit knowledge → discussion).
- Scale claim honestly: mini-validation on processed fragments, full ~20-fragment retrospective as next step.

## 8. Discussion / Limitations / Future work (~0.75–1 pp)

- Composite layer not yet computed; face-to-label join as immediate next step (possibly implemented before submission — see open items).
- Missing cross-links found in schema audit: scan_reliable should gate design_assignment + connection_strategy; rebar_visible should reach connection_strategy; "display value" composite (PLAN Phase 4) not yet in schema.
- Subtype feasibility: small texture crops + zero-shot VLM → aggregate-species/subtype discrimination doubtful; routes = higher-res capture, human-in-the-loop, fine-tuned model; rebar shape possibly better solved geometrically than visually.
- **Taxonomy evolution via open-vocabulary discovery (future work, 2026-07-22):** unconstrained VLM pass proposing labels beyond the taxonomy → designer curates into taxonomy.json → taxonomy becomes an evolving instrument. Also: dedicated open-vocabulary segmentation models could sharpen localization beyond the 8×8 grid but are object-centric-trained and weak on texture-like "stuff" categories; hybrid = future work.
- Fracture-surface subtypes as potential observation-informed refinement of concrete_class (partial answer to IASS strength gap, without lab-testing claims).
- Scan-quality limits on colour entropy (per PLAN risk log).

## 9. Conclusion (~0.3 pp) + References (~1 pp)

- **Outlook (agreed 2026-07-22):** pipeline demonstrated on fragmented, undocumented rubble, but anticipated applicability (no test claim) to documented and future deconstruction stock: applied to a yet-to-be-deconstructed wall, extracted visual/geometric descriptors would be synthesized with documented attributes (rebar layout, concrete class — where documentation survives) to enrich the pre-demolition audit inventory and support design with pre-demolition buildings. Technical credibility hook: in-situ scans of standing elements have MORE unscannable faces (far side, embedded edges) — the §4.3 UNSCANNED/scan_reliable machinery is precisely what makes partial-coverage scans usable with explicit reliability flags; cite it here.

## Page budget check
1: 1.5–2 · 2: 0.5 · 3: 0.75 · 4: 2.5–3 · 5: 1.5–2 · 6: CUT · 7: 1–1.5 · 8: 0.75–1 · 9+refs: 1.3 → **~9.75–10.75 pp** (§6 cut frees ~0.75 pp; comfortable within 11).

## Open items
- [ ] Decide: implement face-to-label join + rule stubs before submission (turns §4.5/§6 "proposed" into partial results)? Effort vs. §7 validation priority.
- [ ] Run pipeline on FS-003, FS-004 (Task #28) → more validation fragments.
- [ ] Fill `06_validation/study1_decisions.md` from Study 1 project records.
- [ ] Check EKA template + figure-reuse/self-citation policy (Fig. 1 from IASS).
- [ ] Fix intro draft flags: [Study 1 citation] → IASS ref; Feretzakis placeholder; Statistik Austria URL; EEA 800 Mt figure.
- [ ] HANDOVER.md says EKA deadline 24 July — outdated (full paper due 15 Aug); correct to avoid misleading future sessions.

## Change log
- 2026-07-22 v0.3 — contribution framing locked (three-step arc, explicit non-claims); intro ¶5 rewritten accordingly; saw-cut procedural citations resolved (Widmer/Küpfer/Bertola); aesthetic-expression citation candidates collected (Wang 2024 rockeries, Mine the Scrap, TAD concrete cutting waste, as-found, Bestul) pending placement decision.
- 2026-07-22 v0.2 — Muchen's comments processed: intro spine rebuilt around design-environment queryable-models gap (narrowed vs. stock-matching literature); §5 fragment count → placeholder, scan_reliable result restored; §9 outlook added (pre-demolition audit enrichment, hedged, UNSCANNED as enabler); postwar emphasis reduced.
- 2026-07-22 v0.1 — initial outline from co-work session: repetition mapping vs IASS, materiality-in-practice intro angle, feature_hierarchy audit findings (schema-vs-code honesty split), validation plan.
