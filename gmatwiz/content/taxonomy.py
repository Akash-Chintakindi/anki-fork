"""Shared GMAT taxonomy, JSON schema helpers, and a keyword topic tagger.

Used by both ``scraper.py`` (scraped -> normalized) and ``make_seed.py``
(authored). The taxonomy follows PRD Section 5:

    Quantitative Reasoning = Problem Solving (arithmetic + algebra; NO geometry,
    NO Data Sufficiency).
    Verbal Reasoning       = Critical Reasoning + Reading Comprehension (NO
    Sentence Correction). Critical Reasoning ships first; Reading Comprehension
    leaves are added in Phase B.

Every normalized question is tagged to exactly one leaf topic of the form
``gmat::<section>::<category>::<leaf>`` (e.g. ``gmat::quant::algebra::quadratics``
or ``gmat::verbal::cr::weaken``) so that coverage %, mastery, and topic-aware
scheduling all key off the same taxonomy. ``section_of()`` recovers the section
from any leaf id; the keyword tagger takes a ``section`` argument to pick the
right rule set.

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

QUANT_TOPICS: List[str] = [
    f"{PREFIX}::{category}::{leaf}"
    for category, leaves in TAXONOMY.items()
    for leaf in leaves
]

# ---------------------------------------------------------------------------
# Verbal taxonomy (PRD Section 5). GMAT Focus Verbal = Critical Reasoning +
# Reading Comprehension ONLY (no Sentence Correction). Reading Comprehension
# leaves are added in Phase B; Critical Reasoning ships first.
# ---------------------------------------------------------------------------
VERBAL_PREFIX = "gmat::verbal"

VERBAL_TAXONOMY: Dict[str, List[str]] = {
    "cr": [
        "assumption",         # find the unstated premise the argument needs
        "strengthen",         # which fact, if true, best supports the argument
        "weaken",             # which fact, if true, most undermines the argument
        "evaluate",           # what would be most useful to know to assess it
        "inference",          # what must be true / is most supported by the text
        "explain_paradox",    # resolve an apparent discrepancy/contradiction
        "flaw",               # describe the reasoning error
        "boldface",           # role two boldfaced portions play in the argument
        "complete_argument",  # logically complete the argument (fill in blank)
    ],
    "rc": [
        "main_idea",      # primary purpose / main point of the passage
        "detail",         # what the passage explicitly states (supporting idea)
        "inference",      # what the passage implies / can be inferred
        "function",       # why the author mentions X / purpose of a paragraph
        "structure",      # how the passage is organized
        "tone",           # the author's attitude / tone
        "application",    # extend the passage's reasoning to a new case
    ],
}

VERBAL_TOPICS: List[str] = [
    f"{VERBAL_PREFIX}::{category}::{leaf}"
    for category, leaves in VERBAL_TAXONOMY.items()
    for leaf in leaves
]

# ---------------------------------------------------------------------------
# Data Insights taxonomy (GMAT Focus third section). Pragmatic MCQ-compatible
# scope first: Data Sufficiency (standard 5 options), Two-Part Analysis (authored
# MCQ-compatible), Multi-Source Reasoning (source stimulus in the passage field).
# Graphics Interpretation + Table Analysis are deferred (need interactive UI).
# ---------------------------------------------------------------------------
DI_PREFIX = "gmat::di"

DI_TAXONOMY: Dict[str, List[str]] = {
    "reasoning": [
        "data_sufficiency",       # is the given data sufficient to answer?
        "two_part_analysis",      # pick the pair that satisfies two conditions
        "multi_source_reasoning", # reason across a short set of sources
    ],
}

DI_TOPICS: List[str] = [
    f"{DI_PREFIX}::{category}::{leaf}"
    for category, leaves in DI_TAXONOMY.items()
    for leaf in leaves
]

# Union used for schema validation and the AI classification universe.
ALL_TOPICS: List[str] = QUANT_TOPICS + VERBAL_TOPICS + DI_TOPICS

# Fallback when the tagger cannot confidently classify an item.
DEFAULT_TOPIC = f"{PREFIX}::arithmetic::number_properties"
VERBAL_DEFAULT_TOPIC = f"{VERBAL_PREFIX}::cr::inference"
DI_DEFAULT_TOPIC = f"{DI_PREFIX}::reasoning::data_sufficiency"


def section_of(topic: str) -> str:
    """Return the GMAT section for a leaf topic id: ``quant`` or ``verbal``.

    Keys off the second ``::`` segment (``gmat::<section>::...``); defaults to
    ``quant`` for anything unrecognized so existing quant callers are unaffected.
    """
    parts = (topic or "").split("::")
    if len(parts) >= 2 and parts[0] == "gmat":
        return parts[1]
    return "quant"


def topics_for_section(section: str) -> List[str]:
    """Leaf topics scoped to a section (``quant`` | ``verbal`` | ``di``); all otherwise."""
    if section == "verbal":
        return VERBAL_TOPICS
    if section == "di":
        return DI_TOPICS
    if section == "quant":
        return QUANT_TOPICS
    return ALL_TOPICS


def default_topic_for_section(section: str) -> str:
    if section == "verbal":
        return VERBAL_DEFAULT_TOPIC
    if section == "di":
        return DI_DEFAULT_TOPIC
    return DEFAULT_TOPIC

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

# Sentence-Correction markers: out of scope for GMAT Focus Verbal (CR + RC only).
SENTENCE_CORRECTION_PATTERNS = [
    r"\bunderlined\b",
    r"\bunderlined portion\b",
    r"\bsentence correction\b",
    r"\bno error\b",
]
_SENTENCE_CORRECTION_RE = re.compile("|".join(SENTENCE_CORRECTION_PATTERNS), re.IGNORECASE)


def out_of_scope_reason(text: str, section: str = "quant") -> str | None:
    """Return a reason string if the text is out of scope for ``section``.

    quant  -> geometry / data sufficiency are out of scope.
    verbal -> Sentence Correction is out of scope (Focus Verbal = CR + RC).
    di     -> no scope filter (Data Sufficiency IS valid Data Insights content).
    """
    body = text or ""
    if section == "verbal":
        if _SENTENCE_CORRECTION_RE.search(body):
            return "sentence_correction"
        return None
    if section == "di":
        # Data Insights admits Data Sufficiency + integrated-reasoning formats;
        # the pragmatic MCQ scope has no out-of-scope filter.
        return None
    if _DATA_SUFFICIENCY_RE.search(body):
        return "data_sufficiency"
    if _GEOMETRY_RE.search(body):
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


# ---------------------------------------------------------------------------
# Verbal (Critical Reasoning) keyword tagger
# ---------------------------------------------------------------------------
# Same weighted-scoring model as the Quant tagger, applied only when the caller
# passes section="verbal". CR question type is inferred from the question stem's
# telltale command phrasing ("which of the following, if true, most weakens...").
_VERBAL_TAGGER_RULES: List[Tuple[str, str, int]] = [
    # --- boldface / describe-the-role ---
    (f"{VERBAL_PREFIX}::cr::boldface", r"\bboldface", 6),
    (f"{VERBAL_PREFIX}::cr::boldface", r"\bin bold\b", 5),
    (f"{VERBAL_PREFIX}::cr::boldface", r"\bportions?\b.{0,20}\bbold", 5),
    (f"{VERBAL_PREFIX}::cr::boldface", r"\bplays? which of the following roles\b", 5),
    (f"{VERBAL_PREFIX}::cr::boldface", r"\brole (?:in|played in) the argument\b", 3),
    # --- explain / resolve the paradox ---
    (f"{VERBAL_PREFIX}::cr::explain_paradox", r"\bparadox\b", 6),
    (f"{VERBAL_PREFIX}::cr::explain_paradox", r"\bdiscrepancy\b", 6),
    (f"{VERBAL_PREFIX}::cr::explain_paradox", r"\breconcile\b", 4),
    (f"{VERBAL_PREFIX}::cr::explain_paradox", r"\bmost helps? to explain\b", 5),
    (f"{VERBAL_PREFIX}::cr::explain_paradox", r"\bapparent(?:ly)? (?:contradict|conflict|discrepan)", 4),
    (f"{VERBAL_PREFIX}::cr::explain_paradox", r"\bexplains?\b.{0,30}\b(?:paradox|discrepancy|contradiction|surprising)\b", 4),
    # --- complete the argument / fill in the blank ---
    (f"{VERBAL_PREFIX}::cr::complete_argument", r"\bcomplete the (?:argument|passage)\b", 6),
    (f"{VERBAL_PREFIX}::cr::complete_argument", r"\b(?:most )?logically completes\b", 6),
    (f"{VERBAL_PREFIX}::cr::complete_argument", r"\bfill in the blank\b", 5),
    (f"{VERBAL_PREFIX}::cr::complete_argument", r"_{3,}", 5),
    # --- evaluate the argument ---
    (f"{VERBAL_PREFIX}::cr::evaluate", r"\bevaluate the argument\b", 6),
    (f"{VERBAL_PREFIX}::cr::evaluate", r"\bmost (?:useful|helpful|important) to (?:know|determine|evaluate|assess)\b", 5),
    (f"{VERBAL_PREFIX}::cr::evaluate", r"\bwould be most useful (?:in|to) (?:evaluat|assess)", 5),
    # --- flaw / vulnerable to criticism ---
    (f"{VERBAL_PREFIX}::cr::flaw", r"\bflaw", 6),
    (f"{VERBAL_PREFIX}::cr::flaw", r"\bvulnerable to (?:the )?criticism\b", 6),
    (f"{VERBAL_PREFIX}::cr::flaw", r"\breasoning is (?:most )?(?:flawed|questionable|vulnerable)\b", 5),
    (f"{VERBAL_PREFIX}::cr::flaw", r"\berror in reasoning\b", 5),
    (f"{VERBAL_PREFIX}::cr::flaw", r"\bfails to (?:consider|account for|recognize)\b", 4),
    # --- assumption ---
    (f"{VERBAL_PREFIX}::cr::assumption", r"\bassumptions?\b", 6),
    (f"{VERBAL_PREFIX}::cr::assumption", r"\bassumes?\b", 4),
    (f"{VERBAL_PREFIX}::cr::assumption", r"\bdepends on\b", 3),
    (f"{VERBAL_PREFIX}::cr::assumption", r"\brelies on (?:the )?assumption", 5),
    (f"{VERBAL_PREFIX}::cr::assumption", r"\bpresupposes?\b", 4),
    (f"{VERBAL_PREFIX}::cr::assumption", r"\bwhich of the following.{0,40}\bassumptions?\b", 4),
    # --- weaken ---
    (f"{VERBAL_PREFIX}::cr::weaken", r"\bweaken", 6),
    (f"{VERBAL_PREFIX}::cr::weaken", r"\bundermine", 5),
    (f"{VERBAL_PREFIX}::cr::weaken", r"\bcasts? doubt\b", 5),
    (f"{VERBAL_PREFIX}::cr::weaken", r"\bcalls? into question\b", 5),
    (f"{VERBAL_PREFIX}::cr::weaken", r"\bmost seriously (?:weakens?|undermines?)\b", 6),
    (f"{VERBAL_PREFIX}::cr::weaken", r"\bif true,?\s+most (?:weakens?|undermines?)\b", 6),
    # --- strengthen ---
    (f"{VERBAL_PREFIX}::cr::strengthen", r"\bstrengthen", 6),
    (f"{VERBAL_PREFIX}::cr::strengthen", r"\bmost (?:strongly )?support(?:s|ed)? the (?:argument|conclusion|claim|prediction|plan)\b", 5),
    (f"{VERBAL_PREFIX}::cr::strengthen", r"\bif true,?\s+most (?:strengthens?|supports?)\b", 6),
    (f"{VERBAL_PREFIX}::cr::strengthen", r"\bprovides? the most support\b", 5),
    # --- inference / must be true ---
    (f"{VERBAL_PREFIX}::cr::inference", r"\bmust be true\b", 6),
    (f"{VERBAL_PREFIX}::cr::inference", r"\bproperly (?:inferred|concluded)\b", 5),
    (f"{VERBAL_PREFIX}::cr::inference", r"\bcan be (?:logically |properly )?(?:inferred|concluded)\b", 5),
    (f"{VERBAL_PREFIX}::cr::inference", r"\bmost strongly supported\b", 5),
    (f"{VERBAL_PREFIX}::cr::inference", r"\bif the (?:statements|information) above are true\b", 3),
    # ===================== Reading Comprehension (Phase B) =====================
    # RC rules key on passage-specific phrasing ("the passage", "the author",
    # "paragraph") that CR stems lack, so they don't cross-match CR items.
    # --- RC: main idea / primary purpose ---
    (f"{VERBAL_PREFIX}::rc::main_idea", r"\bprimary purpose\b", 6),
    (f"{VERBAL_PREFIX}::rc::main_idea", r"\bmain (?:idea|point)\b", 6),
    (f"{VERBAL_PREFIX}::rc::main_idea", r"\bprimarily concerned with\b", 5),
    (f"{VERBAL_PREFIX}::rc::main_idea", r"\bpassage (?:as a whole|is primarily)\b", 4),
    (f"{VERBAL_PREFIX}::rc::main_idea", r"\bbest (?:title|summar)", 4),
    # --- RC: detail / supporting idea ---
    (f"{VERBAL_PREFIX}::rc::detail", r"\baccording to the passage\b", 6),
    (f"{VERBAL_PREFIX}::rc::detail", r"\bthe passage states\b", 5),
    (f"{VERBAL_PREFIX}::rc::detail", r"\bthe passage (?:indicates|mentions)\b", 5),
    (f"{VERBAL_PREFIX}::rc::detail", r"\bthe author (?:mentions|notes|states|indicates)\b", 4),
    # --- RC: inference ---
    (f"{VERBAL_PREFIX}::rc::inference", r"\bthe passage (?:suggests|implies)\b", 6),
    (f"{VERBAL_PREFIX}::rc::inference", r"\bit can be inferred from the passage\b", 6),
    (f"{VERBAL_PREFIX}::rc::inference", r"\bthe author (?:implies|would most likely agree)\b", 5),
    (f"{VERBAL_PREFIX}::rc::inference", r"\bmost likely to agree\b", 4),
    # --- RC: function / purpose of a part ---
    (f"{VERBAL_PREFIX}::rc::function", r"\bprimarily in order to\b", 6),
    (f"{VERBAL_PREFIX}::rc::function", r"\bfunction of the (?:first|second|third|fourth|final|last) paragraph\b", 6),
    (f"{VERBAL_PREFIX}::rc::function", r"\bwhy does the author (?:mention|refer|discuss)\b", 5),
    (f"{VERBAL_PREFIX}::rc::function", r"\b(?:mentions|refers to|discusses)\b.{0,40}\bin order to\b", 5),
    (f"{VERBAL_PREFIX}::rc::function", r"\bserves? (?:primarily )?to\b", 4),
    # --- RC: structure / organization ---
    (f"{VERBAL_PREFIX}::rc::structure", r"\borganization of the passage\b", 6),
    (f"{VERBAL_PREFIX}::rc::structure", r"\bthe passage (?:is organized|proceeds by|is structured)\b", 6),
    (f"{VERBAL_PREFIX}::rc::structure", r"\bhow the passage is organized\b", 5),
    (f"{VERBAL_PREFIX}::rc::structure", r"\bstructure of the passage\b", 5),
    # --- RC: tone / attitude ---
    (f"{VERBAL_PREFIX}::rc::tone", r"\bauthor's attitude\b", 6),
    (f"{VERBAL_PREFIX}::rc::tone", r"\btone of the passage\b", 6),
    (f"{VERBAL_PREFIX}::rc::tone", r"\battitude (?:toward|towards)\b", 5),
    (f"{VERBAL_PREFIX}::rc::tone", r"\bthe author (?:regards|views|would characterize)\b", 4),
    # --- RC: application / extrapolation ---
    (f"{VERBAL_PREFIX}::rc::application", r"\bmost analogous\b", 6),
    (f"{VERBAL_PREFIX}::rc::application", r"\bwould most likely apply\b", 5),
    (f"{VERBAL_PREFIX}::rc::application", r"\bin another (?:context|situation)\b", 4),
]

# Tie-break priority: earlier = more specific / preferred when scores tie.
_VERBAL_PRIORITY = [
    f"{VERBAL_PREFIX}::cr::boldface",
    f"{VERBAL_PREFIX}::cr::explain_paradox",
    f"{VERBAL_PREFIX}::cr::complete_argument",
    f"{VERBAL_PREFIX}::cr::evaluate",
    f"{VERBAL_PREFIX}::cr::flaw",
    f"{VERBAL_PREFIX}::cr::assumption",
    f"{VERBAL_PREFIX}::cr::weaken",
    f"{VERBAL_PREFIX}::cr::strengthen",
    f"{VERBAL_PREFIX}::cr::inference",
    # Reading Comprehension (more specific / passage-anchored first)
    f"{VERBAL_PREFIX}::rc::structure",
    f"{VERBAL_PREFIX}::rc::function",
    f"{VERBAL_PREFIX}::rc::tone",
    f"{VERBAL_PREFIX}::rc::application",
    f"{VERBAL_PREFIX}::rc::main_idea",
    f"{VERBAL_PREFIX}::rc::inference",
    f"{VERBAL_PREFIX}::rc::detail",
]
_VERBAL_PRIORITY_INDEX = {t: i for i, t in enumerate(_VERBAL_PRIORITY)}

_COMPILED_VERBAL_RULES = [
    (topic, re.compile(pat, re.IGNORECASE), w) for topic, pat, w in _VERBAL_TAGGER_RULES
]

# ---------------------------------------------------------------------------
# Data Insights keyword tagger (pragmatic 3 question types)
# ---------------------------------------------------------------------------
_DI_TAGGER_RULES: List[Tuple[str, str, int]] = [
    # --- Data Sufficiency (the standard DS stem + option phrasing) ---
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\bdata sufficiency\b", 6),
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\bstatement\s*\(?1\)?\b", 4),
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\bstatement\s*\(?2\)?\b", 4),
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\beach statement alone\b", 5),
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\balone is sufficient\b", 5),
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\bsufficient to answer\b", 4),
    (f"{DI_PREFIX}::reasoning::data_sufficiency", r"\btogether are sufficient\b", 4),
    # --- Two-Part Analysis ---
    (f"{DI_PREFIX}::reasoning::two_part_analysis", r"\btwo-part analysis\b", 6),
    (f"{DI_PREFIX}::reasoning::two_part_analysis", r"\bselect (?:one|exactly one) (?:option|answer) in each column\b", 6),
    (f"{DI_PREFIX}::reasoning::two_part_analysis", r"\bselect one .{0,20}\band one\b", 4),
    (f"{DI_PREFIX}::reasoning::two_part_analysis", r"\btwo (?:quantities|values|responses)\b.{0,30}\bconditions?\b", 4),
    (f"{DI_PREFIX}::reasoning::two_part_analysis", r"\bmake (?:the|each) (?:column|selection)\b", 3),
    # --- Multi-Source Reasoning ---
    (f"{DI_PREFIX}::reasoning::multi_source_reasoning", r"\bmulti-source reasoning\b", 6),
    (f"{DI_PREFIX}::reasoning::multi_source_reasoning", r"\bbased on the (?:sources|three sources|two sources|information in the sources)\b", 6),
    (f"{DI_PREFIX}::reasoning::multi_source_reasoning", r"\bacross the (?:sources|tabs)\b", 5),
    (f"{DI_PREFIX}::reasoning::multi_source_reasoning", r"\bfrom the sources? (?:above|provided|shown)\b", 4),
    (f"{DI_PREFIX}::reasoning::multi_source_reasoning", r"\bthe (?:email|memo|table|report|chart) (?:and|,)\b.{0,40}\b(?:email|memo|table|report|chart)\b", 3),
]

_DI_PRIORITY = [
    f"{DI_PREFIX}::reasoning::two_part_analysis",
    f"{DI_PREFIX}::reasoning::multi_source_reasoning",
    f"{DI_PREFIX}::reasoning::data_sufficiency",
]
_DI_PRIORITY_INDEX = {t: i for i, t in enumerate(_DI_PRIORITY)}

_COMPILED_DI_RULES = [
    (topic, re.compile(pat, re.IGNORECASE), w) for topic, pat, w in _DI_TAGGER_RULES
]


def _rules_for_section(section: str):
    """Return (compiled_rules, priority_index) for the given section."""
    if section == "verbal":
        return _COMPILED_VERBAL_RULES, _VERBAL_PRIORITY_INDEX
    if section == "di":
        return _COMPILED_DI_RULES, _DI_PRIORITY_INDEX
    return _COMPILED_RULES, _PRIORITY_INDEX


def tag_topic(text: str, default: str | None = None, section: str = "quant") -> str:
    """Classify free text to a single leaf topic via weighted keyword scoring."""
    if default is None:
        default = default_topic_for_section(section)
    if not text:
        return default
    rules, priority = _rules_for_section(section)
    scores: Dict[str, int] = {}
    for topic, regex, weight in rules:
        if regex.search(text):
            scores[topic] = scores.get(topic, 0) + weight
    if not scores:
        return default
    # Highest score wins; ties broken by specificity priority.
    best = max(
        scores.items(),
        key=lambda kv: (kv[1], -priority.get(kv[0], 999)),
    )
    return best[0]


def tag_topic_with_score(
    text: str, default: str | None = None, section: str = "quant"
) -> Tuple[str, int]:
    """Like ``tag_topic`` but also returns the winning score (0 = fell back)."""
    if default is None:
        default = default_topic_for_section(section)
    if not text:
        return default, 0
    rules, priority = _rules_for_section(section)
    scores: Dict[str, int] = {}
    for topic, regex, weight in rules:
        if regex.search(text):
            scores[topic] = scores.get(topic, 0) + weight
    if not scores:
        return default, 0
    best = max(scores.items(), key=lambda kv: (kv[1], -priority.get(kv[0], 999)))
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
