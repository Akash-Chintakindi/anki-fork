#!/usr/bin/env python3
"""Held-out topic-tagging eval: AI vs keyword vs tf-idf-vector baselines.

This is the "eval that runs before students see anything": topic auto-tagging is
the gate the content pipeline uses to route every question into the taxonomy
(coverage %, mastery, and topic-aware scheduling all key off the leaf topic). If a
tag is wrong, a student practices the wrong thing - so we measure tag quality on a
held-out labeled set BEFORE content ships, and we prove the AI tagger beats a
simpler method.

Gold set = the authored seed.json (each item carries a human-assigned leaf topic).
The taggers are zero-shot - none of them is trained on this set - so it is a valid
held-out evaluation.

For each item we compare each tagger's predicted leaf topic to the gold label and
report, per tagger:
  - accuracy         : exact leaf-topic match
  - domain_accuracy  : correct top-level category (arithmetic vs algebra)
  - coverage         : fraction with confidence >= cutoff (i.e. would auto-ship)
  - accepted_accuracy: accuracy among items at/above the cutoff (what ships)
  - confidently_wrong_rate : share of ALL items that are >= cutoff AND wrong -
                             a wrong tag that would reach a student (the metric the
                             cutoff exists to minimize)

The CUTOFF is the ship gate: an item below it is flagged for human review instead
of shipping. Default 0.6 (== ai_ingest.CONFIDENCE_THRESHOLD).

Taggers:
  - AI      : ai_ingest's OpenAIClient / GeminiClient (needs a key), zero-shot.
  - keyword : ai_ingest.HeuristicClient (taxonomy keyword rules) - the simple
              baseline #1 ("keyword search").
  - vector  : tf-idf cosine 1-NN over the gold set, leave-one-out (stdlib, no key)
              - the simple baseline #2 ("vector search").

Usage:
    export OPENAI_API_KEY=sk-...          # (or GEMINI_API_KEY) for a real AI run
    python3 eval_tagging.py               # -> prints table + writes eval_report.json
    python3 eval_tagging.py --mock        # offline/deterministic (AI == MockClient)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ai_ingest  # noqa: E402  (local module: clients, item_blob, thresholds)
import taxonomy  # noqa: E402  (local module: ALL_TOPICS, tagger, normalize)

DEFAULT_GOLD = os.path.join(_HERE, "seed.json")
DEFAULT_REPORT = os.path.join(_HERE, "eval_report.json")


# ---------------------------------------------------------------------------
# tf-idf vector 1-NN tagger (stdlib "vector search" baseline)
# ---------------------------------------------------------------------------


class TfidfVectorTagger:
    """Leave-one-out cosine 1-NN over the gold set using tf-idf vectors.

    For each query item it returns the gold topic of the single most-similar OTHER
    item, with the cosine similarity as the confidence. No training, no network.
    """

    name = "vector"

    def __init__(self, items: List[Dict], section: str = "quant"):
        self._items = items
        self._section = section
        self._docs = [self._tokens(ai_ingest.item_blob(it)) for it in items]
        self._topics = [it.get("topic") for it in items]
        # idf over the gold corpus.
        n = len(self._docs)
        df: Counter = Counter()
        for toks in self._docs:
            for t in set(toks):
                df[t] += 1
        self._idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        self._vecs = [self._vectorize(toks) for toks in self._docs]

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return taxonomy.normalize_for_dedup(text).split()

    def _vectorize(self, toks: List[str]) -> Dict[str, float]:
        if not toks:
            return {}
        tf: Counter = Counter(toks)
        vec = {t: (c / len(toks)) * self._idf.get(t, 0.0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            for t in vec:
                vec[t] /= norm
        return vec

    @staticmethod
    def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        # Both are unit-normalized -> cosine is the dot product.
        small, large = (a, b) if len(a) <= len(b) else (b, a)
        return sum(v * large.get(t, 0.0) for t, v in small.items())

    def classify_index(self, i: int) -> Tuple[str, float]:
        qv = self._vecs[i]
        best_topic = taxonomy.default_topic_for_section(self._section)
        best_sim = 0.0
        for j, jv in enumerate(self._vecs):
            if j == i:
                continue  # leave-one-out
            sim = self._cosine(qv, jv)
            if sim > best_sim:
                best_sim = sim
                best_topic = self._topics[j] or taxonomy.DEFAULT_TOPIC
        return best_topic, best_sim


# ---------------------------------------------------------------------------
# AI client selection (real model when a key is present)
# ---------------------------------------------------------------------------


def pick_ai_client(mock: bool, section: str = "quant"):
    """Return (client, label). Prefer OpenAI, then Gemini; None if unavailable."""
    if mock:
        return ai_ingest.MockClient(section=section), "mock"
    for attr in ("OpenAIClient", "GeminiClient"):
        cls = getattr(ai_ingest, attr, None)
        if cls is None:
            continue
        from_env = getattr(cls, "from_env", None)
        client = from_env(section=section) if callable(from_env) else None
        if client is not None:
            return client, client.name
    return None, "unavailable"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def domain_of(topic: Optional[str]) -> str:
    parts = (topic or "").split("::")
    return parts[2] if len(parts) >= 3 else ""


def score_predictions(
    preds: List[Tuple[str, float]],
    gold: List[str],
    cutoff: float,
) -> Dict[str, object]:
    n = len(gold)
    correct = 0
    domain_correct = 0
    accepted = 0
    accepted_correct = 0
    confidently_wrong = 0
    for (pred_topic, conf), g in zip(preds, gold):
        ok = pred_topic == g
        correct += int(ok)
        domain_correct += int(domain_of(pred_topic) == domain_of(g))
        if conf >= cutoff:
            accepted += 1
            accepted_correct += int(ok)
            if not ok:
                confidently_wrong += 1
    return {
        "n": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "domain_accuracy": round(domain_correct / n, 4) if n else 0.0,
        "coverage": round(accepted / n, 4) if n else 0.0,
        "accepted_accuracy": round(accepted_correct / accepted, 4) if accepted else None,
        "confidently_wrong_rate": round(confidently_wrong / n, 4) if n else 0.0,
    }


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


def load_gold(path: str) -> List[Dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    valid = [it for it in data if it.get("topic") in taxonomy.ALL_TOPICS]
    return valid


def run_eval(items: List[Dict], mock: bool, cutoff: float, section: str = "quant") -> Dict[str, object]:
    gold = [it.get("topic") for it in items]
    cache = ai_ingest.AiCache()

    keyword = ai_ingest.HeuristicClient(section=section)
    vector = TfidfVectorTagger(items, section=section)
    ai_client, ai_label = pick_ai_client(mock, section=section)

    kw_preds: List[Tuple[str, float]] = []
    vec_preds: List[Tuple[str, float]] = []
    ai_preds: List[Tuple[str, float]] = []

    for i, item in enumerate(items):
        kw_preds.append(keyword.classify_topic(item))
        vec_preds.append(vector.classify_index(i))
        if ai_client is not None:
            topic, conf = ai_ingest._cached_call(
                cache, ai_client, item, f"eval_classify:{ai_label}",
                lambda it=item: ai_client.classify_topic(it),
            )
            ai_preds.append((topic, float(conf)))
    if ai_client is not None:
        cache.save()

    taggers: Dict[str, object] = {
        "keyword": score_predictions(kw_preds, gold, cutoff),
        "vector": score_predictions(vec_preds, gold, cutoff),
    }
    if ai_client is not None:
        taggers["ai"] = score_predictions(ai_preds, gold, cutoff)

    # Per-item audit trail.
    per_item = []
    for i, item in enumerate(items):
        row = {
            "id": item.get("id"),
            "gold": gold[i],
            "keyword": {"pred": kw_preds[i][0], "conf": round(kw_preds[i][1], 4),
                        "ok": kw_preds[i][0] == gold[i]},
            "vector": {"pred": vec_preds[i][0], "conf": round(vec_preds[i][1], 4),
                       "ok": vec_preds[i][0] == gold[i]},
        }
        if ai_client is not None:
            row["ai"] = {"pred": ai_preds[i][0], "conf": round(ai_preds[i][1], 4),
                         "ok": ai_preds[i][0] == gold[i]}
        per_item.append(row)

    ai_acc = taggers.get("ai", {}).get("accuracy") if "ai" in taggers else None  # type: ignore[union-attr]
    beats_baseline = None
    if ai_acc is not None:
        beats_baseline = (
            ai_acc > taggers["keyword"]["accuracy"]  # type: ignore[index]
            and ai_acc > taggers["vector"]["accuracy"]  # type: ignore[index]
        )

    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat(),
        "gold_count": len(items),
        "section": section,
        "cutoff": cutoff,
        "ai_client": ai_label,
        "ai_available": ai_client is not None,
        "taggers": taggers,
        "ai_beats_baselines": beats_baseline,
        "per_item": per_item,
    }


def _fmt(v: object) -> str:
    if v is None:
        return "   -  "
    if isinstance(v, float):
        return f"{v * 100:5.1f}%"
    return str(v)


def print_table(report: Dict[str, object]) -> None:
    taggers = report["taggers"]  # type: ignore[assignment]
    order = [k for k in ("ai", "keyword", "vector") if k in taggers]
    cols = [
        ("accuracy", "accuracy"),
        ("domain_accuracy", "domain-acc"),
        ("coverage", "coverage>=cut"),
        ("accepted_accuracy", "acc@accepted"),
        ("confidently_wrong_rate", "conf-wrong"),
    ]
    print()
    print(f"GMATWiz topic-tagging eval  (gold={report['gold_count']} authored items, "
          f"cutoff={report['cutoff']}, AI={report['ai_client']})")
    print("-" * 74)
    header = f"{'metric':<16}" + "".join(f"{label:>14}" for label, _ in
                                         [(k, k) for k in order])
    print(f"{'metric':<16}" + "".join(f"{k:>14}" for k in order))
    print("-" * 74)
    for key, label in cols:
        cells = "".join(f"{_fmt(taggers[k].get(key)):>14}" for k in order)  # type: ignore[union-attr]
        print(f"{label:<16}{cells}")
    print("-" * 74)
    beats = report.get("ai_beats_baselines")
    if beats is True:
        print("RESULT: the AI tagger BEATS both the keyword and vector baselines on accuracy.")
    elif beats is False:
        print("RESULT: the AI tagger did NOT beat both baselines on this set.")
    else:
        print("RESULT: no AI key present - baselines only. Set OPENAI_API_KEY (or "
              "GEMINI_API_KEY), or pass --mock, to score the AI tagger.")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GMATWiz topic-tagging eval.")
    parser.add_argument("--gold", default=DEFAULT_GOLD,
                        help="Labeled held-out set (default: seed.json).")
    parser.add_argument("--report", default=DEFAULT_REPORT,
                        help="Machine-readable eval report path.")
    parser.add_argument("--cutoff", type=float, default=ai_ingest.CONFIDENCE_THRESHOLD,
                        help=f"Ship cutoff (default {ai_ingest.CONFIDENCE_THRESHOLD}).")
    parser.add_argument("--mock", action="store_true",
                        help="Use the deterministic MockClient as the AI (offline).")
    parser.add_argument("--section", choices=["quant", "verbal", "di"], default="quant",
                        help="Which section's taxonomy/tagger to evaluate against.")
    args = parser.parse_args(argv)

    gold_path = os.path.abspath(args.gold)
    if not os.path.isfile(gold_path):
        print(f"Gold set not found: {gold_path}", file=sys.stderr)
        return 1

    items = load_gold(gold_path)
    if not items:
        print(f"No labeled items (with a taxonomy topic) in {gold_path}", file=sys.stderr)
        return 1

    report = run_eval(items, mock=args.mock, cutoff=args.cutoff, section=args.section)
    report["gold_file"] = gold_path

    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print_table(report)
    print(f"Wrote report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
