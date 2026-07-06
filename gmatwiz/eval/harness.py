#!/usr/bin/env python3
"""GMATWiz reproducible evaluation harness (shared foundation).

This module is the deterministic, seeded backbone that the three evals build on
(``ablation.py``, ``paraphrase.py``, ``model_eval.py``). It drives the *real*
prebuilt GMATWiz engine (Anki's Rust scheduler via ``anki.collection`` +
``anki.gmatwiz``) with a *simulated learner*, so anyone can re-run and get the
same numbers.

Why a simulated learner? The engine change under test - topic-aware scheduling
(PRD Section 7) - only changes the *order* review cards are surfaced in. To
measure whether that ordering helps *learning* at equal study time we need a
ground-truth learner whose ability we control and can read out on held-out
items. Real students would be Step 4 (bonus, PRD Section 11); this is the honest,
reproducible stand-in.

Public API (kept stable - the other eval scripts import these names):

    GUESS                        5-option MCQ guess floor (0.2)
    SimConfig                    dataclass of all knobs (seeded)
    Learner                      the simulated student (theta per topic + memory)
    ArmResult                    dataclass returned by run_arm
    make_questions(...)          build a bank of unique-stem question dicts
    build_collection(...)        import a bank into a real engine collection
    run_arm(cfg, arm)            run one arm ("full"|"ablation"|"plain")
    advance_one_day(col)         the "crt trick" (advance the engine clock 1 day)
    fsrs_retrievability(t, S)    FSRS-5 power forgetting curve R(t | stability)

The engine driver recipe (validated) lives in ``build_collection`` / ``run_arm``.

Run the smoke test (from the repo root):

    PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python -m gmatwiz.eval.harness
"""

from __future__ import annotations

import hashlib
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Locate the taxonomy (real Quant leaf topics). ------------------------
# House convention (see gmatwiz/content/eval_tagging.py): add gmatwiz/content to
# sys.path and import the standalone module. Fall back to a hardcoded, sorted
# subset of real leaves so the harness never hard-fails if the path shifts.
_CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")
if _CONTENT_DIR not in sys.path:
    sys.path.insert(0, _CONTENT_DIR)

try:  # pragma: no cover - exercised implicitly by every run
    import taxonomy  # type: ignore

    _ALL_QUANT: List[str] = sorted(taxonomy.QUANT_TOPICS)
except Exception:  # pragma: no cover - defensive fallback only
    _ALL_QUANT = sorted(
        [
            "gmat::quant::algebra::absolute_value",
            "gmat::quant::algebra::expressions",
            "gmat::quant::algebra::functions",
            "gmat::quant::algebra::inequalities",
            "gmat::quant::algebra::linear_equations",
            "gmat::quant::algebra::quadratics",
            "gmat::quant::algebra::sequences",
            "gmat::quant::algebra::word_problems",
            "gmat::quant::arithmetic::counting",
            "gmat::quant::arithmetic::decimals",
            "gmat::quant::arithmetic::exponents_roots",
            "gmat::quant::arithmetic::fractions",
            "gmat::quant::arithmetic::number_properties",
            "gmat::quant::arithmetic::percents",
            "gmat::quant::arithmetic::probability",
            "gmat::quant::arithmetic::ratios_proportions",
            "gmat::quant::arithmetic::sets",
            "gmat::quant::arithmetic::statistics",
        ]
    )

# A deterministic 12-leaf Quant subset used by default across the evals.
DEFAULT_TOPICS: List[str] = _ALL_QUANT[:12]

# 5-option multiple choice: a pure guess is right 1 in 5.
GUESS = 0.2

# How fast a per-card "I recognize this exact card" familiarity saturates with
# repeated exposure (used only when wording_memorization > 0). Higher exposure
# count -> closer to 1.0.
_FAM_DECAY = 0.55

# Running per-topic accuracy EMA smoothing (feeds set_topic_mastery each day).
_EMA_ALPHA = 0.45


# ---------------------------------------------------------------------------
# Small engine helpers
# ---------------------------------------------------------------------------
def fsrs_retrievability(elapsed_days: float, stability: float) -> float:
    """FSRS-5 power forgetting curve: R(t) = (1 + (19/81) * t / S)^(-0.5).

    ``stability`` S is the number of days at which R falls to 0.9. Returns 1.0
    for a non-positive elapsed time and clamps S to a tiny positive value.
    """
    if elapsed_days <= 0:
        return 1.0
    s = max(float(stability), 1e-6)
    return (1.0 + (19.0 / 81.0) * (float(elapsed_days) / s)) ** (-0.5)


