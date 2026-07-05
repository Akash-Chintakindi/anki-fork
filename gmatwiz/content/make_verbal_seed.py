#!/usr/bin/env python3
"""Author the GMATWiz VERBAL (Critical Reasoning) question sets.

These are ORIGINAL GMAT Critical Reasoning questions written for GMATWiz,
spanning the PRD Section 5 Verbal coverage map (Critical Reasoning; Reading
Comprehension ships in Phase B). GMAT Focus Verbal = CR + RC only (NO Sentence
Correction).

Nothing here is copied from any prep book: the questions are original arguments
on neutral topics. The books provided by the user were used only to confirm the
standard CR question-type taxonomy (assumption / strengthen / weaken / evaluate
/ inference / paradox / flaw / boldface / complete-the-argument), never as a
source of text.

Two files are emitted next to this script:
  * verbal_seed.json      -- gold-labeled set (doubles as the eval gold set)
  * verbal_questions.json -- additional authored bank items

Both are imported into the collection (like seed.json + questions.json for
Quant). License for all items: ``authored-gmatwiz``.

Run:  python3 make_verbal_seed.py
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
    return f"{V}::cr::{leaf}"


# ---------------------------------------------------------------------------
# GOLD SEED SET (3 per leaf). Human-assigned leaf labels; used by eval_tagging.
# ---------------------------------------------------------------------------
SEED: List[Dict] = [
    # ============================ assumption ============================
    {
        "topic": _t("assumption"), "difficulty": "medium",
        "stem": "A city council plans to reduce downtown traffic congestion by converting "
                "one busy street into a pedestrian-only zone. Officials predict this will cut "
                "the number of cars entering downtown. The plan's success depends on which of "
                "the following assumptions?",
        "options": {
            "A": "Drivers who now use that street will not simply divert onto other downtown streets.",
            "B": "The pedestrian zone will attract more shoppers to the downtown area.",
            "C": "Most downtown workers commute by car rather than by public transit.",
            "D": "The street being converted is the busiest street in the downtown area.",
            "E": "Pedestrian zones have reduced congestion in several other cities.",
        },
        "correct": "A",
        "explanation": "To cut cars entering downtown, the displaced drivers must not just reroute "
                       "onto nearby streets; if they do, total downtown traffic is unchanged. A is "
                       "the assumption the plan requires.",
    },
    {
        "topic": _t("assumption"), "difficulty": "medium",
        "stem": "TechCorp expects to boost annual profit by replacing its phone-based customer "
                "support with an automated chatbot, since the chatbot costs far less to operate "
                "than a call center. The argument assumes that",
        "options": {
            "A": "switching to the chatbot will not cause enough customers to leave to offset the cost savings.",
            "B": "the chatbot will be able to answer every possible customer question.",
            "C": "competitors have not already adopted similar chatbots.",
            "D": "the displaced call-center employees can be retrained for other roles.",
            "E": "customers generally prefer chatbots to speaking with a person.",
        },
        "correct": "A",
        "explanation": "Profit is revenue minus cost. Lower cost raises profit only if revenue does "
                       "not fall by more than the savings; the argument assumes customer losses will "
                       "not wipe out the cost reduction.",
    },
    {
        "topic": _t("assumption"), "difficulty": "hard",
        "stem": "A researcher concludes that a new fertilizer increases crop yield, because fields "
                "treated with it produced 15 percent more wheat last season than untreated fields. "
                "This conclusion depends on the assumption that",
        "options": {
            "A": "the treated and untreated fields did not differ in other factors, such as rainfall or soil quality, that affect yield.",
            "B": "the fertilizer is affordable for most wheat farmers.",
            "C": "wheat is the most widely grown crop in the region.",
            "D": "the 15 percent increase will recur in future seasons.",
            "E": "no other fertilizer could have produced a larger increase.",
        },
        "correct": "A",
        "explanation": "To credit the fertilizer for the higher yield, the treated and untreated "
                       "fields must be otherwise comparable; if they differed in rainfall or soil, "
                       "that could explain the gap instead.",
    },
    # ============================ strengthen ============================
    {
        "topic": _t("strengthen"), "difficulty": "medium",
        "stem": "A company found that employees who work from home two days a week are more "
                "productive than those who work in the office every day, and concludes that "
                "allowing remote work causes higher productivity. Which of the following, if true, "
                "most strengthens this conclusion?",
        "options": {
            "A": "When a separate group of office-only employees was later allowed two remote days a week, their productivity rose.",
            "B": "Remote employees report higher job satisfaction than office employees.",
            "C": "The company saves money on office space when employees work remotely.",
            "D": "Most employees say they would prefer to work from home.",
            "E": "Productivity was measured by the number of tasks completed.",
        },
        "correct": "A",
        "explanation": "A follow-up in which the same office-only group became more productive after "
                       "gaining remote days supports causation, rather than remote workers simply "
                       "being more productive to begin with.",
    },
    {
        "topic": _t("strengthen"), "difficulty": "medium",
        "stem": "Nutritionists claim that eating a daily handful of almonds lowers cholesterol, "
                "noting that people who eat almonds daily tend to have lower cholesterol than those "
                "who do not. Which of the following, if true, would most strengthen the claim?",
        "options": {
            "A": "In a trial, participants randomly assigned to eat almonds daily had lower cholesterol after three months than those assigned no almonds.",
            "B": "Almonds are a good source of protein and dietary fiber.",
            "C": "People who eat almonds daily also tend to exercise regularly.",
            "D": "Cholesterol levels are known to vary with age and genetics.",
            "E": "Almond consumption has increased over the past decade.",
        },
        "correct": "A",
        "explanation": "A randomized trial isolates almond consumption from confounders such as "
                       "exercise, directly supporting that almonds themselves lower cholesterol.",
    },
    {
        "topic": _t("strengthen"), "difficulty": "medium",
        "stem": "A bookstore added a café, and its book sales rose the following month. The owner "
                "concludes that the café caused the increase in book sales. Which of the following, "
                "if true, most strengthens the owner's conclusion?",
        "options": {
            "A": "Customers who bought coffee at the café browsed longer and bought more books than customers who did not.",
            "B": "The café turned a profit in its first month of operation.",
            "C": "Book sales at a competing store nearby fell during the same month.",
            "D": "The café serves pastries in addition to coffee.",
            "E": "The owner had wanted to open a café for many years.",
        },
        "correct": "A",
        "explanation": "Linking café use to longer browsing and more book purchases supplies a "
                       "mechanism connecting the café to higher book sales, supporting causation.",
    },
    # ============================ weaken ============================
    {
        "topic": _t("weaken"), "difficulty": "medium",
        "stem": "A town installed speed cameras on Main Street, and the number of speeding tickets "
                "issued there fell by 60 percent over the next year. The town concludes that drivers "
                "on Main Street now speed far less often. Which of the following, if true, most "
                "seriously weakens this conclusion?",
        "options": {
            "A": "Soon after installation, most of the cameras were disabled for repairs and issued no tickets for the rest of the year.",
            "B": "Speeding fines were increased at the same time the cameras were installed.",
            "C": "Main Street carries more traffic than any other street in the town.",
            "D": "Some drivers memorized the camera locations and slowed only when near them.",
            "E": "The town plans to install cameras on additional streets next year.",
        },
        "correct": "A",
        "explanation": "If the cameras were disabled and stopped issuing tickets, the drop in tickets "
                       "reflects the cameras' inactivity, not reduced speeding, undermining the "
                       "conclusion.",
    },
    {
        "topic": _t("weaken"), "difficulty": "medium",
        "stem": "A restaurant switched to cheaper ingredients, and its monthly profit rose. The owner "
                "concludes that the cheaper ingredients caused the higher profit. Which of the "
                "following, if true, most weakens the owner's conclusion?",
        "options": {
            "A": "That same month, a popular restaurant next door closed, sending many of its customers to the owner's restaurant.",
            "B": "The cheaper ingredients are sourced from a nearby farm.",
            "C": "The restaurant kept its menu prices unchanged.",
            "D": "Customers did not notice the change in ingredients.",
            "E": "The owner has run the restaurant for ten years.",
        },
        "correct": "A",
        "explanation": "A surge of customers from the closed competitor is an alternative cause for "
                       "the profit increase, weakening the claim that cheaper ingredients were "
                       "responsible.",
    },
    {
        "topic": _t("weaken"), "difficulty": "hard",
        "stem": "A health official argues that a new vaccination campaign reduced flu cases, because "
                "flu cases in the city dropped 30 percent after the campaign. Which of the following, "
                "if true, most undermines the official's argument?",
        "options": {
            "A": "The flu season that followed the campaign was unusually mild nationwide, including in areas that ran no campaign.",
            "B": "The vaccine used was the same formulation as in previous years.",
            "C": "The campaign was advertised heavily on local television.",
            "D": "Not every resident of the city received the vaccine.",
            "E": "Flu cases are tallied by hospitals and clinics.",
        },
        "correct": "A",
        "explanation": "A nationwide mild flu season, affecting places without any campaign, suggests "
                       "the drop would have occurred anyway, weakening the causal claim.",
    },
    # ============================ evaluate ============================
    {
        "topic": _t("evaluate"), "difficulty": "medium",
        "stem": "A delivery company argues that replacing its gasoline vans with electric vans will "
                "lower total operating costs. The answer to which of the following would be most "
                "useful in evaluating this argument?",
        "options": {
            "A": "Whether the higher purchase price of electric vans is outweighed by their lower fuel and maintenance costs over the vans' lifetime.",
            "B": "Whether electric vans are quieter than gasoline vans.",
            "C": "Whether the company's drivers would prefer electric vans.",
            "D": "Whether the company's main competitors have switched to electric vans.",
            "E": "Whether the electric vans are manufactured domestically.",
        },
        "correct": "A",
        "explanation": "Total operating cost depends on whether lifetime fuel and maintenance savings "
                       "exceed the higher upfront price; knowing this is essential to evaluate the "
                       "cost claim.",
    },
    {
        "topic": _t("evaluate"), "difficulty": "medium",
        "stem": "A publisher plans to stop printing physical books and sell only e-books in order to "
                "increase its profit margins. Which of the following would be most useful to know in "
                "order to evaluate the plan?",
        "options": {
            "A": "What proportion of the publisher's current buyers would purchase e-books rather than switch to print competitors.",
            "B": "Whether e-books can include the same illustrations as print books.",
            "C": "How long it takes to convert a printed book into an e-book.",
            "D": "Whether the publisher's authors write mainly fiction or nonfiction.",
            "E": "Whether e-book reading devices are becoming cheaper.",
        },
        "correct": "A",
        "explanation": "Higher margins per e-book help profit only if enough print buyers convert "
                       "rather than leaving; that proportion is key to evaluating the plan.",
    },
    {
        "topic": _t("evaluate"), "difficulty": "medium",
        "stem": "A hospital plans to reduce emergency-room wait times by adding a second triage nurse. "
                "Which of the following would be most useful to know in evaluating whether the plan "
                "will succeed?",
        "options": {
            "A": "Whether triage, rather than a later step such as bed availability, is the main bottleneck causing the wait times.",
            "B": "Whether the second nurse would work the day shift or the night shift.",
            "C": "How much the hospital currently pays its triage nurses.",
            "D": "Whether patients are satisfied with the current triage process.",
            "E": "How many entrances the emergency room has.",
        },
        "correct": "A",
        "explanation": "Adding a triage nurse helps only if triage is the true bottleneck; if beds "
                       "are the constraint, wait times will not fall, so identifying the bottleneck "
                       "is decisive.",
    },
    # ============================ inference ============================
    {
        "topic": _t("inference"), "difficulty": "medium",
        "stem": "Every employee in the marketing department speaks at least two languages. No employee "
                "who speaks at least two languages is required to attend the weekly translation "
                "workshop. If the statements above are true, which of the following must also be true?",
        "options": {
            "A": "No employee in the marketing department is required to attend the weekly translation workshop.",
            "B": "Every employee who attends the workshop speaks only one language.",
            "C": "Some marketing employees speak exactly two languages.",
            "D": "Employees outside the marketing department speak only one language.",
            "E": "The workshop is intended primarily for newly hired employees.",
        },
        "correct": "A",
        "explanation": "Marketing employees all speak at least two languages, and no one who does is "
                       "required to attend; therefore no marketing employee is required to attend. A "
                       "follows necessarily.",
    },
    {
        "topic": _t("inference"), "difficulty": "medium",
        "stem": "The community center is open only on days when at least three volunteers are available. "
                "On Mondays, only two volunteers are ever available. Which of the following can be "
                "properly concluded from these statements?",
        "options": {
            "A": "The community center is not open on Mondays.",
            "B": "The community center is open every day except Monday.",
            "C": "More volunteers are available on weekends than on weekdays.",
            "D": "The center would open on Mondays if it paid its volunteers.",
            "E": "Volunteers generally prefer not to work on Mondays.",
        },
        "correct": "A",
        "explanation": "Opening requires at least three volunteers; Mondays never have more than two; "
                       "so the center cannot be open on Mondays. A must be true, while the others go "
                       "beyond the premises.",
    },
    {
        "topic": _t("inference"), "difficulty": "hard",
        "stem": "All members of the hiking club have completed a first-aid course. Anyone who has "
                "completed a first-aid course is permitted to lead a group hike. Which of the following "
                "must be true on the basis of the statements above?",
        "options": {
            "A": "Every member of the hiking club is permitted to lead a group hike.",
            "B": "Only hiking club members are permitted to lead a group hike.",
            "C": "Some group hikes are led by people without first-aid training.",
            "D": "Completing a first-aid course requires joining the hiking club.",
            "E": "All people who lead group hikes are members of the hiking club.",
        },
        "correct": "A",
        "explanation": "Club members have all completed first aid, and anyone with first aid may lead "
                       "hikes; so every member may lead hikes. A follows; the other options reverse or "
                       "overextend the conditionals.",
    },
    # ============================ explain_paradox ============================
    {
        "topic": _t("explain_paradox"), "difficulty": "medium",
        "stem": "A supermarket lowered the price of its store-brand cereal, expecting to sell more "
                "boxes than before. Instead, it sold fewer boxes of the store-brand cereal than it had "
                "at the higher price. Which of the following, if true, most helps to explain this "
                "surprising result?",
        "options": {
            "A": "Shoppers took the lower price as a sign of lower quality and switched to more expensive name brands.",
            "B": "The store-brand cereal is displayed on a low shelf.",
            "C": "Cereal prices rose at competing supermarkets.",
            "D": "The store-brand cereal is available in several flavors.",
            "E": "The supermarket advertised the price cut in its weekly flyer.",
        },
        "correct": "A",
        "explanation": "If shoppers read the lower price as lower quality and traded up to name "
                       "brands, that explains why cutting the price reduced store-brand sales.",
    },
    {
        "topic": _t("explain_paradox"), "difficulty": "medium",
        "stem": "After a company doubled the size of its customer-service team, the average time "
                "customers spent waiting on hold actually increased. Which of the following, if true, "
                "best resolves this apparent paradox?",
        "options": {
            "A": "News that the company had improved its support prompted far more customers than before to call in.",
            "B": "The newly hired agents were paid the same as the existing agents.",
            "C": "The company's product line did not change during this period.",
            "D": "Some customers prefer to contact the company by email.",
            "E": "The customer-service team works together in a single office.",
        },
        "correct": "A",
        "explanation": "A surge in call volume that outpaced even the larger team would raise hold "
                       "times despite the added agents, resolving the paradox.",
    },
    {
        "topic": _t("explain_paradox"), "difficulty": "hard",
        "stem": "A city widened a congested highway to speed up traffic, but a year later average "
                "commute times on that highway were longer than before. Which of the following, if "
                "true, most helps to explain this surprising finding?",
        "options": {
            "A": "The wider highway drew many drivers who had previously taken other routes or public transit, raising the total number of cars on it.",
            "B": "The construction work was completed ahead of schedule.",
            "C": "The highway runs through the center of the city.",
            "D": "Fuel prices fell slightly over the course of the year.",
            "E": "The widening added one lane in each direction.",
        },
        "correct": "A",
        "explanation": "Induced demand, in which the improved highway attracts new drivers, can raise "
                       "congestion, explaining why commute times grew despite the extra lanes.",
    },
    # ============================ flaw ============================
    {
        "topic": _t("flaw"), "difficulty": "medium",
        "stem": "Columnist: The mayor claims that her policies reduced unemployment. But the mayor is "
                "wealthy and has never been unemployed herself, so her claim should be dismissed. The "
                "columnist's reasoning is most vulnerable to the criticism that it",
        "options": {
            "A": "attacks the mayor's personal circumstances instead of addressing the substance of her claim.",
            "B": "relies on a sample that is too small to be representative.",
            "C": "confuses a cause with an effect.",
            "D": "assumes the very point it is trying to prove.",
            "E": "draws a general conclusion from a single exceptional case.",
        },
        "correct": "A",
        "explanation": "The columnist dismisses the claim by pointing to the mayor's wealth and "
                       "personal history, an ad hominem, rather than addressing whether the policies "
                       "actually reduced unemployment.",
    },
    {
        "topic": _t("flaw"), "difficulty": "medium",
        "stem": "Advertisement: Our toothpaste is the best on the market, because it is the "
                "best-selling toothpaste in the country. The reasoning in the advertisement is flawed "
                "because it",
        "options": {
            "A": "takes the fact that many people buy the product as proof that the product is superior in quality.",
            "B": "fails to specify what counts as toothpaste.",
            "C": "relies on the opinion of a single dentist.",
            "D": "assumes the product will remain popular in the future.",
            "E": "overlooks the prices of competing toothpastes.",
        },
        "correct": "A",
        "explanation": "Being best-selling (most bought) is treated as if it establishes being best "
                       "(highest quality), but widespread purchase does not by itself prove "
                       "superiority.",
    },
    {
        "topic": _t("flaw"), "difficulty": "medium",
        "stem": "Manager: Since we began playing music in the store, sales have increased. Therefore "
                "the music is causing customers to buy more. The manager's argument is most vulnerable "
                "to criticism because it",
        "options": {
            "A": "concludes that the music caused the increase merely because the increase followed the music.",
            "B": "depends on the testimony of only a few customers.",
            "C": "assumes that all customers dislike silence.",
            "D": "relies on an ambiguous definition of the word 'sales.'",
            "E": "ignores the cost of installing the sound system.",
        },
        "correct": "A",
        "explanation": "The argument infers causation from mere sequence: sales rising after the "
                       "music began does not establish that the music caused the rise.",
    },
    # ============================ boldface ============================
    {
        "topic": _t("boldface"), "difficulty": "hard",
        "stem": "Economist: <b>Raising the minimum wage will increase the earnings of low-wage "
                "workers.</b> Some argue that it will also lead employers to cut jobs. However, "
                "<b>studies of recent minimum-wage increases have found no significant loss of "
                "employment.</b> In the economist's argument, the two portions in boldface play which "
                "of the following roles?",
        "options": {
            "A": "The first is the conclusion the economist defends; the second is evidence offered against an objection to that conclusion.",
            "B": "The first is an objection the economist rejects; the second is the economist's conclusion.",
            "C": "Both portions are objections that the economist seeks to refute.",
            "D": "The first is evidence for the conclusion; the second is the conclusion itself.",
            "E": "The first states the conclusion; the second states an assumption the conclusion relies on.",
        },
        "correct": "A",
        "explanation": "The first bold portion is the economist's main claim (the conclusion); the "
                       "second is evidence rebutting the objection that jobs would be lost.",
    },
    {
        "topic": _t("boldface"), "difficulty": "hard",
        "stem": "Critic: The film studio believes that <b>releasing its movies directly to streaming "
                "will maximize its profits.</b> But <b>theatrical releases still generate far more "
                "revenue per film than streaming does.</b> The studio's plan is therefore misguided. "
                "In the critic's argument, the two boldfaced portions play which of the following "
                "roles?",
        "options": {
            "A": "The first is the position the critic argues against; the second is evidence the critic uses to argue against it.",
            "B": "The first is the critic's conclusion; the second is an assumption supporting it.",
            "C": "Both portions are evidence for the critic's conclusion.",
            "D": "The first is evidence; the second is the critic's conclusion.",
            "E": "The first is the critic's conclusion; the second is an objection to it.",
        },
        "correct": "A",
        "explanation": "The first bold portion is the studio's position, which the critic opposes; the "
                       "second is the critic's evidence against it (higher theatrical revenue).",
    },
    {
        "topic": _t("boldface"), "difficulty": "hard",
        "stem": "Analyst: <b>Our company should expand into the overseas market next year.</b> "
                "Expansion carries risk, but <b>our two largest competitors have already captured most "
                "of the domestic market,</b> leaving us little room to grow at home. In the analyst's "
                "argument, the two boldfaced portions play which of the following roles?",
        "options": {
            "A": "The first is the recommendation the analyst makes; the second is a consideration offered in support of that recommendation.",
            "B": "The first is a consideration against the recommendation; the second is the recommendation.",
            "C": "Both portions support a conclusion the analyst ultimately rejects.",
            "D": "The first is evidence; the second is the analyst's main conclusion.",
            "E": "The first is the analyst's conclusion; the second is an objection the analyst concedes.",
        },
        "correct": "A",
        "explanation": "The first bold portion is the analyst's recommendation (conclusion); the "
                       "second is a supporting reason (limited domestic growth) for it.",
    },
    # ============================ complete_argument ============================
    {
        "topic": _t("complete_argument"), "difficulty": "medium",
        "stem": "The city plans to reduce downtown air pollution by encouraging residents to bicycle "
                "instead of drive. This plan is unlikely to succeed, however, because ___. Which of "
                "the following most logically completes the argument?",
        "options": {
            "A": "the downtown area has no bike lanes, and most residents consider cycling there too dangerous to attempt",
            "B": "cycling provides good exercise for residents of all ages",
            "C": "downtown air pollution has decreased slightly over the past decade",
            "D": "several other cities have successfully promoted cycling",
            "E": "the city already operates an extensive network of buses",
        },
        "correct": "A",
        "explanation": "For the plan to fail, something must keep residents from cycling; the absence "
                       "of safe bike lanes deterring them completes the argument.",
    },
    {
        "topic": _t("complete_argument"), "difficulty": "medium",
        "stem": "A bakery found that customers who taste a free sample of a new pastry are much more "
                "likely to buy it, and concludes that offering free samples of all its pastries will "
                "increase overall sales. This conclusion may be unwarranted, since ___. Which of the "
                "following most logically completes the argument?",
        "options": {
            "A": "customers who fill up on free samples may end up buying fewer pastries overall than they otherwise would have",
            "B": "the new pastry is more expensive than the bakery's other items",
            "C": "the bakery has offered free samples on holidays in the past",
            "D": "free samples are a common marketing tactic among bakeries",
            "E": "the bakery's customers tend to visit in the morning",
        },
        "correct": "A",
        "explanation": "The conclusion is undercut if free samples reduce total purchases (customers "
                       "fill up), which is a reason the sales boost might not materialize.",
    },
    {
        "topic": _t("complete_argument"), "difficulty": "hard",
        "stem": "Manufacturers of a popular soda plan to switch to a cheaper sweetener to cut costs, "
                "confident that sales will not suffer. Their confidence appears justified, because "
                "___. Which of the following most logically completes the argument?",
        "options": {
            "A": "in blind taste tests, consumers could not distinguish the new formula from the original",
            "B": "the new sweetener is produced by a different supplier",
            "C": "the soda is sold in more than fifty countries",
            "D": "the company has changed its packaging several times before",
            "E": "artificial sweeteners are used in many diet drinks",
        },
        "correct": "A",
        "explanation": "If consumers cannot tell the new formula from the old, sales are unlikely to "
                       "suffer, supporting the manufacturers' confidence.",
    },
]


# ---------------------------------------------------------------------------
# ADDITIONAL BANK SET (3 per leaf). Shipped for practice depth; not gold.
# ---------------------------------------------------------------------------
BANK: List[Dict] = [
    # ============================ assumption ============================
    {
        "topic": _t("assumption"), "difficulty": "medium",
        "stem": "A publisher decided to release its bestselling novel as an audiobook, reasoning that "
                "doing so will increase the book's total sales. This reasoning assumes that",
        "options": {
            "A": "people who buy the audiobook would not otherwise have bought the print or e-book version.",
            "B": "the novel is well suited to the audiobook format.",
            "C": "the narrator hired is a well-known performer.",
            "D": "audiobooks are more profitable per unit than print books.",
            "E": "the novel's author approves of the audiobook edition.",
        },
        "correct": "A",
        "explanation": "Total sales rise only if audiobook buyers are additional customers, not people "
                       "substituting the audiobook for a copy they would have bought anyway.",
    },
    {
        "topic": _t("assumption"), "difficulty": "medium",
        "stem": "The mayor argues that installing more streetlights will reduce nighttime crime in the "
                "park, citing studies that link brighter lighting to lower crime. The argument "
                "presupposes that",
        "options": {
            "A": "the crime examined in those studies is similar in kind to the crime occurring in the park.",
            "B": "the park has more nighttime crime than any other location in the city.",
            "C": "streetlights are the cheapest available way to reduce crime.",
            "D": "residents have requested additional lighting for the park.",
            "E": "the park is used mainly during the night.",
        },
        "correct": "A",
        "explanation": "Applying the studies' finding to the park assumes the park's crime resembles "
                       "the crime those studies examined; otherwise the link may not transfer.",
    },
    {
        "topic": _t("assumption"), "difficulty": "medium",
        "stem": "A gym owner plans to raise monthly membership fees, expecting total membership "
                "revenue to increase as a result. This plan assumes that",
        "options": {
            "A": "the higher fee will not drive away so many members that revenue falls.",
            "B": "current members are satisfied with the gym's facilities.",
            "C": "no competing gym will lower its fees in response.",
            "D": "the gym is currently operating at full capacity.",
            "E": "new equipment will be purchased with the added revenue.",
        },
        "correct": "A",
        "explanation": "Revenue is price times members. Raising the price increases revenue only if the "
                       "drop in membership is small enough not to offset the higher fee.",
    },
    # ============================ strengthen ============================
    {
        "topic": _t("strengthen"), "difficulty": "medium",
        "stem": "A school district introduced free breakfast, and test scores improved that year. "
                "Administrators conclude the breakfast program raised the scores. Which of the "
                "following, if true, most strengthens this conclusion?",
        "options": {
            "A": "Students who ate the free breakfast improved more than students at the same schools who did not eat it.",
            "B": "The breakfast program was popular with parents.",
            "C": "The district also hired several new teachers that year.",
            "D": "The district lengthened the school day the same year.",
            "E": "The breakfasts met federal nutrition guidelines.",
        },
        "correct": "A",
        "explanation": "Comparing eaters with non-eaters within the same schools ties the score gain "
                       "specifically to the breakfast, ruling out school-wide factors.",
    },
    {
        "topic": _t("strengthen"), "difficulty": "medium",
        "stem": "An airline believes that adding legroom to economy seats will increase ticket sales "
                "enough to offset the loss of seats per plane. Which of the following, if true, most "
                "supports the airline's belief?",
        "options": {
            "A": "Surveys show that many travelers would pay more and switch airlines specifically for extra legroom.",
            "B": "The airline's planes are near the end of their service life.",
            "C": "Adding legroom requires removing two rows of seats per plane.",
            "D": "Competing airlines have not changed their seat configurations.",
            "E": "Fuel costs have declined recently.",
        },
        "correct": "A",
        "explanation": "Evidence that many travelers would switch and pay more for legroom directly "
                       "supports that added sales will offset the fewer seats.",
    },
    {
        "topic": _t("strengthen"), "difficulty": "medium",
        "stem": "A charity claims that its job-training program is the reason its graduates find work "
                "quickly. Which of the following, if true, most strengthens the claim?",
        "options": {
            "A": "Applicants admitted to the program find jobs faster than equally qualified applicants who were turned away only for lack of space.",
            "B": "The program has trained thousands of people since it began.",
            "C": "Graduates frequently express gratitude for the program.",
            "D": "The program is funded entirely by private donations.",
            "E": "Most graduates find work in the same industry.",
        },
        "correct": "A",
        "explanation": "Comparing admitted applicants with equally qualified rejected ones controls "
                       "for applicant quality, isolating the program's effect on job-finding speed.",
    },
    # ============================ weaken ============================
    {
        "topic": _t("weaken"), "difficulty": "medium",
        "stem": "A manager claims that a new bonus scheme caused her sales team to sell more, since "
                "sales rose after the scheme began. Which of the following, if true, most weakens the "
                "claim?",
        "options": {
            "A": "The company launched a major advertising campaign the same week the bonus scheme began.",
            "B": "The bonus scheme rewards the top three salespeople each month.",
            "C": "Some team members preferred the old commission structure.",
            "D": "Sales are recorded automatically by the point-of-sale system.",
            "E": "The manager has led the team for two years.",
        },
        "correct": "A",
        "explanation": "A simultaneous advertising campaign is an alternative explanation for the "
                       "sales increase, weakening the claim that the bonus scheme was the cause.",
    },
    {
        "topic": _t("weaken"), "difficulty": "medium",
        "stem": "A blogger asserts that reading before bed improves sleep, citing a survey in which "
                "people who read before bed reported sleeping better than those who did not. Which of "
                "the following, if true, most seriously weakens the assertion?",
        "options": {
            "A": "People who read before bed also tend to avoid screens at night, which independently improves sleep.",
            "B": "The survey included several thousand respondents.",
            "C": "Some respondents read on paper and others on e-readers.",
            "D": "The blogger reads before bed every night.",
            "E": "The survey was conducted entirely online.",
        },
        "correct": "A",
        "explanation": "If readers also avoid screens, a known sleep aid, then screen avoidance rather "
                       "than reading may explain the better sleep, weakening the claim.",
    },
    {
        "topic": _t("weaken"), "difficulty": "medium",
        "stem": "A city claims its new recycling program cut landfill waste, noting that landfill "
                "waste fell after the program launched. Which of the following, if true, most weakens "
                "the claim?",
        "options": {
            "A": "A large factory that had sent most of the city's landfill waste shut down the same month the program launched.",
            "B": "The recycling program accepts glass, paper, and plastic.",
            "C": "Participation in the program was voluntary.",
            "D": "The city advertised the program widely.",
            "E": "Landfill fees were unchanged during the period.",
        },
        "correct": "A",
        "explanation": "The factory's closure independently removed most landfill waste, providing an "
                       "alternative cause for the decline and weakening the program's claimed effect.",
    },
    # ============================ evaluate ============================
    {
        "topic": _t("evaluate"), "difficulty": "medium",
        "stem": "A streaming service intends to raise its subscriber numbers by producing more "
                "original comedy shows. To evaluate this strategy, it would be most helpful to "
                "determine",
        "options": {
            "A": "whether the viewers the service hopes to attract choose streaming services based on the availability of original comedies.",
            "B": "how much it costs to produce a single original comedy.",
            "C": "whether the service's current shows are mostly dramas.",
            "D": "how many comedies the service's competitors produce.",
            "E": "whether comedies win more awards than dramas.",
        },
        "correct": "A",
        "explanation": "The strategy assumes original comedies attract subscribers; knowing whether "
                       "target viewers actually choose services for comedies tests that link.",
    },
    {
        "topic": _t("evaluate"), "difficulty": "medium",
        "stem": "A farmer plans to increase his orchard's apple output by switching to a new pruning "
                "method. The answer to which of the following would be most useful in evaluating the "
                "plan?",
        "options": {
            "A": "Whether the new pruning method yields more apples per tree than the farmer's current method under similar conditions.",
            "B": "Whether the new method takes less time to perform.",
            "C": "Whether neighboring farmers have heard of the method.",
            "D": "Whether the orchard's apples are sold locally or exported.",
            "E": "Whether the method was developed recently.",
        },
        "correct": "A",
        "explanation": "The plan's success hinges on whether the new method actually produces more "
                       "apples per tree than the current one; that comparison is what needs to be "
                       "known.",
    },
    {
        "topic": _t("evaluate"), "difficulty": "medium",
        "stem": "A university argues that requiring all students to take a public-speaking course will "
                "improve their career outcomes. To evaluate this argument, it would be most useful to "
                "determine",
        "options": {
            "A": "whether students who have taken public-speaking courses go on to have better career outcomes than comparable students who have not.",
            "B": "how many faculty members are available to teach the course.",
            "C": "whether students enjoy public-speaking courses.",
            "D": "how many weeks the public-speaking course lasts.",
            "E": "whether other universities require such a course.",
        },
        "correct": "A",
        "explanation": "The argument's core is that the course improves career outcomes; comparing "
                       "outcomes of those who took it with comparable peers who did not tests exactly "
                       "that.",
    },
    # ============================ inference ============================
    {
        "topic": _t("inference"), "difficulty": "medium",
        "stem": "The bakery sells out of croissants every day that it opens before 7 a.m. Yesterday, "
                "the bakery did not sell out of croissants. Which of the following must be true?",
        "options": {
            "A": "Yesterday the bakery did not open before 7 a.m.",
            "B": "The bakery never opens before 7 a.m.",
            "C": "The bakery baked fewer croissants than usual yesterday.",
            "D": "The bakery will open before 7 a.m. today.",
            "E": "Croissants are the bakery's most popular item.",
        },
        "correct": "A",
        "explanation": "Opening before 7 a.m. guarantees selling out. Since it did not sell out, by "
                       "the contrapositive it did not open before 7 a.m.",
    },
    {
        "topic": _t("inference"), "difficulty": "medium",
        "stem": "No smartphone made by this manufacturer has a removable battery. Every phone in the "
                "store's clearance bin has a removable battery. Which of the following can be "
                "logically concluded?",
        "options": {
            "A": "None of the phones in the clearance bin were made by this manufacturer.",
            "B": "All phones with removable batteries are in the clearance bin.",
            "C": "The manufacturer's phones are not sold in this store.",
            "D": "Phones with removable batteries are cheaper than others.",
            "E": "The clearance bin contains only older phones.",
        },
        "correct": "A",
        "explanation": "The manufacturer's phones lack removable batteries; clearance-bin phones all "
                       "have them; so no clearance-bin phone is from that manufacturer.",
    },
    {
        "topic": _t("inference"), "difficulty": "medium",
        "stem": "Whenever the river rises above the flood line, the riverside path is closed. Today "
                "the riverside path is open. Which of the following must be true?",
        "options": {
            "A": "The river is not above the flood line today.",
            "B": "The river has never risen above the flood line.",
            "C": "The path is open every day that the river is low.",
            "D": "The path will be closed tomorrow.",
            "E": "The flood line was recently lowered.",
        },
        "correct": "A",
        "explanation": "A river above the flood line forces the path to close. The path is open, so by "
                       "the contrapositive the river is not above the flood line.",
    },
    # ============================ explain_paradox ============================
    {
        "topic": _t("explain_paradox"), "difficulty": "medium",
        "stem": "A publisher raised the price of a popular magazine, yet its total revenue from that "
                "magazine fell. Which of the following, if true, most helps to explain this outcome?",
        "options": {
            "A": "So many readers canceled their subscriptions after the price rose that the loss in subscribers outweighed the higher price.",
            "B": "The magazine is published monthly.",
            "C": "The price increase was relatively small.",
            "D": "The magazine focuses on current events.",
            "E": "Competing magazines also raised their prices.",
        },
        "correct": "A",
        "explanation": "Revenue is price times subscribers; if enough readers canceled, revenue could "
                       "fall despite the higher price, explaining the result.",
    },
    {
        "topic": _t("explain_paradox"), "difficulty": "medium",
        "stem": "A gym added dozens of new treadmills to reduce crowding, but members now report that "
                "the treadmill area feels more crowded than before. Which of the following, if true, "
                "does most to explain the discrepancy?",
        "options": {
            "A": "To fit the new treadmills, the gym removed open floor space and packed the machines closer together.",
            "B": "The new treadmills have larger screens than the old ones.",
            "C": "Treadmills are the most popular equipment at the gym.",
            "D": "The gym's total membership has stayed roughly constant.",
            "E": "The gym is open twenty-four hours a day.",
        },
        "correct": "A",
        "explanation": "If adding treadmills meant cramming them into tighter space, the area could "
                       "feel more crowded even with more machines, explaining the discrepancy.",
    },
    {
        "topic": _t("explain_paradox"), "difficulty": "medium",
        "stem": "A software firm let employees set their own hours, expecting productivity to rise. "
                "Overall productivity instead declined. Which of the following, if true, most helps to "
                "explain the decline?",
        "options": {
            "A": "Because employees now worked at widely different times, teams could rarely meet to coordinate projects that required close collaboration.",
            "B": "Employees appreciated the new flexibility.",
            "C": "The firm's software is used by customers worldwide.",
            "D": "The policy applied to all departments equally.",
            "E": "The firm kept its existing vacation policy.",
        },
        "correct": "A",
        "explanation": "If flexible hours reduced the overlap teams needed to collaborate, "
                       "coordination-heavy work could suffer, lowering overall productivity.",
    },
    # ============================ flaw ============================
    {
        "topic": _t("flaw"), "difficulty": "medium",
        "stem": "Debater: My opponent has not proven that the new bridge is unsafe. Therefore the "
                "bridge must be safe. The debater's reasoning is flawed because it",
        "options": {
            "A": "treats the lack of evidence against a claim as proof that the claim is true.",
            "B": "relies on the opinions of unqualified people.",
            "C": "draws a conclusion about all bridges from a single bridge.",
            "D": "confuses the bridge's cost with its safety.",
            "E": "assumes that the opponent is being dishonest.",
        },
        "correct": "A",
        "explanation": "Concluding the bridge is safe simply because its danger has not been proven is "
                       "an appeal to ignorance; absence of disproof is not proof.",
    },
    {
        "topic": _t("flaw"), "difficulty": "medium",
        "stem": "Scientist: Every swan I have observed in this country is white. Therefore all swans "
                "everywhere are white. The scientist's reasoning is most vulnerable to the criticism "
                "that it",
        "options": {
            "A": "draws a sweeping general conclusion from a limited set of observations.",
            "B": "relies on a definition of 'swan' that is too narrow.",
            "C": "mistakes correlation for causation.",
            "D": "assumes the very point it is trying to establish.",
            "E": "appeals to the authority of other scientists.",
        },
        "correct": "A",
        "explanation": "Generalizing from swans seen in one country to all swans everywhere is a hasty "
                       "generalization; the sample cannot support the universal claim.",
    },
    {
        "topic": _t("flaw"), "difficulty": "hard",
        "stem": "Editorial: If we let the store stay open one hour later, employees will soon demand "
                "to work fewer days, and eventually the store will be unable to operate at all. We "
                "must therefore not extend the hours. The editorial's reasoning is flawed because it",
        "options": {
            "A": "assumes, without justification, that one modest change will inevitably set off a chain of increasingly serious consequences.",
            "B": "relies on statistics drawn from an unrepresentative sample.",
            "C": "attacks the character of the store's employees.",
            "D": "confuses a necessary condition with a sufficient one.",
            "E": "treats a product's popularity as evidence of its quality.",
        },
        "correct": "A",
        "explanation": "The argument is a slippery slope: it assumes without support that extending "
                       "hours must trigger an escalating series of demands ending in collapse.",
    },
    # ============================ boldface ============================
    {
        "topic": _t("boldface"), "difficulty": "hard",
        "stem": "Researcher: <b>The new drug does not work better than the old one.</b> Supporters "
                "point to a study in which patients on the new drug recovered faster, but <b>those "
                "patients were also younger and healthier than the patients taking the old drug.</b> "
                "In the researcher's argument, the two boldfaced portions play which of the following "
                "roles?",
        "options": {
            "A": "The first is the researcher's conclusion; the second is evidence the researcher uses to undermine a study cited against that conclusion.",
            "B": "The first is evidence; the second is the researcher's conclusion.",
            "C": "Both portions are conclusions the researcher draws.",
            "D": "The first is an objection; the second is the researcher's conclusion.",
            "E": "The first is the conclusion; the second is an assumption it depends on.",
        },
        "correct": "A",
        "explanation": "The first bold portion is the researcher's conclusion; the second points out a "
                       "confounder (younger, healthier patients) that undercuts the supporting study.",
    },
    {
        "topic": _t("boldface"), "difficulty": "hard",
        "stem": "Official: <b>Building the new stadium will benefit the city's economy.</b> Opponents "
                "cite the high construction cost, yet <b>the stadium is expected to draw millions of "
                "visitors who will spend money at local businesses.</b> In the official's argument, "
                "the two boldfaced portions play which of the following roles?",
        "options": {
            "A": "The first is the conclusion the official defends; the second is evidence offered to support it against an objection.",
            "B": "The first is an objection; the second is the official's conclusion.",
            "C": "Both portions are objections that the official concedes.",
            "D": "The first is evidence; the second is the conclusion.",
            "E": "The first is the conclusion; the second is an assumption the argument requires.",
        },
        "correct": "A",
        "explanation": "The first bold portion is the official's conclusion; the second is supporting "
                       "evidence (visitor spending) that answers the cost objection.",
    },
    {
        "topic": _t("boldface"), "difficulty": "hard",
        "stem": "Columnist: Many people claim that <b>working long hours leads to greater career "
                "success.</b> But <b>employees who take regular breaks and work moderate hours are "
                "often promoted faster than those who overwork.</b> The popular belief is therefore "
                "mistaken. In the columnist's argument, the two boldfaced portions play which of the "
                "following roles?",
        "options": {
            "A": "The first is the position the columnist argues against; the second is evidence the columnist uses to reject that position.",
            "B": "The first is the columnist's conclusion; the second supports it.",
            "C": "Both portions are evidence for the columnist's conclusion.",
            "D": "The first is evidence against the conclusion; the second is the conclusion.",
            "E": "The first is the columnist's conclusion; the second is an objection to it.",
        },
        "correct": "A",
        "explanation": "The first bold portion is the popular claim the columnist opposes; the second "
                       "is the columnist's counter-evidence (moderate-hour workers promoted faster).",
    },
    # ============================ complete_argument ============================
    {
        "topic": _t("complete_argument"), "difficulty": "medium",
        "stem": "A company requires all job applicants to pass a typing-speed test, believing that "
                "faster typists make better administrative assistants. This policy may be misguided, "
                "however, because ___. Which of the following most logically completes the argument?",
        "options": {
            "A": "the most important duties of the company's administrative assistants rarely involve typing",
            "B": "typing tests are inexpensive to administer",
            "C": "many applicants practice before taking the test",
            "D": "the company has used the test for several years",
            "E": "some administrative assistants can type very quickly",
        },
        "correct": "A",
        "explanation": "If the role rarely involves typing, screening on typing speed would not select "
                       "better assistants, showing the policy may be misguided.",
    },
    {
        "topic": _t("complete_argument"), "difficulty": "medium",
        "stem": "To improve student performance, a school district plans to give every student a "
                "laptop. Some administrators doubt the plan will help, arguing that ___. Which of the "
                "following most logically completes their argument?",
        "options": {
            "A": "without training in how to use the laptops for learning, students are likely to use them mainly for entertainment",
            "B": "laptops have become cheaper in recent years",
            "C": "the district has a large annual budget",
            "D": "many students already own smartphones",
            "E": "some teachers are enthusiastic about new technology",
        },
        "correct": "A",
        "explanation": "The doubt is supported if untrained students use the laptops for entertainment "
                       "rather than learning, giving a reason the plan may not improve performance.",
    },
    {
        "topic": _t("complete_argument"), "difficulty": "medium",
        "stem": "A restaurant owner believes that adding more vegetarian dishes to the menu will "
                "attract enough new customers to raise profits. This belief is probably well founded, "
                "because ___. Which of the following most logically completes the argument?",
        "options": {
            "A": "a large and growing number of diners in the area avoid meat and currently have few local dining options",
            "B": "vegetarian dishes are often cheaper to prepare",
            "C": "the restaurant has been in business for many years",
            "D": "the owner personally enjoys vegetarian food",
            "E": "the restaurant is located near a shopping mall",
        },
        "correct": "A",
        "explanation": "If many local diners avoid meat and lack options, adding vegetarian dishes "
                       "would draw new customers, supporting the owner's belief.",
    },
]


# ---------------------------------------------------------------------------
# Build + validate + emit
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def build(items: List[Dict], id_prefix: str, ts: str) -> List[Dict]:
    out: List[Dict] = []
    seen_ids = set()
    failures: List[str] = []

    for i, item in enumerate(items):
        tag = f"{id_prefix} #{i + 1} [{item['topic']}]"
        opts = item["options"]

        if set(opts.keys()) != set(taxonomy.OPTION_KEYS):
            failures.append(f"{tag}: options must be exactly A-E")
            continue
        distinct = {str(v).strip().lower() for v in opts.values()}
        if len(distinct) != 5:
            failures.append(f"{tag}: options are not all distinct")
        if item["correct"] not in taxonomy.OPTION_KEYS:
            failures.append(f"{tag}: correct '{item['correct']}' not in A-E")

        q = taxonomy.make_question(
            id=taxonomy.make_id(id_prefix, item["stem"], opts),
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
        errs = taxonomy.validate_question(q, require_explanation=True)
        if errs:
            failures.append(f"{tag}: schema errors: {errs}")
        if q["id"] in seen_ids:
            failures.append(f"{tag}: duplicate id {q['id']}")
        seen_ids.add(q["id"])
        out.append(q)

    if failures:
        print(f"VERBAL BUILD FAILED ({id_prefix}) — fix these before shipping:", file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        raise SystemExit(1)

    out.sort(key=lambda q: (q["topic"], q["id"]))
    return out


def _tagger_agreement(items: List[Dict]) -> float:
    """Soft signal: how often the keyword tagger recovers the gold leaf."""
    if not items:
        return 0.0
    hits = sum(
        1 for q in items
        if taxonomy.tag_topic(q["stem"] + " " + " ".join(q["options"].values()),
                              section="verbal") == q["topic"]
    )
    return hits / len(items)


def main() -> int:
    ts = now_iso()
    seed = build(SEED, "vseed", ts)
    bank = build(BANK, "vbank", ts)

    seed_path = os.path.join(_HERE, "verbal_seed.json")
    bank_path = os.path.join(_HERE, "verbal_questions.json")
    for path, data in ((seed_path, seed), (bank_path, bank)):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    counts = taxonomy.topic_counts(seed + bank)
    print(f"VERBAL OK — {len(seed)} gold seed + {len(bank)} bank = "
          f"{len(seed) + len(bank)} authored CR questions.")
    print(f"Wrote -> {seed_path}")
    print(f"Wrote -> {bank_path}\n")
    print("Authored CR counts per leaf (seed + bank):")
    for topic in taxonomy.VERBAL_TOPICS:
        print(f"  {topic:40s} {counts.get(topic, 0)}")
    print(f"\nKeyword-tagger agreement with gold labels: "
          f"seed={_tagger_agreement(seed):.0%}, bank={_tagger_agreement(bank):.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
