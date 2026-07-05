# -*- coding: utf-8 -*-
"""
Content source of truth for GMATWiz Verbal (Critical Reasoning) lessons.
Consumed by build.py alongside topics_data.py (Quant). 9 leaf topics from the
PRD Section 5 Verbal map (Critical Reasoning; Reading Comprehension ships in
Phase B). GMAT Focus Verbal = CR + RC only (NO Sentence Correction).

Each topic = retrieval opening + I-do + we-do[] + you-do[] + mastery_check,
identical schema to the Quant lessons. Application-first (SPOV2): you_do
explanations are revealed after an attempt (build.finalize handles that).

All arguments below are ORIGINAL, written for GMATWiz on neutral topics. No
text is taken from any prep book; the provided books were used only to confirm
the standard CR question-type taxonomy.
"""


def opts(a, b, c, d, e):
    return {"A": a, "B": b, "C": c, "D": d, "E": e}


def item(qid, stem, options, correct, explanation, difficulty="medium", **extra):
    d = {
        "id": qid,
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": explanation,
        "difficulty": difficulty,
    }
    d.update(extra)
    return d


def topic(**kw):
    kw.setdefault("domain", "Critical Reasoning")
    kw.setdefault("section", "Verbal Reasoning")
    kw.setdefault("question_type", "Critical Reasoning")
    kw.setdefault("estimated_minutes", 18)
    return kw


# Shared pedagogical model + high-trust public sources (no copyrighted books).
PM = {
    "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
    "sequence": "I do -> we do -> you do",
    "application_first": True,
    "explanation_policy": "revealed_after_attempt",
}
GMAT_OVERVIEW = {
    "name": "GMAC - GMAT Focus Edition (official exam overview)",
    "url": "https://www.mba.com/exams/gmat-focus-edition",
    "note": "Official exam structure and Verbal Reasoning scope.",
    "primary": True,
}
KHAN_LR = {
    "name": "Khan Academy - LSAT Logical Reasoning (free)",
    "url": "https://www.khanacademy.org/prep/lsat",
    "note": "Free lessons on argument structure, assumptions, strengthen/weaken, and flaws.",
}
CR_CITES = [GMAT_OVERVIEW, KHAN_LR]


def cr_script():
    return [
        {"time": "0:00-4:00", "move": "Do Now on screen; learners answer from memory, no notes."},
        {"time": "4:00-6:00", "move": "Cold-call answers; name the argument's conclusion vs premises."},
        {"time": "6:00-8:00", "move": "Bridge to today's question type; state what the stem is really asking."},
        {"time": "8:00-10:00", "move": "Move to I do: model the reasoning on one worked item."},
    ]


