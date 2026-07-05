# -*- coding: utf-8 -*-
"""
Content source of truth for GMATWiz Data Insights (DI) lessons.
Consumed by build.py alongside topics_data.py (Quant) and topics_data_verbal.py
(Verbal). 3 leaf topics from the GMAT Focus Data Insights section:

  - Data Sufficiency      (gmat::di::reasoning::data_sufficiency)
  - Two-Part Analysis     (gmat::di::reasoning::two_part_analysis)
  - Multi-Source Reasoning(gmat::di::reasoning::multi_source_reasoning)

Each topic = retrieval opening + I-do + we-do[] + you-do[] + mastery_check,
identical schema to the Quant and Verbal lessons. Application-first (SPOV2):
you_do explanations are revealed after an attempt (build.finalize handles that).

All questions and prose below are ORIGINAL, written for GMATWiz on neutral
topics. No text is taken from any prep book or official guide; the standard
Data Sufficiency answer choices are a fixed, factual convention.

Shared helpers (opts, item, PM, cr_script) are reused from topics_data_verbal
so the pedagogical model and opening script stay identical across sections.
"""

from topics_data_verbal import opts, item, PM, cr_script  # noqa: E402


# ---------------------------------------------------------------------------
# DI-specific helpers.
# ---------------------------------------------------------------------------
def di_topic(**kw):
    kw.setdefault("domain", "Data Insights")
    kw.setdefault("section", "Data Insights")
    kw.setdefault("question_type", "Data Insights")
    kw.setdefault("estimated_minutes", 18)
    return kw


def ds_opts():
    """The five fixed Data Sufficiency answer choices (standard convention)."""
    return opts(
        "Statement (1) ALONE is sufficient, but statement (2) alone is not sufficient.",
        "Statement (2) ALONE is sufficient, but statement (1) alone is not sufficient.",
        "BOTH statements TOGETHER are sufficient, but NEITHER statement ALONE is sufficient.",
        "EACH statement ALONE is sufficient.",
        "Statements (1) and (2) TOGETHER are NOT sufficient.",
    )


def _ms_stem(sources: str, question: str) -> str:
    """Multi-Source item: 2-3 short sources embedded in the stem, then the ask."""
    return f"{sources}\n\nQuestion: {question}"


# High-trust PUBLIC sources only (no prep books). mba.com is the official exam
# authority; Khan Academy is free and public.
GMAT_DI_OVERVIEW = {
    "name": "GMAC - GMAT Focus Edition (official exam overview)",
    "url": "https://www.mba.com/exams/gmat-focus-edition",
    "note": "Official exam structure and Data Insights section scope.",
    "primary": True,
}
KHAN_DATA = {
    "name": "Khan Academy - Statistics & Probability (free)",
    "url": "https://www.khanacademy.org/math/statistics-probability",
    "note": "Free lessons on reading tables and graphs and reasoning from data.",
}
DI_CITES = [GMAT_DI_OVERVIEW, KHAN_DATA]


