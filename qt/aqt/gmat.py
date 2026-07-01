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
from aqt.qt import QAction, qconnect
from aqt.utils import showInfo, tooltip

GMAT_DECK_NAME = "GMAT::Quant"


def render_gmat_screen(mw: aqt.main.AnkiQt) -> None:
    """Render the GMATWiz app shell into the main window's central webview."""
    mw.web.load_sveltekit_page("gmat")
    mw.web.setFocus()
    # GMATWiz is a full screen; hide Anki's per-state bottom bar.
    mw.bottomWeb.hide()


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


def _add_toolbar_link(links: list, toolbar) -> None:
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

    gui_hooks.top_toolbar_did_init_links.append(_add_toolbar_link)
    gui_hooks.profile_did_open.append(_auto_open)
