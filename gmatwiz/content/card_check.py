#!/usr/bin/env python3
"""Challenge 7f - "AI card check": generate cards from one real source, run them
through a checker, and report the three 7f buckets against a PRE-SET cutoff.

WHAT THIS PROVES (the 7f spec, verbatim intent):
  "Build a gold set: 50 question-and-answer pairs for your exam with known-correct
   answers. Then generate 50 cards from one real source and run them through your
   checker. Report three counts: how many were correct and useful, how many were
   wrong (a wrong fact is worse than no card), how many were correct but bad
   teaching (vague, trivial, or duplicates). Set a passing cutoff before you look at
   the results, and block any card that fails it."

PIECES (all additive, reusing the existing AI plumbing):
  * GOLD SET  : cardcheck_gold.json - 50 ORIGINAL GMAT Quant PS Q&A pairs with
                KNOWN-correct answers (authored + independently verified by
                make_cardcheck_gold.py). The checker cross-verifies generated cards
                against these where they overlap.
  * SOURCE    : cardcheck_source.md - ONE original "textbook chapter" (percents +
                linear equations), the single real source the 50 cards are made FROM.
  * CHECKER   : mirrors ts/routes/gmat/aiChecker.ts's 7f rubric - fields
                pass / correctness / in_scope / well_formed / teaching_quality(0-10)
                / reasons; a card PASSES iff correctness AND in_scope AND well_formed
                AND teaching_quality >= 7. Fail-closed when the AI is unavailable.

==============================================================================
PRE-SET CUTOFF (declared HERE, before any results are computed - see constants):
  A generated card is ADMITTED only if ALL of:
      correctness == true            (the marked answer is actually correct)
    AND in_scope == true             (GMAT Quant PS: arithmetic/algebra, in taxonomy)
    AND well_formed == true          (5 distinct non-empty options, valid key, clear)
    AND teaching_quality >= 7         (0-10 scale; duplicates are capped below 7)
  Any card that fails this cutoff is BLOCKED (not admitted). A wrong-fact card is
  always blocked (worse than no card).
==============================================================================

MODES:
  --mock : deterministic, offline, NO API key. Candidate cards are reproducible
           perturbations of the gold set so the whole pipeline (generate -> check ->
           classify -> block -> report) can be exercised end-to-end without a model.
           The three counts from a mock run are a SMOKE TEST, not real numbers.
  (real) : uses the SAME key/model the app ships with (OpenAI gpt-4.1-mini via
           OPENAI_API_KEY, or Gemini). The model GENERATES cards from the source and
           the checker RE-SOLVES each one. This produces the real three counts.

REPRODUCE:
  # Offline smoke test (no key) - validates the pipeline end-to-end:
  cd /Users/akashchintakindi/Documents/AlphaProjects/GMATWiz/anki-fork && \
      out/pyenv/bin/python gmatwiz/content/card_check.py --mock

  # Real numbers - pull the app's key from Firebase and run the live pipeline:
  export OPENAI_API_KEY="$(npx -y firebase-tools@latest functions:secrets:access OPENAI_API_KEY --project gmatwiz)"
  cd /Users/akashchintakindi/Documents/AlphaProjects/GMATWiz/anki-fork && \
      out/pyenv/bin/python gmatwiz/content/card_check.py

Outputs: gmatwiz/content/cardcheck_report.json (per-card audit + counts) and
         proof/ai-cardcheck.txt (human-readable proof: cutoff up front, 3-count
         table, honest interpretation).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ai_ingest  # noqa: E402  (clients, AiCache, _cached_call, item_blob, thresholds)
import taxonomy  # noqa: E402  (taxonomy leaves, schema, scope filter, dedup helpers)

# ---------------------------------------------------------------------------
# PRE-SET CUTOFF + constants (fixed BEFORE any results are computed).
# ---------------------------------------------------------------------------
# Mirrors aiChecker.ts: pass iff correctness AND in_scope AND well_formed AND
# teaching_quality >= TEACHING_CUTOFF.
TEACHING_CUTOFF = 7            # teaching_quality is 0-10; >= 7 required to admit
DUP_TEACHING_CAP = 3          # a duplicate card's teaching_quality is capped here
PASS_RULE = ("correctness AND in_scope AND well_formed AND "
             f"teaching_quality >= {TEACHING_CUTOFF}")
DEFAULT_N = 50                # generate 50 candidate cards
GEN_BATCH = 10               # live generation batch size (for reliable JSON)

DEFAULT_GOLD = os.path.join(_HERE, "cardcheck_gold.json")
DEFAULT_SOURCE = os.path.join(_HERE, "cardcheck_source.md")
DEFAULT_REPORT = os.path.join(_HERE, "cardcheck_report.json")
DEFAULT_PROOF = os.path.abspath(os.path.join(_HERE, "..", "..", "proof", "ai-cardcheck.txt"))

# The exact LIVE command embedded verbatim in the proof file.
LIVE_CMD = (
    'export OPENAI_API_KEY="$(npx -y firebase-tools@latest '
    'functions:secrets:access OPENAI_API_KEY --project gmatwiz)"\n'
    "cd /Users/akashchintakindi/Documents/AlphaProjects/GMATWiz/anki-fork && "
    "out/pyenv/bin/python gmatwiz/content/card_check.py"
)
MOCK_CMD = (
    "cd /Users/akashchintakindi/Documents/AlphaProjects/GMATWiz/anki-fork && "
    "out/pyenv/bin/python gmatwiz/content/card_check.py --mock"
)

# The three 7f buckets.
BUCKET_GOOD = "correct_and_useful"
BUCKET_WRONG = "wrong"
BUCKET_BAD_TEACH = "correct_but_bad_teaching"


# ---------------------------------------------------------------------------
# AI client selection (mirror eval_tagging.pick_ai_client).
# ---------------------------------------------------------------------------
def pick_ai_client(mock: bool, section: str = "quant"):
    """Return (client, label). --mock -> MockClient; else OpenAI then Gemini; else None."""
    if mock:
        return ai_ingest.MockClient(section=section), "mock"
    for attr in ("OpenAIClient", "GeminiClient"):
        cls = getattr(ai_ingest, attr, None)
        if cls is None:
            continue
        from_env = getattr(cls, "from_env", None)
        client = from_env(section=section) if callable(from_env) else None
        if client is not None:
            model = getattr(client, "model", None)
            return client, (f"{client.name}:{model}" if model else client.name)
    return None, "unavailable"


# ---------------------------------------------------------------------------
# JSON helpers for talking to the real clients (they expose _chat / _generate_text).
# ---------------------------------------------------------------------------
def _loads_json(text: Optional[str]):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    for pat in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                continue
    return None


def _client_raw_json(client, prompt: str):
    """Call whatever raw-generation method the ai_ingest client exposes."""
    chat = getattr(client, "_chat", None)
    if callable(chat):
        return _loads_json(chat(prompt, json_mode=True))
    gen = getattr(client, "_generate_text", None)
    if callable(gen):
        return _loads_json(gen(prompt))
    return None


# ---------------------------------------------------------------------------
# Card normalization (mirror GmatApp.svelte normalizeGen).
# ---------------------------------------------------------------------------
def normalize_card(raw: Dict) -> Optional[Dict]:
    """Enforce 5 non-empty options + a valid correct key; coerce topic/difficulty."""
    if not isinstance(raw, dict):
        return None
    src = raw.get("options") or {}
    if not isinstance(src, dict):
        return None
    options: Dict[str, str] = {}
    for k in taxonomy.OPTION_KEYS:
        v = src.get(k)
        if not isinstance(v, str) or not v.strip():
            return None
        options[k] = v.strip()
    correct = str(raw.get("correct", "")).strip().upper()
    if correct not in taxonomy.OPTION_KEYS:
        return None
    stem = str(raw.get("stem", "")).strip()
    if not stem:
        return None

    topic = raw.get("topic")
    if topic not in taxonomy.QUANT_TOPICS:
        # Re-tag to a real Quant leaf from the text (keyword tagger).
        topic = taxonomy.tag_topic(taxonomy_blob(stem, options), section="quant")
    difficulty = str(raw.get("difficulty", "")).strip().lower()
    if difficulty not in taxonomy.VALID_DIFFICULTIES:
        difficulty = "medium"

    return {
        "id": taxonomy.make_id("cardgen", stem, options),
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": str(raw.get("explanation", "") or ""),
        "topic": topic,
        "difficulty": difficulty,
    }


def taxonomy_blob(stem: str, options: Dict[str, str]) -> str:
    parts = [stem]
    for k in taxonomy.OPTION_KEYS:
        parts.append(str(options.get(k, "")))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# GENERATION - (a) build 50 candidate cards from the ONE source.
# ---------------------------------------------------------------------------
def _gen_prompt(source_text: str, n: int, batch_idx: int) -> str:
    """Card-generation prompt (mirror GmatApp.svelte genPrompt), grounded in source."""
    leaves = ", ".join([
        "gmat::quant::arithmetic::percents",
        "gmat::quant::algebra::linear_equations",
        "gmat::quant::arithmetic::ratios_proportions",
        "gmat::quant::algebra::word_problems",
    ])
    return "\n".join([
        f"Create {n} ORIGINAL GMAT Focus Quant Problem Solving questions grounded in the",
        "STUDY NOTES below. Base every question on the concepts and worked methods in the",
        "notes (this is batch "
        f"{batch_idx + 1}; make this batch's questions different from earlier ones).",
        "Scope is strict: arithmetic and algebra only. NO geometry, NO coordinate geometry,",
        "NO Data Sufficiency, and NO questions that need a figure, chart, or table.",
        "Each question must:",
        "- follow directly from the SOURCE NOTES (percents and/or linear equations);",
        "- be self-contained and solvable by hand (no calculator);",
        "- have exactly five options keyed A, B, C, D, E with exactly one correct answer;",
        "- include a concise worked explanation that DERIVES the correct answer;",
        "- be original - do not reproduce copyrighted or official GMAT items.",
        f'Set each item\'s "topic" to a GMAT Quant leaf id (one of: {leaves}) and',
        '"difficulty" to easy, medium, or hard.',
        'Return JSON ONLY as: {"cards": [ {"stem": "...", "options": {"A": "...", "B": "...",',
        '"C": "...", "D": "...", "E": "..."}, "correct": "A", "explanation": "...",',
        '"topic": "...", "difficulty": "..."} ]}',
        "",
        "SOURCE NOTES:",
        source_text.strip(),
    ])


def generate_live(client, cache, source_text: str, n: int) -> List[Dict]:
    """Ask the real model for n cards grounded in the source (batched + cached)."""
    cards: List[Dict] = []
    batch_idx = 0
    max_batches = (n // GEN_BATCH) + 4
    while len(cards) < n and batch_idx < max_batches:
        want = min(GEN_BATCH, n - len(cards))
        prompt = _gen_prompt(source_text, want, batch_idx)
        # Cache each batch keyed by a synthetic item (source+params) via AiCache.
        cache_item = {"stem": f"cardgen:{want}:{batch_idx}", "options": {}, "correct": ""}
        parsed = ai_ingest._cached_call(
            cache, client, cache_item, "cardgen",
            lambda p=prompt: _client_raw_json(client, p),
        )
        batch = []
        if isinstance(parsed, dict):
            batch = parsed.get("cards") or parsed.get("items") or []
        elif isinstance(parsed, list):
            batch = parsed
        for raw in batch:
            norm = normalize_card(raw)
            if norm is not None:
                cards.append(norm)
            if len(cards) >= n:
                break
        batch_idx += 1
    return cards[:n]


# Deterministic mock generation ---------------------------------------------
# A fixed 10-slot pattern (repeated to fill n) that deliberately produces cards
# across all three 7f buckets AND the block path, so the offline smoke run
# exercises the full pipeline. Cards are perturbations of the gold set so the
# checker can genuinely cross-verify correctness against known-correct answers.
MOCK_PATTERN = [
    "good", "good", "good", "good", "good",
    "bad_vague", "bad_trivial", "dup", "wrong", "wrong",
]


def _wrong_letter(correct: str) -> str:
    for k in taxonomy.OPTION_KEYS:
        if k != correct:
            return k
    return correct


def generate_mock(gold: List[Dict], n: int) -> List[Dict]:
    cards: List[Dict] = []
    canonical: Optional[Dict] = None  # first "good" card, reused to force duplicates
    for i in range(n):
        base = gold[i % len(gold)]
        kind = MOCK_PATTERN[i % len(MOCK_PATTERN)]
        stem = base["stem"]
        options = dict(base["options"])
        correct = base["correct"]
        explanation = base["explanation"]
        topic = base["topic"]
        difficulty = base.get("difficulty", "medium")

        if kind == "good":
            pass  # faithful, correct, full explanation
        elif kind == "bad_vague":
            explanation = f"The correct answer is {correct}."
        elif kind == "bad_trivial":
            explanation = "Obvious."
        elif kind == "wrong":
            correct = _wrong_letter(correct)  # a wrong-fact card (mislabeled answer)
        elif kind == "dup" and canonical is not None:
            stem = canonical["stem"]
            options = dict(canonical["options"])
            correct = canonical["correct"]
            explanation = canonical["explanation"]
            topic = canonical["topic"]
            difficulty = canonical["difficulty"]

        card = {
            "id": taxonomy.make_id("cardgen", stem, options),
            "stem": stem,
            "options": options,
            "correct": correct,
            "explanation": explanation,
            "topic": topic,
            "difficulty": difficulty,
        }
        if kind == "good" and canonical is None:
            canonical = card
        cards.append(card)
    return cards


# ---------------------------------------------------------------------------
# CHECKER - (b) mirror aiChecker.ts's 7f rubric.
# ---------------------------------------------------------------------------
def _structural(card: Dict) -> Tuple[bool, bool, List[str]]:
    """Deterministic well_formed + in_scope checks (both modes, fail-closed)."""
    reasons: List[str] = []
    opts = card.get("options") or {}
    keys_ok = set(opts.keys()) == set(taxonomy.OPTION_KEYS)
    nonempty = all(isinstance(opts.get(k), str) and opts.get(k, "").strip()
                   for k in taxonomy.OPTION_KEYS)
    distinct = len({re.sub(r"\s+", " ", str(v).strip().lower())
                    for v in opts.values() if v}) == 5
    correct_ok = card.get("correct") in taxonomy.OPTION_KEYS
    stem_ok = bool(str(card.get("stem", "")).strip())
    well_formed = keys_ok and nonempty and distinct and correct_ok and stem_ok
    if not distinct:
        reasons.append("duplicate_options")
    if not correct_ok:
        reasons.append("invalid_correct_key")
    if not stem_ok:
        reasons.append("empty_stem")

    blob = ai_ingest.item_blob(card) + " " + str(card.get("explanation", ""))
    scope = taxonomy.out_of_scope_reason(blob, section="quant")
    topic_ok = card.get("topic") in taxonomy.QUANT_TOPICS
    in_scope = scope is None and topic_ok
    if scope:
        reasons.append(f"out_of_scope:{scope}")
    if not topic_ok:
        reasons.append("topic_not_quant_leaf")
    return well_formed, in_scope, reasons


def _heuristic_teaching_quality(explanation: str, is_duplicate: bool) -> Tuple[int, List[str]]:
    """Offline 0-10 teaching-quality proxy: does the explanation actually show work?"""
    e = (explanation or "").strip()
    reasons: List[str] = []
    n = len(e)
    score = 0
    if n >= 15:
        score += 1
    else:
        reasons.append("explanation_too_short")
    if n >= 30:
        score += 2
    if n >= 60:
        score += 1
    if any(sym in e for sym in ("=", "+", "/", "*", "^")) or " x " in e:
        score += 3  # shows a computation
    digits = sum(1 for ch in e if ch.isdigit())
    if digits >= 3:
        score += 3
    elif digits >= 1:
        score += 1
    markers = ("because", "therefore", "so ", "since", "thus", "hence", "substitute",
               "factor", "remainder", "ratio", "average", "sum", "difference")
    low = e.lower()
    score += min(2, sum(1 for m in markers if m in low))
    if is_duplicate:
        reasons.append("duplicate_of_earlier_card")
        return min(score, DUP_TEACHING_CAP), reasons
    return max(0, min(10, score)), reasons


def _ai_check(client, cache, card: Dict) -> Optional[Dict]:
    """Real-mode: mirror aiChecker.ts's prompt and return its ItemCheck fields."""
    options_text = "\n".join(f"{k}: {card['options'][k]}" for k in taxonomy.OPTION_KEYS)
    prompt = "\n".join(x for x in [
        "You are a GMAT Quant item reviewer. Evaluate this multiple-choice question.",
        f"Topic: {card.get('topic')}" if card.get("topic") else "",
        f"Stem: {card.get('stem')}",
        f"Options:\n{options_text}",
        f"Marked correct: {card.get('correct')}",
        f"Explanation: {card.get('explanation')}" if card.get("explanation") else "",
        "",
        "Solve the problem yourself, then return JSON with:",
        "- pass: true only if correctness, in_scope, well_formed are all true AND "
        "teaching_quality >= 7",
        "- correctness: the marked answer is mathematically correct",
        "- in_scope: appropriate GMAT Quant content",
        "- well_formed: stem and options are clear and unambiguous",
        "- teaching_quality: 0-10 pedagogical quality of the explanation (0 if missing)",
        "- reasons: short strings explaining any failures",
    ] if x != "")

    parsed = ai_ingest._cached_call(
        cache, client, card, "cardcheck7f",
        lambda p=prompt: _client_raw_json(client, p),
    )
    if not isinstance(parsed, dict):
        return None
    try:
        tq = float(parsed.get("teaching_quality", 0) or 0)
    except Exception:
        tq = 0.0
    reasons = parsed.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return {
        "correctness": bool(parsed.get("correctness")),
        "in_scope": bool(parsed.get("in_scope")),
        "well_formed": bool(parsed.get("well_formed")),
        "teaching_quality": max(0.0, min(10.0, tq)),
        "reasons": [str(r) for r in reasons],
    }


