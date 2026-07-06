#!/usr/bin/env python3
"""Build the shared 50,000-card GMAT deck used by the speed benchmark (PRD 14.5/14.6).

This is the "make bench" substrate: a synthetic-but-realistic GMAT::Quant deck of
50,000 unique Problem-Solving cards spread across every Quant taxonomy leaf, with
per-topic mastery set and topic-aware scheduling turned on, so gmat_bench.py can
measure button-ack / next-card / dashboard / sync / memory on a real 50k engine.

Design choices (kept honest in proof/bench.txt):
  * Cards are driven into the SAME shared Rust engine as the app, via the exact
    importer the app uses (anki.gmatwiz.import_questions -> "GMAT PS" notes).
  * Stems are made unique by construction: each card's numbers are a bijection of
    its global index, so the importer's stem-hash dedup never collapses two cards
    (we verify the final count == --count). Wording is varied for realism only.
  * Per-topic mastery is set through the engine change under test
    (col._backend.set_topic_mastery) and topic-aware scheduling is enabled, so the
    scheduler's topic reorder path is actually exercised.
  * A realistic fraction of cards is seeded into FSRS "review" state (due today,
    with matching revlog rows) so the topic-aware REVIEW reorder does real work and
    the dashboard scores compute over genuine history - not an all-new deck.
  * Idempotent: if the deck is already at --count cards, it is left untouched.

Usage (drive the prebuilt engine; do NOT rebuild the project):
  PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python \
      gmatwiz/bench/make_bench_deck.py --path out/bench/col.anki2 --count 50000 --seed 7
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

# --- repo-relative imports -------------------------------------------------
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]  # <repo>/gmatwiz/bench/make_bench_deck.py -> <repo>
_CONTENT = _REPO / "gmatwiz" / "content"
_OUT_PYLIB = _REPO / "out" / "pylib"
for _p in (str(_CONTENT), str(_OUT_PYLIB)):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import taxonomy  # noqa: E402  (gmatwiz/content/taxonomy.py: QUANT_TOPICS, etc.)
from anki.collection import Collection  # noqa: E402
import anki.gmatwiz as gw  # noqa: E402

DECK_NAME = "GMAT::Quant"
NOTETYPE_NAME = gw.GMAT_PS_NOTETYPE_NAME  # "GMAT PS"
# Anki's deck-config validation silently reverts new/rev perDay to the default if
# it exceeds 9999 (the app's max), so we use the largest value that persists. This
# makes the scheduler gather up to ~9999 review + ~9999 new of the 50k into the
# active session queue - a large, representative queue on a 50k-card collection.
MAX_PER_DAY = 9999
# All 18 Quant Problem-Solving leaves (gmat::quant::<cat>::<leaf>). The shared 50k
# deck is a single Quant deck so scheduling + gmat_scores stay clean and match the
# validated engine-driver recipe.
LEAVES = list(taxonomy.QUANT_TOPICS)

# Bijection radix: pick three coprime-ish moduli whose product exceeds any --count
# we support, so (a, b, c) is a distinct triple for every global index i.
_MODS = (97, 89, 83)  # 97*89*83 = 716,339 distinct triples

# Wording variety (realism only; uniqueness comes from the numbers).
_NAMES = [
    "Alex", "Bella", "Chen", "Divya", "Emeka", "Farah", "Goro", "Hana",
    "Ivan", "Jamila", "Kofi", "Lena", "Mateo", "Nadia", "Omar", "Priya",
    "Quinn", "Rosa", "Sanjay", "Tara", "Uma", "Viktor", "Wen", "Ximena",
    "Yara", "Zane",
]
_ITEMS = [
    "widgets", "tickets", "beakers", "ledgers", "marbles", "crates",
    "sensors", "coupons", "samples", "packets", "tokens", "reels",
]
_PLACES = [
    "Aventine", "Brookline", "Calder", "Dunmore", "Elmridge", "Fairhaven",
    "Granby", "Holloway", "Ironwood", "Junction City",
]

# Per-leaf stem templates. {a} {b} {c} are the unique numbers; {who}/{item}/{place}
# add human-readable variety. Each template names its topic so the card reads on-topic.
_TEMPLATES: dict[str, list[str]] = {
    "number_properties": [
        "If n is a positive integer and n = {a}\u00b7k + {b} for some integer k, what is the remainder when {a2} is divided by {a}?",
        "The units digit of the integer {a}{b} raised to a positive power cycles; what is the units digit of {a} multiplied by {c}?",
        "How many positive divisors does the integer {prod} have if it is written as a product of the primes below {a}?",
    ],
    "fractions": [
        "{who} filled {a}/{b} of a tank and then drained {c}/{bb} of what remained. What fraction of the tank is now full?",
        "What is the value of the fraction ({a}/{b}) + ({c}/{bb}) expressed in lowest terms?",
    ],
    "decimals": [
        "When {a}.{b} is rounded to the nearest tenth and multiplied by {c}, what is the result?",
        "The decimal {a}.{b}{c} is closest to which of the following values?",
    ],
    "percents": [
        "A price of ${sum} is first increased by {a} percent and then decreased by {b} percent. What is the final price?",
        "{who} scored {a} on a test out of {sum}; approximately what percent of the questions did {who} answer correctly?",
        "If {a} percent of a number is {prod}, what is {b} percent of that same number?",
    ],
    "ratios_proportions": [
        "In {place}, the ratio of {item} to workers is {a} : {b}. If there are {prod} {item}, how many workers are there?",
        "Two quantities are in the ratio {a} : {b} : {c}; if the smallest is {a}, what is the largest?",
    ],
    "exponents_roots": [
        "If 2^{a} \u00b7 2^{b} = 2^x, and the square root of {prod} is an integer, what is x?",
        "What is the value of {a} raised to the power {b}, divided by {a} raised to the power {c}?",
    ],
    "statistics": [
        "The set {{{a}, {b}, {c}, {bb}, {cc}}} has what arithmetic mean, and does its median exceed its mean?",
        "{who}'s {a} scores have an average of {b}; if one more score of {sum} is added, what is the new average?",
    ],
    "sets": [
        "In a survey of {sum} students, {a} study French and {b} study German; if {c} study neither, how many study both?",
        "Set S has {a} elements and set T has {b}; if their union has {sum} elements, how many are in the intersection?",
    ],
    "counting": [
        "In how many ways can {who} arrange {a} distinct {item} on a shelf that holds exactly {b} of them?",
        "A committee of {b} is chosen from {a} candidates from {place}; how many distinct committees are possible?",
    ],
    "probability": [
        "A jar holds {a} red and {b} blue {item}; if {c} are drawn at random without replacement, what is the probability all are red?",
        "The probability that {who} wins a round is {a}/{sum}; what is the probability of winning {b} independent rounds in a row?",
    ],
    "linear_equations": [
        "Solve for x: {a}x + {b} = {c}x - {bb}. What is the value of x?",
        "The system {a}x + {b}y = {sum} and {c}x - y = {b} has what value of x?",
    ],
    "quadratics": [
        "If x^2 - {sum}x + {prod} = 0, what is the larger of the two roots?",
        "The quadratic x^2 + {a}x - {prod} = 0 has roots that differ by how much?",
    ],
    "inequalities": [
        "For how many integers x does the inequality {a} < {b}x - {c} <= {sum} hold?",
        "If {a}x - {b} >= {c}, what is the least integer value of x that satisfies the inequality?",
    ],
    "absolute_value": [
        "How many integer solutions does the equation |{b}x - {a}| = {c} have, and what is their sum?",
        "For which value of x is the absolute value |x - {a}| + |x - {sum}| minimized?",
    ],
    "functions": [
        "If f(x) = {a}x + {b}, what is the value of f({c}) - f({a})?",
        "A function is defined by g(x) = x^2 - {a}; what is g({b}) + g({c})?",
    ],
    "sequences": [
        "In an arithmetic sequence the first term is {a} and the common difference is {b}; what is the {c}th term?",
        "Each term of a sequence is {a} more than {b} times the previous term; if the first term is {c}, what is the third term?",
    ],
    "expressions": [
        "Simplify the expression {a}(x + {b}) - {c}(x - {bb}); the coefficient of x is what?",
        "What is {a}x + {b}x - {c}x equivalent to, in terms of x?",
    ],
    "word_problems": [
        "{who} drives {sum} miles at an average speed of {a} miles per hour, then returns at {b} mph. What is the total travel time, in hours (rounded)?",
        "Two pipes fill a tank in {a} and {b} minutes respectively; working together, about how many minutes do they take?",
        "{who} invests ${sum} at {a} percent simple annual interest; how much interest accrues in {b} years?",
    ],
}

# A generic fallback so every leaf always has at least one template.
_GENERIC = [
    "A GMAT Problem Solving item on {leaf_name}: using the values {a}, {b}, and {c}, what is the required result?",
]

_DIFFICULTIES = ("easy", "medium", "hard")


def _params(i: int) -> dict:
    """Deterministic, collision-free numbers derived from the global index i."""
    a = i % _MODS[0] + 3
    b = (i // _MODS[0]) % _MODS[1] + 2
    c = (i // (_MODS[0] * _MODS[1])) % _MODS[2] + 1
    return {
        "a": a,
        "b": b,
        "c": c,
        "a2": a * a,
        "bb": b + 1,
        "cc": c + 2,
        "sum": a + b + c + 10,
        "prod": a * b + c,
    }


def _fmt_options(base: int, deltas: list[int], suffix: str, rng: random.Random):
    """Return (options_dict, correct_letter) with 5 distinct positive choices."""
    vals = [base]
    for d in deltas:
        vals.append(base + d)
    seen: set[int] = set()
    fixed: list[int] = []
    bump = 1
    for v in vals:
        while v in seen or v <= 0:
            v += bump
            bump += 1
        seen.add(v)
        fixed.append(v)
    labels = list("ABCDE")
    pairs = list(zip(fixed, [True] + [False] * 4))
    rng.shuffle(pairs)
    options = {labels[idx]: f"{pairs[idx][0]}{suffix}" for idx in range(5)}
    correct = labels[[idx for idx, (_, ok) in enumerate(pairs) if ok][0]]
    return options, correct


def _make_question(i: int, seed: int) -> dict:
    """Build one unique, on-topic GMAT PS question dict for global index i."""
    leaf = LEAVES[i % len(LEAVES)]
    short = leaf.split("::")[-1]
    rng = random.Random(f"q:{seed}:{i}")
    p = _params(i)
    fields = dict(p)
    fields["who"] = _NAMES[i % len(_NAMES)]
    fields["item"] = _ITEMS[(i // 7) % len(_ITEMS)]
    fields["place"] = _PLACES[(i // 11) % len(_PLACES)]
    fields["leaf_name"] = short.replace("_", " ")

    templates = _TEMPLATES.get(short, _GENERIC)
    template = templates[i % len(templates)]
    stem = template.format(**fields)

    # Options: a plausible integer answer plus four distractors. (Correctness is
    # irrelevant to a speed benchmark; the shape/uniqueness is what matters.)
    base = p["sum"] + (i % 13)
    suffix = "%" if short == "percents" else ""
    options, correct = _fmt_options(
        base, [p["a"], -p["b"], p["c"], p["a"] + p["b"]], suffix, rng
    )
    return {
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": (
            f"Synthetic benchmark item #{i} for {leaf}. Deterministic values "
            f"a={p['a']}, b={p['b']}, c={p['c']} keep every stem unique."
        ),
        "topic": leaf,
        "difficulty": _DIFFICULTIES[i % len(_DIFFICULTIES)],
        "source": "gmatwiz-bench",
    }


def _chunks(seq, size):
    for start in range(0, len(seq), size):
        yield seq[start : start + size]


def _import_new(col: Collection, start: int, target: int, seed: int, batch: int) -> int:
    """Generate + import indices [start, target) in batches. Returns count added.

    Builds all AddNoteRequests once (a single stem-hash rescan of the existing
    deck) then commits them in batches, so this is O(n) rather than the O(n^2)
    you would get from re-scanning existing notes on every batch.
    """
    questions = [_make_question(i, seed) for i in range(start, target)]
    requests = gw.build_add_requests(col, questions, DECK_NAME)
    added = 0
    total = len(requests)
    t0 = time.time()
    for bi, chunk in enumerate(_chunks(requests, batch)):
        col.add_notes(chunk)
        added += len(chunk)
        elapsed = time.time() - t0
        rate = added / elapsed if elapsed else 0.0
        print(
            f"  imported {added:>6}/{total} notes  ({rate:5.0f}/s, {elapsed:5.1f}s)",
            flush=True,
        )
    return added


def _set_deck_limits(col: Collection, deck_id: int) -> None:
    """Raise new/review per-day caps to the engine max so a large slice of the 50k
    deck is schedulable at once (values above 9999 are rejected by the engine)."""
    col.decks.select(deck_id)
    conf = col.decks.config_dict_for_deck_id(deck_id)
    conf["new"]["perDay"] = MAX_PER_DAY
    conf["rev"]["perDay"] = MAX_PER_DAY
    # Do not clamp answer time (matches the app's _ensure_gmat_time_cap intent).
    conf["maxTaken"] = 300
    col.decks.update_config(conf)


def _set_topic_mastery(col: Collection, seed: int) -> None:
    """Set a varied per-topic mastery for every leaf (drives topic-aware order)."""
    rng = random.Random(f"mastery:{seed}")
    t0 = time.time()
    for idx, leaf in enumerate(LEAVES):
        # Spread masteries across 0.05..0.95 so weak topics clearly surface first.
        mastery = round(0.05 + 0.9 * ((idx + rng.random()) / len(LEAVES)), 3)
        col._backend.set_topic_mastery(topic=leaf, mastery=mastery)
    print(f"  set per-topic mastery for {len(LEAVES)} leaves ({time.time()-t0:4.1f}s)", flush=True)


def _seed_reviews(col: Collection, frac: float, seed: int) -> tuple[int, int]:
    """Drive a realistic fraction of cards into FSRS review state, due today, with
    matching revlog rows, so the topic-aware REVIEW reorder does real work and the
    dashboard scores compute over genuine history.

    Uses direct card-state writes (the same fields the Rust topic_aware test sets:
    type/queue/due/ivl/factor/reps), then a fresh reopen rebuilds the queue from
    these rows. topic_mastery in the card `data` column is left intact.
    Returns (review_cards, revlog_rows).
    """
    if frac <= 0:
        return (0, 0)
    rng = random.Random(f"reviews:{seed}")
    today = col.sched.today
    now = int(time.time())
    now_ms = now * 1000

    cids = col.db.list(
        "select id from cards order by id"
    )
    card_rows = []
    log_rows = []
    log_id = now_ms
    have_revlog = (col.db.scalar("select count() from revlog") or 0) > 0
    for cid in cids:
        if rng.random() >= frac:
            continue
        ivl = rng.randint(1, 210)
        due = today - rng.randint(0, min(ivl, 45))  # due today or overdue
        factor = rng.choice([1800, 2000, 2200, 2500, 2700])
        reps = rng.randint(1, 12)
        lapses = rng.randint(0, 3)
        card_rows.append((2, 2, due, ivl, factor, reps, lapses, 0, now, -1, cid))
        if not have_revlog:
            log_id += rng.randint(1, 900)  # keep revlog ids strictly increasing
            ease = rng.choices([1, 2, 3, 4], weights=[1, 2, 6, 3])[0]
            last_ivl = max(1, ivl // 2)
            taken = rng.randint(1500, 90000)  # ms; realistic GMAT answer times
            log_rows.append((log_id, cid, -1, ease, ivl, last_ivl, factor, taken, 1))

    if card_rows:
        col.db.executemany(
            "update cards set type=?, queue=?, due=?, ivl=?, factor=?, reps=?, "
            "lapses=?, left=?, mod=?, usn=? where id=?",
            card_rows,
        )
    if log_rows:
        col.db.executemany(
            "insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            log_rows,
        )
    return (len(card_rows), len(log_rows))


def build(path: str, count: int, seed: int, batch: int, review_frac: float) -> int:
    """Build (or top up) the benchmark deck at `path`. Returns final card count."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    col = Collection(path)
    try:
        existing = len(col.find_notes(f'note:"{NOTETYPE_NAME}"'))
        if existing >= count:
            print(
                f"Deck already at {existing} '{NOTETYPE_NAME}' notes (>= {count}); "
                f"nothing to do (idempotent)."
            )
            return col.card_count()

        print(
            f"Building bench deck at {path}: have {existing}, target {count} "
            f"(seed={seed}, batch={batch}, review_frac={review_frac})"
        )
        deck_id = col.decks.id(DECK_NAME)
        _set_deck_limits(col, deck_id)

        added = _import_new(col, existing, count, seed, batch)
        print(f"  added {added} new notes", flush=True)

        _set_topic_mastery(col, seed)
        reviews, logs = _seed_reviews(col, review_frac, seed)
        print(f"  seeded {reviews} review cards + {logs} revlog rows", flush=True)

        col.set_config("topicAwareScheduling", True)
        # Direct card/revlog writes above are committed when the collection is
        # closed (see finally); no deprecated save() needed.
        final = col.card_count()
        print(f"  final card count: {final}")
        # Uniqueness / dedup sanity: the importer must not have collapsed stems.
        if final < count:
            print(
                f"WARNING: final count {final} < target {count}. Some stems may "
                f"have collided under stem-hash dedup.",
                file=sys.stderr,
            )
        return final
    finally:
        col.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the shared 50k GMAT bench deck.")
    parser.add_argument(
        "--path",
        default=str(_REPO / "out" / "bench" / "col.anki2"),
        help="Destination .anki2 path (default: out/bench/col.anki2).",
    )
    parser.add_argument("--count", type=int, default=50_000, help="Target card count.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic RNG seed.")
    parser.add_argument("--batch", type=int, default=5_000, help="Import batch size.")
    parser.add_argument(
        "--review-frac",
        type=float,
        default=0.4,
        help="Fraction of cards seeded into review state (0 disables).",
    )
    args = parser.parse_args(argv)

    t0 = time.time()
    final = build(args.path, args.count, args.seed, args.batch, args.review_frac)
    print(f"Done in {time.time() - t0:.1f}s. Deck: {args.path} ({final} cards).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