# ===========================================================================
# DATA SUFFICIENCY
# ===========================================================================
T_data_sufficiency = di_topic(
    topic_id="gmat::di::reasoning::data_sufficiency",
    slug="di-data-sufficiency",
    title="Data Insights: Data Sufficiency",
    question_type="Data Sufficiency",
    prerequisites=[
        "solve a simple linear equation for one unknown",
        "recognize when given facts pin down a single value",
    ],
    learning_objectives=[
        "Evaluate each statement independently, then together, without computing the final answer.",
        "Judge sufficiency by whether the value or yes/no answer is uniquely determined.",
        "Map the result onto the correct one of the five standard Data Sufficiency choices.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Solving a linear equation and telling when facts fix a single value.",
        "do_now": {
            "instructions": "No notes. Answer from memory in 4 minutes.",
            "items": [
                {"prompt": "Solve for x: 2x + 6 = 20.", "answer": "x = 7.", "targets": "solving a linear equation"},
                {"prompt": "From only a + b = 10, can you find a unique value for a?", "answer": "No - many pairs work (3 and 7, 4 and 6, ...).", "targets": "one equation is often not enough"},
                {"prompt": "If a + b = 10 and a - b = 2, is the pair (a, b) determined?", "answer": "Yes - a = 6, b = 4.", "targets": "two equations pin two unknowns"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that a unique answer needs enough independent constraints - the core idea Data Sufficiency tests.",
            "if_students_struggle": "Have them list two different number pairs that fit one equation to feel why a single fact is often not enough.",
            "questions": [
                {"prompt": "In general, how many independent equations do you need to solve for two unknowns?", "answer": "Two.", "targets": "sufficiency of information"},
                {"prompt": "Does 'the value is between 3 and 9' fix a single value?", "answer": "No - a range is not a unique value.", "targets": "unique value vs range"},
            ],
        },
        "prior_knowledge_bridge": "You already sense when facts pin down one answer and when they leave many options. Data Sufficiency makes that the whole task: you never compute the final answer - you decide whether the information is enough to determine it. The discipline is to test statement (1) alone, then statement (2) alone (forgetting (1)), then both together.",
        "learning_intention": "By the end you can decide, for a two-statement Data Sufficiency question, whether statement (1) alone, statement (2) alone, both together, or neither is sufficient - and choose the matching answer.",
        "success_criteria": [
            "I evaluate each statement on its own before combining them.",
            "I decide sufficiency by whether the answer is uniquely determined, not by computing it.",
            "I map my finding onto the correct one of the five standard Data Sufficiency choices.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A bakery sold only muffins and scones one morning. How many muffins did it sell?\n"
        "(1) The bakery sold 40 baked goods in total that morning.\n"
        "(2) The bakery sold three times as many muffins as scones.",
        ds_opts(),
        "C",
        "We need one number: the muffin count. (1) muffins + scones = 40 allows many splits (30 and 10, 20 and 20, ...), not sufficient. (2) muffins = 3 x scones has no total, so muffins could be 3, 30, 300, not sufficient. Together: muffins + scones = 40 and muffins = 3 x scones give 4 x scones = 40, so scones = 10 and muffins = 30 - a unique value. Neither alone works but both together do, so the answer is C.",
        difficulty="medium",
        think_aloud_steps=[
            "The question asks for a single number - how many muffins. In DS I judge sufficiency; I do not need the final count.",
            "Statement (1): total = 40, so muffins + scones = 40. Many splits fit (30 and 10, or 20 and 20). Not sufficient.",
            "Statement (2): muffins = 3 x scones. With no total, muffins could be 3, 30, or 300. Not sufficient.",
            "Together: muffins + scones = 40 and muffins = 3 x scones give 4 x scones = 40, so scones = 10 and muffins = 30 - unique. Sufficient.",
            "Neither alone works but both together do, so the answer is C.",
        ],
        key_takeaway="Data Sufficiency asks whether the information pins down a single answer. Test each statement alone first, then together, and pick the matching choice - without ever needing the final number.",
    ),
    we_do=[
        item(
            "we_1",
            "A rectangular garden has a length of 12 meters. What is the area of the garden, in square meters?\n"
            "(1) The width of the garden is 5 meters.\n"
            "(2) The perimeter of the garden is greater than 30 meters.",
            ds_opts(),
            "A",
            "Length = 12 is given, so only the width is missing. (1) width = 5 gives area = 12 x 5 = 60 - sufficient. (2) perimeter > 30 means 2(12 + w) > 30, so w > 3; width and thus area are not fixed - not sufficient. Statement (1) alone is sufficient; (2) alone is not, so the answer is A.",
            difficulty="medium",
            scaffold_hints=[
                "The length (12 m) is already given, so you only need the width to get the area.",
                "Statement (1) gives the width outright - is the area then fixed?",
                "Statement (2) only bounds the width (perimeter > 30). Does a range of widths give one area?",
            ],
            immediate_feedback={
                "if_correct": "Right - (1) fixes the width and thus the area; (2) gives only a range, so it cannot.",
                "if_incorrect": "Remember the length is given. (1) alone nails the area; (2) leaves many possible widths.",
            },
        ),
        item(
            "we_2",
            "Is the positive integer n even?\n"
            "(1) n is a multiple of 3.\n"
            "(2) n is a multiple of 4.",
            ds_opts(),
            "B",
            "This is a yes/no question. (1) a multiple of 3 could be 6 (even) or 9 (odd) - not a definite answer, not sufficient. (2) a multiple of 4 equals 4k, which is always even - a definite 'yes', sufficient. Statement (2) alone is sufficient, so the answer is B.",
            difficulty="medium",
            scaffold_hints=[
                "Rephrase the goal: you need a yes/no answer that is always the same.",
                "Statement (1): multiples of 3 include 6 (even) and 9 (odd). Does that settle it?",
                "Statement (2): every multiple of 4 is 4 x (integer). Is that always even?",
            ],
            immediate_feedback={
                "if_correct": "Exactly - every multiple of 4 is even, so (2) settles it; (1) allows both even and odd.",
                "if_incorrect": "Test small cases: 3, 6, 9 for (1); 4, 8, 12 for (2). One statement always answers, the other does not.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "What is the value of x?\n"
            "(1) 3x - 5 = 16.\n"
            "(2) x^2 = 49 and x > 0.",
            ds_opts(),
            "D",
            "(1) 3x - 5 = 16 gives 3x = 21, so x = 7 - a unique value, sufficient. (2) x^2 = 49 with x > 0 gives x = 7 (the negative root is excluded) - sufficient. Each statement alone determines x, so the answer is D.",
            difficulty="easy",
        ),
        item(
            "you_2",
            "A jar contains only red, blue, and green marbles. How many green marbles are in the jar?\n"
            "(1) The jar contains 12 red marbles.\n"
            "(2) The jar contains twice as many blue marbles as red marbles.",
            ds_opts(),
            "E",
            "We need the green count. (1) red = 12 says nothing about green - not sufficient. (2) blue = 2 x red gives no green count (and no numbers on its own) - not sufficient. Together we know red = 12 and blue = 24, but with no total for the jar, green is still unknown - not sufficient. So the answer is E.",
            difficulty="hard",
        ),
        item(
            "you_3",
            "Is quadrilateral Q a square?\n"
            "(1) Q has four sides of equal length.\n"
            "(2) Q has four right angles.",
            ds_opts(),
            "C",
            "(1) four equal sides makes a rhombus, which may or may not be a square - not sufficient. (2) four right angles makes a rectangle, which may or may not be a square - not sufficient. Together, four equal sides and four right angles force a square - sufficient. So the answer is C.",
            difficulty="medium",
        ),
    ],
    mastery_check={},
    citations=DI_CITES,
)


# ===========================================================================
# TWO-PART ANALYSIS
# ===========================================================================
T_two_part_analysis = di_topic(
    topic_id="gmat::di::reasoning::two_part_analysis",
    slug="di-two-part",
    title="Data Insights: Two-Part Analysis",
    question_type="Two-Part Analysis",
    prerequisites=[
        "solve a system of two linear equations in two unknowns",
        "check a candidate solution against every condition",
    ],
    learning_objectives=[
        "Translate a two-condition scenario into two equations.",
        "Solve the two equations together for both unknown quantities.",
        "Select the single answer pair that satisfies both conditions at once.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Setting up and solving two linear equations in two unknowns.",
        "do_now": {
            "instructions": "No notes. Answer from memory in 4 minutes.",
            "items": [
                {"prompt": "Solve: x + y = 10 and 2x + y = 16.", "answer": "x = 6, y = 4.", "targets": "solving a 2x2 system"},
                {"prompt": "Buying 3 items for $9, with pens at $2 and notebooks at $5, write two equations.", "answer": "p + n = 3 and 2p + 5n = 9.", "targets": "translating words into two equations"},
                {"prompt": "Does (x, y) = (2, 3) satisfy both x + y = 5 and 2x + y = 8?", "answer": "First yes (5); second no (7 != 8) - so it is not a solution.", "targets": "checking a candidate against BOTH conditions"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls solving two equations at once and the habit of testing a candidate against every condition - the heart of Two-Part Analysis.",
            "if_students_struggle": "Have them plug a wrong pair into both equations to watch it pass one condition and fail the other.",
            "questions": [
                {"prompt": "To accept a candidate answer for two conditions, how many must it satisfy?", "answer": "Both - all conditions at once.", "targets": "simultaneous constraints"},
                {"prompt": "If a pair fits the total count but not the total cost, is it a valid answer?", "answer": "No - it must fit every condition.", "targets": "verify against all constraints"},
            ],
        },
        "prior_knowledge_bridge": "You can solve two equations in two unknowns and check a pair against both. Two-Part Analysis is exactly that in table form: the two 'parts' are two related quantities, and the correct choice is the single pair that makes BOTH given conditions true at once. Translate each fact into an equation, solve, then verify the pair against both facts.",
        "learning_intention": "By the end you can translate a two-condition scenario into two equations and select the one answer pair that satisfies both conditions simultaneously.",
        "success_criteria": [
            "I turn each stated fact into its own equation.",
            "I solve the two equations together for both quantities.",
            "I confirm the chosen pair satisfies both conditions before selecting it.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A customer paid a vending machine exactly $17 using exactly 12 coins, all of them either one-dollar coins or two-dollar coins. "
        "Select the pair that gives the number of one-dollar coins and the number of two-dollar coins used. "
        "Each option lists the count of one-dollar coins and the count of two-dollar coins.",
        opts(
            "5 one-dollar coins and 7 two-dollar coins",
            "7 one-dollar coins and 5 two-dollar coins",
            "8 one-dollar coins and 4 two-dollar coins",
            "6 one-dollar coins and 6 two-dollar coins",
            "9 one-dollar coins and 3 two-dollar coins",
        ),
        "B",
        "Let x = one-dollar coins and y = two-dollar coins. The count gives x + y = 12; the value gives x + 2y = 17. Subtracting, y = 5, so x = 7. Check: 7 + 5 = 12 coins and 7 + 10 = $17 - both hold. The pair is 7 one-dollar and 5 two-dollar coins, option B.",
        difficulty="medium",
        think_aloud_steps=[
            "Two unknowns: the count of one-dollar coins (x) and two-dollar coins (y). I need one pair that fits both facts.",
            "Fact 1 (12 coins): x + y = 12. Fact 2 ($17 paid): x + 2y = 17.",
            "Subtract the first from the second: y = 5, so x = 12 - 5 = 7.",
            "Verify the pair (7, 5): 7 + 5 = 12 coins and 7 + 2(5) = $17 - both conditions hold.",
            "The pair '7 one-dollar coins and 5 two-dollar coins' is option B.",
        ],
        key_takeaway="In Two-Part Analysis, write one equation per condition, solve them together, and pick the single pair that satisfies BOTH - then verify before committing.",
    ),
    we_do=[
        item(
            "we_1",
            "A theater sold adult tickets for $12 each and child tickets for $8 each. One evening it sold 20 tickets for a total of $216. "
            "Select the pair giving the number of adult tickets and the number of child tickets sold. "
            "Each option lists the adult count and the child count.",
            opts(
                "14 adult and 6 child",
                "6 adult and 14 child",
                "12 adult and 8 child",
                "10 adult and 10 child",
                "16 adult and 4 child",
            ),
            "A",
            "Let a = adult tickets, c = child tickets. Count: a + c = 20; money: 12a + 8c = 216. Substituting c = 20 - a gives 12a + 8(20 - a) = 216, so 4a + 160 = 216 and a = 14, c = 6. Check: 14 + 6 = 20 and 12(14) + 8(6) = 168 + 48 = 216. The pair is 14 adult and 6 child, option A.",
            difficulty="medium",
            scaffold_hints=[
                "Let a = adult tickets and c = child tickets; write the count equation and the money equation.",
                "a + c = 20 and 12a + 8c = 216. Substitute to eliminate one variable.",
                "Solve for a, then c, and check both totals before choosing.",
            ],
            immediate_feedback={
                "if_correct": "Right - 14 adult and 6 child give 20 tickets and $216.",
                "if_incorrect": "A correct pair must hit BOTH the 20-ticket count and the $216 total; test your pair against each.",
            },
        ),
        item(
            "we_2",
            "A gardener plants 15 plants in total, using 46 liters of water, with each rose bush needing 4 liters and each lavender plant needing 2 liters. "
            "Select the pair giving the number of rose bushes and the number of lavender plants. "
            "Each option lists the rose-bush count and the lavender count.",
            opts(
                "6 rose bushes and 9 lavender plants",
                "7 rose bushes and 8 lavender plants",
                "8 rose bushes and 7 lavender plants",
                "9 rose bushes and 6 lavender plants",
                "10 rose bushes and 5 lavender plants",
            ),
            "C",
            "Let r = rose bushes, l = lavender plants. Count: r + l = 15; water: 4r + 2l = 46. Substituting l = 15 - r gives 4r + 2(15 - r) = 46, so 2r + 30 = 46 and r = 8, l = 7. Check: 8 + 7 = 15 and 4(8) + 2(7) = 32 + 14 = 46. The pair is 8 rose bushes and 7 lavender plants, option C.",
            difficulty="medium",
            scaffold_hints=[
                "Let r = rose bushes and l = lavender plants; write one equation for the plant count and one for the water.",
                "r + l = 15 and 4r + 2l = 46.",
                "Solve the two together, then verify both totals.",
            ],
            immediate_feedback={
                "if_correct": "Exactly - 8 rose bushes and 7 lavender plants give 15 plants and 46 liters.",
                "if_incorrect": "Check your pair against BOTH the 15-plant count and the 46-liter total.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A print shop charges a fixed setup fee plus a per-page fee. A 100-page order costs $45 and a 250-page order costs $90. "
            "Select the pair giving the setup fee and the per-page fee. "
            "Each option lists the setup fee and the per-page fee.",
            opts(
                "$10 setup and $0.35 per page",
                "$15 setup and $0.30 per page",
                "$20 setup and $0.25 per page",
                "$5 setup and $0.40 per page",
                "$15 setup and $0.35 per page",
            ),
            "B",
            "Let s = setup fee and p = per-page fee. Then s + 100p = 45 and s + 250p = 90. Subtracting, 150p = 45, so p = 0.30 and s = 45 - 100(0.30) = 15. Check: 15 + 250(0.30) = 15 + 75 = 90. The pair is $15 setup and $0.30 per page, option B. Choices that fit only the 100-page order (like $10 and $0.35) fail the 250-page order.",
            difficulty="hard",
        ),
        item(
            "you_2",
            "A quiz has 30 questions worth 96 points in total, all answered correctly, where each Section 1 question is worth 2 points and each Section 2 question is worth 5 points. "
            "Select the pair giving the number of Section 1 questions and the number of Section 2 questions. "
            "Each option lists the Section 1 count and the Section 2 count.",
            opts(
                "12 two-point and 18 five-point",
                "15 two-point and 15 five-point",
                "20 two-point and 10 five-point",
                "18 two-point and 12 five-point",
                "22 two-point and 8 five-point",
            ),
            "D",
            "Let a = 2-point questions and b = 5-point questions. Count: a + b = 30; points: 2a + 5b = 96. Substituting a = 30 - b gives 2(30 - b) + 5b = 96, so 60 + 3b = 96 and b = 12, a = 18. Check: 18 + 12 = 30 and 2(18) + 5(12) = 36 + 60 = 96. The pair is 18 two-point and 12 five-point, option D.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "A charity sold small candles at $6 each and large candles at $10 each, selling 24 candles for a total of $200. "
            "Select the pair giving the number of small candles and the number of large candles sold. "
            "Each option lists the small-candle count and the large-candle count.",
            opts(
                "16 small and 8 large",
                "14 small and 10 large",
                "12 small and 12 large",
                "8 small and 16 large",
                "10 small and 14 large",
            ),
            "E",
            "Let s = small candles and l = large candles. Count: s + l = 24; money: 6s + 10l = 200. Substituting s = 24 - l gives 6(24 - l) + 10l = 200, so 144 + 4l = 200 and l = 14, s = 10. Check: 10 + 14 = 24 and 6(10) + 10(14) = 60 + 140 = 200. The pair is 10 small and 14 large, option E.",
            difficulty="easy",
        ),
    ],
    mastery_check={},
    citations=DI_CITES,
)


# ===========================================================================
# MULTI-SOURCE REASONING
# DI multi-source items are self-contained: each embeds 2-3 short labeled
# sources inside its stem, so the existing lesson player renders them with no
# schema change. The answer usually lives in the COMBINATION of the sources.
# ===========================================================================
MS_CENTER = (
    "Source 1 - Notice: The Riverside Community Center offers Pottery, Painting, "
    "and Weaving classes. Each class session is listed at $15.\n"
    "Source 2 - Email: Members pay 20% less than the listed price for every session."
)
MS_SHUTTLE = (
    "Source 1 - Schedule: Shuttle A leaves the North Lot at 9:00 a.m.; Shuttle B "
    "leaves the South Lot at 9:20 a.m. Each shuttle takes 20 minutes to reach campus.\n"
    "Source 2 - Notice: The North Lot is closed all week for construction.\n"
    "Source 3 - Email: Dr. Lee must be on campus by 9:45 a.m."
)
MS_HOTEL = (
    "Source 1 - Room rates: Standard $90 per night; Deluxe $130 per night; Suite "
    "$180 per night.\n"
    "Source 2 - Policy: Any stay of 3 or more nights receives $20 off per night on any room."
)
MS_BOOKCLUB = (
    "Source 1 - Email: Our book club has 5 members, and we want one copy of the new "
    "novel for each member.\n"
    "Source 2 - Store listing: The novel costs $18 in hardcover and $11 in paperback.\n"
    "Source 3 - Note: The treasury has $70, and everyone must receive the same format."
)
MS_TRAIN = (
    "Source 1 - Timetable: Train X arrives at Central Station at 2:10 p.m.\n"
    "Source 2 - Bus notice: The museum bus leaves Central Station every 30 minutes "
    "starting at 2:00 p.m. (2:00, 2:30, 3:00, and so on); the ride takes 25 minutes.\n"
    "Source 3 - Email: I need to reach the museum by 3:00 p.m."
)
MS_WAREHOUSE = (
    "Source 1 - Inventory: Warehouse A holds 120 units; Warehouse B holds 90 units "
    "of the product.\n"
    "Source 2 - Order: A customer orders 150 units, to ship from a single warehouse "
    "if possible, otherwise split between warehouses.\n"
    "Source 3 - Policy: A split shipment (two warehouses) adds a $25 fee; "
    "single-warehouse shipping is free."
)


T_multi_source_reasoning = di_topic(
    topic_id="gmat::di::reasoning::multi_source_reasoning",
    slug="di-multi-source",
    title="Data Insights: Multi-Source Reasoning",
    question_type="Multi-Source Reasoning",
    prerequisites=[
        "read a short text or table for a specific fact",
        "combine two given facts to reach a conclusion",
    ],
    learning_objectives=[
        "Identify which source holds each fact a question needs.",
        "Combine facts across two or three sources to reach the answer.",
        "Ignore sources that do not bear on the question.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Reading a text or table for a fact and combining two facts into a conclusion.",
        "do_now": {
            "instructions": "No notes. Answer from memory in 4 minutes.",
            "items": [
                {"prompt": "Text A: 'the store opens at 9 a.m.' Text B: 'deliveries arrive 2 hours after opening.' When do deliveries arrive?", "answer": "11 a.m. (9 + 2).", "targets": "combining two sources"},
                {"prompt": "A price list shows $15 and a coupon gives 10% off. What is the paid price?", "answer": "$13.50.", "targets": "applying a rule from one source to a value in another"},
                {"prompt": "A question asks only about cost. Must you use a source that lists only dates?", "answer": "No - use only the sources carrying the facts you need.", "targets": "selecting relevant sources"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls cross-referencing two facts and using only the sources a question needs - the core moves of Multi-Source Reasoning.",
            "if_students_struggle": "Have them underline the one fact each source contributes before answering.",
            "questions": [
                {"prompt": "In a multi-source problem, where does the answer usually come from?", "answer": "Combining facts across two or more sources, not one alone.", "targets": "cross-referencing"},
                {"prompt": "Do you have to use every source to answer a question?", "answer": "No - only the ones holding the facts the question needs.", "targets": "relevance"},
            ],
        },
        "prior_knowledge_bridge": "You can pull a fact from a text or table and combine two facts into a conclusion. Multi-Source Reasoning gives you two or three short sources (like tabs) and asks a question whose answer usually lives in the COMBINATION of them. Your job is to find which source holds each needed fact, ignore the rest, and put the pieces together.",
        "learning_intention": "By the end you can locate the relevant facts across two or three sources and combine them to answer a question, ignoring any source that does not bear on it.",
        "success_criteria": [
            "I identify exactly what the question is asking for.",
            "I find which source holds each fact I need.",
            "I combine those facts (and skip irrelevant sources) to reach the answer.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        _ms_stem(MS_CENTER, "A member attends one Pottery session and one Painting session. What total does she pay?"),
        opts("$24", "$21", "$27", "$30", "$12"),
        "A",
        "The question needs the price (Source 1) and the member rule (Source 2). Listed price is $15 per session; members pay 20% less, so $12 per session. Two sessions at the member price: 2 x $12 = $24, option A. $30 ignores the discount, and $27 discounts only one session.",
        difficulty="medium",
        think_aloud_steps=[
            "The question asks the total a member pays for two sessions - I need the price and the member rule.",
            "Source 1 gives the listed price: $15 per session.",
            "Source 2 gives the member rule: 20% less, so $15 - $3 = $12 per session.",
            "Two sessions at the member price: 2 x $12 = $24.",
            "That is option A; $30 ignores the discount and $27 discounts only one session.",
        ],
        key_takeaway="In Multi-Source Reasoning the answer usually comes from combining sources: find which source holds each needed fact, apply any rule, and integrate - do not answer from a single source when another one modifies it.",
    ),
    we_do=[
        item(
            "we_1",
            _ms_stem(MS_SHUTTLE, "Which shuttle can Dr. Lee take and still arrive on time?"),
            opts(
                "Shuttle A from the North Lot.",
                "Shuttle B from the South Lot.",
                "Either shuttle works.",
                "Shuttle A from the South Lot.",
                "Neither shuttle arrives by 9:45 a.m.",
            ),
            "B",
            "Source 2 closes the North Lot, so Shuttle A is out. Shuttle B leaves the South Lot at 9:20 and takes 20 minutes, arriving 9:40 - before the 9:45 deadline in Source 3. So the answer is Shuttle B from the South Lot, option B.",
            difficulty="medium",
            scaffold_hints=[
                "First, which lots are usable? Check the closure notice.",
                "The North Lot is closed, so any shuttle from it is out.",
                "For the remaining shuttle, add its 20-minute ride to its departure and compare with the 9:45 deadline.",
            ],
            immediate_feedback={
                "if_correct": "Right - the North Lot is closed, and Shuttle B (9:20 + 20 min = 9:40) beats the 9:45 deadline.",
                "if_incorrect": "Combine all three sources: the closure rules out the North Lot shuttle, then check the other shuttle's arrival against 9:45.",
            },
        ),
        item(
            "we_2",
            _ms_stem(MS_HOTEL, "A guest books a Deluxe room for 3 nights. What is the total room cost?"),
            opts("$270", "$310", "$330", "$370", "$390"),
            "C",
            "Source 1 lists Deluxe at $130 per night. Source 2 gives $20 off per night for stays of 3 or more nights, so $110 per night. Three nights: 3 x $110 = $330, option C. $390 forgets the discount; $370 applies it to only one night.",
            difficulty="medium",
            scaffold_hints=[
                "Find the Deluxe nightly rate in the price table.",
                "Check the discount policy - does a 3-night stay qualify?",
                "Apply the per-night discount, then multiply by the number of nights.",
            ],
            immediate_feedback={
                "if_correct": "Exactly - $130 - $20 = $110 per night, times 3 nights = $330.",
                "if_incorrect": "The 3-night stay earns the discount on EVERY night; apply it to all three, then total.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            _ms_stem(MS_BOOKCLUB, "Which format can the club afford for all five members?"),
            opts(
                "Hardcover only.",
                "Either format.",
                "Neither format.",
                "Paperback only.",
                "Hardcover for three members and paperback for two.",
            ),
            "D",
            "Hardcover for all five: 5 x $18 = $90, which is more than the $70 budget - unaffordable. Paperback for all five: 5 x $11 = $55, within budget - affordable. Source 3 requires the same format for everyone, so the split option is out. The answer is paperback only, option D.",
            difficulty="easy",
        ),
        item(
            "you_2",
            _ms_stem(MS_TRAIN, "If the traveler takes Train X, what is the earliest she can arrive at the museum?"),
            opts("2:35 p.m.", "3:00 p.m.", "2:30 p.m.", "3:25 p.m.", "2:55 p.m."),
            "E",
            "Train X arrives at 2:10, so the first catchable bus is the 2:30 (the 2:00 has already left). 2:30 plus the 25-minute ride is 2:55 p.m., which meets the 3:00 deadline. The answer is 2:55 p.m., option E. 2:35 wrongly assumes a bus leaves the moment she arrives.",
            difficulty="hard",
        ),
        item(
            "you_3",
            _ms_stem(MS_WAREHOUSE, "Will the order incur the split-shipment fee, and why?"),
            opts(
                "Yes; neither warehouse alone holds 150 units, so the order must be split.",
                "No; Warehouse A alone can fill the order.",
                "No; Warehouse B alone can fill the order.",
                "No; the order can be split with no fee.",
                "Yes; the customer asked to split the shipment to save money.",
            ),
            "A",
            "The order is 150 units. Warehouse A holds 120 and Warehouse B holds 90, so neither can fill 150 alone; the order must ship from both, which triggers the $25 split-shipment fee (Source 3). The answer is A.",
            difficulty="medium",
        ),
    ],
    mastery_check={},
    citations=DI_CITES,
)


TOPICS = [
    T_data_sufficiency,
    T_two_part_analysis,
    T_multi_source_reasoning,
]
