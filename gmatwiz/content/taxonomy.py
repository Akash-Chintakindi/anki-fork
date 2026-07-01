"""Shared GMAT Quant taxonomy, JSON schema helpers, and a keyword topic tagger.

Used by both ``scraper.py`` (scraped -> normalized) and ``make_seed.py``
(authored). The taxonomy follows PRD Section 5:

    GMAT Focus Edition, Quantitative Reasoning = Problem Solving ONLY.
    Scope = arithmetic + algebra.  NO geometry, NO Data Sufficiency.

Every normalized question is tagged to exactly one leaf topic of the form
``gmat::quant::<category>::<leaf>`` (e.g. ``gmat::quant::algebra::quadratics``)
so that coverage %, mastery, and topic-aware scheduling all key off the same
taxonomy.

This module has zero third-party dependencies.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Tuple

PREFIX = "gmat::quant"

# ---------------------------------------------------------------------------
# Taxonomy (PRD Section 5 leaf topics)
# ---------------------------------------------------------------------------
TAXONOMY: Dict[str, List[str]] = {
    "arithmetic": [
        "number_properties",   # integers, factors/multiples, primes, divisibility, even/odd
        "fractions",
        "decimals",
        "percents",
        "ratios_proportions",
        "exponents_roots",
        "statistics",          # mean/median/mode/range/SD
        "sets",
        "counting",            # counting / combinatorics
        "probability",
    ],
    "algebra": [
        "linear_equations",    # linear equations & systems
        "quadratics",
        "inequalities",
        "absolute_value",
        "functions",
        "sequences",
        "expressions",         # algebraic expressions / exponent rules
        "word_problems",       # rate-time-distance, work, mixtures, interest, etc.
    ],
}

ALL_TOPICS: List[str] = [
    f"{PREFIX}::{category}::{leaf}"
    for category, leaves in TAXONOMY.items()
    for leaf in leaves
]

# Fallback when the tagger cannot confidently classify an item.
DEFAULT_TOPIC = f"{PREFIX}::arithmetic::number_properties"

VALID_DIFFICULTIES = ("easy", "medium", "hard")
OPTION_KEYS = ("A", "B", "C", "D", "E")

# Canonical field order for every emitted JSON object.
SCHEMA_FIELDS = [
    "id",
    "stem",
    "options",
    "correct",
    "explanation",
    "topic",
    "difficulty",
    "source",
    "license",
    "scraped_at",
]

# ---------------------------------------------------------------------------
# Geometry / Data-Sufficiency exclusion (PRD: out of scope for GMAT Focus Quant)
# ---------------------------------------------------------------------------
# Items matching these are NOT valid Quant PS content for this dataset and are
# dropped (with a reason) during normalization.
GEOMETRY_PATTERNS = [
    r"\btriangle\b", r"\bcircle\b", r"\bcircles\b", r"\bradius\b", r"\bradii\b",
    r"\bdiameter\b", r"\bcircumference\b", r"\bperimeter\b", r"\bhypotenuse\b",
    r"\bparallelogram\b", r"\btrapezoid\b", r"\brhombus\b", r"\bpolygon\b",
    r"\bquadrilateral\b", r"\bpentagon\b", r"\bhexagon\b", r"\bcylinder\b",
    r"\bsphere\b", r"\bcone\b", r"\bcuboid\b", r"\bprism\b",
    r"\barea of (?:a|the|an) (?:triangle|circle|rectangle|square|sector)\b",
    r"\bvolume of\b", r"\bsurface area\b", r"\bcoordinate plane\b",
    r"\bisosceles\b", r"\bequilateral\b", r"\bpythagore", r"\bdegrees?\b.{0,20}\bangle\b",
    r"\bangle\b", r"\bvertex\b", r"\bvertices\b", r"\bdiagonal\b",
]
DATA_SUFFICIENCY_PATTERNS = [
    r"statement\s*\(?1\)?",
    r"statement\s*\(?2\)?",
    r"\bdata sufficiency\b",
    r"each statement alone is sufficient",
    r"statements?\s*\(?1\)?\s*and\s*\(?2\)?\s*together",
]

_GEOMETRY_RE = re.compile("|".join(GEOMETRY_PATTERNS), re.IGNORECASE)
_DATA_SUFFICIENCY_RE = re.compile("|".join(DATA_SUFFICIENCY_PATTERNS), re.IGNORECASE)


def out_of_scope_reason(text: str) -> str | None:
    """Return a reason string if the text is out of scope, else None."""
    if _DATA_SUFFICIENCY_RE.search(text or ""):
        return "data_sufficiency"
    if _GEOMETRY_RE.search(text or ""):
        return "geometry"
    return None


# ---------------------------------------------------------------------------
# Keyword topic tagger
# ---------------------------------------------------------------------------
# Each entry: (leaf_full_topic, regex_pattern, weight). Higher weight = stronger
# signal. Scores are summed per topic; the highest score wins, ties broken by the
# order in _PRIORITY (more specific topics earlier).
_TAGGER_RULES: List[Tuple[str, str, int]] = [
    # --- probability ---
    (f"{PREFIX}::arithmetic::probability", r"\bprobabilit", 5),
    (f"{PREFIX}::arithmetic::probability", r"\bp\s*\(", 3),
    (f"{PREFIX}::arithmetic::probability", r"\bat random\b", 3),
    (f"{PREFIX}::arithmetic::probability", r"\bchosen at random\b", 4),
    (f"{PREFIX}::arithmetic::probability", r"\blikelihood\b", 3),
    (f"{PREFIX}::arithmetic::probability", r"\bodds\b", 2),
    # --- counting / combinatorics ---
    (f"{PREFIX}::arithmetic::counting", r"\bhow many ways\b", 5),
    (f"{PREFIX}::arithmetic::counting", r"\bpermutation", 5),
    (f"{PREFIX}::arithmetic::counting", r"\bcombination", 4),
    (f"{PREFIX}::arithmetic::counting", r"\barrangements?\b", 4),
    (f"{PREFIX}::arithmetic::counting", r"\bnumber of ways\b", 4),
    (f"{PREFIX}::arithmetic::counting", r"\bseated\b", 3),
    (f"{PREFIX}::arithmetic::counting", r"\bcan be (?:formed|arranged|selected|chosen)\b", 3),
    (f"{PREFIX}::arithmetic::counting", r"\bdistinct\b.{0,30}\b(?:arrange|order)\b", 3),
    # --- statistics ---
    (f"{PREFIX}::arithmetic::statistics", r"\bstandard deviation\b", 5),
    (f"{PREFIX}::arithmetic::statistics", r"\bmedian\b", 5),
    (f"{PREFIX}::arithmetic::statistics", r"\bmode\b", 4),
    (f"{PREFIX}::arithmetic::statistics", r"\barithmetic mean\b", 5),
    (f"{PREFIX}::arithmetic::statistics", r"\baverage\b", 2),
    (f"{PREFIX}::arithmetic::statistics", r"\bvariance\b", 4),
    (f"{PREFIX}::arithmetic::statistics", r"\brange of the (?:set|numbers|list)\b", 3),
    # --- sets ---
    (f"{PREFIX}::arithmetic::sets", r"\bneither\b", 3),
    (f"{PREFIX}::arithmetic::sets", r"\bboth\b.{0,40}\band\b", 2),
    (f"{PREFIX}::arithmetic::sets", r"\bat least one\b", 2),
    (f"{PREFIX}::arithmetic::sets", r"\bvenn\b", 5),
    (f"{PREFIX}::arithmetic::sets", r"\bunion\b", 3),
    (f"{PREFIX}::arithmetic::sets", r"\bintersection\b", 3),
    (f"{PREFIX}::arithmetic::sets", r"\bset of\b", 2),
    # --- percents ---
    (f"{PREFIX}::arithmetic::percents", r"\bpercent\b", 4),
    (f"{PREFIX}::arithmetic::percents", r"%", 3),
    (f"{PREFIX}::arithmetic::percents", r"\bdiscount\b", 3),
    (f"{PREFIX}::arithmetic::percents", r"\bincreased by\b", 2),
    (f"{PREFIX}::arithmetic::percents", r"\bdecreased by\b", 2),
    (f"{PREFIX}::arithmetic::percents", r"\bmarked up\b", 3),
    # --- ratios & proportions ---
    (f"{PREFIX}::arithmetic::ratios_proportions", r"\bratio\b", 5),
    (f"{PREFIX}::arithmetic::ratios_proportions", r"\bproportion", 4),
    (f"{PREFIX}::arithmetic::ratios_proportions", r"\bfor every\b", 2),
    (f"{PREFIX}::arithmetic::ratios_proportions", r"\bdirectly proportional\b", 4),
    (f"{PREFIX}::arithmetic::ratios_proportions", r"\binversely proportional\b", 4),
    (f"{PREFIX}::arithmetic::ratios_proportions", r"\b\d+\s*:\s*\d+\b", 3),
    # --- exponents & roots ---
    (f"{PREFIX}::arithmetic::exponents_roots", r"\bexponent", 4),
    (f"{PREFIX}::arithmetic::exponents_roots", r"\bsquare root\b", 4),
    (f"{PREFIX}::arithmetic::exponents_roots", r"\bcube root\b", 4),
    (f"{PREFIX}::arithmetic::exponents_roots", r"\braised to\b", 3),
    (f"{PREFIX}::arithmetic::exponents_roots", r"√", 4),
    (f"{PREFIX}::arithmetic::exponents_roots", r"\b\d+\s*\^\s*\d+", 3),
    (f"{PREFIX}::arithmetic::exponents_roots", r"\bto the power\b", 3),
    # --- number properties ---
    (f"{PREFIX}::arithmetic::number_properties", r"\bprime\b", 4),
    (f"{PREFIX}::arithmetic::number_properties", r"\bdivisib", 4),
    (f"{PREFIX}::arithmetic::number_properties", r"\bdivisor", 3),
    (f"{PREFIX}::arithmetic::number_properties", r"\bremainder\b", 4),
    (f"{PREFIX}::arithmetic::number_properties", r"\bfactor", 3),
    (f"{PREFIX}::arithmetic::number_properties", r"\bmultiple of\b", 3),
    (f"{PREFIX}::arithmetic::number_properties", r"\beven integer", 3),
    (f"{PREFIX}::arithmetic::number_properties", r"\bodd integer", 3),
    (f"{PREFIX}::arithmetic::number_properties", r"\bconsecutive integers?\b", 4),
    (f"{PREFIX}::arithmetic::number_properties", r"\bunits digit\b", 4),
    (f"{PREFIX}::arithmetic::number_properties", r"\bgreatest common\b", 3),
    (f"{PREFIX}::arithmetic::number_properties", r"\bleast common multiple\b", 3),
    # --- fractions ---
    (f"{PREFIX}::arithmetic::fractions", r"\bfraction", 4),
    (f"{PREFIX}::arithmetic::fractions", r"\bnumerator\b", 4),
    (f"{PREFIX}::arithmetic::fractions", r"\bdenominator\b", 4),
    (f"{PREFIX}::arithmetic::fractions", r"\breciprocal\b", 3),
    # --- decimals ---
    (f"{PREFIX}::arithmetic::decimals", r"\bdecimal", 4),
    (f"{PREFIX}::arithmetic::decimals", r"\bnearest (?:tenth|hundredth|thousandth)\b", 4),
    (f"{PREFIX}::arithmetic::decimals", r"\brounded to\b", 3),
    (f"{PREFIX}::arithmetic::decimals", r"\btenths?\b", 2),
    # --- algebra: word problems (rate/work/mixture/interest) ---
    (f"{PREFIX}::algebra::word_problems", r"\bmiles per hour\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bmph\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bkilometers per hour\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\baverage speed\b", 5),
    (f"{PREFIX}::algebra::word_problems", r"\bspeed of\b", 3),
    (f"{PREFIX}::algebra::word_problems", r"\bhow (?:long|far)\b", 3),
    (f"{PREFIX}::algebra::word_problems", r"\b(?:trains?|cars?|planes?)\b.{0,40}\b(?:travel|speed|hour)", 3),
    (f"{PREFIX}::algebra::word_problems", r"\bwork(?:ing)? together\b", 5),
    (f"{PREFIX}::algebra::word_problems", r"\b(?:hours|days|minutes) to (?:complete|finish|do|fill)\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bmixture\b", 5),
    (f"{PREFIX}::algebra::word_problems", r"\balloy\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bsolution\b.{0,30}\b(?:percent|%|acid|salt|concentration)\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\binterest\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\binvested\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bcompounded\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bper hour\b", 2),
    (f"{PREFIX}::algebra::word_problems", r"\bprofit\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bcost price\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bselling price\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bshopkeeper\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bpartnership\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bdownstream\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bupstream\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bstill water\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\b(?:pipe|cistern|tap|pump)s?\b", 3),
    (f"{PREFIX}::algebra::word_problems", r"\bfill(?:s|ed)?\b.{0,25}\b(?:tank|cistern|pool|reservoir)\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\byears old\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\bas old as\b", 4),
    (f"{PREFIX}::algebra::word_problems", r"\btwice as old\b", 4),
    # --- algebra: quadratics ---
    (f"{PREFIX}::algebra::quadratics", r"\bquadratic\b", 5),
    (f"{PREFIX}::algebra::quadratics", r"x\s*\^?\s*2\b", 3),
    (f"{PREFIX}::algebra::quadratics", r"x²", 4),
    (f"{PREFIX}::algebra::quadratics", r"\broots of\b", 3),
    (f"{PREFIX}::algebra::quadratics", r"\bparabola\b", 4),
    # --- algebra: inequalities ---
    (f"{PREFIX}::algebra::inequalities", r"\binequalit", 5),
    (f"{PREFIX}::algebra::inequalities", r"≤|≥", 4),
    (f"{PREFIX}::algebra::inequalities", r"\bgreater than or equal\b", 3),
    (f"{PREFIX}::algebra::inequalities", r"\bless than or equal\b", 3),
    # --- algebra: absolute value ---
    (f"{PREFIX}::algebra::absolute_value", r"\babsolute value\b", 5),
    (f"{PREFIX}::algebra::absolute_value", r"\|\s*[a-z0-9].*?\|", 3),
    # --- algebra: functions ---
    (f"{PREFIX}::algebra::functions", r"\bfunction\b", 4),
    (f"{PREFIX}::algebra::functions", r"\bf\s*\(\s*x\s*\)", 5),
    (f"{PREFIX}::algebra::functions", r"\bg\s*\(\s*x\s*\)", 5),
    (f"{PREFIX}::algebra::functions", r"\bdefined as\b", 2),
    (f"{PREFIX}::algebra::functions", r"\bdefined by\b", 2),
    # --- algebra: sequences ---
    (f"{PREFIX}::algebra::sequences", r"\bsequence\b", 5),
    (f"{PREFIX}::algebra::sequences", r"\bnth term\b", 5),
    (f"{PREFIX}::algebra::sequences", r"\barithmetic sequence\b", 5),
    (f"{PREFIX}::algebra::sequences", r"\bgeometric (?:sequence|progression)\b", 5),
    (f"{PREFIX}::algebra::sequences", r"\beach term\b", 3),
    (f"{PREFIX}::algebra::sequences", r"\bterm of the\b", 2),
    # --- algebra: linear equations & systems ---
    (f"{PREFIX}::algebra::linear_equations", r"\bsystem of equations\b", 5),
    (f"{PREFIX}::algebra::linear_equations", r"\bsolve for\b", 3),
    (f"{PREFIX}::algebra::linear_equations", r"\bsimultaneous equations\b", 4),
    (f"{PREFIX}::algebra::linear_equations", r"\blinear equation\b", 4),
    # --- algebra: expressions / exponent rules ---
    (f"{PREFIX}::algebra::expressions", r"\bsimplify\b", 4),
    (f"{PREFIX}::algebra::expressions", r"\bequivalent to\b", 3),
    (f"{PREFIX}::algebra::expressions", r"\bexpression\b", 3),
    (f"{PREFIX}::algebra::expressions", r"\bin terms of\b", 2),
]

# Tie-break priority: earlier = more specific / preferred when scores tie.
_PRIORITY = [
    f"{PREFIX}::arithmetic::probability",
    f"{PREFIX}::arithmetic::counting",
    f"{PREFIX}::algebra::word_problems",
    f"{PREFIX}::algebra::sequences",
    f"{PREFIX}::algebra::functions",
    f"{PREFIX}::algebra::quadratics",
    f"{PREFIX}::algebra::absolute_value",
    f"{PREFIX}::algebra::inequalities",
    f"{PREFIX}::algebra::linear_equations",
    f"{PREFIX}::arithmetic::statistics",
    f"{PREFIX}::arithmetic::sets",
    f"{PREFIX}::arithmetic::exponents_roots",
    f"{PREFIX}::arithmetic::ratios_proportions",
    f"{PREFIX}::arithmetic::percents",
    f"{PREFIX}::arithmetic::number_properties",
    f"{PREFIX}::arithmetic::fractions",
    f"{PREFIX}::arithmetic::decimals",
    f"{PREFIX}::algebra::expressions",
]
_PRIORITY_INDEX = {t: i for i, t in enumerate(_PRIORITY)}

# Pre-compile the tagger rules.
_COMPILED_RULES = [(topic, re.compile(pat, re.IGNORECASE), w) for topic, pat, w in _TAGGER_RULES]


def tag_topic(text: str, default: str = DEFAULT_TOPIC) -> str:
    """Classify free text to a single leaf topic via weighted keyword scoring."""
    if not text:
        return default
    scores: Dict[str, int] = {}
    for topic, regex, weight in _COMPILED_RULES:
        if regex.search(text):
            scores[topic] = scores.get(topic, 0) + weight
    if not scores:
        return default
    # Highest score wins; ties broken by specificity priority.
    best = max(
        scores.items(),
        key=lambda kv: (kv[1], -_PRIORITY_INDEX.get(kv[0], 999)),
    )
    return best[0]


def tag_topic_with_score(text: str, default: str = DEFAULT_TOPIC) -> Tuple[str, int]:
    """Like ``tag_topic`` but also returns the winning score (0 = fell back)."""
    if not text:
        return default, 0
    scores: Dict[str, int] = {}
    for topic, regex, weight in _COMPILED_RULES:
        if regex.search(text):
            scores[topic] = scores.get(topic, 0) + weight
    if not scores:
        return default, 0
    best = max(scores.items(), key=lambda kv: (kv[1], -_PRIORITY_INDEX.get(kv[0], 999)))
    return best[0], best[1]


# ---------------------------------------------------------------------------
# Difficulty heuristic (best-effort, from any difficulty cues in source text)
# ---------------------------------------------------------------------------
def guess_difficulty(text: str, default: str = "medium") -> str:
    t = (text or "").lower()
    # GMAT Club / forum style difficulty bands.
    if re.search(r"\b(7\d\d|700[- ]?level|hard|difficult|tough|sub[- ]?700)\b", t):
        if re.search(r"\b7\d\d\b|700|hard|difficult|tough", t):
            return "hard"
    if re.search(r"\b(5\d\d|500[- ]?level|easy|sub[- ]?600|low[- ]?difficulty)\b", t):
        return "easy"
    if re.search(r"\b(6\d\d|600[- ]?level|medium|moderate)\b", t):
        return "medium"
    return default


# ---------------------------------------------------------------------------
# Normalization / dedup helpers
# ---------------------------------------------------------------------------
def normalize_for_dedup(text: str) -> str:
    """Lowercase, strip option labels, collapse non-alphanumerics for matching."""
    t = (text or "").lower()
    t = re.sub(r"\b[a-e]\s*[\).:]\s*", " ", t)  # drop option labels like "A)" "B."
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def content_hash(stem: str, options: Dict[str, str]) -> str:
    basis = normalize_for_dedup(stem) + "||" + "|".join(
        normalize_for_dedup(options.get(k, "")) for k in OPTION_KEYS
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def make_id(source_tag: str, stem: str, options: Dict[str, str]) -> str:
    return f"{source_tag}-{content_hash(stem, options)[:12]}"


def make_question(
    *,
    id: str,
    stem: str,
    options: Dict[str, str],
    correct: str,
    explanation: str,
    topic: str,
    difficulty: str,
    source: str,
    license: str,
    scraped_at: str,
) -> Dict:
    """Build a normalized question dict in canonical field order."""
    return {
        "id": id,
        "stem": stem,
        "options": {k: options.get(k, "") for k in OPTION_KEYS},
        "correct": correct,
        "explanation": explanation,
        "topic": topic,
        "difficulty": difficulty,
        "source": source,
        "license": license,
        "scraped_at": scraped_at,
    }


def validate_question(q: Dict, *, require_explanation: bool = False) -> List[str]:
    """Return a list of validation error strings (empty == valid)."""
    errors: List[str] = []

    for field in SCHEMA_FIELDS:
        if field not in q:
            errors.append(f"missing field '{field}'")

    if not isinstance(q.get("id"), str) or not q.get("id"):
        errors.append("id must be a non-empty string")
    if not isinstance(q.get("stem"), str) or not q.get("stem", "").strip():
        errors.append("stem must be a non-empty string")

    opts = q.get("options")
    if not isinstance(opts, dict):
        errors.append("options must be an object")
    else:
        if set(opts.keys()) != set(OPTION_KEYS):
            errors.append(f"options keys must be exactly {OPTION_KEYS}, got {sorted(opts.keys())}")
        for k in OPTION_KEYS:
            v = opts.get(k)
            if not isinstance(v, str) or not v.strip():
                errors.append(f"option {k} must be a non-empty string")

    if q.get("correct") not in OPTION_KEYS:
        errors.append(f"correct must be one of {OPTION_KEYS}, got {q.get('correct')!r}")

    if require_explanation and not (isinstance(q.get("explanation"), str) and q.get("explanation", "").strip()):
        errors.append("explanation must be a non-empty string")

    if q.get("topic") not in ALL_TOPICS:
        errors.append(f"topic {q.get('topic')!r} is not in the taxonomy")

    if q.get("difficulty") not in VALID_DIFFICULTIES:
        errors.append(f"difficulty must be one of {VALID_DIFFICULTIES}, got {q.get('difficulty')!r}")

    if not isinstance(q.get("source"), str) or not q.get("source"):
        errors.append("source must be a non-empty string")
    if not isinstance(q.get("license"), str) or not q.get("license"):
        errors.append("license must be a non-empty string")
    if not isinstance(q.get("scraped_at"), str) or not q.get("scraped_at"):
        errors.append("scraped_at must be a non-empty string")

    return errors


def topic_counts(questions: List[Dict]) -> Dict[str, int]:
    counts = {t: 0 for t in ALL_TOPICS}
    for q in questions:
        t = q.get("topic")
        if t in counts:
            counts[t] += 1
        else:
            counts[t] = counts.get(t, 0) + 1
    return counts


if __name__ == "__main__":
    # Tiny self-check of the tagger.
    samples = [
        ("If x^2 - 5x + 6 = 0, what are the roots?", "quadratics"),
        ("A car travels at an average speed of 60 miles per hour...", "word_problems"),
        ("What is the probability of drawing a red ball at random?", "probability"),
        ("The arithmetic mean of 5 numbers is 12; find the median.", "statistics"),
        ("If the ratio of boys to girls is 3:2 ...", "ratios_proportions"),
        ("What is the units digit of 7^53?", "number_properties"),
    ]
    for text, expect_leaf in samples:
        got = tag_topic(text)
        flag = "OK " if got.endswith(expect_leaf) else "MISS"
        print(f"[{flag}] {got:45s} <- {text[:55]}")
    print(f"\n{len(ALL_TOPICS)} leaf topics in taxonomy.")
