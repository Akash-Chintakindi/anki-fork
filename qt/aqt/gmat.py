# Copyright: GMATWiz contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""GMATWiz desktop integration, living inside Anki's `aqt` package.

GMATWiz is a screen INSIDE Anki's main window (not a separate window): it renders
its SvelteKit app shell into the shared central webview via a "gmat" state in
Anki's state machine. The top-toolbar "GMATWiz" tab switches to it; "Decks" is
the free-study escape hatch. Brownfield: uses Anki's own state machine, webview,
CollectionOp and the `anki.gmatwiz` domain helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

import aqt
import aqt.main
import anki.gmatwiz
from anki.collection import OpChanges
from aqt import gui_hooks
from aqt.operations import CollectionOp
from aqt.qt import QAction, QFileDialog, qconnect
from aqt.utils import showInfo, tooltip

GMAT_DECK_NAME = "GMAT::Quant"


def render_gmat_screen(mw: aqt.main.AnkiQt) -> None:
    """Render the GMATWiz app shell into the main window's central webview."""
    mw.web.load_sveltekit_page("gmat")
    mw.web.setFocus()
    # GMATWiz is a full screen; hide Anki's per-state bottom bar.
    mw.bottomWeb.hide()
    # GMATWiz is full-bleed with its own in-app nav; hide the native top toolbar.
    mw.toolbarWeb.hide()


def open_gmat(mw: aqt.main.AnkiQt) -> None:
    mw.moveToState("gmat")


def _content_dir() -> Path:
    # qt/aqt/gmat.py -> aqt -> qt -> repo root; content lives at gmatwiz/content.
    return Path(__file__).resolve().parents[2] / "gmatwiz" / "content"


def _load_question_dicts() -> list[dict]:
    questions: list[dict] = []
    for name in ("seed.json", "questions.json"):
        path = _content_dir() / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("questions", [])
        questions.extend(data)
    return questions


def _ensure_generous_limits(col) -> None:
    """Give the GMAT deck its own preset with high daily limits so the guided
    app isn't capped at Anki's default 20 new/day. Leaves the Default preset
    untouched. Idempotent."""
    deck_id = col.decks.id(GMAT_DECK_NAME)
    conf = col.decks.config_dict_for_deck_id(deck_id)
    if conf.get("name") == "Default":
        conf = col.decks.add_config("GMATWiz")
        deck = col.decks.get(deck_id)
        if deck is not None:
            deck["conf"] = conf["id"]
            col.decks.save(deck)
    conf["new"]["perDay"] = 9999
    conf["rev"]["perDay"] = 9999
    col.decks.update_config(conf)


def import_gmat_content(mw: aqt.main.AnkiQt) -> None:
    """Import the bundled GMAT Quant questions into the current collection."""
    questions = _load_question_dicts()
    if not questions:
        showInfo(
            f"No GMAT content found under {_content_dir()}.",
            parent=mw,
            title="GMATWiz",
        )
        return

    def op(col) -> OpChanges:
        requests = anki.gmatwiz.build_add_requests(col, questions, GMAT_DECK_NAME)
        changes = col.add_notes(requests)
        _ensure_generous_limits(col)
        return changes

    def on_success(_out) -> None:
        tooltip(
            f"Imported {len(questions)} GMAT questions into {GMAT_DECK_NAME}.",
            parent=mw,
        )
        if mw.state == "gmat":
            render_gmat_screen(mw)

    CollectionOp(parent=mw, op=op).success(on_success).run_in_background()


_OPTION_KEYS = ["A", "B", "C", "D", "E"]


def _first(row: dict, *aliases: str) -> str:
    """Fetch the first present, non-empty value among case-insensitive aliases."""
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in aliases:
        val = lower.get(alias.lower())
        if val not in (None, ""):
            return str(val).strip()
    return ""


def _normalize_user_question(row: dict) -> tuple[dict | None, str | None]:
    """Map one imported row (our JSON schema or a flat CSV row) to the GMAT PS
    question dict, or return an error string if it's not usable."""
    stem = _first(row, "stem")
    if not stem:
        return None, "missing stem"

    options: dict = {}
    raw_options = row.get("options")
    if isinstance(raw_options, dict):
        for k in _OPTION_KEYS:
            v = raw_options.get(k) or raw_options.get(k.lower())
            if v not in (None, ""):
                options[k] = str(v).strip()
    else:
        for k in _OPTION_KEYS:
            v = _first(row, k, f"option{k}", f"choice{k}")
            if v:
                options[k] = v
    if len(options) < 2:
        return None, "need at least 2 options"

    correct = _first(row, "correct", "answer", "correct_answer").upper()
    if correct not in options:
        return None, f"correct answer {correct or '(blank)'} is not one of the options"

    return {
        "stem": stem,
        "options": options,
        "correct": correct,
        "explanation": _first(row, "explanation", "solution"),
        "topic": _first(row, "topic"),
        "difficulty": _first(row, "difficulty") or "medium",
        "source": _first(row, "source") or "user-upload",
    }, None


