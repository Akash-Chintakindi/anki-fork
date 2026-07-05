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
GMAT_VERBAL_DECK_NAME = "GMAT::Verbal"
GMAT_DI_DECK_NAME = "GMAT::DI"

# Bump when the bundled content changes (new sections, scraped questions, etc.)
# so ``ensure_bundled_content_sync`` re-imports it on the next login (after the
# cloud sync settles). Import is idempotent (stem-hash dedup), so a re-run only
# adds genuinely new questions.
#   1 = initial all-three-section import (Quant + Verbal + Data Insights)
#   2 = + deepened Quant bank (AQuA-RAT scrape, ~60/topic)
#   3 = re-apply reasonable exam-paced new/day limits (fix the "due today" flood)
GMAT_BUNDLED_CONTENT_VERSION = 3


def render_gmat_screen(mw: aqt.main.AnkiQt) -> None:
    """Render the GMATWiz app shell into the main window's central webview."""
    # NOTE: bundled-content import is NOT triggered here. It must run AFTER the
    # cloud collection sync settles on login (otherwise colReplace would clobber a
    # locally-imported bank with the older cloud copy), so the client drives it via
    # the gmatEnsureContent endpoint (see ensure_bundled_content_sync).
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


def _load_verbal_question_dicts() -> list[dict]:
    """Bundled Verbal (Critical Reasoning + Reading Comprehension)."""
    questions: list[dict] = []
    for name in ("verbal_seed.json", "verbal_questions.json", "verbal_rc_questions.json"):
        path = _content_dir() / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        questions.extend(anki.gmatwiz.flatten_verbal_items(data))
    return questions


def _load_di_question_dicts() -> list[dict]:
    """Bundled Data Insights (Data Sufficiency + Two-Part + Multi-Source)."""
    questions: list[dict] = []
    for name in ("di_seed.json", "di_questions.json"):
        path = _content_dir() / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        questions.extend(anki.gmatwiz.flatten_verbal_items(data))
    return questions


def _gmat_daily_new_target(col, deck_name: str, fallback: int = 15) -> int:
    """A REASONABLE new-cards-per-day for a GMAT deck, so importing the whole
    question bank doesn't dump every card in as "due today" at once (the cause of
    absurd multi-hour daily estimates). Paced from the exam date + weekly
    availability: introduce this deck's new cards evenly across the study days in
    the learn window (up to ~10 days before the exam), clamped to a sane range.
    Falls back to a fixed default when there's no exam date yet."""
    from datetime import date, datetime

    try:
        new_count = len(col.find_cards(f'deck:"{deck_name}" is:new'))
    except Exception:
        new_count = 0
    if new_count <= 0:
        return fallback
    profile = col.get_config("gmatProfile", {}) or {}
    exam_date = profile.get("exam_date", "") or ""
    days_per_week = int(profile.get("days_per_week", 5) or 5)
    if not exam_date:
        return min(fallback, new_count)
    try:
        days_to_exam = (
            datetime.strptime(exam_date, "%Y-%m-%d").date() - date.today()
        ).days
    except Exception:
        return min(fallback, new_count)
    learn_days = max(1, days_to_exam - 10)  # finish new intake ~10 days pre-exam
    study_days = max(1, round(learn_days * days_per_week / 7.0))
    per_day = round(new_count / study_days)
    return max(6, min(40, per_day))


def _ensure_generous_limits(col, deck_name: str = GMAT_DECK_NAME) -> None:
    """Give a GMAT deck its own preset with a REASONABLE, exam-paced new/day (see
    _gmat_daily_new_target) instead of Anki's fixed default - so the bulk-imported
    bank drips in over the run-up to the exam rather than all becoming due at once.
    Reviews stay uncapped (you should always clear what's actually due). Leaves the
    Default preset untouched. Idempotent."""
    deck_id = col.decks.id(deck_name)
    conf = col.decks.config_dict_for_deck_id(deck_id)
    if conf.get("name") == "Default":
        conf = col.decks.add_config("GMATWiz")
        deck = col.decks.get(deck_id)
        if deck is not None:
            deck["conf"] = conf["id"]
            col.decks.save(deck)
    conf["new"]["perDay"] = _gmat_daily_new_target(col, deck_name)
    conf["rev"]["perDay"] = 9999
    col.decks.update_config(conf)


