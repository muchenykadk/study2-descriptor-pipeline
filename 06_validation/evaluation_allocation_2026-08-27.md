# Evaluation allocation, against the frozen corpus of 2026-08-27

What the eleven records can and cannot discriminate, and how the eight decisions in
`study1_decisions.md` should be spread across the four competency categories as a result.
Written before any decision was reconstructed, so the allocation cannot be fitted to a
known answer.

---

## What the corpus supports

Fragment-level range is wide and usable:

| | min | max |
|---|---:|---:|
| mass | 181 kg (FS-012) | 1564 kg (FS-003) |
| longest dimension | 737 mm | 2051 mm |
| thickness | 432 mm | 706 mm |
| faces per fragment | 5 | 8 |

Face-level surface labels are the constraint. **Twelve of 79 faces carry any feature**, and
only four features reach a face at all:

| feature | faces | fragments |
|---|---:|---|
| `exposed_aggregate` | 11 | most |
| `broken_face` | 11 | most |
| `brick_inclusion` | 2 | FS-002, FS-004 |
| `paste_dominant` | 1 | FS-012 |

**Five active features reach no face whatsoever**: `tile_remnant`, `rebar_visible`,
`pipe_opening`, `formwork_face`, `biological_growth`. They were classified, on regions, and
those regions are non-planar so they have no face to attach to. Four fragments have no
labelled face at all: FS-006, FS-008, FS-009, FS-010.

---

## Consequences for the four categories

**A, attribute filtering.** The only distinctive attribute query the corpus can answer is
`--label brick_inclusion`, returning 2 faces. Everything else is either one of the two
ubiquitous features, which cannot discriminate, or a feature no face carries.
**Allocate 1 decision.**

**B, multi-criteria over geometry and mass.** Fully supported, and it exercises the values
marked `measured`. Mass, thickness, height band, face area and flatness all vary usefully.
**Allocate 5 decisions.**

**C, a condition located on a specific face.** Possible only for brick, on FS-002 or FS-004.
**Allocate 1 decision**, and expect it to overlap with A.

**D, documented but inexpressible.** Better supported than when the protocol was written,
and by a real case rather than an invented one. Study 1 reinterpreted a former pipe
penetration as a planter. `pipe_opening` was classified on two regions in this run, both
non-planar, so no face carries it and `planter_void` cannot fire. The decision is documented,
the descriptor exists, and the query cannot be expressed. **Allocate 1 decision**, and use
this one.

---

## Two queries whose outcome is already determined

Worth stating before running, so the result is not read as a surprise.

`--use planter_void` returns nothing on any fragment. So do `bench_top`, `cut_candidate` and
`shelf_slab`. The first three are blocked by the face-label gap; `shelf_slab` is blocked
geometrically, since it requires a thickness between 50 and 180 mm and the thinnest fragment
in the corpus is 432 mm.

---

## What each result means

A returning 2 candidates that include the documented choice is a real, if small, success.
A returning nothing is a finding about the face-label gap and not about the classifier.
B is where a genuine recovery rate can be reported.
D succeeding means the query was refused rather than answered, which is the behaviour under
test.

Every decision runs twice, with and without `--geometry-only`, and is reported as candidate
set size plus whether the documented choice is in it.
