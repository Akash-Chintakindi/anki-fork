# Copyright: GMATWiz contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""GMATWiz domain helpers that live inside Anki's `anki` package.

This is brownfield code: it uses Anki's own notetype/collection APIs rather than
wrapping a layer on top. It defines the GMAT Problem Solving notetype and an
importer from the normalized question schema (see gmatwiz/content/) into real
Anki notes, so the shared scheduler can schedule them.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anki.collection
    import anki.models
    import anki.notes


def _stem_hash(stem: str) -> str:
    """Stable dedup key for a question: its Stem lowercased with runs of non-
    alphanumerics collapsed, then hashed. Lets re-import skip content already in
    the collection (no dedicated id field needed). Blank stems return ""."""
    norm = re.sub(r"[^a-z0-9]+", " ", str(stem or "").lower()).strip()
    if not norm:
        return ""
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def _existing_stem_hashes(
    col: anki.collection.Collection, notetype_name: str
) -> set[str]:
    """Stem hashes of every existing note of ``notetype_name`` (empty if none),
    so importers can skip questions already in the collection."""
    hashes: set[str] = set()
    try:
        nids = col.find_notes(f'note:"{notetype_name}"')
    except Exception:
        return hashes
    for nid in nids:
        try:
            note = col.get_note(nid)
            h = _stem_hash(note["Stem"])
        except Exception:
            continue
        if h:
            hashes.add(h)
    return hashes


GMAT_PS_NOTETYPE_NAME = "GMAT PS"

# Fields match the normalized question schema in PRD Section 8 / gmatwiz/content.
GMAT_PS_FIELDS = [
    "Stem",
    "OptionA",
    "OptionB",
    "OptionC",
    "OptionD",
    "OptionE",
    "Correct",
    "Explanation",
    "Topic",
    "Difficulty",
    "Source",
]

_QFMT = """\
<div class="gmat-stem">{{Stem}}</div>
<ol class="gmat-options" type="A">
  <li>{{OptionA}}</li>
  <li>{{OptionB}}</li>
  <li>{{OptionC}}</li>
  <li>{{OptionD}}</li>
  <li>{{OptionE}}</li>
</ol>
"""

_AFMT = """\
{{FrontSide}}
<hr id="answer">
<div class="gmat-correct">Correct answer: {{Correct}}</div>
<div class="gmat-explanation">{{Explanation}}</div>
<div class="gmat-meta">{{Topic}} &middot; {{Difficulty}}</div>
"""

_CSS = """\
.card { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 18px;
  color: #1b1b1f; background: #ffffff; text-align: left; max-width: 640px; margin: 0 auto; }
.gmat-stem { margin: 12px 0 16px; line-height: 1.5; }
.gmat-options { line-height: 1.9; }
#answer { margin: 18px 0; border: none; border-top: 1px solid #e2e2ea; }
.gmat-correct { font-weight: 600; }
.gmat-explanation { margin-top: 8px; color: #333; line-height: 1.5; }
.gmat-meta { margin-top: 12px; font-size: 13px; color: #8a8a96; }
"""


def add_gmat_ps_notetype(
    col: anki.collection.Collection,
) -> anki.models.NotetypeDict:
    """Create the GMAT PS notetype if missing, and return it.

    Idempotent: returns the existing notetype if one with the name exists.
    """
    mm = col.models
    existing = mm.by_name(GMAT_PS_NOTETYPE_NAME)
    if existing:
        return existing

    nt = mm.new(GMAT_PS_NOTETYPE_NAME)
    nt["flds"] = []
    for field_name in GMAT_PS_FIELDS:
        mm.add_field(nt, mm.new_field(field_name))

    nt["tmpls"] = []
    template = mm.new_template("Card 1")
    template["qfmt"] = _QFMT
    template["afmt"] = _AFMT
    mm.add_template(nt, template)

    nt["css"] = _CSS
    mm.add_dict(nt)
    return mm.by_name(GMAT_PS_NOTETYPE_NAME)


