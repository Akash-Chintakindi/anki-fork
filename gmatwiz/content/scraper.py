#!/usr/bin/env python3
"""GMATWiz content scraper — GMAT Quant (Problem Solving) questions.

Pulls free, publicly-accessible GMAT Quant PS questions, normalizes them to the
GMATWiz schema, dedupes near-duplicates, auto-tags each item to a PRD Section 5
leaf topic, and writes:

  * questions.json        — normalized, deduped, in-scope questions
  * raw/<source>__*.{...} — raw per-source captures (HTML / JSON / robots / errors)
  * scrape_report.json    — per-source machine-readable run report

Design goals
------------
* Reusable + dependency-light: runs on the Python standard library alone.
  (If ``requests`` happens to be installed it will be used; otherwise urllib.)
* Honest + safe: respects robots.txt by default; tags every item with its
  ``source`` and a conservative ``license`` ("scraped-unverified" unless the
  source is a clearly-open, license-verified dataset). Official/copyrighted
  forum content is never relabeled as open.
* Resilient: any source that is blocked, rate-limited, or unparseable is
  recorded and skipped — the pipeline keeps going (the authored seed.json is the
  guaranteed-usable fallback).

Sources (each is a self-contained adapter):
  1. gmatclub   — GMAT Club free "Problem Solving (PS)" forum threads.
  2. reddit     — Reddit r/GMAT public JSON listing/search.
  3. aqua_rat   — AQuA-RAT (DeepMind) open dataset, Apache-2.0 (GMAT/GRE-style
                  algebraic word problems, 5 options A-E + rationale). This is
                  the redistributable, license-verified source.

Usage examples
--------------
    python3 scraper.py                       # all sources, respect robots
    python3 scraper.py --sources aqua_rat    # just the open dataset
    python3 scraper.py --limit 100           # cap per-source normalized output
    python3 scraper.py --ignore-robots aqua_rat   # override robots for the
                                                   # Apache-2.0 dataset only

Out of scope (dropped with a reason): geometry and Data Sufficiency
(PRD Section 5 — GMAT Focus Quant = Problem Solving, arithmetic + algebra only).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

# Make the shared taxonomy importable regardless of the caller's CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import taxonomy  # noqa: E402  (local module)

# Optional dependency — used only if present.
try:  # pragma: no cover
    import requests  # type: ignore

    _HAVE_REQUESTS = True
except Exception:  # pragma: no cover
    requests = None  # type: ignore
    _HAVE_REQUESTS = False

USER_AGENT = (
    "GMATWiz-ContentBot/0.1 (+educational GMAT prep; respects robots.txt; "
    "contact: gmatwiz-content@example.invalid)"
)
DEFAULT_TIMEOUT = 25
RAW_DIR_NAME = "raw"


# ===========================================================================
# Utilities
# ===========================================================================
def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)[:120]


class HttpResult:
    def __init__(self, url: str, status: Optional[int], body: bytes,
                 headers: Dict[str, str], error: Optional[str]):
        self.url = url
        self.status = status
        self.body = body
        self.headers = headers
        self.error = error

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and not self.error

    def text(self, encoding: str = "utf-8") -> str:
        try:
            return self.body.decode(encoding, errors="replace")
        except Exception:
            return self.body.decode("latin-1", errors="replace")


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT,
             accept: str = "text/html,application/json,*/*") -> HttpResult:
    """GET a URL with a clear bot UA. Never raises — returns an HttpResult."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if _HAVE_REQUESTS:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            return HttpResult(url, resp.status_code, resp.content,
                              {k.lower(): v for k, v in resp.headers.items()}, None)
        except Exception as exc:  # pragma: no cover
            return HttpResult(url, None, b"", {}, f"{type(exc).__name__}: {exc}")
    # urllib fallback
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            return HttpResult(url, r.status, body, hdrs, None)
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read()
        except Exception:
            pass
        return HttpResult(url, exc.code, body, {}, f"HTTPError {exc.code}: {exc.reason}")
    except Exception as exc:
        return HttpResult(url, None, b"", {}, f"{type(exc).__name__}: {exc}")


