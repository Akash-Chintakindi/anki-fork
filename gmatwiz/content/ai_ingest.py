#!/usr/bin/env python3
"""GMATWiz AI content-ingestion layer — build-time curation over normalized items.

Runs four passes over an existing question bank (e.g. questions.json):

  1. Validity / scope filter  — drop or quarantine malformed / out-of-scope items
  2. AI auto-tag              — classify to exactly one taxonomy leaf + confidence
  3. Semantic dedupe          — near-duplicate detection (embeddings or text sim)
  4. Difficulty estimate      — easy / medium / hard (leave unchanged if no AI)

Design goals (mirror scraper.py):
  * Dependency-light: stdlib at import time; optional google-genai inside guards.
  * Degrades gracefully: HeuristicClient always works; Gemini when key + package
    present; --mock for deterministic offline validation.
  * Deterministic caching in .ai_cache.json keyed by item hash + operation.

Usage:
    python3 ai_ingest.py --in questions.json --out questions.curated.json \\
        --report ai_ingest_report.json
    python3 ai_ingest.py --in questions.json --out /tmp/curated.json \\
        --report /tmp/report.json --mock
    python3 ai_ingest.py --in questions.json --out questions.json --write  # explicit
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Protocol, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import taxonomy  # noqa: E402  (local module)

DEFAULT_QUESTIONS = os.path.join(_HERE, "questions.json")
CACHE_PATH = os.path.join(_HERE, ".ai_cache.json")
CONFIDENCE_THRESHOLD = 0.6
DEDUPE_THRESHOLD = 0.85
OFFICIAL_LICENSE_MARKERS = ("official", "copyrighted")

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class AiCache:
    """Persistent cache for AI operations — keyed by item content + operation."""

    def __init__(self, path: str = CACHE_PATH):
        self.path = path
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except Exception:
                self._data = {}

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")

    @staticmethod
    def item_basis(item: Dict) -> str:
        payload = {
            "stem": item.get("stem", ""),
            "options": item.get("options", {}),
            "correct": item.get("correct", ""),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def key(self, item: Dict, operation: str) -> str:
        basis = f"{operation}:{self.item_basis(item)}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

    def get(self, item: Dict, operation: str) -> Any:
        return self._data.get(self.key(item, operation))

    def set(self, item: Dict, operation: str, value: Any) -> None:
        self._data[self.key(item, operation)] = value


# ---------------------------------------------------------------------------
# Text similarity (stdlib — no rapidfuzz)
# ---------------------------------------------------------------------------


def item_blob(item: Dict) -> str:
    opts = item.get("options") or {}
    parts = [item.get("stem") or ""]
    for k in taxonomy.OPTION_KEYS:
        parts.append(str(opts.get(k, "")))
    return " ".join(parts)


def token_set_ratio(a: str, b: str) -> float:
    """Jaccard similarity over normalized token sets (0..1)."""
    ta = set(taxonomy.normalize_for_dedup(a).split())
    tb = set(taxonomy.normalize_for_dedup(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def is_official_license(license_str: str) -> bool:
    low = (license_str or "").lower()
    return any(m in low for m in OFFICIAL_LICENSE_MARKERS)


# ---------------------------------------------------------------------------
# AI client protocol + implementations
# ---------------------------------------------------------------------------


class AiClient(Protocol):
    @property
    def name(self) -> str: ...

    def classify_topic(self, item: Dict) -> Tuple[str, float]:
        """Return (leaf_topic_id, confidence 0..1)."""
        ...

    def estimate_difficulty(self, item: Dict) -> Optional[str]:
        """Return easy/medium/hard, or None to keep existing."""
        ...

    def similar(self, text_a: str, text_b: str) -> float:
        """Semantic or text similarity in 0..1."""
        ...

    def check_validity(self, item: Dict) -> Tuple[bool, Optional[str]]:
        """Return (is_valid, drop_or_quarantine_reason)."""
        ...


class HeuristicClient:
    """Always-available fallback — keyword tagger + rules, no network."""

    name = "heuristic"

    def classify_topic(self, item: Dict) -> Tuple[str, float]:
        text = item_blob(item)
        topic, score = taxonomy.tag_topic_with_score(text)
        # Map keyword score to a pseudo-confidence (cap at 0.95).
        if score <= 0:
            conf = 0.35
        else:
            conf = min(0.95, 0.45 + score * 0.05)
        return topic, conf

    def estimate_difficulty(self, item: Dict) -> Optional[str]:
        # No AI — preserve the item's existing difficulty label.
        return None

    def similar(self, text_a: str, text_b: str) -> float:
        return token_set_ratio(text_a, text_b)

    def check_validity(self, item: Dict) -> Tuple[bool, Optional[str]]:
        return _rule_validity(item)


class MockClient:
    """Deterministic fake AI — stable hashes, no network."""

    name = "mock"

    def _h(self, item: Dict, salt: str = "") -> int:
        basis = AiCache.item_basis(item) + salt
        return int(hashlib.sha256(basis.encode("utf-8")).hexdigest(), 16)

    def classify_topic(self, item: Dict) -> Tuple[str, float]:
        h = self._h(item, "topic")
        topic = taxonomy.ALL_TOPICS[h % len(taxonomy.ALL_TOPICS)]
        conf = 0.50 + (h % 46) / 100.0  # 0.50 .. 0.95
        return topic, round(conf, 4)

    def estimate_difficulty(self, item: Dict) -> Optional[str]:
        h = self._h(item, "diff")
        return taxonomy.VALID_DIFFICULTIES[h % 3]

    def similar(self, text_a: str, text_b: str) -> float:
        # Deterministic pseudo-similarity from combined hash.
        combined = taxonomy.normalize_for_dedup(text_a) + "||" + taxonomy.normalize_for_dedup(text_b)
        h = int(hashlib.sha256(combined.encode("utf-8")).hexdigest(), 16)
        base = token_set_ratio(text_a, text_b)
        # Boost identical-normalized pairs to 1.0; otherwise blend hash noise.
        if base >= 0.99:
            return 1.0
        jitter = (h % 21) / 100.0  # 0 .. 0.20
        return min(1.0, base * 0.85 + jitter)

    def check_validity(self, item: Dict) -> Tuple[bool, Optional[str]]:
        ok, reason = _rule_validity(item)
        return ok, reason


class GeminiClient:
    """Lazy google-genai / google-generativeai wrapper."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self._genai = None
        self._client = None
        self._use_new_sdk = False

    @classmethod
    def available(cls) -> bool:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            return False
        try:
            import google.genai  # type: ignore  # noqa: F401
            return True
        except Exception:
            pass
        try:
            import google.generativeai  # type: ignore  # noqa: F401
            return True
        except Exception:
            return False

    @classmethod
    def from_env(cls) -> Optional["GeminiClient"]:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            return None
        if not cls.available():
            return None
        return cls(api_key=key)

    def _ensure(self) -> bool:
        if self._genai is not None or self._client is not None:
            return True
        try:
            import google.genai as genai  # type: ignore

            self._genai = genai
            self._client = genai.Client(api_key=self.api_key)
            self._use_new_sdk = True
            return True
        except Exception:
            pass
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.api_key)
            self._genai = genai
            self._use_new_sdk = False
            return True
        except Exception:
            return False

    def _generate_text(self, prompt: str) -> Optional[str]:
        if not self._ensure():
            return None
        try:
            if self._use_new_sdk and self._client is not None:
                resp = self._client.models.generate_content(
                    model=self.model, contents=prompt
                )
                return getattr(resp, "text", None) or str(resp)
            model = self._genai.GenerativeModel(self.model)  # type: ignore
            resp = model.generate_content(prompt)
            return getattr(resp, "text", None)
        except Exception:
            return None

    def _parse_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    def classify_topic(self, item: Dict) -> Tuple[str, float]:
        topics = "\n".join(f"  - {t}" for t in taxonomy.ALL_TOPICS)
        prompt = (
            "Classify this GMAT Quant Problem Solving question to exactly ONE leaf topic.\n"
            f"Valid topics:\n{topics}\n\n"
            f"Question:\n{item.get('stem', '')}\n\n"
            f"Options:\n{json.dumps(item.get('options', {}), ensure_ascii=False)}\n\n"
            'Reply JSON only: {"topic": "<full topic id>", "confidence": 0.0-1.0}'
        )
        parsed = self._parse_json(self._generate_text(prompt) or "")
        if parsed and parsed.get("topic") in taxonomy.ALL_TOPICS:
            conf = float(parsed.get("confidence", 0.7))
            return parsed["topic"], max(0.0, min(1.0, conf))
        # Degrade to heuristic for this call.
        return HeuristicClient().classify_topic(item)

    def estimate_difficulty(self, item: Dict) -> Optional[str]:
        prompt = (
            "Rate GMAT Quant PS difficulty as exactly one of: easy, medium, hard.\n\n"
            f"Question:\n{item.get('stem', '')}\n\n"
            f"Options:\n{json.dumps(item.get('options', {}), ensure_ascii=False)}\n\n"
            'Reply JSON only: {"difficulty": "easy"|"medium"|"hard"}'
        )
        parsed = self._parse_json(self._generate_text(prompt) or "")
        diff = (parsed or {}).get("difficulty")
        if diff in taxonomy.VALID_DIFFICULTIES:
            return diff
        return None

    def similar(self, text_a: str, text_b: str) -> float:
        if not self._ensure():
            return token_set_ratio(text_a, text_b)
        try:
            if self._use_new_sdk and self._client is not None:
                emb = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=[text_a, text_b],
                )
                vecs = [e.values for e in emb.embeddings]
            else:
                result = self._genai.embed_content(  # type: ignore
                    model="models/text-embedding-004",
                    content=[text_a, text_b],
                    task_type="SEMANTIC_SIMILARITY",
                )
                vecs = [e["embedding"] for e in result["embedding"]]
            if len(vecs) != 2:
                return token_set_ratio(text_a, text_b)
            dot = sum(a * b for a, b in zip(vecs[0], vecs[1]))
            na = sum(a * a for a in vecs[0]) ** 0.5
            nb = sum(b * b for b in vecs[1]) ** 0.5
            if na == 0 or nb == 0:
                return token_set_ratio(text_a, text_b)
            cos = dot / (na * nb)
            return max(0.0, min(1.0, (cos + 1) / 2))
        except Exception:
            return token_set_ratio(text_a, text_b)

    def check_validity(self, item: Dict) -> Tuple[bool, Optional[str]]:
        prompt = (
            "Is this a valid, solvable GMAT Quant Problem Solving question "
            "(arithmetic/algebra only, NOT geometry, NOT data sufficiency)?\n\n"
            f"Question:\n{item.get('stem', '')}\n\n"
            f"Options:\n{json.dumps(item.get('options', {}), ensure_ascii=False)}\n\n"
            f"Marked correct: {item.get('correct')}\n\n"
            'Reply JSON only: {"valid": true|false, "reason": "<short reason if invalid>"}'
        )
        parsed = self._parse_json(self._generate_text(prompt) or "")
        if parsed is not None:
            if parsed.get("valid") is True:
                return True, None
            reason = parsed.get("reason") or "ai_invalid"
            return False, f"ai:{reason}"
        return _rule_validity(item)


