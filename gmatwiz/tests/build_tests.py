#!/usr/bin/env python3
"""
build_tests.py -- Assemble versioned GMAT Quant practice-test "forms" for GMATWiz.

Reads the legally-sourced, already-normalized question bank in ../content/ and
partitions it into mutually DISJOINT 21-question practice-test forms. (The GMAT
Focus Edition Quantitative Reasoning section is 21 Problem Solving questions in
45 minutes.) Forms never share a question id and never repeat a stem, so every
form is an independent, held-out set.

Sources (already normalized upstream; we only read them and preserve their
`source`/`license` fields verbatim):
    ../content/questions.json   231 items   AQuA-RAT (DeepMind), Apache-2.0
    ../content/seed.json         42 items   GMATWiz-authored (authored-gmatwiz)

Nothing new is scraped or fetched. No official/copyrighted GMAT material is used.

Determinism: a single seeded RNG (random.Random(20260101)) drives every random
choice, so re-running produces byte-for-byte identical output. Standard library
only (json, os, random, collections, hashlib).

Run:
    cd gmatwiz/tests && python3 build_tests.py
"""

import hashlib
import json
import os
import random
from collections import Counter, OrderedDict, defaultdict

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.normpath(os.path.join(HERE, "..", "content"))
QUESTIONS_PATH = os.path.join(CONTENT_DIR, "questions.json")
SEED_PATH = os.path.join(CONTENT_DIR, "seed.json")

# Year 2026 == GMAT Focus edition / import year (AQuA-RAT carries no intrinsic
# year), used only to version the generated library.
YEAR = 2026
YEAR_KEY = str(YEAR)

FORM_SIZE = 21          # questions per form (GMAT Focus Quant section length)
MIN_FORMS = 6
MAX_FORMS = 8
SECONDS = 2700          # 45 minutes, whole-section time budget
TARGET_MS = 128000      # per-question target pace (~2700s / 21)
RNG_SEED = 20260101

VALID_LETTERS = ("A", "B", "C", "D", "E")
DIFFICULTY_ORDER = ("easy", "medium", "hard")
# The exact key set (and order) required on every emitted form item.
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


def leaf(topic):
    """Short label for a taxonomy id, e.g. 'algebra::word_problems'."""
    parts = topic.split("::")
    return "::".join(parts[-2:]) if len(parts) >= 2 else topic


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

    return problems