def advance_one_day(col) -> None:
    """Advance the engine's clock by exactly one day (the validated "crt trick").

    Moving the collection creation time back one day makes "today" one day later,
    so due reviews recur and topic-aware ordering can concentrate reps on weak
    topics across days.
    """
    crt = col.db.scalar("select crt from col")
    col.db.execute("update col set crt = ?", crt - 86400)
    col.reset()


def reset_all_due_today(col) -> None:
    """Make every card a fresh review due *today* (and un-bury/un-suspend).

    This models a motivated student who always has a full backlog eligible: every
    card is a candidate for today's fixed review budget, so the *only* thing that
    decides which cards actually get reviewed is the queue order - which is
    exactly the lever topic-aware scheduling pulls. It sidesteps SM-2/FSRS
    same-day relearn churn and bury/unbury timing (which fight the crt day-trick)
    without touching the FSRS memory state (stability/difficulty live in a
    separate column and keep accruing across reviews).
    """
    today = col.sched.today
    col.db.execute(
        "update cards set type = 2, queue = 2, due = ?, ivl = 1, odue = 0, odid = 0",
        today,
    )
    col.reset()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class SimConfig:
    """All knobs for one simulated run. Everything downstream is a function of
    these values plus the arm, so runs are fully reproducible."""

    seed: int
    topics: List[str]
    cards_per_topic: int = 40
    heldout_per_topic: int = 20
    days: int = 15
    daily_budget: int = 40
    learn_rate: float = 0.12
    careless: float = 0.05
    wording_memorization: float = 0.0
    enable_fsrs: bool = False