class OpenAIClient:
    """OpenAI wrapper over the REST API via stdlib urllib (no SDK required).

    Uses the SAME key the runtime proxy holds (OPENAI_API_KEY) and the same model
    default (gpt-4.1-mini, overridable via OPENAI_MODEL), so the eval and any
    build-time curation score the model the app actually ships with.
    """

    name = "openai"
    _CHAT_URL = "https://api.openai.com/v1/chat/completions"
    _EMBED_URL = "https://api.openai.com/v1/embeddings"

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        self.api_key = api_key
        self.model = os.environ.get("OPENAI_MODEL") or model

    @classmethod
    def available(cls) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    @classmethod
    def from_env(cls) -> Optional["OpenAIClient"]:
        key = os.environ.get("OPENAI_API_KEY")
        return cls(api_key=key) if key else None

    def _post(self, url: str, payload: Dict) -> Optional[Dict]:
        import urllib.request  # stdlib; imported lazily like the Gemini guard
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def _chat(self, prompt: str, json_mode: bool = True) -> Optional[str]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system",
                 "content": "You are a precise GMAT Quant content classifier. Reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        out = self._post(self._CHAT_URL, payload)
        if not out:
            return None
        try:
            return out["choices"][0]["message"]["content"]
        except Exception:
            return None

    def _parse_json(self, text: Optional[str]) -> Optional[Dict]:
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return None
            try:
                return json.loads(m.group(0))
            except Exception:
                return None

    def classify_topic(self, item: Dict) -> Tuple[str, float]:
        topics = "\n".join(f"  - {t}" for t in taxonomy.ALL_TOPICS)
        prompt = (
            "Classify this GMAT Quant Problem Solving question to exactly ONE leaf topic.\n"
            f"Valid topics:\n{topics}\n\n"
            f"Question:\n{item.get('stem', '')}\n\n"
            f"Options:\n{json.dumps(item.get('options', {}), ensure_ascii=False)}\n\n"
            'Reply JSON only: {"topic": "<full topic id>", "confidence": 0.0-1.0}'
        )
        parsed = self._parse_json(self._chat(prompt))
        if parsed and parsed.get("topic") in taxonomy.ALL_TOPICS:
            conf = float(parsed.get("confidence", 0.7))
            return parsed["topic"], max(0.0, min(1.0, conf))
        return HeuristicClient().classify_topic(item)

    def estimate_difficulty(self, item: Dict) -> Optional[str]:
        prompt = (
            "Rate GMAT Quant PS difficulty as exactly one of: easy, medium, hard.\n\n"
            f"Question:\n{item.get('stem', '')}\n\n"
            f"Options:\n{json.dumps(item.get('options', {}), ensure_ascii=False)}\n\n"
            'Reply JSON only: {"difficulty": "easy"|"medium"|"hard"}'
        )
        parsed = self._parse_json(self._chat(prompt))
        diff = (parsed or {}).get("difficulty")
        return diff if diff in taxonomy.VALID_DIFFICULTIES else None

    def similar(self, text_a: str, text_b: str) -> float:
        out = self._post(self._EMBED_URL, {
            "model": "text-embedding-3-small",
            "input": [text_a, text_b],
        })
        try:
            vecs = [d["embedding"] for d in out["data"]]  # type: ignore[index]
            if len(vecs) != 2:
                return token_set_ratio(text_a, text_b)
            dot = sum(a * b for a, b in zip(vecs[0], vecs[1]))
            na = sum(a * a for a in vecs[0]) ** 0.5
            nb = sum(b * b for b in vecs[1]) ** 0.5
            if na == 0 or nb == 0:
                return token_set_ratio(text_a, text_b)
            return max(0.0, min(1.0, dot / (na * nb)))
        except Exception:
            return token_set_ratio(text_a, text_b)

    def check_validity(self, item: Dict) -> Tuple[bool, Optional[str]]:
        prompt = (
            "Is this a valid, solvable GMAT Quant Problem Solving question "
            "(arithmetic/algebra only, NOT geometry, NOT data sufficiency)?\n\n"
            f"Question:\n{item.get('stem', '')}\n\n"
            f"Options:\n{json.dumps(item.get('options', {}), ensure_ascii=False)}\n\n"
            f"Marked correct: {item.get('correct')}\n\n"
            'Reply JSON only: {"valid": true|false, "reason": "<short reason if invalid>"}'
        )
        parsed = self._parse_json(self._chat(prompt))
        if parsed is not None:
            if parsed.get("valid") is True:
                return True, None
            return False, f"ai:{parsed.get('reason') or 'ai_invalid'}"
        return _rule_validity(item)


