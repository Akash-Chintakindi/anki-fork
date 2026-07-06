# Copyright: GMATWiz contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Shared helpers for the GMATWiz reliability proofs (7g crash/offline + 7b sync).

Additive-only and read-through: these helpers drive the ALREADY-BUILT engine via
the public ``anki.collection.Collection`` API and ``anki.gmatwiz`` importer - the
same recipe the desktop/mobile apps use - so nothing here changes app behaviour.

Run everything with the prebuilt engine, e.g.:

    PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python tools/gmat-crash-test.py

The GMAT leaf-topic strings come from ``gmatwiz/content/taxonomy.py`` (the real
taxonomy: 18 Quant + 16 Verbal + 3 Data-Insights leaves) so the seeded questions
land in the same buckets coverage/mastery/scoring key off. If that module can't
be imported we fall back to an inline copy kept in lock-step with it.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List

# ---------------------------------------------------------------------------
# Authentic taxonomy (zero third-party deps) with an inline fallback.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_CONTENT = os.path.join(_REPO, "gmatwiz", "content")
if _CONTENT not in sys.path:
    sys.path.insert(0, _CONTENT)

try:  # pragma: no cover - exercised implicitly by the proof runs
    import taxonomy as _tax

    QUANT_TOPICS: List[str] = list(_tax.QUANT_TOPICS)
    VERBAL_TOPICS: List[str] = list(_tax.VERBAL_TOPICS)
    DI_TOPICS: List[str] = list(_tax.DI_TOPICS)
except Exception:  # keep the proofs runnable even if content moves
    QUANT_TOPICS = [
        "gmat::quant::arithmetic::number_properties",
        "gmat::quant::arithmetic::fractions",
        "gmat::quant::arithmetic::decimals",
        "gmat::quant::arithmetic::percents",
        "gmat::quant::arithmetic::ratios_proportions",
        "gmat::quant::arithmetic::exponents_roots",
        "gmat::quant::arithmetic::statistics",
        "gmat::quant::arithmetic::sets",
        "gmat::quant::arithmetic::counting",
        "gmat::quant::arithmetic::probability",
        "gmat::quant::algebra::linear_equations",
        "gmat::quant::algebra::quadratics",
        "gmat::quant::algebra::inequalities",
        "gmat::quant::algebra::absolute_value",
        "gmat::quant::algebra::functions",
        "gmat::quant::algebra::sequences",
        "gmat::quant::algebra::expressions",
        "gmat::quant::algebra::word_problems",
    ]
    VERBAL_TOPICS = [
        f"gmat::verbal::cr::{leaf}"
        for leaf in (
            "assumption", "strengthen", "weaken", "evaluate", "inference",
            "explain_paradox", "flaw", "boldface", "complete_argument",
        )
    ] + [
        f"gmat::verbal::rc::{leaf}"
        for leaf in (
            "main_idea", "detail", "inference", "function", "structure",
            "tone", "application",
        )
    ]
    DI_TOPICS = [
        "gmat::di::reasoning::data_sufficiency",
        "gmat::di::reasoning::two_part_analysis",
        "gmat::di::reasoning::multi_source_reasoning",
    ]

SECTION_TOPICS: Dict[str, List[str]] = {
    "quant": QUANT_TOPICS,
    "verbal": VERBAL_TOPICS,
    "di": DI_TOPICS,
}
SECTION_DECK: Dict[str, str] = {
    "quant": "GMAT::Quant",
    "verbal": "GMAT::Verbal",
    "di": "GMAT::DI",
}

# A big per-day limit so the whole seeded deck is reviewable in one session; this
# is a proof harness, not a study plan. Set on BOTH the preset (perDay) and the
# v3 deck-level override (newLimit/reviewLimit), which is what actually raises the
# number of new cards the scheduler will hand out.
_BIG_LIMIT = 1_000_000


def make_questions(section: str, tag: str, n: int) -> List[dict]:
    """Build ``n`` normalized question dicts for ``section``, spread round-robin
    across that section's real leaf topics (so topic coverage is exercised).

    Stems embed ``tag`` + index so they are unique (the importer dedups by a
    normalized stem hash - identical stems would be skipped)."""
    topics = SECTION_TOPICS[section]
    out: List[dict] = []
    for i in range(n):
        topic = topics[i % len(topics)]
        leaf = topic.split("::")[-1]
        out.append({
            "stem": f"[{tag} #{i}] GMAT {section} practice item on {leaf} "
                    f"(seed id {tag}-{i}). What is x?",
            "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
            "correct": "C",
            "explanation": f"Deterministic worked solution for a {leaf} item.",
            "topic": topic,
            "difficulty": "medium",
            "source": f"proof-seed:{tag}",
        })
    return out


def import_for_section(col, section: str, questions: List[dict], deck: str | None = None) -> int:
    """Import questions with the right notetype importer for ``section``."""
    import anki.gmatwiz as gw

    deck = deck or SECTION_DECK[section]
    if section == "verbal":
        return gw.import_verbal_questions(col, questions, deck)
    if section == "di":
        return gw.import_di_questions(col, questions, deck)
    return gw.import_questions(col, questions, deck)


def raise_deck_limits(col, deck: str) -> int:
    """Raise new/review limits for ``deck`` so a whole seeded deck is reviewable,
    select it, and return its id. Idempotent."""
    did = col.decks.id(deck)
    col.decks.select(did)
    conf = col.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = _BIG_LIMIT
    conf["rev"]["perDay"] = _BIG_LIMIT
    col.decks.update_config(conf)
    d = col.decks.get(did)
    d["newLimit"] = _BIG_LIMIT
    d["reviewLimit"] = _BIG_LIMIT
    col.decks.save(d)
    return did


def revlog_count(col) -> int:
    return col.db.scalar("select count() from revlog") or 0


def revlog_ids(col) -> List[int]:
    """All revlog ids (each id is the review's epoch-ms timestamp)."""
    return [row[0] for row in col.db.all("select id from revlog order by id")]


def integrity_report(col) -> dict:
    """Run SQLite ``pragma integrity_check`` + ``quick_check`` AND Anki's own DB
    check (``col.fix_integrity()`` -> backend ``check_database``). Returns a dict;
    ``ok`` is True only if every check is clean."""
    def _rows(sql: str) -> List[str]:
        return [r[0] for r in col.db.execute(sql)]

    pragma = _rows("pragma integrity_check")
    quick = _rows("pragma quick_check")
    pragma_ok = pragma == ["ok"]
    quick_ok = quick == ["ok"]
    try:
        msg, dbcheck_ok = col.fix_integrity()
    except Exception as exc:  # a raising DB check is itself a corruption signal
        msg, dbcheck_ok = f"{type(exc).__name__}: {exc}", False
    return {
        "ok": bool(pragma_ok and quick_ok and dbcheck_ok),
        "pragma_ok": pragma_ok,
        "pragma": pragma,
        "quick_ok": quick_ok,
        "quick": quick,
        "dbcheck_ok": bool(dbcheck_ok),
        "dbcheck_msg": (msg or "").strip().replace("\n", " | "),
    }