# ---------------------------------------------------------------------------
# The simulated learner
# ---------------------------------------------------------------------------
class Learner:
    """A deterministic, seeded simulated student.

    * ``theta[topic]`` in [0,1] is latent ability on that topic. It is seeded
      with a heterogeneous spread so ~half the topics start WEAK (~0.15-0.35)
      and ~half start STRONG (~0.7-0.9). That heterogeneity is the whole reason
      topic-aware reallocation can matter: reps spent on a weak topic buy more
      ability than reps on an already-strong one (diminishing returns in
      ``learn``).
    * ``p_ability(topic)`` maps ability to the probability of a *correct MCQ
      answer on a fresh item*: GUESS + (1-GUESS)*theta  (a guess floor of 0.2).
    * ``attempt_card`` is correctness on an *already-studied* card. It may exceed
      p_ability through a per-card familiarity that grows with each exposure and
      is scaled by ``wording_memorization`` - i.e. the student memorizes the
      exact wording of that card. This bonus is per-card and does NOT transfer to
      new items (that is what the paraphrase eval exploits).
    * ``attempt_heldout`` is the EXPECTED probability on a brand-new item of a
      topic (no card familiarity) - the honest measure of transferable skill.
    * ``learn`` nudges ability up after each rep, with diminishing returns, so
      the same rep helps a weak topic much more than a strong one.
    """

    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.learn_rate = cfg.learn_rate
        self.careless = cfg.careless
        self.wording_memorization = cfg.wording_memorization
        import random

        rng = random.Random(cfg.seed)
        topics = list(cfg.topics)
        # Deterministic weak/strong split: shuffle by seed, first half weak.
        order = topics[:]
        rng.shuffle(order)
        half = len(order) // 2
        self.theta: Dict[str, float] = {}
        self.weak_topics: List[str] = []
        self.strong_topics: List[str] = []
        for i, t in enumerate(order):
            if i < half:
                self.theta[t] = round(rng.uniform(0.15, 0.35), 4)
                self.weak_topics.append(t)
            else:
                self.theta[t] = round(rng.uniform(0.70, 0.90), 4)
                self.strong_topics.append(t)
        self.weak_topics.sort()
        self.strong_topics.sort()
        # Per-card exposure counts (drive familiarity). Keyed by an opaque card
        # key (card id or stem tag) supplied by the caller.
        self._exposures: Dict[str, int] = {}
        self._seed = cfg.seed

    # -- probabilities ------------------------------------------------------
    def p_ability(self, topic: str) -> float:
        """P(correct on a *fresh* item of this topic) = guess floor + skill."""
        return GUESS + (1.0 - GUESS) * self.theta.get(topic, 0.5)

    def _familiarity(self, exposures: int) -> float:
        """Per-card recognition in [0,1): 0 at first sight, -> 1 with reps."""
        if exposures <= 0:
            return 0.0
        return 1.0 - (_FAM_DECAY ** exposures)

    def _draw(self, card_key: str, k: int) -> float:
        """Deterministic uniform in [0,1) from (seed, card_key, exposure index).

        Order-independent so an arm's randomness depends only on *what* was
        studied and how many times, not on interleaving - which makes the paired
        full-vs-ablation comparison clean.
        """
        h = hashlib.sha1(f"{self._seed}|{card_key}|{k}".encode("utf-8")).hexdigest()
        return int(h[:13], 16) / float(0x10 ** 13)

    # -- attempts -----------------------------------------------------------
    def attempt_card(self, topic: str, card_key: str) -> bool:
        """Correctness on a *studied* card; grows a per-card familiarity bonus.

        p = p_ability(topic) + wording_memorization * familiarity(exposures),
        then a careless-error haircut. Deterministic given (seed, card_key,
        exposure index). Increments the exposure count as a side effect.
        """
        k = self._exposures.get(card_key, 0)
        fam = self._familiarity(k)
        p = self.p_ability(topic) + self.wording_memorization * fam
        p = max(0.0, min(1.0, p)) * (1.0 - self.careless)
        correct = self._draw(card_key, k) < p
        self._exposures[card_key] = k + 1
        return correct

    def attempt_heldout(self, topic: str) -> float:
        """Expected accuracy on a brand-new item of ``topic`` (no card memory).

        Returned as the probability (not a coin flip): the eval averages these
        expected values, which is a lower-variance, honest read of transferable
        skill on new mixed-topic questions.
        """
        return self.p_ability(topic)

    def sample_heldout(self, topic: str, key: str) -> bool:
        """Bernoulli draw of a fresh-item outcome (used where a 0/1 is needed)."""
        p = self.p_ability(topic) * (1.0 - self.careless)
        return self._draw(f"held|{key}", 0) < p

    # -- learning -----------------------------------------------------------
    def learn(self, topic: str, correct: bool) -> None:
        """One study rep. Diminishing returns: gain ~ (1 - theta), and a correct
        rep helps more than a wrong one. So reps on weak topics buy the most."""
        th = self.theta.get(topic, 0.5)
        gain = self.learn_rate * (1.0 - th) * (1.0 if correct else 0.4)
        self.theta[topic] = min(1.0, th + gain)


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------
def make_questions(
    topics: List[str], n_per_topic: int, seed: int, prefix: str
) -> List[Dict]:
    """Build ``n_per_topic`` question dicts per topic with UNIQUE stems.

    ``anki.gmatwiz.import_questions`` dedups by normalized-stem hash, so every
    stem must be unique - we vary the numbers and embed the topic + prefix +
    index. Each item is tagged to its leaf topic (stored in the Topic field AND
    added as a tag, which is what ``set_topic_mastery`` keys off).
    """
    import random

    rng = random.Random(f"make_questions|{seed}|{prefix}")
    out: List[Dict] = []
    for topic in topics:
        leaf = topic.split("::")[-1]
        for i in range(n_per_topic):
            a = rng.randint(2, 99)
            b = rng.randint(2, 99)
            c = a + b
            # Correct answer is c; distractors are deterministic near-misses.
            opts = [c, c + 1, c - 1, a * b % 97 + 1, abs(a - b) + 1]
            labels = ["A", "B", "C", "D", "E"]
            options = {labels[j]: str(opts[j]) for j in range(5)}
            out.append(
                {
                    "stem": (
                        f"[{prefix}:{leaf}:{i}] A {leaf} drill: if p = {a} and "
                        f"q = {b}, what is p + q? (item {prefix}-{leaf}-{i})"
                    ),
                    "options": options,
                    "correct": "A",
                    "explanation": f"p + q = {a} + {b} = {c}.",
                    "topic": topic,
                    "difficulty": "medium",
                    "source": f"gmatwiz-eval-sim:{prefix}",
                }
            )
    return out