def check_card(
    card: Dict,
    gold_by_key: Dict[str, Dict],
    seen_keys: set,
    *,
    mock: bool,
    client,
    cache,
) -> Dict:
    """Produce a 7f ItemCheck + the gold cross-verification for one card."""
    reasons: List[str] = []

    # Duplicate detection across the candidate batch (order-sensitive).
    key = taxonomy.content_hash(card["stem"], card["options"])
    is_duplicate = key in seen_keys
    seen_keys.add(key)

    # Structural (deterministic) well_formed + in_scope, both modes.
    well_formed, in_scope, struct_reasons = _structural(card)
    reasons.extend(struct_reasons)

    # Cross-verify correctness against the gold set where the card matches a pair.
    gold_item = gold_by_key.get(key)
    gold_matched = gold_item is not None
    gold_correct = gold_item["correct"] if gold_item else None

    ai_fields = None
    if not mock and client is not None:
        ai_fields = _ai_check(client, cache, card)

    # ---- correctness -----------------------------------------------------
    if gold_matched:
        correctness = (card["correct"] == gold_item["correct"])
        if not correctness:
            reasons.append(f"answer_disagrees_with_gold(gold={gold_correct})")
    elif ai_fields is not None:
        correctness = ai_fields["correctness"]
        if not correctness:
            reasons.append("ai_recheck_marked_incorrect")
    else:
        # Offline and no gold match -> cannot verify -> fail closed.
        correctness = False
        reasons.append("unverifiable_offline")

    # ---- in_scope / well_formed (AND the AI's judgment when present) -----
    if ai_fields is not None:
        if not ai_fields["in_scope"]:
            in_scope = False
            reasons.append("ai_out_of_scope")
        if not ai_fields["well_formed"]:
            well_formed = False
            reasons.append("ai_not_well_formed")

    # ---- teaching_quality ------------------------------------------------
    if ai_fields is not None:
        teaching_quality = float(ai_fields["teaching_quality"])
        reasons.extend(ai_fields.get("reasons", []))
        if is_duplicate:
            teaching_quality = min(teaching_quality, float(DUP_TEACHING_CAP))
            reasons.append("duplicate_of_earlier_card")
    else:
        teaching_quality, tq_reasons = _heuristic_teaching_quality(
            card.get("explanation", ""), is_duplicate)
        reasons.extend(tq_reasons)

    if teaching_quality < TEACHING_CUTOFF:
        reasons.append(
            f"teaching_quality_below_cutoff({teaching_quality:.1f}<{TEACHING_CUTOFF})")

    passed = bool(correctness and in_scope and well_formed
                  and teaching_quality >= TEACHING_CUTOFF)

    if not correctness:
        bucket = BUCKET_WRONG
    elif passed:
        bucket = BUCKET_GOOD
    else:
        bucket = BUCKET_BAD_TEACH

    # Informational topic-confidence check (reuses CONFIDENCE_THRESHOLD; no effect on pass).
    kw_topic, kw_conf = ai_ingest.HeuristicClient(section="quant").classify_topic(card)
    if kw_conf < ai_ingest.CONFIDENCE_THRESHOLD:
        reasons.append("low_topic_confidence")

    # De-duplicate reason strings, preserve order.
    seen_r: set = set()
    reasons = [r for r in reasons if not (r in seen_r or seen_r.add(r))]

    return {
        "id": card["id"],
        "topic": card["topic"],
        "difficulty": card.get("difficulty"),
        "correct": card["correct"],
        "gold_matched": gold_matched,
        "gold_correct": gold_correct,
        "duplicate": is_duplicate,
        "topic_confidence": round(float(kw_conf), 4),
        "check": {
            "pass": passed,
            "correctness": bool(correctness),
            "in_scope": bool(in_scope),
            "well_formed": bool(well_formed),
            "teaching_quality": round(float(teaching_quality), 2),
            "reasons": reasons,
        },
        "bucket": bucket,
        "blocked": not passed,
        "stem": card["stem"],
    }


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_gold(path: str) -> List[Dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    warnings: List[str] = []
    for it in data:
        errs = taxonomy.validate_question(it, require_explanation=True)
        if errs:
            warnings.append(f"{it.get('id')}: {errs}")
    if warnings:
        print(f"WARNING: {len(warnings)} gold item(s) failed schema validation:",
              file=sys.stderr)
        for w in warnings[:5]:
            print("  - " + w, file=sys.stderr)
    return data


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(gold: List[Dict], source_text: str, *, mock: bool, n: int,
        client, ai_label: str) -> Dict:
    cache = ai_ingest.AiCache()

    if mock:
        candidates = generate_mock(gold, n)
    else:
        candidates = generate_live(client, cache, source_text, n)
        cache.save()

    gold_by_key = {taxonomy.content_hash(g["stem"], g["options"]): g for g in gold}
    seen_keys: set = set()

    per_card: List[Dict] = []
    for card in candidates:
        row = check_card(card, gold_by_key, seen_keys,
                         mock=mock, client=client, cache=cache)
        per_card.append(row)
    if not mock and client is not None:
        cache.save()

    counts = {BUCKET_GOOD: 0, BUCKET_WRONG: 0, BUCKET_BAD_TEACH: 0}
    for row in per_card:
        counts[row["bucket"]] += 1
    blocked_ids = [r["id"] for r in per_card if r["blocked"]]
    gold_cross_verified = sum(1 for r in per_card if r["gold_matched"])

    report = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat(),
        "mode": "mock" if mock else "live",
        "ai_client": ai_label,
        "source_file": os.path.abspath(DEFAULT_SOURCE),
        "gold_file": os.path.abspath(DEFAULT_GOLD),
        "gold_count": len(gold),
        "n_requested": n,
        "n_generated": len(candidates),
        "cutoff": {
            "teaching_quality_min": TEACHING_CUTOFF,
            "duplicate_teaching_cap": DUP_TEACHING_CAP,
            "pass_rule": PASS_RULE,
            "preset_before_results": True,
        },
        "counts": counts,
        "admitted_count": counts[BUCKET_GOOD],
        "blocked_count": counts[BUCKET_WRONG] + counts[BUCKET_BAD_TEACH],
        "gold_cross_verified": gold_cross_verified,
        "blocked_ids": blocked_ids,
        "per_card": per_card,
    }
    return report