def import_gmat_content(mw: aqt.main.AnkiQt) -> None:
    """Import the bundled GMAT Quant + Verbal questions into the collection."""
    questions = _load_question_dicts()
    verbal = _load_verbal_question_dicts()
    di = _load_di_question_dicts()
    if not questions and not verbal and not di:
        showInfo(
            f"No GMAT content found under {_content_dir()}.",
            parent=mw,
            title="GMATWiz",
        )
        return

    def op(col) -> OpChanges:
        requests = anki.gmatwiz.build_add_requests(col, questions, GMAT_DECK_NAME)
        if verbal:
            requests += anki.gmatwiz.build_verbal_add_requests(
                col, verbal, GMAT_VERBAL_DECK_NAME
            )
        if di:
            requests += anki.gmatwiz.build_di_add_requests(col, di, GMAT_DI_DECK_NAME)
        changes = col.add_notes(requests)
        _ensure_generous_limits(col, GMAT_DECK_NAME)
        if verbal:
            _ensure_generous_limits(col, GMAT_VERBAL_DECK_NAME)
        if di:
            _ensure_generous_limits(col, GMAT_DI_DECK_NAME)
        return changes

    def on_success(_out) -> None:
        tooltip(
            f"Imported {len(questions)} Quant + {len(verbal)} Verbal + {len(di)} "
            "Data Insights GMAT questions.",
            parent=mw,
        )
        if mw.state == "gmat":
            render_gmat_screen(mw)

    CollectionOp(parent=mw, op=op).success(on_success).run_in_background()


def ensure_bundled_content_sync(col) -> int:
    """Version-gated, SYNCHRONOUS import of the bundled GMAT content (all three
    sections) into `col`, so the collection has cards for the whole syllabus and
    coverage reflects Quant + Verbal + Data Insights. Returns the number of notes
    added (0 when already at the current version). Idempotent - stem-hash dedup
    skips anything already imported (e.g. an existing Quant bank).

    Runs INLINE (called from the gmatEnsureContent endpoint) rather than as a
    background op so the client can sequence it AFTER the cloud collection sync
    settles, then upload the result. Bumping GMAT_BUNDLED_CONTENT_VERSION makes it
    re-run once (pulling in only genuinely new questions)."""
    if col is None:
        return 0
    try:
        current = int(col.get_config("gmatContentVersion", 0) or 0)
    except Exception:
        current = 0
    if current >= GMAT_BUNDLED_CONTENT_VERSION:
        return 0

    questions = _load_question_dicts()
    verbal = _load_verbal_question_dicts()
    di = _load_di_question_dicts()
    if not (questions or verbal or di):
        return 0

    added = anki.gmatwiz.import_questions(col, questions, GMAT_DECK_NAME)
    added += anki.gmatwiz.import_verbal_questions(col, verbal, GMAT_VERBAL_DECK_NAME)
    added += anki.gmatwiz.import_di_questions(col, di, GMAT_DI_DECK_NAME)
    _ensure_generous_limits(col, GMAT_DECK_NAME)
    _ensure_generous_limits(col, GMAT_VERBAL_DECK_NAME)
    _ensure_generous_limits(col, GMAT_DI_DECK_NAME)
    # Record the version last so a mid-import failure retries next time.
    col.set_config("gmatContentVersion", GMAT_BUNDLED_CONTENT_VERSION)
    return added


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

    import_action = QAction("Import GMAT content", mw)
    qconnect(import_action.triggered, lambda: import_gmat_content(mw))
    menu.addAction(import_action)

    user_import_action = QAction("Import my questions\u2026", mw)
    qconnect(user_import_action.triggered, lambda: import_user_questions(mw))
    menu.addAction(user_import_action)

    gui_hooks.top_toolbar_did_init_links.append(_add_toolbar_link)
    gui_hooks.profile_did_open.append(_auto_open)