def _populate_note(note: anki.notes.Note, q: dict) -> None:
    options = q.get("options", {}) or {}
    note["Stem"] = str(q.get("stem", ""))
    note["OptionA"] = str(options.get("A", ""))
    note["OptionB"] = str(options.get("B", ""))
    note["OptionC"] = str(options.get("C", ""))
    note["OptionD"] = str(options.get("D", ""))
    note["OptionE"] = str(options.get("E", ""))
    note["Correct"] = str(q.get("correct", ""))
    note["Explanation"] = str(q.get("explanation", ""))
    note["Topic"] = str(q.get("topic", ""))
    note["Difficulty"] = str(q.get("difficulty", ""))
    note["Source"] = str(q.get("source", ""))
    topic = q.get("topic")
    if topic:
        note.tags.append(str(topic))


def build_add_requests(
    col: anki.collection.Collection,
    questions: list[dict],
    deck_name: str = "GMAT::Quant",
) -> list[anki.collection.AddNoteRequest]:
    """Build AddNoteRequests (creating the notetype + deck if needed)."""
    from anki.collection import AddNoteRequest

    notetype = add_gmat_ps_notetype(col)
    deck_id = col.decks.id(deck_name)
    seen = _existing_stem_hashes(col, GMAT_PS_NOTETYPE_NAME)
    requests = []
    for q in questions:
        h = _stem_hash(q.get("stem", ""))
        if not h or h in seen:
            continue  # already in the collection (or a dup within this batch)
        seen.add(h)
        note = col.new_note(notetype)
        _populate_note(note, q)
        requests.append(AddNoteRequest(note=note, deck_id=deck_id))
    return requests


def import_questions(
    col: anki.collection.Collection,
    questions: list[dict],
    deck_name: str = "GMAT::Quant",
) -> int:
    """Import normalized question dicts as GMAT PS notes. Returns count added.

    Uses a single batched add_notes call so the whole import is one undoable op.
    """
    requests = build_add_requests(col, questions, deck_name)
    if requests:
        col.add_notes(requests)
    return len(requests)


def import_question_files(
    col: anki.collection.Collection,
    paths: list[str],
    deck_name: str = "GMAT::Quant",
) -> int:
    """Load one or more JSON files of questions and import them. Returns count.

    Each file may be a list of question dicts, or a dict with a "questions" key.
    """
    total = 0
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("questions", [])
        total += import_questions(col, data, deck_name)
    return total


# ---------------------------------------------------------------------------
# GMAT Verbal notetype (Critical Reasoning now; Reading Comprehension in Phase B).
#
# One notetype covers both CR and RC. ``Stem`` is the first (sort) field so it is
# never empty; ``Passage`` / ``PassageId`` are optional and used by RC to share
# one passage across several question cards. The card template renders the passage
# only when present ({{#Passage}}...{{/Passage}}), so CR cards look like PS cards.
# ---------------------------------------------------------------------------
GMAT_VERBAL_NOTETYPE_NAME = "GMAT Verbal"

GMAT_VERBAL_FIELDS = [
    "Stem",
    "OptionA",
    "OptionB",
    "OptionC",
    "OptionD",
    "OptionE",
    "Correct",
    "Explanation",
    "Topic",
    "Difficulty",
    "Source",
    "Passage",
    "PassageId",
]

_V_QFMT = """\
{{#Passage}}<div class="gmat-passage">{{Passage}}</div>{{/Passage}}
<div class="gmat-stem">{{Stem}}</div>
<ol class="gmat-options" type="A">
  <li>{{OptionA}}</li>
  <li>{{OptionB}}</li>
  <li>{{OptionC}}</li>
  <li>{{OptionD}}</li>
  <li>{{OptionE}}</li>
</ol>
"""

_V_AFMT = """\
{{FrontSide}}
<hr id="answer">
<div class="gmat-correct">Correct answer: {{Correct}}</div>
<div class="gmat-explanation">{{Explanation}}</div>
<div class="gmat-meta">{{Topic}} &middot; {{Difficulty}}</div>
"""

