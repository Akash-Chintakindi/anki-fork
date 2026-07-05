#!/usr/bin/env python3
"""Author the GMATWiz Reading Comprehension content (Phase B).

ORIGINAL GMAT-style Reading Comprehension passages + questions written for
GMATWiz. Nothing is copied from any prep book or source: the passages are
original expository prose on neutral academic topics, and the questions are
written to exercise the RC question-type taxonomy (main idea / detail /
inference / function / structure / tone / application).

Emits two files next to this script:
  * verbal_rc_questions.json -- passage-GROUPED bank (imported: one GMAT Verbal
    note per question, all sharing their passage's Passage/PassageId fields).
  * verbal_rc_seed.json      -- FLAT gold set (each item carries its passage
    inline) used by eval_tagging.py --section verbal for the RC eval.

License for all items: authored-gmatwiz.

Run:  python3 make_verbal_rc.py
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from typing import Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import taxonomy  # noqa: E402

SOURCE = "GMATWiz original (authored)"
LICENSE = "authored-gmatwiz"
V = taxonomy.VERBAL_PREFIX  # "gmat::verbal"


def _t(leaf: str) -> str:
    return f"{V}::rc::{leaf}"


def opts(a, b, c, d, e):
    return {"A": a, "B": b, "C": c, "D": d, "E": e}


def q(topic_leaf, difficulty, stem, options, correct, explanation):
    return {
        "topic": _t(topic_leaf),
        "difficulty": difficulty,
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# ORIGINAL passages, each with several questions of varied RC types.
# ---------------------------------------------------------------------------
PASSAGES: List[Dict] = [
    {
        "passage_id": "rc-tardigrade",
        "passage": (
            "Tardigrades, microscopic animals often called water bears, are among the "
            "hardiest organisms known. When their watery habitats dry out, tardigrades "
            "expel most of the water from their bodies and enter a dormant state called "
            "the tun, in which metabolism slows to a virtual standstill. In this state "
            "they can survive extreme cold, intense radiation, and even the vacuum of "
            "space. Early researchers assumed that a sugar called trehalose, which some "
            "dormant organisms use to protect their cells, was the key to this endurance. "
            "More recent work, however, has shown that many tardigrade species produce "
            "little trehalose. Instead, these species rely on a set of proteins, unique "
            "to tardigrades, that form a glass-like matrix around delicate cellular "
            "structures as the animal dries. Because these proteins can be transferred to "
            "other cells in the laboratory, some scientists hope they might one day help "
            "preserve biological materials such as vaccines without refrigeration."
        ),
        "questions": [
            q(
                "main_idea", "medium",
                "The primary purpose of the passage is to",
                opts(
                    "describe a mechanism that accounts for an organism's unusual endurance and note a possible application of it",
                    "argue that trehalose plays no role in the survival of any dormant organism",
                    "compare tardigrades with other microscopic animals that enter dormancy",
                    "trace the history of research on the vacuum of space",
                    "explain why vaccines currently require refrigeration",
                ),
                "A",
                "The passage explains how tardigrades survive drying (the protein matrix, correcting the earlier trehalose assumption) and closes with a possible application (preserving vaccines). A captures both.",
            ),
            q(
                "detail", "easy",
                "According to the passage, the tun state is characterized by",
                opts(
                    "a metabolism that slows to a virtual standstill",
                    "an increase in the animal's water content",
                    "the production of large amounts of trehalose",
                    "a permanent loss of the ability to revive",
                    "the transfer of proteins to other organisms",
                ),
                "A",
                "The passage states that in the tun state 'metabolism slows to a virtual standstill.' The other options contradict or overstate the text.",
            ),
            q(
                "inference", "hard",
                "The passage suggests that the earlier assumption about trehalose was",
                opts(
                    "incorrect as a general explanation for tardigrade endurance, because many species produce little of it",
                    "never tested by any researcher",
                    "correct for every tardigrade species studied",
                    "based on observations of the vacuum of space",
                    "unrelated to the survival of any organism",
                ),
                "A",
                "Since 'many tardigrade species produce little trehalose,' the earlier assumption cannot be the general explanation. A follows; B, C, D, E overreach or contradict.",
            ),
            q(
                "function", "medium",
                "The author mentions that the protective proteins can be transferred to other cells primarily in order to",
                opts(
                    "support the suggestion that the proteins might have practical uses",
                    "prove that trehalose is unnecessary for any organism",
                    "explain why tardigrades expel water when their habitats dry out",
                    "question whether tardigrades can survive radiation",
                    "describe the structure of the tun state",
                ),
                "A",
                "The transfer-to-other-cells detail sets up the closing point that the proteins 'might one day help preserve biological materials.' Its function is to support that application.",
            ),
        ],
    },
    {
        "passage_id": "rc-guilds",
        "passage": (
            "Medieval craft guilds are often portrayed simply as early trade unions that "
            "protected workers. Their role, however, was considerably broader. A guild "
            "regulated the quality of goods produced in its trade, set standards for "
            "training, and controlled who could practice the craft within a town. To many "
            "historians, these functions look restrictive, and it is true that guilds "
            "limited competition. Yet the same rules that limited entry also guaranteed "
            "buyers a predictable level of quality at a time when there were few other "
            "ways to verify a craftsman's skill. A customer purchasing a barrel from a "
            "guild cooper could reasonably assume it would not leak, because the cooper "
            "had passed the guild's examination. Some economic historians therefore argue "
            "that guilds, whatever their costs to would-be competitors, lowered the risk "
            "of commerce and so helped trade to expand. The debate over whether guilds "
            "were on balance helpful or harmful remains unresolved."
        ),
        "questions": [
            q(
                "main_idea", "medium",
                "The passage is primarily concerned with",
                opts(
                    "presenting a more complex view of guilds than the common portrayal allows",
                    "proving that guilds were purely harmful to medieval commerce",
                    "describing the examination a guild cooper had to pass",
                    "arguing that guilds were identical to modern trade unions",
                    "explaining how barrels were manufactured in medieval towns",
                ),
                "A",
                "The passage opens by noting guilds are 'often portrayed simply' one way, then broadens that view (quality assurance, lowered risk). A captures this corrective purpose.",
            ),
            q(
                "inference", "hard",
                "It can be inferred from the passage that, in the period discussed, buyers",
                opts(
                    "had limited means of judging a craftsman's skill apart from guild membership",
                    "always preferred goods made outside the guild system",
                    "were legally required to buy from guild members",
                    "could easily test every product before purchase",
                    "distrusted goods that carried a guild's approval",
                ),
                "A",
                "The passage says there 'were few other ways to verify a craftsman's skill,' implying buyers relied on guild membership as a signal. A follows.",
            ),
            q(
                "tone", "medium",
                "The author's attitude toward the claim that guilds were merely restrictive can best be described as",
                opts(
                    "qualified disagreement",
                    "complete acceptance",
                    "scornful dismissal",
                    "indifference",
                    "enthusiastic endorsement",
                ),
                "A",
                "The author concedes guilds limited competition ('it is true') but argues they also lowered commercial risk, disagreeing in a measured way. A ('qualified disagreement') fits.",
            ),
            q(
                "structure", "hard",
                "Which of the following best describes the organization of the passage?",
                opts(
                    "A common view is stated, complicated by additional considerations, and left as an open debate.",
                    "A thesis is stated and then supported by a single extended example.",
                    "Two historians' theories are compared and one is shown to be false.",
                    "A chronological history of guilds is presented from origin to decline.",
                    "A problem is described and a definitive solution is proposed.",
                ),
                "A",
                "The passage gives the simple portrayal, adds broader functions and the risk-lowering argument, and ends noting the debate is 'unresolved.' A matches.",
            ),
        ],
    },
    {
        "passage_id": "rc-darkskies",
        "passage": (
            "For most of human history the night sky was a shared feature of experience, "
            "but artificial lighting has made truly dark skies rare near cities. The glow "
            "of streetlights and buildings scatters in the atmosphere and washes out all "
            "but the brightest stars, a phenomenon known as skyglow. Astronomers were the "
            "first to raise the alarm, since skyglow degrades observations from ground-based "
            "telescopes. In recent decades, however, the concern has widened. Researchers "
            "have documented that excessive nighttime light disrupts the behavior of "
            "nocturnal animals: migrating birds veer off course, and hatchling sea turtles, "
            "which navigate toward the brightest horizon, crawl inland toward roads instead "
            "of out to sea. Some studies also link chronic exposure to light at night with "
            "disrupted sleep in humans. Advocates for dark skies stress that the remedy is "
            "not to abandon outdoor lighting but to use it more thoughtfully—shielding "
            "fixtures so light points downward and switching to warmer tones—measures that "
            "reduce skyglow while still lighting the ground where people need it."
        ),
        "questions": [
            q(
                "main_idea", "easy",
                "The main idea of the passage is that",
                opts(
                    "excessive artificial light causes a range of problems that can be reduced through better lighting practices",
                    "ground-based telescopes should be replaced with space-based ones",
                    "outdoor lighting should be eliminated to protect wildlife",
                    "sea turtles are the species most harmed by artificial light",
                    "skyglow is a concern only for professional astronomers",
                ),
                "A",
                "The passage catalogs harms from skyglow (astronomy, wildlife, sleep) and ends with thoughtful-lighting remedies. A captures both problem and solution; the others are too narrow or contradicted.",
            ),
            q(
                "detail", "medium",
                "According to the passage, hatchling sea turtles are affected by artificial light because they",
                opts(
                    "navigate toward the brightest horizon",
                    "are attracted to warm-toned light specifically",
                    "sleep less when exposed to light at night",
                    "migrate along the same routes as birds",
                    "cannot survive near ground-based telescopes",
                ),
                "A",
                "The passage states the hatchlings 'navigate toward the brightest horizon' and so head inland toward roads. A restates this; the others misattribute the mechanism.",
            ),
            q(
                "function", "medium",
                "The author mentions migrating birds and sea turtles primarily in order to",
                opts(
                    "illustrate that the harms of skyglow extend beyond astronomy",
                    "argue that wildlife matters more than human sleep",
                    "explain how ground-based telescopes work",
                    "prove that outdoor lighting should be abandoned",
                    "describe how warmer light tones are produced",
                ),
                "A",
                "The birds and turtles are examples introduced after 'the concern has widened,' showing skyglow's reach beyond astronomy. A gives their function.",
            ),
            q(
                "application", "hard",
                "Which of the following outdoor-lighting choices is most consistent with the advocates' recommendations described in the passage?",
                opts(
                    "A downward-shielded, warm-toned lamp that illuminates a walkway",
                    "A bright, upward-facing floodlight aimed at the sky",
                    "A cool blue-white light left on all night across an empty field",
                    "The complete removal of all lighting from public streets",
                    "A rotating beacon designed to be visible for many miles",
                ),
                "A",
                "The advocates favor shielding fixtures to point light downward and using warmer tones while still lighting the ground. A matches; the others increase skyglow or abandon lighting entirely.",
            ),
        ],
    },
]


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def build():
    ts = now_iso()
    grouped: List[Dict] = []
    flat: List[Dict] = []
    failures: List[str] = []
    seen_ids = set()

    for p in PASSAGES:
        pid = p["passage_id"]
        passage = p["passage"]
        group_qs: List[Dict] = []
        for i, item in enumerate(p["questions"]):
            tag = f"{pid} #{i + 1} [{item['topic']}]"
            o = item["options"]
            if set(o.keys()) != set(taxonomy.OPTION_KEYS):
                failures.append(f"{tag}: options must be A-E")
                continue
            if len({str(v).strip().lower() for v in o.values()}) != 5:
                failures.append(f"{tag}: options not all distinct")
            if item["correct"] not in taxonomy.OPTION_KEYS:
                failures.append(f"{tag}: correct not in A-E")

            qid = taxonomy.make_id("vrc", item["stem"], o)
            if qid in seen_ids:
                failures.append(f"{tag}: duplicate id")
            seen_ids.add(qid)

            # grouped bank entry (passage carried by the group)
            group_qs.append({
                "id": qid,
                "stem": item["stem"],
                "options": o,
                "correct": item["correct"],
                "explanation": item["explanation"],
                "topic": item["topic"],
                "difficulty": item["difficulty"],
            })
            # flat gold entry (passage inline) for the eval harness
            gold = taxonomy.make_question(
                id=qid, stem=item["stem"], options=o, correct=item["correct"],
                explanation=item["explanation"], topic=item["topic"],
                difficulty=item["difficulty"], source=SOURCE, license=LICENSE,
                scraped_at=ts,
            )
            gold["passage_id"] = pid
            gold["passage"] = passage
            errs = taxonomy.validate_question(gold, require_explanation=True)
            if errs:
                failures.append(f"{tag}: schema errors: {errs}")
            flat.append(gold)

        grouped.append({
            "passage_id": pid,
            "passage": passage,
            "source": SOURCE,
            "license": LICENSE,
            "scraped_at": ts,
            "questions": group_qs,
        })

    if failures:
        print("VERBAL RC BUILD FAILED:", file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        raise SystemExit(1)
    return grouped, flat


def main() -> int:
    grouped, flat = build()
    grouped_path = os.path.join(_HERE, "verbal_rc_questions.json")
    seed_path = os.path.join(_HERE, "verbal_rc_seed.json")
    with open(grouped_path, "w", encoding="utf-8") as fh:
        json.dump(grouped, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(seed_path, "w", encoding="utf-8") as fh:
        json.dump(flat, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    counts = taxonomy.topic_counts(flat)
    print(f"VERBAL RC OK — {len(grouped)} passages, {len(flat)} questions.")
    print(f"Wrote -> {grouped_path}")
    print(f"Wrote -> {seed_path}\n")
    print("RC counts per leaf:")
    for topic in taxonomy.VERBAL_TOPICS:
        if topic.split("::")[2] == "rc":
            print(f"  {topic:40s} {counts.get(topic, 0)}")
    agree = sum(
        1 for it in flat
        if taxonomy.tag_topic(it["stem"] + " " + " ".join(it["options"].values()),
                              section="verbal") == it["topic"]
    )
    print(f"\nKeyword-tagger agreement with RC gold labels: {agree}/{len(flat)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
