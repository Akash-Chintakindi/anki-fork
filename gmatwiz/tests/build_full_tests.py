#!/usr/bin/env python3
"""
build_full_tests.py -- Assemble FULL-length, 3-section GMAT Focus Edition
practice-test "forms" for GMATWiz.

Where build_tests.py produces Quant-only forms, this builder assembles complete
GMAT Focus Edition test forms with all three scored sections:

    Quantitative Reasoning : 21 items / 45 min
    Verbal Reasoning       : 23 items / 45 min
    Data Insights          : 20 items / 45 min
                             --------
    total                    64 items

Content banks (read-only; every item keeps its own `source`/`license` verbatim):
    ../content/questions.json          Quant  -- AQuA-RAT (DeepMind), Apache-2.0
    ../content/seed.json               Quant  -- GMATWiz authored
    ../content/verbal_seed.json        Verbal -- GMATWiz authored (standalone)
    ../content/verbal_questions.json   Verbal -- GMATWiz authored (standalone)
    ../content/verbal_rc_questions.json Verbal -- GMATWiz authored (passage groups)
    ../content/di_seed.json            DI     -- GMATWiz authored
    ../content/di_questions.json       DI     -- GMATWiz authored

Nothing is scraped or fetched; no official/copyrighted GMAT material is used.

Selection strategy
------------------
* Quant is deep (~850 clean items), so the three forms' Quant sections are
  mutually DISJOINT (they never share an item).
* Verbal (~66 clean items) and DI (~24 clean items) are thin -- three full
  sections need 69 and 60 slots respectively, more than the banks hold. Those
  sections are therefore drawn with modulo WRAPAROUND: every form still gets a
  full 23 / 20 items, some items are REUSED across forms, but because each
  section size is <= its pool size no item repeats *within* a single section.

Determinism
-----------
A single seeded RNG (random.Random(20260101), matching build_tests.py) drives
every shuffle, and the index is rebuilt idempotently, so re-running produces
byte-for-byte identical output. Standard library only (json, os, random,
collections, hashlib).

Run:
    cd gmatwiz/tests && python3 build_full_tests.py
"""

import hashlib
import json
import os
import random
from collections import Counter, OrderedDict

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.normpath(os.path.join(HERE, "..", "content"))

QUANT_QUESTIONS = os.path.join(CONTENT_DIR, "questions.json")
QUANT_SEED = os.path.join(CONTENT_DIR, "seed.json")
VERBAL_SEED = os.path.join(CONTENT_DIR, "verbal_seed.json")
VERBAL_QUESTIONS = os.path.join(CONTENT_DIR, "verbal_questions.json")
VERBAL_RC = os.path.join(CONTENT_DIR, "verbal_rc_questions.json")
DI_SEED = os.path.join(CONTENT_DIR, "di_seed.json")
DI_QUESTIONS = os.path.join(CONTENT_DIR, "di_questions.json")

# 2026 == GMAT Focus edition / import year, used only to version the library.
YEAR = 2026
YEAR_KEY = str(YEAR)
RNG_SEED = 20260101
N_FORMS = 3
SECONDS = 2700          # 45 minutes per section (whole-section time budget)

FORM_IDS = ("2026-full-01", "2026-full-02", "2026-full-03")
FORM_LABELS = ("Full Practice Test 1", "Full Practice Test 2", "Full Practice Test 3")

# Section emission order and GMAT Focus Edition section sizes.
SECTION_ORDER = ("quant", "verbal", "di")
SECTION_LABEL = {
    "quant": "Quantitative Reasoning",
    "verbal": "Verbal Reasoning",
    "di": "Data Insights",
}
SECTION_SIZE = {"quant": 21, "verbal": 23, "di": 20}
# Quant is deep enough to keep disjoint across forms; verbal/di must reuse.
SECTION_DISJOINT = {"quant": True, "verbal": False, "di": False}

VALID_LETTERS = ("A", "B", "C", "D", "E")
DIFFICULTY_ORDER = ("easy", "medium", "hard")
# The exact key set required on every emitted item (passage is optional/extra).
ITEM_FIELDS = (
    "stem", "options", "correct", "explanation",
    "topic", "difficulty", "source", "license",
)