# ---------------------------------------------------------------------------
# Engine collection
# ---------------------------------------------------------------------------
def build_collection(path: str, questions: List[Dict], enable_fsrs: bool = False):
    """Import ``questions`` into a fresh engine collection and prime it to study.

    Validated recipe: import via anki.gmatwiz, select the deck (otherwise the
    queue is empty), and raise the per-day new/review limits so the daily budget
    is the only cap. Learning/relearning steps are cleared so a Good answer
    graduates a card straight to a day-scale review (which is where topic-aware
    ordering and FSRS intervals apply). When ``enable_fsrs`` is set, FSRS is
    turned on so cards accrue a memory state (stability/difficulty).
    """
    import anki.gmatwiz as gw
    from anki.collection import Collection

    if os.path.exists(path):
        os.remove(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    col = Collection(path)

    gw.import_questions(col, questions, "GMAT::Quant")

    if enable_fsrs:
        col.set_config("fsrs", True)

    did = col.decks.id("GMAT::Quant")
    col.decks.select(did)
    conf = col.decks.config_dict_for_deck_id(did)
    conf["new"]["perDay"] = 100000
    conf["rev"]["perDay"] = 100000
    conf["new"]["delays"] = []      # Good on a new card -> straight to review
    conf["lapse"]["delays"] = []    # Again on a review -> back to review, no steps
    # Cap the review interval at 1 day so every studied card is eligible for
    # review every day. This turns the study loop into the fixed-daily-budget
    # setting where topic-aware ordering is the ONLY thing that decides which
    # cards get today's reps - i.e. it isolates the scheduling lever under test.
    # (FSRS/SM-2 memory state still evolves; only the surfacing interval is
    # capped - the same "equal study time, different allocation" control the
    # ablation depends on.)
    conf["rev"]["maxIvl"] = 1
    col.decks.save(conf)
    # Introduce new cards before reviews each day so the bank is exposed quickly
    # and the remaining days are a pure fixed-budget review-allocation contest.
    col.set_config("newSpread", 2)  # NEW_CARDS_FIRST
    col.reset()
    return col


# ---------------------------------------------------------------------------
# Arm result + runner
# ---------------------------------------------------------------------------
@dataclass
class ArmResult:
    arm: str
    total_reviews: int
    reps_per_topic: Dict[str, int]
    final_theta: Dict[str, float]
    heldout_overall: float
    heldout_per_topic: Dict[str, float]
    reviews: List[Dict] = field(default_factory=list)
    weak_topics: List[str] = field(default_factory=list)
    strong_topics: List[str] = field(default_factory=list)


def run_arm(cfg: SimConfig, arm: str) -> ArmResult:
    """Run one arm end to end on the real engine and score held-out ability.

    arm:
      * "full"     - topicAwareScheduling ON. Before each day we push each
                     topic's running accuracy EMA into set_topic_mastery, so the
                     review queue keeps surfacing weak topics first.
      * "ablation" - identical learner / seed / bank / budget, but
                     topicAwareScheduling OFF. We still compute the EMA and still
                     call set_topic_mastery (so the only difference is the
                     ordering toggle), it just has no effect on order.
      * "plain"    - vanilla Anki: no topic mastery written, toggle OFF, default
                     order.

    Study loop: for each day we (re)build the queue and answer EXACTLY up to
    daily_budget cards, counting EVERY answerCard toward the budget so total
    reviews are equal across arms (the equal-study-time control). We rate Good(3)
    when the learner gets it right, else Again(1), call learner.learn each time,
    then advance one day.
    """
    if arm not in ("full", "ablation", "plain"):
        raise ValueError(f"unknown arm {arm!r}")

    import tempfile

    learner = Learner(cfg)
    studied = make_questions(cfg.topics, cfg.cards_per_topic, cfg.seed, "std")

    tmpdir = tempfile.mkdtemp(prefix=f"gw_arm_{arm}_")
    col_path = os.path.join(tmpdir, "col.anki2")
    col = build_collection(col_path, studied, enable_fsrs=cfg.enable_fsrs)

    topic_aware = arm == "full"
    write_mastery = arm in ("full", "ablation")
    col.set_config("topicAwareScheduling", topic_aware)

    # Map each card id -> its leaf topic (read once; stable for the run).
    card_topic: Dict[int, str] = {}
    for cid in col.find_cards('deck:"GMAT::Quant"'):
        card_topic[cid] = col.get_card(cid).note()["Topic"]

    # Running per-topic accuracy EMA, seeded from a first-exposure diagnostic
    # (the learner's expected accuracy on a fresh item of each topic).
    ema: Dict[str, float] = {t: learner.p_ability(t) for t in cfg.topics}

    reps_per_topic: Dict[str, int] = {t: 0 for t in cfg.topics}
    reviews: List[Dict] = []
    # FSRS bookkeeping for the optional predicted-retrievability record.
    last_day: Dict[int, int] = {}
    last_stab: Dict[int, float] = {}

    total_reviews = 0
    for day in range(cfg.days):
        if write_mastery:
            for t in cfg.topics:
                col._backend.set_topic_mastery(topic=t, mastery=float(ema[t]))
        # Everything eligible today; order (weak-first when ON) does the rest.
        reset_all_due_today(col)

        answered = 0
        guard = 0
        while answered < cfg.daily_budget and guard < cfg.daily_budget * 50:
            guard += 1
            card = col.sched.getCard()
            if card is None:
                break
            cid = card.id
            topic = card_topic.get(cid) or card.note()["Topic"]

            pred_r: Optional[float] = None
            if cfg.enable_fsrs and cid in last_stab:
                pred_r = fsrs_retrievability(day - last_day.get(cid, day), last_stab[cid])

            correct = learner.attempt_card(topic, str(cid))
            ease = 3 if correct else 1
            col.sched.answerCard(card, ease)
            # Seen once today -> remove from today's queue (morning reset undoes).
            col.sched.bury_cards([cid])

            learner.learn(topic, correct)
            ema[topic] = (1.0 - _EMA_ALPHA) * ema[topic] + _EMA_ALPHA * (1.0 if correct else 0.0)
            reps_per_topic[topic] += 1
            rec = {"day": day, "topic": topic, "correct": bool(correct), "card_key": cid}
            if cfg.enable_fsrs:
                rec["pred_r"] = pred_r
                cobj = col.get_card(cid)
                if cobj.memory_state is not None:
                    last_stab[cid] = float(cobj.memory_state.stability)
                last_day[cid] = day
            reviews.append(rec)
            answered += 1
            total_reviews += 1

        advance_one_day(col)

    final_theta = dict(learner.theta)
    heldout_per_topic = {t: learner.attempt_heldout(t) for t in cfg.topics}
    # Held-out overall = mean expected accuracy over all held-out items (each
    # topic contributes heldout_per_topic items, equal counts -> mean of topics).
    heldout_overall = sum(heldout_per_topic.values()) / len(heldout_per_topic)

    col.close()
    import shutil

    shutil.rmtree(tmpdir, ignore_errors=True)

    return ArmResult(
        arm=arm,
        total_reviews=total_reviews,
        reps_per_topic=reps_per_topic,
        final_theta=final_theta,
        heldout_overall=heldout_overall,
        heldout_per_topic=heldout_per_topic,
        reviews=reviews,
        weak_topics=list(learner.weak_topics),
        strong_topics=list(learner.strong_topics),
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
def _smoke() -> int:
    import warnings

    warnings.filterwarnings("ignore")

    cfg = SimConfig(
        seed=0,
        topics=DEFAULT_TOPICS,
        cards_per_topic=8,
        heldout_per_topic=10,
        days=10,
        daily_budget=24,
    )
    print("GMATWiz eval harness - smoke test")
    print(f"topics={len(cfg.topics)} cards/topic={cfg.cards_per_topic} "
          f"days={cfg.days} budget={cfg.daily_budget} seed={cfg.seed}")

    full = run_arm(cfg, "full")
    abl = run_arm(cfg, "ablation")

    weak = full.weak_topics
    strong = full.strong_topics

    def reps_on(res: ArmResult, group: List[str]) -> int:
        return sum(res.reps_per_topic[t] for t in group)

    print(f"\ntotal reviews: full={full.total_reviews} ablation={abl.total_reviews} "
          "(should be equal - the equal-study-time control)")
    print(f"weak topics ({len(weak)}):   {[t.split('::')[-1] for t in weak]}")
    print(f"strong topics ({len(strong)}): {[t.split('::')[-1] for t in strong]}")

    print("\nReps on WEAK topics:   "
          f"full={reps_on(full, weak):4d}   ablation={reps_on(abl, weak):4d}")
    print("Reps on STRONG topics: "
          f"full={reps_on(full, strong):4d}   ablation={reps_on(abl, strong):4d}")

    print(f"\nHeld-out overall accuracy: full={full.heldout_overall:.4f} "
          f"ablation={abl.heldout_overall:.4f} "
          f"delta={full.heldout_overall - abl.heldout_overall:+.4f}")

    ok = reps_on(full, weak) > reps_on(abl, weak)
    print("\nWEAK topics got MORE reps in 'full' than 'ablation': "
          f"{'YES' if ok else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