# ---------------------------------------------------------------------------
# Validity / scope (shared rules)
# ---------------------------------------------------------------------------


def _rule_validity(item: Dict) -> Tuple[bool, Optional[str]]:
    errs = taxonomy.validate_question(item)
    if errs:
        return False, "validation:" + ";".join(errs)

    opts = item.get("options") or {}
    distinct = {
        re.sub(r"\s+", " ", str(v).strip().lower())
        for v in opts.values()
        if v
    }
    if len(distinct) < 5:
        return False, "duplicate_options"

    blob = item_blob(item) + " " + (item.get("explanation") or "")
    scope = taxonomy.out_of_scope_reason(blob)
    if scope:
        return False, f"out_of_scope:{scope}"

    if not item.get("correct") or item.get("correct") not in taxonomy.OPTION_KEYS:
        return False, "no_valid_correct_answer"

    correct_val = opts.get(item.get("correct"), "")
    if not correct_val or not str(correct_val).strip():
        return False, "empty_correct_option"

    return True, None


def _cached_call(
    cache: AiCache,
    client: AiClient,
    item: Dict,
    operation: str,
    fn,
) -> Any:
    hit = cache.get(item, operation)
    if hit is not None:
        return hit
    val = fn()
    cache.set(item, operation, val)
    return val