class RobotsGate:
    """robots.txt checker with a per-host cache."""

    def __init__(self, user_agent: str = USER_AGENT):
        self.user_agent = user_agent
        self._cache: Dict[str, Tuple[Optional[urllib.robotparser.RobotFileParser], str]] = {}

    def _robots_for(self, url: str):
        from urllib.parse import urlsplit

        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host in self._cache:
            return self._cache[host]
        robots_url = host + "/robots.txt"
        res = http_get(robots_url, accept="text/plain")
        rp = urllib.robotparser.RobotFileParser()
        raw_txt = ""
        if res.ok and res.body:
            raw_txt = res.text()
            try:
                rp.parse(raw_txt.splitlines())
            except Exception:
                rp = None  # type: ignore
        elif res.status in (401, 403):
            # Treat an access-denied robots as "be conservative": disallow.
            rp.parse(["User-agent: *", "Disallow: /"])
            raw_txt = f"(robots.txt returned {res.status}; treated as Disallow: /)"
        else:
            # No robots.txt (404/empty) => generally allowed.
            rp.parse(["User-agent: *", "Allow: /"])
            raw_txt = f"(no usable robots.txt; status={res.status})"
        self._cache[host] = (rp, raw_txt)
        return self._cache[host]

    def can_fetch(self, url: str) -> bool:
        rp, _ = self._robots_for(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(self.user_agent, url) or rp.can_fetch("*", url)
        except Exception:
            return True

    def robots_text(self, url: str) -> str:
        _, txt = self._robots_for(url)
        return txt


class RawSink:
    """Writes raw per-source captures into content/raw/."""

    def __init__(self, raw_dir: str):
        self.raw_dir = raw_dir
        os.makedirs(raw_dir, exist_ok=True)
        self.written: List[str] = []

    def save(self, source: str, label: str, content, ext: str = "txt") -> str:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fname = f"{_safe_name(source)}__{_safe_name(label)}__{ts}.{ext}"
        path = os.path.join(self.raw_dir, fname)
        mode = "wb" if isinstance(content, (bytes, bytearray)) else "w"
        with open(path, mode, encoding=None if "b" in mode else "utf-8") as fh:
            fh.write(content)
        self.written.append(path)
        return path


# ===========================================================================
# HTML helpers
# ===========================================================================
class _TextExtractor(HTMLParser):
    _BLOCK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "blockquote", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._buf: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self._BLOCK:
            self._buf.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in self._BLOCK:
            self._buf.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def get_text(self) -> str:
        text = "".join(self._buf)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)
        return text.strip()


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return p.get_text()


_OPTION_MARKER = re.compile(r"(?:(?<=^)|(?<=\s)|(?<=\())\(?([A-E])\)?\s*[.):\-]\s+")


def parse_options(text: str) -> Optional[Dict[str, str]]:
    """Extract A-E options from a block of text. Returns dict or None."""
    markers = list(_OPTION_MARKER.finditer(text))
    # Keep the first clean ascending A,B,C,D,E run.
    seq: List[Tuple[str, int, int]] = []
    expected_ord = ord("A")
    for m in markers:
        letter = m.group(1)
        if ord(letter) == expected_ord:
            seq.append((letter, m.start(), m.end()))
            expected_ord += 1
            if expected_ord > ord("E"):
                break
    if len(seq) != 5:
        return None
    options: Dict[str, str] = {}
    for i, (letter, _start, content_start) in enumerate(seq):
        end = seq[i + 1][1] if i + 1 < len(seq) else len(text)
        val = text[content_start:end]
        # Options are single-line in practice; drop anything on later lines.
        val = val.split("\n", 1)[0]
        # Trim a trailing answer/explanation marker that bled into the slice
        # (common on the last option, e.g. "10  OA: B").
        val = re.split(
            r"\s+(?:OA|O\.A\.|official answer|correct answer|answer|ans|key|"
            r"explanation|spoiler)\b.*",
            val, maxsplit=1, flags=re.IGNORECASE,
        )[0]
        val = re.sub(r"\s+", " ", val).strip().strip(".;,")
        if not val or len(val) > 200:
            return None
        options[letter] = val
    return options


