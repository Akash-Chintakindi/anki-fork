#!/usr/bin/env python3
"""Train/test leakage check (Challenge 7e): no held-out item in the learning pool.

This is the "leakage check that runs before any score is trusted": every question
that becomes a student card lives in the LEARNING POOL, and every held-out
eval/gold/practice item lives in a TEST set. If a test item (or a near-copy of
one) has slipped into the learning pool, a model that is scored on that test set
looks smarter than it is - so PRD S14.3 requires a script that scans the training
data and flags any such overlap, and it must run CLEAN. (PRD S13 adds a second
rule: no official/copyrighted item may enter the learning pool at all.)

WHAT IS TRAIN vs TEST HERE
  LEARNING POOL (train)  = the banks that get imported as cards:
      questions.json (AQuA-RAT Quant), seed.json, verbal_questions.json,
      verbal_seed.json, verbal_rc_questions.json, di_questions.json, di_seed.json.
  HELD-OUT (test)        = the gold/eval + practice sets:
      seed.json + verbal_gold.json + di_seed.json        (tagging-eval gold),
      gmatwiz/tests/2026/*.json                          (practice-test forms),
      paraphrase_gold.json + cardcheck_gold.json         (7d / 7f gold, if present).

DUAL-USE IS NOT LEAKAGE (and the check proves the difference)
  Some authored gold sets are *intentionally* also imported as cards - seed.json
  "doubles as the eval gold set", and verbal_rc_seed.json is the flat gold twin of
  the imported verbal_rc_questions.json (identical items, identical ``vrc-*`` ids;
  see make_verbal_rc.py). That is the SAME authored artifact playing two roles, so
  it shares an ``id`` with its pool copy. Likewise the tests/2026 forms are
  ASSEMBLED FROM the bank by build_tests.py (item text + source/license copied
  verbatim), so their overlap with the pool is by construction. The check
  therefore classifies every content match into:
      dual_use          - the test item IS the pool item (shared non-empty id);
      selected_from_pool- a practice-test item verbatim-selected from the bank
                          (only for test sets declared assembled-from-pool);
      LEAKAGE           - an independently-sourced duplicate of a held-out item
                          (different id / different source) -> the harmful case.
  A strict (gold) test set gets ONLY the dual_use exemption; any other match is
  leakage. VERDICT is CLEAN iff there is zero leakage AND zero official/
  copyrighted item in the pool.

MATCHING (deterministic, stdlib only, NO network)
  exact : taxonomy.content_hash(stem, options) equality.
  near  : Jaccard over normalized token sets - the same normalization
          (taxonomy.normalize_for_dedup) and token-set similarity used by
          ai_ingest.token_set_ratio - at a configurable --threshold (default 0.9).

Usage:
    python3 leakage_check.py                       # defaults; writes report + proof
    python3 leakage_check.py --threshold 0.85      # looser near-dup bar
    python3 leakage_check.py --pool a.json b.json --test gold.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ai_ingest  # noqa: E402  (local module: token_set_ratio, is_official_license)
import taxonomy  # noqa: E402  (local module: content_hash, normalize_for_dedup)

_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_TESTS_2026 = os.path.join(_HERE, "..", "tests", "2026")

# LEARNING POOL (train): the *_questions.json banks + the seed banks that also get
# imported into the collection as cards.
DEFAULT_POOL = [
    "questions.json",
    "seed.json",
    "verbal_questions.json",
    "verbal_seed.json",
    "verbal_rc_questions.json",
    "di_questions.json",
    "di_seed.json",
]

# HELD-OUT (test), STRICT: only a shared-id dual-use item is exempt; anything else
# that matches the pool is leakage. paraphrase_gold.json / cardcheck_gold.json are
# authored in parallel (7d / 7f) - listed here and skipped gracefully if absent.
DEFAULT_STRICT_TESTS = [
    "seed.json",
    "verbal_gold.json",
    "di_seed.json",
    "paraphrase_gold.json",
    "cardcheck_gold.json",
]

# HELD-OUT (test), ASSEMBLED-FROM-POOL: the practice-test forms are built by
# build_tests.py / build_full_tests.py by selecting bank items verbatim, so an
# overlap with the pool is expected (selected_from_pool), not leakage.
DEFAULT_ASSEMBLED_TESTS = sorted(
    glob.glob(os.path.join(_TESTS_2026, "*.json"))
)

DEFAULT_THRESHOLD = 0.9
DEFAULT_REPORT = os.path.join(_HERE, "leakage_report.json")
DEFAULT_PROOF = os.path.join(_REPO_ROOT, "proof", "leakage-check.txt")


# ---------------------------------------------------------------------------
# Loading / flattening (robust to every content + test shape in the repo)
# ---------------------------------------------------------------------------


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_INHERIT_KEYS = ("source", "license", "topic", "passage")


def _walk(node, inherited: Dict[str, str], out: List[Dict]) -> None:
    """Recursively collect every dict that carries a real ``stem`` as one item.

    Handles all shapes present in the repo uniformly: flat item arrays, passage-
    grouped RC banks (``{passage, questions:[...]}``), quant-only forms
    (``{items:[...]}``), full 3-section forms (``{sections:[{items:[...]}]}``),
    and any future gold shape (e.g. paraphrase/card-check pairs) - each stem-
    bearing object becomes an item, inheriting the nearest ancestor's
    source/license/topic/passage when its own is missing.
    """
    if isinstance(node, dict):
        inh = dict(inherited)
        for key in _INHERIT_KEYS:
            val = node.get(key)
            if isinstance(val, str) and val.strip():
                inh[key] = val
        stem = node.get("stem")
        if isinstance(stem, str) and stem.strip():
            item = dict(node)
            for key, val in inh.items():
                cur = item.get(key)
                if not (isinstance(cur, str) and cur.strip()):
                    item[key] = val
            out.append(item)
            return  # an item's own subfields are not scanned for nested items
        for val in node.values():
            _walk(val, inh, out)
    elif isinstance(node, list):
        for element in node:
            _walk(element, inherited, out)


def flatten_items(data) -> List[Dict]:
    out: List[Dict] = []
    _walk(data, {}, out)
    return out


# ---------------------------------------------------------------------------
# Item fingerprints
# ---------------------------------------------------------------------------


def content_hash(item: Dict) -> str:
    return taxonomy.content_hash(item.get("stem", ""), item.get("options", {}) or {})


def token_set(item: Dict) -> frozenset:
    """Normalized token set of stem+options (matches ai_ingest.token_set_ratio)."""
    return frozenset(taxonomy.normalize_for_dedup(ai_ingest.item_blob(item)).split())


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Token-set (Jaccard) similarity - identical to ai_ingest.token_set_ratio."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _short(text: str, n: int = 80) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Learning pool index
# ---------------------------------------------------------------------------


class PoolRecord:
    __slots__ = ("id", "file", "hash", "tokens", "source", "license")

    def __init__(self, item: Dict, file: str):
        self.id = item.get("id")
        self.file = file
        self.hash = content_hash(item)
        self.tokens = token_set(item)
        self.source = item.get("source") or ""
        self.license = item.get("license") or ""


class LearningPool:
    def __init__(self):
        self.records: List[PoolRecord] = []
        self.by_hash: Dict[str, List[PoolRecord]] = {}
        self.files: List[str] = []

    def add_file(self, path: str, label: str) -> int:
        items = flatten_items(load_json(path))
        for item in items:
            rec = PoolRecord(item, label)
            self.records.append(rec)
            self.by_hash.setdefault(rec.hash, []).append(rec)
        self.files.append(label)
        return len(items)

    @property
    def unique_content(self) -> int:
        return len(self.by_hash)

    def official_items(self) -> List[Dict]:
        """Any pool item whose source/license marks it official/copyrighted."""
        flagged = []
        for rec in self.records:
            if ai_ingest.is_official_license(rec.license) or ai_ingest.is_official_license(rec.source):
                flagged.append({"id": rec.id, "file": rec.file,
                                "source": rec.source, "license": rec.license})
        flagged.sort(key=lambda d: (d["file"], d["id"] or ""))
        return flagged

    def near_matches(self, tokens: frozenset, threshold: float) -> List[Tuple[float, PoolRecord]]:
        out: List[Tuple[float, PoolRecord]] = []
        la = len(tokens)
        if not la:
            return out
        for rec in self.records:
            lb = len(rec.tokens)
            if not lb:
                continue
            # Length prefilter: Jaccard cannot reach the threshold if the smaller
            # token set is < threshold * the larger one.
            if min(la, lb) < threshold * max(la, lb):
                continue
            sim = _jaccard(tokens, rec.tokens)
            if sim >= threshold:
                out.append((sim, rec))
        out.sort(key=lambda sr: (-sr[0], sr[1].file, sr[1].id or ""))
        return out


# ---------------------------------------------------------------------------
# Scan one test set against the pool
# ---------------------------------------------------------------------------


def classify_match(
    test_item: Dict,
    matched: List[PoolRecord],
    strict: bool,
) -> str:
    """dual_use | selected_from_pool | leakage for a matched test item."""
    tid = test_item.get("id")
    if tid and any(rec.id == tid for rec in matched):
        return "dual_use"  # same authored artifact, imported as a card
    if not strict:
        return "selected_from_pool"  # practice test drawn verbatim from the bank
    return "leakage"


def scan_testset(
    path: str,
    label: str,
    pool: LearningPool,
    threshold: float,
    strict: bool,
) -> Dict:
    items = flatten_items(load_json(path))
    result = {
        "name": label,
        "path": os.path.relpath(path, _REPO_ROOT),
        "kind": "strict_gold" if strict else "assembled_from_pool",
        "test_count": len(items),
        "exact_hits": 0,
        "near_hits": 0,
        "not_in_pool": 0,
        "dual_use": 0,
        "selected_from_pool": 0,
        "leakage": 0,
        "leaks": [],
    }

    for item in items:
        exact = pool.by_hash.get(content_hash(item), [])
        if exact:
            result["exact_hits"] += 1
            category, matched, sim = classify_match(item, exact, strict), exact, 1.0
            kind = "exact"
        else:
            near = pool.near_matches(token_set(item), threshold)
            if not near:
                result["not_in_pool"] += 1
                continue
            result["near_hits"] += 1
            matched = [rec for _s, rec in near]
            category = classify_match(item, matched, strict)
            sim = near[0][0]
            kind = "near"

        result[category] += 1
        if category == "leakage":
            result["leaks"].append({
                "match_type": kind,
                "similarity": round(sim, 4),
                "test_id": item.get("id"),
                "test_stem": _short(item.get("stem", "")),
                "test_source": item.get("source"),
                "test_license": item.get("license"),
                "pool_ids": sorted({rec.id for rec in matched if rec.id}),
                "pool_files": sorted({rec.file for rec in matched}),
            })

    result["leaks"].sort(key=lambda d: (-d["similarity"], str(d["test_id"])))
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def build_report(
    pool: LearningPool,
    pool_kept: List[Tuple[str, int]],
    testset_results: List[Dict],
    missing_tests: List[str],
    threshold: float,
) -> Dict:
    official = pool.official_items()
    totals = {k: 0 for k in ("test_items", "exact_hits", "near_hits", "not_in_pool",
                             "dual_use", "selected_from_pool", "leakage")}
    for r in testset_results:
        totals["test_items"] += r["test_count"]
        totals["exact_hits"] += r["exact_hits"]
        totals["near_hits"] += r["near_hits"]
        totals["not_in_pool"] += r["not_in_pool"]
        totals["dual_use"] += r["dual_use"]
        totals["selected_from_pool"] += r["selected_from_pool"]
        totals["leakage"] += r["leakage"]

    clean = totals["leakage"] == 0 and len(official) == 0
    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat(),
        "threshold": threshold,
        "pool": {
            "files": [{"file": f, "items": n} for f, n in pool_kept],
            "record_count": len(pool.records),
            "unique_content": pool.unique_content,
        },
        "official_or_copyrighted_in_pool": {
            "count": len(official),
            "items": official,
        },
        "testsets": testset_results,
        "missing_testsets": missing_tests,
        "totals": totals,
        "verdict": "CLEAN" if clean else "DIRTY",
    }


def _row(name: str, pool_n, test_n, exact, near, dual, derived, leak) -> str:
    return (f"{name:<30}{str(pool_n):>6}{str(test_n):>6}{str(exact):>7}"
            f"{str(near):>6}{str(dual):>6}{str(derived):>9}{str(leak):>6}")


def render_proof(report: Dict, argv_hint: str) -> str:
    L = "=" * 79
    D = "-" * 79
    pool = report["pool"]
    tot = report["totals"]
    official = report["official_or_copyrighted_in_pool"]
    lines: List[str] = []
    lines.append(L)
    lines.append("GMATWiz - TRAIN/TEST LEAKAGE CHECK  (Challenge 7e)")
    lines.append(L)
    lines.append("What this proves (PRD S14.3 + S13):")
    lines.append("  A script scans the TRAINING DATA (the learning pool that becomes student")
    lines.append("  cards) and flags any HELD-OUT test/gold item, or a near-copy, that slipped")
    lines.append("  in - plus any official/copyrighted item in the pool. Leaked test data makes")
    lines.append("  a model look smarter than it is and zeroes the affected score, so this must")
    lines.append("  run CLEAN.")
    lines.append("")
    lines.append("LEARNING POOL (train) - imported as cards:")
    for entry in pool["files"]:
        lines.append(f"  {entry['file']:<26} {entry['items']:>5} items")
    lines.append(f"  {'= pool total':<26} {pool['record_count']:>5} records "
                 f"({pool['unique_content']} unique by content-hash)")
    lines.append("")
    lines.append("HELD-OUT (test) - gold eval sets + practice-test forms:")
    lines.append("  strict gold      : seed.json, verbal_gold.json, di_seed.json,")
    lines.append("                     paraphrase_gold.json, cardcheck_gold.json (7d/7f, if present)")
    lines.append("  assembled-from-pool: gmatwiz/tests/2026/*.json (practice forms; build_tests.py")
    lines.append("                     selects bank items verbatim, so overlap is by construction)")
    if report["missing_testsets"]:
        lines.append("  not present yet  : " + ", ".join(report["missing_testsets"])
                     + "  (skipped gracefully)")
    lines.append("")
    lines.append("HOW A MATCH IS CLASSIFIED (dual-use is NOT leakage):")
    lines.append("  dual_use   - the test item IS the pool item (shares a non-empty id): an")
    lines.append("               authored gold set that is intentionally also imported as cards")
    lines.append("               (seed.json doubles as gold; verbal_rc_seed == verbal_rc_questions).")
    lines.append("  derived    - a practice-test item selected verbatim from the bank (only for")
    lines.append("               assembled-from-pool sets).")
    lines.append("  LEAK       - an independently-sourced duplicate (different id/source) of a")
    lines.append("               held-out item -> the harmful case this check exists to catch.")
    lines.append(f"  exact = content_hash(stem,options); near = token-set Jaccard >= "
                 f"{report['threshold']} (ai_ingest similarity).")
    lines.append("")
    lines.append(D)
    lines.append("REPRODUCE")
    lines.append(D)
    lines.append("  cd <repo root>   # the anki-fork checkout")
    lines.append("  out/pyenv/bin/python gmatwiz/content/leakage_check.py" +
                 (f" {argv_hint}" if argv_hint else ""))
    lines.append("  # writes gmatwiz/content/leakage_report.json (full machine-readable detail)")
    lines.append("  # and this proof/leakage-check.txt")
    lines.append("")
    lines.append(D)
    lines.append(f"RESULTS  (real run; threshold={report['threshold']}; "
                 f"pool={pool['unique_content']} unique items)")
    lines.append(D)
    lines.append(_row("test set", "pool", "test", "exact", "near", "dual", "derived", "LEAK"))
    lines.append(D)
    for r in report["testsets"]:
        lines.append(_row(_short(r["name"], 30), pool["unique_content"], r["test_count"],
                          r["exact_hits"], r["near_hits"], r["dual_use"],
                          r["selected_from_pool"], r["leakage"]))
    lines.append(D)
    lines.append(_row("TOTAL", pool["unique_content"], tot["test_items"], tot["exact_hits"],
                      tot["near_hits"], tot["dual_use"], tot["selected_from_pool"],
                      tot["leakage"]))
    lines.append(D)
    lines.append(f"Official/copyrighted items in the learning pool: {official['count']}")
    lines.append("")
    lines.append(f"VERDICT: {report['verdict']}  "
                 + ("- no held-out test item (or near-copy) leaked into the learning pool, "
                    "and no official/copyrighted content is in the pool."
                    if report["verdict"] == "CLEAN"
                    else "- leakage found (listed below); the affected score is not trustworthy."))
    lines.append("")
    if tot["leakage"]:
        lines.append(D)
        lines.append("LEAKAGE DETAILS")
        lines.append(D)
        for r in report["testsets"]:
            for leak in r["leaks"]:
                lines.append(f"  [{r['name']}] {leak['match_type']} "
                             f"sim={leak['similarity']}  test_id={leak['test_id']}")
                lines.append(f"      stem : {leak['test_stem']}")
                lines.append(f"      pool : {', '.join(leak['pool_ids']) or '(id-less)'} "
                             f"in {', '.join(leak['pool_files'])}")
        lines.append("")
    lines.append("READING IT (honest nuance):")
    lines.append("  The gold sets show up as dual_use, not leakage: they share ids with their")
    lines.append("  pool copies because those authored sets are deliberately imported as cards")
    lines.append("  AND used as tagging-eval gold (the taggers are zero-shot, so a shared item")
    lines.append("  does not train the model on its own answer). The practice forms are derived")
    lines.append("  (verbatim selections from the legally-sourced bank). What WOULD zero a score")
    lines.append("  - an independently-sourced copy of a held-out item, or an official/")
    lines.append("  copyrighted item in the pool - is exactly what the LEAK column counts.")
    lines.append(L)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _resolve(path: str) -> str:
    """Resolve a bare filename against the content dir; else use as given."""
    if os.path.isabs(path) or os.sep in path or (os.altsep and os.altsep in path):
        return os.path.abspath(path)
    return os.path.join(_HERE, path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GMATWiz train/test leakage check (7e).")
    parser.add_argument("--pool", nargs="+", default=DEFAULT_POOL,
                        help="Learning-pool JSON files (bare names resolve to content/).")
    parser.add_argument("--test", nargs="+", default=DEFAULT_STRICT_TESTS,
                        help="Strict held-out gold sets (only shared-id dual-use is exempt).")
    parser.add_argument("--assembled-test", nargs="+", default=DEFAULT_ASSEMBLED_TESTS,
                        help="Test sets assembled from the pool (practice-test forms).")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Near-duplicate token-set threshold (default {DEFAULT_THRESHOLD}).")
    parser.add_argument("--report", default=DEFAULT_REPORT,
                        help="Machine-readable JSON report path.")
    parser.add_argument("--proof", default=DEFAULT_PROOF,
                        help="Human-readable proof text path.")
    parser.add_argument("--no-proof", action="store_true",
                        help="Do not write the proof/*.txt file.")
    args = parser.parse_args(argv)

    # ---- Build the learning pool ----
    pool = LearningPool()
    pool_kept: List[Tuple[str, int]] = []
    for spec in args.pool:
        path = _resolve(spec)
        if not os.path.isfile(path):
            print(f"WARNING: pool file not found, skipping: {path}", file=sys.stderr)
            continue
        label = os.path.basename(path)
        n = pool.add_file(path, label)
        pool_kept.append((label, n))

    if not pool.records:
        print("No learning-pool items loaded; nothing to check.", file=sys.stderr)
        return 1

    # ---- Scan every test set ----
    testset_results: List[Dict] = []
    missing_tests: List[str] = []

    for spec in args.test:
        path = _resolve(spec)
        if not os.path.isfile(path):
            missing_tests.append(os.path.basename(path))
            continue
        testset_results.append(
            scan_testset(path, os.path.basename(path), pool, args.threshold, strict=True)
        )
    for spec in args.assembled_test:
        path = _resolve(spec)
        if not os.path.isfile(path):
            missing_tests.append(os.path.basename(path))
            continue
        testset_results.append(
            scan_testset(path, os.path.basename(path), pool, args.threshold, strict=False)
        )

    report = build_report(pool, pool_kept, testset_results, missing_tests, args.threshold)

    # ---- Write machine-readable report ----
    report_path = os.path.abspath(args.report)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # ---- Write proof + print a compact summary ----
    argv_hint = "" if args.threshold == DEFAULT_THRESHOLD else f"--threshold {args.threshold}"
    proof_text = render_proof(report, argv_hint)
    if not args.no_proof:
        proof_path = os.path.abspath(args.proof)
        os.makedirs(os.path.dirname(proof_path) or ".", exist_ok=True)
        with open(proof_path, "w", encoding="utf-8") as fh:
            fh.write(proof_text)

    print(proof_text)
    print(f"Wrote report -> {report_path}")
    if not args.no_proof:
        print(f"Wrote proof  -> {os.path.abspath(args.proof)}")
    tot = report["totals"]
    print(f"\nVERDICT: {report['verdict']}  (pool={report['pool']['unique_content']} unique, "
          f"test items={tot['test_items']}, exact={tot['exact_hits']}, "
          f"near={tot['near_hits']}, leakage={tot['leakage']}, "
          f"official_in_pool={report['official_or_copyrighted_in_pool']['count']})")
    return 0 if report["verdict"] == "CLEAN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