_V_CSS = """\
.card { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 18px;
  color: #1b1b1f; background: #ffffff; text-align: left; max-width: 680px; margin: 0 auto; }
.gmat-passage { margin: 8px 0 16px; padding: 12px 14px; background: #f6f4ef;
  border-left: 3px solid #c9bfa8; border-radius: 6px; line-height: 1.55; }
.gmat-stem { margin: 12px 0 16px; line-height: 1.5; }
.gmat-options { line-height: 1.9; }
#answer { margin: 18px 0; border: none; border-top: 1px solid #e2e2ea; }
.gmat-correct { font-weight: 600; }
.gmat-explanation { margin-top: 8px; color: #333; line-height: 1.5; }
.gmat-meta { margin-top: 12px; font-size: 13px; color: #8a8a96; }
"""


def add_gmat_verbal_notetype(
    col: anki.collection.Collection,
) -> anki.models.NotetypeDict:
    """Create the GMAT Verbal notetype if missing, and return it. Idempotent."""
    mm = col.models
    existing = mm.by_name(GMAT_VERBAL_NOTETYPE_NAME)
    if existing:
        return existing

    nt = mm.new(GMAT_VERBAL_NOTETYPE_NAME)
    nt["flds"] = []
    for field_name in GMAT_VERBAL_FIELDS:
        mm.add_field(nt, mm.new_field(field_name))

    nt["tmpls"] = []
    template = mm.new_template("Card 1")
    template["qfmt"] = _V_QFMT
    template["afmt"] = _V_AFMT
    mm.add_template(nt, template)

    nt["css"] = _V_CSS
    mm.add_dict(nt)
    return mm.by_name(GMAT_VERBAL_NOTETYPE_NAME)


def _populate_verbal_note(note: anki.notes.Note, q: dict) -> None:
    options = q.get("options", {}) or {}
    note["Stem"] = str(q.get("stem", ""))
    note["OptionA"] = str(options.get("A", ""))
    note["OptionB"] = str(options.get("B", ""))
    note["OptionC"] = str(options.get("C", ""))
    note["OptionD"] = str(options.get("D", ""))
    note["OptionE"] = str(options.get("E", ""))
    note["Correct"] = str(q.get("correct", ""))
    note["Explanation"] = str(q.get("explanation", ""))
    note["Topic"] = str(q.get("topic", ""))
    note["Difficulty"] = str(q.get("difficulty", ""))
    note["Source"] = str(q.get("source", ""))
    note["Passage"] = str(q.get("passage", "") or "")
    note["PassageId"] = str(q.get("passage_id", "") or "")
    topic = q.get("topic")
    if topic:
        note.tags.append(str(topic))


def build_verbal_add_requests(
    col: anki.collection.Collection,
    questions: list[dict],
    deck_name: str = "GMAT::Verbal",
) -> list[anki.collection.AddNoteRequest]:
    """Build AddNoteRequests for Verbal notes (creating notetype + deck if needed)."""
    from anki.collection import AddNoteRequest

    notetype = add_gmat_verbal_notetype(col)
    deck_id = col.decks.id(deck_name)
    seen = _existing_stem_hashes(col, GMAT_VERBAL_NOTETYPE_NAME)
    requests = []
    for q in questions:
        h = _stem_hash(q.get("stem", ""))
        if not h or h in seen:
            continue
        seen.add(h)
        note = col.new_note(notetype)
        _populate_verbal_note(note, q)
        requests.append(AddNoteRequest(note=note, deck_id=deck_id))
    return requests


def import_verbal_questions(
    col: anki.collection.Collection,
    questions: list[dict],
    deck_name: str = "GMAT::Verbal",
) -> int:
    """Import normalized Verbal question dicts as GMAT Verbal notes. Returns count."""
    requests = build_verbal_add_requests(col, questions, deck_name)
    if requests:
        col.add_notes(requests)
    return len(requests)


def import_verbal_question_files(
    col: anki.collection.Collection,
    paths: list[str],
    deck_name: str = "GMAT::Verbal",
) -> int:
    """Load one or more JSON files of Verbal questions and import them.

    Each file may be a list of question dicts, a dict with a "questions" key, or a
    list of passage groups ({passage_id, passage, topic, questions:[...]}) which are
    flattened so each question carries its shared passage (Reading Comprehension).
    """
    total = 0
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        total += import_verbal_questions(col, flatten_verbal_items(data), deck_name)
    return total