_ANSWER_RE = re.compile(
    r"(?:OA|official answer|correct answer|the answer is|answer\s*choice|answer|ans|key)"
    r"\s*(?:is|:|=|-|\u2013)?\s*\(?([A-E])\)?\b",
    re.IGNORECASE,
)


def parse_correct(text: str) -> Optional[str]:
    matches = _ANSWER_RE.findall(text or "")
    if not matches:
        return None
    return matches[-1].upper()


# ===========================================================================
# Normalization
# ===========================================================================
def normalize_item(
    *,
    source_tag: str,
    stem: str,
    options: Dict[str, str],
    correct: str,
    explanation: str,
    source: str,
    license: str,
    difficulty: Optional[str] = None,
) -> Optional[Tuple[Dict, Optional[str]]]:
    """Return (question_dict, drop_reason). drop_reason is None when accepted."""
    stem = re.sub(r"\s+", " ", (stem or "").strip())
    if not stem or len(stem) < 12:
        return None, "stem_too_short"
    if correct not in taxonomy.OPTION_KEYS:
        return None, "no_valid_correct_answer"
    if set(options.keys()) != set(taxonomy.OPTION_KEYS):
        return None, "options_not_A_to_E"
    if any(not (v and v.strip()) for v in options.values()):
        return None, "empty_option"
    distinct = {re.sub(r"\s+", " ", v.strip().lower()) for v in options.values()}
    if len(distinct) < 5:
        return None, "duplicate_options"

    blob = stem + " " + " ".join(options.values()) + " " + (explanation or "")
    scope = taxonomy.out_of_scope_reason(blob)
    if scope:
        return None, f"out_of_scope:{scope}"

    topic = taxonomy.tag_topic(stem + " " + " ".join(options.values()))
    diff = difficulty or taxonomy.guess_difficulty(blob, default="medium")

    q = taxonomy.make_question(
        id=taxonomy.make_id(source_tag, stem, options),
        stem=stem,
        options=options,
        correct=correct,
        explanation=re.sub(r"\s+\n", "\n", (explanation or "").strip()),
        topic=topic,
        difficulty=diff,
        source=source,
        license=license,
        scraped_at=now_iso(),
    )
    errs = taxonomy.validate_question(q)
    if errs:
        return None, "validation:" + ";".join(errs)
    return q, None