# ---------------------------------------------------------------------------
# Proof writer (human-readable proof/ai-cardcheck.txt).
# ---------------------------------------------------------------------------
def _bar(width: int = 79) -> str:
    return "=" * width


def write_proof(report: Dict, path: str) -> None:
    mock = report["mode"] == "mock"
    c = report["counts"]
    total = report["n_generated"]

    def pct(x: int) -> str:
        return f"{(100.0 * x / total):5.1f}%" if total else "  -  "

    lines: List[str] = []
    lines.append(_bar())
    lines.append("GMATWiz - 7f AI CARD CHECK  (generate -> check -> block -> report)")
    lines.append(_bar())
    lines.append("What this proves (challenge 7f): build a 50-pair gold set with known-correct")
    lines.append("answers; generate 50 cards from ONE real source; run them through a checker;")
    lines.append("report three counts (correct & useful / wrong / correct-but-bad-teaching);")
    lines.append("set a passing cutoff BEFORE looking at results and block any card that fails.")
    lines.append("")
    lines.append("GOLD SET   : gmatwiz/content/cardcheck_gold.json - 50 ORIGINAL GMAT Quant PS")
    lines.append("             Q&A pairs, answers independently recomputed + verified by")
    lines.append("             make_cardcheck_gold.py (license authored-gmatwiz).")
    lines.append("SOURCE     : gmatwiz/content/cardcheck_source.md - ONE original chapter")
    lines.append("             (percents + linear equations), the single source cards are made from.")
    lines.append("CHECKER    : mirrors ts/routes/gmat/aiChecker.ts - fields pass / correctness /")
    lines.append("             in_scope / well_formed / teaching_quality(0-10) / reasons. Where a")
    lines.append("             generated card matches a gold pair, its answer is ALSO cross-")
    lines.append("             verified against the known-correct gold answer.")
    lines.append("")
    lines.append("-" * 79)
    lines.append("PRE-SET CUTOFF (fixed BEFORE the results below; see card_check.py constants)")
    lines.append("-" * 79)
    lines.append("A generated card is ADMITTED only if ALL of:")
    lines.append("    correctness == true      (the marked answer is actually correct)")
    lines.append("  AND in_scope == true       (GMAT Quant PS: arithmetic/algebra, in taxonomy)")
    lines.append("  AND well_formed == true    (5 distinct non-empty options, valid key, clear)")
    lines.append(f"  AND teaching_quality >= {TEACHING_CUTOFF}   (0-10 scale; duplicates capped at "
                 f"{DUP_TEACHING_CAP})")
    lines.append("Any card that fails the cutoff is BLOCKED. A wrong-fact card is always blocked")
    lines.append("(a wrong fact is worse than no card).")
    lines.append("")
    lines.append("-" * 79)
    lines.append("REPRODUCE")
    lines.append("-" * 79)
    lines.append("  # Offline smoke test (no key) - validates the pipeline end-to-end:")
    lines.append(f"  {MOCK_CMD}")
    lines.append("")
    lines.append("  # Real numbers - pull the app's key from Firebase and run the live pipeline:")
    for cmd_line in LIVE_CMD.splitlines():
        lines.append(f"  {cmd_line}")
    lines.append("")
    lines.append("Full machine-readable per-card audit trail (every check + reasons) is written")
    lines.append("to gmatwiz/content/cardcheck_report.json.")
    lines.append("")
    lines.append("-" * 79)
    if mock:
        lines.append(f"RESULTS - MOCK smoke run (NOT real numbers)   [client={report['ai_client']}]")
    else:
        lines.append(f"RESULTS - LIVE run (real numbers)   [client={report['ai_client']}]")
    lines.append(f"n_generated={total}, gold={report['gold_count']}, "
                 f"cross-verified against gold={report['gold_cross_verified']}, "
                 f"cutoff teaching_quality>={TEACHING_CUTOFF}")
    lines.append("-" * 79)
    lines.append(f"{'bucket':<32}{'count':>8}{'share':>10}")
    lines.append(f"{'correct & useful (admitted)':<32}{c[BUCKET_GOOD]:>8}{pct(c[BUCKET_GOOD]):>10}")
    lines.append(f"{'wrong (blocked)':<32}{c[BUCKET_WRONG]:>8}{pct(c[BUCKET_WRONG]):>10}")
    lines.append(f"{'correct but bad teaching (blk)':<32}"
                 f"{c[BUCKET_BAD_TEACH]:>8}{pct(c[BUCKET_BAD_TEACH]):>10}")
    lines.append("-" * 79)
    lines.append(f"{'ADMITTED (passed cutoff)':<32}{report['admitted_count']:>8}"
                 f"{pct(report['admitted_count']):>10}")
    lines.append(f"{'BLOCKED (failed cutoff)':<32}{report['blocked_count']:>8}"
                 f"{pct(report['blocked_count']):>10}")
    lines.append("-" * 79)
    lines.append("")
    lines.append("-" * 79)
    lines.append("HONEST INTERPRETATION")
    lines.append("-" * 79)
    if mock:
        lines.append("These are NOT real quality numbers. --mock has no API key and no model: the")
        lines.append("50 candidates are deterministic perturbations of the gold set, planted to")
        lines.append("exercise every path - some faithful (correct + full explanation), some with a")
        lines.append("deliberately wrong answer letter, some with vague/trivial explanations, and")
        lines.append("some exact duplicates. So the split above just proves the pipeline WORKS end-")
        lines.append("to-end: it generates candidates, cross-verifies correctness against the known-")
        lines.append("correct gold answers, scores teaching quality, applies the pre-set cutoff, and")
        lines.append("BLOCKS every card that fails (all wrong-answer and bad-teaching/duplicate")
        lines.append("cards were blocked; only faithful cards were admitted). For REAL numbers -")
        lines.append("the model actually generating from the source and the checker re-solving each")
        lines.append("item - run the LIVE command above with the OpenAI key. This environment has")
        lines.append("no key, so only the mock smoke run is captured here.")
    else:
        lines.append("The counts above are real: the model generated the cards from the source and")
        lines.append("the checker re-solved each one (cross-verifying against the gold where items")
        lines.append("overlap). 'wrong' is the number that would have shipped a wrong fact had the")
        lines.append("cutoff not blocked them - the count the 7f gate exists to drive to zero.")
        lines.append("'correct but bad teaching' are answerable-but-not-shippable (vague, trivial,")
        lines.append("or duplicate). Only the 'correct & useful' cards passed the cutoff and would")
        lines.append("be admitted into the bank.")
    lines.append("")
    lines.append(_bar())

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Console table
# ---------------------------------------------------------------------------
def print_summary(report: Dict) -> None:
    c = report["counts"]
    total = report["n_generated"]
    print()
    tag = "MOCK smoke run (NOT real numbers)" if report["mode"] == "mock" else "LIVE run"
    print(f"GMATWiz 7f card check - {tag}  (client={report['ai_client']})")
    print(f"generated={total}  gold={report['gold_count']}  "
          f"cross-verified={report['gold_cross_verified']}  "
          f"cutoff: {PASS_RULE}")
    print("-" * 70)
    print(f"  correct & useful (admitted) : {c[BUCKET_GOOD]}")
    print(f"  wrong (blocked)             : {c[BUCKET_WRONG]}")
    print(f"  correct but bad teaching    : {c[BUCKET_BAD_TEACH]}")
    print("-" * 70)
    print(f"  ADMITTED = {report['admitted_count']}   BLOCKED = {report['blocked_count']}")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GMATWiz 7f AI card check.")
    parser.add_argument("--mock", action="store_true",
                        help="Deterministic offline smoke run (no key, MockClient).")
    parser.add_argument("--n", type=int, default=DEFAULT_N,
                        help=f"Number of candidate cards to generate (default {DEFAULT_N}).")
    parser.add_argument("--gold", default=DEFAULT_GOLD, help="Gold set JSON.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="The single source .md.")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Machine-readable report path.")
    parser.add_argument("--proof", default=DEFAULT_PROOF, help="Human-readable proof path.")
    args = parser.parse_args(argv)

    gold_path = os.path.abspath(args.gold)
    source_path = os.path.abspath(args.source)
    if not os.path.isfile(gold_path):
        print(f"Gold set not found: {gold_path}\nRun make_cardcheck_gold.py first.",
              file=sys.stderr)
        return 1
    if not os.path.isfile(source_path):
        print(f"Source not found: {source_path}", file=sys.stderr)
        return 1

    gold = load_gold(gold_path)
    if len(gold) < args.n:
        print(f"WARNING: gold has {len(gold)} items but n={args.n}; "
              f"mock will cycle through the gold set.", file=sys.stderr)
    with open(source_path, encoding="utf-8") as fh:
        source_text = fh.read()
    if not source_text.strip():
        print(f"Source is empty: {source_path}", file=sys.stderr)
        return 1

    client, ai_label = pick_ai_client(args.mock)
    if not args.mock and client is None:
        print("No AI client available (set OPENAI_API_KEY or GEMINI_API_KEY, or pass "
              "--mock).\nThe 7f checker fails closed without a model.", file=sys.stderr)
        return 2

    print(f"GMATWiz 7f card check - client={ai_label}  mode="
          f"{'mock' if args.mock else 'live'}  n={args.n}")
    print(f"  gold   = {gold_path} ({len(gold)} pairs)")
    print(f"  source = {source_path}")

    report = run(gold, source_text, mock=args.mock, n=args.n,
                 client=client, ai_label=ai_label)

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    write_proof(report, os.path.abspath(args.proof))

    print_summary(report)
    print(f"Wrote report -> {os.path.abspath(args.report)}")
    print(f"Wrote proof  -> {os.path.abspath(args.proof)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