class BuildError(Exception):
    """Raised on any validation/consistency violation so the build fails loudly."""


def fail(msg):
    raise BuildError(msg)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def norm_stem(text):
    """Whitespace-collapsed, lower-cased stem used for duplicate detection."""
    return " ".join(str(text).split()).lower()


def load_json_list(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        fail("%s does not contain a JSON array" % path)
    return data


def item_problems(item):
    """Return a list of structural problems with an item (empty == valid)."""
    problems = []
    for field in ITEM_FIELDS:
        if field not in item:
            problems.append("missing field '%s'" % field)

    stem = item.get("stem")
    if not isinstance(stem, str) or not stem.strip():
        problems.append("empty/invalid stem")

    opts = item.get("options")
    if not isinstance(opts, dict):
        problems.append("options is not an object")
    else:
        for letter in VALID_LETTERS:
            val = opts.get(letter)
            if not isinstance(val, str) or not val.strip():
                problems.append("option %s missing/empty" % letter)
        extra = [k for k in opts if k not in VALID_LETTERS]
        if extra:
            problems.append("unexpected option keys %r" % extra)

    correct = item.get("correct")
    if correct not in VALID_LETTERS:
        problems.append("correct %r not in A-E" % (correct,))
    elif isinstance(opts, dict) and correct not in opts:
        problems.append("correct letter %r absent from options" % (correct,))

    if item.get("difficulty") not in DIFFICULTY_ORDER:
        problems.append("difficulty %r invalid" % (item.get("difficulty"),))

    for field in ("topic", "source", "license"):
        val = item.get(field)
        if not isinstance(val, str) or not val.strip():
            problems.append("empty/invalid %s" % field)

    if not isinstance(item.get("explanation", ""), str):
        problems.append("explanation is not a string")

    # passage is optional, but if present it must be a non-empty string.
    if "passage" in item and item["passage"] is not None:
        if not isinstance(item["passage"], str) or not item["passage"].strip():
            problems.append("passage present but empty/invalid")

    return problems


def source_label(item):
    """Human-readable source/license label derived from the item's own fields."""
    lic = item.get("license", "")
    src = item.get("source", "")
    if lic == "Apache-2.0" or "AQuA" in src:
        return "AQuA-RAT (DeepMind), Apache-2.0"
    if lic == "authored-gmatwiz" or "GMATWiz" in src:
        return "GMATWiz authored (authored-gmatwiz)"
    return "%s (%s)" % (src or "unknown-source", lic or "unknown-license")


# --------------------------------------------------------------------------- #
# Content loading
# --------------------------------------------------------------------------- #
def flatten_rc_groups(groups):
    """
    Flatten passage-grouped RC data into standalone items.

    Each question in a group inherits the group's passage/source/license (the
    questions themselves carry only stem/options/correct/explanation/topic/
    difficulty), while keeping its own, more specific topic. The result matches
    the standalone verbal item schema, with a `passage` field carrying the
    shared stimulus.
    """
    flat = []
    for group in groups:
        passage = group.get("passage")
        g_source = group.get("source")
        g_license = group.get("license")
        g_topic = group.get("topic")
        for question in group.get("questions", []):
            item = dict(question)
            if passage:
                item["passage"] = passage
            if not item.get("source"):
                item["source"] = g_source
            if not item.get("license"):
                item["license"] = g_license
            if not item.get("topic"):
                item["topic"] = g_topic
            flat.append(item)
    return flat


def build_pool(origin_lists):
    """
    Merge origin item lists into one clean, de-duplicated pool.

    De-duplication is by question id AND by normalized stem; the first
    occurrence wins. Malformed items are skipped (the final forms are still
    validated strictly below). Returns (pool, skipped, kept_per_origin).
    """
    pool = []
    seen_ids = set()
    seen_stems = set()
    skipped = Counter()
    kept_per_origin = Counter()

    for origin, items in origin_lists:
        for item in items:
            if item_problems(item):
                skipped["malformed"] += 1
                continue

            iid = item.get("id")
            if not isinstance(iid, str) or not iid.strip():
                iid = "gen-" + hashlib.sha1(
                    norm_stem(item["stem"]).encode("utf-8")
                ).hexdigest()[:12]

            nstem = norm_stem(item["stem"])
            if iid in seen_ids:
                skipped["duplicate_id"] += 1
                continue
            if nstem in seen_stems:
                skipped["duplicate_stem"] += 1
                continue

            seen_ids.add(iid)
            seen_stems.add(nstem)
            record = dict(item)
            record["_id"] = iid
            record["_origin"] = origin
            record["_nstem"] = nstem
            pool.append(record)
            kept_per_origin[origin] += 1

    return pool, skipped, kept_per_origin


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
def select_sections(pool, size, disjoint, rng):
    """
    Deal `pool` into N_FORMS section lists of `size` items each.

    disjoint=True  -> consecutive, non-overlapping chunks: the forms share no
                      item (used for the deep Quant bank).
    disjoint=False -> sliding windows taken with modulo wraparound over a single
                      shuffled order: every form still gets a full `size` items,
                      items may be REUSED across forms, but no item repeats
                      within a form because size <= len(pool).
    """
    order = list(pool)
    rng.shuffle(order)
    n = len(order)

    forms = []
    if disjoint:
        if n < N_FORMS * size:
            fail("need %d disjoint items but pool only has %d"
                 % (N_FORMS * size, n))
        for f in range(N_FORMS):
            forms.append(order[f * size:(f + 1) * size])
    else:
        if size > n:
            fail("section size %d exceeds pool size %d (cannot keep a form "
                 "internally unique)" % (size, n))
        for f in range(N_FORMS):
            window = [order[(f * size + j) % n] for j in range(size)]
            forms.append(window)

    # Shuffle each section so it reads like a real (mixed-order) test.
    for form in forms:
        rng.shuffle(form)
    return forms


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_section(section, forms, pool_size):
    """Strictly validate one section across all forms; return reuse stats."""
    size = SECTION_SIZE[section]
    if len(forms) != N_FORMS:
        fail("%s: expected %d forms, got %d" % (section, N_FORMS, len(forms)))

    id_sets = []
    for f, form in enumerate(forms, start=1):
        if len(form) != size:
            fail("%s form %d has %d items (expected %d)"
                 % (section, f, len(form), size))
        ids, stems = [], []
        for item in form:
            problems = item_problems(item)
            if problems:
                fail("%s form %d item %s invalid: %s"
                     % (section, f, item.get("_id"), "; ".join(problems)))
            ids.append(item["_id"])
            stems.append(item["_nstem"])
        if len(set(ids)) != len(ids):
            dups = [k for k, c in Counter(ids).items() if c > 1]
            fail("%s form %d has duplicate id(s) within the section: %s"
                 % (section, f, dups))
        if len(set(stems)) != len(stems):
            fail("%s form %d has duplicate stem(s) within the section"
                 % (section, f))
        id_sets.append(set(ids))

    all_ids = [i for s in id_sets for i in s]
    counts = Counter(all_ids)
    reused_items = sum(1 for c in counts.values() if c > 1)

    if SECTION_DISJOINT[section] and reused_items:
        shared = [k for k, c in counts.items() if c > 1]
        fail("%s must be DISJOINT across forms but %d item(s) are shared: %s"
             % (section, reused_items, shared))

    return {
        "pool_size": pool_size,
        "slots": len(all_ids),
        "distinct_used": len(counts),
        "reused_items": reused_items,
        "in_all_forms": sum(1 for c in counts.values() if c == N_FORMS),
        "reused_slots": len(all_ids) - len(counts),
    }


# --------------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------------- #
def target_ms(count):
    """Per-question target pace in ms: round(section_seconds * 1000 / count)."""
    return round(SECONDS * 1000 / count)


def emit_item(item):
    """Emit an item with keys in the required order; passage only when present."""
    out = OrderedDict()
    out["stem"] = item["stem"]
    out["options"] = OrderedDict((L, item["options"][L]) for L in VALID_LETTERS)
    out["correct"] = item["correct"]
    out["explanation"] = item.get("explanation", "")
    out["topic"] = item["topic"]
    out["difficulty"] = item["difficulty"]
    out["source"] = item["source"]
    out["license"] = item["license"]
    passage = item.get("passage")
    if isinstance(passage, str) and passage.strip():
        out["passage"] = passage
    return out


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def build_form_obj(idx, sections_by_form):
    form_obj = OrderedDict()
    form_obj["id"] = FORM_IDS[idx]
    form_obj["year"] = YEAR
    form_obj["label"] = FORM_LABELS[idx]
    form_obj["full"] = True
    form_obj["sections"] = []
    for section in SECTION_ORDER:
        items = sections_by_form[section][idx]
        sec = OrderedDict()
        sec["section"] = section
        sec["label"] = SECTION_LABEL[section]
        sec["seconds"] = SECONDS
        sec["target_ms"] = target_ms(len(items))
        sec["items"] = [emit_item(item) for item in items]
        form_obj["sections"].append(sec)
    return form_obj


def build_index_entry(idx, sections_by_form):
    sources = set()
    for section in SECTION_ORDER:
        for item in sections_by_form[section][idx]:
            sources.add(source_label(item))

    entry = OrderedDict()
    entry["id"] = FORM_IDS[idx]
    entry["year"] = YEAR
    entry["label"] = FORM_LABELS[idx]
    entry["full"] = True
    entry["count"] = sum(SECTION_SIZE[s] for s in SECTION_ORDER)
    entry["sections"] = OrderedDict((s, SECTION_SIZE[s]) for s in SECTION_ORDER)
    entry["sources"] = sorted(sources)
    return entry


def emit_forms(sections_by_form):
    """Write the per-form files; return (index_entries, written_paths)."""
    year_dir = os.path.join(HERE, YEAR_KEY)
    os.makedirs(year_dir, exist_ok=True)

    index_entries = []
    written = []
    for idx in range(N_FORMS):
        form_obj = build_form_obj(idx, sections_by_form)
        form_path = os.path.join(year_dir, FORM_IDS[idx] + ".json")
        write_json(form_path, form_obj)
        written.append(form_path)
        index_entries.append(build_index_entry(idx, sections_by_form))
    return index_entries, written


def update_index(index_entries):
    """
    Append the full-form entries to the existing index.json without disturbing
    the quant-only forms or the top-level fields. Idempotent: any prior full
    entries are stripped first so re-runs stay byte-identical.
    """
    index_path = os.path.join(HERE, "index.json")
    with open(index_path, "r", encoding="utf-8") as handle:
        index = json.load(handle, object_pairs_hook=OrderedDict)

    years = index.setdefault("years", OrderedDict())
    existing = years.get(YEAR_KEY, [])
    full_ids = set(FORM_IDS)
    kept = [e for e in existing
            if not e.get("full") and e.get("id") not in full_ids]
    years[YEAR_KEY] = kept + index_entries

    write_json(index_path, index)
    total_forms = sum(len(v) for v in years.values())
    return index_path, total_forms, len(kept)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def print_summary(pools, kept, stats, sections_by_form, index_entries,
                  written, index_path, total_forms, kept_existing):
    line = "=" * 74
    print(line)
    print("GMATWiz -- FULL 3-section GMAT Focus practice-test form builder")
    print(line)

    print("\nContent banks (read-only, from ../content/):")
    print("  Quant  : %3d clean items  (questions.json=%d, seed.json=%d)"
          % (len(pools["quant"]), kept["quant"].get("questions", 0),
             kept["quant"].get("seed", 0)))
    print("  Verbal : %3d clean items  (verbal_seed=%d, verbal_questions=%d, "
          "verbal_rc=%d)"
          % (len(pools["verbal"]), kept["verbal"].get("verbal_seed", 0),
             kept["verbal"].get("verbal_questions", 0),
             kept["verbal"].get("verbal_rc", 0)))
    print("  DI     : %3d clean items  (di_seed=%d, di_questions=%d)"
          % (len(pools["di"]), kept["di"].get("di_seed", 0),
             kept["di"].get("di_questions", 0)))

    print("\nForms built: %d (%s)" % (N_FORMS, ", ".join(FORM_IDS)))
    print("Section shape: Quant %d + Verbal %d + DI %d = %d items/form; "
          "each section %ds."
          % (SECTION_SIZE["quant"], SECTION_SIZE["verbal"], SECTION_SIZE["di"],
             sum(SECTION_SIZE.values()), SECONDS))
    print("Per-section target pace (ms/question): quant=%d, verbal=%d, di=%d"
          % (target_ms(SECTION_SIZE["quant"]),
             target_ms(SECTION_SIZE["verbal"]),
             target_ms(SECTION_SIZE["di"])))

    print("\nPer-form, per-section item counts:")
    for idx, entry in enumerate(index_entries):
        counts = ", ".join(
            "%s=%d" % (s, len(sections_by_form[s][idx])) for s in SECTION_ORDER
        )
        print("  %s (%s): %s  [total %d]"
              % (entry["id"], entry["label"], counts, entry["count"]))

    print("\nCross-form reuse (quant is disjoint by design):")
    for section in SECTION_ORDER:
        st = stats[section]
        mode = "DISJOINT" if SECTION_DISJOINT[section] else "wraparound reuse"
        print("  %-6s [%s]: pool=%d, slots=%d (%d/form), distinct used=%d, "
              "reused across forms=%d (of which in all %d forms=%d), "
              "duplicate placements=%d"
              % (section, mode, st["pool_size"], st["slots"],
                 SECTION_SIZE[section], st["distinct_used"],
                 st["reused_items"], N_FORMS, st["in_all_forms"],
                 st["reused_slots"]))

    print("\nFiles written:")
    for path in written:
        print("  %s" % os.path.relpath(path, HERE))
    print("  %s (updated; kept %d existing quant-only form entries)"
          % (os.path.relpath(index_path, HERE), kept_existing))

    print("\nTotal forms now in index.json (all years): %d" % total_forms)
    print("\nVALIDATION: PASSED -- %d full forms x (21+23+20)=64 items; options "
          "A-E present, correct-in-options verified; quant disjoint; each "
          "section internally unique." % N_FORMS)
    print(line)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    rng = random.Random(RNG_SEED)

    # ---- Load + de-duplicate each section's content bank (read-only) ----
    quant_pool, _, quant_kept = build_pool([
        ("questions", load_json_list(QUANT_QUESTIONS)),
        ("seed", load_json_list(QUANT_SEED)),
    ])
    verbal_pool, _, verbal_kept = build_pool([
        ("verbal_seed", load_json_list(VERBAL_SEED)),
        ("verbal_questions", load_json_list(VERBAL_QUESTIONS)),
        ("verbal_rc", flatten_rc_groups(load_json_list(VERBAL_RC))),
    ])
    di_pool, _, di_kept = build_pool([
        ("di_seed", load_json_list(DI_SEED)),
        ("di_questions", load_json_list(DI_QUESTIONS)),
    ])
    pools = {"quant": quant_pool, "verbal": verbal_pool, "di": di_pool}
    kept = {"quant": quant_kept, "verbal": verbal_kept, "di": di_kept}

    # ---- Deal each section into the three forms (deterministic order) ----
    sections_by_form = {}
    for section in SECTION_ORDER:
        sections_by_form[section] = select_sections(
            pools[section], SECTION_SIZE[section],
            SECTION_DISJOINT[section], rng,
        )

    # ---- Validate every section strictly; gather reuse stats ----
    stats = {}
    for section in SECTION_ORDER:
        stats[section] = validate_section(
            section, sections_by_form[section], len(pools[section]),
        )

    # ---- Emit form files + append to index.json ----
    index_entries, written = emit_forms(sections_by_form)
    index_path, total_forms, kept_existing = update_index(index_entries)
    written.append(index_path)

    print_summary(pools, kept, stats, sections_by_form, index_entries,
                  written, index_path, total_forms, kept_existing)


if __name__ == "__main__":
    try:
        main()
    except BuildError as exc:
        raise SystemExit("BUILD FAILED: %s" % exc)
