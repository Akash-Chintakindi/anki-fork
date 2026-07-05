#!/usr/bin/env python3
"""Author the GMATWiz DATA INSIGHTS (DI) question sets.

These are ORIGINAL GMAT Focus Data Insights questions written for GMATWiz on
neutral academic / business topics. Nothing here is copied, paraphrased, or
reworded from any prep book or official guide: only the standard, non-
copyrightable question-type STRUCTURE is reused. The books the user provided
were consulted solely to confirm the DI taxonomy (Data Sufficiency, Two-Part
Analysis, Multi-Source Reasoning), never as a source of text.

The pragmatic MCQ-compatible DI scope (see taxonomy.DI_TAXONOMY) covers three
leaf types:

  * Data Sufficiency       -- a question + two numbered statements, answered with
                              the STANDARD five DS answer choices.
  * Two-Part Analysis      -- a scenario with two related quantities and two
                              conditions; each option is a candidate PAIR and
                              exactly one pair satisfies both conditions.
  * Multi-Source Reasoning -- 2-3 short original sources (memo / table-in-words /
                              note) carried in an extra ``passage`` field; the
                              question is answerable only from the sources.

Two files are emitted next to this script:
  * di_seed.json      -- gold-labeled set (doubles as the eval gold set)
  * di_questions.json -- additional authored bank items

Every item is built with ``taxonomy.make_question`` (id from
``taxonomy.make_id("di", ...)``) and validated with
``taxonomy.validate_question(q, require_explanation=True)``. License for all
items: ``authored-gmatwiz``.

Run:  python3 make_di_seed.py
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from typing import Dict, List, Set

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import taxonomy  # noqa: E402

SOURCE = "GMATWiz original (authored)"
LICENSE = "authored-gmatwiz"
DI = taxonomy.DI_PREFIX  # "gmat::di"


def _t(leaf: str) -> str:
    return f"{DI}::reasoning::{leaf}"


# The five STANDARD Data Sufficiency answer choices, authored verbatim. Every DS
# item reuses exactly these (only the stem's question + statements change).
DS_OPTIONS: Dict[str, str] = {
    "A": "Statement (1) ALONE is sufficient, but statement (2) alone is not sufficient.",
    "B": "Statement (2) ALONE is sufficient, but statement (1) alone is not sufficient.",
    "C": "BOTH statements TOGETHER are sufficient, but NEITHER statement ALONE is sufficient.",
    "D": "EACH statement ALONE is sufficient.",
    "E": "Statements (1) and (2) TOGETHER are NOT sufficient.",
}


def _opts(a: str, b: str, c: str, d: str, e: str) -> Dict[str, str]:
    return {"A": a, "B": b, "C": c, "D": d, "E": e}


def ds(difficulty: str, stem: str, correct: str, explanation: str) -> Dict:
    """A Data Sufficiency item: standard 5 options, stem carries the statements."""
    return {
        "topic": _t("data_sufficiency"),
        "difficulty": difficulty,
        "stem": stem,
        "options": dict(DS_OPTIONS),
        "correct": correct,
        "explanation": explanation,
    }


def tpa(difficulty: str, stem: str, options: Dict[str, str], correct: str,
        explanation: str) -> Dict:
    """A Two-Part Analysis item: each option is a candidate pair."""
    return {
        "topic": _t("two_part_analysis"),
        "difficulty": difficulty,
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": explanation,
    }


def msr(difficulty: str, passage_id: str, passage: str, stem: str,
        options: Dict[str, str], correct: str, explanation: str) -> Dict:
    """A Multi-Source Reasoning item: sources carried in the ``passage`` field."""
    return {
        "topic": _t("multi_source_reasoning"),
        "difficulty": difficulty,
        "passage_id": passage_id,
        "passage": passage,
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# GOLD SEED SET (4 per leaf). Human-assigned leaf labels; used by eval_tagging.
# ---------------------------------------------------------------------------
SEED: List[Dict] = [
    # ======================= data_sufficiency =======================
    ds(
        "medium",
        "Is the integer p greater than 50? "
        "(1) p is a multiple of 20, and 40 < p < 100. "
        "(2) p is even.",
        "A",
        "Statement (1): the multiples of 20 strictly between 40 and 100 are 60 "
        "and 80, both of which exceed 50, so p > 50 is definitely true -- "
        "sufficient. Statement (2): p even allows p = 2 (not > 50) or p = 60 "
        "(> 50) -- not sufficient. Since (1) alone settles the question and (2) "
        "does not, the answer is A.",
    ),
    ds(
        "medium",
        "A bookstore sold only notebooks and pens on Monday. How many notebooks "
        "did it sell? "
        "(1) It sold 40 items in all. "
        "(2) It sold three times as many pens as notebooks.",
        "C",
        "Let n be the notebooks and p the pens. Statement (1): n + p = 40 fixes "
        "only the total -- not sufficient. Statement (2): p = 3n gives no total "
        "-- not sufficient. Together: n + 3n = 40, so 4n = 40 and n = 10 -- "
        "sufficient. Neither works alone, so the answer is C.",
    ),
    ds(
        "medium",
        "What is the value of the number x? "
        "(1) x^2 = 16. "
        "(2) x^3 = -64.",
        "B",
        "Statement (1): x^2 = 16 gives x = 4 or x = -4 -- two values, not "
        "sufficient. Statement (2): x^3 = -64 has the single real solution "
        "x = -4 -- sufficient. Because (2) alone determines x and (1) does not, "
        "the answer is B.",
    ),
    ds(
        "hard",
        "If n is an integer, what is the value of n? "
        "(1) n is a prime number less than 10. "
        "(2) n is odd.",
        "E",
        "Statement (1): the primes less than 10 are 2, 3, 5, and 7 -- not a "
        "single value, not sufficient. Statement (2): 'n is odd' allows many "
        "values -- not sufficient. Together, the odd primes less than 10 are 3, "
        "5, and 7 -- still more than one value, so even combined they do not fix "
        "n. The answer is E.",
    ),
    # ======================= two_part_analysis =======================
    tpa(
        "medium",
        "A department is assigning full-time staff to two projects, Project X "
        "and Project Y, with a whole number of staff on each. Two conditions "
        "must both hold: (i) the total number of staff assigned to the two "
        "projects is 18; and (ii) Project X receives exactly twice as many staff "
        "as Project Y. This is a two-part analysis: select one value for Project "
        "X and one value for Project Y so that both conditions are satisfied. "
        "Which of the following pairs does so?",
        _opts(
            "Project X = 12, Project Y = 6",
            "Project X = 6, Project Y = 12",
            "Project X = 10, Project Y = 8",
            "Project X = 14, Project Y = 4",
            "Project X = 8, Project Y = 4",
        ),
        "A",
        "From (ii), X = 2Y. Substituting into (i): 2Y + Y = 18, so 3Y = 18, "
        "giving Y = 6 and X = 12. The pair X = 12, Y = 6 meets both conditions. "
        "B reverses the doubling; C and D total 18 but violate the 2-to-1 ratio; "
        "E has the correct ratio but totals only 12.",
    ),
    tpa(
        "medium",
        "A cafe sells one cup of coffee and one pastry, each priced at a whole "
        "number of dollars. Two conditions must both hold: (i) one coffee plus "
        "one pastry costs 9 dollars; and (ii) the coffee costs 3 dollars more "
        "than the pastry. This is a two-part analysis: select one price for the "
        "coffee and one price for the pastry so that both conditions are "
        "satisfied. Which of the following pairs does so?",
        _opts(
            "Coffee = 3, Pastry = 6",
            "Coffee = 5, Pastry = 4",
            "Coffee = 6, Pastry = 3",
            "Coffee = 7, Pastry = 2",
            "Coffee = 6, Pastry = 2",
        ),
        "C",
        "Let the pastry cost p; from (ii) the coffee costs p + 3. Then (i) gives "
        "(p + 3) + p = 9, so 2p = 6 and p = 3, making the coffee 6. The pair "
        "Coffee = 6, Pastry = 3 satisfies both. A reverses the difference; B and "
        "D total 9 but the gap is not 3 dollars; E totals only 8.",
    ),
    tpa(
        "medium",
        "A chemist combines Solution A and Solution B, using a whole number of "
        "liters of each. Two conditions must both hold: (i) the combined volume "
        "is 20 liters; and (ii) Solution A's volume is 4 liters greater than "
        "Solution B's volume. This is a two-part analysis: select one volume for "
        "Solution A and one volume for Solution B so that both conditions are "
        "satisfied. Which of the following pairs does so?",
        _opts(
            "Solution A = 8 L, Solution B = 12 L",
            "Solution A = 14 L, Solution B = 6 L",
            "Solution A = 10 L, Solution B = 10 L",
            "Solution A = 12 L, Solution B = 8 L",
            "Solution A = 11 L, Solution B = 7 L",
        ),
        "D",
        "Let B be Solution B's volume; from (ii) Solution A is B + 4. Then (i) "
        "gives (B + 4) + B = 20, so 2B = 16 and B = 8, making Solution A 12. The "
        "pair 12 L and 8 L meets both conditions. A reverses which solution is "
        "larger; B and C total 20 but the difference is not 4 liters; E has the "
        "correct 4-liter difference but totals only 18.",
    ),
    tpa(
        "medium",
        "In a points game, each easy task is worth e points and each hard task "
        "is worth h points, where e and h are whole numbers. Two conditions must "
        "both hold: (i) one easy task and one hard task together are worth 25 "
        "points; and (ii) a hard task is worth four times as many points as an "
        "easy task. This is a two-part analysis: select one value for e and one "
        "value for h so that both conditions are satisfied. Which of the "
        "following pairs does so?",
        _opts(
            "e = 20, h = 5",
            "e = 5, h = 20",
            "e = 10, h = 15",
            "e = 4, h = 16",
            "e = 5, h = 15",
        ),
        "B",
        "From (ii), h = 4e. Substituting into (i): e + 4e = 25, so 5e = 25 and "
        "e = 5, giving h = 20. The pair e = 5, h = 20 meets both conditions. A "
        "reverses the multiple; C totals 25 but h is not four times e; D has "
        "h = 4e but totals only 20; E totals 20 and lacks the 4-to-1 relationship.",
    ),
    # ===================== multi_source_reasoning =====================
    msr(
        "medium",
        "msr-greenleaf-tea",
        "Source 1 (Product memo): GreenLeaf Tea sells exactly three blends. The "
        "Morning blend and the Afternoon blend both contain caffeine; the "
        "Evening blend is caffeine-free.\n\n"
        "Source 2 (Inventory note): Current stock, in cases: Morning 40, "
        "Afternoon 25, Evening 60.\n\n"
        "Source 3 (Purchasing policy): Any blend with fewer than 30 cases in "
        "stock must be reordered this week.",
        "Based on the sources above, which blend both contains caffeine and must "
        "be reordered this week?",
        _opts(
            "The Morning blend",
            "The Afternoon blend",
            "The Evening blend",
            "Both the Morning and Afternoon blends",
            "None of the blends",
        ),
        "B",
        "The caffeinated blends are Morning and Afternoon (Source 1). Reordering "
        "is required for any blend under 30 cases (Source 3); by Source 2 only "
        "the Afternoon blend (25 cases) is under 30. Morning has 40 cases, so it "
        "is not reordered, and Evening is caffeine-free. Only the Afternoon "
        "blend meets both conditions.",
    ),
    msr(
        "hard",
        "msr-annual-workshop",
        "Source 1 (Planning email): The annual workshop will be held on either "
        "Tuesday or Thursday of next week. Our invited keynote speaker is "
        "available only on Thursday.\n\n"
        "Source 2 (Venue note): The main hall is already booked on Thursday but "
        "is free on Tuesday.\n\n"
        "Source 3 (Requirements note): The workshop must be held in the main "
        "hall; if the main hall is unavailable, the workshop cannot take place "
        "that day.",
        "Based on the sources above, on which day can the workshop be held with "
        "the keynote speaker present?",
        _opts(
            "Tuesday",
            "Thursday",
            "Either Tuesday or Thursday",
            "It cannot be held with the keynote speaker on either day",
            "It can be held on any day of the week",
        ),
        "D",
        "The keynote speaker is available only on Thursday (Source 1), but the "
        "main hall -- required for the workshop (Source 3) -- is booked on "
        "Thursday (Source 2), so Thursday is impossible. Tuesday has the hall "
        "free but not the keynote speaker. Therefore the workshop cannot be held "
        "with the keynote speaker on either candidate day.",
    ),
    msr(
        "medium",
        "msr-library-grant",
        "Source 1 (Grant memo): A library branch qualifies for the annual grant "
        "only if it recorded more than 5,000 visitors last year AND signed up at "
        "least 500 new members last year.\n\n"
        "Source 2 (Data table, last year): Downtown -- 6,200 visitors, 400 new "
        "members. Riverside -- 5,500 visitors, 600 new members. Hillside -- "
        "4,800 visitors, 700 new members.",
        "Based on the sources above, which branch qualifies for the annual grant?",
        _opts(
            "Downtown",
            "Hillside",
            "Riverside",
            "Both Downtown and Riverside",
            "All three branches",
        ),
        "C",
        "Qualifying requires both more than 5,000 visitors and at least 500 new "
        "members (Source 1). From Source 2: Downtown had enough visitors (6,200) "
        "but only 400 new members; Hillside had 700 new members but only 4,800 "
        "visitors; Riverside had 5,500 visitors and 600 new members, meeting "
        "both thresholds. Only Riverside qualifies.",
    ),
    msr(
        "medium",
        "msr-techstart-tiers",
        "Source 1 (Product memo): TechStart offers three subscription tiers -- "
        "Basic, Plus, and Pro. Priority support is included with Plus and Pro "
        "only. The analytics dashboard is included with Pro only.\n\n"
        "Source 2 (Price list, per month): Basic 10 dollars, Plus 20 dollars, "
        "Pro 35 dollars.\n\n"
        "Source 3 (Customer request): A customer needs priority support, does "
        "not need the analytics dashboard, and wants the lowest-priced tier that "
        "meets these needs.",
        "Based on the sources above, which tier should the customer choose?",
        _opts(
            "Plus",
            "Basic",
            "Pro",
            "Either Plus or Pro",
            "None of the tiers",
        ),
        "A",
        "Priority support rules out Basic, leaving Plus and Pro (Source 1). The "
        "customer does not need the analytics dashboard, the only feature "
        "exclusive to Pro, so Plus meets every stated need. Between the two "
        "qualifying tiers, Plus (20 dollars) is cheaper than Pro (35 dollars) "
        "(Source 2), so the lowest-priced tier that works is Plus.",
    ),
]


# ---------------------------------------------------------------------------
# ADDITIONAL BANK SET (4 per leaf). Shipped for practice depth; not gold.
# ---------------------------------------------------------------------------
BANK: List[Dict] = [
    # ======================= data_sufficiency =======================
    ds(
        "medium",
        "What was Greenfield Corporation's revenue in 2022? "
        "(1) The company's 2022 revenue was 2.0 million dollars. "
        "(2) The company's 2022 revenue was 25 percent greater than its 2021 "
        "revenue, which was 1.6 million dollars.",
        "D",
        "Statement (1): revenue = 2.0 million dollars directly answers the "
        "question -- sufficient. Statement (2): 25 percent more than 1.6 million "
        "is 1.6 x 1.25 = 2.0 million dollars -- also sufficient. Each statement "
        "alone determines the revenue, so the answer is D.",
    ),
    ds(
        "hard",
        "Is the average (arithmetic mean) of five different integers greater "
        "than 10? "
        "(1) The smallest of the five integers is 11. "
        "(2) The largest of the five integers is 20.",
        "A",
        "Statement (1): if the smallest of five different integers is 11, then "
        "all five are at least 11, so their mean is at least 11, which exceeds "
        "10 -- sufficient (the answer is 'yes'). Statement (2): if the largest "
        "is 20, the others could be small (e.g., 1, 2, 3, 4, giving mean 6) or "
        "large (e.g., 16, 17, 18, 19, giving mean 18), so the mean may or may "
        "not exceed 10 -- not sufficient. The answer is A.",
    ),
    ds(
        "medium",
        "If k is a positive integer, is k divisible by 6? "
        "(1) k is divisible by 3. "
        "(2) k is divisible by 12.",
        "B",
        "Statement (1): k divisible by 3 could be 3 (not divisible by 6) or 6 "
        "(divisible by 6) -- not sufficient. Statement (2): any multiple of 12 "
        "is also a multiple of 6, since 6 divides 12, so k is divisible by 6 -- "
        "sufficient. Because (2) alone answers the question and (1) does not, "
        "the answer is B.",
    ),
    ds(
        "medium",
        "At a market, what is the price of one apple? "
        "(1) Three apples and two oranges together cost 4.20 dollars. "
        "(2) One orange costs 0.90 dollars.",
        "C",
        "Let a be the price of an apple and r the price of an orange. Statement "
        "(1): 3a + 2r = 4.20 alone has many solutions -- not sufficient. "
        "Statement (2): r = 0.90 alone says nothing about a -- not sufficient. "
        "Together: 3a + 2(0.90) = 4.20, so 3a = 2.40 and a = 0.80 -- sufficient. "
        "Neither works alone, so the answer is C.",
    ),
    # ======================= two_part_analysis =======================
    tpa(
        "medium",
        "Two donors each contributed a whole number of dollars to a fund. Two "
        "conditions must both hold: (i) together the two donors gave 50 dollars; "
        "and (ii) the first donor gave 10 dollars more than the second donor. "
        "This is a two-part analysis: select one amount for the first donor and "
        "one amount for the second donor so that both conditions are satisfied. "
        "Which of the following pairs does so?",
        _opts(
            "First = 20, Second = 30",
            "First = 25, Second = 25",
            "First = 35, Second = 15",
            "First = 40, Second = 10",
            "First = 30, Second = 20",
        ),
        "E",
        "Let the second donor give s; from (ii) the first gives s + 10. Then (i) "
        "gives (s + 10) + s = 50, so 2s = 40 and s = 20, making the first donor "
        "30. The pair First = 30, Second = 20 meets both conditions. A reverses "
        "who gave more; B splits evenly (no 10-dollar gap); C and D total 50 but "
        "the gap is not 10 dollars.",
    ),
    tpa(
        "medium",
        "A recipe uses a whole number of cups of flour and a whole number of "
        "cups of sugar. Two conditions must both hold: (i) the recipe uses 10 "
        "cups of flour and sugar combined; and (ii) it uses four times as many "
        "cups of flour as cups of sugar. This is a two-part analysis: select one "
        "value for the cups of flour and one value for the cups of sugar so that "
        "both conditions are satisfied. Which of the following pairs does so?",
        _opts(
            "Flour = 8, Sugar = 2",
            "Flour = 2, Sugar = 8",
            "Flour = 6, Sugar = 4",
            "Flour = 5, Sugar = 5",
            "Flour = 12, Sugar = 3",
        ),
        "A",
        "Let the cups of sugar be s; from (ii) the cups of flour is 4s. Then (i) "
        "gives 4s + s = 10, so 5s = 10 and s = 2, making the flour 8. The pair "
        "Flour = 8, Sugar = 2 meets both conditions. B reverses the multiple; C "
        "and D total 10 but flour is not four times sugar; E has flour equal to "
        "four times sugar but totals 15, not 10.",
    ),
    tpa(
        "medium",
        "On a test, a student answered a whole number of multiple-choice "
        "questions and a whole number of essay questions. Two conditions must "
        "both hold: (i) the student answered 24 questions in all; and (ii) the "
        "number of multiple-choice questions was five times the number of essay "
        "questions. This is a two-part analysis: select one value for the "
        "multiple-choice questions and one value for the essay questions so that "
        "both conditions are satisfied. Which of the following pairs does so?",
        _opts(
            "Multiple-choice = 4, Essay = 20",
            "Multiple-choice = 18, Essay = 6",
            "Multiple-choice = 20, Essay = 4",
            "Multiple-choice = 12, Essay = 12",
            "Multiple-choice = 25, Essay = 5",
        ),
        "C",
        "Let the essay count be x; from (ii) the multiple-choice count is 5x. "
        "Then (i) gives 5x + x = 24, so 6x = 24 and x = 4, making the "
        "multiple-choice count 20. The pair 20 and 4 meets both conditions. A "
        "reverses the multiple; B and D total 24 but multiple-choice is not five "
        "times essay; E has the 5-to-1 ratio but totals 30, not 24.",
    ),
    tpa(
        "medium",
        "A conference splits its talks between a morning track and an afternoon "
        "track, each with a whole number of talks. Two conditions must both "
        "hold: (i) the two tracks have 21 talks combined; and (ii) the morning "
        "track has half as many talks as the afternoon track. This is a two-part "
        "analysis: select one value for the morning track and one value for the "
        "afternoon track so that both conditions are satisfied. Which of the "
        "following pairs does so?",
        _opts(
            "Morning = 14, Afternoon = 7",
            "Morning = 10, Afternoon = 11",
            "Morning = 8, Afternoon = 13",
            "Morning = 7, Afternoon = 14",
            "Morning = 6, Afternoon = 12",
        ),
        "D",
        "From (ii), morning = (1/2) x afternoon, so afternoon = 2 x morning. "
        "Then (i) gives morning + 2 x morning = 21, so 3 x morning = 21 and "
        "morning = 7, making the afternoon track 14. The pair Morning = 7, "
        "Afternoon = 14 meets both conditions. A reverses the halving; B and C "
        "total 21 but the morning track is not half the afternoon track; E has "
        "the correct 1-to-2 ratio but totals only 18.",
    ),
    # ===================== multi_source_reasoning =====================
    msr(
        "medium",
        "msr-manuscript-fasttrack",
        "Source 1 (Editorial memo): A submitted manuscript is fast-tracked only "
        "if it is written by a returning author and is under 80,000 words.\n\n"
        "Source 2 (Submissions log): 'Harbor Lights' -- returning author, 75,000 "
        "words. 'Red Comet' -- new author, 60,000 words. 'The Ledger' -- "
        "returning author, 95,000 words.",
        "Based on the sources above, which submission qualifies to be "
        "fast-tracked?",
        _opts(
            "The Ledger",
            "Red Comet",
            "All three submissions",
            "The Ledger and Harbor Lights",
            "Harbor Lights",
        ),
        "E",
        "Fast-tracking requires both a returning author and a length under "
        "80,000 words (Source 1). From Source 2: 'Red Comet' is by a new author; "
        "'The Ledger,' though by a returning author, is 95,000 words; 'Harbor "
        "Lights' is by a returning author and is 75,000 words, meeting both "
        "requirements. Only 'Harbor Lights' qualifies.",
    ),
    msr(
        "medium",
        "msr-building-maintenance",
        "Source 1 (Facilities email): Building maintenance can be scheduled only "
        "on a day when the building is closed. The building is closed every "
        "Sunday and on any public holiday.\n\n"
        "Source 2 (Next week's calendar): Monday is a public holiday. Tuesday "
        "through Saturday the building is open as usual. Sunday is a normal "
        "Sunday.\n\n"
        "Source 3 (Deadline note): The maintenance must be completed at some "
        "point next week (Monday through Sunday).",
        "Based on the sources above, on which day or days next week can the "
        "maintenance be scheduled?",
        _opts(
            "Only Sunday",
            "Monday or Sunday",
            "Only Monday",
            "Any day from Tuesday through Saturday",
            "No day next week",
        ),
        "B",
        "Maintenance is allowed only on days the building is closed -- Sundays "
        "and public holidays (Source 1). Next week, Monday is a public holiday "
        "and Sunday is closed, while Tuesday through Saturday the building is "
        "open (Source 2). Both closed days fall within the required window "
        "(Source 3), so the maintenance can be scheduled on Monday or Sunday.",
    ),
    msr(
        "medium",
        "msr-grocery-supplier",
        "Source 1 (Sourcing memo): A supplier is designated 'preferred' only if "
        "it is organic-certified and can deliver within 2 days.\n\n"
        "Source 2 (Supplier table): Orchard One -- organic-certified, 3-day "
        "delivery. Orchard Two -- not organic-certified, 1-day delivery. Orchard "
        "Three -- organic-certified, 1-day delivery.",
        "Based on the sources above, which supplier qualifies as preferred?",
        _opts(
            "Orchard One",
            "Orchard Two",
            "Orchard Three",
            "Orchard One and Orchard Three",
            "None of the suppliers",
        ),
        "C",
        "A preferred supplier must be both organic-certified and able to deliver "
        "within 2 days (Source 1). From Source 2: Orchard One is organic but "
        "takes 3 days; Orchard Two delivers in 1 day but is not organic; Orchard "
        "Three is organic-certified and delivers in 1 day, satisfying both "
        "criteria. Only Orchard Three qualifies.",
    ),
    msr(
        "hard",
        "msr-airline-lounge",
        "Source 1 (Policy memo): A passenger receives airport lounge access if "
        "the passenger is flying business class or is a Gold member. A Silver "
        "member receives lounge access only when flying business class.\n\n"
        "Source 2 (Passenger list, today): Ms. Adams -- economy class, Gold "
        "member. Mr. Boone -- business class, Silver member. Ms. Carr -- economy "
        "class, Silver member.",
        "Based on the sources above, which passengers receive lounge access today?",
        _opts(
            "Ms. Adams only",
            "Mr. Boone only",
            "All three passengers",
            "Ms. Adams and Mr. Boone",
            "None of the passengers",
        ),
        "D",
        "Lounge access is granted to anyone flying business class or holding "
        "Gold membership (Source 1). Ms. Adams flies economy but is a Gold "
        "member, so she qualifies; Mr. Boone flies business class, so he "
        "qualifies regardless of his Silver status; Ms. Carr is an economy-class "
        "Silver member, so she does not qualify. Thus Ms. Adams and Mr. Boone "
        "receive access.",
    ),
]


# ---------------------------------------------------------------------------
# Build + validate + emit
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def build(items: List[Dict], label: str, ts: str, seen_ids: Set[str]) -> List[Dict]:
    """Structurally + schema validate authored DI items; fail loudly on any error.

    ``seen_ids`` is shared across both files so duplicate content is caught
    globally (all items must be distinct across di_seed.json + di_questions.json).
    """
    out: List[Dict] = []
    failures: List[str] = []

    for i, item in enumerate(items):
        tag = f"{label} #{i + 1} [{item['topic']}]"
        opts = item["options"]

        if item["topic"] not in taxonomy.DI_TOPICS:
            failures.append(f"{tag}: topic is not a DI leaf")

        if set(opts.keys()) != set(taxonomy.OPTION_KEYS):
            failures.append(f"{tag}: options must be exactly A-E")
            continue
        distinct = {str(v).strip().lower() for v in opts.values()}
        if len(distinct) != 5:
            failures.append(f"{tag}: options are not all distinct")
        if item["correct"] not in taxonomy.OPTION_KEYS:
            failures.append(f"{tag}: correct '{item['correct']}' not in A-E")

        is_ds = item["topic"] == _t("data_sufficiency")
        is_msr = item["topic"] == _t("multi_source_reasoning")

        # Data Sufficiency must use the standard five answer choices verbatim.
        if is_ds and opts != DS_OPTIONS:
            failures.append(f"{tag}: DS options must match the standard 5 choices verbatim")

        # Only Multi-Source Reasoning items may carry a passage, and they must.
        passage = item.get("passage")
        if is_msr:
            if not (isinstance(passage, str) and passage.strip()):
                failures.append(f"{tag}: multi_source_reasoning item needs a non-empty 'passage'")
        elif passage:
            failures.append(f"{tag}: only multi_source_reasoning items may carry a 'passage'")

        q = taxonomy.make_question(
            id=taxonomy.make_id("di", item["stem"], opts),
            stem=item["stem"],
            options=opts,
            correct=item["correct"],
            explanation=item["explanation"],
            topic=item["topic"],
            difficulty=item["difficulty"],
            source=SOURCE,
            license=LICENSE,
            scraped_at=ts,
        )
        if is_msr:
            q["passage_id"] = item.get("passage_id", "")
            q["passage"] = passage

        errs = taxonomy.validate_question(q, require_explanation=True)
        if errs:
            failures.append(f"{tag}: schema errors: {errs}")
        if q["id"] in seen_ids:
            failures.append(f"{tag}: duplicate id {q['id']} (not distinct across files)")
        seen_ids.add(q["id"])
        out.append(q)

    if failures:
        print(f"DI BUILD FAILED ({label}) -- fix these before shipping:", file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        raise SystemExit(1)

    out.sort(key=lambda q: (q["topic"], q["id"]))
    return out


def _tagger_agreement(items: List[Dict]) -> float:
    """Soft signal: how often the keyword tagger recovers the gold DI leaf."""
    if not items:
        return 0.0
    hits = sum(
        1 for q in items
        if taxonomy.tag_topic(q["stem"] + " " + " ".join(q["options"].values()),
                              section="di") == q["topic"]
    )
    return hits / len(items)


def main() -> int:
    ts = now_iso()
    seen_ids: Set[str] = set()
    seed = build(SEED, "di-seed", ts, seen_ids)
    bank = build(BANK, "di-bank", ts, seen_ids)

    seed_path = os.path.join(_HERE, "di_seed.json")
    bank_path = os.path.join(_HERE, "di_questions.json")
    for path, data in ((seed_path, seed), (bank_path, bank)):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    seed_counts = taxonomy.topic_counts(seed)
    bank_counts = taxonomy.topic_counts(bank)

    print(f"DI OK -- {len(seed)} gold seed + {len(bank)} bank = "
          f"{len(seed) + len(bank)} authored Data Insights questions.")
    print(f"Wrote -> {seed_path}")
    print(f"Wrote -> {bank_path}\n")

    print(f"Per-leaf counts ({'leaf':38s} seed | bank):")
    for topic in taxonomy.DI_TOPICS:
        print(f"  {topic:40s} {seed_counts.get(topic, 0):4d} | {bank_counts.get(topic, 0):4d}")

    print(f"\nTotals: seed={len(seed)}, bank={len(bank)}, combined={len(seed) + len(bank)}")
    print(f"Keyword-tagger agreement with gold labels (section=di): "
          f"seed={_tagger_agreement(seed):.0%}, bank={_tagger_agreement(bank):.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
