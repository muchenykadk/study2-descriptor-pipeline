#!/usr/bin/env python3
"""
Manage the surface feature taxonomy without hand-editing JSON.

Adding a label means two entries that have to agree: one in `labels` and one in
`_display_precedence`.  Forgetting the second used to mean the label existed but
never reached the prompt, so the model could not choose it and nothing said so.
This writes both, or neither.

    python 03_src/taxonomy_tool.py list
    python 03_src/taxonomy_tool.py check
    python 03_src/taxonomy_tool.py folders        # one drop-folder per label
    python 03_src/taxonomy_tool.py add            # asks for what it needs
    python 03_src/taxonomy_tool.py add --id embedded_metal --after rebar_visible --rule "..."
    python 03_src/taxonomy_tool.py remove --id original_finish   # only if unused
    python 03_src/taxonomy_tool.py retire --id original_finish   # always safe

Write it on one line.  PowerShell continues with a backtick, not with ^ (cmd)
or \\ (bash), and a stray continuation character arrives as an argument.

`--after` and `--before` set the position in `_display_precedence`, which is the
precedence the model applies when two labels both fit.  In `labels` the entry is
always appended last: that array's order is the integer `feature_id` stored in
every viewer JSON, so inserting mid-array would silently recolour every fragment
already processed.

`add` also creates `01_input/reference_surfaces/<id>/` for the exemplars.  It
does NOT create anything under `_candidates/`: that folder is written by
`build_reference_set.py` from labels the model has already assigned, so a new
label has nothing there until a run produces some.  Crop its first exemplars
from the atlas by hand.

A label can be retired but not deleted once anything references it.  `remove`
refuses in that case and `retire` is the answer: the id and its index stay, so
every feature_id already written keeps its meaning, while the label leaves both
the prompt and the interface.  Reversible with `--undo`.

Adding, retiring or removing a label changes the prompt, so the API cache is
invalidated and every fragment needs `--force` to stay comparable.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_JSON = REPO_ROOT / "env" / "taxonomy.json"
REFERENCE_DIR = REPO_ROOT / "01_input" / "reference_surfaces"

# Distinct hues to fall back on, so a new label never lands on a colour already
# in use; the report legend and the feature map both key on colour.
PALETTE = ["#94a3b8", "#f472b6", "#2dd4bf", "#facc15", "#a78bfa",
           "#fb923c", "#4ade80", "#38bdf8", "#e879f9", "#fca5a5"]


def load() -> dict:
    return json.loads(TAXONOMY_JSON.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    TAXONOMY_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _ids(data: dict) -> list:
    return [l["id"] for l in data.get("features", [])]


def _ref_count(label: str) -> int:
    folder = REFERENCE_DIR / label
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.iterdir()
               if p.suffix.lower() in {".png", ".jpg", ".jpeg"})


# ── commands ────────────────────────────────────────────────────────────────

def cmd_list(data: dict) -> int:
    order = data.get("_display_precedence", [])
    print(f"\n  {len(_ids(data))} features. NOTHING HERE COMPETES: a region may")
    print(f"  carry any number of them. The order below is RENDERING precedence")
    print(f"  only, deciding which colour is drawn on top when several apply.\n")
    groups = {}
    for e in data.get("features", []):
        groups.setdefault(e.get("group", "manufacture"), []).append(e["id"])
    for g in ("manufacture", "inclusion", "defect"):
        if groups.get(g):
            print(f"  {g:<12} {', '.join(groups[g])}")
    print()
    for i, lab in enumerate(order, 1):
        entry = next((l for l in data["features"] if l["id"] == lab), None)
        if entry is None:
            print(f"  {i:>2}. {lab}  ← in _display_precedence but not in labels")
            continue
        n = _ref_count(lab)
        refs = f"{n} exemplar(s)" if n else "no exemplars"
        print(f"  {i:>2}. {lab:<20} {entry.get('color','')}  {refs}")
        rule = entry.get("decision_rule") or "(no decision_rule — the model gets only the id)"
        print(f"      {rule[:96]}{'...' if len(rule) > 96 else ''}")
    absent  = [l for l in _ids(data) if l not in order]
    entry_of = {l["id"]: l for l in data["features"]}
    retired = [l for l in absent if entry_of[l].get("retired")]
    orphan  = [l for l in absent if not entry_of[l].get("retired")]
    for lab in retired:
        print(f"   -. {lab:<20} {entry_of[lab].get('color','')}  retired: id kept so "
              f"stored data resolves, out of the prompt and interface")
    if orphan:
        print(f"\n  Not in _display_precedence, and not retired: {', '.join(orphan)}")

    anoms = data.get("anomalies", [])
    if anoms:
        live = [a for a in anoms if not a.get("retired")]
        print(f"\n  {len(live)} anomaly label(s). A surface label says what a region IS;")
        print(f"  an anomaly is a localized patch within it, with a bounding box.\n")
        for a in anoms:
            mark = "retired" if a.get("retired") else ""
            print(f"      {a['id']:<20} {mark}")
            print(f"          {(a.get('hint') or '')[:88]}"
                  f"{'...' if len(a.get('hint') or '') > 88 else ''}")
    print()
    return 0


def cmd_check(data: dict) -> int:
    problems = 0
    ids, order = _ids(data), data.get("_display_precedence", [])

    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"  ✗ duplicate label id(s): {', '.join(sorted(dupes))}")
        problems += 1

    retired = {l["id"] for l in data.get("features", []) if l.get("retired")}
    missing = [i for i in ids if i not in order and i not in retired]
    if missing:
        print(f"  ✗ in labels but not in _display_precedence: {', '.join(missing)}")
        print(f"      They are appended last at load time, so precedence is not "
              f"what you intended.")
        problems += 1

    unknown = [o for o in order if o not in ids]
    if unknown:
        print(f"  ✗ in _display_precedence but not in labels: {', '.join(unknown)}")
        problems += 1

    for entry in data.get("features", []):
        if entry.get("retired"):
            continue          # out of the prompt, so its rule is not used
        if not entry.get("decision_rule"):
            print(f"  ✗ {entry['id']}: no decision_rule. The prompt would give the "
                  f"model only the bare id.")
            problems += 1
        if not entry.get("color"):
            print(f"  ! {entry['id']}: no color; it will fall back to grey in the "
                  f"report and the feature map.")

    colours = [l.get("color") for l in data.get("features", []) if l.get("color")]
    if len(colours) != len(set(colours)):
        print(f"  ! two labels share a colour; they will be "
              f"indistinguishable in the feature map.")

    for d in sorted(REFERENCE_DIR.iterdir()) if REFERENCE_DIR.is_dir() else []:
        if d.is_dir() and d.name != "_candidates" and d.name not in ids:
            print(f"  ! reference folder '{d.name}' matches no label and is ignored.")

    # Every active feature should have at least one exemplar. The reference
    # images are sent ahead of the regions and told to define what each feature
    # means for this material, so a feature with none is at a standing
    # disadvantage against one with three, and nothing said so until now.
    bare = [e["id"] for e in data.get("features", [])
            if not e.get("retired") and _ref_count(e["id"]) == 0]
    if bare:
        print(f"  ! no exemplar for: {', '.join(bare)}")
        print(f"      The reference set calibrates some features and not these, "
              f"which biases the model toward the ones it has seen. Either crop "
              f"one for each, or run with --no-references and say so.")

    print(f"\n  {problems} problem(s).\n" if problems else "\n  Taxonomy is consistent.\n")
    return problems


def cmd_folders(data: dict) -> int:
    """Create `reference_surfaces/<label>/` for every label in the taxonomy.

    Somewhere to drop hand-made exemplar crops, one folder per category, so the
    set to be filled is visible rather than remembered.

    There is deliberately no equivalent for `_candidates/`. Those folders are
    created by `build_reference_set.py` as it writes each crop, and are named
    after labels the model has already assigned, so an empty one has nothing
    that could go in it.
    """
    # Retired labels are skipped: their folder can never be assigned to, so
    # recreating one after it has been deleted would just put the clutter back.
    retired = {l["id"] for l in data.get("features", []) if l.get("retired")}
    active = [l for l in _ids(data) if l not in retired]

    made = []
    for label in active:
        folder = REFERENCE_DIR / label
        if not folder.is_dir():
            folder.mkdir(parents=True, exist_ok=True)
            made.append(label)

    print()
    for label in active:
        n = _ref_count(label)
        mark = "created" if label in made else f"{n} exemplar(s)" if n else "empty"
        print(f"  {REFERENCE_DIR.name}/{label:<22} {mark}")
    for label in retired:
        if (REFERENCE_DIR / label).is_dir():
            n = _ref_count(label)
            print(f"  {REFERENCE_DIR.name}/{label:<22} retired"
                  + (f", still holds {n} file(s); safe to delete" if n
                     else ", empty; safe to delete"))
    print(f"\n  Crop exemplars from an atlas in 05_output/descriptors/ into these.")
    print(f"  Then: python 03_src/build_reference_set.py --check\n")
    return 0


RECORD_DIR = REPO_ROOT / "05_output" / "descriptors"


def _label_usage(label: str, index: int) -> tuple:
    """Where a label, and its feature_id, appear in already-written output.

    Removing a label is normally forbidden because it breaks comparability. It
    is only safe when nothing carries it, and when nothing carries a HIGHER
    feature_id either: `TAXONOMY` order is that integer, so deleting an entry
    renumbers everything after it and silently recolours stored viewer data.
    """
    in_records, in_viewer, shifted = [], [], []
    for p in sorted(RECORD_DIR.glob("*_geometry.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        hits = [x.get("label") for x in ((r.get("vision") or {}).get("regions") or [])]
        hits += [fa.get("surface_label") for fa in (r.get("planarity") or [])]
        if label in hits:
            in_records.append(r.get("fragment_id", p.stem))

    for p in sorted(RECORD_DIR.glob("*_viewer.json")):
        try:
            v = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ids = {int(pt[4]) for pt in (v.get("points") or []) if len(pt) > 4}
        if index in ids:
            in_viewer.append(p.name)
        if any(i > index for i in ids):
            shifted.append(p.name)
    return in_records, in_viewer, shifted


def cmd_remove(data: dict, args: argparse.Namespace) -> int:
    """Delete a label from both `labels` and `_display_precedence`, if it is unused."""
    ids = _ids(data)
    label = args.id
    if label not in ids:
        print(f"\n  '{label}' is not in the taxonomy. Present: {', '.join(ids)}\n")
        return 1

    index = ids.index(label)
    in_records, in_viewer, shifted = _label_usage(label, index)

    if in_records or in_viewer or shifted:
        print(f"\n  Refusing to remove '{label}' (feature_id {index}).\n")
        if in_records:
            print(f"    assigned in: {', '.join(in_records)}")
        if in_viewer:
            print(f"    feature_id {index} appears in: {', '.join(in_viewer)}")
        if shifted:
            print(f"    higher feature_ids in use, which would renumber: "
                  f"{', '.join(sorted(set(shifted)))}")
        print(f"\n  Removing it would break comparability with output already written.\n"
              f"  If you mean to retire it, leave the id in place and give it a "
              f"decision_rule\n  the model will never satisfy, so nothing new is "
              f"labelled with it.\n")
        return 1

    n_refs = _ref_count(label)
    data["features"] = [l for l in data["features"] if l["id"] != label]
    data["_display_precedence"] = [o for o in data["_display_precedence"] if o != label]
    save(data)

    folder = REFERENCE_DIR / label
    note = ""
    if folder.is_dir():
        if n_refs:
            note = (f"\n  Kept {folder.relative_to(REPO_ROOT)} with its {n_refs} "
                    f"exemplar(s); delete it yourself if you want them gone.")
        else:
            folder.rmdir()
            note = f"\n  Removed the empty folder {folder.relative_to(REPO_ROOT)}."

    print(f"\n  Removed '{label}'. Nothing in 05_output referenced it.")
    print(f"  Order : {' > '.join(data['_display_precedence'])}{note}")
    print(f"\n  The prompt has changed, so the API cache is invalidated. Every "
          f"fragment needs\n  --force to stay comparable.\n")
    return 0


def cmd_retire(data: dict, args: argparse.Namespace) -> int:
    """Take a label out of the prompt and the interface, keeping its id.

    The answer for a label that is in use and so cannot be removed. Its
    position in `labels` stays, so every feature_id already written keeps its
    meaning, but it is dropped from `_display_precedence` and from the report
    legend, chips and filters. Nothing new can be labelled with it; anything
    already labelled still renders correctly.
    """
    ids = _ids(data)
    label = args.id
    if label not in ids:
        print(f"\n  '{label}' is not in the taxonomy. Present: {', '.join(ids)}\n")
        return 1

    entry = next(l for l in data["features"] if l["id"] == label)
    if entry.get("retired") and not args.undo:
        print(f"\n  '{label}' is already retired. Use --undo to bring it back.\n")
        return 1

    if args.undo:
        entry.pop("retired", None)
        if label not in data["_display_precedence"]:
            data["_display_precedence"].append(label)
    else:
        entry["retired"] = True
        # Drop it from the stated order too. taxonomy.py filters retired labels
        # at load time either way, but leaving it here made the file disagree
        # with what the pipeline actually does, and `list` showed it as active.
        data["_display_precedence"] = [o for o in data["_display_precedence"] if o != label]
    save(data)

    in_records, in_viewer, _ = _label_usage(label, ids.index(label))
    verb = "Restored" if args.undo else "Retired"
    print(f"\n  {verb} '{label}' (feature_id {ids.index(label)}, kept so stored "
          f"data still resolves).")
    if not args.undo:
        print(f"  It is now out of the prompt and out of the report legend, chips "
              f"and filters.")
        if in_records or in_viewer:
            print(f"  Still rendered where already assigned: "
                  f"{', '.join(in_records or in_viewer)}")
        else:
            print(f"  Nothing has ever been labelled with it, so you could also "
                  f"remove it outright:\n    python 03_src/taxonomy_tool.py remove "
                  f"--id {label}")
    print(f"\n  The prompt has changed, so the API cache is invalidated.\n")
    return 0


def cmd_add(data: dict, args: argparse.Namespace) -> int:
    ids = _ids(data)

    def ask(prompt: str, default: str = "") -> str:
        """Prompt only when there is a terminal to prompt at.

        Run non-interactively (a script, a CI step, an editor's run button) the
        prompt would hang forever on a read that never returns.
        """
        if not sys.stdin.isatty():
            return default
        try:
            got = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
        except EOFError:
            got = ""
        return got or default

    label_id = args.id or ask("id (lower_snake_case, permanent)")
    if not label_id:
        print("\n  No id given. Pass --id, or run this in a terminal to be asked.\n")
        return 1
    if label_id in ids:
        print(f"\n  '{label_id}' already exists.\n")
        return 1

    rule = args.rule or ask("decision_rule (when to use it, and when NOT to)")
    if not rule:
        print("\n  A decision_rule is required: it is what the model actually reads. "
              "Pass --rule.\n")
        return 1

    description = args.description or ask("description (report legend only)", rule[:60])
    used = {l.get("color") for l in data["features"]}
    colour = args.color or next((c for c in PALETTE if c not in used), "#94a3b8")

    after, before = args.after, args.before
    if not after and not before and sys.stdin.isatty():
        print(f"\n  Current order: {' > '.join(data['_display_precedence'])}")
        after = ask("place it after which label? (blank = last)")
    # --after / --before position the label in `_display_precedence`, which is the
    # precedence the model actually applies.
    order = list(data["_display_precedence"])
    if before and before in order:
        order.insert(order.index(before), label_id)
    elif after and after in order:
        order.insert(order.index(after) + 1, label_id)
    else:
        order.append(label_id)

    # In `labels` it always goes last, and that is a correctness requirement
    # rather than tidiness. `TAXONOMY` follows this array, and a label's position
    # in it is the integer `feature_id` written into every viewer JSON. Inserting
    # mid-array would shift every later index, and every fragment already
    # processed would silently recolour: FS-006 stores id 2 meaning
    # exposed_aggregate, which would become whatever landed at 2 instead.
    data["features"].append({
        "id": label_id, "color": colour, "description": description,
        "subtypes": ["unknown"], "decision_rule": rule,
    })
    data["_display_precedence"] = order
    save(data)

    folder = REFERENCE_DIR / label_id
    folder.mkdir(parents=True, exist_ok=True)

    print(f"\n  Added '{label_id}' ({colour})")
    print(f"  Precedence : {' > '.join(order)}")
    print(f"  feature_id : {len(data['labels']) - 1}  (appended last in 'labels', so the "
          f"ids already stored in viewer JSON keep their meaning)")
    print(f"  Folder: {folder.relative_to(REPO_ROOT)}  (empty; crop exemplars from "
          f"an atlas in 05_output/descriptors/)")
    print(f"\n  The prompt has changed, so the API cache is invalidated. Every "
          f"fragment needs\n  --force to stay comparable; do not compare across "
          f"that boundary.\n")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="show labels, precedence and exemplar counts")
    sub.add_parser("check", help="validate that labels and _display_precedence agree")
    sub.add_parser("folders", help="create reference_surfaces/<label>/ for every label")
    a = sub.add_parser("add", help="add a label to both places at once")
    a.add_argument("--id")
    a.add_argument("--color")
    a.add_argument("--rule", help="decision_rule: what the model actually reads")
    a.add_argument("--description", help="report legend only")
    a.add_argument("--after", help="place after this label in the decision order")
    a.add_argument("--before", help="place before this label")
    rm = sub.add_parser("remove", help="delete a label, if no output uses it")
    rm.add_argument("--id", required=True)
    rt = sub.add_parser("retire", help="hide a label from the prompt and the interface, "
                                       "keeping its id so stored data still resolves")
    rt.add_argument("--id", required=True)
    rt.add_argument("--undo", action="store_true", help="bring a retired label back")
    args = ap.parse_args()

    if not TAXONOMY_JSON.exists():
        print(f"\n  No taxonomy at {TAXONOMY_JSON}\n")
        sys.exit(1)
    data = load()

    if args.cmd == "add":
        sys.exit(cmd_add(data, args))
    if args.cmd == "remove":
        sys.exit(cmd_remove(data, args))
    if args.cmd == "retire":
        sys.exit(cmd_retire(data, args))
    if args.cmd == "check":
        sys.exit(1 if cmd_check(data) else 0)
    if args.cmd == "folders":
        sys.exit(cmd_folders(data))
    sys.exit(cmd_list(data))


if __name__ == "__main__":
    main()