# ===========================================================================
# ASSUMPTION
# ===========================================================================
T_assumption = topic(
    topic_id="gmat::verbal::cr::assumption",
    slug="cr-assumption",
    title="Critical Reasoning: Assumption",
    prerequisites=["identify an argument's conclusion", "separate premises from the conclusion"],
    learning_objectives=[
        "Locate the conclusion and the evidence, then find the gap between them.",
        "State the unstated premise the argument needs in order to hold.",
        "Use the negation test: if negating a choice breaks the argument, it is the assumption.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Telling an argument's conclusion apart from its evidence.",
        "do_now": {
            "instructions": "No notes. Answer from memory in 4 minutes.",
            "items": [
                {"prompt": "In 'Sales rose after we added music, so music boosts sales,' what is the conclusion?", "answer": "Music boosts sales.", "targets": "finding the conclusion"},
                {"prompt": "What is an assumption?", "answer": "An unstated premise the argument needs to be true.", "targets": "definition"},
                {"prompt": "Negate: 'The two groups were similar in all other respects.'", "answer": "The two groups differed in some other relevant respect.", "targets": "negation"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls conclusion-vs-evidence and negation, the two tools an assumption question rests on.",
            "if_students_struggle": "If they cannot find the conclusion, have them ask 'what is the author trying to convince me of?' first.",
            "questions": [
                {"prompt": "Underline the conclusion: 'Profits will rise because costs fell.'", "answer": "'Profits will rise' is the conclusion; 'costs fell' is the evidence.", "targets": "conclusion vs premise"},
                {"prompt": "Why does 'costs fell -> profits rise' need an assumption?", "answer": "It assumes revenue will not fall by more than costs did.", "targets": "the gap"},
            ],
        },
        "prior_knowledge_bridge": "You can already find a conclusion and its evidence. An assumption question asks for the missing link between them - the fact the author never states but silently relies on. Find the gap, and the assumption is what bridges it.",
        "learning_intention": "By the end you can find the gap between evidence and conclusion and state the assumption that closes it, confirming it with the negation test.",
        "success_criteria": [
            "I can name the conclusion and the evidence in one sentence each.",
            "I can describe the gap the argument leaps over.",
            "I can use the negation test to confirm the required assumption.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A company will cut its shipping costs by moving its warehouse closer to the highway, because trucks will then spend less time in city traffic. The argument depends on which of the following assumptions?",
        opts(
            "Time spent in city traffic is a meaningful part of the trucks' current shipping costs.",
            "The new warehouse location is larger than the current one.",
            "The company's competitors also ship by truck.",
            "Highway tolls are lower than city parking fees.",
            "The company ships more products in summer than in winter.",
        ),
        "A",
        "The conclusion (lower shipping costs) rests on cutting traffic time; that only helps if traffic time is actually a meaningful cost driver. Negate A - traffic time is negligible - and the savings vanish, so A is required.",
        difficulty="medium",
        think_aloud_steps=[
            "Conclusion: shipping costs will fall. Evidence: less time in city traffic.",
            "Gap: does traffic time actually drive costs? The argument assumes it does.",
            "Negation test: if traffic time is a negligible cost, moving saves nothing - argument collapses.",
            "So A is the needed assumption; the others are irrelevant to the cost link.",
        ],
        key_takeaway="An assumption bridges the evidence to the conclusion; negate it and the argument should fall apart.",
    ),
    we_do=[
        item(
            "we_1",
            "A school will raise its graduation rate by giving every student a personal laptop, since students will be able to complete assignments more easily. This argument assumes that",
            opts(
                "difficulty completing assignments is a significant reason students currently fail to graduate.",
                "laptops are cheaper than textbooks.",
                "teachers prefer digital assignments to paper ones.",
                "students do not already own computers at home.",
                "the school's internet connection is reliable.",
            ),
            "A",
            "The plan only raises graduation if assignment difficulty is a real cause of non-graduation; otherwise easier assignments change nothing. Negating A breaks the link.",
            difficulty="medium",
            scaffold_hints=[
                "What is the conclusion, and what is the single piece of evidence for it?",
                "Ask: for easier assignments to raise graduation, what must be true about why students don't graduate?",
                "Try the negation test on each choice.",
            ],
            immediate_feedback={
                "if_correct": "Right - the plan works only if assignment difficulty is actually holding students back.",
                "if_incorrect": "The other choices may be nice to know, but negating them leaves the argument standing; negating A destroys it.",
            },
        ),
        item(
            "we_2",
            "A city will reduce littering in its parks by adding more trash cans, because people litter when a trash can is not within easy reach. The argument relies on the assumption that",
            opts(
                "a shortage of nearby trash cans is a substantial cause of the current littering.",
                "the new trash cans will be emptied every day.",
                "littering is worse in parks than on city streets.",
                "residents have complained about the litter.",
                "the parks are busiest on weekends.",
            ),
            "A",
            "Adding cans reduces littering only if 'no can nearby' is really why people litter; if they litter for other reasons, more cans won't help. Negate A and the plan fails.",
            difficulty="medium",
            scaffold_hints=[
                "Separate the recommendation from its stated reason.",
                "The reason names one cause of littering - the argument bets that cause is the main one.",
                "Which choice, if false, sinks the plan?",
            ],
            immediate_feedback={
                "if_correct": "Exactly - the fix assumes the diagnosed cause is a real, substantial one.",
                "if_incorrect": "Focus on what MUST be true for 'more cans' to cut littering, not on details that merely sound relevant.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A publisher will increase magazine subscriptions by adding a weekly puzzle section, reasoning that readers enjoy puzzles. The argument assumes that",
            opts(
                "enough potential subscribers value a puzzle section enough to subscribe because of it.",
                "the puzzles will be written by a famous puzzle designer.",
                "the magazine currently has no games of any kind.",
                "puzzle sections are cheaper to produce than articles.",
                "readers spend more time on puzzles than on articles.",
            ),
            "A",
            "Subscriptions rise only if the puzzle section actually moves people to subscribe; general enjoyment of puzzles is not enough. Negating A removes the reason subscriptions would grow.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "A restaurant will boost weekday lunch profits by offering a faster express menu, since many office workers skip lunch out because they lack time. This argument depends on the assumption that",
            opts(
                "a meaningful number of these workers would buy lunch if service were faster.",
                "the express menu will use the same ingredients as the regular menu.",
                "the restaurant is located near several offices.",
                "competing restaurants do not offer express menus.",
                "office workers prefer hot meals to cold ones.",
            ),
            "A",
            "The profit gain depends on time-pressed workers actually buying once service is faster; if they would still not buy, the express menu adds nothing. Negation of A breaks the plan.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "A university claims it will improve student writing by requiring a first-year composition course, because practice improves writing. The argument assumes that",
            opts(
                "the composition course will give students the kind of practice that actually improves writing.",
                "most students dislike writing when they arrive.",
                "the course will be taught by tenured professors.",
                "students write more in college than in high school.",
                "writing ability affects starting salaries.",
            ),
            "A",
            "'Practice improves writing' supports the plan only if the required course supplies effective practice; a course that does not would not help. Negating A defeats the argument.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# STRENGTHEN
# ===========================================================================
T_strengthen = topic(
    topic_id="gmat::verbal::cr::strengthen",
    slug="cr-strengthen",
    title="Critical Reasoning: Strengthen",
    prerequisites=["identify an argument's conclusion", "spot the assumption connecting evidence to conclusion"],
    learning_objectives=[
        "Find the conclusion, then choose the fact that makes it more likely to be true.",
        "Prefer answers that confirm the argument's assumption or rule out an alternative cause.",
        "Reject choices that are merely on-topic but do not affect the conclusion.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Finding an argument's assumption.",
        "do_now": {
            "instructions": "No notes. 4 minutes, from memory.",
            "items": [
                {"prompt": "To STRENGTHEN a causal claim, what is one powerful move?", "answer": "Rule out an alternative cause, or show the cause-effect holds in a controlled comparison.", "targets": "strengthen moves"},
                {"prompt": "Does a choice that repeats the conclusion strengthen it?", "answer": "No - restating is not new support.", "targets": "trap answers"},
                {"prompt": "Strengthen or not: evidence that a confounding factor was absent.", "answer": "Strengthens (removes an alternative explanation).", "targets": "confounders"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that strengthening usually means confirming the assumption or eliminating a rival cause.",
            "if_students_struggle": "Remind them a strengthener need not prove the conclusion - just make it more likely.",
            "questions": [
                {"prompt": "Name two ways to strengthen a causal argument.", "answer": "Confirm the assumption; rule out an alternative cause.", "targets": "strengthen strategy"},
                {"prompt": "Why is 'the study had many participants' often a weak strengthener?", "answer": "Sample size alone doesn't address the logical gap in the argument.", "targets": "trap answers"},
            ],
        },
        "prior_knowledge_bridge": "You can find the assumption that props up an argument. A strengthen question rewards the choice that makes that assumption more secure - or slams the door on a competing explanation. Same gap, now you reinforce it instead of just naming it.",
        "learning_intention": "By the end you can pick the choice that most increases the likelihood the conclusion is true, usually by supporting the assumption or removing an alternative cause.",
        "success_criteria": [
            "I can state the conclusion the choice must support.",
            "I can tell a real strengthener from an on-topic distractor.",
            "I can recognize 'rule out another cause' as a strengthening move.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A town noticed that crime fell in the year after it installed brighter streetlights, and concluded the lights caused the drop. Which of the following, if true, most strengthens the conclusion?",
        opts(
            "In a neighboring town that installed no new lights that year, crime stayed the same.",
            "The brighter streetlights were more energy-efficient than the old ones.",
            "Residents said they felt safer after the lights were installed.",
            "The town had wanted brighter lighting for several years.",
            "Crime is generally higher in areas with more foot traffic.",
        ),
        "A",
        "A controlled comparison - a similar town with no new lights and no crime drop - rules out a region-wide trend, isolating the lights as the cause and strengthening the conclusion.",
        difficulty="medium",
        think_aloud_steps=[
            "Conclusion: the lights caused the crime drop (a causal claim).",
            "To strengthen a cause, rule out that something else caused the drop.",
            "A shows a comparable town without new lights had no drop - so the drop wasn't a general trend.",
            "That isolates the lights as the cause; the others don't touch causation.",
        ],
        key_takeaway="For causal conclusions, the strongest strengthener usually eliminates an alternative cause via a controlled comparison.",
    ),
    we_do=[
        item(
            "we_1",
            "A company found that employees who use its new project-management software finish projects faster, and concluded the software makes teams more efficient. Which of the following, if true, most strengthens this conclusion?",
            opts(
                "When a team that had been slow was switched to the software, its completion times improved.",
                "The software was developed by an award-winning design firm.",
                "Employees say the software is easy to learn.",
                "The software is used by many large companies.",
                "Faster teams tend to have higher morale.",
            ),
            "A",
            "Showing the same previously-slow team sped up after adopting the software supports causation rather than the possibility that fast teams simply chose the software.",
            difficulty="medium",
            scaffold_hints=[
                "The claim is causal: software -> efficiency.",
                "Watch for reverse causation: maybe efficient teams adopt the software.",
                "Which choice shows the software CHANGING a team's speed?",
            ],
            immediate_feedback={
                "if_correct": "Yes - a before/after on the same team addresses reverse causation.",
                "if_incorrect": "Popularity and design awards don't show the software caused the speed-up.",
            },
        ),
        item(
            "we_2",
            "A nutrition writer argues that a new breakfast cereal improves focus, citing that children who eat it score higher on morning attention tests. Which of the following, if true, most strengthens the argument?",
            opts(
                "Before eating the cereal, those same children had scored no higher than other children on the tests.",
                "The cereal is fortified with several vitamins.",
                "The cereal is popular among parents.",
                "Attention tests are administered by trained staff.",
                "Children generally focus better after eating something.",
            ),
            "A",
            "If the high scorers were ordinary before the cereal, the cereal - not pre-existing ability - is the likely cause of the improvement, strengthening the claim.",
            difficulty="medium",
            scaffold_hints=[
                "Beware the alternative: maybe naturally focused kids eat this cereal.",
                "A before/after within the same children rules that out.",
                "Vitamins and popularity don't establish the focus effect.",
            ],
            immediate_feedback={
                "if_correct": "Right - ruling out prior ability strengthens the causal link.",
                "if_incorrect": "Choice E actually weakens by giving an alternative cause (any breakfast helps).",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A retailer concluded that its new loyalty program increased customer spending, because members spend more than non-members. Which of the following, if true, most strengthens the conclusion?",
            opts(
                "Customers' spending rose after they joined the program, compared with their spending before joining.",
                "The loyalty program was advertised on social media.",
                "Members receive a discount on their birthdays.",
                "The retailer has stores in many cities.",
                "High spenders enjoy collecting reward points.",
            ),
            "A",
            "A within-customer before/after comparison shows the program changed behavior, rather than merely that big spenders join programs.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "A city argues that its new bike-share program reduced car traffic, noting traffic fell after the program launched. Which of the following, if true, most strengthens the argument?",
            opts(
                "During the same period, a comparable city with no bike-share saw no decline in car traffic.",
                "The bike-share stations are conveniently located.",
                "Many residents praised the program.",
                "The bikes are maintained by a private contractor.",
                "Car traffic is usually lighter in warm weather.",
            ),
            "A",
            "A comparison city without bike-share and without a traffic drop rules out a general trend, isolating the program as the cause.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "Researchers claim a meditation app lowers stress, citing that users report less stress than non-users. Which of the following, if true, most strengthens the claim?",
            opts(
                "Users who were randomly assigned to the app reported lower stress than those assigned no app.",
                "The app includes guided sessions of varying lengths.",
                "The app has millions of downloads.",
                "Stress was measured with a standard questionnaire.",
                "People who meditate often also exercise.",
            ),
            "A",
            "Random assignment rules out that already-calm people simply chose the app, giving strong support that the app itself lowers stress.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# WEAKEN
# ===========================================================================
T_weaken = topic(
    topic_id="gmat::verbal::cr::weaken",
    slug="cr-weaken",
    title="Critical Reasoning: Weaken",
    prerequisites=["identify an argument's conclusion", "spot the assumption connecting evidence to conclusion"],
    learning_objectives=[
        "Find the conclusion, then choose the fact that makes it less likely to be true.",
        "Attack the assumption, or supply an alternative cause for the evidence.",
        "Ignore choices that are irrelevant or that merely fail to help the argument.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Finding an argument's assumption and how a strengthener supports it.",
        "do_now": {
            "instructions": "No notes. 4 minutes, from memory.",
            "items": [
                {"prompt": "What is the most common way to weaken a causal claim?", "answer": "Provide an alternative cause for the observed effect.", "targets": "weaken moves"},
                {"prompt": "Does a choice that is merely irrelevant weaken an argument?", "answer": "No - it must make the conclusion less likely.", "targets": "trap answers"},
                {"prompt": "Weaken or not: the two groups compared differed in another important way.", "answer": "Weakens (introduces a confounder).", "targets": "confounders"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that weakening usually means attacking the assumption or offering a rival cause.",
            "if_students_struggle": "Remind them the correct answer need not disprove the conclusion - just dent it.",
            "questions": [
                {"prompt": "Name two ways to weaken a causal argument.", "answer": "Break the assumption; give an alternative cause.", "targets": "weaken strategy"},
                {"prompt": "Why doesn't 'the plan is expensive' weaken 'the plan will cut congestion'?", "answer": "Cost doesn't bear on whether congestion falls.", "targets": "relevance"},
            ],
        },
        "prior_knowledge_bridge": "Strengthening reinforced the assumption; weakening does the opposite - it pries the assumption loose or hands you a different explanation for the evidence. Find the gap, then widen it.",
        "learning_intention": "By the end you can pick the choice that most reduces the likelihood the conclusion is true, usually by attacking the assumption or providing an alternative cause.",
        "success_criteria": [
            "I can state the conclusion the choice must undercut.",
            "I can tell a real weakener from an irrelevant choice.",
            "I can spot 'here's another cause' as a weakening move.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A bakery introduced a rewards card and its sales rose the next month, so the owner concluded the rewards card increased sales. Which of the following, if true, most seriously weakens the conclusion?",
        opts(
            "The bakery's only nearby competitor closed for renovations that same month.",
            "The rewards card was printed on recycled paper.",
            "Some customers forgot to bring their rewards card.",
            "The bakery had offered a rewards card once before.",
            "The bakery sells both bread and pastries.",
        ),
        "A",
        "A competitor closing for the month offers an alternative cause for the sales bump, undermining the claim that the rewards card was responsible.",
        difficulty="medium",
        think_aloud_steps=[
            "Conclusion: the rewards card caused higher sales (causal).",
            "To weaken a cause, find another explanation for the effect.",
            "A competitor closing that month explains the rise without the card.",
            "The other choices are irrelevant to what caused the increase.",
        ],
        key_takeaway="For causal conclusions, the strongest weakener usually supplies an alternative cause for the evidence.",
    ),
    we_do=[
        item(
            "we_1",
            "A manager concluded that a new training program improved her team's sales, since sales rose after the training. Which of the following, if true, most weakens the conclusion?",
            opts(
                "The company launched a large price promotion the same week as the training.",
                "The training program lasted two full days.",
                "Some team members had attended similar training before.",
                "The trainer was hired from outside the company.",
                "Sales are tracked by an automated system.",
            ),
            "A",
            "A simultaneous price promotion is an alternative cause for the sales rise, so the training may not deserve the credit.",
            difficulty="medium",
            scaffold_hints=[
                "The claim is causal: training -> higher sales.",
                "Look for something else that could have raised sales at the same time.",
                "Which choice offers a competing explanation?",
            ],
            immediate_feedback={
                "if_correct": "Yes - a concurrent promotion undercuts the causal claim.",
                "if_incorrect": "Details about the trainer or tracking don't change what caused the rise.",
            },
        ),
        item(
            "we_2",
            "A health official argued that a public-awareness campaign reduced smoking, because smoking rates fell after the campaign. Which of the following, if true, most weakens the argument?",
            opts(
                "A steep national tax on cigarettes took effect at the same time as the campaign.",
                "The campaign used billboards and radio ads.",
                "Some smokers said they never saw the campaign.",
                "The campaign was funded by a health charity.",
                "Smoking rates are measured through annual surveys.",
            ),
            "A",
            "A simultaneous cigarette tax is a well-known driver of reduced smoking, giving an alternative cause for the decline and weakening the campaign's claimed effect.",
            difficulty="medium",
            scaffold_hints=[
                "What else, happening at the same time, is known to cut smoking?",
                "That competing cause weakens the campaign's claim.",
                "Ad formats and funding don't address causation.",
            ],
            immediate_feedback={
                "if_correct": "Right - the tax is a strong alternative cause.",
                "if_incorrect": "'Some never saw it' is minor; a nationwide tax is a much bigger competing cause.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A store owner concluded that moving the checkout counter increased impulse purchases, since such purchases rose after the move. Which of the following, if true, most weakens the conclusion?",
            opts(
                "The store began stocking popular candy and magazines near the checkout at the same time.",
                "The new counter is made of a more durable material.",
                "The move took place over a single weekend.",
                "The store has two entrances.",
                "Impulse purchases are recorded at the register.",
            ),
            "A",
            "Adding tempting items by the checkout is an alternative cause for the rise in impulse buys, independent of the counter's location.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "A blogger claims that switching to a standing desk increased her productivity, noting she got more done after the switch. Which of the following, if true, most weakens the claim?",
            opts(
                "She also started using a new task-planning app the week she got the standing desk.",
                "The standing desk was more expensive than her old desk.",
                "She sometimes lowers the desk to sit.",
                "Standing desks are increasingly common in offices.",
                "She measures productivity by tasks completed.",
            ),
            "A",
            "Adopting a new planning app at the same time provides an alternative cause for the productivity gain, undermining the desk's claimed effect.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "A city concluded that a new after-school program reduced youth crime, because such crime fell after the program opened. Which of the following, if true, most weakens the conclusion?",
            opts(
                "During the same period, the city hired dozens of additional police officers to patrol youth areas.",
                "The program offers sports and tutoring.",
                "The program is open four days a week.",
                "Attendance at the program varies by season.",
                "Youth crime is reported by local schools.",
            ),
            "A",
            "A simultaneous surge in policing is an alternative cause for the drop in youth crime, weakening the claim that the program was responsible.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# EVALUATE
# ===========================================================================
T_evaluate = topic(
    topic_id="gmat::verbal::cr::evaluate",
    slug="cr-evaluate",
    title="Critical Reasoning: Evaluate the Argument",
    prerequisites=["identify an argument's assumption", "understand strengthen and weaken"],
    learning_objectives=[
        "Identify the question whose answer would most affect the argument's validity.",
        "Use the 'variance test': a good evaluate answer helps either way it is resolved.",
        "Avoid questions whose answers leave the conclusion unchanged.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Knowing what strengthens and weakens an argument.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "What makes a good 'evaluate' answer?", "answer": "Its answer would strengthen the argument one way and weaken it the other.", "targets": "variance test"},
                {"prompt": "If a question's answer doesn't change the conclusion either way, is it a good evaluate choice?", "answer": "No.", "targets": "relevance"},
                {"prompt": "Turn 'the plan will cut costs' into an evaluate target.", "answer": "Ask whether the savings exceed the plan's added expenses.", "targets": "forming the question"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that an evaluate answer must be able to swing the argument both ways.",
            "if_students_struggle": "Have them literally answer the choice 'yes' then 'no' and see if the conclusion moves.",
            "questions": [
                {"prompt": "State the variance (both-ways) test.", "answer": "A good evaluate question strengthens if answered one way and weakens if answered the other.", "targets": "variance test"},
                {"prompt": "Why test both answers to a choice?", "answer": "To confirm the answer actually affects the conclusion.", "targets": "method"},
            ],
        },
        "prior_knowledge_bridge": "Strengthen and weaken each move the argument one direction. An evaluate question asks for the single fact that could move it EITHER direction - so you test a choice by answering it both ways and watching whether the conclusion shifts.",
        "learning_intention": "By the end you can select the question whose answer would most affect the argument, verified by the both-ways variance test.",
        "success_criteria": [
            "I can state what the argument concludes and assumes.",
            "I can apply the both-ways test to a candidate question.",
            "I can reject questions that don't move the conclusion.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A hospital plans to shorten patient wait times by adding a second check-in clerk. The answer to which of the following would be most useful in evaluating whether the plan will work?",
        opts(
            "Whether the check-in step, rather than a later step such as seeing a doctor, is what causes most of the waiting.",
            "Whether the second clerk will be paid the same as the first.",
            "Whether patients are satisfied with the current clerks.",
            "Whether the hospital has enough desks for two clerks.",
            "Whether wait times are longer on weekends.",
        ),
        "A",
        "Test A both ways: if check-in is the bottleneck, a second clerk helps (strengthens); if the delay is later, a second clerk won't help (weakens). Because its answer swings the plan either way, A is the best evaluation target.",
        difficulty="medium",
        think_aloud_steps=[
            "Conclusion: a second clerk will cut wait times. Assumption: check-in is the bottleneck.",
            "Apply the both-ways test to A: bottleneck at check-in -> helps; bottleneck later -> useless.",
            "Since A's answer can strengthen or weaken, it's the key evaluation question.",
            "The others (pay, desks, satisfaction) don't change whether the plan works.",
        ],
        key_takeaway="The best evaluate answer is the question whose two possible answers push the conclusion in opposite directions.",
    ),
    we_do=[
        item(
            "we_1",
            "A publisher plans to raise profit by releasing its novels only as e-books. Which of the following would be most useful to determine in order to evaluate the plan?",
            opts(
                "Whether most current print buyers would switch to e-books rather than buy from print competitors.",
                "Whether e-books can display cover art.",
                "How long it takes to format an e-book.",
                "Whether the publisher's authors write fiction.",
                "Whether e-readers are dropping in price.",
            ),
            "A",
            "Both ways: if buyers switch to e-books, profit can rise; if they defect to print rivals, profit falls. Its answer swings the plan, so it is the key question.",
            difficulty="medium",
            scaffold_hints=[
                "What must be true for e-book-only to raise profit?",
                "Answer the choice 'yes' and 'no' - does the conclusion move?",
                "Only one choice changes the outcome either way.",
            ],
            immediate_feedback={
                "if_correct": "Right - buyer switching is the pivot the plan turns on.",
                "if_incorrect": "Formatting time and cover art don't determine whether profit rises.",
            },
        ),
        item(
            "we_2",
            "A farm plans to raise its apple yield by switching to a new irrigation system. The answer to which of the following would be most useful in evaluating the plan?",
            opts(
                "Whether water supply, rather than something like soil quality, is what currently limits the yield.",
                "Whether the new system is quieter than the old one.",
                "Whether neighboring farms use the same system.",
                "Whether the apples are sold locally.",
                "Whether the system was installed by certified technicians.",
            ),
            "A",
            "Both ways: if water is the limiting factor, better irrigation raises yield; if soil is the limit, it won't. The answer moves the conclusion either way, making A decisive.",
            difficulty="medium",
            scaffold_hints=[
                "The plan assumes water is the bottleneck to yield.",
                "Test that assumption with the both-ways method.",
                "Which choice's answer could sink or save the plan?",
            ],
            immediate_feedback={
                "if_correct": "Yes - if water isn't the limit, better irrigation won't help.",
                "if_incorrect": "Noise, installers, and sales location don't affect whether yield rises.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A streaming service plans to gain subscribers by producing more original comedies. The answer to which of the following would be most useful in evaluating the plan?",
            opts(
                "Whether the viewers the service hopes to attract choose a service based on its original comedies.",
                "Whether comedies cost less to produce than dramas.",
                "Whether the service currently offers any comedies.",
                "Whether competitors also produce comedies.",
                "Whether comedies win more awards than dramas.",
            ),
            "A",
            "Both ways: if target viewers pick services for comedies, the plan can add subscribers; if not, it won't. The answer swings the conclusion, so A is the key question.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "A company plans to cut costs by letting most employees work from home and giving up its office lease. The answer to which of the following would be most useful in evaluating the plan?",
            opts(
                "Whether the productivity of remote employees would fall enough to outweigh the rent savings.",
                "Whether employees prefer working from home.",
                "Whether the office is in a downtown location.",
                "Whether the lease has a renewal option.",
                "Whether other firms have gone remote.",
            ),
            "A",
            "Both ways: if remote productivity holds, savings are real; if it drops sharply, the losses can exceed the rent saved. The answer moves the conclusion, so A is decisive.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "A museum plans to increase attendance by staying open late on Fridays. The answer to which of the following would be most useful in evaluating the plan?",
            opts(
                "Whether a substantial number of potential visitors are unable to attend during current hours but could attend on Friday evenings.",
                "Whether the museum's cafe is open on Fridays.",
                "Whether staff are willing to work late.",
                "Whether the museum is near public transit.",
                "Whether other museums stay open late.",
            ),
            "A",
            "Both ways: if many would-be visitors are free only on Friday evenings, attendance can rise; if not, late hours add little. The answer swings the plan, so A is the key question.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# INFERENCE
# ===========================================================================
T_inference = topic(
    topic_id="gmat::verbal::cr::inference",
    slug="cr-inference",
    title="Critical Reasoning: Inference",
    prerequisites=["read a set of statements precisely", "distinguish 'must be true' from 'could be true'"],
    learning_objectives=[
        "Choose the statement that MUST be true given the premises - nothing more.",
        "Combine conditional statements and use the contrapositive.",
        "Reject choices that go even slightly beyond what the text guarantees.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Reading conditional ('if-then') statements and their contrapositives.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "Contrapositive of 'If it rains, the game is canceled.'", "answer": "If the game is not canceled, it did not rain.", "targets": "contrapositive"},
                {"prompt": "Does 'most A are B' let you conclude 'most B are A'?", "answer": "No.", "targets": "quantifier traps"},
                {"prompt": "'Must be true' vs 'could be true' - which does inference require?", "answer": "Must be true.", "targets": "standard"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls the contrapositive and the strict 'must be true' bar - the backbone of inference questions.",
            "if_students_struggle": "Have them cross out any choice that adds a new idea not in the text.",
            "questions": [
                {"prompt": "If 'All X are Y' and 'no Y are Z,' what must be true?", "answer": "No X are Z.", "targets": "chaining"},
                {"prompt": "Why reject a choice that is merely plausible?", "answer": "Inference requires it be guaranteed, not just likely.", "targets": "standard"},
            ],
        },
        "prior_knowledge_bridge": "Unlike strengthen/weaken, inference gives you the premises as true and asks what they force. Your job isn't to judge an argument - it's to find the one choice the statements guarantee, using chaining and the contrapositive, and to reject anything that reaches beyond the text.",
        "learning_intention": "By the end you can select the only choice that must be true given the statements, combining conditionals and rejecting overreach.",
        "success_criteria": [
            "I can take the premises as given and not add outside assumptions.",
            "I can chain conditionals and apply the contrapositive.",
            "I can eliminate 'could be true but not guaranteed' choices.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "Every product in the store's front display is on sale. Nothing that is on sale can be returned for a refund. If the statements above are true, which of the following must also be true?",
        opts(
            "No product in the front display can be returned for a refund.",
            "Every product that cannot be returned is in the front display.",
            "Products not on sale are all in the back of the store.",
            "Some products in the front display can be returned.",
            "The store rarely gives refunds.",
        ),
        "A",
        "Front-display items are all on sale, and on-sale items cannot be refunded; chaining these, no front-display item can be refunded. A is forced; the others reverse the logic or add new claims.",
        difficulty="medium",
        think_aloud_steps=[
            "Premise 1: front display -> on sale. Premise 2: on sale -> no refund.",
            "Chain them: front display -> on sale -> no refund.",
            "So every front-display product cannot be refunded - that's A.",
            "B reverses the chain; C, D, E add facts the text never gives.",
        ],
        key_takeaway="Inference = what the premises force. Chain conditionals forward; never reverse them or add outside information.",
    ),
    we_do=[
        item(
            "we_1",
            "All of the interns attended the safety briefing. Anyone who attended the safety briefing received a badge. If the statements above are true, which of the following must be true?",
            opts(
                "Every intern received a badge.",
                "Only interns received badges.",
                "Everyone with a badge is an intern.",
                "Some interns did not attend the briefing.",
                "The briefing was required by law.",
            ),
            "A",
            "Interns -> attended -> received a badge, so every intern got a badge. The reversed and added-fact choices aren't guaranteed.",
            difficulty="easy",
            scaffold_hints=[
                "Write the two conditionals and chain them.",
                "intern -> attended -> badge.",
                "Beware choices that flip the arrow ('everyone with a badge is an intern').",
            ],
            immediate_feedback={
                "if_correct": "Right - chaining gives intern -> badge.",
                "if_incorrect": "B and C reverse the logic; the text only guarantees intern -> badge.",
            },
        ),
        item(
            "we_2",
            "No book in the reference room may be borrowed. Every atlas in this library is kept in the reference room. If the statements above are true, which of the following must be true?",
            opts(
                "No atlas in this library may be borrowed.",
                "Every book that may not be borrowed is an atlas.",
                "All borrowable books are outside the reference room.",
                "Some atlases may be borrowed.",
                "The reference room contains only atlases.",
            ),
            "A",
            "Atlases are in the reference room, and reference-room books cannot be borrowed; so no atlas can be borrowed. The rest reverse the logic or overreach.",
            difficulty="medium",
            scaffold_hints=[
                "atlas -> in reference room -> cannot be borrowed.",
                "Chain forward to the guaranteed result.",
                "Reject choices that reverse or add claims.",
            ],
            immediate_feedback={
                "if_correct": "Exactly - the chain forces 'no atlas may be borrowed.'",
                "if_incorrect": "C reverses the relationship; only atlas -> not borrowable is guaranteed.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "The theater sells out every show that opens on a Saturday. Last week's show did not sell out. If the statements above are true, which of the following must be true?",
            opts(
                "Last week's show did not open on a Saturday.",
                "The theater never opens shows on Saturdays.",
                "Last week's show was poorly reviewed.",
                "The theater will sell out its next Saturday show.",
                "Most of the theater's shows open on Saturdays.",
            ),
            "A",
            "Opening on Saturday guarantees a sellout; since the show did not sell out, by the contrapositive it did not open on a Saturday.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "Every applicant who passed the exam was invited to an interview. Maria was not invited to an interview. If the statements above are true, which of the following must be true?",
            opts(
                "Maria did not pass the exam.",
                "Maria did not apply.",
                "Everyone who was invited passed the exam.",
                "Maria will be invited later.",
                "The exam was difficult.",
            ),
            "A",
            "Passing guarantees an invitation; Maria wasn't invited, so by the contrapositive she did not pass. The others aren't forced.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "All the vehicles in the company fleet run on electricity. No electric vehicle in the city is allowed in the old tunnel. If the statements above are true, which of the following must be true?",
            opts(
                "No vehicle in the company fleet is allowed in the old tunnel.",
                "Every vehicle barred from the tunnel is in the company fleet.",
                "The company fleet is the largest in the city.",
                "Some fleet vehicles are allowed in the tunnel.",
                "Electric vehicles are cheaper to operate.",
            ),
            "A",
            "Fleet vehicles are electric, and city electric vehicles are barred from the tunnel; so no fleet vehicle is allowed in the tunnel. The rest reverse or overreach.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# EXPLAIN THE PARADOX
# ===========================================================================
T_paradox = topic(
    topic_id="gmat::verbal::cr::explain_paradox",
    slug="cr-paradox",
    title="Critical Reasoning: Explain the Paradox",
    prerequisites=["state two facts that seem to conflict", "distinguish an explanation from a mere comment"],
    learning_objectives=[
        "Pin down the two facts that seem to contradict each other.",
        "Choose the option that lets BOTH facts be true at once.",
        "Reject options that deepen the mystery or address only one fact.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Reading two facts and noticing the tension between them.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "What does a paradox/resolve question ask you to do?", "answer": "Explain how two seemingly conflicting facts can both be true.", "targets": "task"},
                {"prompt": "Should the right answer make one fact false?", "answer": "No - both facts stay true; the answer explains the gap.", "targets": "method"},
                {"prompt": "Resolve: prices rose but revenue fell.", "answer": "So many customers left that the loss outweighed the higher price.", "targets": "example"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that a resolution must let both surprising facts coexist.",
            "if_students_struggle": "Have them write the two facts as 'X, yet Y' and look for the missing bridge.",
            "questions": [
                {"prompt": "State the two facts to reconcile in your own words before answering.", "answer": "Identify 'fact 1, yet surprising fact 2.'", "targets": "framing"},
                {"prompt": "Why reject a choice that explains only fact 1?", "answer": "It must account for the surprising second fact too.", "targets": "scope"},
            ],
        },
        "prior_knowledge_bridge": "A paradox question hands you two facts that seem to clash. You're not judging an argument - you're finding the missing piece of information that makes the clash disappear so both facts can be true together.",
        "learning_intention": "By the end you can identify two conflicting facts and pick the option that reconciles them without denying either.",
        "success_criteria": [
            "I can restate the paradox as 'X, yet surprisingly Y.'",
            "I can pick the option that lets both X and Y be true.",
            "I can reject options that ignore one fact or make it worse.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "A coffee shop replaced its paper cups with more expensive reusable-style cups, yet its total cup costs for the year went down. Which of the following, if true, best explains this result?",
        opts(
            "Customers who brought the reusable-style cups back for refills sharply reduced the number of new cups the shop had to buy.",
            "The reusable-style cups come in several colors.",
            "The shop's coffee sales rose slightly during the year.",
            "Paper cups had been the shop's cheapest supply.",
            "The new cups are made by a local manufacturer.",
        ),
        "A",
        "Both facts stay true: the cups cost more each, yet total cup costs fell because far fewer cups were purchased overall. A supplies the bridge; the others don't reconcile the two facts.",
        difficulty="medium",
        think_aloud_steps=[
            "Fact 1: each new cup is more expensive. Fact 2: total cup costs fell (surprising).",
            "I need a reason total cost could drop despite higher unit price.",
            "A: reuse cut the NUMBER of cups bought - fewer cups times higher price can still be less.",
            "Both facts remain true; the other choices don't explain the drop.",
        ],
        key_takeaway="A good resolution keeps both surprising facts true and supplies the missing information that removes the conflict.",
    ),
    we_do=[
        item(
            "we_1",
            "A factory installed faster machines expecting to produce more units per day, but its daily output actually fell. Which of the following, if true, best explains the drop?",
            opts(
                "The faster machines broke down often and sat idle awaiting repairs for long stretches.",
                "The faster machines use more electricity.",
                "The factory kept the same number of workers.",
                "The old machines had been in use for years.",
                "The new machines are larger than the old ones.",
            ),
            "A",
            "Frequent breakdowns and idle time can lower output even though the machines are faster when running - reconciling 'faster machines' with 'lower output.'",
            difficulty="medium",
            scaffold_hints=[
                "State it as 'faster machines, yet lower output.'",
                "What could make faster machines produce less overall?",
                "Look for downtime, not for irrelevant details.",
            ],
            immediate_feedback={
                "if_correct": "Right - idle time from breakdowns explains the paradox.",
                "if_incorrect": "Electricity use and size don't explain why fewer units came out.",
            },
        ),
        item(
            "we_2",
            "A library extended its hours to increase the number of visitors, but the number of visitors decreased afterward. Which of the following, if true, best explains this outcome?",
            opts(
                "To fund the longer hours, the library cut its budget for new books, and many regulars stopped coming once new titles grew scarce.",
                "The library is located near a university.",
                "The extended hours were advertised on the library's website.",
                "The library employs several part-time staff.",
                "Library visits are counted by an electronic gate.",
            ),
            "A",
            "The longer hours came at the cost of fewer new books, driving regulars away; both facts hold, and A bridges them.",
            difficulty="medium",
            scaffold_hints=[
                "Frame it: 'longer hours, yet fewer visitors.'",
                "What trade-off could the longer hours have caused?",
                "The bridge must explain why visitors fell.",
            ],
            immediate_feedback={
                "if_correct": "Yes - a hidden trade-off (fewer new books) explains the decline.",
                "if_incorrect": "Location and staffing don't account for the drop in visitors.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A phone maker lowered the price of its flagship model, expecting to sell more units, but it sold fewer units than before. Which of the following, if true, best explains this result?",
            opts(
                "Buyers took the lower price as a sign the model was about to be discontinued and avoided it.",
                "The phone comes in three colors.",
                "The price cut was announced online.",
                "The company also makes tablets.",
                "The phone's battery lasts a full day.",
            ),
            "A",
            "If the lower price signaled impending discontinuation, buyers would shy away - explaining why a price cut reduced sales while both facts remain true.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "A city added dozens of new bus routes to reduce car traffic, yet car traffic increased in the following year. Which of the following, if true, best explains this?",
            opts(
                "The new routes made the city more attractive to newcomers, and the resulting population growth put more cars on the road than the buses removed.",
                "The buses run on a fixed schedule.",
                "The new routes were mapped by transit planners.",
                "Bus fares stayed the same.",
                "The buses are wheelchair-accessible.",
            ),
            "A",
            "Population growth spurred by better transit can add more cars than the buses take off the road, letting both facts be true.",
            difficulty="hard",
        ),
        item(
            "you_3",
            "A software company started offering generous unlimited vacation, expecting employees to feel less burned out, but reported burnout rose. Which of the following, if true, best explains the increase?",
            opts(
                "Without a set number of days, employees felt unsure how much leave was acceptable and ended up taking less time off than before.",
                "The company has offices in several countries.",
                "The policy was announced in a company email.",
                "Employees can also work from home.",
                "The company's software is used worldwide.",
            ),
            "A",
            "Ambiguity about acceptable leave led employees to take less vacation, raising burnout - reconciling the generous policy with the worse outcome.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# FLAW
# ===========================================================================
T_flaw = topic(
    topic_id="gmat::verbal::cr::flaw",
    slug="cr-flaw",
    title="Critical Reasoning: Find the Flaw",
    prerequisites=["identify an argument's conclusion and evidence", "recognize common reasoning errors"],
    learning_objectives=[
        "Name the specific reasoning error an argument commits.",
        "Recognize classic flaws: ad hominem, appeal to popularity, post hoc, hasty generalization, appeal to ignorance, slippery slope.",
        "Match the abstract flaw description to what the argument actually did.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Separating an argument's conclusion from its evidence.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "Name the flaw: 'X happened after Y, so Y caused X.'", "answer": "Post hoc (correlation/sequence mistaken for causation).", "targets": "post hoc"},
                {"prompt": "Name the flaw: 'Most people buy it, so it's the best.'", "answer": "Appeal to popularity.", "targets": "popularity"},
                {"prompt": "Name the flaw: 'No one has proven it's harmful, so it's safe.'", "answer": "Appeal to ignorance.", "targets": "ignorance"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls the named flaw families so learners can match them to the argument.",
            "if_students_struggle": "Have them describe in their own words what the author did wrong before reading the choices.",
            "questions": [
                {"prompt": "Name the flaw: 'She's rich, so ignore her economic argument.'", "answer": "Ad hominem (attacking the person).", "targets": "ad hominem"},
                {"prompt": "Name the flaw: 'Every swan I've seen is white, so all swans are white.'", "answer": "Hasty generalization from a limited sample.", "targets": "generalization"},
            ],
        },
        "prior_knowledge_bridge": "You can find a conclusion and its evidence. A flaw question asks WHY the leap between them is illegitimate - and the answer is usually one of a handful of named reasoning errors. Describe the mistake in your own words first, then match it.",
        "learning_intention": "By the end you can name the specific reasoning error an argument commits and match it to the correct abstract description.",
        "success_criteria": [
            "I can describe, in plain words, what the argument did wrong.",
            "I can recognize the classic named flaws.",
            "I can match my description to the answer choice that states it.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "Critic: The restaurant's owner says his food is the healthiest in town, but he is trying to sell meals, so his claim is worthless. The critic's reasoning is most vulnerable to the criticism that it",
        opts(
            "rejects a claim based on the source's motive rather than on any evidence about the claim itself.",
            "relies on a sample of diners that is too small.",
            "assumes that healthy food cannot be profitable.",
            "confuses a cause with an effect.",
            "treats the owner's opinion as expert testimony.",
        ),
        "A",
        "The critic dismisses the health claim only because the owner has a motive to sell - an ad hominem that ignores whether the food is actually healthy. A names that error.",
        difficulty="medium",
        think_aloud_steps=[
            "Conclusion: the owner's claim is worthless. Evidence: he wants to sell meals.",
            "In my words: attacking the person's motive, not the claim - that's ad hominem.",
            "Find the choice describing that: A.",
            "The other choices name flaws the argument didn't commit.",
        ],
        key_takeaway="Describe the reasoning error in plain words first, then match it to the choice - don't be lured by real flaws the argument didn't make.",
    ),
    we_do=[
        item(
            "we_1",
            "Advertisement: More dentists choose BrightSmile toothpaste than any other brand, so BrightSmile must be the most effective toothpaste. The reasoning is most vulnerable to the criticism that it",
            opts(
                "treats a product's popularity as proof of its effectiveness.",
                "relies on the opinion of a single dentist.",
                "assumes dentists never change brands.",
                "ignores the price of competing toothpastes.",
                "confuses effectiveness with safety.",
            ),
            "A",
            "The ad slides from 'most chosen' to 'most effective' - an appeal to popularity. A names that error.",
            difficulty="easy",
            scaffold_hints=[
                "What is the evidence, and what is concluded from it?",
                "Popularity -> quality is a classic named flaw.",
                "Match your description to the choice.",
            ],
            immediate_feedback={
                "if_correct": "Right - popularity doesn't establish effectiveness.",
                "if_incorrect": "The ad cites many dentists, not one; the core error is popularity -> quality.",
            },
        ),
        item(
            "we_2",
            "Politician: No study has ever shown that our new tax policy harms small businesses, so the policy is clearly safe for them. The reasoning is most vulnerable to the criticism that it",
            opts(
                "treats the absence of evidence of harm as proof that there is no harm.",
                "relies on studies funded by the government.",
                "assumes all small businesses are alike.",
                "confuses correlation with causation.",
                "attacks the motives of the policy's critics.",
            ),
            "A",
            "Concluding the policy is safe merely because harm hasn't been shown is an appeal to ignorance. A names it.",
            difficulty="medium",
            scaffold_hints=[
                "The evidence is a LACK of evidence.",
                "Absence of proof of harm is not proof of safety.",
                "Which named flaw is that?",
            ],
            immediate_feedback={
                "if_correct": "Exactly - appeal to ignorance.",
                "if_incorrect": "The argument doesn't attack critics or cite studies; it leans on missing evidence.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "Manager: Right after we repainted the office, output went up, so the new paint color is boosting productivity. The reasoning is most vulnerable to the criticism that it",
            opts(
                "concludes that the paint caused the rise simply because the rise came after the painting.",
                "relies on the testimony of a few employees.",
                "assumes all employees like the color.",
                "ignores the cost of the paint.",
                "treats productivity and morale as the same thing.",
            ),
            "A",
            "Inferring causation from mere sequence (output rose after painting) is a post hoc flaw. A names it.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "Editorial: If the city allows food trucks on Main Street, soon every sidewalk will be blocked and no pedestrian will be able to walk downtown. So food trucks must be banned. The reasoning is most vulnerable to the criticism that it",
            opts(
                "assumes without support that a limited step will inevitably lead to an extreme outcome.",
                "relies on an unrepresentative survey.",
                "attacks the character of food-truck owners.",
                "confuses a necessary condition with a sufficient one.",
                "treats popularity as evidence of quality.",
            ),
            "A",
            "Claiming one modest allowance must snowball into total blockage is a slippery-slope flaw. A names it.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "Reviewer: This author's last three novels were bestsellers, so her next book is certain to be a bestseller too. The reasoning is most vulnerable to the criticism that it",
            opts(
                "assumes that a past pattern must continue without considering factors that could change the outcome.",
                "relies on the opinions of unqualified readers.",
                "attacks the author rather than the books.",
                "confuses sales with literary quality.",
                "treats the absence of failure as proof of success.",
            ),
            "A",
            "Projecting a past streak forward as a certainty ignores factors that could break the pattern - an unwarranted assumption of continuity. A names it.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# BOLDFACE (DESCRIBE THE ROLE)
# ===========================================================================
T_boldface = topic(
    topic_id="gmat::verbal::cr::boldface",
    slug="cr-boldface",
    title="Critical Reasoning: Boldface (Describe the Role)",
    prerequisites=["identify the author's conclusion", "distinguish evidence, opposing views, and conclusions"],
    learning_objectives=[
        "Determine the author's overall conclusion first.",
        "Label each boldfaced portion by its role: conclusion, supporting evidence, opposing position, or objection.",
        "Match both labels to the answer choice that describes them.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Telling an author's own conclusion from a view the author opposes.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "What roles can a boldfaced statement play?", "answer": "Conclusion, supporting evidence, an opposing position, or an objection the author answers.", "targets": "role types"},
                {"prompt": "First step on a boldface question?", "answer": "Find the author's own conclusion.", "targets": "method"},
                {"prompt": "If a portion is a view the author argues against, its role is...", "answer": "An opposing position (not the author's conclusion).", "targets": "opposing view"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls the small set of roles a boldfaced portion can play and the 'find the conclusion first' method.",
            "if_students_struggle": "Have them mark each boldface as 'author agrees' or 'author disagrees' before labeling.",
            "questions": [
                {"prompt": "How do you tell the author's conclusion from an opposing view?", "answer": "The author supports the conclusion and argues against the opposing view.", "targets": "stance"},
                {"prompt": "Why label roles before reading the choices?", "answer": "To avoid being swayed by tempting but wrong role labels.", "targets": "method"},
            ],
        },
        "prior_knowledge_bridge": "Boldface questions are structure questions: they ask what job each bolded sentence does. If you first pin down the author's own conclusion, every other sentence becomes easy to label as support, an opposing view, or an objection the author rebuts.",
        "learning_intention": "By the end you can label each boldfaced portion by its role in the argument and match both to the correct answer choice.",
        "success_criteria": [
            "I can state the author's overall conclusion.",
            "I can label a boldface as support, opposing view, or objection.",
            "I can match both role labels to the answer choice.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "Analyst: <b>The company should keep its downtown store open.</b> Critics point to the store's high rent. However, <b>the downtown store attracts customers who then shop at the company's other locations.</b> In the analyst's argument, the two boldfaced portions play which of the following roles?",
        opts(
            "The first is the conclusion the analyst defends; the second is evidence the analyst offers in support of that conclusion.",
            "The first is an objection the analyst rejects; the second is the analyst's conclusion.",
            "Both portions are evidence for the analyst's conclusion.",
            "The first is the conclusion; the second is an objection to it.",
            "The first is evidence; the second is the analyst's conclusion.",
        ),
        "A",
        "The analyst's own view is 'keep the store open' (conclusion). The second bold portion (it draws customers to other stores) is support answering the rent objection. So first = conclusion, second = supporting evidence.",
        difficulty="medium",
        think_aloud_steps=[
            "Find the author's conclusion: 'keep the downtown store open.' That's the first bold portion.",
            "The critics' rent point is an objection (not bolded).",
            "The second bold portion answers that objection - it's supporting evidence.",
            "So first = conclusion, second = support -> choice A.",
        ],
        key_takeaway="Find the author's conclusion first; then every boldface is either that conclusion, support for it, or a view the author opposes.",
    ),
    we_do=[
        item(
            "we_1",
            "Columnist: Many believe that <b>working longer hours always increases a company's output.</b> But <b>studies show that overworked employees make more errors, which lowers total output.</b> The belief is therefore mistaken. In the columnist's argument, the two boldfaced portions play which of the following roles?",
            opts(
                "The first is a position the columnist argues against; the second is evidence used to reject that position.",
                "The first is the columnist's conclusion; the second supports it.",
                "Both portions are the columnist's evidence.",
                "The first is evidence; the second is the conclusion.",
                "The first is the conclusion; the second is an objection to it.",
            ),
            "A",
            "The columnist's conclusion is 'the belief is mistaken.' The first bold portion is that popular belief (opposed); the second is evidence against it.",
            difficulty="medium",
            scaffold_hints=[
                "What does the columnist actually conclude?",
                "Is the first bold portion something the columnist agrees or disagrees with?",
                "Label the second: does it support the belief or attack it?",
            ],
            immediate_feedback={
                "if_correct": "Right - first = opposed position, second = evidence against it.",
                "if_incorrect": "The columnist's conclusion is unbolded ('the belief is mistaken'); the first bold is the view being refuted.",
            },
        ),
        item(
            "we_2",
            "Scientist: <b>This drug does not reduce recovery time.</b> Its supporters cite a trial in which patients on the drug recovered faster, but <b>those patients were also much younger than the comparison group.</b> In the scientist's argument, the two boldfaced portions play which of the following roles?",
            opts(
                "The first is the scientist's conclusion; the second is evidence used to undermine a study offered against that conclusion.",
                "The first is evidence; the second is the scientist's conclusion.",
                "Both portions are conclusions the scientist draws.",
                "The first is an objection; the second is the scientist's conclusion.",
                "The first is the conclusion; the second is an assumption it relies on.",
            ),
            "A",
            "The scientist concludes the drug doesn't help (first bold). The second bold points out a confounder (younger patients) that undercuts the supporting trial - it's evidence for the conclusion.",
            difficulty="medium",
            scaffold_hints=[
                "The first bold is a flat claim - likely the conclusion.",
                "The second bold weakens the opponents' trial - so it supports the scientist.",
                "Match: conclusion + supporting evidence.",
            ],
            immediate_feedback={
                "if_correct": "Yes - conclusion first, confounder-evidence second.",
                "if_incorrect": "The 'younger patients' point backs the scientist by discrediting the rival trial.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "Official: <b>The city should build the new light-rail line.</b> Opponents cite its cost. Still, <b>the line is projected to remove thousands of cars from the roads each day, easing congestion.</b> In the official's argument, the two boldfaced portions play which of the following roles?",
            opts(
                "The first is the conclusion the official defends; the second is evidence offered to support it against an objection.",
                "The first is an objection; the second is the conclusion.",
                "Both portions are objections the official concedes.",
                "The first is evidence; the second is the conclusion.",
                "The first is the conclusion; the second is an assumption it requires.",
            ),
            "A",
            "The official's conclusion is 'build the line' (first bold). The projected car reduction (second bold) is supporting evidence that answers the cost objection.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "Editor: Some argue that <b>printed newspapers will disappear within a decade.</b> Yet <b>subscriptions to several major print papers have grown steadily over the past five years.</b> The prediction is therefore doubtful. In the editor's argument, the two boldfaced portions play which of the following roles?",
            opts(
                "The first is a prediction the editor disputes; the second is evidence the editor uses against it.",
                "The first is the editor's conclusion; the second supports it.",
                "Both portions are the editor's evidence.",
                "The first is evidence against the conclusion; the second is the conclusion.",
                "The first is the editor's conclusion; the second is an objection to it.",
            ),
            "A",
            "The editor concludes the prediction is doubtful. The first bold is that disputed prediction; the second is evidence (rising subscriptions) against it.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "Consultant: <b>The firm should adopt a four-day workweek.</b> Skeptics worry productivity will fall. However, <b>at similar firms that made the switch, output per employee stayed the same or rose.</b> In the consultant's argument, the two boldfaced portions play which of the following roles?",
            opts(
                "The first is the recommendation the consultant makes; the second is evidence offered to support it against a worry.",
                "The first is a worry the consultant shares; the second is the recommendation.",
                "Both portions are evidence for the recommendation.",
                "The first is evidence; the second is the recommendation.",
                "The first is the recommendation; the second is an objection to it.",
            ),
            "A",
            "The consultant's recommendation (conclusion) is the four-day week (first bold). The comparable-firm data (second bold) supports it against the productivity worry.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# COMPLETE THE ARGUMENT
# ===========================================================================
T_complete = topic(
    topic_id="gmat::verbal::cr::complete_argument",
    slug="cr-complete",
    title="Critical Reasoning: Complete the Argument",
    prerequisites=["identify what an argument is trying to conclude", "recognize a supporting vs. undermining statement"],
    learning_objectives=[
        "Read the sentence just before the blank to learn what the blank must do.",
        "Follow the connector: 'because/since' needs support; 'but/however' needs a contrast.",
        "Choose the option that logically completes the intended direction of the argument.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Recognizing whether a statement supports or undermines a claim.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "After 'because ___,' what must the blank provide?", "answer": "A reason that supports the preceding claim.", "targets": "because"},
                {"prompt": "After 'the plan will fail, since ___,' what must the blank do?", "answer": "Give a reason the plan will fail.", "targets": "direction"},
                {"prompt": "Does the connector before the blank set the direction?", "answer": "Yes - 'because/since' = support; 'but/yet' = contrast.", "targets": "connectors"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that the word before the blank fixes what the completion must accomplish.",
            "if_students_struggle": "Have them read only the clause containing the blank and predict its job before scanning choices.",
            "questions": [
                {"prompt": "What job does a blank after 'however' do?", "answer": "It contrasts with or limits the prior statement.", "targets": "contrast"},
                {"prompt": "Why read the clause right before the blank first?", "answer": "It tells you exactly what the completion must supply.", "targets": "method"},
            ],
        },
        "prior_knowledge_bridge": "Complete-the-argument items are strengthen/weaken in disguise: the connector before the blank ('because,' 'since,' 'but') tells you whether the missing piece must support or push back, and you pick the option that does exactly that.",
        "learning_intention": "By the end you can use the connector before a blank to choose the option that logically completes the argument in the intended direction.",
        "success_criteria": [
            "I can identify the claim the blank must support or oppose.",
            "I can use 'because/since' vs 'but/however' to set the direction.",
            "I can pick the option that fills the blank in that direction.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        "The town plans to reduce car accidents at a dangerous intersection by adding a traffic light. The plan is likely to succeed, because ___. Which of the following most logically completes the argument?",
        opts(
            "most accidents at that intersection are caused by drivers who are unsure when it is their turn to proceed",
            "the intersection is one of the busiest in the town",
            "traffic lights are expensive to install and maintain",
            "the town has added traffic lights at other intersections before",
            "many drivers in the town exceed the speed limit",
        ),
        "A",
        "'Because' means the blank must give a reason the light will succeed. If accidents stem from confusion over the right of way, a light - which assigns turns - directly fixes that cause. A completes the support.",
        difficulty="medium",
        think_aloud_steps=[
            "Conclusion: the traffic-light plan is likely to succeed.",
            "The connector is 'because,' so the blank must SUPPORT that.",
            "A light resolves right-of-way confusion; if that's the cause, the light works.",
            "A supports the plan; the others are neutral or don't explain success.",
        ],
        key_takeaway="Let the connector before the blank set the direction: 'because/since' needs support, 'but/however' needs a contrast.",
    ),
    we_do=[
        item(
            "we_1",
            "A company believes that offering free coffee will make employees more productive. This belief may be mistaken, however, because ___. Which of the following most logically completes the argument?",
            opts(
                "the main thing slowing employees down is unclear project priorities, which free coffee does nothing to address",
                "coffee is inexpensive to provide in bulk",
                "many employees already drink coffee at home",
                "the office has space for a coffee machine",
                "some employees prefer tea to coffee",
            ),
            "A",
            "'However ... because' signals the blank must give a reason the belief is mistaken. If the real drag is unclear priorities, free coffee won't help - completing the doubt.",
            difficulty="medium",
            scaffold_hints=[
                "The connector 'however' plus 'because' means: give a reason the plan won't work.",
                "What would make free coffee fail to raise productivity?",
                "Pick the choice that names the real obstacle.",
            ],
            immediate_feedback={
                "if_correct": "Right - if priorities are the bottleneck, coffee is beside the point.",
                "if_incorrect": "Cost and preferences don't explain why productivity wouldn't rise.",
            },
        ),
        item(
            "we_2",
            "A bookstore expects that hosting weekly author events will increase book sales. This expectation is probably well founded, because ___. Which of the following most logically completes the argument?",
            opts(
                "at bookstores that host such events, attendees frequently buy the featured author's books on the spot",
                "author events require setting up chairs and a microphone",
                "the bookstore has hosted a few events in the past",
                "the bookstore is open seven days a week",
                "some authors are better public speakers than others",
            ),
            "A",
            "'Because' requires support for the expectation. Evidence that attendees buy books at such events directly supports that the events raise sales.",
            difficulty="medium",
            scaffold_hints=[
                "The connector is 'because' - the blank must support the expectation.",
                "What fact would show events actually drive sales?",
                "Choose the supporting evidence, not logistics.",
            ],
            immediate_feedback={
                "if_correct": "Yes - on-the-spot buying supports the sales expectation.",
                "if_incorrect": "Setup logistics and hours don't show sales will rise.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            "A gym plans to attract more members by opening a swimming pool. The plan is unlikely to work, however, because ___. Which of the following most logically completes the argument?",
            opts(
                "very few people in the area have expressed any interest in swimming, and a large public pool already operates nearby",
                "swimming is good low-impact exercise",
                "the pool will require regular cleaning",
                "the gym already has a large parking lot",
                "the gym is busiest in the evenings",
            ),
            "A",
            "'However ... because' needs a reason the plan will fail. Low local interest plus an existing nearby pool means the new pool won't draw members - completing the doubt.",
            difficulty="medium",
        ),
        item(
            "you_2",
            "A city expects that building a new stadium downtown will revive local businesses. This expectation is probably justified, because ___. Which of the following most logically completes the argument?",
            opts(
                "stadium events are projected to bring large crowds who spend money at nearby restaurants and shops before and after games",
                "the stadium will have a retractable roof",
                "the city has built stadiums in other neighborhoods",
                "construction will take about two years",
                "the stadium will seat tens of thousands of people",
            ),
            "A",
            "'Because' requires support. Crowds spending at nearby businesses is a direct reason local businesses would be revived, completing the argument.",
            difficulty="medium",
        ),
        item(
            "you_3",
            "A manufacturer believes that switching to a cheaper supplier will increase its profit margin. This belief may be unwarranted, however, because ___. Which of the following most logically completes the argument?",
            opts(
                "the cheaper supplier's parts fail more often, and the resulting warranty repairs could cost more than the savings",
                "the cheaper supplier is located in another country",
                "the manufacturer has used several suppliers over the years",
                "the current supplier delivers parts weekly",
                "the manufacturer sells its products online",
            ),
            "A",
            "'However ... because' needs a reason the belief may fail. If higher failure rates drive up warranty costs beyond the savings, the margin may not improve - completing the doubt.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# ===========================================================================
# READING COMPREHENSION (Phase B)
# RC lesson items are self-contained: each carries a short passage inside its
# stem, so the existing lesson player renders them without a schema change. The
# full passage-panel experience lives in the RC practice/diagnostic bank
# (gmatwiz/content/verbal_rc_questions.json).
# ===========================================================================
def rc_topic(**kw):
    kw.setdefault("domain", "Reading Comprehension")
    kw.setdefault("section", "Verbal Reasoning")
    kw.setdefault("question_type", "Reading Comprehension")
    kw.setdefault("estimated_minutes", 18)
    return kw


def _rc_stem(passage: str, question: str) -> str:
    return f"Passage: {passage}\n\nQuestion: {question}"


RC_MAIN_P1 = (
    "The invention of cheap aluminum in the late nineteenth century transformed "
    "industries far beyond the obvious. Once as costly as silver, aluminum became "
    "affordable after a new electrolytic process was devised, and it soon reshaped "
    "packaging, transportation, and construction."
)
RC_MAIN_P2 = (
    "Coral reefs occupy a tiny fraction of the ocean floor, yet they shelter a "
    "quarter of all marine species. Scientists studying reef resilience have found "
    "that reefs exposed to mild, occasional heat stress sometimes withstand later, "
    "severe heat waves better than reefs that had been fully protected."
)

T_rc_main_idea = rc_topic(
    topic_id="gmat::verbal::rc::main_idea",
    slug="rc-main-idea",
    title="Reading Comprehension: Main Idea",
    prerequisites=["read a short passage for its overall point", "tell a main point from a supporting detail"],
    learning_objectives=[
        "State the passage's primary purpose in one sentence before reading the choices.",
        "Choose the option that covers the WHOLE passage, not just one paragraph.",
        "Reject options that are too narrow, too broad, or not discussed.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Summarizing a paragraph in a single sentence.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "What is a passage's 'primary purpose'?", "answer": "The main job the whole passage does (e.g. explain, argue, describe).", "targets": "primary purpose"},
                {"prompt": "Is a detail from one sentence usually the main idea?", "answer": "No - the main idea covers the whole passage.", "targets": "scope"},
                {"prompt": "Why predict the main idea before reading choices?", "answer": "To avoid being pulled by narrow but tempting options.", "targets": "method"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls the difference between a whole-passage point and a single detail.",
            "if_students_struggle": "Have them write a one-line summary of the passage first, then match it to an option.",
            "questions": [
                {"prompt": "A right main-idea answer must cover how much of the passage?", "answer": "All of it (the whole passage), not one part.", "targets": "scope"},
                {"prompt": "Name two wrong-answer traps for main idea.", "answer": "Too narrow (one detail) and too broad / not discussed.", "targets": "traps"},
            ],
        },
        "prior_knowledge_bridge": "You can summarize a paragraph. A main-idea question just scales that up: capture what the ENTIRE passage is doing in one sentence, then pick the choice that matches that sentence - not a true-but-narrow detail.",
        "learning_intention": "By the end you can state a passage's primary purpose and select the option that matches the whole passage.",
        "success_criteria": [
            "I can summarize a passage's overall point in one sentence.",
            "I can reject options that are too narrow or not discussed.",
            "I can pick the option that spans the whole passage.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        _rc_stem(RC_MAIN_P1, "The primary purpose of the passage is to"),
        opts(
            "describe how a technological change had wide-ranging effects",
            "argue that aluminum is more useful than silver",
            "explain the chemistry of the electrolytic process in detail",
            "criticize nineteenth-century packaging methods",
            "predict future uses of aluminum in construction",
        ),
        "A",
        "The passage says cheap aluminum 'reshaped packaging, transportation, and construction' - a wide-ranging effect. A covers the whole passage; the others are narrow or not stated.",
        difficulty="medium",
        think_aloud_steps=[
            "One-line summary: a new process made aluminum cheap, and that changed many industries.",
            "Predict: purpose = show a technological change had broad effects.",
            "Match to A; reject B/C/D/E as narrow or unstated.",
        ],
        key_takeaway="Predict the whole-passage point first, then pick the option that matches it.",
    ),
    we_do=[
        item(
            "we_1",
            _rc_stem(RC_MAIN_P2, "The passage is primarily concerned with"),
            opts(
                "a surprising finding about what helps reefs survive heat",
                "proving that reefs cover very little of the ocean floor",
                "listing the species that live on coral reefs",
                "arguing that reefs should be fully protected from all stress",
                "describing how heat waves form in the ocean",
            ),
            "A",
            "The passage's point is the surprising resilience finding (mild prior stress can help). A matches the whole passage; the others are narrow or contradicted.",
            difficulty="medium",
            scaffold_hints=[
                "What is the passage's most important, whole-passage point?",
                "The reef-area fact is just a setup detail.",
                "Watch for an option that contradicts the finding (full protection).",
            ],
            immediate_feedback={
                "if_correct": "Right - the resilience finding is the main point.",
                "if_incorrect": "The area statistic and species count are supporting details, not the main idea.",
            },
        ),
        item(
            "we_2",
            _rc_stem(RC_MAIN_P1, "Which of the following best expresses the main idea of the passage?"),
            opts(
                "A drop in aluminum's cost led it to affect many industries.",
                "Aluminum was once as expensive as silver.",
                "The electrolytic process is difficult to describe.",
                "Packaging improved more than transportation did.",
                "Construction depends entirely on aluminum.",
            ),
            "A",
            "The whole passage is about cheap aluminum's broad impact. A states that; B is a setup detail, and C/D/E are unstated or overstated.",
            difficulty="easy",
            scaffold_hints=[
                "Pick the sentence that could headline the whole passage.",
                "A single fact (once costly as silver) is too narrow.",
                "Avoid extreme wording (entirely).",
            ],
            immediate_feedback={
                "if_correct": "Yes - broad impact from a cost drop.",
                "if_incorrect": "B is true but narrow; the main idea must span the passage.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            _rc_stem(
                "Before refrigerated railcars, most fresh meat was slaughtered near cities. "
                "Refrigerated cars let packers centralize slaughter in a few large plants and ship "
                "dressed meat long distances, lowering costs but drawing complaints from local butchers.",
                "The primary purpose of the passage is to",
            ),
            opts(
                "explain how a new technology changed an industry and note a reaction to it",
                "argue that local butchers produced better meat",
                "describe the mechanical design of refrigerated railcars",
                "prove that centralized slaughter was a mistake",
                "trace the history of cities near railways",
            ),
            "A",
            "The passage explains the change (refrigerated cars centralized slaughter) and notes a reaction (butchers' complaints). A captures both; the others are narrow or unstated.",
            difficulty="medium",
        ),
        item(
            "you_2",
            _rc_stem(
                "Many assume bird migration is triggered mainly by falling temperature. Studies of caged "
                "birds, however, show that even in constant warmth the birds grow restless at the usual "
                "migration time, suggesting an internal calendar plays a large role.",
                "Which of the following best states the main point of the passage?",
            ),
            opts(
                "An internal timing mechanism, not just temperature, drives migration.",
                "Caged birds behave exactly like wild birds.",
                "Temperature has no effect on birds at all.",
                "Bird migration occurs at the same time every year everywhere.",
                "Studying caged birds is the only way to understand migration.",
            ),
            "A",
            "The study shows restlessness even in constant warmth, pointing to an internal calendar. A states the main point; the others overstate or contradict.",
            difficulty="medium",
        ),
        item(
            "you_3",
            _rc_stem(
                "Public libraries were once quiet halls devoted almost entirely to books. Today many devote "
                "space to computers, meeting rooms, and classes, reflecting a broader idea of the library as "
                "a community hub rather than a mere book repository.",
                "The passage is primarily concerned with",
            ),
            opts(
                "a shift in how libraries are conceived and used",
                "proving that books are no longer important",
                "describing the layout of a specific library",
                "arguing that libraries should ban computers",
                "explaining how meeting rooms are scheduled",
            ),
            "A",
            "The passage contrasts the old book-only library with today's community hub - a shift in conception. A matches; the others are narrow, extreme, or unstated.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


T_rc_inference = rc_topic(
    topic_id="gmat::verbal::rc::inference",
    slug="rc-inference",
    title="Reading Comprehension: Inference",
    prerequisites=["read a passage precisely", "distinguish what is stated from what is implied"],
    learning_objectives=[
        "Choose the option that must be true given the passage - no outside knowledge.",
        "Prefer small, well-supported inferences over large leaps.",
        "Reject options that go beyond, distort, or contradict the passage.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Telling a stated fact from an implied one.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "An RC inference must be what, relative to the passage?", "answer": "Strongly supported / must be true given the text.", "targets": "standard"},
                {"prompt": "May you use outside knowledge on inference questions?", "answer": "No - only the passage.", "targets": "scope"},
                {"prompt": "Are big, dramatic inferences usually right on the GMAT?", "answer": "No - the GMAT rewards small, safe inferences.", "targets": "safe inference"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls the strict 'supported by the passage only' bar for inference.",
            "if_students_struggle": "Have them point to the exact sentence that supports a candidate inference.",
            "questions": [
                {"prompt": "How do you test a candidate inference?", "answer": "Find the passage sentence(s) that force it.", "targets": "support test"},
                {"prompt": "Why reject an inference that needs outside facts?", "answer": "RC inferences must rest on the passage alone.", "targets": "scope"},
            ],
        },
        "prior_knowledge_bridge": "You can tell stated from implied. An inference question asks for the implied claim the passage makes almost inevitable - the smallest safe step beyond the words, supported by a specific sentence, never a leap that needs outside facts.",
        "learning_intention": "By the end you can select the choice the passage most supports and reject leaps beyond it.",
        "success_criteria": [
            "I can point to the sentence that supports my inference.",
            "I can prefer a small, safe inference over a dramatic one.",
            "I can reject options that add outside information.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        _rc_stem(
            "The town's only bridge is closed for repairs until spring. During the closure, the ferry "
            "is the sole way to cross the river, and it does not run after dark.",
            "It can be inferred from the passage that, during the closure,",
        ),
        opts(
            "there is no way to cross the river after dark",
            "the bridge will never reopen",
            "the ferry is faster than the bridge was",
            "most residents rarely need to cross the river",
            "the ferry runs more often than it did before",
        ),
        "A",
        "The ferry is the SOLE crossing and doesn't run after dark, so during the closure there is no after-dark crossing. A is a small, forced inference; the others add facts the passage never gives.",
        difficulty="medium",
        think_aloud_steps=[
            "Facts: ferry is the only crossing; ferry stops after dark.",
            "Combine: after dark, no crossing at all.",
            "A is forced; B/C/D/E need outside information.",
        ],
        key_takeaway="Combine the passage's own statements into the smallest claim they force - nothing extra.",
    ),
    we_do=[
        item(
            "we_1",
            _rc_stem(
                "Every painting in the exhibit was completed after 1950. The museum's oldest painting was "
                "completed in 1600.",
                "The passage most strongly supports which of the following?",
            ),
            opts(
                "The museum's oldest painting is not in the exhibit.",
                "The exhibit contains the museum's most valuable paintings.",
                "Paintings from 1600 are rare.",
                "The exhibit has more paintings than the rest of the museum.",
                "The museum was founded after 1950.",
            ),
            "A",
            "Exhibit paintings are all post-1950; the 1600 painting is pre-1950, so it can't be in the exhibit. A is forced; the rest add unsupported claims.",
            difficulty="medium",
            scaffold_hints=[
                "Compare the dates: exhibit is post-1950; the oldest is 1600.",
                "A pre-1950 painting cannot be in a post-1950 exhibit.",
                "Reject options needing value, rarity, or founding date.",
            ],
            immediate_feedback={
                "if_correct": "Right - the date rule excludes the 1600 painting.",
                "if_incorrect": "Value and rarity aren't in the passage; only dates are.",
            },
        ),
        item(
            "we_2",
            _rc_stem(
                "The clinic accepts walk-in patients only on weekday mornings. On weekday afternoons and all "
                "weekend, patients must have an appointment.",
                "It can be inferred that a patient without an appointment",
            ),
            opts(
                "cannot be seen on a Saturday",
                "will always be seen faster than one with an appointment",
                "prefers mornings to afternoons",
                "is never accepted by the clinic",
                "must pay more than a patient with an appointment",
            ),
            "A",
            "Walk-ins are allowed only weekday mornings; weekends require an appointment, so a walk-in cannot be seen Saturday. A is forced; the others add unsupported facts.",
            difficulty="medium",
            scaffold_hints=[
                "When are walk-ins allowed? Only weekday mornings.",
                "Saturday is a weekend, so an appointment is required.",
                "Avoid options about speed or cost - not stated.",
            ],
            immediate_feedback={
                "if_correct": "Exactly - no walk-ins on weekends.",
                "if_incorrect": "D is too strong (walk-ins ARE accepted weekday mornings).",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            _rc_stem(
                "All of the company's electric vehicles were built at its newest plant. The company's first "
                "plant, built in 1980, produces only gasoline vehicles.",
                "The passage most strongly supports which of the following?",
            ),
            opts(
                "No electric vehicle was built at the 1980 plant.",
                "The newest plant is larger than the 1980 plant.",
                "Gasoline vehicles are cheaper to build.",
                "The company stopped building gasoline vehicles.",
                "The 1980 plant will be closed soon.",
            ),
            "A",
            "Electric vehicles all come from the newest plant, and the 1980 plant makes only gasoline vehicles, so no electric vehicle came from it. A is forced; the rest add facts.",
            difficulty="medium",
        ),
        item(
            "you_2",
            _rc_stem(
                "The festival is held outdoors and is canceled whenever it rains. This year the festival was "
                "held as scheduled.",
                "It can be inferred from the passage that this year",
            ),
            opts(
                "it did not rain on the festival day",
                "the festival was more popular than last year",
                "the weather is usually sunny in the region",
                "the festival will be held indoors next year",
                "more people attended than expected",
            ),
            "A",
            "Rain forces cancellation; the festival was held, so by the contrapositive it did not rain. A is forced; the others are unsupported.",
            difficulty="medium",
        ),
        item(
            "you_3",
            _rc_stem(
                "Researchers noted that a certain frog species is found only in caves that stay near a "
                "constant cool temperature year-round. A newly surveyed cave has temperatures that swing "
                "widely between seasons.",
                "The passage most strongly supports which of the following about the newly surveyed cave?",
            ),
            opts(
                "The frog species is unlikely to be found living there.",
                "The cave is larger than the frogs' usual caves.",
                "The frogs would thrive there if introduced.",
                "The cave has no other animal species.",
                "The temperature swings are caused by the frogs.",
            ),
            "A",
            "The frog needs constant cool temperatures; this cave swings widely, so the frog is unlikely to live there. A is the supported inference; the others add or reverse facts.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


T_rc_function = rc_topic(
    topic_id="gmat::verbal::rc::function",
    slug="rc-function",
    title="Reading Comprehension: Function",
    prerequisites=["identify a passage's main point", "see how a sentence relates to that point"],
    learning_objectives=[
        "Explain WHY the author includes a specific detail (its role), not just what it says.",
        "Common roles: give an example, support a claim, raise an objection, provide contrast.",
        "Reject options that merely restate the detail or misstate its role.",
    ],
    pedagogical_model=PM,
    opening={
        "builds_on": "Seeing how a sentence supports or complicates a main point.",
        "do_now": {
            "instructions": "No notes. 4 minutes.",
            "items": [
                {"prompt": "A function question asks what about a detail?", "answer": "Why the author included it - its role in the passage.", "targets": "role vs content"},
                {"prompt": "Name two common roles a detail can play.", "answer": "Give an example; support (or object to) a claim.", "targets": "role types"},
                {"prompt": "Is restating the detail a correct function answer?", "answer": "No - you must say what job it does.", "targets": "traps"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Recalls that function = the author's reason for including a detail.",
            "if_students_struggle": "Ask 'what would be lost if this sentence were deleted?' to reveal its role.",
            "questions": [
                {"prompt": "How can you reveal a sentence's role?", "answer": "Ask what the passage would lose without it.", "targets": "role test"},
                {"prompt": "Why is 'it repeats the main idea' rarely the role of an example?", "answer": "An example usually supports or illustrates, not repeats.", "targets": "roles"},
            ],
        },
        "prior_knowledge_bridge": "You can see how a sentence relates to the main point. A function question makes that explicit: name the JOB a detail does - example, support, objection, contrast - rather than repeating what it says.",
        "learning_intention": "By the end you can state the role a specific detail plays in a passage and match it to the right option.",
        "success_criteria": [
            "I can say why the author included a detail, not just what it says.",
            "I can name the role (example, support, objection, contrast).",
            "I can reject options that restate the detail or misname its role.",
        ],
        "opening_script": cr_script(),
    },
    i_do=item(
        "i_do",
        _rc_stem(
            "Some claim that working from home lowers productivity. Yet at one large firm, output per "
            "employee rose after a shift to remote work - evidence that the claim is not universally true.",
            "The author mentions the large firm's rising output primarily in order to",
        ),
        opts(
            "provide evidence against the claim that remote work lowers productivity",
            "prove that all firms should adopt remote work",
            "describe how the firm measures output",
            "introduce a new claim about employee morale",
            "explain why some people work from home",
        ),
        "A",
        "The firm's rising output is offered right after the claim, as counter-evidence ('evidence that the claim is not universally true'). Its role is to rebut the claim. A names that role.",
        difficulty="medium",
        think_aloud_steps=[
            "Main point: the 'remote lowers productivity' claim isn't universally true.",
            "The firm's rising output is the evidence for that point.",
            "So its role is to counter the claim - choice A.",
        ],
        key_takeaway="Name the JOB a detail does for the argument, not what it literally says.",
    ),
    we_do=[
        item(
            "we_1",
            _rc_stem(
                "Vitamin supplements are widely believed to prevent colds. In a large trial, however, people "
                "taking the supplement caught colds just as often as those taking a placebo.",
                "The author mentions the trial primarily in order to",
            ),
            opts(
                "challenge the belief that supplements prevent colds",
                "recommend a specific brand of supplement",
                "explain how placebos are manufactured",
                "prove that colds are impossible to prevent",
                "describe the symptoms of the common cold",
            ),
            "A",
            "The trial's result (no difference from placebo) is introduced with 'however' to push back on the belief. Its role is to challenge that belief. A matches.",
            difficulty="medium",
            scaffold_hints=[
                "What belief is stated first?",
                "The trial is introduced with 'however' - a contrast signal.",
                "So the trial's job is to counter the belief.",
            ],
            immediate_feedback={
                "if_correct": "Right - the trial challenges the belief.",
                "if_incorrect": "D is too strong; the trial challenges ONE belief, not all prevention.",
            },
        ),
        item(
            "we_2",
            _rc_stem(
                "The new policy has clear benefits. It will, for instance, cut commute times for thousands of "
                "workers who currently drive across town each day.",
                "The reference to cutting commute times functions primarily to",
            ),
            opts(
                "give a specific example of the policy's benefits",
                "raise an objection to the policy",
                "prove the policy has no drawbacks",
                "define what a commute is",
                "compare the policy to an older one",
            ),
            "A",
            "'For instance' marks the commute detail as an example illustrating the stated benefits. A names that role; the others misstate it.",
            difficulty="easy",
            scaffold_hints=[
                "The signal 'for instance' tells you the role.",
                "It illustrates the 'clear benefits' claim.",
                "That's an example, not an objection.",
            ],
            immediate_feedback={
                "if_correct": "Yes - it's an illustrative example.",
                "if_incorrect": "'For instance' signals an example, not an objection or proof of no drawbacks.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1",
            _rc_stem(
                "Critics say the museum's new wing clashes with the old building. Supporters counter that the "
                "contrast draws visitors in - attendance has risen 30 percent since the wing opened.",
                "The author mentions the 30 percent rise in attendance primarily in order to",
            ),
            opts(
                "support the supporters' response to the critics",
                "concede that the critics are correct",
                "explain how attendance is counted",
                "argue that the old building should be demolished",
                "describe the design of the new wing",
            ),
            "A",
            "The attendance rise backs the supporters' counter to the critics. Its role is to support that response. A matches; the others misname it.",
            difficulty="medium",
        ),
        item(
            "you_2",
            _rc_stem(
                "The device is marketed as waterproof. In testing, however, it failed after ten minutes in "
                "shallow water, casting doubt on that description.",
                "The author refers to the testing result primarily in order to",
            ),
            opts(
                "cast doubt on the device's waterproof marketing",
                "explain how the device is manufactured",
                "recommend the device to consumers",
                "prove that no device can be waterproof",
                "describe the price of the device",
            ),
            "A",
            "The failed test is introduced with 'however' to undercut the waterproof claim. Its role is to cast doubt on that marketing. A matches.",
            difficulty="medium",
        ),
        item(
            "you_3",
            _rc_stem(
                "Many cities have tried to reduce littering with fines, but enforcement is costly. One city "
                "instead added colorful, conveniently placed bins and saw litter drop sharply, suggesting "
                "that design can sometimes succeed where penalties struggle.",
                "The author mentions the city that added bins primarily in order to",
            ),
            opts(
                "offer an example of an alternative to fines that worked",
                "argue that fines should be increased",
                "explain how litter is measured",
                "prove that fines never reduce littering",
                "describe the color of the new bins",
            ),
            "A",
            "The bin city illustrates an alternative to fines that succeeded, supporting the point that design can work where penalties struggle. A names that role; the others misstate or overstate.",
            difficulty="hard",
        ),
    ],
    mastery_check={},
    citations=CR_CITES,
)


# Order mirrors the taxonomy leaves (CR first, then the Phase B RC leaves).
TOPICS = [
    T_assumption,
    T_strengthen,
    T_weaken,
    T_evaluate,
    T_inference,
    T_paradox,
    T_flaw,
    T_boldface,
    T_complete,
    T_rc_main_idea,
    T_rc_inference,
    T_rc_function,
]
