# -*- coding: utf-8 -*-
"""
Content source of truth for GMATWiz Quant (Problem Solving) lessons.
Consumed by build.py. 18 leaf topics from PRD Section 5 (arithmetic + algebra).

Each topic = retrieval opening + I-do + we-do[] + you-do[] + mastery_check.
Application-first (SPOV2): you_do explanations are revealed after an attempt
(build.finalize sets reveal_explanation_after_attempt + error-log tags).
All math is authored to be calculator-free and verified in each explanation.
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
    return kw


# High-trust, stable primary sources reused across topics.
GMAT = {
    "name": "GMAC — GMAT Focus Edition (official exam overview)",
    "url": "https://www.mba.com/exams/gmat-focus-edition",
    "note": "Official exam structure and Quantitative Reasoning scope.",
}
OSX_PREALG = "https://openstax.org/details/books/prealgebra-2e"
OSX_ELEM = "https://openstax.org/details/books/elementary-algebra-2e"
OSX_INT = "https://openstax.org/details/books/intermediate-algebra-2e"
OSX_STAT = "https://openstax.org/details/books/introductory-statistics"
KHAN_ARITH = "https://www.khanacademy.org/math/arithmetic"
KHAN_PREALG = "https://www.khanacademy.org/math/pre-algebra"
KHAN_ALG = "https://www.khanacademy.org/math/algebra"
KHAN_ALG2 = "https://www.khanacademy.org/math/algebra2"
KHAN_STAT = "https://www.khanacademy.org/math/statistics-probability"


# ===========================================================================
# ARITHMETIC
# ===========================================================================

T_number_properties = topic(
    topic_id="gmat::quant::arithmetic::number_properties",
    slug="number-properties",
    title="Number Properties",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["whole-number multiplication & division facts", "place value"],
    learning_objectives=[
        "Apply even/odd and sign rules to predict the result of an expression.",
        "Use divisibility rules (2, 3, 5, 6, 9, 10) and the idea that divisibility by a composite means divisibility by its prime parts.",
        "Prime-factorize an integer and use it to count factors and find GCD/LCM.",
        "Translate 'must be true' number-property statements into fast tests.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Whole-number multiplication/division facts and place value.",
        "do_now": {
            "instructions": "No notes, no calculator. Answer from memory in 4 minutes.",
            "items": [
                {"prompt": "List all positive factors of 24.", "answer": "1, 2, 3, 4, 6, 8, 12, 24", "targets": "factors"},
                {"prompt": "Is 51 prime? Show why in one product.", "answer": "No: 51 = 3 × 17.", "targets": "primes / composites"},
                {"prompt": "Compute 7 × 8 and 9 × 6.", "answer": "56 and 54.", "targets": "multiplication fluency"},
                {"prompt": "Is 0 even or odd?", "answer": "Even (0 = 2 × 0).", "targets": "even/odd definition"},
                {"prompt": "What must be true for a number to be divisible by 6?", "answer": "Divisible by 2 AND by 3.", "targets": "divisibility composition"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Surfaces factors, primes, even/odd, and the key idea that divisibility by a composite equals divisibility by its prime parts — exactly the tools today extends to factor-counting and GCD/LCM.",
            "if_students_struggle": "If factors of 24 are shaky, rebuild with a factor-pair ladder (1×24, 2×12, 3×8, 4×6) before moving on; today's factor counting depends on it.",
            "questions": [
                {"prompt": "Compute 7 × 8 and 9 × 6.", "answer": "56 and 54.", "targets": "multiplication facts (prerequisite)"},
                {"prompt": "Compute 56 ÷ 8 and 63 ÷ 9.", "answer": "7 and 7.", "targets": "division facts (prerequisite)"},
                {"prompt": "In 3,204, what is the value of the digit 2?", "answer": "200 (the hundreds place).", "targets": "place value (prerequisite)"},
            ],
        },
        "prior_knowledge_bridge": "You just found the factors of 24 by trial. That works for small numbers, but the GMAT asks about numbers like 72 — or 2³ × 3² × 5 — where listing is far too slow. Today we replace listing with prime factorization, the 'DNA' of an integer, which lets you count factors and find GCD/LCM in seconds.",
        "learning_intention": "By the end you can prime-factorize an integer and use it to count its factors, find GCD/LCM, and settle 'must be true' even/odd and divisibility questions without listing.",
        "success_criteria": [
            "I can write any integer up to ~200 as a product of primes.",
            "I can count an integer's positive factors from its prime factorization.",
            "I can predict the even/odd and the sign of an expression and justify it.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now on screen; learners answer Q1–5 from memory, silent, no notes."},
            {"time": "4:00–6:00", "move": "Cold-call answers; spotlight Q5 — 'divisible by 6' = divisible by 2 AND 3."},
            {"time": "6:00–8:00", "move": "Bridge: listing factors of 72 is slow; introduce prime factorization as the shortcut."},
            {"time": "8:00–9:00", "move": "State learning intention + success criteria on the board."},
            {"time": "9:00–10:00", "move": "Move to I do: count the factors of 72 by reasoning aloud."},
        ],
    },
    i_do=item(
        "i_do", "How many distinct positive factors does 72 have?",
        opts("6", "8", "10", "12", "14"), "D",
        "72 = 2³ × 3². The number of positive factors is (3+1)(2+1) = 4 × 3 = 12.",
        difficulty="medium",
        think_aloud_steps=[
            "Prime-factorize: 72 = 8 × 9 = 2³ × 3².",
            "Any factor uses 0–3 twos (4 choices) and 0–2 threes (3 choices).",
            "Independent choices multiply: 4 × 3 = 12 factors.",
            "Spot-check by listing: 1, 2, 3, 4, 6, 8, 9, 12, 18, 24, 36, 72 — twelve.",
        ],
        key_takeaway="Number of positive factors = product of (each prime's exponent + 1).",
    ),
    we_do=[
        item(
            "we_1", "If a is odd and b is even, which of the following must be ODD?",
            opts("a + b", "ab", "b − 2", "a + b + 1", "2a"), "A",
            "a is odd and b is even, so a + b = odd + even = odd. ab and 2a have an even factor (even); b − 2 is even − even = even; a + b + 1 flips a + b to even. Only a + b is odd.",
            difficulty="easy",
            scaffold_hints=[
                "Parity rules: even ± even = even; odd ± even = odd.",
                "Anything multiplied by an even number is even.",
                "Test with a = 3, b = 2 and check each option's parity.",
            ],
            immediate_feedback={
                "if_correct": "Right — odd + even is always odd; the ×even and +even options are forced even.",
                "if_incorrect": "Re-check parity: B and E have an even factor (even); C subtracts an even number (stays even); D adds 1 to an odd, making it even.",
            },
        ),
        item(
            "we_2", "What is the greatest common divisor (GCD) of 48 and 60?",
            opts("4", "6", "12", "16", "24"), "C",
            "48 = 2⁴ × 3 and 60 = 2² × 3 × 5. The GCD takes each SHARED prime at its LOWEST power: 2² × 3 = 12.",
            difficulty="medium",
            scaffold_hints=[
                "Prime-factorize both numbers first.",
                "GCD uses only the primes they share, each at its smaller exponent.",
                "Shared primes: 2 (lowest power 2²) and 3 (lowest power 3¹).",
            ],
            immediate_feedback={
                "if_correct": "Yes — 2² × 3 = 12 divides both, and nothing larger does.",
                "if_incorrect": "Don't multiply every prime. 5 appears only in 60, so it can't be in the GCD; use shared primes at their lowest exponent.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "If the product of two integers is odd, which of the following MUST be true?",
            opts("Both integers are odd", "Both integers are even", "Exactly one integer is even", "Their product is divisible by 2", "At least one integer is even"), "A",
            "A product is odd only when every factor is odd; a single even factor would make the product even. So both integers must be odd. Every other option requires or implies an even factor.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "Which of the following is a multiple of BOTH 4 and 6?",
            opts("18", "28", "36", "42", "54"), "C",
            "A number divisible by both 4 and 6 must be divisible by their LCM, 12. Only 36 = 12 × 3 qualifies (18, 28, 42, 54 each fail divisibility by 4 or by 6).",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "If n = 2³ × 3² × 5, how many distinct positive factors does n have?",
            opts("6", "10", "12", "18", "24"), "E",
            "Factor count = product of (exponent + 1) over all primes: (3+1)(2+1)(1+1) = 4 × 3 × 2 = 24.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "If p and q are distinct prime numbers, each greater than 2, which of the following MUST be even?",
            opts("p + q", "pq", "2p + 1", "pq + 2", "p + q + 1"), "A",
            "Primes greater than 2 are odd. Odd + odd = even, so p + q is even. pq is odd; pq + 2 stays odd; 2p + 1 is odd; p + q + 1 is even + 1 = odd. Only p + q must be even.",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "What is the least common multiple (LCM) of 9 and 12?",
                opts("18", "24", "36", "72", "108"), "C",
                "9 = 3² and 12 = 2² × 3. The LCM takes each prime at its HIGHEST power: 2² × 3² = 36.",
                difficulty="medium",
            ),
            item(
                "mc_2", "How many distinct prime factors does 84 have?",
                opts("2", "3", "4", "5", "6"), "B",
                "84 = 2² × 3 × 7. The distinct primes are 2, 3, and 7 — three of them (count distinct primes, not total factors).",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Prealgebra 2e — Integers, factors, multiples, primes", "url": OSX_PREALG, "note": "Free peer-reviewed text: divisibility, primes, LCM/GCD.", "primary": True},
        {"name": "Khan Academy — Factors and multiples", "url": KHAN_ARITH, "note": "Short videos + practice on factors, primes, divisibility."},
        GMAT,
    ],
    tags=["arithmetic", "number-properties", "divisibility", "primes", "factors", "gcd", "lcm", "even-odd"],
)

T_fractions = topic(
    topic_id="gmat::quant::arithmetic::fractions",
    slug="fractions",
    title="Fractions",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["number properties (factors, LCM)", "whole-number division"],
    learning_objectives=[
        "Add and subtract fractions using a common denominator; simplify results.",
        "Multiply fractions and divide by multiplying by the reciprocal.",
        "Convert between mixed numbers and improper fractions.",
        "Find a fraction 'of' a quantity, including a fraction of what remains.",
        "Compare fractions quickly using a common denominator or benchmarks.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Factors and LCM (for common denominators) and division.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Write 18/24 in lowest terms.", "answer": "3/4 (divide top and bottom by 6).", "targets": "simplifying via common factors"},
                {"prompt": "Compute 3/8 + 1/8.", "answer": "4/8 = 1/2.", "targets": "same-denominator addition"},
                {"prompt": "What is the LCM of 4 and 6?", "answer": "12.", "targets": "common denominators"},
                {"prompt": "Convert 2 1/3 to an improper fraction.", "answer": "7/3.", "targets": "mixed → improper"},
                {"prompt": "Why can't 1/3 + 1/4 equal 2/7?", "answer": "The pieces are different sizes; you must use a common denominator first.", "targets": "conceptual setup for today"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves simplifying, same-denominator addition, and LCM — the prerequisites for adding unlike fractions and for the 'fraction of a quantity' problems the GMAT loves.",
            "if_students_struggle": "If LCM is shaky, recap with multiples lists (4: 4,8,12 …; 6: 6,12) before today's unlike-denominator work; the whole topic rides on it.",
            "questions": [
                {"prompt": "Write 18/24 in lowest terms.", "answer": "3/4 (divide top and bottom by 6).", "targets": "factors (number properties)"},
                {"prompt": "What is the LCM of 4 and 6?", "answer": "12.", "targets": "LCM (number properties)"},
                {"prompt": "Compute 84 ÷ 7.", "answer": "12.", "targets": "whole-number division"},
            ],
        },
        "prior_knowledge_bridge": "You added 3/8 + 1/8 easily because the pieces were the same size. The Do-Now's last question is the whole point of today: when denominators differ, you can't just add tops. You'll use the LCM skill you just retrieved to make the pieces the same size first — then multiply, divide, and take fractions of quantities the way GMAT word problems demand.",
        "learning_intention": "By the end you can add, subtract, multiply, and divide fractions (including mixed numbers) and compute a fraction of a quantity — simplifying as you go.",
        "success_criteria": [
            "I can combine two unlike fractions by rewriting them over a common denominator.",
            "I can divide fractions by multiplying by the reciprocal.",
            "I can answer a 'fraction of a quantity' word problem in one clean setup.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now on screen; silent retrieval of Q1–5."},
            {"time": "4:00–6:00", "move": "Check answers; dwell on Q5 — different-sized pieces need a common denominator."},
            {"time": "6:00–8:00", "move": "Bridge: reuse LCM to make pieces equal; preview 'of' = multiply."},
            {"time": "8:00–9:00", "move": "State learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: the partially-emptied jar problem."},
        ],
    },
    i_do=item(
        "i_do", "A jar is 3/4 full of water. If 1/3 of the water is poured out, what fraction of the jar is now filled?",
        opts("1/2", "5/12", "1/4", "7/12", "2/3"), "A",
        "Pouring out 1/3 of the water leaves 2/3 of it. Remaining = 2/3 × 3/4 = 6/12 = 1/2 of the jar.",
        difficulty="medium",
        think_aloud_steps=[
            "The jar starts at 3/4 full.",
            "Removing 1/3 of the water leaves 2/3 of the water.",
            "'Of' means multiply: 2/3 × 3/4 = (2×3)/(3×4) = 6/12.",
            "Simplify 6/12 = 1/2. The jar is half full.",
        ],
        key_takeaway="'Of' means multiply; 'a fraction of what's left' multiplies the leftover fraction, not the original amount.",
    ),
    we_do=[
        item(
            "we_1", "Compute 5/6 − 3/8.",
            opts("1/4", "11/24", "1/2", "13/24", "7/24"), "B",
            "LCD of 6 and 8 is 24: 5/6 = 20/24 and 3/8 = 9/24, so 20/24 − 9/24 = 11/24.",
            difficulty="easy",
            scaffold_hints=[
                "Find the LCD of 6 and 8 — it's 24.",
                "Rewrite: 5/6 = 20/24, 3/8 = 9/24.",
                "Subtract the numerators over 24.",
            ],
            immediate_feedback={
                "if_correct": "Right — 20/24 − 9/24 = 11/24, already in lowest terms.",
                "if_incorrect": "Don't subtract numerators and denominators separately. Convert both to /24 first.",
            },
        ),
        item(
            "we_2", "What is 2/3 ÷ 4/9?",
            opts("8/27", "3/4", "3/2", "2/3", "6"), "C",
            "Dividing by a fraction = multiplying by its reciprocal: 2/3 ÷ 4/9 = 2/3 × 9/4 = 18/12 = 3/2.",
            difficulty="medium",
            scaffold_hints=[
                "Keep–change–flip: dividing by 4/9 means multiplying by 9/4.",
                "2/3 × 9/4. Cancel the 3 into the 9 first.",
                "= 2 × 3 / 4 = 6/4 = 3/2.",
            ],
            immediate_feedback={
                "if_correct": "Yes — reciprocal then simplify gives 3/2.",
                "if_incorrect": "8/27 is the trap from multiplying instead of inverting. Flip the divisor: × 9/4.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "On a test, 3/5 of the questions are quantitative and 1/4 of the remaining questions are geometry. What fraction of all the questions are geometry?",
            opts("1/10", "1/20", "3/20", "2/9", "1/5"), "A",
            "Remaining after quant = 1 − 3/5 = 2/5. Geometry = 1/4 × 2/5 = 2/20 = 1/10.",
            difficulty="medium", target_seconds=90,
        ),
        item(
            "you_2", "Which of these is the greatest: 5/8, 7/12, or 2/3?",
            opts("5/8", "7/12", "2/3", "They are equal", "Cannot be determined"), "C",
            "Common denominator 24: 5/8 = 15/24, 7/12 = 14/24, 2/3 = 16/24. The largest is 2/3.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "If 3/4 of a number is 18, what is 5/6 of the same number?",
            opts("15", "20", "22", "24", "30"), "B",
            "If (3/4)x = 18 then x = 24. Then (5/6)(24) = 20.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "A tank is 2/5 full. After adding 12 liters it is 7/10 full. What is the tank's full capacity, in liters?",
            opts("30", "36", "40", "48", "60"), "C",
            "The added water is 7/10 − 2/5 = 7/10 − 4/10 = 3/10 of the tank = 12 L, so capacity = 12 ÷ 3/10 = 40 liters.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Compute 7/10 + 2/15.",
                opts("5/6", "9/25", "3/5", "11/15", "9/30"), "A",
                "LCD 30: 7/10 = 21/30, 2/15 = 4/30; sum = 25/30 = 5/6.",
                difficulty="medium",
            ),
            item(
                "mc_2", "If 2/3 of a number is 10, what is the number?",
                opts("20/3", "15", "20", "30", "7.5"), "B",
                "(2/3)x = 10 → x = 10 × 3/2 = 15.",
                difficulty="easy",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Prealgebra 2e — Fractions", "url": OSX_PREALG, "note": "Operations with fractions, mixed numbers, and 'of' problems.", "primary": True},
        {"name": "Khan Academy — Fractions", "url": KHAN_ARITH, "note": "Practice on add/subtract/multiply/divide and comparing fractions."},
        GMAT,
    ],
    tags=["arithmetic", "fractions", "common-denominator", "reciprocal", "fraction-of-quantity"],
)


T_decimals = topic(
    topic_id="gmat::quant::arithmetic::decimals",
    slug="decimals",
    title="Decimals",
    domain="Arithmetic",
    estimated_minutes=20,
    prerequisites=["place value", "fractions"],
    learning_objectives=[
        "Multiply and divide decimals by tracking decimal places and shifting by powers of 10.",
        "Convert fluently among fractions, decimals, and percents.",
        "Round and estimate to sanity-check the size of an answer.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Place value and the fraction ↔ decimal link.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Write 0.75 as a fraction in lowest terms.", "answer": "3/4.", "targets": "decimal → fraction"},
                {"prompt": "Compute 0.2 × 0.3.", "answer": "0.06.", "targets": "decimal multiplication"},
                {"prompt": "Round 3.467 to the nearest hundredth.", "answer": "3.47.", "targets": "rounding"},
                {"prompt": "What fraction equals 0.125?", "answer": "1/8.", "targets": "common decimal–fraction pairs"},
                {"prompt": "Why is 0.2 × 0.3 = 0.06, not 0.6?", "answer": "Multiply the digits (2 × 3 = 6), then place the point by the TOTAL decimal places (1 + 1 = 2).", "targets": "place-value reasoning for today"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves decimal–fraction conversions and the decimal-place rule for multiplication — the foundation for the division and size-estimation problems coming up.",
            "if_students_struggle": "If place counting is shaky, model 0.2 × 0.3 as (2/10)(3/10) = 6/100 = 0.06 to anchor the rule in fractions.",
            "questions": [
                {"prompt": "In 5.36, which digit is in the tenths place?", "answer": "3.", "targets": "place value"},
                {"prompt": "Write 0.75 as a fraction in lowest terms.", "answer": "3/4.", "targets": "fractions"},
                {"prompt": "What fraction equals 0.125?", "answer": "1/8.", "targets": "fractions"},
            ],
        },
        "prior_knowledge_bridge": "Q5 explains the rule you'll lean on all lesson: a decimal is just a fraction over a power of ten. Once you see 0.2 = 2/10, multiplying and dividing decimals becomes counting places and shifting by powers of 10 — and converting to fractions is often the fastest GMAT move.",
        "learning_intention": "By the end you can multiply and divide decimals reliably, convert among fractions/decimals/percents, and estimate to check an answer's size.",
        "success_criteria": [
            "I can divide by a decimal by shifting both numbers to make the divisor whole.",
            "I can convert a decimal to a reduced fraction and back.",
            "I can predict roughly how big an answer should be before computing.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; dwell on Q5's place-value reasoning."},
            {"time": "6:00–8:00", "move": "Bridge: decimals are fractions over powers of 10; preview division by shifting."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: 0.0036 ÷ 0.04."},
        ],
    },
    i_do=item(
        "i_do", "Which of the following is equal to 0.0036 ÷ 0.04?",
        opts("0.9", "0.09", "0.009", "9", "0.0009"), "B",
        "Multiply both numbers by 100 to make the divisor whole: 0.0036 ÷ 0.04 = 0.36 ÷ 4 = 0.09.",
        difficulty="medium",
        think_aloud_steps=[
            "Dividing by a decimal is awkward; make the divisor a whole number.",
            "Multiply BOTH by 100: 0.0036 → 0.36 and 0.04 → 4.",
            "0.36 ÷ 4 = 0.09.",
            "Size check: dividing by the small number 0.04 should give a small result — 0.09 fits.",
        ],
        key_takeaway="To divide by a decimal, shift the decimal point in BOTH numbers until the divisor is a whole number.",
    ),
    we_do=[
        item(
            "we_1", "Compute 1.2 × 0.05.",
            opts("0.6", "0.06", "0.006", "6.0", "0.0006"), "B",
            "Ignore the points: 12 × 5 = 60. Total decimal places = 1 + 2 = 3, so 0.060 = 0.06.",
            difficulty="easy",
            scaffold_hints=[
                "Drop the decimals: 12 × 5 = 60.",
                "Count decimal places in the factors: 1 (in 1.2) + 2 (in 0.05) = 3.",
                "Place the point 3 from the right: 0.060 = 0.06.",
            ],
            immediate_feedback={
                "if_correct": "Right — 60 with three decimal places is 0.06.",
                "if_incorrect": "Count places in BOTH factors (1 + 2 = 3), not just one.",
            },
        ),
        item(
            "we_2", "Write 7/8 as a decimal.",
            opts("0.78", "0.875", "0.825", "0.88", "0.7875"), "B",
            "1/8 = 0.125, so 7/8 = 7 × 0.125 = 0.875 (or divide 7 ÷ 8 = 0.875).",
            difficulty="medium",
            scaffold_hints=[
                "Recall 1/8 = 0.125.",
                "7/8 = 7 × (1/8).",
                "7 × 0.125 = 0.875.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 0.875.",
                "if_incorrect": "Use the benchmark 1/8 = 0.125 and multiply by 7, or long-divide 7 ÷ 8.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "Compute 0.6 ÷ 0.0012.",
            opts("5", "50", "500", "5000", "0.5"), "C",
            "Shift both by 10,000: 6000 ÷ 12 = 500.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "Which fraction is equal to 0.0625?",
            opts("1/8", "1/16", "5/8", "1/4", "1/32"), "B",
            "0.0625 = 625/10000 = 1/16 (and 1/16 = 0.0625).",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "If n = 0.00025, then 1/n = ?",
            opts("400", "4000", "40000", "250", "2500"), "B",
            "0.00025 = 25/100000, so 1/n = 100000/25 = 4000.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "Compute (0.03)² ÷ 0.0009.",
            opts("0.1", "1", "10", "0.01", "100"), "B",
            "(0.03)² = 0.0009, and 0.0009 ÷ 0.0009 = 1.",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Compute 2.5 × 0.4.",
                opts("0.1", "1", "10", "0.01", "100"), "B",
                "25 × 4 = 100; two total decimal places → 1.00 = 1.",
                difficulty="easy",
            ),
            item(
                "mc_2", "Write 0.16 as a fraction in lowest terms.",
                opts("1/6", "4/25", "1/16", "2/25", "16/25"), "B",
                "0.16 = 16/100 = 4/25.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Prealgebra 2e — Decimals", "url": OSX_PREALG, "note": "Decimal operations, rounding, and fraction/decimal conversion.", "primary": True},
        {"name": "Khan Academy — Decimals", "url": KHAN_ARITH, "note": "Multiplying/dividing decimals and converting to fractions."},
        GMAT,
    ],
    tags=["arithmetic", "decimals", "place-value", "conversion", "estimation"],
)

T_percents = topic(
    topic_id="gmat::quant::arithmetic::percents",
    slug="percents",
    title="Percents",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["fractions", "decimals"],
    learning_objectives=[
        "Convert among percents, fractions, and decimals.",
        "Compute a percent of a number and find percent change (increase/decrease).",
        "Handle successive (compound) percents by multiplying factors, not adding.",
        "Reverse a percent: find the original from a part and its percent.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Fractions and decimals — 'percent' means 'per hundred'.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Write 25% as a fraction in lowest terms.", "answer": "1/4.", "targets": "percent → fraction"},
                {"prompt": "What is 10% of 80?", "answer": "8.", "targets": "percent of a number"},
                {"prompt": "Convert 0.45 to a percent.", "answer": "45%.", "targets": "decimal → percent"},
                {"prompt": "Write 1/5 as a percent.", "answer": "20%.", "targets": "fraction → percent"},
                {"prompt": "If a price goes up 50% then down 50%, are you back to the start?", "answer": "No — the 50% drop is taken from the larger amount (100 → 150 → 75).", "targets": "successive-percent misconception"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves conversions and 'percent of a number', and surfaces the #1 percent misconception (successive percents don't add) that today's lesson resolves.",
            "if_students_struggle": "If 10% of 80 is hard, anchor '10% = move the decimal one place'; build 5% and 15% from there.",
            "questions": [
                {"prompt": "Write 1/4 as a decimal.", "answer": "0.25.", "targets": "fraction ↔ decimal"},
                {"prompt": "Write 0.6 as a fraction in lowest terms.", "answer": "3/5.", "targets": "decimal ↔ fraction"},
                {"prompt": "Compute 1/2 of 80.", "answer": "40.", "targets": "fraction of a quantity"},
            ],
        },
        "prior_knowledge_bridge": "Q5 is the trap the GMAT sets constantly: people add percents. You can't, because each percent acts on a different base. Today you'll treat every percent as a multiplier (15% off = ×0.85) and chain them — the same equivalent-fraction thinking you used with decimals, now applied to change.",
        "learning_intention": "By the end you can compute percent-of and percent-change, chain successive percents by multiplying, and reverse a percent to find the original amount.",
        "success_criteria": [
            "I can rewrite any percent as a multiplier (e.g., +20% = ×1.20).",
            "I can compute percent change as change ÷ original.",
            "I can find the original quantity when given a part and its percent.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; act out 100 → 150 → 75 to kill the 'add percents' habit."},
            {"time": "6:00–8:00", "move": "Bridge: percent as a multiplier; chain multipliers."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: the double-discount shirt."},
        ],
    },
    i_do=item(
        "i_do", "A shirt priced at $80 is discounted 25%, then an additional 10% is taken off the reduced price. What is the final price?",
        opts("$52", "$54", "$56", "$58", "$60"), "B",
        "Apply discounts in sequence: 80 × 0.75 = 60, then 60 × 0.90 = 54.",
        difficulty="medium",
        think_aloud_steps=[
            "25% off means you pay 75%: 80 × 0.75 = 60.",
            "The next 10% comes off $60, not $80: 60 × 0.90 = 54.",
            "Final price is $54 — equivalent to ×0.675, i.e., 32.5% off, not 35%.",
        ],
        key_takeaway="Successive percents MULTIPLY (×0.75 then ×0.90 = ×0.675); they never simply add.",
    ),
    we_do=[
        item(
            "we_1", "What is 15% of 240?",
            opts("24", "30", "36", "40", "48"), "C",
            "10% of 240 = 24, and 5% = 12, so 15% = 24 + 12 = 36.",
            difficulty="easy",
            scaffold_hints=[
                "Find 10% first: move the decimal one place → 24.",
                "5% is half of 10% → 12.",
                "15% = 10% + 5% = 24 + 12.",
            ],
            immediate_feedback={
                "if_correct": "Right — building from 10% keeps it calculator-free.",
                "if_incorrect": "Decompose: 15% = 10% + 5%. Find each, then add.",
            },
        ),
        item(
            "we_2", "A quantity increases from 50 to 65. What is the percent increase?",
            opts("15%", "23%", "30%", "65%", "130%"), "C",
            "Percent change = change ÷ original = (65 − 50)/50 = 15/50 = 0.30 = 30%.",
            difficulty="medium",
            scaffold_hints=[
                "Percent change uses the ORIGINAL as the base.",
                "Change = 65 − 50 = 15.",
                "15/50 = 0.30.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 30% increase.",
                "if_incorrect": "Divide the change by the original (50), not by the new value (65).",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "If 40% of a number is 28, what is the number?",
            opts("56", "64", "70", "112", "11.2"), "C",
            "0.40x = 28 → x = 28 ÷ 0.40 = 70.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "A price rises 20% and then falls 20%. Compared with the original price, the result is:",
            opts("no change", "a 4% increase", "a 4% decrease", "a 20% decrease", "a 40% increase"), "C",
            "1.20 × 0.80 = 0.96, which is a 4% decrease from the original.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "30 is what percent of 24?",
            opts("80%", "120%", "125%", "130%", "144%"), "C",
            "30 ÷ 24 = 1.25 = 125%.",
            difficulty="hard", target_seconds=75,
        ),
        item(
            "you_4", "In a group, 60% are women, and 25% of the women wear glasses. What percent of the whole group are women who wear glasses?",
            opts("12%", "15%", "20%", "25%", "35%"), "B",
            "A percent OF a percent multiplies: 0.25 × 0.60 = 0.15 = 15%.",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "What is 35% of 80?",
                opts("24", "28", "30", "32", "36"), "B",
                "10% = 8 → 30% = 24; 5% = 4; total 35% = 28.",
                difficulty="easy",
            ),
            item(
                "mc_2", "A quantity decreases from 200 to 150. What is the percent decrease?",
                opts("20%", "25%", "30%", "33%", "50%"), "B",
                "Change 50 over original 200 = 50/200 = 25%.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Prealgebra 2e — Percents", "url": OSX_PREALG, "note": "Percent of a number, percent change, applications.", "primary": True},
        {"name": "Khan Academy — Percentages", "url": KHAN_ARITH, "note": "Percent of, percent change, and word problems."},
        GMAT,
    ],
    tags=["arithmetic", "percents", "percent-change", "successive-percents", "reverse-percent"],
)


T_ratios_proportions = topic(
    topic_id="gmat::quant::arithmetic::ratios_proportions",
    slug="ratios-proportions",
    title="Ratios & Proportions",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["fractions", "percents"],
    learning_objectives=[
        "Simplify ratios and distinguish part-to-part from part-to-whole.",
        "Model a ratio with a common multiplier (the 'parts' method).",
        "Solve proportions by cross-multiplication and apply scaling.",
        "Combine two ratios that share a term.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Equivalent fractions and dividing a quantity.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Simplify the ratio 18:24.", "answer": "3:4.", "targets": "simplifying ratios"},
                {"prompt": "If a:b = 2:3 and a = 10, find b.", "answer": "15.", "targets": "scaling a ratio"},
                {"prompt": "Split 30 in the ratio 2:3.", "answer": "12 and 18.", "targets": "parts method"},
                {"prompt": "Solve 3/4 = x/20.", "answer": "x = 15.", "targets": "proportion / cross-multiply"},
                {"prompt": "A recipe uses 2 cups flour to 3 cups sugar. Scale to 6 cups flour.", "answer": "Multiply both by 3 → 6:9.", "targets": "common-multiplier idea"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves simplifying, scaling, and cross-multiplication — the exact moves needed for the parts method and combined ratios today.",
            "if_students_struggle": "If splitting 30 as 2:3 is hard, show 2+3 = 5 parts, 30/5 = 6 per part, then 12 and 18.",
            "questions": [
                {"prompt": "Write 18/24 in lowest terms.", "answer": "3/4.", "targets": "simplifying fractions"},
                {"prompt": "Solve 3/4 = x/20.", "answer": "x = 15.", "targets": "equivalent fractions"},
                {"prompt": "What is 25% of 40?", "answer": "10.", "targets": "percents"},
            ],
        },
        "prior_knowledge_bridge": "A ratio is a pair of equivalent fractions waiting to be scaled. In the Do-Now you scaled 2:3 by a multiplier; today you'll formalize that into the 'parts' method — sum the parts, find the value of one part, then scale every share — and chain ratios that share a term.",
        "learning_intention": "By the end you can solve ratio and proportion problems with the parts method, scale with cross-multiplication, and combine ratios sharing a common term.",
        "success_criteria": [
            "I can turn a ratio into parts and find the value of one part.",
            "I can solve a:b problems given a difference or a total.",
            "I can combine a:b and b:c into a:c.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; formalize 'parts' from Q3."},
            {"time": "6:00–8:00", "move": "Bridge: ratio = scalable equivalent fractions; preview combining ratios."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: boys:girls = 3:5 with 32 students."},
        ],
    },
    i_do=item(
        "i_do", "The ratio of boys to girls in a class is 3:5. If there are 32 students in total, how many are girls?",
        opts("12", "15", "18", "20", "24"), "D",
        "Total parts = 3 + 5 = 8; each part = 32/8 = 4; girls = 5 × 4 = 20.",
        difficulty="medium",
        think_aloud_steps=[
            "The ratio 3:5 means the class is made of 3 + 5 = 8 equal parts.",
            "32 students ÷ 8 parts = 4 students per part.",
            "Girls are 5 parts: 5 × 4 = 20.",
            "Check: boys = 3 × 4 = 12, and 12 + 20 = 32. ✓",
        ],
        key_takeaway="Parts method: value of one part = total ÷ (sum of ratio terms); then scale each share.",
    ),
    we_do=[
        item(
            "we_1", "If a : b = 4 : 7 and b = 21, what is a?",
            opts("9", "12", "14", "15", "28"), "B",
            "b corresponds to 7 parts, so one part = 21/7 = 3; then a = 4 × 3 = 12.",
            difficulty="easy",
            scaffold_hints=[
                "The 21 matches the '7' in the ratio.",
                "One part = 21 ÷ 7 = 3.",
                "a = 4 parts = 4 × 3.",
            ],
            immediate_feedback={
                "if_correct": "Right — a = 12.",
                "if_incorrect": "Find the value of one part first (21/7 = 3), then multiply by a's term (4).",
            },
        ),
        item(
            "we_2", "Solve for x: 5/8 = x/40.",
            opts("8", "15", "20", "25", "64"), "D",
            "Cross-multiply: 8x = 5 × 40 = 200, so x = 25.",
            difficulty="medium",
            scaffold_hints=[
                "Cross-multiply: 8 · x = 5 · 40.",
                "8x = 200.",
                "x = 200/8.",
            ],
            immediate_feedback={
                "if_correct": "Yes — x = 25.",
                "if_incorrect": "Cross-multiply both diagonals and solve the resulting equation.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "A map's scale is 1 cm : 5 km. Two cities are 8.5 cm apart on the map. How far apart are they in reality?",
            opts("13.5 km", "40 km", "42.5 km", "45 km", "1.7 km"), "C",
            "Each cm is 5 km, so 8.5 × 5 = 42.5 km.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "$84 is divided among A, B, and C in the ratio 2 : 3 : 7. How much does C receive?",
            opts("$14", "$21", "$42", "$49", "$56"), "D",
            "Parts = 2 + 3 + 7 = 12; each part = 84/12 = 7; C = 7 × 7 = $49.",
            difficulty="medium", target_seconds=90,
        ),
        item(
            "you_3", "The ratio of cats to dogs at a shelter is 5 : 3. If there are 16 more cats than dogs, how many dogs are there?",
            opts("12", "18", "24", "30", "40"), "C",
            "Cats − dogs = 5 − 3 = 2 parts = 16, so one part = 8; dogs = 3 × 8 = 24.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "If a : b = 2 : 3 and b : c = 4 : 5, what is a : c?",
            opts("2 : 5", "8 : 15", "1 : 2", "6 : 5", "10 : 9"), "B",
            "Scale to a common b (LCM of 3 and 4 is 12): a:b = 8:12 and b:c = 12:15, so a:c = 8:15.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Simplify the ratio 45 : 27.",
                opts("3 : 5", "5 : 3", "9 : 5", "9 : 7", "5 : 9"), "B",
                "Divide both terms by 9: 45:27 = 5:3.",
                difficulty="easy",
            ),
            item(
                "mc_2", "If 3 pencils cost $0.90, how much do 8 pencils cost at the same rate?",
                opts("$2.10", "$2.40", "$2.70", "$3.00", "$7.20"), "B",
                "Unit price = 0.90/3 = $0.30; 8 × 0.30 = $2.40.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Prealgebra 2e — Ratios and Rate / Proportions", "url": OSX_PREALG, "note": "Ratios, unit rates, proportions, and applications.", "primary": True},
        {"name": "Khan Academy — Ratios, rates, and proportions", "url": KHAN_ARITH, "note": "Parts method, scaling, and cross-multiplication."},
        GMAT,
    ],
    tags=["arithmetic", "ratios", "proportions", "parts-method", "scaling"],
)

T_exponents_roots = topic(
    topic_id="gmat::quant::arithmetic::exponents_roots",
    slug="exponents-roots",
    title="Exponents & Roots",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["number properties (prime factorization)", "multiplication"],
    learning_objectives=[
        "Apply the exponent rules: product, quotient, power-of-a-power, zero, and negative exponents.",
        "Interpret roots as fractional exponents and simplify radicals.",
        "Solve a^x = N by rewriting N as a power of a and matching exponents.",
        "Compare powers by expressing them on a common base.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Repeated multiplication and prime factorization.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Compute 2^3 and 5^2.", "answer": "8 and 25.", "targets": "meaning of exponents"},
                {"prompt": "Simplify x^2 · x^3.", "answer": "x^5.", "targets": "product rule"},
                {"prompt": "What is √36?", "answer": "6.", "targets": "square roots"},
                {"prompt": "What is x^0 for x ≠ 0?", "answer": "1.", "targets": "zero exponent"},
                {"prompt": "Why is x^2 · x^3 = x^5, not x^6?", "answer": "Multiplying powers of the same base ADDS exponents — you're counting total factors (2 + 3 = 5).", "targets": "reasoning behind the product rule"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves the product rule, square roots, and the zero exponent — the building blocks for power-of-a-power, fractional exponents, and same-base comparisons today.",
            "if_students_struggle": "If the product rule is fuzzy, expand it: x^2 · x^3 = (x·x)(x·x·x) = x^5. Counting factors makes 'add exponents' obvious.",
            "questions": [
                {"prompt": "Write 72 as a product of primes.", "answer": "2^3 × 3^2 (72 = 8 × 9).", "targets": "prime factorization (number properties)"},
                {"prompt": "Compute 2^3 and 5^2.", "answer": "8 and 25.", "targets": "repeated multiplication"},
                {"prompt": "Compute 6 × 7 and 8 × 9.", "answer": "42 and 72.", "targets": "multiplication facts"},
            ],
        },
        "prior_knowledge_bridge": "Q5 is the engine of this whole topic: every exponent rule is just careful factor-counting, and prime factorization (last week) is how you put two different-looking powers on the same base. Today you'll extend 'add the exponents' to dividing, nesting, and fractional exponents (roots) — and use a common base to compare powers fast.",
        "learning_intention": "By the end you can simplify expressions with the exponent rules, convert between roots and fractional exponents, and solve and compare exponential expressions by matching bases.",
        "success_criteria": [
            "I can simplify products, quotients, and powers of powers without errors.",
            "I can rewrite a root as a fractional exponent and evaluate it.",
            "I can compare powers by putting them on a common base.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; expand x^2·x^3 to justify Q5."},
            {"time": "6:00–8:00", "move": "Bridge: same-base thinking via prime factorization."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: solve 2^x = 8 and 3^y = 81."},
        ],
    },
    i_do=item(
        "i_do", "If 2^x = 8 and 3^y = 81, what is x + y?",
        opts("5", "6", "7", "12", "24"), "C",
        "Rewrite each side on its own base: 8 = 2^3 so x = 3; 81 = 3^4 so y = 4; x + y = 7.",
        difficulty="medium",
        think_aloud_steps=[
            "8 is a power of 2: 8 = 2^3, so x = 3.",
            "81 is a power of 3: 81 = 3^4, so y = 4.",
            "x + y = 3 + 4 = 7.",
        ],
        key_takeaway="To solve a^x = N, rewrite N as a power of a, then match the exponents.",
    ),
    we_do=[
        item(
            "we_1", "Simplify (x^3)^4 · x^2.",
            opts("x^9", "x^14", "x^24", "x^20", "x^12"), "B",
            "Power of a power multiplies: (x^3)^4 = x^12. Then multiply like bases by adding: x^12 · x^2 = x^14.",
            difficulty="easy",
            scaffold_hints=[
                "Inner first: (x^3)^4 means multiply exponents → x^12.",
                "Now you have x^12 · x^2.",
                "Same base, multiplying → add exponents: 12 + 2.",
            ],
            immediate_feedback={
                "if_correct": "Right — x^14.",
                "if_incorrect": "Multiply for power-of-a-power, then ADD for the product. Don't mix the two.",
            },
        ),
        item(
            "we_2", "Simplify √72.",
            opts("6√2", "8√3", "36", "12", "9√2"), "A",
            "Pull out the largest perfect-square factor: 72 = 36 × 2, so √72 = √36 · √2 = 6√2.",
            difficulty="medium",
            scaffold_hints=[
                "Find the largest perfect square dividing 72.",
                "72 = 36 × 2 and 36 is a perfect square.",
                "√(36·2) = √36 · √2 = 6√2.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 6√2.",
                "if_incorrect": "Factor out a perfect square (36), not just any factor, so the root comes out whole.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "Compute 4^(3/2).",
            opts("6", "8", "12", "16", "64"), "B",
            "A fractional exponent is root-then-power: 4^(3/2) = (√4)^3 = 2^3 = 8.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "Simplify 3^5 / 3^2.",
            opts("3", "9", "27", "81", "243"), "C",
            "Dividing like bases subtracts exponents: 3^(5−2) = 3^3 = 27.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_3", "If 2^(x+3) = 32, what is x?",
            opts("1", "2", "3", "4", "5"), "B",
            "32 = 2^5, so x + 3 = 5, giving x = 2.",
            difficulty="hard", target_seconds=75,
        ),
        item(
            "you_4", "Which of the following is the greatest?",
            opts("2^14", "4^9", "8^5", "16^4", "2^17"), "B",
            "Put everything on base 2: 2^14, 4^9 = 2^18, 8^5 = 2^15, 16^4 = 2^16, 2^17. The largest exponent is 18, so 4^9 is greatest.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Simplify (2^3)^2.",
                opts("16", "32", "64", "128", "256"), "C",
                "Multiply exponents: (2^3)^2 = 2^6 = 64.",
                difficulty="easy",
            ),
            item(
                "mc_2", "Compute 9^(1/2) + 27^(1/3).",
                opts("5", "6", "9", "12", "18"), "B",
                "9^(1/2) = √9 = 3 and 27^(1/3) = ∛27 = 3; sum = 6.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Intermediate Algebra 2e — Exponents and Radicals", "url": OSX_INT, "note": "Exponent rules, rational exponents, simplifying radicals.", "primary": True},
        {"name": "Khan Academy — Exponents & radicals", "url": KHAN_ALG, "note": "Rules of exponents and working with roots."},
        GMAT,
    ],
    tags=["arithmetic", "exponents", "roots", "radicals", "fractional-exponents", "same-base"],
)


T_statistics = topic(
    topic_id="gmat::quant::arithmetic::statistics",
    slug="statistics",
    title="Descriptive Statistics",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["addition & division (for averages)", "ordering numbers"],
    learning_objectives=[
        "Compute mean, median, mode, and range.",
        "Use sum = mean × count to handle 'add/remove a value' and 'missing value' problems.",
        "Reason about standard deviation as spread about the mean (no formula needed on the GMAT).",
        "Compare measures of center for skewed data.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Addition, division, and putting numbers in order.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Find the mean of 4, 8, 9, 11.", "answer": "8 (sum 32 ÷ 4).", "targets": "mean"},
                {"prompt": "Find the median of 3, 7, 9, 12, 20.", "answer": "9 (middle value).", "targets": "median"},
                {"prompt": "Find the mode of 2, 3, 3, 5, 7.", "answer": "3 (most frequent).", "targets": "mode"},
                {"prompt": "Find the range of 5, 9, 14, 21.", "answer": "16 (21 − 5).", "targets": "range"},
                {"prompt": "If you add a value equal to the current mean, does the mean change?", "answer": "No — adding the mean itself leaves the average unchanged.", "targets": "how the mean responds to new data"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves the four basic measures and the key intuition (the mean is a balance point) that powers today's sum-based reasoning.",
            "if_students_struggle": "If median is shaky with an even count, remind them to sort first and average the two middle values.",
            "questions": [
                {"prompt": "Compute 4 + 8 + 9 + 11.", "answer": "32.", "targets": "addition (for a sum)"},
                {"prompt": "Compute 32 ÷ 4.", "answer": "8.", "targets": "division (for an average)"},
                {"prompt": "Put 12, 3, 20, 7, 9 in increasing order.", "answer": "3, 7, 9, 12, 20.", "targets": "ordering numbers"},
            ],
        },
        "prior_knowledge_bridge": "You computed means by adding then dividing. The GMAT rarely asks that directly — it gives you the average and asks you to work backward. The move is to flip the formula into sum = mean × count. Q5's insight (the mean is a balance point) is why that flip works, and it's the key to every 'missing value' and 'new average' question today.",
        "learning_intention": "By the end you can compute mean/median/mode/range and use sum = mean × count to solve missing-value and changing-average problems, and reason qualitatively about standard deviation.",
        "success_criteria": [
            "I can convert between an average and a total using count.",
            "I can find a missing value given an average.",
            "I can say which of two data sets has the larger spread and why.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; dwell on Q5 (balance-point intuition)."},
            {"time": "6:00–8:00", "move": "Bridge: flip mean = sum/count into sum = mean × count."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: new average after adding a value."},
        ],
    },
    i_do=item(
        "i_do", "The average (arithmetic mean) of 5 numbers is 12. If a sixth number, 30, is added to the set, what is the new average?",
        opts("13", "14", "15", "16", "18"), "C",
        "Sum = mean × count = 12 × 5 = 60. New sum = 60 + 30 = 90 over 6 numbers, so the new average = 90/6 = 15.",
        difficulty="medium",
        think_aloud_steps=[
            "Convert the average to a sum: 12 × 5 = 60.",
            "Add the new value: 60 + 30 = 90.",
            "Divide by the new count: 90 ÷ 6 = 15.",
        ],
        key_takeaway="Don't average the averages — turn the mean into a SUM (mean × count), adjust, then divide by the new count.",
    ),
    we_do=[
        item(
            "we_1", "Find the median of 4, 1, 7, 3, 9, 6.",
            opts("4", "5", "6", "6.5", "7"), "B",
            "Sort: 1, 3, 4, 6, 7, 9. With 6 values the median is the average of the 3rd and 4th: (4 + 6)/2 = 5.",
            difficulty="easy",
            scaffold_hints=[
                "Always sort before finding a median.",
                "Six values → no single middle; use the two middle ones.",
                "Average the 3rd and 4th: (4 + 6)/2.",
            ],
            immediate_feedback={
                "if_correct": "Right — 5.",
                "if_incorrect": "Sort first, then average the two middle values for an even-sized list.",
            },
        ),
        item(
            "we_2", "The mean of 6 numbers is 10. What is their sum?",
            opts("10", "16", "36", "60", "600"), "D",
            "Sum = mean × count = 10 × 6 = 60.",
            difficulty="easy",
            scaffold_hints=[
                "Mean = sum ÷ count.",
                "Rearrange: sum = mean × count.",
                "10 × 6.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 60.",
                "if_incorrect": "Multiply the mean by how many numbers there are.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "The average of 8 and x is 14. What is x?",
            opts("6", "14", "18", "20", "22"), "D",
            "(8 + x)/2 = 14 → 8 + x = 28 → x = 20.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_2", "For the set {3, 5, 5, 9, 13}, which is the largest: the mean, the median, or the mode?",
            opts("mean", "median", "mode", "all equal", "cannot be determined"), "A",
            "Mean = 35/5 = 7; median = 5 (middle); mode = 5 (most frequent). The mean, 7, is largest.",
            difficulty="medium", target_seconds=90,
        ),
        item(
            "you_3", "The average of 5 test scores is 82. Four of the scores are 78, 85, 90, and 75. What is the fifth score?",
            opts("80", "82", "84", "86", "88"), "B",
            "Total = 82 × 5 = 410. The four given sum to 328, so the fifth = 410 − 328 = 82.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "Which set has the greater standard deviation?  P = {10, 10, 10, 10};  Q = {7, 9, 11, 13}.",
            opts("P", "Q", "they are equal", "cannot be determined", "both are zero"), "B",
            "Standard deviation measures spread about the mean. P has no spread (SD = 0); Q's values vary about their mean, so Q has the greater SD.",
            difficulty="hard", target_seconds=75,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Find the mean of 6, 10, 14, 18, 22.",
                opts("12", "14", "15", "16", "18"), "B",
                "Sum = 70; 70/5 = 14.",
                difficulty="easy",
            ),
            item(
                "mc_2", "The average of 4 numbers is 9. After one number is removed, the average of the remaining 3 is 8. What number was removed?",
                opts("8", "9", "11", "12", "15"), "D",
                "Original sum = 36; remaining sum = 24; removed = 36 − 24 = 12.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Introductory Statistics — Measures of center and spread", "url": OSX_STAT, "note": "Mean, median, mode, range, and standard deviation.", "primary": True},
        {"name": "Khan Academy — Summarizing quantitative data", "url": KHAN_STAT, "note": "Center, spread, and effects of changing data."},
        GMAT,
    ],
    tags=["arithmetic", "statistics", "mean", "median", "mode", "range", "standard-deviation", "weighted-average"],
)

T_sets = topic(
    topic_id="gmat::quant::arithmetic::sets",
    slug="sets",
    title="Sets & Venn Diagrams",
    domain="Arithmetic",
    estimated_minutes=22,
    prerequisites=["addition & subtraction", "percents (for proportion-of-group overlaps)"],
    learning_objectives=[
        "Use union, intersection, and complement correctly.",
        "Apply the two-set formula |A∪B| = |A| + |B| − |A∩B| and account for 'neither'.",
        "Translate overlap word problems into a Venn structure (only-A, only-B, both, neither).",
        "Find 'only one group' counts from totals and overlaps.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Adding and subtracting counts; reading 'and/or'.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "A = {1,2,3,4}, B = {3,4,5}. List A ∩ B.", "answer": "{3, 4}.", "targets": "intersection"},
                {"prompt": "For the same sets, list A ∪ B.", "answer": "{1, 2, 3, 4, 5}.", "targets": "union"},
                {"prompt": "How many elements are in that A ∪ B?", "answer": "5.", "targets": "counting a union"},
                {"prompt": "Of 30 students, 18 play a sport. How many do not?", "answer": "12 (the complement).", "targets": "complement / 'neither'"},
                {"prompt": "If 18 like tea and 15 like coffee in a class of 30, why isn't the total 33?", "answer": "People who like BOTH are counted twice; the overlap is double-counted.", "targets": "the double-counting idea behind today"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves union/intersection/complement and exposes the double-counting problem that inclusion–exclusion fixes.",
            "if_students_struggle": "If union vs intersection blurs, anchor: 'or' = union (everything), 'and' = intersection (overlap only).",
            "questions": [
                {"prompt": "Compute 25 + 18.", "answer": "43.", "targets": "addition"},
                {"prompt": "Of 30 students, 18 play a sport. How many do not?", "answer": "12 (30 − 18).", "targets": "subtraction (complement)"},
                {"prompt": "What is 20% of 50?", "answer": "10.", "targets": "percents (of a group)"},
            ],
        },
        "prior_knowledge_bridge": "Q5 names today's whole idea: when you add two group sizes, the people in both get counted twice. The fix is to subtract the overlap once — that's the two-set formula. Combined with 'neither', it turns any overlap word problem into a quick arithmetic setup.",
        "learning_intention": "By the end you can solve two-set overlap problems with |A∪B| = |A| + |B| − |A∩B|, include a 'neither' group, and extract 'only-A' counts.",
        "success_criteria": [
            "I can find the overlap when given two group sizes and the union (or total and neither).",
            "I can find how many are in exactly one group.",
            "I can lay out only-A / only-B / both / neither and have them sum to the total.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; dramatize the double-count in Q5."},
            {"time": "6:00–8:00", "move": "Bridge: subtract the overlap once → the formula."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: languages with a 'neither' group."},
        ],
    },
    i_do=item(
        "i_do", "In a group of 40 people, 25 speak French, 18 speak Spanish, and 7 speak both languages. How many speak neither?",
        opts("2", "4", "6", "11", "15"), "B",
        "Speakers of at least one = 25 + 18 − 7 = 36. Neither = total − union = 40 − 36 = 4.",
        difficulty="medium",
        think_aloud_steps=[
            "First find how many speak at least one language (the union).",
            "|F ∪ S| = |F| + |S| − |both| = 25 + 18 − 7 = 36.",
            "Neither = total − union = 40 − 36 = 4.",
        ],
        key_takeaway="Total = only-A + only-B + both + neither; equivalently Total = |A| + |B| − |both| + neither.",
    ),
    we_do=[
        item(
            "we_1", "In a class of 30, 20 study math and 14 study physics; 8 study both. How many study at least one of the two?",
            opts("22", "24", "26", "28", "34"), "C",
            "|M ∪ P| = 20 + 14 − 8 = 26.",
            difficulty="easy",
            scaffold_hints=[
                "Add the two groups, then remove the overlap once.",
                "20 + 14 = 34.",
                "Subtract both (8): 34 − 8 = 26.",
            ],
            immediate_feedback={
                "if_correct": "Right — subtracting the overlap once avoids double counting.",
                "if_incorrect": "34 double-counts the 8 who do both; subtract them once.",
            },
        ),
        item(
            "we_2", "Of 50 people, 30 own a car, 25 own a bike, and 10 own neither. How many own both?",
            opts("5", "10", "15", "20", "25"), "C",
            "Own at least one = 50 − 10 = 40. Then 40 = 30 + 25 − both, so both = 55 − 40 = 15.",
            difficulty="medium",
            scaffold_hints=[
                "Find 'at least one' first: total − neither = 50 − 10 = 40.",
                "Now use 40 = 30 + 25 − both.",
                "both = 55 − 40.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 15 own both.",
                "if_incorrect": "Subtract 'neither' from the total to get the union, then solve for the overlap.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "In a survey of 60 people, 35 like apples and 40 like bananas. Every person likes at least one. How many like both?",
            opts("5", "10", "15", "20", "25"), "C",
            "Union = 60 (everyone likes at least one), so both = 35 + 40 − 60 = 15.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "Set A has 12 elements, set B has 18 elements, and A ∩ B has 5 elements. How many elements are in A ∪ B?",
            opts("23", "25", "30", "35", "5"), "B",
            "|A ∪ B| = 12 + 18 − 5 = 25.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_3", "In a class of 36, every student takes art, music, or both. 22 take art and 20 take music. How many take ONLY art?",
            opts("14", "16", "18", "6", "22"), "B",
            "Both = 22 + 20 − 36 = 6; only art = 22 − 6 = 16.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "Of 100 people, 60 drink coffee, 50 drink tea, and 30 drink both. How many drink coffee but NOT tea?",
            opts("20", "30", "40", "50", "10"), "B",
            "Coffee but not tea = |coffee| − |both| = 60 − 30 = 30. (The union is 80 and 20 drink neither — consistent.)",
            difficulty="hard", target_seconds=75,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "A = {2, 4, 6, 8} and B = {4, 8, 12}. How many elements are in A ∪ B?",
                opts("3", "4", "5", "6", "7"), "C",
                "Union = {2, 4, 6, 8, 12}; |A ∪ B| = 4 + 3 − 2 = 5 (4 and 8 are shared).",
                difficulty="easy",
            ),
            item(
                "mc_2", "Of 80 people, 45 read fiction, 38 read nonfiction, and 12 read neither. How many read both?",
                opts("9", "12", "15", "18", "21"), "C",
                "At least one = 80 − 12 = 68; both = 45 + 38 − 68 = 15.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Introductory Statistics — Venn diagrams & set operations", "url": OSX_STAT, "note": "Unions, intersections, and complements in the probability chapter.", "primary": True},
        {"name": "Khan Academy — Basic set operations", "url": KHAN_STAT, "note": "Venn diagrams and counting overlaps."},
        GMAT,
    ],
    tags=["arithmetic", "sets", "venn", "inclusion-exclusion", "overlap", "union", "intersection"],
)


T_counting = topic(
    topic_id="gmat::quant::arithmetic::counting",
    slug="counting-combinatorics",
    title="Counting & Combinatorics",
    domain="Arithmetic",
    estimated_minutes=24,
    prerequisites=["multiplication principle", "factorials"],
    learning_objectives=[
        "Apply the fundamental counting principle (multiply independent choices).",
        "Decide whether order matters: permutation vs combination.",
        "Compute permutations P(n,k) and combinations C(n,k) without a calculator.",
        "Handle simple restrictions (no repeats, fixed roles, by-category choices).",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Multiplication and the idea of independent choices.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "How many 2-digit codes use digits 1–4 if repeats are allowed?", "answer": "16 (4 × 4).", "targets": "multiplication principle"},
                {"prompt": "Compute 4! (4 factorial).", "answer": "24.", "targets": "factorials"},
                {"prompt": "How many ways to arrange A, B, C in a row?", "answer": "6 (3!).", "targets": "arrangements"},
                {"prompt": "Pick 1 of 3 shirts and 1 of 2 pants — how many outfits?", "answer": "6 (3 × 2).", "targets": "independent choices"},
                {"prompt": "Choosing a 2-person team from a group — does order matter? Why?", "answer": "No — {A,B} is the same team as {B,A}; that's a combination.", "targets": "order vs no order"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves the multiplication principle, factorials, and the order-vs-no-order distinction that decides permutation versus combination.",
            "if_students_struggle": "If factorials are shaky, write 4! = 4·3·2·1 explicitly and connect to arranging 4 items.",
            "questions": [
                {"prompt": "How many 2-digit codes use digits 1–4 if repeats are allowed?", "answer": "16 (4 × 4).", "targets": "multiplication principle"},
                {"prompt": "Compute 4! (4 factorial).", "answer": "24.", "targets": "factorials"},
                {"prompt": "Pick 1 of 3 shirts and 1 of 2 pants — how many outfits?", "answer": "6 (3 × 2).", "targets": "independent choices"},
            ],
        },
        "prior_knowledge_bridge": "Everything in counting grows from the multiplication principle you just used for outfits. Q5 splits the world in two: when order matters you keep all arrangements (permutations); when it doesn't, you divide out the repeats (combinations). Today you'll pick the right tool and compute it by hand.",
        "learning_intention": "By the end you can count outcomes with the multiplication principle and decide between permutations and combinations, computing each without a calculator.",
        "success_criteria": [
            "I can multiply independent choices to count outcomes.",
            "I can tell whether a problem needs a permutation or a combination.",
            "I can evaluate P(n,k) and C(n,k) by canceling factorials.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; sort Q5 into the combination bucket."},
            {"time": "6:00–8:00", "move": "Bridge: permutations keep order; combinations divide it out."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: choose a committee of 3 from 7."},
        ],
    },
    i_do=item(
        "i_do", "A committee of 3 people is chosen from a group of 7. How many different committees are possible?",
        opts("21", "35", "105", "210", "343"), "B",
        "A committee is unordered, so use a combination: C(7,3) = (7·6·5)/(3·2·1) = 210/6 = 35.",
        difficulty="medium",
        think_aloud_steps=[
            "Does order matter? No — a committee {A,B,C} is the same in any order. Use combinations.",
            "C(7,3) = 7! / (3! · 4!) = (7·6·5)/(3·2·1).",
            "Numerator 7·6·5 = 210; denominator 3·2·1 = 6.",
            "210 / 6 = 35.",
        ],
        key_takeaway="Order matters → permutation; order doesn't → combination. Committees, teams, and groups are combinations.",
    ),
    we_do=[
        item(
            "we_1", "In how many ways can 5 people line up in a row?",
            opts("20", "25", "60", "120", "720"), "D",
            "A line is an ordered arrangement of all 5: 5! = 5·4·3·2·1 = 120.",
            difficulty="easy",
            scaffold_hints=[
                "A row is ordered → permutation.",
                "All five are arranged → 5!.",
                "5·4·3·2·1.",
            ],
            immediate_feedback={
                "if_correct": "Right — 120.",
                "if_incorrect": "Arranging all n distinct items in order is n!, not a combination.",
            },
        ),
        item(
            "we_2", "From 6 books, in how many ways can you choose 2 to take on a trip?",
            opts("12", "15", "30", "36", "720"), "B",
            "Choosing (order irrelevant) → combination: C(6,2) = (6·5)/(2·1) = 15.",
            difficulty="medium",
            scaffold_hints=[
                "Order doesn't matter for which 2 books → combination.",
                "C(6,2) = (6·5)/(2·1).",
                "30/2 = 15.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 15.",
                "if_incorrect": "30 is the ordered count (P(6,2)); divide by 2! because the 2 books' order doesn't matter.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "A restaurant offers 4 appetizers, 5 main courses, and 3 desserts. How many different 3-course meals (one of each) are possible?",
            opts("12", "35", "60", "120", "220"), "C",
            "Independent choices multiply: 4 × 5 × 3 = 60.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_2", "How many distinct arrangements are there of the letters in the word MATH?",
            opts("4", "12", "16", "24", "256"), "D",
            "Four distinct letters arranged in order: 4! = 24.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_3", "A team of 2 is selected from 4 women and 3 men. How many teams have exactly 1 woman and 1 man?",
            opts("6", "7", "10", "12", "21"), "D",
            "Choose 1 of 4 women and 1 of 3 men: 4 × 3 = 12.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "How many 3-digit numbers can be formed from the digits 1, 2, 3, 4, 5 if no digit is repeated?",
            opts("10", "15", "60", "120", "125"), "C",
            "No repeats: 5 choices, then 4, then 3 → 5·4·3 = 60 (this is P(5,3)).",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Compute C(5,2).",
                opts("5", "10", "20", "25", "120"), "B",
                "C(5,2) = (5·4)/(2·1) = 10.",
                difficulty="easy",
            ),
            item(
                "mc_2", "In how many ways can 4 distinct paintings be hung in a row?",
                opts("8", "12", "16", "24", "256"), "D",
                "Ordered arrangement of 4 distinct items = 4! = 24.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "Khan Academy — Counting, permutations, and combinations", "url": "https://www.khanacademy.org/math/precalculus", "note": "Multiplication principle, P(n,k), C(n,k) with worked examples.", "primary": True},
        {"name": "OpenStax, Introductory Statistics — Counting principles", "url": OSX_STAT, "note": "Factorials, permutations, and combinations."},
        GMAT,
    ],
    tags=["arithmetic", "counting", "combinatorics", "permutations", "combinations", "factorial", "multiplication-principle"],
)

T_probability = topic(
    topic_id="gmat::quant::arithmetic::probability",
    slug="probability",
    title="Probability",
    domain="Arithmetic",
    estimated_minutes=24,
    prerequisites=["fractions", "counting & combinatorics"],
    learning_objectives=[
        "Compute basic probability as favorable ÷ total equally likely outcomes.",
        "Use the complement rule P(not A) = 1 − P(A), especially for 'at least one'.",
        "Combine events: 'and' (multiply, independent) vs 'or' (add, then subtract overlap).",
        "Handle without-replacement draws by updating counts.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Fractions and counting outcomes.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "A fair die is rolled. P(rolling a 4)?", "answer": "1/6.", "targets": "basic probability"},
                {"prompt": "A fair coin is flipped. P(heads)?", "answer": "1/2.", "targets": "equally likely outcomes"},
                {"prompt": "A fair die is rolled. P(even number)?", "answer": "3/6 = 1/2.", "targets": "favorable ÷ total"},
                {"prompt": "If P(rain) = 0.3, what is P(no rain)?", "answer": "0.7 (the complement).", "targets": "complement rule"},
                {"prompt": "Two coin flips: why is P(two heads) = 1/4, not 1/2?", "answer": "The flips are independent, so multiply: 1/2 × 1/2 = 1/4.", "targets": "'and' of independent events"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves favorable-over-total, the complement, and the multiply-for-'and' rule — the three moves behind every problem today.",
            "if_students_struggle": "If the multiply rule is unclear, list all four outcomes of two flips (HH, HT, TH, TT) to show P(HH) = 1/4.",
            "questions": [
                {"prompt": "Simplify 3/6.", "answer": "1/2.", "targets": "fractions"},
                {"prompt": "How many equally likely outcomes are there when rolling one die?", "answer": "6.", "targets": "counting outcomes"},
                {"prompt": "How many outcomes are there for one coin flip?", "answer": "2 (heads, tails).", "targets": "counting a sample space"},
            ],
        },
        "prior_knowledge_bridge": "Probability is just counting wrapped in a fraction: favorable outcomes over total outcomes (your counting skills). Q4 and Q5 add the two power tools — the complement (turn 'at least one' into '1 minus none') and multiplying for 'and'. Today you'll combine them, including draws without replacement where the counts change.",
        "learning_intention": "By the end you can compute single-event probabilities, use the complement for 'at least one', and combine events with the 'and' (multiply) and 'or' (add minus overlap) rules.",
        "success_criteria": [
            "I can set up favorable ÷ total for an equally likely sample space.",
            "I can solve 'at least one' problems via the complement.",
            "I can chain dependent draws by updating the counts.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; enumerate two-flip outcomes to justify Q5."},
            {"time": "6:00–8:00", "move": "Bridge: complement + multiply rule; preview without replacement."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: drawing two red marbles without replacement."},
        ],
    },
    i_do=item(
        "i_do", "A bag contains 4 red and 6 green marbles. Two marbles are drawn at random without replacement. What is the probability that both are red?",
        opts("2/15", "4/25", "1/6", "2/5", "6/25"), "A",
        "P(both red) = (4/10)(3/9) = (2/5)(1/3) = 2/15. Without replacement, the second draw uses the reduced counts.",
        difficulty="medium",
        think_aloud_steps=[
            "First draw: 4 red out of 10 → 4/10 = 2/5.",
            "No replacement: now 3 red remain out of 9 → 3/9 = 1/3.",
            "'Both' means multiply: 2/5 × 1/3 = 2/15.",
        ],
        key_takeaway="'And' (both happen) → multiply; without replacement, update the totals for the next draw.",
    ),
    we_do=[
        item(
            "we_1", "A fair die is rolled once. What is the probability of rolling a number greater than 4?",
            opts("1/6", "1/3", "1/2", "2/3", "1/4"), "B",
            "Favorable outcomes are 5 and 6 → 2 out of 6 = 1/3.",
            difficulty="easy",
            scaffold_hints=[
                "List the outcomes greater than 4: 5 and 6.",
                "Total equally likely outcomes = 6.",
                "2/6 reduces to 1/3.",
            ],
            immediate_feedback={
                "if_correct": "Right — 1/3.",
                "if_incorrect": "'Greater than 4' excludes 4 itself; only 5 and 6 qualify.",
            },
        ),
        item(
            "we_2", "The probability that an event occurs is 3/7. What is the probability it does NOT occur?",
            opts("3/7", "4/7", "3/4", "7/10", "1/7"), "B",
            "Complement: 1 − 3/7 = 4/7.",
            difficulty="easy",
            scaffold_hints=[
                "P(not A) = 1 − P(A).",
                "1 = 7/7.",
                "7/7 − 3/7 = 4/7.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 4/7.",
                "if_incorrect": "Subtract the probability from 1 (written as 7/7).",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "A jar has 2 white, 3 black, and 5 red marbles. One marble is drawn at random. What is the probability it is NOT red?",
            opts("1/2", "1/5", "3/10", "2/5", "7/10"), "A",
            "Not red = (2 + 3)/10 = 5/10 = 1/2 (equivalently 1 − 5/10).",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_2", "Two fair coins are flipped. What is the probability of getting at least one head?",
            opts("1/4", "1/2", "2/3", "3/4", "1"), "D",
            "Use the complement: P(no heads) = (1/2)(1/2) = 1/4, so P(at least one head) = 1 − 1/4 = 3/4.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "A fair die is rolled twice. What is the probability that both rolls show a 6?",
            opts("1/3", "1/12", "1/36", "1/18", "1/6"), "C",
            "Independent rolls multiply: (1/6)(1/6) = 1/36.",
            difficulty="hard", target_seconds=60,
        ),
        item(
            "you_4", "From a standard deck of 52 cards, one card is drawn. What is the probability it is a heart OR a king?",
            opts("17/52", "15/52", "4/13", "1/4", "1/13"), "C",
            "P(heart or king) = 13/52 + 4/52 − 1/52 (the king of hearts is in both) = 16/52 = 4/13.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "A spinner has 8 equal sections numbered 1–8. What is the probability of landing on a multiple of 3?",
                opts("1/8", "1/4", "3/8", "1/3", "1/2"), "B",
                "Multiples of 3 up to 8 are 3 and 6 → 2/8 = 1/4.",
                difficulty="medium",
            ),
            item(
                "mc_2", "A bag has 5 red and 3 blue marbles. Two are drawn without replacement. What is the probability the first is red and the second is blue?",
                opts("15/64", "15/56", "8/15", "5/14", "1/2"), "B",
                "(5/8)(3/7) = 15/56; the totals drop after the first draw.",
                difficulty="hard",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Introductory Statistics — Probability Topics", "url": OSX_STAT, "note": "Sample spaces, complements, 'and'/'or', conditional probability.", "primary": True},
        {"name": "Khan Academy — Probability", "url": KHAN_STAT, "note": "Basic, complementary, and compound probability."},
        GMAT,
    ],
    tags=["arithmetic", "probability", "complement", "independent-events", "without-replacement", "or-rule"],
)

T_algebraic_expressions = topic(
    topic_id="gmat::quant::algebra::algebraic_expressions",
    slug="algebraic-expressions",
    title="Algebraic Expressions & Exponent Rules",
    domain="Algebra",
    estimated_minutes=22,
    prerequisites=["exponents & roots", "number properties"],
    learning_objectives=[
        "Combine like terms and distribute correctly, watching signs.",
        "Multiply binomials with FOIL and recognize special products.",
        "Factor out a GCF and factor a difference of squares.",
        "Evaluate expressions by substitution and use identities like (a+b)^2.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Exponent rules and the order of operations.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Simplify 3x + 5x − 2x.", "answer": "6x.", "targets": "combining like terms"},
                {"prompt": "Expand 2(x + 4).", "answer": "2x + 8.", "targets": "distributing"},
                {"prompt": "Simplify x^2 · x^3.", "answer": "x^5.", "targets": "product rule"},
                {"prompt": "Evaluate 2a + 3 when a = 4.", "answer": "11.", "targets": "substitution"},
                {"prompt": "Why can't 3x + 2y be simplified to 5xy?", "answer": "They are unlike terms — only terms with the same variable part combine.", "targets": "what 'like terms' means"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves like terms, distribution, the product rule, and substitution — the moves you'll chain into FOIL and factoring today.",
            "if_students_struggle": "If distribution slips, model the sign trap: −2(x − 5) = −2x + 10, not −2x − 10.",
            "questions": [
                {"prompt": "Simplify x^2 · x^3.", "answer": "x^5.", "targets": "exponent product rule (exponents & roots)"},
                {"prompt": "Compute √49.", "answer": "7.", "targets": "square roots (exponents & roots)"},
                {"prompt": "What is the GCF of 6 and 9?", "answer": "3.", "targets": "common factors (number properties)"},
            ],
        },
        "prior_knowledge_bridge": "Q5 pins down the one rule beginners break: you can only combine like terms. Distribution and FOIL are just organized ways to create like terms and then collect them; factoring is running that machine in reverse. Today you'll expand, factor, and evaluate — the algebra plumbing behind every equation later in the course.",
        "learning_intention": "By the end you can expand products with FOIL, factor out common factors and differences of squares, and evaluate expressions accurately.",
        "success_criteria": [
            "I can distribute a negative without sign errors.",
            "I can multiply two binomials and collect the middle term.",
            "I can factor out a GCF and recognize a^2 − b^2.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; stress the sign in distribution."},
            {"time": "6:00–8:00", "move": "Bridge: FOIL makes like terms; factoring reverses it."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: expand (x + 3)(x − 5)."},
        ],
    },
    i_do=item(
        "i_do", "Expand and simplify: (x + 3)(x − 5).",
        opts("x^2 − 2x − 15", "x^2 + 2x − 15", "x^2 − 8x − 15", "x^2 − 2x + 15", "x^2 − 15"), "A",
        "FOIL then combine: x·x + x·(−5) + 3·x + 3·(−5) = x^2 − 5x + 3x − 15 = x^2 − 2x − 15.",
        difficulty="medium",
        think_aloud_steps=[
            "First: x · x = x^2.",
            "Outer: x · (−5) = −5x. Inner: 3 · x = 3x.",
            "Last: 3 · (−5) = −15.",
            "Combine the middle terms: −5x + 3x = −2x, giving x^2 − 2x − 15.",
        ],
        key_takeaway="FOIL: multiply every term in the first factor by every term in the second, then collect the like (middle) terms.",
    ),
    we_do=[
        item(
            "we_1", "Simplify: 4(2x − 3) − 2(x − 5).",
            opts("6x − 2", "6x − 22", "6x + 2", "10x − 2", "6x − 7"), "A",
            "Distribute: 8x − 12 − 2x + 10. Combine: (8x − 2x) + (−12 + 10) = 6x − 2.",
            difficulty="easy",
            scaffold_hints=[
                "Distribute both groups first.",
                "Mind the sign: −2(x − 5) = −2x + 10.",
                "Combine x-terms and constants separately.",
            ],
            immediate_feedback={
                "if_correct": "Right — 6x − 2.",
                "if_incorrect": "The −2 multiplies BOTH terms, turning −5 into +10. Re-do that distribution.",
            },
        ),
        item(
            "we_2", "Factor completely: 6x^2 + 9x.",
            opts("3x(2x + 3)", "3(2x^2 + 3x)", "x(6x + 9)", "3x(2x + 9)", "6x(x + 3)"), "A",
            "GCF of 6x^2 and 9x is 3x: 6x^2 + 9x = 3x(2x + 3).",
            difficulty="medium",
            scaffold_hints=[
                "What is the greatest common factor of 6x^2 and 9x?",
                "Numbers share 3; both terms share an x → 3x.",
                "6x^2 ÷ 3x = 2x and 9x ÷ 3x = 3.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 3x(2x + 3), fully factored.",
                "if_incorrect": "Pull out the FULL common factor (3x), not just 3 or just x.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "If x = 2 and y = −3, evaluate 3x^2 − 2y.",
            opts("6", "12", "18", "24", "30"), "C",
            "3(2)^2 − 2(−3) = 3·4 + 6 = 12 + 6 = 18.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_2", "Expand (2x − 1)^2.",
            opts("4x^2 − 1", "4x^2 + 1", "4x^2 − 4x + 1", "4x^2 − 2x + 1", "2x^2 − 4x + 1"), "C",
            "(2x − 1)^2 = (2x)^2 − 2(2x)(1) + 1^2 = 4x^2 − 4x + 1.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "Simplify (6x^3 y^2) / (2x y^2).",
            opts("3x^2", "3x^2 y", "3x^3", "3x^2 y^4", "4x^2"), "A",
            "6/2 = 3; x^3/x = x^2; y^2/y^2 = 1. Result: 3x^2.",
            difficulty="hard", target_seconds=75,
        ),
        item(
            "you_4", "If a + b = 7 and ab = 12, what is a^2 + b^2?",
            opts("13", "25", "37", "49", "61"), "B",
            "a^2 + b^2 = (a + b)^2 − 2ab = 49 − 24 = 25.",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Simplify 5(x − 2) + 3x.",
                opts("8x − 10", "8x − 2", "8x − 7", "5x − 10", "8x + 10"), "A",
                "5x − 10 + 3x = 8x − 10.",
                difficulty="easy",
            ),
            item(
                "mc_2", "Factor: x^2 − 9.",
                opts("(x − 3)^2", "(x − 3)(x + 3)", "(x − 9)(x + 1)", "(x + 3)^2", "x(x − 9)"), "B",
                "Difference of squares: x^2 − 9 = (x − 3)(x + 3).",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Elementary Algebra 2e — Polynomials & Factoring", "url": OSX_ELEM, "note": "Like terms, special products, GCF and difference-of-squares factoring.", "primary": True},
        {"name": "Khan Academy — Algebraic expressions", "url": KHAN_ALG, "note": "Distributing, multiplying binomials, and factoring."},
        GMAT,
    ],
    tags=["algebra", "expressions", "foil", "factoring", "exponent-rules", "substitution", "difference-of-squares"],
)


T_linear_equations = topic(
    topic_id="gmat::quant::algebra::linear_equations",
    slug="linear-equations",
    title="Linear Equations & Systems",
    domain="Algebra",
    estimated_minutes=22,
    prerequisites=["algebraic expressions"],
    learning_objectives=[
        "Solve one-variable linear equations, including those with parentheses and fractions.",
        "Use inverse operations in the right order.",
        "Solve two-variable systems by substitution and by elimination.",
        "Translate simple statements into linear equations.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Combining like terms and distributing.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Solve 2x + 5 = 13.", "answer": "x = 4.", "targets": "two-step equation"},
                {"prompt": "Solve x/3 = 6.", "answer": "x = 18.", "targets": "clearing a fraction"},
                {"prompt": "Solve 3(x − 2) = 9.", "answer": "x = 5.", "targets": "distribute then solve"},
                {"prompt": "If x + y = 10 and x = 4, find y.", "answer": "y = 6.", "targets": "substitution idea"},
                {"prompt": "In 2x + 5 = 13, why subtract 5 before dividing by 2?", "answer": "Undo operations in reverse (inverse) order — addition last applied is undone first.", "targets": "inverse-operation logic"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves the isolate-the-variable routine and the substitution idea that drives systems today.",
            "if_students_struggle": "If order trips them, label the operations done TO x, then undo them last-in-first-out.",
            "questions": [
                {"prompt": "Simplify 3x + 5x − 2x.", "answer": "6x.", "targets": "combining like terms (algebraic expressions)"},
                {"prompt": "Expand 3(x − 2).", "answer": "3x − 6.", "targets": "distributing (algebraic expressions)"},
                {"prompt": "Evaluate 2x + 5 when x = 4.", "answer": "13.", "targets": "evaluating expressions (algebraic expressions)"},
            ],
        },
        "prior_knowledge_bridge": "Solving an equation is just undoing operations in reverse, as Q5 highlights. A system is two equations sharing the same unknowns; the trick is to remove one variable — by substitution (use one equation inside the other) or elimination (add/subtract to cancel) — and reduce it to the single-variable problem you already own.",
        "learning_intention": "By the end you can solve linear equations (including fractional ones) and two-variable systems by substitution or elimination.",
        "success_criteria": [
            "I can isolate a variable using inverse operations in the correct order.",
            "I can clear fractions before solving.",
            "I can solve a 2×2 system and check the solution in both equations.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; verbalize inverse-operation order from Q5."},
            {"time": "6:00–8:00", "move": "Bridge: systems → eliminate one variable, then it's a one-variable solve."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: solve 5x − 3 = 2x + 12."},
        ],
    },
    i_do=item(
        "i_do", "Solve for x: 5x − 3 = 2x + 12.",
        opts("3", "5", "9", "15", "−5"), "B",
        "Collect variables: 5x − 2x = 12 + 3 → 3x = 15 → x = 5.",
        difficulty="medium",
        think_aloud_steps=[
            "Move variable terms to one side: subtract 2x from both → 3x − 3 = 12.",
            "Move constants to the other side: add 3 → 3x = 15.",
            "Divide by the coefficient: x = 15/3 = 5.",
            "Check: 5(5) − 3 = 22 and 2(5) + 12 = 22. ✓",
        ],
        key_takeaway="Gather variable terms on one side and constants on the other, then divide by the coefficient.",
    ),
    we_do=[
        item(
            "we_1", "Solve: x/2 + 3 = 11.",
            opts("4", "8", "14", "16", "22"), "D",
            "Subtract 3: x/2 = 8. Multiply by 2: x = 16.",
            difficulty="easy",
            scaffold_hints=[
                "Undo the +3 first.",
                "x/2 = 8.",
                "Multiply both sides by 2.",
            ],
            immediate_feedback={
                "if_correct": "Right — x = 16.",
                "if_incorrect": "Subtract 3 before clearing the fraction; then multiply by 2.",
            },
        ),
        item(
            "we_2", "Solve the system and find x:  x + y = 10,  x − y = 4.",
            opts("3", "5", "6", "7", "10"), "D",
            "Add the equations to eliminate y: 2x = 14, so x = 7.",
            difficulty="medium",
            scaffold_hints=[
                "Adding the two equations cancels y.",
                "2x = 14.",
                "x = 7 (then y = 3).",
            ],
            immediate_feedback={
                "if_correct": "Yes — x = 7.",
                "if_incorrect": "Add the equations; the +y and −y cancel, leaving 2x = 14.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "Solve: 4(x + 2) = 3x + 14.",
            opts("2", "4", "6", "8", "22"), "C",
            "4x + 8 = 3x + 14 → x = 6.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "If 2x − 7 = 11, what is 3x?",
            opts("9", "18", "24", "27", "30"), "D",
            "2x = 18 → x = 9 → 3x = 27.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_3", "Solve the system and find y:  2x + 3y = 16,  x = y + 3.",
            opts("1", "2", "3", "4", "5"), "B",
            "Substitute x = y + 3: 2(y + 3) + 3y = 16 → 5y + 6 = 16 → y = 2.",
            difficulty="hard", target_seconds=105,
        ),
        item(
            "you_4", "Three consecutive even integers add up to 78. What is the largest of the three?",
            opts("24", "26", "28", "30", "32"), "C",
            "Let them be n, n+2, n+4: 3n + 6 = 78 → n = 24, so the integers are 24, 26, 28; the largest is 28.",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Solve: 7x + 2 = 4x + 20.",
                opts("3", "6", "9", "18", "22"), "B",
                "3x = 18 → x = 6.",
                difficulty="easy",
            ),
            item(
                "mc_2", "Solve the system and find x:  x + 2y = 11,  3x − 2y = 9.",
                opts("3", "4", "5", "7", "11"), "C",
                "Add the equations: 4x = 20 → x = 5.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Elementary Algebra 2e — Linear Equations & Systems", "url": OSX_ELEM, "note": "Solving linear equations and 2-variable systems.", "primary": True},
        {"name": "Khan Academy — Solving equations & systems", "url": KHAN_ALG, "note": "One-variable solving, substitution, and elimination."},
        GMAT,
    ],
    tags=["algebra", "linear-equations", "systems", "substitution", "elimination", "translation"],
)


T_quadratics = topic(
    topic_id="gmat::quant::algebra::quadratics",
    slug="quadratics",
    title="Quadratic Equations",
    domain="Algebra",
    estimated_minutes=24,
    prerequisites=["algebraic expressions (factoring)", "linear equations"],
    learning_objectives=[
        "Factor a quadratic of the form x^2 + bx + c.",
        "Solve quadratics using the zero-product property.",
        "Solve x^2 = kx without losing the x = 0 root.",
        "Use the relationships sum of roots = −b and product of roots = c (for monic quadratics).",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Factoring expressions and solving linear equations.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Factor x^2 + 5x + 6.", "answer": "(x + 2)(x + 3).", "targets": "factoring trinomials"},
                {"prompt": "Expand (x + 4)(x − 1).", "answer": "x^2 + 3x − 4.", "targets": "FOIL (check of factoring)"},
                {"prompt": "Solve x(x − 3) = 0.", "answer": "x = 0 or x = 3.", "targets": "zero-product property"},
                {"prompt": "Factor x^2 − 16.", "answer": "(x − 4)(x + 4).", "targets": "difference of squares"},
                {"prompt": "If (x − 2)(x + 5) = 0, why must a factor be 0?", "answer": "A product equals 0 only if at least one factor is 0.", "targets": "the logic that turns factoring into solving"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves trinomial factoring, difference of squares, and the zero-product property — the three tools that solve almost every GMAT quadratic.",
            "if_students_struggle": "If factoring stalls, list factor pairs of c and test which pair sums to b.",
            "questions": [
                {"prompt": "Factor x^2 + 5x + 6.", "answer": "(x + 2)(x + 3).", "targets": "factoring trinomials (algebraic expressions)"},
                {"prompt": "Factor x^2 − 16.", "answer": "(x − 4)(x + 4).", "targets": "difference of squares (algebraic expressions)"},
                {"prompt": "Solve 2x − 4 = 0.", "answer": "x = 2.", "targets": "linear equations"},
            ],
        },
        "prior_knowledge_bridge": "You can already factor (last lesson) and solve linear equations. Q5 is the hinge that connects them: once a quadratic is factored and set equal to 0, the zero-product property turns it into two linear equations. Today you'll factor, then solve — and learn the trap of dividing by x.",
        "learning_intention": "By the end you can solve quadratic equations by factoring and the zero-product property, and read off the sum and product of the roots.",
        "success_criteria": [
            "I can factor x^2 + bx + c by finding two numbers with product c and sum b.",
            "I can apply the zero-product property to get both solutions.",
            "I move everything to one side instead of dividing by x.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; emphasize zero-product reasoning (Q5)."},
            {"time": "6:00–8:00", "move": "Bridge: factor → set each factor to 0 → two linear solves."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: solve x^2 − 7x + 10 = 0."},
        ],
    },
    i_do=item(
        "i_do", "Solve for x: x^2 − 7x + 10 = 0.",
        opts("x = 2 or x = 5", "x = −2 or x = −5", "x = 1 or x = 10", "x = 2 or x = −5", "x = −2 or x = 5"), "A",
        "Two numbers with product +10 and sum −7 are −2 and −5: (x − 2)(x − 5) = 0, so x = 2 or x = 5.",
        difficulty="medium",
        think_aloud_steps=[
            "Need two numbers multiplying to +10 and adding to −7 → −2 and −5.",
            "Factor: (x − 2)(x − 5) = 0.",
            "Zero-product property: x − 2 = 0 or x − 5 = 0.",
            "So x = 2 or x = 5.",
        ],
        key_takeaway="For x^2 + bx + c = 0, find two numbers multiplying to c and adding to b; then set each factor to 0.",
    ),
    we_do=[
        item(
            "we_1", "Solve: x^2 + 2x − 15 = 0.",
            opts("x = 3 or 5", "x = −5 or 3", "x = 5 or −3", "x = −5 or −3", "x = 15 or −1"), "B",
            "Product −15, sum +2 → +5 and −3: (x + 5)(x − 3) = 0, so x = −5 or x = 3.",
            difficulty="medium",
            scaffold_hints=[
                "Find two numbers with product −15 and sum +2.",
                "+5 and −3 work.",
                "(x + 5)(x − 3) = 0.",
            ],
            immediate_feedback={
                "if_correct": "Right — x = −5 or 3.",
                "if_incorrect": "A negative product means opposite signs; the larger absolute value (5) carries the sign of b (+).",
            },
        ),
        item(
            "we_2", "Solve: x^2 = 9x.",
            opts("x = 9", "x = 0 or 9", "x = 3 or −3", "x = 0 or −9", "x = 81"), "B",
            "Move everything to one side: x^2 − 9x = 0 → x(x − 9) = 0 → x = 0 or x = 9.",
            difficulty="medium",
            scaffold_hints=[
                "Don't divide by x — that throws away a root.",
                "Bring all terms to one side: x^2 − 9x = 0.",
                "Factor out x: x(x − 9) = 0.",
            ],
            immediate_feedback={
                "if_correct": "Yes — both x = 0 and x = 9.",
                "if_incorrect": "Dividing by x loses x = 0. Factor instead.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "Solve: x^2 − 5x − 14 = 0.",
            opts("x = 7 or 2", "x = 7 or −2", "x = −7 or 2", "x = −7 or −2", "x = 14 or −1"), "B",
            "Product −14, sum −5 → −7 and +2: (x − 7)(x + 2) = 0, so x = 7 or x = −2.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "If (x − 4)(x + 6) = 0, what is the sum of the solutions?",
            opts("−2", "2", "10", "−24", "−10"), "A",
            "Solutions are x = 4 and x = −6; their sum is −2.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_3", "One solution of x^2 + kx + 12 = 0 is x = 3. What is k?",
            opts("−7", "−4", "4", "7", "−12"), "A",
            "Substitute x = 3: 9 + 3k + 12 = 0 → 3k = −21 → k = −7.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "The two solutions of x^2 − bx + 12 = 0 are positive integers. Which of the following could be the value of b?",
            opts("5", "7", "10", "11", "14"), "B",
            "Positive-integer roots multiplying to 12 are (1,12), (2,6), (3,4), giving b = sum = 13, 8, or 7. Only 7 appears.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Solve: x^2 − x − 6 = 0.",
                opts("x = 3 or 2", "x = 3 or −2", "x = −3 or 2", "x = 6 or −1", "x = −3 or −2"), "B",
                "Product −6, sum −1 → −3 and +2: (x − 3)(x + 2) = 0, so x = 3 or x = −2.",
                difficulty="medium",
            ),
            item(
                "mc_2", "What is the product of the solutions of x^2 − 9x + 20 = 0?",
                opts("−9", "9", "20", "−20", "5"), "C",
                "For x^2 + bx + c, the product of the roots is c = 20 (the roots are 4 and 5).",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Elementary Algebra 2e — Quadratic Equations", "url": OSX_ELEM, "note": "Factoring and the zero-product property.", "primary": True},
        {"name": "Khan Academy — Quadratic equations", "url": KHAN_ALG, "note": "Factoring, zero-product, and roots."},
        GMAT,
    ],
    tags=["algebra", "quadratics", "factoring", "zero-product", "roots", "sum-product-of-roots"],
)


T_inequalities = topic(
    topic_id="gmat::quant::algebra::inequalities",
    slug="inequalities",
    title="Inequalities",
    domain="Algebra",
    estimated_minutes=22,
    prerequisites=["linear equations"],
    learning_objectives=[
        "Solve linear inequalities using inverse operations.",
        "Reverse the inequality sign when multiplying or dividing by a negative.",
        "Solve and interpret compound inequalities.",
        "Count integer solutions within a range.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Solving linear equations by inverse operations.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Solve x + 4 < 9.", "answer": "x < 5.", "targets": "basic inequality"},
                {"prompt": "Is −3 < −1 true?", "answer": "Yes (−3 is farther left).", "targets": "ordering negatives"},
                {"prompt": "Solve 2x > 10.", "answer": "x > 5.", "targets": "divide by positive"},
                {"prompt": "If x > 3, is x = 3 a solution?", "answer": "No — strict inequality excludes 3.", "targets": "strict vs inclusive"},
                {"prompt": "Solve −x < 4. Why does it become x > −4?", "answer": "Multiplying/dividing by a negative reverses the inequality.", "targets": "the sign-flip rule"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves equation-style solving and surfaces the single rule that makes inequalities different: flip when you multiply or divide by a negative.",
            "if_students_struggle": "If the flip is unintuitive, test x = −10 in −x < 4: −(−10) = 10, which is NOT < 4, confirming the reversed solution.",
            "questions": [
                {"prompt": "Solve 2x = 10.", "answer": "x = 5.", "targets": "solving a one-step equation (linear equations)"},
                {"prompt": "Solve x + 4 = 9.", "answer": "x = 5.", "targets": "solving equations (linear equations)"},
                {"prompt": "Solve 3x − 6 = 0.", "answer": "x = 2.", "targets": "isolating the variable (linear equations)"},
            ],
        },
        "prior_knowledge_bridge": "Inequalities solve exactly like equations — with one twist from Q5: multiplying or dividing both sides by a negative reverses the direction. Master that and you also handle compound inequalities (a range) and 'how many integers' questions the GMAT likes.",
        "learning_intention": "By the end you can solve linear and compound inequalities, flipping the sign correctly, and count integer solutions in a range.",
        "success_criteria": [
            "I solve inequalities with inverse operations like equations.",
            "I reverse the sign exactly when I divide/multiply by a negative.",
            "I can read a compound inequality as a range and count its integers.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; test a value to justify the flip in Q5."},
            {"time": "6:00–8:00", "move": "Bridge: same as equations + flip rule; preview compound ranges."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: solve −3x + 2 ≤ 11."},
        ],
    },
    i_do=item(
        "i_do", "Solve for x: −3x + 2 ≤ 11.",
        opts("x ≤ −3", "x ≥ −3", "x ≤ 3", "x ≥ 3", "x ≤ 9"), "B",
        "Subtract 2: −3x ≤ 9. Divide by −3 and FLIP the sign: x ≥ −3.",
        difficulty="medium",
        think_aloud_steps=[
            "Subtract 2 from both sides: −3x ≤ 9.",
            "Divide by −3 — because it's negative, reverse ≤ to ≥: x ≥ −3.",
            "Check x = 0: −3(0) + 2 = 2 ≤ 11 ✓ and 0 ≥ −3 ✓.",
        ],
        key_takeaway="Solve like an equation, but reverse the inequality whenever you multiply or divide by a negative number.",
    ),
    we_do=[
        item(
            "we_1", "Solve: 4x − 7 > 5.",
            opts("x > 3", "x < 3", "x > 12", "x > −3", "x < 12"), "A",
            "Add 7: 4x > 12. Divide by +4 (no flip): x > 3.",
            difficulty="easy",
            scaffold_hints=[
                "Add 7 to both sides.",
                "4x > 12.",
                "Divide by positive 4 — sign stays.",
            ],
            immediate_feedback={
                "if_correct": "Right — x > 3 (no flip, since 4 is positive).",
                "if_incorrect": "You only flip for a negative divisor; here it's +4.",
            },
        ),
        item(
            "we_2", "Solve: 5 − 2x ≥ 1.",
            opts("x ≤ 2", "x ≥ 2", "x ≤ −2", "x ≥ −2", "x ≤ 3"), "A",
            "Subtract 5: −2x ≥ −4. Divide by −2 and flip: x ≤ 2.",
            difficulty="medium",
            scaffold_hints=[
                "Subtract 5: −2x ≥ −4.",
                "Dividing by −2 reverses ≥ to ≤.",
                "x ≤ 2.",
            ],
            immediate_feedback={
                "if_correct": "Yes — x ≤ 2.",
                "if_incorrect": "The −2 divisor forces the flip; ≥ becomes ≤.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "Solve: 3x + 4 < x + 12.",
            opts("x < 4", "x > 4", "x < 8", "x < 16", "x > 8"), "A",
            "3x + 4 < x + 12 → 2x < 8 → x < 4 (divide by +2, no flip).",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "If −2 < x ≤ 3 and x is an integer, how many values can x take?",
            opts("4", "5", "6", "7", "3"), "B",
            "Integers with −2 < x ≤ 3 are −1, 0, 1, 2, 3 — five values (−2 excluded, 3 included).",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "Solve: −4 ≤ 2x − 6 < 8.",
            opts("1 ≤ x < 7", "1 < x ≤ 7", "−1 ≤ x < 7", "1 ≤ x ≤ 7", "2 ≤ x < 14"), "A",
            "Add 6 throughout: 2 ≤ 2x < 14; divide by 2: 1 ≤ x < 7.",
            difficulty="hard", target_seconds=105,
        ),
        item(
            "you_4", "If 3 − 2x > 7, which of the following must be true?",
            opts("x > 2", "x < −2", "x > −2", "x < 2", "x = −2"), "B",
            "3 − 2x > 7 → −2x > 4 → x < −2 (flip when dividing by −2).",
            difficulty="hard", target_seconds=75,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Solve: 2x + 9 ≤ 3.",
                opts("x ≤ −3", "x ≥ −3", "x ≤ 3", "x ≤ −6", "x ≥ 3"), "A",
                "2x ≤ −6 → x ≤ −3 (divide by +2, no flip).",
                difficulty="easy",
            ),
            item(
                "mc_2", "If −x/2 > 3, then:",
                opts("x > −6", "x < −6", "x > 6", "x < 6", "x > −3"), "B",
                "Multiply both sides by −2 and flip: x < −6.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Elementary Algebra 2e — Inequalities", "url": OSX_ELEM, "note": "Solving linear and compound inequalities.", "primary": True},
        {"name": "Khan Academy — Inequalities", "url": KHAN_ALG, "note": "One- and two-step inequalities and the sign-flip rule."},
        GMAT,
    ],
    tags=["algebra", "inequalities", "sign-flip", "compound-inequality", "integer-solutions"],
)

T_absolute_value = topic(
    topic_id="gmat::quant::algebra::absolute_value",
    slug="absolute-value",
    title="Absolute Value",
    domain="Algebra",
    estimated_minutes=22,
    prerequisites=["inequalities", "the number line"],
    learning_objectives=[
        "Interpret |x| as distance from zero (always ≥ 0).",
        "Solve |A| = c by splitting into A = c and A = −c.",
        "Solve |A| < c as a band (−c < A < c) and |A| > c as two rays.",
        "Count integer solutions of absolute-value inequalities.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "The number line and solving equations/inequalities.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Compute |−7|.", "answer": "7.", "targets": "absolute value as magnitude"},
                {"prompt": "Compute |3 − 10|.", "answer": "7.", "targets": "evaluate inside first"},
                {"prompt": "Solve |x| = 5.", "answer": "x = 5 or x = −5.", "targets": "two-case structure"},
                {"prompt": "Can |x| ever be negative?", "answer": "No — it's a distance, so it's ≥ 0.", "targets": "range of absolute value"},
                {"prompt": "Why does |x| = 5 have two solutions?", "answer": "Both 5 and −5 are distance 5 from 0.", "targets": "distance interpretation"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves the distance meaning of |x| and the two-solution idea, which generalize into the two-case method for equations and inequalities today.",
            "if_students_struggle": "If two cases feel arbitrary, mark 5 and −5 on a number line and note both sit 5 units from 0.",
            "questions": [
                {"prompt": "Solve 2x < 6.", "answer": "x < 3.", "targets": "inequalities"},
                {"prompt": "Solve −x < 4.", "answer": "x > −4 (flip when dividing by a negative).", "targets": "inequality sign-flip"},
                {"prompt": "On a number line, which is greater: −5 or −2?", "answer": "−2 (it is farther right).", "targets": "the number line"},
            ],
        },
        "prior_knowledge_bridge": "Absolute value is distance from zero — that single idea (Q5) explains everything today. '= c' means two points (c and −c); '< c' means everything within c of zero (a band); '> c' means everything farther than c (two outward rays). You'll turn each into the plain equations and inequalities you already solve.",
        "learning_intention": "By the end you can solve absolute-value equations with two cases and absolute-value inequalities as bands or two rays.",
        "success_criteria": [
            "I can split |A| = c into A = c and A = −c.",
            "I can rewrite |A| < c as −c < A < c.",
            "I can rewrite |A| > c as A > c or A < −c.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; place ±5 on a number line for Q5."},
            {"time": "6:00–8:00", "move": "Bridge: distance → equation two cases and inequality band/rays."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: solve |2x − 3| = 7."},
        ],
    },
    i_do=item(
        "i_do", "Solve for x: |2x − 3| = 7.",
        opts("x = 5 or x = −2", "x = 5 or x = 2", "x = −5 or x = 2", "x = 5", "x = 2 or x = −2"), "A",
        "The inside is 7 or −7. Case 1: 2x − 3 = 7 → x = 5. Case 2: 2x − 3 = −7 → x = −2.",
        difficulty="medium",
        think_aloud_steps=[
            "|something| = 7 means that something is 7 or −7.",
            "Case 1: 2x − 3 = 7 → 2x = 10 → x = 5.",
            "Case 2: 2x − 3 = −7 → 2x = −4 → x = −2.",
            "Two solutions: x = 5 and x = −2.",
        ],
        key_takeaway="|A| = c (with c ≥ 0) always splits into A = c or A = −c — two cases.",
    ),
    we_do=[
        item(
            "we_1", "Solve: |x + 4| = 9.",
            opts("x = 5 or −13", "x = 5 or 13", "x = −5 or 13", "x = 5", "x = −13"), "A",
            "x + 4 = 9 → x = 5; or x + 4 = −9 → x = −13.",
            difficulty="easy",
            scaffold_hints=[
                "The inside equals 9 or −9.",
                "x + 4 = 9 → x = 5.",
                "x + 4 = −9 → x = −13.",
            ],
            immediate_feedback={
                "if_correct": "Right — x = 5 or −13.",
                "if_incorrect": "Don't forget the negative case: x + 4 = −9 gives x = −13.",
            },
        ),
        item(
            "we_2", "Solve: |x| < 3.",
            opts("x < 3", "x > 3", "−3 < x < 3", "x < −3 or x > 3", "x ≤ 3"), "C",
            "Distance from 0 less than 3 means x is between −3 and 3: −3 < x < 3.",
            difficulty="medium",
            scaffold_hints=[
                "|x| < 3 means x is within 3 units of zero.",
                "That's an interval around 0.",
                "−3 < x < 3.",
            ],
            immediate_feedback={
                "if_correct": "Yes — the band −3 < x < 3.",
                "if_incorrect": "'Less than' makes a single band between −c and c, not two separate rays.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "Solve: |3x| = 12.",
            opts("x = 4", "x = 4 or −4", "x = 36 or −36", "x = 12 or −12", "x = 3 or −3"), "B",
            "3x = 12 or 3x = −12 → x = 4 or x = −4.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_2", "How many integer solutions does |x| < 4 have?",
            opts("3", "4", "6", "7", "8"), "D",
            "−4 < x < 4 gives integers −3, −2, −1, 0, 1, 2, 3 → 7 values.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "Solve: |x − 5| > 2.",
            opts("3 < x < 7", "x > 7 or x < 3", "x > 3", "x < 7", "x > 7 or x < −3"), "B",
            "x − 5 > 2 (x > 7) or x − 5 < −2 (x < 3).",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_4", "Solve: |2x + 1| ≤ 5.",
            opts("−3 ≤ x ≤ 2", "−2 ≤ x ≤ 3", "x ≤ 2", "−3 ≤ x ≤ 3", "x ≥ −3"), "A",
            "−5 ≤ 2x + 1 ≤ 5 → −6 ≤ 2x ≤ 4 → −3 ≤ x ≤ 2.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Solve: |x − 2| = 6.",
                opts("x = 8 or −4", "x = 8 or 4", "x = −8 or 4", "x = 8", "x = 4 or −4"), "A",
                "x − 2 = 6 → x = 8; or x − 2 = −6 → x = −4.",
                difficulty="medium",
            ),
            item(
                "mc_2", "The solution to |x| ≥ 2 is:",
                opts("−2 ≤ x ≤ 2", "x ≤ −2 or x ≥ 2", "x ≥ 2", "x ≤ 2", "x ≥ −2"), "B",
                "Distance from 0 at least 2 → x ≤ −2 or x ≥ 2 (two outward rays).",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Intermediate Algebra 2e — Absolute Value Equations & Inequalities", "url": OSX_INT, "note": "Two-case equations and band/ray inequalities.", "primary": True},
        {"name": "Khan Academy — Absolute value equations & inequalities", "url": KHAN_ALG, "note": "Distance interpretation and solving."},
        GMAT,
    ],
    tags=["algebra", "absolute-value", "two-case", "distance", "compound-inequality"],
)


T_functions = topic(
    topic_id="gmat::quant::algebra::functions",
    slug="functions",
    title="Functions",
    domain="Algebra",
    estimated_minutes=22,
    prerequisites=["algebraic expressions", "linear equations"],
    learning_objectives=[
        "Read and use function notation f(x); evaluate by substitution.",
        "Evaluate compositions f(g(x)) from the inside out.",
        "Interpret GMAT-style custom operation symbols.",
        "Solve for an input given an output, and find an unknown inner function.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Evaluating expressions by substitution.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "If f(x) = 2x + 1, find f(3).", "answer": "7.", "targets": "function notation"},
                {"prompt": "If g(x) = x^2, find g(−4).", "answer": "16.", "targets": "substituting a negative"},
                {"prompt": "Evaluate 3a − 2 at a = 5.", "answer": "13.", "targets": "substitution"},
                {"prompt": "If f(x) = x − 4, find f(4).", "answer": "0.", "targets": "evaluation"},
                {"prompt": "In f(g(2)), what do you compute first?", "answer": "g(2) first (inside out), then apply f.", "targets": "order of composition"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves substitution (the only mechanical skill functions need) and the inside-out order that composition and custom symbols depend on.",
            "if_students_struggle": "If notation feels alien, read f(3) as 'the rule f applied to 3' — substitute 3 wherever x appears.",
            "questions": [
                {"prompt": "Evaluate 2x + 1 when x = 3.", "answer": "7.", "targets": "evaluating expressions (algebraic expressions)"},
                {"prompt": "Evaluate x^2 when x = −4.", "answer": "16.", "targets": "substituting a negative value"},
                {"prompt": "Solve x + 1 = 10.", "answer": "x = 9.", "targets": "linear equations"},
            ],
        },
        "prior_knowledge_bridge": "A function is just a substitution rule with a name. You've evaluated expressions for years; f(x) only labels the rule so we can chain rules. Q5 sets up the one new habit: in f(g(x)) you work the inside first. Custom GMAT symbols (like a ◇ b) are the same idea wearing a costume.",
        "learning_intention": "By the end you can evaluate functions and compositions, decode custom operation symbols, and solve for an input or an inner rule.",
        "success_criteria": [
            "I can evaluate f(x) for any input, including negatives.",
            "I can compute f(g(x)) inside out.",
            "I can apply a defined custom operation correctly.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; read notation aloud as 'apply the rule to'."},
            {"time": "6:00–8:00", "move": "Bridge: composition is inside-out; custom symbols are disguised functions."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: f(g(2)) with f(x)=2x+3, g(x)=x^2."},
        ],
    },
    i_do=item(
        "i_do", "If f(x) = 2x + 3 and g(x) = x^2, what is f(g(2))?",
        opts("7", "11", "14", "19", "49"), "B",
        "Inside out: g(2) = 2^2 = 4, then f(4) = 2(4) + 3 = 11.",
        difficulty="medium",
        think_aloud_steps=[
            "Composition works from the inside out — do g(2) first.",
            "g(2) = 2^2 = 4.",
            "Now apply f to that result: f(4) = 2·4 + 3 = 11.",
        ],
        key_takeaway="For f(g(x)), evaluate the inner function first, then substitute that value into the outer function.",
    ),
    we_do=[
        item(
            "we_1", "If f(x) = 3x − 5, find f(−2).",
            opts("−11", "−1", "1", "11", "−6"), "A",
            "f(−2) = 3(−2) − 5 = −6 − 5 = −11.",
            difficulty="easy",
            scaffold_hints=[
                "Substitute x = −2 everywhere.",
                "3(−2) = −6.",
                "−6 − 5 = −11.",
            ],
            immediate_feedback={
                "if_correct": "Right — −11.",
                "if_incorrect": "Keep the negative: 3 times −2 is −6, then subtract 5.",
            },
        ),
        item(
            "we_2", "A custom operation is defined by a ◇ b = a^2 − b. What is 5 ◇ 3?",
            opts("22", "13", "28", "2", "8"), "A",
            "Replace a with 5 and b with 3: 5^2 − 3 = 25 − 3 = 22.",
            difficulty="medium",
            scaffold_hints=[
                "Match the symbols: a = 5, b = 3.",
                "a^2 = 25.",
                "25 − 3 = 22.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 22.",
                "if_incorrect": "Square the first input (a), then subtract the second (b).",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "If f(x) = x^2 + 1, what is f(3) − f(1)?",
            opts("6", "8", "9", "10", "12"), "B",
            "f(3) = 10 and f(1) = 2, so f(3) − f(1) = 8.",
            difficulty="medium", target_seconds=60,
        ),
        item(
            "you_2", "If g(x) = (x + 1)/2, for what value of x does g(x) = 5?",
            opts("4", "9", "10", "11", "24"), "B",
            "(x + 1)/2 = 5 → x + 1 = 10 → x = 9.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_3", "If f(x) = 2x − 1 and f(g(x)) = 4x + 3, what is g(x)?",
            opts("2x + 2", "2x − 2", "4x + 4", "2x + 1", "x + 2"), "A",
            "f(g(x)) = 2·g(x) − 1 = 4x + 3 → 2g(x) = 4x + 4 → g(x) = 2x + 2.",
            difficulty="hard", target_seconds=105,
        ),
        item(
            "you_4", "The operation ★ is defined by n★ = n^2 − n. What is (3★)★?",
            opts("6", "30", "36", "42", "870"), "B",
            "3★ = 9 − 3 = 6; then 6★ = 36 − 6 = 30.",
            difficulty="hard", target_seconds=90,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "If f(x) = 4 − x^2, find f(−3).",
                opts("13", "1", "−5", "−13", "5"), "C",
                "f(−3) = 4 − (−3)^2 = 4 − 9 = −5.",
                difficulty="medium",
            ),
            item(
                "mc_2", "If f(x) = 2x and g(x) = x + 4, what is g(f(3))?",
                opts("10", "14", "9", "18", "22"), "A",
                "f(3) = 6, then g(6) = 6 + 4 = 10.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Intermediate Algebra 2e — Functions", "url": OSX_INT, "note": "Function notation, evaluation, and composition.", "primary": True},
        {"name": "Khan Academy — Functions", "url": KHAN_ALG2, "note": "Evaluating functions and composing them."},
        GMAT,
    ],
    tags=["algebra", "functions", "function-notation", "composition", "custom-operations"],
)


T_sequences = topic(
    topic_id="gmat::quant::algebra::sequences",
    slug="sequences",
    title="Sequences",
    domain="Algebra",
    estimated_minutes=22,
    prerequisites=["functions", "algebraic expressions"],
    learning_objectives=[
        "Identify arithmetic (constant difference) vs geometric (constant ratio) sequences.",
        "Use the arithmetic nth-term formula a_n = a_1 + (n − 1)d.",
        "Use the geometric nth-term formula a_n = a_1 · r^(n−1).",
        "Find the sum of an arithmetic sequence with (n/2)(first + last).",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Function evaluation and recognizing patterns.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "Next term: 3, 7, 11, 15, ___ .", "answer": "19 (add 4).", "targets": "arithmetic pattern"},
                {"prompt": "Next term: 2, 6, 18, 54, ___ .", "answer": "162 (multiply by 3).", "targets": "geometric pattern"},
                {"prompt": "Common difference of 5, 8, 11, 14?", "answer": "3.", "targets": "common difference"},
                {"prompt": "Common ratio of 1, 2, 4, 8?", "answer": "2.", "targets": "common ratio"},
                {"prompt": "Why is a formula faster than listing to find the 100th term of 3, 7, 11, …?", "answer": "A formula jumps straight to term 100 instead of writing 99 terms first.", "targets": "motivation for nth-term formulas"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves the difference/ratio distinction and the need for a direct formula — exactly what the nth-term rules provide today.",
            "if_students_struggle": "If difference vs ratio blurs, ask 'add or multiply to advance?' — add = arithmetic, multiply = geometric.",
            "questions": [
                {"prompt": "If f(n) = 3n + 1, find f(4).", "answer": "13.", "targets": "function evaluation (functions)"},
                {"prompt": "If g(x) = 2x, find g(5).", "answer": "10.", "targets": "function notation (functions)"},
                {"prompt": "Evaluate 4 + (n − 1) × 3 when n = 20.", "answer": "61.", "targets": "evaluating an expression (algebraic expressions)"},
            ],
        },
        "prior_knowledge_bridge": "A sequence is a function whose input is the term number n. You spotted the step rule in the Do-Now; today you turn that rule into a formula so you can leap to the 20th or 100th term without listing. Arithmetic adds a fixed d; geometric multiplies by a fixed r — same idea, different operation.",
        "learning_intention": "By the end you can find any term of an arithmetic or geometric sequence with its formula and sum an arithmetic sequence.",
        "success_criteria": [
            "I can apply a_n = a_1 + (n − 1)d for arithmetic sequences.",
            "I can apply a_n = a_1 · r^(n−1) for geometric sequences.",
            "I can sum an arithmetic sequence with (n/2)(first + last).",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; sort each Do-Now sequence as arithmetic or geometric."},
            {"time": "6:00–8:00", "move": "Bridge: term number is the input; derive the (n−1) multiplier."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: 20th term of 4, 7, 10, 13, …"},
        ],
    },
    i_do=item(
        "i_do", "In the arithmetic sequence 4, 7, 10, 13, …, what is the 20th term?",
        opts("58", "60", "61", "64", "67"), "C",
        "a_1 = 4, d = 3. a_20 = a_1 + (n − 1)d = 4 + 19·3 = 4 + 57 = 61.",
        difficulty="medium",
        think_aloud_steps=[
            "First term a_1 = 4; common difference d = 7 − 4 = 3.",
            "Use a_n = a_1 + (n − 1)d.",
            "a_20 = 4 + (20 − 1)(3) = 4 + 57 = 61.",
        ],
        key_takeaway="Arithmetic nth term: a_n = a_1 + (n − 1)d. The jump count is (n − 1), not n.",
    ),
    we_do=[
        item(
            "we_1", "Find the 10th term of the arithmetic sequence with a_1 = 5 and d = 4.",
            opts("36", "40", "41", "45", "49"), "C",
            "a_10 = 5 + (10 − 1)(4) = 5 + 36 = 41.",
            difficulty="easy",
            scaffold_hints=[
                "Use a_n = a_1 + (n − 1)d.",
                "n = 10 means 9 jumps of size 4.",
                "5 + 9(4) = 41.",
            ],
            immediate_feedback={
                "if_correct": "Right — 41.",
                "if_incorrect": "Multiply d by (n − 1) = 9, not by 10.",
            },
        ),
        item(
            "we_2", "In the geometric sequence 3, 6, 12, 24, …, what is the next term after 24?",
            opts("36", "30", "48", "96", "27"), "C",
            "Common ratio r = 6/3 = 2; next term = 24 × 2 = 48.",
            difficulty="medium",
            scaffold_hints=[
                "Find the ratio between consecutive terms: 6/3 = 2.",
                "Geometric sequences multiply by r each step.",
                "24 × 2 = 48.",
            ],
            immediate_feedback={
                "if_correct": "Yes — 48.",
                "if_incorrect": "This sequence multiplies (×2), it doesn't add a constant.",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "What is the 15th term of 2, 5, 8, 11, …?",
            opts("41", "42", "44", "45", "47"), "C",
            "a_1 = 2, d = 3: a_15 = 2 + 14(3) = 2 + 42 = 44.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_2", "The first term of a geometric sequence is 5 and the 4th term is 40. What is the common ratio?",
            opts("2", "3", "4", "8", "1/2"), "A",
            "a_4 = a_1 · r^3 = 5r^3 = 40 → r^3 = 8 → r = 2.",
            difficulty="hard", target_seconds=90,
        ),
        item(
            "you_3", "An arithmetic sequence has a_1 = 7 and a_5 = 23. What is the common difference?",
            opts("3", "4", "5", "16", "8"), "B",
            "a_5 = 7 + 4d = 23 → 4d = 16 → d = 4.",
            difficulty="medium", target_seconds=75,
        ),
        item(
            "you_4", "What is the sum of the first 10 terms of the arithmetic sequence 3, 7, 11, …?",
            opts("165", "195", "210", "220", "240"), "C",
            "a_10 = 3 + 9(4) = 39; sum = (10/2)(first + last) = 5(3 + 39) = 5·42 = 210.",
            difficulty="hard", target_seconds=105,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "Find the 8th term of the arithmetic sequence with a_1 = 10 and d = −2.",
                opts("4", "−2", "−4", "−6", "24"), "C",
                "a_8 = 10 + 7(−2) = 10 − 14 = −4.",
                difficulty="medium",
            ),
            item(
                "mc_2", "In a geometric sequence, a_1 = 2 and r = 3. What is a_4?",
                opts("18", "24", "54", "162", "216"), "C",
                "a_4 = a_1 · r^3 = 2 · 27 = 54.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Intermediate Algebra 2e — Sequences, Series", "url": OSX_INT, "note": "Arithmetic and geometric sequences and sums.", "primary": True},
        {"name": "Khan Academy — Sequences", "url": KHAN_ALG2, "note": "Explicit formulas for arithmetic and geometric sequences."},
        GMAT,
    ],
    tags=["algebra", "sequences", "arithmetic-sequence", "geometric-sequence", "nth-term", "series-sum"],
)


T_word_problems = topic(
    topic_id="gmat::quant::algebra::word_problems",
    slug="word-problems",
    title="Word Problems: Rate, Work, Mixture & Interest",
    domain="Algebra",
    estimated_minutes=26,
    prerequisites=["linear equations", "ratios & proportions", "percents"],
    learning_objectives=[
        "Use distance = rate × time, including total-time and relative-speed setups.",
        "Solve work problems by adding rates (jobs per unit time).",
        "Set up mixture/concentration problems by tracking the pure quantity.",
        "Compute simple interest with I = P·r·t.",
    ],
    pedagogical_model={
        "frameworks": ["Rosenshine (daily review)", "Archer (I-do/we-do/you-do)", "SPOV2 application-first"],
        "sequence": "I do → we do → you do",
        "application_first": True,
        "explanation_policy": "revealed_after_attempt",
    },
    opening={
        "builds_on": "Linear equations, rates/ratios, and percents.",
        "do_now": {
            "instructions": "From memory, no calculator. 4 minutes.",
            "items": [
                {"prompt": "A car goes 180 miles in 3 hours. What is its speed?", "answer": "60 mph.", "targets": "rate = distance/time"},
                {"prompt": "Find distance if rate = 50 mph and time = 4 h.", "answer": "200 miles (d = rt).", "targets": "the D = rt relationship"},
                {"prompt": "If a worker finishes a job in 6 hours, what fraction is done in 1 hour?", "answer": "1/6.", "targets": "work as a rate"},
                {"prompt": "5% simple interest on $200 for 1 year = ?", "answer": "$10.", "targets": "percent of an amount"},
                {"prompt": "Two cars approach each other at 40 and 60 mph. How fast does the gap close?", "answer": "100 mph — speeds add when moving toward each other.", "targets": "relative speed"},
            ],
        },
        "retrieval_starter": {
            "duration_minutes": 5,
            "purpose": "Retrieves D = rt, work-as-rate, percent-of, and relative speed — the four setups behind today's classic word-problem types.",
            "if_students_struggle": "If D = rt is shaky, drill the triangle (cover the unknown to get the formula) before composite problems.",
            "questions": [
                {"prompt": "Solve 4x = 200.", "answer": "x = 50.", "targets": "linear equations"},
                {"prompt": "A car goes 180 miles in 3 hours. What is its speed?", "answer": "60 mph.", "targets": "rates (ratios & proportions)"},
                {"prompt": "What is 5% of 200?", "answer": "10.", "targets": "percents"},
            ],
        },
        "prior_knowledge_bridge": "Every word problem today is a translation exercise built on one relationship you already know: rate × time = amount (miles, jobs, dollars of interest). The art is choosing a variable, writing one honest equation, and solving it with your linear-equation skills. Q5's relative-speed idea unlocks the trickier travel problems.",
        "learning_intention": "By the end you can translate rate, work, mixture, and interest scenarios into equations and solve them.",
        "success_criteria": [
            "I can set up and solve distance = rate × time problems, including total time.",
            "I can add work rates to find combined or individual times.",
            "I can track the pure quantity in a mixture and compute simple interest.",
        ],
        "opening_script": [
            {"time": "0:00–4:00", "move": "Do Now; silent retrieval."},
            {"time": "4:00–6:00", "move": "Check; surface relative speed from Q5."},
            {"time": "6:00–8:00", "move": "Bridge: all types are rate × time = amount; pick a variable, write one equation."},
            {"time": "8:00–9:00", "move": "Learning intention + success criteria."},
            {"time": "9:00–10:00", "move": "I do: two pipes filling a tank together."},
        ],
    },
    i_do=item(
        "i_do", "Pipe A fills a tank in 4 hours and pipe B fills the same tank in 6 hours. Working together, how long do they take to fill the tank?",
        opts("2.4 hours", "5 hours", "2 hours", "3 hours", "10 hours"), "A",
        "Add rates: 1/4 + 1/6 = 3/12 + 2/12 = 5/12 of the tank per hour. Time = 1 ÷ (5/12) = 12/5 = 2.4 hours.",
        difficulty="medium",
        think_aloud_steps=[
            "Convert each time to a rate: A does 1/4 tank per hour, B does 1/6.",
            "Working together, rates ADD: 1/4 + 1/6 = 5/12 tank per hour.",
            "Time = total work ÷ rate = 1 ÷ (5/12) = 12/5 = 2.4 hours (2 h 24 min).",
        ],
        key_takeaway="Work problems: add RATES (jobs per hour), never times. Combined time = 1 ÷ (sum of rates).",
    ),
    we_do=[
        item(
            "we_1", "A cyclist rides 60 miles at a steady 15 mph. How long does the trip take?",
            opts("3 hours", "4 hours", "5 hours", "45 hours", "900 hours"), "B",
            "time = distance ÷ rate = 60 ÷ 15 = 4 hours.",
            difficulty="easy",
            scaffold_hints=[
                "Rearrange d = rt to t = d/r.",
                "60 ÷ 15.",
                "= 4 hours.",
            ],
            immediate_feedback={
                "if_correct": "Right — 4 hours.",
                "if_incorrect": "Divide distance by rate; don't multiply.",
            },
        ),
        item(
            "we_2", "What is the simple interest on $500 at 6% per year for 2 years?",
            opts("$30", "$60", "$530", "$560", "$600"), "B",
            "I = P·r·t = 500 × 0.06 × 2 = $60.",
            difficulty="easy",
            scaffold_hints=[
                "Simple interest I = principal × rate × time.",
                "500 × 0.06 = 30 per year.",
                "× 2 years = 60.",
            ],
            immediate_feedback={
                "if_correct": "Yes — $60 of interest.",
                "if_incorrect": "The question asks for interest only, not the new balance ($560).",
            },
        ),
    ],
    you_do=[
        item(
            "you_1", "A car travels 150 miles at 50 mph, then 120 miles at 40 mph. What is the total travel time?",
            opts("5 hours", "5.5 hours", "6 hours", "6.5 hours", "7 hours"), "C",
            "150/50 = 3 hours and 120/40 = 3 hours; total = 6 hours.",
            difficulty="medium", target_seconds=90,
        ),
        item(
            "you_2", "Two workers together paint a fence in 3 hours. One of them alone would take 5 hours. How long would the other take alone?",
            opts("2 hours", "7.5 hours", "8 hours", "4 hours", "15 hours"), "B",
            "Combined rate 1/3; one is 1/5; the other = 1/3 − 1/5 = 2/15 fence/hour → time = 15/2 = 7.5 hours.",
            difficulty="hard", target_seconds=120,
        ),
        item(
            "you_3", "How many liters of pure water must be added to 10 liters of a 40% salt solution to dilute it to a 25% solution?",
            opts("4", "5", "6", "8", "15"), "C",
            "Salt stays 0.40 × 10 = 4 L. Need 4/(10 + x) = 0.25 → 10 + x = 16 → x = 6 liters.",
            difficulty="hard", target_seconds=120,
        ),
        item(
            "you_4", "A boat travels 30 miles downstream in 2 hours and returns the same 30 miles upstream in 3 hours. What is the speed of the boat in still water?",
            opts("10 mph", "11 mph", "12.5 mph", "13 mph", "15 mph"), "C",
            "Downstream b + c = 30/2 = 15; upstream b − c = 30/3 = 10. Adding: 2b = 25, so b = 12.5 mph.",
            difficulty="hard", target_seconds=120,
        ),
    ],
    mastery_check={
        "sample_held_out_items": [
            item(
                "mc_1", "A printer prints 24 pages per minute. How many minutes does it take to print 300 pages?",
                opts("10", "12", "12.5", "13", "15"), "C",
                "300 ÷ 24 = 12.5 minutes.",
                difficulty="easy",
            ),
            item(
                "mc_2", "Sam invests $800 at 5% simple annual interest. How much interest does he earn after 3 years?",
                opts("$40", "$80", "$120", "$200", "$920"), "C",
                "I = P·r·t = 800 × 0.05 × 3 = $120.",
                difficulty="medium",
            ),
        ],
    },
    citations=[
        {"name": "OpenStax, Elementary Algebra 2e — Applications (rate, work, mixture, interest)", "url": OSX_ELEM, "note": "Translating and solving classic word problems.", "primary": True},
        {"name": "Khan Academy — Rate & work word problems", "url": KHAN_ALG, "note": "Distance/rate/time, combined work, and mixtures."},
        GMAT,
    ],
    tags=["algebra", "word-problems", "rate-time-distance", "work-rate", "mixtures", "simple-interest", "relative-speed"],
)

ARITHMETIC = [
    T_number_properties,
    T_fractions,
    T_decimals,
    T_percents,
    T_ratios_proportions,
    T_exponents_roots,
    T_statistics,
    T_sets,
    T_counting,
    T_probability,
]

ALGEBRA = [
    T_algebraic_expressions,
    T_linear_equations,
    T_quadratics,
    T_inequalities,
    T_absolute_value,
    T_functions,
    T_sequences,
    T_word_problems,
]

TOPICS = ARITHMETIC + ALGEBRA