def load_json_list(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        fail("%s does not contain a JSON array" % path)
    return data


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
# Pool construction
# --------------------------------------------------------------------------- #
def build_pool(origin_lists):
    """
    Merge origin item lists into one clean, de-duplicated pool.

    De-duplication is by question id AND by normalized stem; the first
    occurrence wins (so questions.json takes precedence over seed.json for any
    coincidental collision). Malformed items are skipped rather than aborting
    the build -- the final forms are still validated strictly below.
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
# Stratified selection + distribution
# --------------------------------------------------------------------------- #
def allocate(topic_counts, total_needed):
    """
    Largest-remainder apportionment of `total_needed` slots across topics,
    proportional to each topic's share of the pool and capped at availability.
    Deterministic tie-breaks keep the result reproducible.
    """
    total_avail = sum(topic_counts.values())
    if total_needed > total_avail:
        fail("need %d items but pool only has %d" % (total_needed, total_avail))

    topics = sorted(topic_counts, key=lambda t: (-topic_counts[t], t))
    alloc = {}
    remainder = {}
    for topic in topics:
        ideal = total_needed * topic_counts[topic] / total_avail
        base = min(int(ideal), topic_counts[topic])
        alloc[topic] = base
        remainder[topic] = ideal - base

    leftover = total_needed - sum(alloc.values())
    order = sorted(topics, key=lambda t: (-remainder[t], -topic_counts[t], t))
    cursor = 0
    guard = 0
    while leftover > 0:
        topic = order[cursor % len(order)]
        if alloc[topic] < topic_counts[topic]:
            alloc[topic] += 1
            leftover -= 1
        cursor += 1
        guard += 1
        if guard > 10 * total_needed + len(order) + 10:
            fail("allocation failed to converge")
    return alloc


def difficulty_interleaved(items, rng):
    """
    Order a topic's items so difficulties are interleaved (easy, medium, hard,
    repeat). Scarce difficulties surface early, so taking the first N keeps a
    representative difficulty mix and scatters the rare ones across forms.
    """
    buckets = {d: [] for d in DIFFICULTY_ORDER}
    for item in items:
        buckets[item["difficulty"]].append(item)
    for diff in DIFFICULTY_ORDER:
        rng.shuffle(buckets[diff])

    ordered = []
    idx = {d: 0 for d in DIFFICULTY_ORDER}
    remaining = sum(len(b) for b in buckets.values())
    while remaining > 0:
        for diff in DIFFICULTY_ORDER:
            if idx[diff] < len(buckets[diff]):
                ordered.append(buckets[diff][idx[diff]])
                idx[diff] += 1
                remaining -= 1
    return ordered


def build_forms(pool, n_forms, rng):
    """
    Select n_forms * FORM_SIZE items stratified by topic, then deal them into
    forms via continuous round-robin over a topic-grouped list. Because the
    total is an exact multiple of n_forms, every form receives exactly
    FORM_SIZE items, and each topic block is spread evenly across the forms.
    """
    total_needed = n_forms * FORM_SIZE

    by_topic = defaultdict(list)
    for item in pool:
        by_topic[item["topic"]].append(item)
    topic_counts = {t: len(v) for t, v in by_topic.items()}
    alloc = allocate(topic_counts, total_needed)

    # Group selected items by topic (largest topics first) so the round-robin
    # deal below distributes each topic proportionally over the forms.
    topic_order = sorted(
        by_topic, key=lambda t: (-alloc[t], -topic_counts[t], t)
    )
    selected = []
    for topic in topic_order:
        ordered = difficulty_interleaved(by_topic[topic], rng)
        selected.extend(ordered[: alloc[topic]])

    if len(selected) != total_needed:
        fail("selected %d items, expected %d" % (len(selected), total_needed))

    forms = [[] for _ in range(n_forms)]
    for position, item in enumerate(selected):
        forms[position % n_forms].append(item)

    # Mix each form's order so it reads like a real (topic-shuffled) test.
    for form in forms:
        rng.shuffle(form)

    return forms, alloc


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_forms(forms, n_forms):
    if len(forms) != n_forms:
        fail("expected %d forms, built %d" % (n_forms, len(forms)))

    all_ids = []
    all_stems = []
    for i, form in enumerate(forms, start=1):
        if len(form) != FORM_SIZE:
            fail("form %d has %d items (expected %d)" % (i, len(form), FORM_SIZE))
        for item in form:
            problems = item_problems(item)
            if problems:
                fail("form %d item %s invalid: %s"
                     % (i, item.get("_id"), "; ".join(problems)))
            all_ids.append(item["_id"])
            all_stems.append(item["_nstem"])

    if len(set(all_ids)) != len(all_ids):
        dupes = [k for k, c in Counter(all_ids).items() if c > 1]
        fail("question id(s) shared across forms: %s" % dupes)
    if len(set(all_stems)) != len(all_stems):
        fail("duplicate stem(s) detected across forms")


# --------------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------------- #
def emit_item(item):
    out = OrderedDict()
    out["stem"] = item["stem"]
    out["options"] = OrderedDict((L, item["options"][L]) for L in VALID_LETTERS)
    out["correct"] = item["correct"]
    out["explanation"] = item.get("explanation", "")
    out["topic"] = item["topic"]
    out["difficulty"] = item["difficulty"]
    out["source"] = item["source"]
    out["license"] = item["license"]
    return out


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def emit_forms(forms):
    """Write per-form files and index.json; return the index entries."""
    year_dir = os.path.join(HERE, YEAR_KEY)
    os.makedirs(year_dir, exist_ok=True)

    index_entries = []
    written = []
    for i, form in enumerate(forms, start=1):
        fid = "%d-form-%02d" % (YEAR, i)
        label = "%d Practice Test %d" % (YEAR, i)

        topic_counts = Counter(item["topic"] for item in form)
        topics = OrderedDict(
            sorted(topic_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        sources = sorted({source_label(item) for item in form})

        form_obj = OrderedDict()
        form_obj["id"] = fid
        form_obj["year"] = YEAR
        form_obj["label"] = label
        form_obj["seconds"] = SECONDS
        form_obj["target_ms"] = TARGET_MS
        form_obj["items"] = [emit_item(item) for item in form]

        form_path = os.path.join(year_dir, fid + ".json")
        write_json(form_path, form_obj)
        written.append(form_path)

        entry = OrderedDict()
        entry["id"] = fid
        entry["year"] = YEAR
        entry["label"] = label
        entry["count"] = len(form)
        entry["topics"] = topics
        entry["sources"] = sources
        index_entries.append(entry)

    index_obj = OrderedDict()
    index_obj["schema_version"] = "1.0"
    index_obj["exam"] = "GMAT Focus Edition"
    index_obj["section"] = "Quantitative Reasoning"
    index_obj["question_type"] = "Problem Solving"
    index_obj["years"] = OrderedDict()
    index_obj["years"][YEAR_KEY] = index_entries

    index_path = os.path.join(HERE, "index.json")
    write_json(index_path, index_obj)
    written.append(index_path)

    return index_entries, written


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def print_summary(pool, kept_per_origin, skipped, n_forms, forms, alloc,
                  index_entries, written):
    line = "=" * 74
    print(line)
    print("GMATWiz -- GMAT Quant practice-test form builder")
    print(line)

    print("\nInputs (read-only, from ../content/):")
    print("  questions.json : %d clean items kept (AQuA-RAT, Apache-2.0)"
          % kept_per_origin.get("questions", 0))
    print("  seed.json      : %d clean items kept (authored-gmatwiz)"
          % kept_per_origin.get("seed", 0))
    print("  clean pool     : %d unique items" % len(pool))
    if skipped:
        print("  skipped        : %s"
              % ", ".join("%s=%d" % (k, v) for k, v in sorted(skipped.items())))
    else:
        print("  skipped        : none")

    print("\nBuild decision:")
    print("  forms built    : %d (allowed range %d-%d)"
          % (n_forms, MIN_FORMS, MAX_FORMS))
    print("  questions used : %d of %d (%d per form)"
          % (n_forms * FORM_SIZE, len(pool), FORM_SIZE))

    used_topics = sorted(
        alloc, key=lambda t: (-alloc[t], t)
    )
    print("\nTarget topic allocation across all forms (largest-remainder):")
    for topic in used_topics:
        if alloc[topic]:
            print("  %-34s %3d  (~%.1f per form)"
                  % (leaf(topic), alloc[topic], alloc[topic] / n_forms))

    print("\nPer-form composition:")
    overall_diff = Counter()
    for entry, form in zip(index_entries, forms):
        topics = Counter(item["topic"] for item in form)
        diffs = Counter(item["difficulty"] for item in form)
        overall_diff.update(diffs)
        topic_str = ", ".join(
            "%s:%d" % (leaf(t), c)
            for t, c in sorted(topics.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        diff_str = ", ".join(
            "%s:%d" % (d, diffs.get(d, 0)) for d in DIFFICULTY_ORDER
        )
        print("  %s (%s)" % (entry["id"], entry["label"]))
        print("      count   : %d" % entry["count"])
        print("      topics  : %s" % topic_str)
        print("      difficulty: %s" % diff_str)
        print("      sources : %s" % "; ".join(entry["sources"]))

    print("\nOverall difficulty mix across all forms: %s"
          % ", ".join("%s:%d" % (d, overall_diff.get(d, 0))
                      for d in DIFFICULTY_ORDER))

    print("\nFiles written:")
    for path in written:
        print("  %s" % os.path.relpath(path, HERE))

    print("\nVALIDATION: PASSED -- %d forms x %d items, all disjoint, "
          "options A-E present, correct-in-options verified." % (n_forms, FORM_SIZE))
    print(line)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    rng = random.Random(RNG_SEED)

    questions = load_json_list(QUESTIONS_PATH)
    origin_lists = [("questions", questions)]
    if os.path.exists(SEED_PATH):
        origin_lists.append(("seed", load_json_list(SEED_PATH)))

    pool, skipped, kept_per_origin = build_pool(origin_lists)

    total_clean = len(pool)
    max_possible = total_clean // FORM_SIZE
    if max_possible < MIN_FORMS:
        fail("only %d clean items -> cannot build the minimum of %d forms (%d needed)"
             % (total_clean, MIN_FORMS, MIN_FORMS * FORM_SIZE))

    # Prefer the maximum (8) when questions.json alone supplies enough clean
    # items for it; otherwise take as many complete forms as the pool supports.
    clean_from_questions = kept_per_origin.get("questions", 0)
    if clean_from_questions >= MAX_FORMS * FORM_SIZE:
        n_forms = MAX_FORMS
    else:
        n_forms = min(MAX_FORMS, max_possible)
    n_forms = max(MIN_FORMS, min(MAX_FORMS, n_forms))

    forms, alloc = build_forms(pool, n_forms, rng)
    validate_forms(forms, n_forms)
    index_entries, written = emit_forms(forms)

    print_summary(pool, kept_per_origin, skipped, n_forms, forms, alloc,
                  index_entries, written)


if __name__ == "__main__":
    try:
        main()
    except BuildError as exc:
        raise SystemExit("BUILD FAILED: %s" % exc)