# ---------------------------------------------------------------------------
# Pipeline passes
# ---------------------------------------------------------------------------


def pass_validity(
    items: List[Dict],
    client: AiClient,
    cache: AiCache,
    use_ai_check: bool,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Return (kept, dropped, quarantined)."""
    kept: List[Dict] = []
    dropped: List[Dict] = []
    quarantined: List[Dict] = []

    for item in items:
        if use_ai_check and client.name in ("gemini", "openai", "mock"):
            ok, reason = _cached_call(
                cache, client, item, "validity",
                lambda i=item: client.check_validity(i),
            )
        else:
            ok, reason = _rule_validity(item)

        if ok:
            kept.append(dict(item))
        elif reason and reason.startswith("out_of_scope:"):
            quarantined.append({"id": item.get("id"), "reason": reason, "item": item})
        else:
            dropped.append({"id": item.get("id"), "reason": reason or "invalid", "item": item})

    return kept, dropped, quarantined


def pass_auto_tag(
    items: List[Dict],
    client: AiClient,
    cache: AiCache,
    threshold: float,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Return (tagged_items, retagged_log, low_confidence_log)."""
    tagged: List[Dict] = []
    retagged: List[Dict] = []
    low_conf: List[Dict] = []

    for item in items:
        old_topic = item.get("topic")
        topic, conf = _cached_call(
            cache, client, item, "classify_topic",
            lambda i=item: client.classify_topic(i),
        )
        if not isinstance(conf, (int, float)):
            conf = float(conf)
        new_item = dict(item)
        new_item["topic"] = topic
        tagged.append(new_item)

        if old_topic != topic:
            retagged.append({
                "id": item.get("id"),
                "old_topic": old_topic,
                "new_topic": topic,
                "confidence": conf,
            })
        if conf < threshold:
            low_conf.append({
                "id": item.get("id"),
                "topic": topic,
                "confidence": conf,
                "needs_review": True,
            })

    return tagged, retagged, low_conf


def pass_dedupe(
    items: List[Dict],
    client: AiClient,
    threshold: float,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Return (kept, duplicate_groups, leakage_risks)."""
    n = len(items)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    blobs = [item_blob(q) for q in items]
    for i in range(n):
        for j in range(i + 1, n):
            sim = client.similar(blobs[i], blobs[j])
            if sim >= threshold:
                union(i, j)

    groups: Dict[int, List[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    def pick_canonical(idxs: List[int]) -> int:
        def rank(idx: int) -> Tuple[int, str]:
            lic = (items[idx].get("license") or "").lower()
            # Prefer open/authored licenses; deprioritize official/copyrighted.
            if is_official_license(lic):
                score = 2
            elif "apache" in lic or "authored" in lic or "cc" in lic:
                score = 0
            else:
                score = 1
            return score, items[idx].get("id") or ""

        return min(idxs, key=rank)

    kept: List[Dict] = []
    dup_groups: List[Dict] = []
    leakage: List[Dict] = []

    for idxs in groups.values():
        if len(idxs) == 1:
            kept.append(dict(items[idxs[0]]))
            continue

        canon_idx = pick_canonical(idxs)
        canon = items[canon_idx]
        dup_ids = [items[i].get("id") for i in idxs if i != canon_idx]

        dup_groups.append({
            "canonical": canon.get("id"),
            "duplicates": dup_ids,
        })

        # Leakage: non-official item near-dup of official/copyrighted.
        official_idxs = [i for i in idxs if is_official_license(items[i].get("license", ""))]
        if official_idxs:
            off_idx = official_idxs[0]
            for i in idxs:
                if i == off_idx:
                    continue
                if not is_official_license(items[i].get("license", "")):
                    leakage.append({
                        "id": items[i].get("id"),
                        "matched_official_id": items[off_idx].get("id"),
                        "reason": "near_duplicate_of_official",
                    })

        kept.append(dict(canon))

    # Remove leakage items from kept (quarantine instead).
    leak_ids = {x["id"] for x in leakage}
    kept = [q for q in kept if q.get("id") not in leak_ids]

    return kept, dup_groups, leakage


def pass_difficulty(
    items: List[Dict],
    client: AiClient,
    cache: AiCache,
    ai_available: bool,
) -> List[Dict]:
    out: List[Dict] = []
    for item in items:
        new_item = dict(item)
        if ai_available:
            diff = _cached_call(
                cache, client, item, "difficulty",
                lambda i=item: client.estimate_difficulty(i),
            )
            if diff in taxonomy.VALID_DIFFICULTIES:
                new_item["difficulty"] = diff
        out.append(new_item)
    return out


def difficulty_distribution(items: List[Dict]) -> Dict[str, int]:
    counts = {d: 0 for d in taxonomy.VALID_DIFFICULTIES}
    for q in items:
        d = q.get("difficulty")
        if d in counts:
            counts[d] += 1
    return counts


def run_pipeline(
    items: List[Dict],
    client: AiClient,
    *,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    dedupe_threshold: float = DEDUPE_THRESHOLD,
    cache: Optional[AiCache] = None,
) -> Tuple[List[Dict], Dict]:
    cache = cache or AiCache()
    ai_difficulty = client.name in ("gemini", "openai", "mock")

    diff_before = difficulty_distribution(items)

    kept, dropped, quarantined_scope = pass_validity(
        items, client, cache, use_ai_check=client.name in ("gemini", "openai"),
    )
    tagged, retagged, low_conf = pass_auto_tag(
        kept, client, cache, confidence_threshold,
    )
    deduped, dup_groups, leakage = pass_dedupe(tagged, client, dedupe_threshold)
    final = pass_difficulty(deduped, client, cache, ai_difficulty)

    # Stable ordering.
    final.sort(key=lambda q: (q.get("topic", ""), q.get("id", "")))

    quarantined = list(quarantined_scope)
    for entry in leakage:
        src = next((q for q in items if q.get("id") == entry["id"]), None)
        if src:
            quarantined.append({
                "id": entry["id"],
                "reason": entry["reason"],
                "matched_official_id": entry.get("matched_official_id"),
                "item": src,
            })

    report = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "client": client.name,
        "confidence_threshold": confidence_threshold,
        "dedupe_threshold": dedupe_threshold,
        "totals": {
            "input_count": len(items),
            "output_count": len(final),
            "retagged": len(retagged),
            "low_confidence": len(low_conf),
            "dupes_removed": sum(len(g["duplicates"]) for g in dup_groups),
            "dropped": len(dropped),
            "quarantined": len(quarantined),
        },
        "difficulty_before": diff_before,
        "difficulty_after": difficulty_distribution(final),
        "drops": [{"id": d["id"], "reason": d["reason"]} for d in dropped],
        "quarantined": [
            {"id": q["id"], "reason": q["reason"],
             "matched_official_id": q.get("matched_official_id")}
            for q in quarantined
        ],
        "duplicate_groups": dup_groups,
        "leakage_risks": leakage,
        "low_confidence_items": low_conf,
        "retagged_items": retagged,
    }
    cache.save()
    return final, report


def select_client(mock: bool) -> AiClient:
    if mock:
        return MockClient()
    oai = OpenAIClient.from_env()
    if oai is not None:
        return oai
    gem = GeminiClient.from_env()
    if gem is not None:
        return gem
    return HeuristicClient()


def load_items(path: str) -> List[Dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    return data


def validate_output(items: List[Dict]) -> List[str]:
    errors: List[str] = []
    for q in items:
        errors.extend(taxonomy.validate_question(q))
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="GMATWiz AI content-ingestion / curation layer.",
    )
    parser.add_argument("--in", dest="in_path", default=DEFAULT_QUESTIONS,
                        help="Input normalized questions JSON.")
    parser.add_argument("--out", dest="out_path",
                        default=os.path.join(_HERE, "questions.curated.json"),
                        help="Output curated questions JSON.")
    parser.add_argument("--report", dest="report_path",
                        default=os.path.join(_HERE, "ai_ingest_report.json"),
                        help="Machine-readable curation report.")
    parser.add_argument("--write", action="store_true",
                        help="Allow overwriting the canonical questions.json.")
    parser.add_argument("--mock", action="store_true",
                        help="Use deterministic mock AI (offline, no network).")
    parser.add_argument("--confidence", type=float, default=CONFIDENCE_THRESHOLD,
                        help=f"Topic confidence threshold (default {CONFIDENCE_THRESHOLD}).")
    parser.add_argument("--dedupe", type=float, default=DEDUPE_THRESHOLD,
                        help=f"Near-duplicate similarity threshold (default {DEDUPE_THRESHOLD}).")
    args = parser.parse_args(argv)

    in_path = os.path.abspath(args.in_path)
    out_path = os.path.abspath(args.out_path)
    default_q = os.path.abspath(DEFAULT_QUESTIONS)

    if out_path == default_q and not args.write:
        print(
            "Refusing to overwrite questions.json without --write.\n"
            f"Use --out {os.path.join(_HERE, 'questions.curated.json')} or pass --write.",
            file=sys.stderr,
        )
        return 1

    if not os.path.isfile(in_path):
        print(f"Input not found: {in_path}", file=sys.stderr)
        return 1

    client = select_client(args.mock)
    print(f"GMATWiz ai_ingest — client={client.name}  in={in_path}")

    items = load_items(in_path)
    curated, report = run_pipeline(
        items,
        client,
        confidence_threshold=args.confidence,
        dedupe_threshold=args.dedupe,
    )

    val_errs = validate_output(curated)
    if val_errs:
        print(f"WARNING: {len(val_errs)} validation issue(s) in curated output.", file=sys.stderr)
        report["validation_warnings"] = val_errs[:20]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(curated, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    report["input_file"] = in_path
    report["output_file"] = out_path
    with open(args.report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    t = report["totals"]
    print(f"  input={t['input_count']}  output={t['output_count']}  "
          f"retagged={t['retagged']}  low_conf={t['low_confidence']}  "
          f"dupes_removed={t['dupes_removed']}  dropped={t['dropped']}  "
          f"quarantined={t['quarantined']}")
    print(f"  difficulty before: {report['difficulty_before']}")
    print(f"  difficulty after:  {report['difficulty_after']}")
    print(f"Wrote {len(curated)} curated items -> {out_path}")
    print(f"Wrote report -> {args.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
