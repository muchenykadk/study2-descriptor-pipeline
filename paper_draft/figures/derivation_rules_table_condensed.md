# Condensed derivation rules table, LNCS format

Formatting per `splnproc2510` template: caption **above** the table, bold run-in "Table N.",
horizontal rules only (top, under the header, bottom), no vertical lines, no rules between
body rows, table centred, 9 pt.

---

**Table 2.** Encoded design rules. Within each factor the rules are tried in order and the
first match wins; a default closing each list is omitted. Candidate uses are not exclusive:
every one is tested and all matches are kept, and their conditions are given as fragment
conditions, then face conditions after the semicolon. Thresholds are project-derived and
carry the data status `proposed`.

| Factor | Conditions | Result |
|---|---|---|
| **Handling class** (per fragment) | longest dimension > 800 mm | excavator |
| | mass ≤ 25 kg | manual |
| | mass ≤ 50 kg | two person |
| **Connection** (per face) | face not scanned | gravity only |
| | RMS ≤ 5 mm, area ≥ 0.10 m² | direct bolt |
| | RMS ≤ 12 mm, area ≥ 0.05 m² | adaptive bracket |
| **Assignment** (per face) | face not scanned | buried |
| | label ∈ {formwork, tile, brick} | show face |
| | label ∈ {broken, aggregate}, area ≥ 0.10 m², RMS ≤ 8 mm | seat face |
| **Candidate use** (fragment; face) | thickness ≥ 80 mm; ≥ 0.25 m², RMS ≤ 8 mm, label ∈ {formwork, tile} | bench top |
| | mass ≥ 150 kg; ≥ 0.20 m², RMS ≤ 15 mm | leaning support |
| | –; ≥ 0.10 m², label ∈ {formwork, tile, brick} | exposed face |
| | curvature ≥ 0.3 rad; ≥ 0.10 m², label ∈ {broken, aggregate} | rough feature |
| | thickness ≥ 150 mm, mass ≥ 150 kg; **no** face ≥ 0.12 m² at RMS ≤ 8 mm | cut candidate |
| | thickness ≥ 100 mm; label = pipe opening | planter void |
| | height 380–520 mm, mass ≥ 50 kg; ≥ 0.10 m², RMS ≤ 10 mm | seat block |
| | height 900–1150 mm, mass ≥ 100 kg; ≥ 0.08 m², RMS ≤ 12 mm | bar-table stand |
| | height 250–400 mm, mass ≥ 30 kg; ≥ 0.08 m², RMS ≤ 12 mm | low support |
| | mass ≥ 150 kg; ≥ 0.12 m², RMS ≤ 10 mm | pedestal support |
| | thickness 50–180 mm, aspect ≥ 2.5; ≥ 0.20 m², RMS ≤ 8 mm | shelf slab |

*All face conditions additionally require the face to have been scanned, except
`pedestal_support`, which omits the test.*

---

## What was cut to condense, and why

**`finishing_requirement` is omitted entirely**, seven rules. It is withheld from the record,
and a method table should describe what the pipeline produces. §6.4 explains the withholding.

**Default rules are omitted**, four rows. Each factor closes with an unconditional rule
returning `unassigned`, `gravity_only` or `none`. The caption states that a default exists.

**`drill_zone` is omitted.** Also withheld, and it is a single computation rather than a
rule list.

**The scope column is folded into the factor name**, saving a column across 21 rows.

**Field names are shortened to their measured quantity.** `fit_rms_mm` to RMS,
`area_m2_est` to area, `min_fine_curvature_rad` to curvature. The full identifiers stay in
`derivation_rules_all.md` and in the repository.

Result: two tables of 18 and 11 rows in five and four columns become one table of 21 rows in
three columns. At 9 pt this is roughly half a page.

## If more space is needed

The three height-band uses (seat block, bar-table stand, low support) are one rule shape with
three sets of numbers and could collapse to a single row reading
`height 250–1150 mm in three bands, mass ≥ 30–100 kg; flat face ≥ 0.08 m²`. That saves two
rows and loses the ability to read off which band gives which use.