def _parse_user_questions(path: str) -> tuple[list[dict], list[str]]:
    """Parse a user JSON or CSV file into validated question dicts + row errors."""
    text = Path(path).read_text(encoding="utf-8")
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("questions", [])
        rows = data if isinstance(data, list) else []
    elif suffix == ".csv":
        import csv
        import io

        rows = [dict(r) for r in csv.DictReader(io.StringIO(text))]
    else:
        raise ValueError("unsupported file type (use .json or .csv)")

    valid: list[dict] = []
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"Row {i}: not an object")
            continue
        q, err = _normalize_user_question(row)
        if err:
            errors.append(f"Row {i}: {err}")
        else:
            valid.append(q)
    return valid, errors


def import_user_questions(mw: aqt.main.AnkiQt) -> None:
    """Let the student import their OWN question set (content they legally have)
    to practice in-app - the PRD ContentSource 'user-upload' seam. Accepts JSON
    (our schema) or CSV; validates, tags provenance, and imports into GMAT::Quant."""
    path, _ = QFileDialog.getOpenFileName(
        mw, "Import GMAT questions", "", "GMAT questions (*.json *.csv)"
    )
    if not path:
        return
    try:
        questions, errors = _parse_user_questions(path)
    except Exception as exc:
        showInfo(f"Could not read that file:\n{exc}", parent=mw, title="GMATWiz")
        return
    if not questions:
        detail = "\n".join(errors[:10]) if errors else "The file had no questions."
        showInfo(f"No valid questions found.\n\n{detail}", parent=mw, title="GMATWiz")
        return

    def op(col) -> OpChanges:
        requests = anki.gmatwiz.build_add_requests(col, questions, GMAT_DECK_NAME)
        for req in requests:
            req.note.tags.append("gmatwiz::user-upload")
        changes = col.add_notes(requests)
        _ensure_generous_limits(col)
        return changes

    def on_success(_out) -> None:
        msg = f"Imported {len(questions)} question(s) into {GMAT_DECK_NAME}."
        if errors:
            msg += f"\n\nSkipped {len(errors)} row(s):\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n… and {len(errors) - 10} more."
        showInfo(msg, parent=mw, title="GMATWiz")
        if mw.state == "gmat":
            render_gmat_screen(mw)

    CollectionOp(parent=mw, op=op).success(on_success).run_in_background()


# Native Anki toolbar tabs we hide: GMATWiz surfaces Decks (free study) and
# Stats inside its own UI, and Sync via its own control, so the raw tabs are
# redundant clutter for a focused GMAT student.
_HIDDEN_TOOLBAR_IDS = ('id="decks"', 'id="add"', 'id="browse"', 'id="stats"', 'id="sync"')


def _add_toolbar_link(links: list, toolbar) -> None:
    # Strip the built-in tabs, leaving a single GMATWiz-focused toolbar.
    links[:] = [l for l in links if not any(h in l for h in _HIDDEN_TOOLBAR_IDS)]
    link = toolbar.create_link(
        "gmatwiz",
        "GMATWiz",
        lambda: open_gmat(aqt.mw),
        tip="Open the GMATWiz study app",
        id="gmatwiz",
    )
    links.insert(0, link)


def _auto_open(*_args) -> None:
    # Land on GMATWiz once the collection is ready, so it's the first screen the
    # student sees. Deferred so it runs after the normal startup state is set.
    mw = aqt.mw
    if mw is None:
        return

    def go() -> None:
        try:
            if mw.col is not None and mw.state in ("deckBrowser", "startup"):
                mw.moveToState("gmat")
        except Exception as exc:  # never block startup on the companion UI
            print(f"GMATWiz auto-open failed: {exc}")

    mw.progress.single_shot(100, go, False)


def setup_gmat_menu(mw: aqt.main.AnkiQt) -> None:
    """Wire GMATWiz into Anki: Tools menu, toolbar tab, and auto-land."""
    menu = mw.form.menuTools
    menu.addSeparator()

    open_action = QAction("GMATWiz", mw)
    qconnect(open_action.triggered, lambda: open_gmat(mw))
    menu.addAction(open_action)

    import_action = QAction("Import GMAT Quant", mw)
    qconnect(import_action.triggered, lambda: import_gmat_content(mw))
    menu.addAction(import_action)

    user_import_action = QAction("Import my questions\u2026", mw)
    qconnect(user_import_action.triggered, lambda: import_user_questions(mw))
    menu.addAction(user_import_action)

    gui_hooks.top_toolbar_did_init_links.append(_add_toolbar_link)
    gui_hooks.profile_did_open.append(_auto_open)
