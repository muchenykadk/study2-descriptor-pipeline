# design_assignment — rule set

Source: `env/design_factors.json`. Evaluated per face. Rules are tried in order and the first match wins.

**Basis recorded in the file:** Study 1 spolia principle: cast and finished faces exposed, fracture faces seated or buried.

| # | Conditions | Result | Note in the file |
|---|---|---|---|
| 1 | `if_scan_reliable: false` | **buried** | ground-contact face, not observed |
| 2 | `if_label` in {`formwork_face`, `tile_remnant`, `brick_inclusion`} | **show_face** | carries visible material history: a cast face, adhering tile, or brick cast into the concrete |
| 3 | `if_label` in {`broken_face`, `exposed_aggregate`} and `min_area_m2: 0.1` and `max_fit_rms_mm: 8.0` | **seat_face** | flat fracture face, suitable for bearing |
| 4 | none | **unassigned** | no rule applies |

## Corpus outcome, 2026-08-25 run, 82 faces across 11 fragments

| result | faces |
|---|---:|
| unassigned | 63 |
| buried | 10 |
| seat_face | 8 |
| show_face | 1 |

## Known defects

1. **`if_label` reads `surface_label`, not `features`.** `surface_label` holds one display-precedence winner, so a face carrying several features is judged on one of them. `finishing_requirement` was migrated to read the full `features` set; this factor was not.

2. **A display ordering can flip the result.** On FS-002 face 6, `features` = [`brick_inclusion`, `exposed_aggregate`, `broken_face`], area 0.451 m2, RMS 1.53 mm. With `surface_label` = `brick_inclusion` rule 2 fires and the face is shown. With `surface_label` = `broken_face` rule 2 is skipped and rule 3 fires, seating the same face. Reordering display precedence on 2026-08-25 changed which one applies.

3. **`exposed_aggregate` is a composition label used to infer formation.** The taxonomy admits it for aggregate "washed clear", a decorative finish, so a designed exposed-aggregate face satisfies rule 3 and is hidden.

4. **`buried` records a scanning circumstance.** The face marked unreliable is whichever the fragment rested on when scanned. A different resting orientation yields a different buried face.

5. **Rule 2 has no size or flatness test.** A face qualifies as a show face on its label alone, however small or irregular.
