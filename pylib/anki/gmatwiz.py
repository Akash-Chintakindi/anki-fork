# Copyright: GMATWiz contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""GMATWiz domain helpers that live inside Anki's `anki` package.

This is brownfield code: it uses Anki's own notetype/collection APIs rather than
wrapping a layer on top. It defines the GMAT Problem Solving notetype and an
importer from the normalized question schema (see gmatwiz/content/) into real
Anki notes, so the shared scheduler can schedule them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anki.collection
    import anki.models
    import anki.notes

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
    requests = []
    for q in questions:
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
