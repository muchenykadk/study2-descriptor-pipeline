# Derivation rules, complete set

Source `env/design_factors.json`, state of 2026-08-25. For review and revision.
Notation: ∈ means the value is one of the listed set. Rules within a factor are tried in
order and the first match wins. `label` currently reads `surface_label`, the display
winner, which is a known defect: it should read `features`.

---

## Table A — the four design factors

| Factor | Scope | # | Conditions | Result |
|---|---|---:|---|---|
| **handling_class** | fragment | 0 | `max_dim` > 800 mm | **excavator** (override, tested first) |
| | | 1 | `mass` ≤ 25 kg | **manual** |
| | | 2 | `mass` ≤ 50 kg | **two_person** |
| | | 3 | none | **excavator** |
| **connection_strategy** | face | 1 | `scan_reliable` = false | **gravity_only** |
| | | 2 | `fit_rms` ≤ 5 mm ∧ `area` ≥ 0.10 m² | **direct_bolt** |
| | | 3 | `fit_rms` ≤ 12 mm ∧ `area` ≥ 0.05 m² | **adaptive_bracket** |
| | | 4 | none | **gravity_only** |
| **design_assignment** | face | 1 | `scan_reliable` = false | **buried** |
| | | 2 | `label` ∈ {`formwork_face`, `tile_remnant`, `brick_inclusion`} | **show_face** |
| | | 3 | `label` ∈ {`broken_face`, `exposed_aggregate`} ∧ `area` ≥ 0.10 m² ∧ `fit_rms` ≤ 8 mm | **seat_face** |
| | | 4 | none | **unassigned** |
| **finishing_requirement** *(withheld)* | face | 1 | `label` = `rebar_visible` | **cut_back_and_seal** |
| | | 2 | `label` = `tile_remnant` | **strip_bedding** |
| | | 3 | `label` ∈ {`broken_face`, `exposed_aggregate`} ∧ `fine_curvature` ≥ 0.3 rad | **ease_sharp_arrises** |
| | | 4 | `label` = `biological_growth` | **clean_before_use** |
| | | 5 | `assignment` = `show_face` | **clean_only** |
| | | 6 | `scan_reliable` = false | **none** |
| | | 7 | none | **none** |

`drill_zone` is a fragment-scope factor with a single computation rather than a rule list.
It is also withheld. Assumptions: 20 mm cover, 12 mm bar diameter, 60 mm minimum clear core,
35° edge-normal tolerance.

---

## Table B — candidate uses

All eleven are tested; every match is kept. A rule needs its fragment conditions to hold and
at least one face to satisfy its face conditions.

| # | Use | Fragment conditions | Face conditions |
|---:|---|---|---|
| 1 | bench_top | `thickness` ≥ 80 mm | `area` ≥ 0.25 m² ∧ `fit_rms` ≤ 8 mm ∧ `label` ∈ {`formwork_face`, `tile_remnant`} ∧ `scan_reliable` |
| 2 | leaning_support | `mass` ≥ 150 kg | `area` ≥ 0.20 m² ∧ `fit_rms` ≤ 15 mm ∧ `scan_reliable` |
| 3 | exposed_face | none | `area` ≥ 0.10 m² ∧ `label` ∈ {`formwork_face`, `tile_remnant`, `brick_inclusion`} ∧ `scan_reliable` |
| 4 | rough_feature | `fine_curvature` ≥ 0.3 rad | `area` ≥ 0.10 m² ∧ `label` ∈ {`broken_face`, `exposed_aggregate`} ∧ `scan_reliable` |
| 5 | cut_candidate | `thickness` ≥ 150 mm ∧ `mass` ≥ 150 kg | **no** face with `area` ≥ 0.12 m² ∧ `fit_rms` ≤ 8 mm ∧ `scan_reliable` |
| 6 | planter_void | `thickness` ≥ 100 mm | `label` ∈ {`pipe_opening`} ∧ `scan_reliable` |
| 7 | seat_block | `height` ∈ [380, 520] mm ∧ `mass` ≥ 50 kg | `area` ≥ 0.10 m² ∧ `fit_rms` ≤ 10 mm ∧ `scan_reliable` |
| 8 | bar_table_stand | `height` ∈ [900, 1150] mm ∧ `mass` ≥ 100 kg | `area` ≥ 0.08 m² ∧ `fit_rms` ≤ 12 mm ∧ `scan_reliable` |
| 9 | low_support | `height` ∈ [250, 400] mm ∧ `mass` ≥ 30 kg | `area` ≥ 0.08 m² ∧ `fit_rms` ≤ 12 mm ∧ `scan_reliable` |
| 10 | pedestal_support | `mass` ≥ 150 kg | `area` ≥ 0.12 m² ∧ `fit_rms` ≤ 10 mm **(no `scan_reliable` test)** |
| 11 | shelf_slab | `thickness` ∈ [50, 180] mm ∧ `aspect_ratio` ≥ 2.5 | `area` ≥ 0.20 m² ∧ `fit_rms` ≤ 8 mm ∧ `scan_reliable` |