# ===========================================================================
# Source adapters
# Each returns (questions: List[dict], report: dict)
# ===========================================================================
def scrape_gmatclub(robots: RobotsGate, raw: RawSink, limit: int,
                    ignore_robots: bool, delay: float, max_threads: int = 12) -> Tuple[List[Dict], Dict]:
    name = "gmatclub"
    index_url = "https://gmatclub.com/forum/problem-solving-ps-140/"
    report = {
        "source": name,
        "site": "https://gmatclub.com",
        "entrypoint": index_url,
        "license_policy": "scraped-unverified (forum content, copyright retained by authors)",
        "robots_allowed": None,
        "robots_excerpt": "",
        "http_status": None,
        "raw_items_found": 0,
        "normalized": 0,
        "dropped": {},
        "blocked": False,
        "notes": [],
    }
    questions: List[Dict] = []

    allowed = robots.can_fetch(index_url)
    report["robots_allowed"] = allowed
    report["robots_excerpt"] = robots.robots_text(index_url)[:500]
    raw.save(name, "robots", robots.robots_text(index_url), "txt")
    if not allowed and not ignore_robots:
        report["blocked"] = True
        report["notes"].append("robots.txt disallows this path for our user-agent; skipped (respecting robots).")
        return questions, report

    res = http_get(index_url)
    report["http_status"] = res.status
    raw.save(name, "index", res.body or (res.error or "").encode(), "html" if res.body else "txt")
    if not res.ok:
        report["blocked"] = True
        report["notes"].append(f"index fetch failed (status={res.status}, error={res.error}); likely Cloudflare/bot protection.")
        return questions, report

    html = res.text()
    # Forum thread links look like <a ... class="topictitle" href="/forum/....html">Title</a>
    thread_links = re.findall(r'href="(/forum/[^"#?]+?-\d+\.html)"[^>]*class="[^"]*topictitle', html)
    thread_links += re.findall(r'class="[^"]*topictitle[^"]*"[^>]*href="(/forum/[^"#?]+?-\d+\.html)"', html)
    seen = set()
    ordered = []
    for href in thread_links:
        if href not in seen:
            seen.add(href)
            ordered.append(href)
    report["raw_items_found"] = len(ordered)
    if not ordered:
        report["notes"].append("no thread links parsed from index (page structure may have changed or content is JS-rendered).")

    dropped: Dict[str, int] = {}
    for href in ordered[:max_threads]:
        if len(questions) >= limit:
            break
        url = "https://gmatclub.com" + href
        if not (ignore_robots or robots.can_fetch(url)):
            dropped["robots_thread"] = dropped.get("robots_thread", 0) + 1
            continue
        time.sleep(delay)
        tres = http_get(url)
        if not tres.ok:
            dropped[f"thread_http_{tres.status}"] = dropped.get(f"thread_http_{tres.status}", 0) + 1
            continue
        thtml = tres.text()
        # First post body — GMAT Club uses <div class="item text"> / "content" containers.
        m = re.search(r'class="(?:item text|content|postbody)"[^>]*>(.*?)</div>', thtml, re.DOTALL | re.IGNORECASE)
        post_html = m.group(1) if m else thtml
        text = html_to_text(post_html)
        opts = parse_options(text)
        if not opts:
            dropped["no_options"] = dropped.get("no_options", 0) + 1
            continue
        first_marker = _OPTION_MARKER.search(text)
        stem = text[: first_marker.start()].strip() if first_marker else ""
        correct = parse_correct(thtml) or parse_correct(text) or ""
        if not correct:
            dropped["no_official_answer"] = dropped.get("no_official_answer", 0) + 1
            continue
        q, reason = normalize_item(
            source_tag="gmatclub",
            stem=stem,
            options=opts,
            correct=correct,
            explanation="",
            source=url,
            license="scraped-unverified",
        )
        if q:
            questions.append(q)
        else:
            dropped[reason or "unknown"] = dropped.get(reason or "unknown", 0) + 1

    report["normalized"] = len(questions)
    report["dropped"] = dropped
    if not questions and not report["blocked"]:
        report["notes"].append("reachable but yielded 0 normalized items (answers are typically hidden in spoilers/JS).")
    return questions, report


