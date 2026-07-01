#!/usr/bin/env python3
"""Author + self-verify the GMATWiz SEED question set (writes seed.json).

These are ORIGINAL GMAT Quant Problem Solving questions written for GMATWiz,
spanning the PRD Section 5 coverage map (arithmetic + algebra; NO geometry, NO
Data Sufficiency). They are the guaranteed-usable content even if scraping is
blocked.

Every question is INDEPENDENTLY verified: a ``check`` callable recomputes the
answer from first principles (it does not read the labelled answer), locates the
matching option, and the build asserts that option equals the declared
``correct`` letter. The build fails loudly if any question's math is wrong,
options aren't distinct, or the schema is violated.

License for all items: ``authored-gmatwiz``.

Run:  python3 make_seed.py        # writes seed.json next to this file
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import re
import sys
from fractions import Fraction
from typing import Callable, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import taxonomy  # noqa: E402

SOURCE = "GMATWiz original (authored)"
LICENSE = "authored-gmatwiz"


# ---------------------------------------------------------------------------
# Verification helpers (used by per-question ``check`` callables)
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
    """Return the option letter whose numeric value matches ``value``."""
    tol = max(1e-9, rel_tol * max(1.0, abs(value)))
    for letter, text in options.items():
        v = _num(text)
        if v is not None and abs(v - value) <= tol:
            return letter
    return None


def _monomial_value(s: str, x: float) -> Optional[float]:
    """Evaluate a simple monomial like 'x^7', '3x^3', '12x^3', '5' at x."""
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
    """Return the option letter whose monomial matches ``func`` at all xs."""
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


# ---------------------------------------------------------------------------
# The authored questions.
# Each: topic, difficulty, stem, options(A-E), correct, explanation, check.
# ``check(options) -> letter`` recomputes the answer independently.
# ---------------------------------------------------------------------------
Q = taxonomy.PREFIX  # "gmat::quant"

QUESTIONS: List[Dict] = [
    # ===================== ARITHMETIC :: number_properties =====================
    {
        "topic": f"{Q}::arithmetic::number_properties",
        "difficulty": "medium",
        "stem": "What is the units digit of 7^53?",
        "options": {"A": "1", "B": "3", "C": "7", "D": "9", "E": "5"},
        "correct": "C",
        "explanation": "The units digit of powers of 7 cycles in a period of 4: 7, 9, 3, 1, "
                       "then repeats. Since 53 = 4(13) + 1, the units digit matches that of 7^1, "
                       "which is 7.",
        "check": lambda o: letter_for_value(o, (7 ** 53) % 10),
    },
    {
        "topic": f"{Q}::arithmetic::number_properties",
        "difficulty": "easy",
        "stem": "When the positive integer n is divided by 7, the remainder is 4. What is the "
                "remainder when 3n is divided by 7?",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
        "correct": "E",
        "explanation": "If n leaves remainder 4 on division by 7, then 3n leaves the same "
                       "remainder as 3(4) = 12. Since 12 = 7 + 5, the remainder is 5. "
                       "(Check with n = 11: 3(11) = 33 = 28 + 5.)",
        "check": lambda o: letter_for_value(o, (3 * 11) % 7),
    },
    {
        "topic": f"{Q}::arithmetic::number_properties",
        "difficulty": "hard",
        "stem": "How many distinct positive factors does 360 have?",
        "options": {"A": "12", "B": "16", "C": "18", "D": "20", "E": "24"},
        "correct": "E",
        "explanation": "Prime-factorize: 360 = 2^3 x 3^2 x 5^1. The number of factors is "
                       "(3+1)(2+1)(1+1) = 4 x 3 x 2 = 24.",
        "check": lambda o: letter_for_value(o, num_divisors(360)),
    },
    # ===================== ARITHMETIC :: fractions =====================
    {
        "topic": f"{Q}::arithmetic::fractions",
        "difficulty": "easy",
        "stem": "What is the value of 2/3 + 1/6 ?",
        "options": {"A": "1/2", "B": "2/3", "C": "5/6", "D": "1", "E": "7/6"},
        "correct": "C",
        "explanation": "Use a common denominator of 6: 2/3 = 4/6, so 4/6 + 1/6 = 5/6.",
        "check": lambda o: letter_for_value(o, float(Fraction(2, 3) + Fraction(1, 6))),
    },
    {
        "topic": f"{Q}::arithmetic::fractions",
        "difficulty": "medium",
        "stem": "A jar is 3/4 full of water. After 1/3 of the water is poured out, what "
                "fraction of the jar is then filled with water?",
        "options": {"A": "1/4", "B": "5/12", "C": "1/2", "D": "7/12", "E": "2/3"},
        "correct": "C",
        "explanation": "Pouring out 1/3 of the water leaves 2/3 of it. So the jar holds "
                       "3/4 x 2/3 = 6/12 = 1/2 of its capacity.",
        "check": lambda o: letter_for_value(o, float(Fraction(3, 4) * (1 - Fraction(1, 3)))),
    },
    # ===================== ARITHMETIC :: decimals =====================
    {
        "topic": f"{Q}::arithmetic::decimals",
        "difficulty": "easy",
        "stem": "What is the value of 0.2 x 0.05 ?",
        "options": {"A": "0.001", "B": "0.01", "C": "0.1", "D": "0.0001", "E": "1.0"},
        "correct": "B",
        "explanation": "Multiply 2 x 5 = 10, then place the decimal: 0.2 has one decimal place "
                       "and 0.05 has two, for three places total: 0.010 = 0.01.",
        "check": lambda o: letter_for_value(o, 0.2 * 0.05),
    },
    {
        "topic": f"{Q}::arithmetic::decimals",
        "difficulty": "medium",
        "stem": "When 3.14159 is rounded to the nearest hundredth, what is the result?",
        "options": {"A": "3.1", "B": "3.14", "C": "3.142", "D": "3.15", "E": "3.0"},
        "correct": "B",
        "explanation": "The hundredths digit is 4; the next digit (1) is less than 5, so we "
                       "round down and keep 3.14.",
        "check": lambda o: letter_for_value(o, round(3.14159, 2)),
    },
    # ===================== ARITHMETIC :: percents =====================
    {
        "topic": f"{Q}::arithmetic::percents",
        "difficulty": "easy",
        "stem": "What is 15% of 80?",
        "options": {"A": "8", "B": "10", "C": "12", "D": "15", "E": "20"},
        "correct": "C",
        "explanation": "15% = 0.15, and 0.15 x 80 = 12.",
        "check": lambda o: letter_for_value(o, 0.15 * 80),
    },
    {
        "topic": f"{Q}::arithmetic::percents",
        "difficulty": "medium",
        "stem": "The price of a stock first increased by 20% and then decreased by 10%. "
                "The final price is what percent of the original price?",
        "options": {"A": "90%", "B": "100%", "C": "108%", "D": "110%", "E": "112%"},
        "correct": "C",
        "explanation": "Apply the factors in sequence: 1.20 x 0.90 = 1.08, i.e. 108% of the "
                       "original price.",
        "check": lambda o: letter_for_value(o, 1.20 * 0.90 * 100),
    },
    {
        "topic": f"{Q}::arithmetic::percents",
        "difficulty": "hard",
        "stem": "After a 25% discount, a jacket sells for $90. What was its original price?",
        "options": {"A": "$112.50", "B": "$115", "C": "$120", "D": "$125", "E": "$135"},
        "correct": "C",
        "explanation": "A 25% discount means the sale price is 75% of the original: "
                       "0.75 x P = 90, so P = 90 / 0.75 = $120.",
        "check": lambda o: letter_for_value(o, 90 / 0.75),
    },
    # ===================== ARITHMETIC :: ratios_proportions =====================
    {
        "topic": f"{Q}::arithmetic::ratios_proportions",
        "difficulty": "easy",
        "stem": "The ratio of boys to girls in a class is 3 to 5. If there are 24 boys, "
                "how many girls are there?",
        "options": {"A": "15", "B": "30", "C": "36", "D": "40", "E": "45"},
        "correct": "D",
        "explanation": "Each ratio unit equals 24 / 3 = 8 students. Girls = 5 units = 5 x 8 = 40.",
        "check": lambda o: letter_for_value(o, 24 / 3 * 5),
    },
    {
        "topic": f"{Q}::arithmetic::ratios_proportions",
        "difficulty": "medium",
        "stem": "If 4 identical machines produce 240 widgets in one hour, how many widgets do "
                "7 such machines produce in one hour at the same rate?",
        "options": {"A": "360", "B": "400", "C": "420", "D": "480", "E": "560"},
        "correct": "C",
        "explanation": "Each machine makes 240 / 4 = 60 widgets per hour, so 7 machines make "
                       "7 x 60 = 420.",
        "check": lambda o: letter_for_value(o, 240 / 4 * 7),
    },
    # ===================== ARITHMETIC :: exponents_roots =====================
    {
        "topic": f"{Q}::arithmetic::exponents_roots",
        "difficulty": "medium",
        "stem": "If 2^x = 32, what is the value of x?",
        "options": {"A": "4", "B": "5", "C": "6", "D": "8", "E": "16"},
        "correct": "B",
        "explanation": "Write 32 as a power of 2: 32 = 2^5, so x = 5.",
        "check": lambda o: letter_for_value(o, math.log2(32)),
    },
    {
        "topic": f"{Q}::arithmetic::exponents_roots",
        "difficulty": "easy",
        "stem": "What is the value of sqrt(144) + sqrt(25) ?",
        "options": {"A": "13", "B": "15", "C": "17", "D": "19", "E": "169"},
        "correct": "C",
        "explanation": "sqrt(144) = 12 and sqrt(25) = 5, so the sum is 12 + 5 = 17.",
        "check": lambda o: letter_for_value(o, math.isqrt(144) + math.isqrt(25)),
    },
    # ===================== ARITHMETIC :: statistics =====================
    {
        "topic": f"{Q}::arithmetic::statistics",
        "difficulty": "easy",
        "stem": "The average (arithmetic mean) of 5 numbers is 14. What is the sum of the "
                "5 numbers?",
        "options": {"A": "60", "B": "65", "C": "70", "D": "75", "E": "80"},
        "correct": "C",
        "explanation": "Sum = average x count = 14 x 5 = 70.",
        "check": lambda o: letter_for_value(o, 5 * 14),
    },
    {
        "topic": f"{Q}::arithmetic::statistics",
        "difficulty": "medium",
        "stem": "What is the median of the list 3, 8, 12, 5, 21, 7 ?",
        "options": {"A": "6.5", "B": "7", "C": "7.5", "D": "8", "E": "10"},
        "correct": "C",
        "explanation": "Sort the list: 3, 5, 7, 8, 12, 21. With 6 values, the median is the "
                       "average of the 3rd and 4th: (7 + 8) / 2 = 7.5.",
        "check": lambda o: letter_for_value(o, __import__("statistics").median([3, 8, 12, 5, 21, 7])),
    },
    {
        "topic": f"{Q}::arithmetic::statistics",
        "difficulty": "hard",
        "stem": "The average (arithmetic mean) of 6 numbers is 10. When a seventh number is "
                "added to the list, the average becomes 12. What is the seventh number?",
        "options": {"A": "14", "B": "18", "C": "20", "D": "22", "E": "24"},
        "correct": "E",
        "explanation": "Sum of the first 6 is 6 x 10 = 60. After adding the 7th, the sum is "
                       "7 x 12 = 84. The seventh number is 84 - 60 = 24.",
        "check": lambda o: letter_for_value(o, 7 * 12 - 6 * 10),
    },
    # ===================== ARITHMETIC :: sets =====================
    {
        "topic": f"{Q}::arithmetic::sets",
        "difficulty": "medium",
        "stem": "In a group of 50 people, 30 like coffee and 25 like tea. If 10 like neither, "
                "how many like both coffee and tea?",
        "options": {"A": "5", "B": "10", "C": "15", "D": "20", "E": "25"},
        "correct": "C",
        "explanation": "People who like at least one drink: 50 - 10 = 40. By inclusion-exclusion, "
                       "both = 30 + 25 - 40 = 15.",
        "check": lambda o: letter_for_value(o, 30 + 25 - (50 - 10)),
    },
    {
        "topic": f"{Q}::arithmetic::sets",
        "difficulty": "medium",
        "stem": "Of 40 students, 25 are enrolled in Spanish and 20 in French. If every student "
                "takes at least one of these two languages, how many take both?",
        "options": {"A": "5", "B": "10", "C": "15", "D": "20", "E": "45"},
        "correct": "A",
        "explanation": "Since everyone takes at least one, the union is 40. By inclusion-exclusion, "
                       "both = 25 + 20 - 40 = 5.",
        "check": lambda o: letter_for_value(o, 25 + 20 - 40),
    },
    # ===================== ARITHMETIC :: counting =====================
    {
        "topic": f"{Q}::arithmetic::counting",
        "difficulty": "medium",
        "stem": "In how many different ways can all the letters of the word LOGIC be arranged? "
                "(All five letters are distinct.)",
        "options": {"A": "24", "B": "60", "C": "100", "D": "120", "E": "720"},
        "correct": "D",
        "explanation": "Five distinct letters can be arranged in 5! = 5 x 4 x 3 x 2 x 1 = 120 ways.",
        "check": lambda o: letter_for_value(o, math.factorial(5)),
    },
    {
        "topic": f"{Q}::arithmetic::counting",
        "difficulty": "medium",
        "stem": "A committee of 3 people is to be selected from a group of 6 people. How many "
                "different committees are possible?",
        "options": {"A": "18", "B": "20", "C": "24", "D": "120", "E": "216"},
        "correct": "B",
        "explanation": "Order does not matter, so use combinations: 6C3 = 6! / (3! x 3!) = 20.",
        "check": lambda o: letter_for_value(o, math.comb(6, 3)),
    },
    # ===================== ARITHMETIC :: probability =====================
    {
        "topic": f"{Q}::arithmetic::probability",
        "difficulty": "easy",
        "stem": "A bag contains 4 red and 6 blue marbles. If one marble is drawn at random, "
                "what is the probability that it is red?",
        "options": {"A": "1/5", "B": "2/5", "C": "1/2", "D": "3/5", "E": "2/3"},
        "correct": "B",
        "explanation": "P(red) = favorable / total = 4 / (4 + 6) = 4/10 = 2/5.",
        "check": lambda o: letter_for_value(o, 4 / 10),
    },
    {
        "topic": f"{Q}::arithmetic::probability",
        "difficulty": "hard",
        "stem": "A box contains 3 defective and 7 non-defective bulbs. If 2 bulbs are drawn at "
                "random without replacement, what is the probability that both are defective?",
        "options": {"A": "1/15", "B": "1/10", "C": "9/100", "D": "1/5", "E": "3/20"},
        "correct": "A",
        "explanation": "P(both defective) = (3/10) x (2/9) = 6/90 = 1/15.",
        "check": lambda o: letter_for_value(o, (3 / 10) * (2 / 9)),
    },
    # ===================== ALGEBRA :: linear_equations =====================
    {
        "topic": f"{Q}::algebra::linear_equations",
        "difficulty": "easy",
        "stem": "If 5x - 3 = 2x + 12, what is the value of x?",
        "options": {"A": "3", "B": "4", "C": "5", "D": "6", "E": "9"},
        "correct": "C",
        "explanation": "Subtract 2x from both sides: 3x - 3 = 12. Add 3: 3x = 15, so x = 5.",
        "check": lambda o: letter_for_value(o, (12 + 3) / (5 - 2)),
    },
    {
        "topic": f"{Q}::algebra::linear_equations",
        "difficulty": "medium",
        "stem": "If x + y = 10 and x - y = 4, what is the value of xy?",
        "options": {"A": "16", "B": "21", "C": "24", "D": "25", "E": "40"},
        "correct": "B",
        "explanation": "Adding the equations gives 2x = 14, so x = 7; then y = 3. "
                       "Therefore xy = 7 x 3 = 21.",
        "check": lambda o: (lambda x: letter_for_value(o, x * (10 - x)))((10 + 4) / 2),
    },
    {
        "topic": f"{Q}::algebra::linear_equations",
        "difficulty": "medium",
        "stem": "Tickets cost $8 for adults and $5 for children. If 20 tickets were sold for a "
                "total of $139, how many adult tickets were sold?",
        "options": {"A": "9", "B": "11", "C": "13", "D": "15", "E": "17"},
        "correct": "C",
        "explanation": "Let a be adult tickets; children = 20 - a. Then 8a + 5(20 - a) = 139, "
                       "so 3a + 100 = 139, giving 3a = 39 and a = 13.",
        "check": lambda o: letter_for_value(o, (139 - 5 * 20) / (8 - 5)),
    },
    # ===================== ALGEBRA :: quadratics =====================
    {
        "topic": f"{Q}::algebra::quadratics",
        "difficulty": "medium",
        "stem": "If x^2 - 7x + 12 = 0 and x > 3, what is the value of x?",
        "options": {"A": "2", "B": "3", "C": "4", "D": "6", "E": "12"},
        "correct": "C",
        "explanation": "Factor: (x - 3)(x - 4) = 0, so x = 3 or x = 4. Since x > 3, x = 4.",
        "check": lambda o: letter_for_value(o, max(quad_roots(1, -7, 12))),
    },
    {
        "topic": f"{Q}::algebra::quadratics",
        "difficulty": "hard",
        "stem": "If x^2 - 5x = 14, which of the following is a possible value of x?",
        "options": {"A": "-7", "B": "-1", "C": "2", "D": "5", "E": "7"},
        "correct": "E",
        "explanation": "Rewrite as x^2 - 5x - 14 = 0 and factor: (x - 7)(x + 2) = 0, so "
                       "x = 7 or x = -2. Of the choices, only 7 appears.",
        "check": lambda o: letter_for_any_root(o, quad_roots(1, -5, -14)),
    },
    # ===================== ALGEBRA :: inequalities =====================
    {
        "topic": f"{Q}::algebra::inequalities",
        "difficulty": "easy",
        "stem": "What is the least integer value of x for which 3x - 5 > 7 ?",
        "options": {"A": "3", "B": "4", "C": "5", "D": "6", "E": "7"},
        "correct": "C",
        "explanation": "Add 5: 3x > 12, so x > 4. The least integer strictly greater than 4 is 5.",
        "check": lambda o: letter_for_value(o, math.floor((7 + 5) / 3) + 1),
    },
    {
        "topic": f"{Q}::algebra::inequalities",
        "difficulty": "medium",
        "stem": "If -2 < x < 5 and x is an integer, how many possible values can x have?",
        "options": {"A": "5", "B": "6", "C": "7", "D": "8", "E": "9"},
        "correct": "B",
        "explanation": "The integers strictly between -2 and 5 are -1, 0, 1, 2, 3, 4 — that is "
                       "6 values.",
        "check": lambda o: letter_for_value(o, sum(1 for x in range(-20, 21) if -2 < x < 5)),
    },
    # ===================== ALGEBRA :: absolute_value =====================
    {
        "topic": f"{Q}::algebra::absolute_value",
        "difficulty": "medium",
        "stem": "If |x - 3| = 7, what is the sum of all possible values of x?",
        "options": {"A": "-4", "B": "3", "C": "6", "D": "10", "E": "14"},
        "correct": "C",
        "explanation": "Either x - 3 = 7 (so x = 10) or x - 3 = -7 (so x = -4). "
                       "Their sum is 10 + (-4) = 6.",
        "check": lambda o: letter_for_value(o, (3 + 7) + (3 - 7)),
    },
    {
        "topic": f"{Q}::algebra::absolute_value",
        "difficulty": "easy",
        "stem": "How many integer values of x satisfy |x| < 4 ?",
        "options": {"A": "3", "B": "4", "C": "6", "D": "7", "E": "8"},
        "correct": "D",
        "explanation": "|x| < 4 means -4 < x < 4. The integers are -3, -2, -1, 0, 1, 2, 3 — "
                       "that is 7 values.",
        "check": lambda o: letter_for_value(o, sum(1 for x in range(-20, 21) if abs(x) < 4)),
    },
    # ===================== ALGEBRA :: functions =====================
    {
        "topic": f"{Q}::algebra::functions",
        "difficulty": "easy",
        "stem": "If f(x) = 2x^2 - 3x + 1, what is f(3)?",
        "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "16"},
        "correct": "C",
        "explanation": "f(3) = 2(3^2) - 3(3) + 1 = 18 - 9 + 1 = 10.",
        "check": lambda o: letter_for_value(o, 2 * 3 ** 2 - 3 * 3 + 1),
    },
    {
        "topic": f"{Q}::algebra::functions",
        "difficulty": "medium",
        "stem": "For all numbers a and b, the operation # is defined by a # b = a^2 - b. "
                "What is the value of 4 # 5?",
        "options": {"A": "3", "B": "6", "C": "9", "D": "11", "E": "21"},
        "correct": "D",
        "explanation": "Substitute into the definition: 4 # 5 = 4^2 - 5 = 16 - 5 = 11.",
        "check": lambda o: letter_for_value(o, 4 ** 2 - 5),
    },
    # ===================== ALGEBRA :: sequences =====================
    {
        "topic": f"{Q}::algebra::sequences",
        "difficulty": "medium",
        "stem": "In an arithmetic sequence, the first term is 5 and the common difference is 4. "
                "What is the 10th term?",
        "options": {"A": "36", "B": "40", "C": "41", "D": "45", "E": "49"},
        "correct": "C",
        "explanation": "The nth term is a + (n - 1)d = 5 + (10 - 1)(4) = 5 + 36 = 41.",
        "check": lambda o: letter_for_value(o, 5 + (10 - 1) * 4),
    },
    {
        "topic": f"{Q}::algebra::sequences",
        "difficulty": "hard",
        "stem": "The first term of a geometric sequence is 3 and the common ratio is 2. "
                "What is the sum of the first 5 terms?",
        "options": {"A": "45", "B": "48", "C": "93", "D": "96", "E": "189"},
        "correct": "C",
        "explanation": "The terms are 3, 6, 12, 24, 48; their sum is 93. "
                       "(Or use 3 x (2^5 - 1)/(2 - 1) = 3 x 31 = 93.)",
        "check": lambda o: letter_for_value(o, sum(3 * 2 ** k for k in range(5))),
    },
    # ===================== ALGEBRA :: expressions =====================
    {
        "topic": f"{Q}::algebra::expressions",
        "difficulty": "easy",
        "stem": "For any nonzero x, which of the following is equivalent to (x^3)(x^4) ?",
        "options": {"A": "x^7", "B": "x^12", "C": "x^1", "D": "2x^7", "E": "x^34"},
        "correct": "A",
        "explanation": "When multiplying powers with the same base, add the exponents: "
                       "x^3 x x^4 = x^(3+4) = x^7.",
        "check": lambda o: letter_for_monomial(o, lambda x: x ** 7),
    },
    {
        "topic": f"{Q}::algebra::expressions",
        "difficulty": "medium",
        "stem": "For any nonzero x, which of the following is equivalent to (6x^5) / (2x^2) ?",
        "options": {"A": "3x^3", "B": "3x^7", "C": "4x^3", "D": "3x^2", "E": "12x^3"},
        "correct": "A",
        "explanation": "Divide the coefficients (6/2 = 3) and subtract the exponents "
                       "(5 - 2 = 3): the result is 3x^3.",
        "check": lambda o: letter_for_monomial(o, lambda x: 3 * x ** 3),
    },
    # ===================== ALGEBRA :: word_problems =====================
    {
        "topic": f"{Q}::algebra::word_problems",
        "difficulty": "medium",
        "stem": "A train travels 360 miles in 4 hours. At the same constant rate, how many "
                "miles will it travel in 7 hours?",
        "options": {"A": "540", "B": "600", "C": "630", "D": "720", "E": "840"},
        "correct": "C",
        "explanation": "The rate is 360 / 4 = 90 miles per hour, so in 7 hours it covers "
                       "90 x 7 = 630 miles.",
        "check": lambda o: letter_for_value(o, 360 / 4 * 7),
    },
    {
        "topic": f"{Q}::algebra::word_problems",
        "difficulty": "hard",
        "stem": "Pipe A can fill a tank in 6 hours, and pipe B can fill the same tank in "
                "12 hours. Working together, how many hours will they take to fill the tank?",
        "options": {"A": "3", "B": "4", "C": "6", "D": "8", "E": "9"},
        "correct": "B",
        "explanation": "Combined rate = 1/6 + 1/12 = 2/12 + 1/12 = 3/12 = 1/4 tank per hour, "
                       "so the time is the reciprocal: 4 hours.",
        "check": lambda o: letter_for_value(o, 1 / (1 / 6 + 1 / 12)),
    },
    {
        "topic": f"{Q}::algebra::word_problems",
        "difficulty": "hard",
        "stem": "How many liters of a 20% salt solution must be added to 10 liters of a 50% "
                "salt solution to produce a 30% salt solution?",
        "options": {"A": "10", "B": "15", "C": "20", "D": "25", "E": "30"},
        "correct": "C",
        "explanation": "Let x be the liters of 20% solution. Salt balance: 0.20x + 0.50(10) = "
                       "0.30(x + 10). Then 0.20x + 5 = 0.30x + 3, so 2 = 0.10x and x = 20.",
        "check": lambda o: letter_for_value(o, (0.50 * 10 - 0.30 * 10) / (0.30 - 0.20)),
    },
    {
        "topic": f"{Q}::algebra::word_problems",
        "difficulty": "medium",
        "stem": "$2,000 is invested at 5% simple annual interest. How much interest is earned "
                "after 3 years?",
        "options": {"A": "$100", "B": "$200", "C": "$300", "D": "$315", "E": "$350"},
        "correct": "C",
        "explanation": "Simple interest = principal x rate x time = 2000 x 0.05 x 3 = $300.",
        "check": lambda o: letter_for_value(o, 2000 * 0.05 * 3),
    },
]


# ---------------------------------------------------------------------------
# Build + verify
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def build() -> List[Dict]:
    out: List[Dict] = []
    seen_ids = set()
    failures: List[str] = []
    ts = now_iso()

    for i, item in enumerate(QUESTIONS):
        tag = f"Q{i+1} [{item['topic']}]"
        opts = item["options"]

        # Structural checks.
        if set(opts.keys()) != set(taxonomy.OPTION_KEYS):
            failures.append(f"{tag}: options must be exactly A-E")
            continue
        distinct = {str(v).strip().lower() for v in opts.values()}
        if len(distinct) != 5:
            failures.append(f"{tag}: options are not all distinct")
        if item["correct"] not in taxonomy.OPTION_KEYS:
            failures.append(f"{tag}: correct '{item['correct']}' not in A-E")

        # The core: independently recompute the answer and confirm it matches.
        try:
            computed = item["check"](opts)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{tag}: check() raised {type(exc).__name__}: {exc}")
            computed = None
        if computed is None:
            failures.append(f"{tag}: check() could not locate the answer among the options")
        elif computed != item["correct"]:
            failures.append(
                f"{tag}: VERIFICATION MISMATCH — recomputed answer is '{computed}' "
                f"but labelled correct is '{item['correct']}'"
            )

        q = taxonomy.make_question(
            id=taxonomy.make_id("seed", item["stem"], opts),
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
        print("SEED BUILD FAILED — fix these before shipping:", file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        raise SystemExit(1)

    out.sort(key=lambda q: (q["topic"], q["id"]))
    return out


def main() -> int:
    questions = build()
    out_path = os.path.join(_HERE, "seed.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(questions, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    counts = taxonomy.topic_counts(questions)
    print(f"SEED OK — {len(questions)} authored questions, all independently verified.")
    print(f"Wrote -> {out_path}\n")
    print("Authored counts per topic:")
    for topic in taxonomy.ALL_TOPICS:
        print(f"  {topic:45s} {counts.get(topic, 0)}")
    diff_counts: Dict[str, int] = {}
    for q in questions:
        diff_counts[q["difficulty"]] = diff_counts.get(q["difficulty"], 0) + 1
    print("\nBy difficulty:", dict(sorted(diff_counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
