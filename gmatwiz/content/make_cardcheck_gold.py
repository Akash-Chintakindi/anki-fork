#!/usr/bin/env python3
"""Author + self-verify the GMATWiz 7f CARD-CHECK GOLD set (cardcheck_gold.json).

This is the "gold set" for challenge 7f: 50 ORIGINAL GMAT Quant Problem Solving
question-and-answer pairs with KNOWN-correct answers. They are the ground truth the
card checker (card_check.py) cross-verifies AI-generated cards against.

Same discipline as make_seed.py: every question ships a ``check`` callable that
recomputes the answer from first principles (it does NOT read the labelled answer),
finds the matching option, and the build asserts that option equals the declared
``correct`` letter. The build fails loudly if any question's math is wrong, options
aren't distinct, or the schema is violated -- so the 50 gold answers are guaranteed
genuinely correct.

All content is ORIGINAL, written for GMATWiz (license/source ``authored-gmatwiz``).
NO copyrighted or official GMAT items are copied. Scope is PRD Section 5 Quant:
arithmetic + algebra Problem Solving only (NO geometry, NO Data Sufficiency), spread
across all 18 taxonomy leaves. These items are deliberately distinct from seed.json.

Run:  out/pyenv/bin/python gmatwiz/content/make_cardcheck_gold.py
      -> writes gmatwiz/content/cardcheck_gold.json (50 verified items)
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import sys
from fractions import Fraction
from typing import Callable, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import taxonomy  # noqa: E402

SOURCE = "authored-gmatwiz"
LICENSE = "authored-gmatwiz"
# Fixed timestamp so re-running produces a byte-identical file (stable diffs).
GOLD_TS = "2026-07-05T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Verification helpers (mirror make_seed.py): recompute answers independently.
# ---------------------------------------------------------------------------
def _num(s: str) -> Optional[float]:
    """Parse a number from an option string ($, %, commas, simple fractions)."""
    if s is None:
        return None
    t = str(s).strip()
    t = t.replace("$", "").replace(",", "").replace("%", "").strip()
    t = t.replace("\u2212", "-")  # unicode minus
    if re.fullmatch(r"-?\d+\s*/\s*\d+", t):
        a, b = t.split("/")
        return float(a) / float(b)
    try:
        return float(t)
    except ValueError:
        return None


def letter_for_value(options: Dict[str, str], value: float,
                     rel_tol: float = 1e-6) -> Optional[str]:
    """Return the option letter whose numeric value matches ``value`` (unique)."""
    tol = max(1e-9, rel_tol * max(1.0, abs(value)))
    hits = [ltr for ltr, txt in options.items()
            if (_num(txt) is not None and abs(_num(txt) - value) <= tol)]
    return hits[0] if len(hits) == 1 else None


def _monomial_value(s: str, x: float) -> Optional[float]:
    """Evaluate a simple monomial like 'x^7', '3x^3', '12x^7', '5' at x."""
    t = str(s).strip().lower().replace(" ", "").replace("**", "^")
    m = re.fullmatch(r"(-?\d+)?(x)?(?:\^(-?\d+))?", t)
    if not m:
        return None
    coeff_s, has_x, pow_s = m.group(1), m.group(2) == "x", m.group(3)
    coeff = int(coeff_s) if coeff_s not in (None, "") else 1
    if not has_x:
        return float(coeff)
    power = int(pow_s) if pow_s is not None else 1
    return float(coeff) * (x ** power)


def letter_for_monomial(options: Dict[str, str], func: Callable[[float], float],
                        xs=(2.0, 3.0)) -> Optional[str]:
    """Return the option letter whose monomial matches ``func`` at all xs (unique)."""
    best = None
    for letter, text in options.items():
        ok = True
        for x in xs:
            mv = _monomial_value(text, x)
            if mv is None or abs(mv - func(x)) > 1e-6 * max(1.0, abs(func(x))):
                ok = False
                break
        if ok:
            if best is not None:
                return None  # ambiguous
            best = letter
    return best


def num_divisors(n: int) -> int:
    return sum(1 for d in range(1, n + 1) if n % d == 0)


def quad_roots(a: float, b: float, c: float):
    disc = b * b - 4 * a * c
    r = math.sqrt(disc)
    return ((-b + r) / (2 * a), (-b - r) / (2 * a))


def letter_for_any_root(options, roots):
    for r in roots:
        letter = letter_for_value(options, r)
        if letter:
            return letter
    return None


def int_pow_solution(base: int, target: int) -> int:
    """Smallest exponent k with base**k == target (for clean exponent items)."""
    return next(k for k in range(0, 40) if base ** k == target)


# ---------------------------------------------------------------------------
# The 50 authored gold questions (each with an independent check()).
# ---------------------------------------------------------------------------
Q = taxonomy.PREFIX  # "gmat::quant"

QUESTIONS: List[Dict] = [
    # ===================== ARITHMETIC :: number_properties (3) =============
    {
        "topic": f"{Q}::arithmetic::number_properties", "difficulty": "medium",
        "stem": "What is the units digit of 3^24?",
        "options": {"A": "1", "B": "3", "C": "6", "D": "7", "E": "9"},
        "correct": "A",
        "explanation": "The units digit of powers of 3 cycles with period 4: 3, 9, 7, 1, then "
                       "repeats. Since 24 is a multiple of 4, the units digit matches that of "
                       "3^4, which ends in 1.",
        "check": lambda o: letter_for_value(o, (3 ** 24) % 10),
    },
    {
        "topic": f"{Q}::arithmetic::number_properties", "difficulty": "easy",
        "stem": "When the positive integer n is divided by 5, the remainder is 3. What is the "
                "remainder when 4n is divided by 5?",
        "options": {"A": "0", "B": "1", "C": "2", "D": "3", "E": "4"},
        "correct": "C",
        "explanation": "4n leaves the same remainder as 4 x 3 = 12 does on division by 5. "
                       "Since 12 = 10 + 2, the remainder is 2. (Check n = 8: 4 x 8 = 32 = 30 + 2.)",
        "check": lambda o: letter_for_value(o, (4 * 8) % 5),
    },
    {
        "topic": f"{Q}::arithmetic::number_properties", "difficulty": "medium",
        "stem": "How many distinct positive factors does 72 have?",
        "options": {"A": "6", "B": "8", "C": "10", "D": "12", "E": "14"},
        "correct": "D",
        "explanation": "Prime-factorize: 72 = 2^3 x 3^2. The number of factors is "
                       "(3 + 1)(2 + 1) = 4 x 3 = 12.",
        "check": lambda o: letter_for_value(o, num_divisors(72)),
    },
    # ===================== ARITHMETIC :: fractions (3) ====================
    {
        "topic": f"{Q}::arithmetic::fractions", "difficulty": "easy",
        "stem": "What is the value of 3/4 - 1/6 ?",
        "options": {"A": "1/3", "B": "5/12", "C": "1/2", "D": "7/12", "E": "2/3"},
        "correct": "D",
        "explanation": "Use a common denominator of 12: 3/4 = 9/12 and 1/6 = 2/12, so "
                       "9/12 - 2/12 = 7/12.",
        "check": lambda o: letter_for_value(o, float(Fraction(3, 4) - Fraction(1, 6))),
    },
    {
        "topic": f"{Q}::arithmetic::fractions", "difficulty": "medium",
        "stem": "A tank is 5/8 full of water. Water equal to 1/4 of the tank's capacity is then "
                "added. What fraction of the tank is filled?",
        "options": {"A": "3/4", "B": "13/16", "C": "7/8", "D": "11/12", "E": "1"},
        "correct": "C",
        "explanation": "Add the fractions of capacity: 5/8 + 1/4 = 5/8 + 2/8 = 7/8.",
        "check": lambda o: letter_for_value(o, float(Fraction(5, 8) + Fraction(1, 4))),
    },
    {
        "topic": f"{Q}::arithmetic::fractions", "difficulty": "medium",
        "stem": "What is the reciprocal of 2/5 + 1/10 ?",
        "options": {"A": "1/5", "B": "1/2", "C": "2", "D": "5/2", "E": "10"},
        "correct": "C",
        "explanation": "First add: 2/5 + 1/10 = 4/10 + 1/10 = 5/10 = 1/2. The reciprocal of "
                       "1/2 is 2.",
        "check": lambda o: letter_for_value(o, 1.0 / float(Fraction(2, 5) + Fraction(1, 10))),
    },
    # ===================== ARITHMETIC :: decimals (3) =====================
    {
        "topic": f"{Q}::arithmetic::decimals", "difficulty": "easy",
        "stem": "What is the value of 0.6 x 0.15 ?",
        "options": {"A": "0.009", "B": "0.045", "C": "0.09", "D": "0.9", "E": "9.0"},
        "correct": "C",
        "explanation": "Multiply 6 x 15 = 90, then place the decimal: 0.6 has one decimal place "
                       "and 0.15 has two, for three places total: 0.090 = 0.09.",
        "check": lambda o: letter_for_value(o, 0.6 * 0.15),
    },
    {
        "topic": f"{Q}::arithmetic::decimals", "difficulty": "medium",
        "stem": "What is the value of 2.5 / 0.05 ?",
        "options": {"A": "0.05", "B": "0.5", "C": "5", "D": "50", "E": "500"},
        "correct": "D",
        "explanation": "Multiply top and bottom by 100: 250 / 5 = 50.",
        "check": lambda o: letter_for_value(o, 2.5 / 0.05),
    },
    {
        "topic": f"{Q}::arithmetic::decimals", "difficulty": "easy",
        "stem": "What is 4.7823 rounded to the nearest hundredth?",
        "options": {"A": "4.7", "B": "4.78", "C": "4.782", "D": "4.79", "E": "4.8"},
        "correct": "B",
        "explanation": "The hundredths digit is 8; the next digit (2) is less than 5, so we "
                       "round down and keep 4.78.",
        "check": lambda o: letter_for_value(o, round(4.7823, 2)),
    },
    # ===================== ARITHMETIC :: percents (3) =====================
    {
        "topic": f"{Q}::arithmetic::percents", "difficulty": "easy",
        "stem": "What is 30% of 250?",
        "options": {"A": "55", "B": "65", "C": "70", "D": "75", "E": "80"},
        "correct": "D",
        "explanation": "30% = 0.30, and 0.30 x 250 = 75.",
        "check": lambda o: letter_for_value(o, 0.30 * 250),
    },
    {
        "topic": f"{Q}::arithmetic::percents", "difficulty": "medium",
        "stem": "A price is increased by 40% and then decreased by 25%. The final price is what "
                "percent of the original price?",
        "options": {"A": "95%", "B": "100%", "C": "105%", "D": "110%", "E": "115%"},
        "correct": "C",
        "explanation": "Apply the factors in sequence: 1.40 x 0.75 = 1.05, i.e. 105% of the "
                       "original price.",
        "check": lambda o: letter_for_value(o, 1.40 * 0.75 * 100),
    },
    {
        "topic": f"{Q}::arithmetic::percents", "difficulty": "medium",
        "stem": "After a 20% discount, a book sells for $48. What was its original price?",
        "options": {"A": "$54", "B": "$56", "C": "$58", "D": "$60", "E": "$64"},
        "correct": "D",
        "explanation": "A 20% discount means the sale price is 80% of the original: "
                       "0.80 x P = 48, so P = 48 / 0.80 = $60.",
        "check": lambda o: letter_for_value(o, 48 / 0.80),
    },
    # ===================== ARITHMETIC :: ratios_proportions (3) ===========
    {
        "topic": f"{Q}::arithmetic::ratios_proportions", "difficulty": "easy",
        "stem": "The ratio of cats to dogs in a shelter is 4 to 7. If there are 28 dogs, how "
                "many cats are there?",
        "options": {"A": "12", "B": "14", "C": "16", "D": "18", "E": "20"},
        "correct": "C",
        "explanation": "Each ratio unit equals 28 / 7 = 4 animals. Cats = 4 units = 4 x 4 = 16.",
        "check": lambda o: letter_for_value(o, 28 / 7 * 4),
    },
    {
        "topic": f"{Q}::arithmetic::ratios_proportions", "difficulty": "medium",
        "stem": "If 5 workers assemble 60 chairs in a day, how many chairs do 8 workers assemble "
                "in a day at the same rate?",
        "options": {"A": "84", "B": "90", "C": "96", "D": "108", "E": "120"},
        "correct": "C",
        "explanation": "Each worker makes 60 / 5 = 12 chairs per day, so 8 workers make "
                       "8 x 12 = 96.",
        "check": lambda o: letter_for_value(o, 60 / 5 * 8),
    },
    {
        "topic": f"{Q}::arithmetic::ratios_proportions", "difficulty": "medium",
        "stem": "Two numbers are in the ratio 3 to 5, and their sum is 64. What is the larger "
                "number?",
        "options": {"A": "24", "B": "32", "C": "36", "D": "40", "E": "48"},
        "correct": "D",
        "explanation": "The 8 total ratio units share 64, so each unit is 64 / 8 = 8. The "
                       "larger number is 5 units = 5 x 8 = 40.",
        "check": lambda o: letter_for_value(o, 64 / (3 + 5) * 5),
    },
    # ===================== ARITHMETIC :: exponents_roots (3) ==============
    {
        "topic": f"{Q}::arithmetic::exponents_roots", "difficulty": "easy",
        "stem": "If 3^x = 81, what is the value of x?",
        "options": {"A": "2", "B": "3", "C": "4", "D": "5", "E": "9"},
        "correct": "C",
        "explanation": "Write 81 as a power of 3: 81 = 3^4, so x = 4.",
        "check": lambda o: letter_for_value(o, int_pow_solution(3, 81)),
    },
    {
        "topic": f"{Q}::arithmetic::exponents_roots", "difficulty": "easy",
        "stem": "What is the value of sqrt(196) - sqrt(49) ?",
        "options": {"A": "5", "B": "7", "C": "9", "D": "11", "E": "147"},
        "correct": "B",
        "explanation": "sqrt(196) = 14 and sqrt(49) = 7, so the difference is 14 - 7 = 7.",
        "check": lambda o: letter_for_value(o, math.isqrt(196) - math.isqrt(49)),
    },
    {
        "topic": f"{Q}::arithmetic::exponents_roots", "difficulty": "medium",
        "stem": "What is the value of 2^5 x 2^3 ?",
        "options": {"A": "16", "B": "64", "C": "128", "D": "256", "E": "512"},
        "correct": "D",
        "explanation": "Add the exponents when multiplying like bases: 2^5 x 2^3 = 2^8 = 256.",
        "check": lambda o: letter_for_value(o, 2 ** 5 * 2 ** 3),
    },
    # ===================== ARITHMETIC :: statistics (3) ==================
    {
        "topic": f"{Q}::arithmetic::statistics", "difficulty": "easy",
        "stem": "The average (arithmetic mean) of 8 numbers is 15. What is the sum of the "
                "8 numbers?",
        "options": {"A": "100", "B": "110", "C": "115", "D": "120", "E": "128"},
        "correct": "D",
        "explanation": "Sum = average x count = 15 x 8 = 120.",
        "check": lambda o: letter_for_value(o, 8 * 15),
    },
    {
        "topic": f"{Q}::arithmetic::statistics", "difficulty": "easy",
        "stem": "What is the median of the list 14, 3, 9, 21, 6 ?",
        "options": {"A": "6", "B": "9", "C": "10", "D": "11", "E": "14"},
        "correct": "B",
        "explanation": "Sort the list: 3, 6, 9, 14, 21. With 5 values the median is the middle "
                       "one, which is 9.",
        "check": lambda o: letter_for_value(o, statistics.median([14, 3, 9, 21, 6])),
    },
    {
        "topic": f"{Q}::arithmetic::statistics", "difficulty": "hard",
        "stem": "The average (arithmetic mean) of 5 numbers is 20. When one number is removed, "
                "the average of the remaining 4 numbers is 18. What number was removed?",
        "options": {"A": "24", "B": "26", "C": "28", "D": "30", "E": "32"},
        "correct": "C",
        "explanation": "Sum of all 5 is 5 x 20 = 100; sum of the 4 that remain is 4 x 18 = 72. "
                       "The removed number is 100 - 72 = 28.",
        "check": lambda o: letter_for_value(o, 5 * 20 - 4 * 18),
    },
    # ===================== ARITHMETIC :: sets (3) ========================
    {
        "topic": f"{Q}::arithmetic::sets", "difficulty": "medium",
        "stem": "In a group of 60 people, 35 own a car and 30 own a bicycle. If 15 own both, "
                "how many own neither?",
        "options": {"A": "5", "B": "10", "C": "15", "D": "20", "E": "25"},
        "correct": "B",
        "explanation": "Owners of at least one = 35 + 30 - 15 = 50 (inclusion-exclusion). So "
                       "those with neither = 60 - 50 = 10.",
        "check": lambda o: letter_for_value(o, 60 - (35 + 30 - 15)),
    },
    {
        "topic": f"{Q}::arithmetic::sets", "difficulty": "medium",
        "stem": "Of 80 students, 50 study math and 45 study science. If 5 study neither, how "
                "many study both?",
        "options": {"A": "15", "B": "20", "C": "25", "D": "30", "E": "35"},
        "correct": "B",
        "explanation": "Students studying at least one = 80 - 5 = 75. By inclusion-exclusion, "
                       "both = 50 + 45 - 75 = 20.",
        "check": lambda o: letter_for_value(o, 50 + 45 - (80 - 5)),
    },
    {
        "topic": f"{Q}::arithmetic::sets", "difficulty": "easy",
        "stem": "In a class of 30 students, 18 play soccer and 14 play tennis, and every student "
                "plays at least one of the two. How many play both?",
        "options": {"A": "2", "B": "4", "C": "6", "D": "8", "E": "10"},
        "correct": "A",
        "explanation": "Since everyone plays at least one, the union is 30. By inclusion-"
                       "exclusion, both = 18 + 14 - 30 = 2.",
        "check": lambda o: letter_for_value(o, 18 + 14 - 30),
    },
    # ===================== ARITHMETIC :: counting (3) ====================
    {
        "topic": f"{Q}::arithmetic::counting", "difficulty": "medium",
        "stem": "In how many different ways can all the letters of the word NUMBER be arranged? "
                "(All six letters are distinct.)",
        "options": {"A": "120", "B": "240", "C": "360", "D": "720", "E": "5040"},
        "correct": "D",
        "explanation": "Six distinct letters can be arranged in 6! = 720 ways.",
        "check": lambda o: letter_for_value(o, math.factorial(6)),
    },
    {
        "topic": f"{Q}::arithmetic::counting", "difficulty": "medium",
        "stem": "A team of 2 people is to be chosen from a group of 7 people. How many different "
                "teams are possible?",
        "options": {"A": "14", "B": "21", "C": "28", "D": "42", "E": "49"},
        "correct": "B",
        "explanation": "Order does not matter, so use combinations: 7C2 = (7 x 6) / 2 = 21.",
        "check": lambda o: letter_for_value(o, math.comb(7, 2)),
    },
    {
        "topic": f"{Q}::arithmetic::counting", "difficulty": "medium",
        "stem": "How many 3-digit numbers can be formed from the digits 1, 2, 3, 4, 5 if no "
                "digit is repeated?",
        "options": {"A": "60", "B": "75", "C": "100", "D": "120", "E": "125"},
        "correct": "A",
        "explanation": "There are 5 choices for the first digit, 4 for the second, and 3 for the "
                       "third: 5 x 4 x 3 = 60.",
        "check": lambda o: letter_for_value(o, 5 * 4 * 3),
    },
    # ===================== ARITHMETIC :: probability (3) =================
    {
        "topic": f"{Q}::arithmetic::probability", "difficulty": "easy",
        "stem": "A bag contains 5 green and 3 yellow balls. If one ball is drawn at random, what "
                "is the probability that it is yellow?",
        "options": {"A": "1/4", "B": "3/8", "C": "1/2", "D": "5/8", "E": "3/5"},
        "correct": "B",
        "explanation": "P(yellow) = favorable / total = 3 / (5 + 3) = 3/8.",
        "check": lambda o: letter_for_value(o, 3 / 8),
    },
    {
        "topic": f"{Q}::arithmetic::probability", "difficulty": "easy",
        "stem": "A fair six-sided die is rolled once. What is the probability of rolling a "
                "number greater than 4?",
        "options": {"A": "1/6", "B": "1/3", "C": "1/2", "D": "2/3", "E": "5/6"},
        "correct": "B",
        "explanation": "The favorable outcomes are 5 and 6 (two of six equally likely faces), "
                       "so the probability is 2/6 = 1/3.",
        "check": lambda o: letter_for_value(o, 2 / 6),
    },
    {
        "topic": f"{Q}::arithmetic::probability", "difficulty": "hard",
        "stem": "A box contains 4 red and 6 blue pens. If 2 pens are drawn at random without "
                "replacement, what is the probability that both are blue?",
        "options": {"A": "1/3", "B": "3/10", "C": "9/25", "D": "2/5", "E": "1/2"},
        "correct": "A",
        "explanation": "P(both blue) = (6/10) x (5/9) = 30/90 = 1/3.",
        "check": lambda o: letter_for_value(o, (6 / 10) * (5 / 9)),
    },
    # ===================== ALGEBRA :: linear_equations (3) ===============
    {
        "topic": f"{Q}::algebra::linear_equations", "difficulty": "easy",
        "stem": "If 4x + 7 = 2x + 19, what is the value of x?",
        "options": {"A": "4", "B": "5", "C": "6", "D": "7", "E": "8"},
        "correct": "C",
        "explanation": "Subtract 2x from both sides: 2x + 7 = 19. Subtract 7: 2x = 12, so x = 6.",
        "check": lambda o: letter_for_value(o, (19 - 7) / (4 - 2)),
    },
    {
        "topic": f"{Q}::algebra::linear_equations", "difficulty": "medium",
        "stem": "If 3x - 2y = 12 and x + 2y = 8, what is the value of x?",
        "options": {"A": "3", "B": "4", "C": "5", "D": "6", "E": "7"},
        "correct": "C",
        "explanation": "Add the two equations so the y-terms cancel: 4x = 20, so x = 5.",
        "check": lambda o: letter_for_value(o, (12 + 8) / (3 + 1)),
    },
    {
        "topic": f"{Q}::algebra::linear_equations", "difficulty": "easy",
        "stem": "A number added to three times itself equals 48. What is the number?",
        "options": {"A": "8", "B": "10", "C": "12", "D": "16", "E": "24"},
        "correct": "C",
        "explanation": "Let the number be x. Then x + 3x = 4x = 48, so x = 12.",
        "check": lambda o: letter_for_value(o, 48 / 4),
    },
    # ===================== ALGEBRA :: quadratics (3) =====================
    {
        "topic": f"{Q}::algebra::quadratics", "difficulty": "medium",
        "stem": "If x^2 - 9x + 20 = 0 and x > 4, what is the value of x?",
        "options": {"A": "2", "B": "4", "C": "5", "D": "9", "E": "20"},
        "correct": "C",
        "explanation": "Factor: (x - 4)(x - 5) = 0, so x = 4 or x = 5. Since x > 4, x = 5.",
        "check": lambda o: letter_for_value(o, max(quad_roots(1, -9, 20))),
    },
    {
        "topic": f"{Q}::algebra::quadratics", "difficulty": "medium",
        "stem": "If x^2 - 3x - 10 = 0, which of the following is a possible value of x?",
        "options": {"A": "-5", "B": "-3", "C": "1", "D": "2", "E": "5"},
        "correct": "E",
        "explanation": "Factor: (x - 5)(x + 2) = 0, so x = 5 or x = -2. Of the choices, only "
                       "5 appears.",
        "check": lambda o: letter_for_any_root(o, quad_roots(1, -3, -10)),
    },
    {
        "topic": f"{Q}::algebra::quadratics", "difficulty": "hard",
        "stem": "The product of two consecutive positive integers is 56. What is the larger of "
                "the two integers?",
        "options": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "14"},
        "correct": "C",
        "explanation": "If the smaller integer is n, then n(n + 1) = 56. Since 7 x 8 = 56, the "
                       "integers are 7 and 8, and the larger is 8.",
        "check": lambda o: letter_for_value(o, max(quad_roots(1, 1, -56)) + 1),
    },
    # ===================== ALGEBRA :: inequalities (2) ===================
    {
        "topic": f"{Q}::algebra::inequalities", "difficulty": "easy",
        "stem": "What is the greatest integer value of x for which 2x + 3 < 15 ?",
        "options": {"A": "4", "B": "5", "C": "6", "D": "7", "E": "8"},
        "correct": "B",
        "explanation": "Subtract 3: 2x < 12, so x < 6. The greatest integer strictly less than "
                       "6 is 5.",
        "check": lambda o: letter_for_value(o, math.ceil((15 - 3) / 2) - 1),
    },
    {
        "topic": f"{Q}::algebra::inequalities", "difficulty": "medium",
        "stem": "How many integer values of x satisfy 1 <= 2x - 3 <= 9 ?",
        "options": {"A": "3", "B": "4", "C": "5", "D": "6", "E": "7"},
        "correct": "C",
        "explanation": "Add 3 throughout: 4 <= 2x <= 12, so 2 <= x <= 6. The integers 2, 3, 4, "
                       "5, 6 give 5 values.",
        "check": lambda o: letter_for_value(o, sum(1 for x in range(-50, 50) if 1 <= 2 * x - 3 <= 9)),
    },
    # ===================== ALGEBRA :: absolute_value (2) =================
    {
        "topic": f"{Q}::algebra::absolute_value", "difficulty": "medium",
        "stem": "If |2x - 1| = 9, what is the sum of all possible values of x?",
        "options": {"A": "-4", "B": "0", "C": "1", "D": "5", "E": "9"},
        "correct": "C",
        "explanation": "Either 2x - 1 = 9 (so x = 5) or 2x - 1 = -9 (so x = -4). Their sum is "
                       "5 + (-4) = 1.",
        "check": lambda o: letter_for_value(o, (1 + 9) / 2 + (1 - 9) / 2),
    },
    {
        "topic": f"{Q}::algebra::absolute_value", "difficulty": "easy",
        "stem": "How many integer values of x satisfy |x - 2| <= 3 ?",
        "options": {"A": "5", "B": "6", "C": "7", "D": "8", "E": "9"},
        "correct": "C",
        "explanation": "|x - 2| <= 3 means -3 <= x - 2 <= 3, i.e. -1 <= x <= 5. The integers "
                       "-1, 0, 1, 2, 3, 4, 5 give 7 values.",
        "check": lambda o: letter_for_value(o, sum(1 for x in range(-50, 50) if abs(x - 2) <= 3)),
    },
    # ===================== ALGEBRA :: functions (3) ======================
    {
        "topic": f"{Q}::algebra::functions", "difficulty": "easy",
        "stem": "If f(x) = 3x^2 - 2x + 4, what is f(2)?",
        "options": {"A": "8", "B": "10", "C": "12", "D": "14", "E": "16"},
        "correct": "C",
        "explanation": "f(2) = 3(2^2) - 2(2) + 4 = 12 - 4 + 4 = 12.",
        "check": lambda o: letter_for_value(o, 3 * 2 ** 2 - 2 * 2 + 4),
    },
    {
        "topic": f"{Q}::algebra::functions", "difficulty": "medium",
        "stem": "For all numbers a and b, the operation @ is defined by a @ b = 2a + b^2. What "
                "is the value of 3 @ 4?",
        "options": {"A": "10", "B": "14", "C": "18", "D": "22", "E": "26"},
        "correct": "D",
        "explanation": "Substitute into the definition: 3 @ 4 = 2(3) + 4^2 = 6 + 16 = 22.",
        "check": lambda o: letter_for_value(o, 2 * 3 + 4 ** 2),
    },
    {
        "topic": f"{Q}::algebra::functions", "difficulty": "medium",
        "stem": "If g(x) = (x + 5) / 2, for what value of x does g(x) = 9?",
        "options": {"A": "9", "B": "11", "C": "13", "D": "15", "E": "18"},
        "correct": "C",
        "explanation": "Set (x + 5) / 2 = 9, so x + 5 = 18 and x = 13.",
        "check": lambda o: letter_for_value(o, 9 * 2 - 5),
    },
    # ===================== ALGEBRA :: sequences (2) ======================
    {
        "topic": f"{Q}::algebra::sequences", "difficulty": "medium",
        "stem": "In an arithmetic sequence, the first term is 7 and the common difference is 5. "
                "What is the 8th term?",
        "options": {"A": "35", "B": "40", "C": "42", "D": "47", "E": "52"},
        "correct": "C",
        "explanation": "The nth term is a + (n - 1)d = 7 + (8 - 1)(5) = 7 + 35 = 42.",
        "check": lambda o: letter_for_value(o, 7 + (8 - 1) * 5),
    },
    {
        "topic": f"{Q}::algebra::sequences", "difficulty": "medium",
        "stem": "The first term of a geometric sequence is 2 and the common ratio is 3. What is "
                "the 4th term?",
        "options": {"A": "18", "B": "27", "C": "54", "D": "81", "E": "162"},
        "correct": "C",
        "explanation": "The nth term is a x r^(n-1) = 2 x 3^(4-1) = 2 x 27 = 54.",
        "check": lambda o: letter_for_value(o, 2 * 3 ** (4 - 1)),
    },
    # ===================== ALGEBRA :: expressions (2) ====================
    {
        "topic": f"{Q}::algebra::expressions", "difficulty": "easy",
        "stem": "For any nonzero x, which of the following is equivalent to (x^6) / (x^2) ?",
        "options": {"A": "x^2", "B": "x^3", "C": "x^4", "D": "x^8", "E": "x^12"},
        "correct": "C",
        "explanation": "When dividing powers with the same base, subtract the exponents: "
                       "x^(6-2) = x^4.",
        "check": lambda o: letter_for_monomial(o, lambda x: x ** 4),
    },
    {
        "topic": f"{Q}::algebra::expressions", "difficulty": "medium",
        "stem": "For any nonzero x, which of the following is equivalent to (4x^5)(3x^2) ?",
        "options": {"A": "7x^7", "B": "12x^3", "C": "12x^7", "D": "12x^10", "E": "7x^10"},
        "correct": "C",
        "explanation": "Multiply the coefficients (4 x 3 = 12) and add the exponents "
                       "(5 + 2 = 7): the result is 12x^7.",
        "check": lambda o: letter_for_monomial(o, lambda x: 12 * x ** 7),
    },
    # ===================== ALGEBRA :: word_problems (3) ==================
    {
        "topic": f"{Q}::algebra::word_problems", "difficulty": "medium",
        "stem": "A car travels 300 kilometers in 5 hours. At the same constant rate, how far "
                "will it travel in 8 hours?",
        "options": {"A": "420", "B": "450", "C": "480", "D": "540", "E": "600"},
        "correct": "C",
        "explanation": "The rate is 300 / 5 = 60 km per hour, so in 8 hours it covers "
                       "60 x 8 = 480 kilometers.",
        "check": lambda o: letter_for_value(o, 300 / 5 * 8),
    },
    {
        "topic": f"{Q}::algebra::word_problems", "difficulty": "hard",
        "stem": "Pipe X can fill a tank in 4 hours and pipe Y can fill the same tank in 12 "
                "hours. Working together, how many hours will they take to fill the tank?",
        "options": {"A": "2", "B": "3", "C": "4", "D": "6", "E": "8"},
        "correct": "B",
        "explanation": "Combined rate = 1/4 + 1/12 = 3/12 + 1/12 = 4/12 = 1/3 tank per hour, so "
                       "the time is the reciprocal: 3 hours.",
        "check": lambda o: letter_for_value(o, 1 / (1 / 4 + 1 / 12)),
    },
    {
        "topic": f"{Q}::algebra::word_problems", "difficulty": "medium",
        "stem": "$1,500 is invested at 6% simple annual interest. How much interest is earned "
                "after 4 years?",
        "options": {"A": "$240", "B": "$300", "C": "$360", "D": "$420", "E": "$450"},
        "correct": "C",
        "explanation": "Simple interest = principal x rate x time = 1500 x 0.06 x 4 = $360.",
        "check": lambda o: letter_for_value(o, 1500 * 0.06 * 4),
    },
]


# ---------------------------------------------------------------------------
# Build + verify (fail loudly on any wrong answer / schema / duplicate).
# ---------------------------------------------------------------------------
def build() -> List[Dict]:
    out: List[Dict] = []
    seen_ids = set()
    seen_content = set()
    failures: List[str] = []

    for i, item in enumerate(QUESTIONS):
        tag = f"G{i + 1} [{item['topic']}]"
        opts = item["options"]

        if set(opts.keys()) != set(taxonomy.OPTION_KEYS):
            failures.append(f"{tag}: options must be exactly A-E")
            continue
        distinct = {str(v).strip().lower() for v in opts.values()}
        if len(distinct) != 5:
            failures.append(f"{tag}: options are not all distinct")
        if item["correct"] not in taxonomy.OPTION_KEYS:
            failures.append(f"{tag}: correct '{item['correct']}' not in A-E")

        # Core: independently recompute the answer and confirm it matches.
        try:
            computed = item["check"](opts)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{tag}: check() raised {type(exc).__name__}: {exc}")
            computed = None
        if computed is None:
            failures.append(f"{tag}: check() could not uniquely locate the answer")
        elif computed != item["correct"]:
            failures.append(
                f"{tag}: VERIFICATION MISMATCH - recomputed '{computed}' but labelled "
                f"'{item['correct']}'"
            )

        q = taxonomy.make_question(
            id=taxonomy.make_id("cardgold", item["stem"], opts),
            stem=item["stem"],
            options=opts,
            correct=item["correct"],
            explanation=item["explanation"],
            topic=item["topic"],
            difficulty=item["difficulty"],
            source=SOURCE,
            license=LICENSE,
            scraped_at=GOLD_TS,
        )
        errs = taxonomy.validate_question(q, require_explanation=True)
        if errs:
            failures.append(f"{tag}: schema errors: {errs}")
        if q["id"] in seen_ids:
            failures.append(f"{tag}: duplicate id {q['id']}")
        seen_ids.add(q["id"])
        chash = taxonomy.content_hash(item["stem"], opts)
        if chash in seen_content:
            failures.append(f"{tag}: duplicate content (stem+options)")
        seen_content.add(chash)
        out.append(q)

    if failures:
        print("GOLD BUILD FAILED - fix these before shipping:", file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        raise SystemExit(1)

    out.sort(key=lambda q: (q["topic"], q["id"]))
    return out


def main() -> int:
    questions = build()
    out_path = os.path.join(_HERE, "cardcheck_gold.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(questions, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    counts = taxonomy.topic_counts(questions)
    print(f"GOLD OK - {len(questions)} authored Q&A pairs, all independently verified.")
    print(f"Wrote -> {out_path}\n")
    print("Authored gold counts per topic:")
    for topic in taxonomy.QUANT_TOPICS:
        print(f"  {topic:45s} {counts.get(topic, 0)}")
    diff_counts: Dict[str, int] = {}
    for q in questions:
        diff_counts[q["difficulty"]] = diff_counts.get(q["difficulty"], 0) + 1
    print("\nBy difficulty:", dict(sorted(diff_counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