---

## Where varieties are missing

**Three active features no rule reads at all.** `embedded_metal`, `paste_dominant`,
`trowelled_finish`. Eight of the eleven features drive something; these three are classified
and then ignored. `embedded_metal` is the notable one: non-reinforcement steel cast into the
piece has obvious consequences for cutting and drilling and has no finishing rule.

**Two connection classes named in the basis and never encoded.** The `connection_strategy`
basis cites four classes from the reuse literature: dry mechanical or demountable,
post-tensioned, wet or cast, and bearing without direct connection. The rules implement
only the first and the last, as `direct_bolt`, `adaptive_bracket` and `gravity_only`.

**Handling has no band above 50 kg.** Everything heavier is `excavator`, which returned the
same answer on all eleven fragments and therefore carries no information. EN 474-5 and
ISO 8643 give a threshold at 1,000 kg object-handling capacity, or 40,000 Nm load moment,
above which the machine must carry an overload warning device, load-holding valves and a
rated capacity chart. That is a change in required equipment rather than a limit of
capability, and on this corpus it splits 6 over and 5 under. The load-moment limb cannot be
evaluated from a fragment record, since it needs the working radius.

**No rule uses colour.** `colour_entropy_bits` was added on 2026-08-25 and nothing reads it.

**No rule uses the coarse curvature scale.** Only `fine_mm.mean_rad` reaches a rule. The
coarse scale drives a display grade in the report and nothing else, and the standard
deviations and quartiles at both scales are read by nothing.

**Four use rules wait on an uncomputed descriptor.** `seat_block`, `bar_table_stand` and
`low_support` all test a height band, and `leaning_support` tests a presented angle. A height
band means nothing until the stable resting orientation is known, and it is not computed.

**Assignment has no vocabulary for a cut face or a joint face.** The four outcomes are show,
seat, buried and unassigned. A face created by sawing, or a face meeting another fragment in
an assembly, has no term.

---

## Known defects in the rules as written

1. `design_assignment` and `use_suggestions` read `surface_label`, one display-precedence
   winner, instead of `features`. `finishing_requirement` was migrated and these were not.
   On FS-002 face 6 this makes a colour-ordering list decide between `show_face` and
   `seat_face` on identical classification.
2. `exposed_aggregate` is a composition label used to infer formation, in
   `design_assignment` rule 3 and `finishing_requirement` rule 3. The taxonomy admits it for
   aggregate washed clear, a decorative finish, so a designed exposed-aggregate face is
   seated and its arrises eased.
3. `pedestal_support` omits `scan_reliable`, so it can be proposed on reconstructed
   ground-contact geometry. It is the rule with the heaviest consequence and it fired on all
   eleven fragments.
4. `design_assignment` rule 2 has no size or flatness test. A face qualifies as a show face
   on its label alone, however small or irregular.
5. `buried` records a scanning circumstance. The unreliable face is whichever the fragment
   rested on when scanned, so a different resting orientation yields a different buried face.
6. The `finishing_requirement` evidence note still cites `spalling` and the anomaly axis,
   both removed on 2026-08-20.
7. No rule can require two features together, because a list is read as OR. Adding a
   `requires_all_labels` key would make co-occurrence expressible.