def flatten_verbal_items(data) -> list[dict]:
    """Normalize a verbal content file into a flat list of question dicts.

    Accepts a flat list, a {"questions": [...]} wrapper, or passage groups of the
    form {passage_id, passage, topic, questions:[{stem, options, correct, ...}]}.
    Passage-group questions inherit passage/passage_id/topic from their group.
    """
    if isinstance(data, dict):
        data = data.get("questions", data.get("passages", []))
    out: list[dict] = []
    for entry in data or []:
        if isinstance(entry, dict) and isinstance(entry.get("questions"), list):
            passage = entry.get("passage", "")
            passage_id = entry.get("passage_id", "")
            group_topic = entry.get("topic", "")
            for q in entry["questions"]:
                merged = dict(q)
                merged.setdefault("passage", passage)
                merged.setdefault("passage_id", passage_id)
                if group_topic and not merged.get("topic"):
                    merged["topic"] = group_topic
                out.append(merged)
        elif isinstance(entry, dict):
            out.append(entry)
    return out


# ---------------------------------------------------------------------------
# GMAT DI notetype (Data Insights). Structurally identical to GMAT Verbal: the
# Passage field holds a Multi-Source stimulus (empty for Data Sufficiency /
# Two-Part), and the card template conditionally renders it. Separate notetype +
# deck (GMAT::DI) so section-scoped scoring/queries stay clean.
# ---------------------------------------------------------------------------
GMAT_DI_NOTETYPE_NAME = "GMAT DI"
GMAT_DI_FIELDS = list(GMAT_VERBAL_FIELDS)


def add_gmat_di_notetype(
    col: anki.collection.Collection,
) -> anki.models.NotetypeDict:
    """Create the GMAT DI notetype if missing, and return it. Idempotent."""
    mm = col.models
    existing = mm.by_name(GMAT_DI_NOTETYPE_NAME)
    if existing:
        return existing

    nt = mm.new(GMAT_DI_NOTETYPE_NAME)
    nt["flds"] = []
    for field_name in GMAT_DI_FIELDS:
        mm.add_field(nt, mm.new_field(field_name))

    nt["tmpls"] = []
    template = mm.new_template("Card 1")
    template["qfmt"] = _V_QFMT
    template["afmt"] = _V_AFMT
    mm.add_template(nt, template)

    nt["css"] = _V_CSS
    mm.add_dict(nt)
    return mm.by_name(GMAT_DI_NOTETYPE_NAME)


def build_di_add_requests(
    col: anki.collection.Collection,
    questions: list[dict],
    deck_name: str = "GMAT::DI",
) -> list[anki.collection.AddNoteRequest]:
    """Build AddNoteRequests for DI notes (creating notetype + deck if needed)."""
    from anki.collection import AddNoteRequest

    notetype = add_gmat_di_notetype(col)
    deck_id = col.decks.id(deck_name)
    seen = _existing_stem_hashes(col, GMAT_DI_NOTETYPE_NAME)
    requests = []
    for q in questions:
        h = _stem_hash(q.get("stem", ""))
        if not h or h in seen:
            continue
        seen.add(h)
        note = col.new_note(notetype)
        _populate_verbal_note(note, q)
        requests.append(AddNoteRequest(note=note, deck_id=deck_id))
    return requests


def import_di_questions(
    col: anki.collection.Collection,
    questions: list[dict],
    deck_name: str = "GMAT::DI",
) -> int:
    """Import normalized Data Insights question dicts as GMAT DI notes. Returns count."""
    requests = build_di_add_requests(col, questions, deck_name)
    if requests:
        col.add_notes(requests)
    return len(requests)


def import_di_question_files(
    col: anki.collection.Collection,
    paths: list[str],
    deck_name: str = "GMAT::DI",
) -> int:
    """Load one or more JSON files of DI questions and import them (flat or
    passage-grouped for Multi-Source)."""
    total = 0
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        total += import_di_questions(col, flatten_verbal_items(data), deck_name)
    return total