def scrape_reddit(robots: RobotsGate, raw: RawSink, limit: int,
                  ignore_robots: bool, delay: float) -> Tuple[List[Dict], Dict]:
    name = "reddit"
    listing_url = "https://www.reddit.com/r/GMAT/search.json?q=problem+solving&restrict_sr=1&limit=100"
    report = {
        "source": name,
        "site": "https://www.reddit.com/r/GMAT",
        "entrypoint": listing_url,
        "license_policy": "scraped-unverified (user posts, copyright retained by authors)",
        "robots_allowed": None,
        "robots_excerpt": "",
        "http_status": None,
        "raw_items_found": 0,
        "normalized": 0,
        "dropped": {},
        "blocked": False,
        "notes": [],
    }
    questions: List[Dict] = []

    allowed = robots.can_fetch(listing_url)
    report["robots_allowed"] = allowed
    report["robots_excerpt"] = robots.robots_text(listing_url)[:500]
    raw.save(name, "robots", robots.robots_text(listing_url), "txt")
    if not allowed and not ignore_robots:
        report["blocked"] = True
        report["notes"].append("reddit.com/robots.txt disallows automated crawling for our user-agent; skipped (respecting robots).")
        return questions, report

    time.sleep(delay)
    res = http_get(listing_url, accept="application/json")
    report["http_status"] = res.status
    raw.save(name, "search", res.body or (res.error or "").encode(), "json" if res.body else "txt")
    if not res.ok:
        report["blocked"] = True
        report["notes"].append(f"listing fetch failed (status={res.status}, error={res.error}); Reddit blocks unauthenticated bots.")
        return questions, report

    try:
        data = json.loads(res.text())
        children = data.get("data", {}).get("children", [])
    except Exception as exc:
        report["blocked"] = True
        report["notes"].append(f"could not parse Reddit JSON: {exc}")
        return questions, report

    report["raw_items_found"] = len(children)
    dropped: Dict[str, int] = {}
    for child in children:
        if len(questions) >= limit:
            break
        post = child.get("data", {})
        body = (post.get("selftext") or "").strip()
        title = (post.get("title") or "").strip()
        permalink = "https://www.reddit.com" + post.get("permalink", "")
        if not body:
            dropped["no_selftext"] = dropped.get("no_selftext", 0) + 1
            continue
        opts = parse_options(body)
        if not opts:
            dropped["no_options"] = dropped.get("no_options", 0) + 1
            continue
        first_marker = _OPTION_MARKER.search(body)
        stem = body[: first_marker.start()].strip() if first_marker else title
        if len(stem) < 12:
            stem = (title + " " + stem).strip()
        correct = parse_correct(body) or ""
        if not correct:
            dropped["no_answer"] = dropped.get("no_answer", 0) + 1
            continue
        q, reason = normalize_item(
            source_tag="reddit",
            stem=stem,
            options=opts,
            correct=correct,
            explanation="",
            source=permalink,
            license="scraped-unverified",
        )
        if q:
            questions.append(q)
        else:
            dropped[reason or "unknown"] = dropped.get(reason or "unknown", 0) + 1

    report["normalized"] = len(questions)
    report["dropped"] = dropped
    if not questions and not report["blocked"]:
        report["notes"].append("reachable but 0 clean 5-option PS items with a stated answer were found.")
    return questions, report


# AQuA-RAT: open, Apache-2.0 licensed dataset of GMAT/GRE-style multiple-choice
# algebraic word problems with rationales. https://github.com/google-deepmind/AQuA
_AQUA_CANDIDATES = [
    "https://raw.githubusercontent.com/google-deepmind/AQuA/master/test.json",
    "https://raw.githubusercontent.com/google-deepmind/AQuA/main/test.json",
    "https://raw.githubusercontent.com/deepmind/AQuA/master/test.json",
    "https://raw.githubusercontent.com/deepmind/AQuA/master/dev.json",
]
_AQUA_OPTION_RE = re.compile(r"^\s*([A-E])\s*[\).:\-]?\s*(.*)$")


