#!/usr/bin/env python3
# Copyright: GMATWiz contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Author the paraphrase gold set for the memory-vs-performance test (challenge 7d).

Writes gmatwiz/content/paraphrase_gold.json: 30 ORIGINAL GMAT Quant base cards,
each with 2 reworded exam-style VARIANTS that test the SAME underlying idea with
new wording (and identical correct answer). All content is authored-gmatwiz; the
answers are recomputed here so they are provably correct. Nothing is copied from
any copyrighted/official source (the leakage check scans for that).

Schema:
  [{ id, topic, base:{stem,options{A..E},correct,explanation},
     variants:[{stem,options{A..E},correct}, {stem,options{A..E},correct}] }]

Run:  out/pyenv/bin/python gmatwiz/content/make_paraphrase_gold.py
"""

from __future__ import annotations

import json
import os
import random
from typing import Callable, Dict, List, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "paraphrase_gold.json")


def _options(value: int, rng: random.Random, suffix: str = "") -> Tuple[Dict[str, str], str]:
    """Five distinct positive options containing the correct value; return
    (options, correct_letter). Deterministic given rng."""
    cand = [value, value + 1, value - 1, value + 2, value * 2, value - 2, value + 3]
    seen: set = set()
    vals: List[int] = []
    for v in cand:
        if v > 0 and v not in seen:
            seen.add(v)
            vals.append(v)
        if len(vals) == 5:
            break
    while len(vals) < 5:  # pad if collisions removed too many
        v = max(vals) + 1
        if v not in seen:
            vals.append(v)
            seen.add(v)
    labels = list("ABCDE")
    pairs = [(v, v == value) for v in vals]
    rng.shuffle(pairs)
    options = {labels[i]: f"{pairs[i][0]}{suffix}" for i in range(5)}
    correct = labels[[i for i, (_, ok) in enumerate(pairs) if ok][0]]
    return options, correct


# Each builder returns (topic, answer, explanation, base_stem, variant1, variant2, suffix)
def _percents(a: int, b: int) -> Tuple:
    ans = a * b // 100
    return (
        "gmat::quant::arithmetic::percents", ans,
        f"{a}% of {b} = {a}/100 * {b} = {ans}.",
        f"What is {a}% of {b}?",
        f"Find {a} percent of {b}.",
        f"In a group of {b} people, {a}% attended. How many people attended?",
        "",
    )


def _linear(m: int, x: int, c: int) -> Tuple:
    d = m * x + c
    return (
        "gmat::quant::algebra::linear_equations", x,
        f"{m}x + {c} = {d}  =>  {m}x = {d - c}  =>  x = {x}.",
        f"If {m}x + {c} = {d}, what is the value of x?",
        f"Solve for x:  {m}x + {c} = {d}.",
        f"A number x satisfies '{m} times x, increased by {c}, equals {d}.' Find x.",
        "",
    )


def _fractions(num: int, den: int, n: int) -> Tuple:
    ans = num * n // den
    return (
        "gmat::quant::arithmetic::fractions", ans,
        f"({num}/{den}) * {n} = {ans}.",
        f"What is {num}/{den} of {n}?",
        f"Compute the product ({num}/{den}) x {n}.",
        f"{num}/{den} of a shipment of {n} boxes were delivered. How many boxes were delivered?",
        "",
    )


def _ratio(a: int, b: int, unit: int) -> Tuple:
    # total split in ratio a:b; total = (a+b)*unit; larger part = max(a,b)*unit
    ans = max(a, b) * unit
    total = (a + b) * unit
    return (
        "gmat::quant::arithmetic::ratios_proportions", ans,
        f"Ratio {a}:{b} over {total} => one share = {unit}; larger part = {max(a,b)} * {unit} = {ans}.",
        f"{total} is divided in the ratio {a}:{b}. What is the larger of the two parts?",
        f"Two amounts are in the ratio {a} to {b} and sum to {total}. Find the bigger amount.",
        f"A prize of {total} dollars is split between two teams in a {a}:{b} ratio. How much does the larger share get?",
        "",
    )


def _mean(x: int, y: int, z: int) -> Tuple:
    ans = (x + y + z) // 3
    return (
        "gmat::quant::arithmetic::statistics", ans,
        f"mean = ({x}+{y}+{z})/3 = {ans}.",
        f"What is the average (arithmetic mean) of {x}, {y}, and {z}?",
        f"Three values are {x}, {y}, and {z}. Find their mean.",
        f"Over three days a store sold {x}, {y}, and {z} units. What was the average daily number sold?",
        "",
    )


def _exponents(base: int, p: int) -> Tuple:
    ans = base ** p
    return (
        "gmat::quant::arithmetic::exponents_roots", ans,
        f"{base}^{p} = {ans}.",
        f"What is the value of {base}^{p}?",
        f"Compute {base} raised to the power {p}.",
        f"A quantity doubles-style growth: evaluate {base} multiplied by itself {p} times.",
        "",
    )


def build() -> List[Dict]:
    rng = random.Random("paraphrase-gold-v1")
    specs: List[Callable] = []
    # 5 items per builder * 6 builders = 30
    percents_args = [(15, 80), (25, 120), (40, 60), (12, 50), (30, 90)]
    linear_args = [(2, 4, 3), (3, 5, 2), (5, 6, 4), (4, 7, 1), (6, 3, 5)]
    fraction_args = [(3, 4, 40), (2, 5, 45), (5, 6, 42), (3, 8, 56), (7, 9, 27)]
    ratio_args = [(2, 3, 12), (3, 5, 8), (4, 1, 10), (5, 7, 6), (2, 7, 9)]
    mean_args = [(10, 20, 30), (12, 18, 24), (30, 45, 60), (14, 28, 42), (9, 15, 21)]
    exp_args = [(2, 5), (3, 3), (5, 3), (2, 7), (4, 3)]

    items: List[Dict] = []
    builders = [
        (_percents, percents_args),
        (_linear, linear_args),
        (_fractions, fraction_args),
        (_ratio, ratio_args),
        (_mean, mean_args),
        (_exponents, exp_args),
    ]
    idx = 0
    for fn, arglist in builders:
        for args in arglist:
            topic, ans, expl, base_stem, v1, v2, suffix = fn(*args)
            base_opts, base_correct = _options(ans, rng, suffix)
            v1_opts, v1_correct = _options(ans, rng, suffix)
            v2_opts, v2_correct = _options(ans, rng, suffix)
            items.append({
                "id": f"para-{idx:02d}",
                "topic": topic,
                "answer": ans,
                "base": {
                    "stem": base_stem,
                    "options": base_opts,
                    "correct": base_correct,
                    "explanation": expl,
                },
                "variants": [
                    {"stem": v1, "options": v1_opts, "correct": v1_correct},
                    {"stem": v2, "options": v2_opts, "correct": v2_correct},
                ],
                "source": "authored-gmatwiz",
                "license": "authored-gmatwiz",
            })
            idx += 1
    return items


def main() -> int:
    items = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"Wrote {len(items)} paraphrase items ({len(items)} base + "
          f"{sum(len(it['variants']) for it in items)} variants) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