def scrape_aqua_rat(robots: RobotsGate, raw: RawSink, limit: int,
                    ignore_robots: bool, delay: float) -> Tuple[List[Dict], Dict]:
    name = "aqua_rat"
    report = {
        "source": name,
        "site": "https://github.com/google-deepmind/AQuA",
        "entrypoint": _AQUA_CANDIDATES[0],
        "license_policy": "Apache-2.0 (verified open dataset; redistributable with attribution)",
        "robots_allowed": None,
        "robots_excerpt": "",
        "http_status": None,
        "raw_items_found": 0,
        "normalized": 0,
        "dropped": {},
        "blocked": False,
        "notes": [],
    }
    questions: List[Dict] = []

    chosen = None
    body_text = None
    for url in _AQUA_CANDIDATES:
        allowed = robots.can_fetch(url)
        report["robots_allowed"] = allowed
        report["robots_excerpt"] = robots.robots_text(url)[:500]
        if not allowed and not ignore_robots:
            report["notes"].append(f"robots disallows {url}; trying next candidate / skipping.")
            continue
        time.sleep(delay)
        res = http_get(url, accept="application/json,text/plain,*/*")
        report["http_status"] = res.status
        if res.ok and res.body:
            chosen = url
            body_text = res.text()
            report["entrypoint"] = url
            raw.save(name, "dataset", res.body, "jsonl")
            break
        else:
            report["notes"].append(f"fetch failed for {url} (status={res.status}, error={res.error}).")

    if not body_text:
        report["blocked"] = True
        if report["robots_allowed"] is False and not ignore_robots:
            report["notes"].append("all candidate URLs were robots-disallowed; re-run with --ignore-robots aqua_rat to fetch this Apache-2.0 dataset.")
        else:
            report["notes"].append("could not retrieve the AQuA-RAT dataset from any candidate URL.")
        return questions, report

    # AQuA is JSON-lines: one JSON object per line.
    lines = [ln for ln in body_text.splitlines() if ln.strip()]
    report["raw_items_found"] = len(lines)
    dropped: Dict[str, int] = {}
    for ln in lines:
        if len(questions) >= limit:
            break
        try:
            obj = json.loads(ln)
        except Exception:
            dropped["bad_json_line"] = dropped.get("bad_json_line", 0) + 1
            continue
        stem = (obj.get("question") or "").strip()
        raw_opts = obj.get("options") or []
        correct = (obj.get("correct") or "").strip().upper()
        rationale = (obj.get("rationale") or "").strip()
        if len(raw_opts) != 5:
            dropped["not_5_options"] = dropped.get("not_5_options", 0) + 1
            continue
        options: Dict[str, str] = {}
        ok = True
        for raw_opt in raw_opts:
            m = _AQUA_OPTION_RE.match(str(raw_opt))
            if not m:
                ok = False
                break
            letter, val = m.group(1), m.group(2).strip()
            options[letter] = val
        if not ok or set(options.keys()) != set(taxonomy.OPTION_KEYS):
            dropped["unparseable_options"] = dropped.get("unparseable_options", 0) + 1
            continue
        q, reason = normalize_item(
            source_tag="aqua",
            stem=stem,
            options=options,
            correct=correct,
            explanation=rationale,
            source=f"AQuA-RAT (DeepMind) {chosen}",
            license="Apache-2.0",
        )
        if q:
            questions.append(q)
        else:
            dropped[reason or "unknown"] = dropped.get(reason or "unknown", 0) + 1

    report["normalized"] = len(questions)
    report["dropped"] = dropped
    report["notes"].append(
        "AQuA-RAT (Ling et al., 2017), Apache-2.0. GMAT/GRE-style PS word problems; "
        "geometry & data-sufficiency items filtered out per PRD scope."
    )
    return questions, report


ADAPTERS = {
    "gmatclub": scrape_gmatclub,
    "reddit": scrape_reddit,
    "aqua_rat": scrape_aqua_rat,
}


# ===========================================================================
# Dedup (exact content hash + near-duplicate via token Jaccard)
# ===========================================================================
def _tokens(text: str) -> set:
    return set(taxonomy.normalize_for_dedup(text).split())


def dedupe(questions: List[Dict], jaccard_threshold: float = 0.85) -> Tuple[List[Dict], int]:
    """Remove exact and near-duplicate stems. Returns (kept, removed_count)."""
    kept: List[Dict] = []
    seen_hashes = set()
    kept_token_sets: List[set] = []
    removed = 0
    for q in questions:
        h = taxonomy.content_hash(q["stem"], q["options"])
        if h in seen_hashes:
            removed += 1
            continue
        toks = _tokens(q["stem"])
        is_dup = False
        if toks:
            for prev in kept_token_sets:
                if not prev:
                    continue
                inter = len(toks & prev)
                union = len(toks | prev)
                if union and inter / union >= jaccard_threshold:
                    is_dup = True
                    break
        if is_dup:
            removed += 1
            continue
        seen_hashes.add(h)
        kept_token_sets.append(toks)
        kept.append(q)
    return kept, removed


# ===========================================================================
# Main
# ===========================================================================
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GMATWiz GMAT Quant PS scraper.")
    parser.add_argument("--sources", nargs="*", default=list(ADAPTERS.keys()),
                        choices=list(ADAPTERS.keys()),
                        help="Which source adapters to run (default: all).")
    parser.add_argument("--limit", type=int, default=300,
                        help="Max normalized items to KEEP per source (default 300).")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Politeness delay (seconds) between requests (default 1.0).")
    parser.add_argument("--ignore-robots", nargs="*", default=[],
                        help="Source name(s) for which to bypass robots.txt (use only for "
                             "clearly-open/own content, e.g. aqua_rat). 'all' bypasses for every source.")
    parser.add_argument("--out", default=os.path.join(_HERE, "questions.json"),
                        help="Output path for normalized questions JSON.")
    parser.add_argument("--raw-dir", default=os.path.join(_HERE, RAW_DIR_NAME),
                        help="Directory for raw per-source captures.")
    parser.add_argument("--report", default=os.path.join(_HERE, "scrape_report.json"),
                        help="Output path for the machine-readable scrape report.")
    parser.add_argument("--jaccard", type=float, default=0.85,
                        help="Near-duplicate Jaccard threshold (default 0.85).")
    args = parser.parse_args(argv)

    robots = RobotsGate()
    raw = RawSink(args.raw_dir)

    ignore_all = "all" in args.ignore_robots
    all_questions: List[Dict] = []
    reports: List[Dict] = []

    print(f"GMATWiz scraper — sources: {', '.join(args.sources)}  "
          f"(requests={'yes' if _HAVE_REQUESTS else 'no, urllib'})")
    for src in args.sources:
        ignore = ignore_all or (src in args.ignore_robots)
        print(f"\n=== {src} (ignore_robots={ignore}) ===")
        try:
            qs, rep = ADAPTERS[src](robots, raw, args.limit, ignore, args.delay)
        except Exception as exc:  # never let one source kill the run
            tb = traceback.format_exc()
            raw.save(src, "exception", tb, "txt")
            qs, rep = [], {
                "source": src, "blocked": True, "normalized": 0,
                "notes": [f"adapter raised: {type(exc).__name__}: {exc}"],
            }
        reps_status = "BLOCKED" if rep.get("blocked") else "ok"
        print(f"    robots_allowed={rep.get('robots_allowed')}  http={rep.get('http_status')}  "
              f"raw={rep.get('raw_items_found')}  normalized={rep.get('normalized')}  [{reps_status}]")
        for note in rep.get("notes", []):
            print(f"    note: {note}")
        all_questions.extend(qs)
        reports.append(rep)

    before = len(all_questions)
    deduped, removed = dedupe(all_questions, args.jaccard)
    print(f"\nDedup: {before} -> {len(deduped)} kept ({removed} near/exact dupes removed)")

    # Stable ordering: by topic then id.
    deduped.sort(key=lambda q: (q["topic"], q["id"]))

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(deduped, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    tcounts = taxonomy.topic_counts(deduped)
    report_doc = {
        "generated_at": now_iso(),
        "user_agent": USER_AGENT,
        "http_client": "requests" if _HAVE_REQUESTS else "urllib",
        "totals": {
            "normalized_before_dedupe": before,
            "kept_after_dedupe": len(deduped),
            "removed_dupes": removed,
        },
        "per_source": reports,
        "topic_counts": {k: v for k, v in tcounts.items() if v},
        "raw_files_written": raw.written,
        "output_file": args.out,
    }
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report_doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"\nWrote {len(deduped)} questions -> {args.out}")
    print(f"Wrote scrape report -> {args.report}")
    print(f"Raw captures ({len(raw.written)}) -> {args.raw_dir}")
    print("\nPer-source normalized counts:")
    for rep in reports:
        print(f"  {rep.get('source'):10s}: {rep.get('normalized', 0):4d}"
              f"  {'(blocked)' if rep.get('blocked') else ''}")
    print("\nTopic counts (non-zero):")
    for topic, count in sorted(tcounts.items()):
        if count:
            print(f"  {topic:45s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
