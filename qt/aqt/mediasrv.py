# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import base64
import enum
import json
import logging
import mimetypes
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from errno import EPROTOTYPE
from http import HTTPStatus
from pathlib import Path

import flask
import stringcase
import waitress.wasyncore
from flask import Response, abort, request
from waitress.server import create_server

import aqt
import aqt.main
import aqt.operations
from anki import hooks
from anki.collection import OpChangesOnly, Progress, SearchNode
from anki.decks import UpdateDeckConfigs, UpdateDeckConfigsMode
from anki.scheduler.v3 import SchedulingStatesWithContext, SetSchedulingStatesRequest
from anki.utils import dev_mode
from aqt.changenotetype import ChangeNotetypeDialog
from aqt.deckoptions import DeckOptionsDialog
from aqt.operations import on_op_finished
from aqt.operations.deck import update_deck_configs as update_deck_configs_op
from aqt.progress import ProgressUpdate
from aqt.qt import *
from aqt.utils import aqt_data_path, show_warning, tr

# https://forums.ankiweb.net/t/anki-crash-when-using-a-specific-deck/22266
waitress.wasyncore._DISCONNECTED = waitress.wasyncore._DISCONNECTED.union({EPROTOTYPE})  # type: ignore

logger = logging.getLogger(__name__)
app = flask.Flask(__name__, root_path="/fake")


@dataclass
class LocalFileRequest:
    # base folder, eg media folder
    root: str
    # path to file relative to root folder
    path: str
    # collection media is untrusted user content; add-on web exports are not
    untrusted: bool = True


UNTRUSTED_MEDIA_CSP = "; ".join(
    (
        "default-src 'none'",
        "script-src 'none'",
        "connect-src 'none'",
        "object-src 'none'",
        "frame-src 'none'",
        "child-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "sandbox",
    )
)


def _editor_content_security_policy(port: int) -> str:
    csp_paths = (
        f"http://127.0.0.1:{port}/_anki/",
        f"http://127.0.0.1:{port}/_addons/",
    )
    return "; ".join((f"script-src {' '.join(csp_paths)}",))


@dataclass
class BundledFileRequest:
    # path relative to aqt data folder
    path: str


@dataclass
class NotFound:
    message: str


DynamicRequest = Callable[[], Response]


class PageContext(enum.IntEnum):
    UNKNOWN = enum.auto()
    EDITOR = enum.auto()
    REVIEWER = enum.auto()
    PREVIEWER = enum.auto()
    CARD_LAYOUT = enum.auto()
    DECK_OPTIONS = enum.auto()
    # something in /_anki/pages/
    NON_LEGACY_PAGE = enum.auto()
    # Do not use this if you present user content (e.g. content from cards), as it's a
    # security issue.
    ADDON_PAGE = enum.auto()


@dataclass
class LegacyPage:
    html: str
    context: PageContext


class MediaServer(threading.Thread):
    _ready = threading.Event()
    daemon = True

    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        super().__init__()
        self.is_shutdown = False
        # map of webview ids to pages
        self._legacy_pages: dict[int, LegacyPage] = {}

    def run(self) -> None:
        try:
            desired_host = os.getenv("ANKI_API_HOST", "127.0.0.1")
            desired_port = int(os.getenv("ANKI_API_PORT") or 0)
            self.server = create_server(
                app,
                host=desired_host,
                port=desired_port,
                clear_untrusted_proxy_headers=True,
            )
            logger.info(
                "Serving on http://%s:%s",
                self.server.effective_host,  # type: ignore[union-attr]
                self.server.effective_port,  # type: ignore[union-attr]
            )

            self._ready.set()
            self.server.run()

        except Exception:
            if not self.is_shutdown:
                raise

    def shutdown(self) -> None:
        self.is_shutdown = True
        sockets = list(self.server._map.values())  # type: ignore
        for socket in sockets:
            socket.handle_close()
        # https://github.com/Pylons/webtest/blob/4b8a3ebf984185ff4fefb31b4d0cf82682e1fcf7/webtest/http.py#L93-L104
        self.server.task_dispatcher.shutdown()

    def getPort(self) -> int:
        self._ready.wait()
        return int(self.server.effective_port)  # type: ignore

    def set_page_html(
        self, id: int, html: str, context: PageContext = PageContext.UNKNOWN
    ) -> None:
        self._legacy_pages[id] = LegacyPage(html, context)

    def get_page(self, id: int) -> LegacyPage | None:
        return self._legacy_pages.get(id)

    def get_page_html(self, id: int) -> str | None:
        if page := self.get_page(id):
            return page.html
        else:
            return None

    def get_page_context(self, id: int) -> PageContext | None:
        if page := self.get_page(id):
            return page.context
        else:
            return None

    def clear_page_html(self, id: int) -> None:
        try:
            del self._legacy_pages[id]
        except KeyError:
            pass


@app.route("/favicon.ico")
def favicon() -> Response:
    request = BundledFileRequest(os.path.join("imgs", "favicon.ico"))
    return _handle_builtin_file_request(request)


def _mime_for_path(path: str) -> str:
    "Mime type for provided path/filename."

    _, ext = os.path.splitext(path)
    ext = ext.lower()

    # Badly-behaved apps on Windows can alter the standard mime types in the registry, which can completely
    # break Anki's UI. So we hard-code the most common extensions.
    mime_types = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".html": "text/html",
        ".htm": "text/html",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".ico": "image/x-icon",
        ".json": "application/json",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".ogg": "audio/ogg",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }

    if mime := mime_types.get(ext):
        return mime
    else:
        # fallback to mimetypes, which may consult the registry
        mime, _encoding = mimetypes.guess_type(path)
        return mime or "application/octet-stream"


def _text_response(code: HTTPStatus, text: str) -> Response:
    """Return an error message.

    Response is returned as text/plain, so no escaping of untrusted
    input is required."""
    resp = flask.make_response(text, code)
    resp.headers["Content-type"] = "text/plain"
    return resp


class UnsafePathException(Exception):
    def __init__(self, path: str):
        super().__init__(f"Invalid path: {path}")


def ensure_safe_path(base_dir: str | Path, path: str | Path) -> str:
    base_dir = os.path.realpath(base_dir)
    path = os.path.normpath(path)
    fullpath = os.path.abspath(os.path.join(base_dir, path))

    # protect against directory traversal: https://security.openstack.org/guidelines/dg_using-file-paths.html
    if not fullpath.startswith(base_dir + os.sep):
        raise UnsafePathException(path)
    return fullpath


_LOCALHOST_HOSTS = ("127.0.0.1", "localhost", "[::1]")

_ALLOWED_ORIGIN_PREFIXES = tuple(
    f"{scheme}{host}" for scheme in ("http://", "https://") for host in _LOCALHOST_HOSTS
)


def is_localhost_origin(origin: str) -> bool:
    for prefix in _ALLOWED_ORIGIN_PREFIXES:
        if (
            origin == prefix
            or origin.startswith(prefix + ":")
            or origin.startswith(prefix + "/")
        ):
            return True
    return False


def _handle_local_file_request(request: LocalFileRequest) -> Response:
    directory = request.root
    path = request.path
    try:
        isdir = os.path.isdir(os.path.join(directory, path))
    except ValueError:
        return _text_response(
            HTTPStatus.BAD_REQUEST, f"Path for '{directory} - {path}' is too long!"
        )

    fullpath = ensure_safe_path(directory, path)

    if isdir:
        return _text_response(
            HTTPStatus.FORBIDDEN,
            f"Path for '{directory} - {path}' is a directory (not supported)!",
        )

    try:
        mimetype = _mime_for_path(fullpath)
        if os.path.exists(fullpath):
            if fullpath.endswith(".css"):
                # caching css files prevents flicker in the webview, but we want
                # a short cache
                max_age = 10
            elif fullpath.endswith(".js"):
                # don't cache js files
                max_age = 0
            else:
                max_age = 60 * 60
            response = flask.send_file(
                fullpath,
                mimetype=mimetype,
                conditional=True,
                max_age=max_age,
                download_name="foo",  # type: ignore[call-arg]
            )
            if request.untrusted:
                # Prevent user-provided HTML/SVG from running as an active document.
                response.headers["Content-Security-Policy"] = UNTRUSTED_MEDIA_CSP
            return response
        else:
            print(f"Not found: {path}")
            return _text_response(HTTPStatus.NOT_FOUND, f"Invalid path: {path}")

    except Exception as error:
        if dev_mode:
            print(
                "Caught HTTP server exception,\n%s"
                % "".join(traceback.format_exception(*sys.exc_info())),
            )

        # swallow it - user likely surfed away from
        # review screen before an image had finished
        # downloading
        return _text_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))


def _builtin_data(path: str) -> bytes:
    """Return data from file in aqt/data folder."""
    full_path = ensure_safe_path(aqt_data_path().parent, path)
    with open(full_path, "rb") as f:
        return f.read()


def _handle_builtin_file_request(request: BundledFileRequest) -> Response:
    path = request.path
    # do we need to serve the fallback page?
    immutable = "immutable" in path
    if path.startswith("sveltekit/") and not immutable:
        path = "sveltekit/index.html"
    mimetype = _mime_for_path(path)
    data_path = f"data/web/{path}"
    try:
        data = _builtin_data(data_path)
        response = Response(data, mimetype=mimetype)
        if immutable:
            response.headers["Cache-Control"] = "max-age=31536000"
        return response
    except FileNotFoundError:
        if dev_mode:
            print(f"404: {data_path}")
        resp = _text_response(HTTPStatus.NOT_FOUND, f"Invalid path: {path}")
        # we're including the path verbatim in our response, so we need to either use
        # plain text, or escape HTML characters to avoid reflecting untrusted input
        resp.headers["Content-type"] = "text/plain"
        return resp
    except Exception as error:
        if dev_mode:
            print(
                "Caught HTTP server exception,\n%s"
                % "".join(traceback.format_exception(*sys.exc_info())),
            )

        # swallow it - user likely surfed away from
        # review screen before an image had finished
        # downloading
        return _text_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))


@app.route("/<path:pathin>", methods=["GET", "POST"])
def handle_request(pathin: str) -> Response:
    if os.environ.get("ANKI_API_HOST") != "0.0.0.0":
        host = request.headers.get("Host", "").lower()
        origin = request.headers.get("Origin", "").lower()
        allowed_hosts = tuple(f"{h}:" for h in _LOCALHOST_HOSTS)
        if not any(host.startswith(h) for h in allowed_hosts):
            logger.warning("denied non-local host: %s", host)
            abort(403)
        if origin and not is_localhost_origin(origin):
            logger.warning("denied non-local origin: %s", origin)
            abort(403)

    req = _extract_request(pathin)
    logger.debug("%s /%s", flask.request.method, pathin)

    try:
        if isinstance(req, NotFound):
            print(req.message)
            return _text_response(HTTPStatus.NOT_FOUND, f"Invalid path: {pathin}")
        elif callable(req):
            return _handle_dynamic_request(req)
        elif isinstance(req, BundledFileRequest):
            return _handle_builtin_file_request(req)
        elif isinstance(req, LocalFileRequest):
            return _handle_local_file_request(req)
        else:
            return _text_response(HTTPStatus.FORBIDDEN, f"unexpected request: {pathin}")
    except UnsafePathException as exc:
        return _text_response(HTTPStatus.FORBIDDEN, str(exc))


def is_sveltekit_page(path: str) -> bool:
    page_name = path.split("/")[0]
    return page_name in [
        "graphs",
        "congrats",
        "card-info",
        "change-notetype",
        "deck-options",
        "import-anki-package",
        "import-csv",
        "import-page",
        "image-occlusion",
        "gmat-practice",
        "gmat",
    ]


def _extract_internal_request(
    path: str,
) -> BundledFileRequest | DynamicRequest | NotFound | None:
    "Catch /_anki references and rewrite them to web export folder."
    if is_sveltekit_page(path):
        path = f"_anki/sveltekit/_app/{path}"
    if path.startswith("_app/"):
        path = path.replace("_app", "_anki/sveltekit/_app")

    prefix = "_anki/"
    if not path.startswith(prefix):
        return None

    dirname = os.path.dirname(path)
    filename = os.path.basename(path)
    additional_prefix = None

    if dirname == "_anki":
        if flask.request.method == "POST":
            return _extract_collection_post_request(filename)
        elif get_handler := _extract_dynamic_get_request(filename):
            return get_handler

        # remap legacy top-level references
        base, ext = os.path.splitext(filename)
        if ext == ".css":
            additional_prefix = "css/"
        elif ext == ".js":
            if base in ("jquery-ui", "jquery", "plot"):
                additional_prefix = "js/vendor/"
            else:
                additional_prefix = "js/"
    # handle requests for vendored libraries
    elif dirname == "_anki/js/vendor":
        base, ext = os.path.splitext(filename)

        if base == "jquery":
            base = "jquery.min"
            additional_prefix = "js/vendor/"

        elif base == "jquery-ui":
            base = "jquery-ui.min"
            additional_prefix = "js/vendor/"

    if additional_prefix:
        oldpath = path
        path = f"{prefix}{additional_prefix}{base}{ext}"
        print(f"legacy {oldpath} remapped to {path}")

    return BundledFileRequest(path=path[len(prefix) :])


def _extract_addon_request(path: str) -> LocalFileRequest | NotFound | None:
    "Catch /_addons references and rewrite them to addons folder."
    prefix = "_addons/"
    if not path.startswith(prefix):
        return None

    addon_path = path[len(prefix) :]

    try:
        manager = aqt.mw.addonManager
    except AttributeError as error:
        if dev_mode:
            print(f"_redirectWebExports: {error}")
        return None

    try:
        addon, sub_path = addon_path.split("/", 1)
    except ValueError:
        return None
    if not addon:
        return None

    pattern = manager.getWebExports(addon)
    if not pattern:
        return None

    if re.fullmatch(pattern, sub_path):
        return LocalFileRequest(
            root=manager.addonsFolder(), path=addon_path, untrusted=False
        )

    return NotFound(message=f"couldn't locate item in add-on folder {path}")


def _extract_request(
    path: str,
) -> LocalFileRequest | BundledFileRequest | DynamicRequest | NotFound:
    if internal := _extract_internal_request(path):
        return internal
    elif addon := _extract_addon_request(path):
        return addon

    if not aqt.mw.col:
        return NotFound(message=f"collection not open, ignore request for {path}")

    path = hooks.media_file_filter(path)
    return LocalFileRequest(root=aqt.mw.col.media.dir(), path=path)


def congrats_info() -> bytes:
    if not aqt.mw.col.sched._is_finished():
        aqt.mw.taskman.run_on_main(lambda: aqt.mw.moveToState("overview"))
    return raw_backend_request("congrats_info")()


def get_deck_configs_for_update() -> bytes:
    return aqt.mw.col._backend.get_deck_configs_for_update_raw(request.data)


def _on_update_deck_configs_success(input: UpdateDeckConfigs) -> None:
    is_compute_all = (
        input.mode == UpdateDeckConfigsMode.UPDATE_DECK_CONFIGS_MODE_COMPUTE_ALL_PARAMS
    )
    if not is_compute_all and isinstance(
        window := aqt.mw.app.activeModalWidget(), DeckOptionsDialog
    ):
        window.reject()


def update_deck_configs() -> bytes:
    # the regular change tracking machinery expects to be started on the main
    # thread and uses a callback on success, so we need to run this op on
    # main, and return immediately from the web request

    input = UpdateDeckConfigs()
    input.ParseFromString(request.data)

    def on_progress(progress: Progress, update: ProgressUpdate) -> None:
        if progress.HasField("compute_memory"):
            val = progress.compute_memory
            update.max = val.total_cards
            update.value = val.current_cards
            update.label = val.label
        elif progress.HasField("compute_params"):
            val2 = progress.compute_params
            # prevent an indeterminate progress bar from appearing at the start of each preset
            update.max = max(val2.total, 1)
            update.value = val2.current
            pct = str(int(val2.current / val2.total * 100) if val2.total > 0 else 0)
            label = tr.deck_config_optimizing_preset(
                current_count=val2.current_preset, total_count=val2.total_presets
            )
            if val2.reviews:
                reviews = tr.deck_config_percent_of_reviews(
                    pct=pct, reviews=val2.reviews
                )
            else:
                reviews = tr.qt_misc_processing()

            update.label = label + "\n" + reviews
        else:
            return
        if update.user_wants_abort:
            update.abort = True

    def handle_on_main() -> None:
        update_deck_configs_op(parent=aqt.mw, input=input).success(
            lambda _: _on_update_deck_configs_success(input)
        ).with_backend_progress(on_progress).run_in_background()

    aqt.mw.taskman.run_on_main(handle_on_main)
    return b""


def get_scheduling_states_with_context() -> bytes:
    return SchedulingStatesWithContext(
        states=aqt.mw.reviewer.get_scheduling_states(),
        context=aqt.mw.reviewer.get_scheduling_context(),
    ).SerializeToString()


def set_scheduling_states() -> bytes:
    states = SetSchedulingStatesRequest()
    states.ParseFromString(request.data)
    aqt.mw.reviewer.set_scheduling_states(states)
    return b""


def import_done() -> bytes:
    def update_window_modality() -> None:
        if window := aqt.mw.app.activeModalWidget():
            from aqt.import_export.import_dialog import ImportDialog

            if isinstance(window, ImportDialog):
                window.hide()
                window.setWindowModality(Qt.WindowModality.NonModal)
                window.show()

    aqt.mw.taskman.run_on_main(update_window_modality)
    return b""


def import_request(endpoint: str) -> bytes:
    output = raw_backend_request(endpoint)()
    response = OpChangesOnly()
    response.ParseFromString(output)

    def handle_on_main() -> None:
        window = aqt.mw.app.activeModalWidget()
        on_op_finished(aqt.mw, response, window)

    aqt.mw.taskman.run_on_main(handle_on_main)

    return output


def import_csv() -> bytes:
    return import_request("import_csv")


def import_anki_package() -> bytes:
    return import_request("import_anki_package")


def import_json_file() -> bytes:
    return import_request("import_json_file")


def import_json_string() -> bytes:
    return import_request("import_json_string")


def search_in_browser() -> bytes:
    node = SearchNode()
    node.ParseFromString(request.data)

    def handle_on_main() -> None:
        aqt.dialogs.open("Browser", aqt.mw, search=(node,))

    aqt.mw.taskman.run_on_main(handle_on_main)

    return b""


def change_notetype() -> bytes:
    data = request.data

    def handle_on_main() -> None:
        window = aqt.mw.app.activeModalWidget()
        if isinstance(window, ChangeNotetypeDialog):
            window.save(data)

    aqt.mw.taskman.run_on_main(handle_on_main)
    return b""


def deck_options_require_close() -> bytes:
    def handle_on_main() -> None:
        window = aqt.mw.app.activeModalWidget()
        if isinstance(window, DeckOptionsDialog):
            window.require_close()

    # on certain linux systems, askUser's QMessageBox.question unsets the active window
    # so we wait for the next event loop before querying the next current active window
    aqt.mw.taskman.run_on_main(lambda: QTimer.singleShot(0, handle_on_main))
    return b""


def deck_options_ready() -> bytes:
    def handle_on_main() -> None:
        window = aqt.mw.app.activeModalWidget()
        if isinstance(window, DeckOptionsDialog):
            window.set_ready()

    aqt.mw.taskman.run_on_main(handle_on_main)
    return b""


def save_custom_colours() -> bytes:
    colors = [
        QColorDialog.customColor(i).name(QColor.NameFormat.HexRgb)
        for i in range(QColorDialog.customCount())
    ]
    aqt.mw.col.set_config("customColorPickerPalette", colors)
    return b""


def gmat_questions() -> bytes:
    """Return GMAT PS questions from the GMAT::Quant deck as JSON.

    Served at /_anki/gmatQuestions for the GMAT Practice page. Read-only.
    """
    col = aqt.mw.col
    questions = []
    try:
        note_ids = col.find_notes('note:"GMAT PS"')
    except Exception:
        note_ids = []
    for nid in note_ids:
        note = col.get_note(nid)
        fields = dict(note.items())
        questions.append(
            {
                "stem": fields.get("Stem", ""),
                "options": {
                    "A": fields.get("OptionA", ""),
                    "B": fields.get("OptionB", ""),
                    "C": fields.get("OptionC", ""),
                    "D": fields.get("OptionD", ""),
                    "E": fields.get("OptionE", ""),
                },
                "correct": fields.get("Correct", ""),
                "explanation": fields.get("Explanation", ""),
                "topic": fields.get("Topic", ""),
                "difficulty": fields.get("Difficulty", ""),
            }
        )
    return json.dumps({"questions": questions}).encode("utf-8")


# Number of leaf topics in the GMAT Focus Quant coverage map (PRD Section 5).
GMAT_QUANT_TOPIC_TOTAL = 18
# Verbal leaf topics: 9 Critical Reasoning + 7 Reading Comprehension = 16.
GMAT_VERBAL_TOPIC_TOTAL = 16
# Data Insights leaf topics (pragmatic MCQ scope): DS + Two-Part + Multi-Source.
GMAT_DI_TOPIC_TOTAL = 3


def _score_unavailable() -> dict:
    return {
        "status": "abstain",
        "reason": "Scores are temporarily unavailable.",
        "updated_ts": int(time.time()),
    }


def _gmat_scores(col) -> dict:
    """The three honest scores (Memory, Performance, Readiness) from the SHARED
    Rust engine - the single source of truth for desktop AND mobile, so the
    numbers and give-up abstentions can never drift between platforms. Degrades
    cleanly to abstention if the engine call fails, so reviews keep working.
    """
    total_topics = (
        GMAT_QUANT_TOPIC_TOTAL + GMAT_VERBAL_TOPIC_TOTAL + GMAT_DI_TOPIC_TOTAL
    )
    try:
        raw = col._backend.gmat_scores()
        data = json.loads(getattr(raw, "val", raw))
        # One Memory / Performance / Readiness, each carrying a by_section
        # breakdown (Quant / Verbal / DI); Readiness headline is the 205-805 Total.
        return {
            "memory": data.get("memory", _score_unavailable()),
            "performance": data.get("performance", _score_unavailable()),
            "readiness": data.get("readiness", _score_unavailable()),
            "topics_covered": data.get("topics_covered", 0),
            "topics_total": data.get("topics_total", total_topics),
        }
    except Exception as exc:
        print(f"GMATWiz: score engine unavailable: {exc}")
        return {
            "memory": _score_unavailable(),
            "performance": _score_unavailable(),
            "readiness": _score_unavailable(),
            "topics_covered": 0,
            "topics_total": total_topics,
        }


def _ensure_gmat_time_cap(col) -> None:
    """Raise the GMAT deck's answer-time cap (default 60s) so slow answers are
    stored truthfully in the revlog - timing analytics need to see 3-minute
    struggles, not a clamped 60s. Idempotent."""
    try:
        conf = col.decks.config_dict_for_deck_id(col.decks.id("GMAT::Quant"))
        if int(conf.get("maxTaken", 60)) < 300:
            conf["maxTaken"] = 300
            col.decks.update_config(conf)
    except Exception as exc:
        print(f"GMATWiz: could not raise answer-time cap: {exc}")


def gmat_overview() -> bytes:
    """Headline stats for the GMATWiz home + dashboard (honesty rule)."""
    col = aqt.mw.col
    _ensure_gmat_time_cap(col)
    try:
        total = len(col.find_cards('note:"GMAT PS"'))
        new = len(col.find_cards('note:"GMAT PS" is:new'))
        due = len(col.find_cards('note:"GMAT PS" (is:due OR is:learn)'))
    except Exception:
        total = new = due = 0

    reviews = col.db.scalar("select count() from revlog") or 0
    scores = _gmat_scores(col)

    return json.dumps(
        {
            "deck": "GMAT::Quant",
            "total": total,
            "new": new,
            "due": due,
            "reviews": reviews,
            "topics_covered": scores["topics_covered"],
            "topics_total": scores["topics_total"],
            "memory": scores["memory"],
            "performance": scores["performance"],
            "readiness": scores["readiness"],
            "profile": col.get_config("gmatProfile", None),
            "plan": col.get_config("gmatPlan", None),
            "planVerbal": col.get_config("gmatPlanVerbal", None),
            "planDI": col.get_config("gmatPlanDI", None),
            # null when never set on any device, so the app can tell "unset" from
            # an explicit off and let synced config win over the local override.
            "gmatAiEnabled": col.get_config("gmatAiEnabled", None),
        }
    ).encode("utf-8")


def gmat_error_log() -> bytes:
    """Return the student's logged errors (most recent first)."""
    col = aqt.mw.col
    entries = col.get_config("gmatErrorLog", []) or []
    return json.dumps({"entries": list(reversed(entries))}).encode("utf-8")


def _gmat_append_error(col, entry: dict) -> None:
    entries = col.get_config("gmatErrorLog", []) or []
    entries.append(entry)
    col.set_config("gmatErrorLog", entries[-500:])


def _gmat_record_application(col, topic: str, correct: bool, ms: int) -> None:
    """Log one assessment answer (topic quiz / milestone) as an APPLICATION
    attempt. These never touch the scheduler/revlog, so the Performance reader
    (rslib `gmat_performance_json`) folds this synced log in alongside revlog
    first-exposure attempts - keeping the honesty thresholds evidence-based."""
    log = col.get_config("gmatApplication", []) or []
    log.append(
        {
            "ts": int(time.time()),
            "topic": str(topic or ""),
            "correct": bool(correct),
            "ms": int(ms or 0),
        }
    )
    col.set_config("gmatApplication", log[-2000:])


def _gmat_apply_repair(col, topic: str, why: str) -> None:
    """Turn a classified miss into scheduled remediation (Brainlift: every
    wrong, slow, or guessed question is a future scheduled learning event).

    - concept_gap: an extra mastery penalty (a misunderstanding is worse than a
      slip), make sure the topic's lesson items are in the review queue, and
      queue the topic for a "Repair" block in Today (relearn the lesson).
    - timing: mark the topic for timed-drill focus in Today's practice.
    - guess: the scheduler recorded Good, but the student didn't know it -
      counter the EMA update so mastery reflects reality.
    - careless: logged for the record; FSRS's Again already resurfaces the card.
    """
    if not topic:
        return
    now = int(time.time())
    if why == "concept_gap":
        _gmat_update_mastery(col, topic, False)
        try:
            _schedule_lesson_items(col, topic)
        except Exception as exc:
            print(f"GMATWiz: repair scheduling failed for {topic}: {exc}")
        repairs = col.get_config("gmatRepairTopics", {}) or {}
        repairs[topic] = now
        col.set_config("gmatRepairTopics", repairs)
    elif why == "timing":
        drills = col.get_config("gmatTimedDrill", {}) or {}
        drills[topic] = now
        col.set_config("gmatTimedDrill", drills)
    elif why == "guess":
        _gmat_update_mastery(col, topic, False)


def gmat_log_error() -> bytes:
    """Append a missed (or guessed) question to the error log and schedule its
    repair. Body: JSON entry with optional why/ms/guess/mock/options/explanation."""
    col = aqt.mw.col
    try:
        entry = json.loads(request.data or b"{}")
    except Exception:
        entry = {}
    topic = str(entry.get("topic", ""))
    why = str(entry.get("why", ""))
    record: dict = {
        "stem": str(entry.get("stem", ""))[:400],
        "topic": topic,
        "chosen": str(entry.get("chosen", "")),
        "correct": str(entry.get("correct", "")),
        "why": why,
        "ms": int(entry.get("ms", 0) or 0),
        "mock": bool(entry.get("mock", False)),
        "ts": int(time.time()),
    }
    options = entry.get("options")
    if isinstance(options, dict):
        record["options"] = {str(k): str(v) for k, v in options.items()}
    explanation = entry.get("explanation")
    if explanation:
        record["explanation"] = str(explanation)[:2000]
    _gmat_append_error(col, record)
    _gmat_apply_repair(col, topic, why)
    return b""


def gmat_set_error_takeaway() -> bytes:
    """Attach a cached AI coach takeaway to an existing error-log entry."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        return b""
    ts = int(body.get("ts", 0) or 0)
    takeaway = body.get("takeaway")
    if not ts or takeaway is None:
        return b""
    entries = col.get_config("gmatErrorLog", []) or []
    for entry in entries:
        if int(entry.get("ts", 0)) == ts:
            entry["ai_takeaway"] = takeaway
            col.set_config("gmatErrorLog", entries)
            break
    return b""


def gmat_next_card() -> bytes:
    """Return the next scheduled GMAT card from the REAL scheduler.

    Selecting the GMAT deck and calling get_queued_cards means the topic-aware
    ordering and daily limits from the engine apply. Read-only.
    """
    from anki.cards import Card

    col = aqt.mw.col
    section = _gmat_req_section()
    deck_id = col.decks.id(_gmat_deck_for_section(section))
    if col.decks.get_current_id() != deck_id:
        col.decks.select(deck_id)
    queued = col.sched.get_queued_cards(fetch_limit=1)
    counts = {
        "new": queued.new_count,
        "learning": queued.learning_count,
        "review": queued.review_count,
    }
    if not queued.cards:
        return json.dumps({"card": None, "counts": counts}).encode("utf-8")
    card = Card(col)
    card._load_from_backend_card(queued.cards[0].card)
    fields = dict(card.note().items())
    return json.dumps(
        {
            "card": {
                "card_id": card.id,
                "stem": fields.get("Stem", ""),
                "options": {k: fields.get(f"Option{k}", "") for k in "ABCDE"},
                "correct": fields.get("Correct", ""),
                "explanation": fields.get("Explanation", ""),
                "topic": fields.get("Topic", ""),
                "difficulty": fields.get("Difficulty", ""),
                "passage": fields.get("Passage", ""),
            },
            "counts": counts,
        }
    ).encode("utf-8")


def gmat_answer_card() -> bytes:
    """Record an answer to the current GMAT card through the real scheduler.

    Maps a correct MCQ answer to Good and an incorrect one to Again, so a real
    revlog entry is written and FSRS reschedules the card.
    """
    from anki.scheduler.v3 import CardAnswer
    from anki.utils import int_time

    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    card_id = int(body.get("card_id", 0))
    correct = bool(body.get("correct", False))
    ms = int(body.get("ms", 0))

    _sec_raw = str(body.get("section") or "")
    section = _sec_raw if _sec_raw in ("verbal", "di") else "quant"
    deck_id = col.decks.id(_gmat_deck_for_section(section))
    if col.decks.get_current_id() != deck_id:
        col.decks.select(deck_id)
    # Answer the SPECIFIED card even when it isn't the very top of the queue, so
    # front-loaded AI cards (served out of scheduler order in Drill) still record
    # a real review. Fall back to a no-op if the card isn't in the queue window.
    queued = col.sched.get_queued_cards(fetch_limit=200)
    match = next((qc for qc in queued.cards if qc.card.id == card_id), None)
    if match is None:
        return b""
    states = match.states
    answer = CardAnswer(
        card_id=card_id,
        current_state=states.current,
        new_state=states.good if correct else states.again,
        rating=CardAnswer.GOOD if correct else CardAnswer.AGAIN,
        answered_at_millis=int_time(1000),
        milliseconds_taken=ms,
    )
    col.sched.answer_card(answer)
    # Living plan: let ongoing performance move the topic's mastery so the plan
    # and topic-aware scheduling keep re-adapting (not just the one diagnostic).
    _gmat_update_mastery(col, _gmat_topic_of_card(col, card_id), correct)
    return b""


# EMA weight for how much one fresh answer moves a topic's mastery.
GMAT_MASTERY_ALPHA = 0.3
# Assessment answers (topic quiz / milestone) move mastery HARDER than a single
# drill: they are deliberate, timed checks, so one carries more signal.
GMAT_QUIZ_MASTERY_ALPHA = 0.5
# Soft mastery gate (PRD assessment layer): a topic is "mastered" once its quiz
# history has >= 2 passing sessions (accuracy >= the pass bar) on >= 2 distinct
# days - proof it stuck, not a one-day fluke.
GMAT_QUIZ_PASS_ACCURACY = 0.85
GMAT_QUIZ_PASS_SESSIONS = 2
GMAT_QUIZ_PASS_DISTINCT_DAYS = 2
# Topic-quiz length (single topic) and the spacing before a passed-once topic is
# re-quizzed to confirm it stuck on a distinct day. 7 (not 6) so a single miss
# still clears the 85% bar: 6/7 = 85.7% >= 0.85, where 5/6 = 83.3% would fail.
GMAT_QUIZ_N = 7
GMAT_QUIZ_RESPACE_SECS = 3 * 86400


def _gmat_status(mastery: float) -> str:
    return "weak" if mastery < 0.5 else ("developing" if mastery < 0.8 else "strong")


def _gmat_mastery_bar(target_score: int) -> float:
    """Per-topic mastery a student must reach, derived from their target GMAT
    Focus total. Higher goals demand deeper mastery before a topic is 'done'."""
    if target_score >= 705:
        return 0.90
    if target_score >= 645:
        return 0.85
    if target_score >= 585:
        return 0.80
    return 0.72


def _gmat_topic_of_card(col, card_id: int) -> str:
    try:
        note = col.get_card(card_id).note()
        return dict(note.items()).get("Topic", "") or ""
    except Exception:
        return ""


def _gmat_update_mastery(
    col, topic: str, correct: bool, alpha: float = GMAT_MASTERY_ALPHA
) -> None:
    """EMA-update one topic's mastery from a single practice answer and keep the
    stored plan + topic-aware scheduling in sync. No-op until a plan exists.

    `alpha` is the EMA weight: the default (0.3) suits ordinary drills; the
    assessment layer passes a stronger weight (0.5) for deliberate quiz/milestone
    answers. This drives the plan display + topic-aware order; the hard mastery
    GATE is quiz-history based (see `_gmat_topic_mastered`)."""
    if not topic or not col.get_config("gmatPlan", None):
        return
    diagnosis = col.get_config("gmatDiagnosis", {}) or {}
    old = diagnosis.get(topic)
    old = 0.5 if old is None else float(old)
    new = round(
        (1 - alpha) * old + alpha * (1.0 if correct else 0.0),
        3,
    )
    diagnosis[topic] = new
    col.set_config("gmatDiagnosis", diagnosis)
    try:
        col._backend.set_topic_mastery(topic=topic, mastery=new)
    except Exception as exc:
        print(f"set_topic_mastery failed for {topic}: {exc}")
    plan = col.get_config("gmatPlan", None)
    if plan and isinstance(plan.get("topics"), list):
        for entry in plan["topics"]:
            if entry.get("topic") == topic:
                entry["mastery"] = new
                entry["status"] = _gmat_status(new)
                break
        else:
            plan["topics"].append(
                {"topic": topic, "mastery": new, "status": _gmat_status(new)}
            )
        plan["topics"].sort(key=lambda e: e.get("mastery", 0.5))
        col.set_config("gmatPlan", plan)


def _gmat_day_bucket(col) -> int:
    """Absolute day index from the scheduler's day cutoff - constant within an
    Anki day, +1 each rollover. Used to stamp quiz sessions so the mastery gate
    can require passes on DISTINCT days."""
    try:
        return int(col.sched.day_cutoff) // 86400
    except Exception:
        return int(time.time()) // 86400


def _gmat_topic_mastered(col, topic: str) -> bool:
    """The SOFT mastery gate: True once the topic's quiz history proves it stuck
    - at least GMAT_QUIZ_PASS_SESSIONS passing sessions (accuracy >= the pass
    bar) spread over at least GMAT_QUIZ_PASS_DISTINCT_DAYS distinct days. This is
    the single definition of 'mastered' that pacing + Today + Study read; the
    EMA `gmatDiagnosis` value is only the display/scheduling signal."""
    if not topic:
        return False
    quizzes = col.get_config("gmatQuizzes", {}) or {}
    sessions = quizzes.get(topic, []) or []
    passing = [s for s in sessions if float(s.get("accuracy", 0) or 0) >= GMAT_QUIZ_PASS_ACCURACY]
    if len(passing) < GMAT_QUIZ_PASS_SESSIONS:
        return False
    distinct_days = {int(s.get("day", 0) or 0) for s in passing}
    return len(distinct_days) >= GMAT_QUIZ_PASS_DISTINCT_DAYS


def _gmat_notetype_for_section(section: str) -> str:
    return {"verbal": "GMAT Verbal", "di": "GMAT DI"}.get(section, "GMAT PS")


def _gmat_deck_for_section(section: str) -> str:
    return {"verbal": "GMAT::Verbal", "di": "GMAT::DI"}.get(section, "GMAT::Quant")


def _gmat_section_of_topic(topic: str) -> str:
    """Section ('quant' | 'verbal' | 'di') for a leaf topic id, 2nd segment."""
    parts = (topic or "").split("::")
    if len(parts) >= 2 and parts[1] in ("verbal", "di"):
        return parts[1]
    return "quant"


def _gmat_notes_by_topic(section: str = "quant") -> dict:
    from collections import defaultdict

    col = aqt.mw.col
    by_topic: dict = defaultdict(list)
    notetype = _gmat_notetype_for_section(section)
    for nid in col.find_notes(f'note:"{notetype}"'):
        fields = dict(col.get_note(nid).items())
        topic = fields.get("Topic", "")
        if topic:
            by_topic[topic].append(fields)
    return by_topic


def _gmat_content_dir() -> str:
    # qt/aqt/mediasrv.py -> aqt -> qt -> repo root; content at gmatwiz/content.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "gmatwiz", "content")


def _gmat_pool_by_topic(section: str = "quant") -> dict:
    """Notes grouped by topic for a section, falling back to the bundled content
    files when the collection has no notes for that section yet (mirrors the Rust
    engine's seed fallback on a fresh phone)."""
    from collections import defaultdict

    by_topic = _gmat_notes_by_topic(section)
    if by_topic:
        return by_topic
    # Bundled fallback per section (mirrors the Rust engine's seed fallback on a
    # fresh phone), so verbal/DI still render before notes are imported.
    section_files = {
        "verbal": ("verbal_seed.json", "verbal_questions.json", "verbal_rc_questions.json"),
        "di": ("di_seed.json", "di_questions.json"),
    }
    if section not in section_files:
        return by_topic
    import anki.gmatwiz

    fallback: dict = defaultdict(list)
    for name in section_files[section]:
        path = os.path.join(_gmat_content_dir(), name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        for q in anki.gmatwiz.flatten_verbal_items(data):
            topic = str(q.get("topic", ""))
            if not topic:
                continue
            fallback[topic].append(
                {
                    "Stem": q.get("stem", ""),
                    "OptionA": (q.get("options") or {}).get("A", ""),
                    "OptionB": (q.get("options") or {}).get("B", ""),
                    "OptionC": (q.get("options") or {}).get("C", ""),
                    "OptionD": (q.get("options") or {}).get("D", ""),
                    "OptionE": (q.get("options") or {}).get("E", ""),
                    "Correct": q.get("correct", ""),
                    "Topic": topic,
                    "Difficulty": q.get("difficulty", ""),
                    "Passage": q.get("passage", "") or "",
                }
            )
    return fallback


def gmat_save_profile() -> bytes:
    """Store the student's exam date + weekly availability."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    target_score = max(205, min(805, int(body.get("target_score", 645) or 645)))
    profile = {
        "exam_date": str(body.get("exam_date", "")),
        "days_per_week": int(body.get("days_per_week", 5) or 5),
        "target_score": target_score,
    }
    col.set_config("gmatProfile", profile)
    # Profile can be set/changed AFTER the diagnostics (gated onboarding), so
    # rebuild every section plan that already has a diagnosis, giving the new
    # exam date / weekly availability its pacing across all three tracks.
    for sec, plan_key, diag_key in (
        ("quant", "gmatPlan", "gmatDiagnosis"),
        ("verbal", "gmatPlanVerbal", "gmatDiagnosisVerbal"),
        ("di", "gmatPlanDI", "gmatDiagnosisDI"),
    ):
        diag = col.get_config(diag_key, None)
        if diag:
            col.set_config(plan_key, _gmat_build_section_plan(col, diag, sec))
    # Re-pace each existing section deck's daily new-card intake to the (possibly
    # new) exam date, so the daily session stays reasonable.
    try:
        import aqt.gmat

        for deck in ("GMAT::Quant", "GMAT::Verbal", "GMAT::DI"):
            if col.decks.id_for_name(deck) is not None:
                aqt.gmat._ensure_generous_limits(col, deck)
    except Exception as exc:
        print(f"GMATWiz: re-pace deck limits failed: {exc}")
    return b""


def gmat_ensure_content() -> bytes:
    """Import the bundled GMAT content (all three sections) into the collection if
    it is behind the current content version. Idempotent (stem-hash dedup). The
    CLIENT calls this AFTER the cloud collection sync settles, then uploads if
    anything changed - so a fresh device gets the full syllabus without the sync
    clobbering it. Returns {"imported": n, "changed": bool}."""
    import aqt.gmat

    try:
        added = aqt.gmat.ensure_bundled_content_sync(aqt.mw.col)
    except Exception as exc:
        print(f"GMATWiz: ensure content failed: {exc}")
        added = 0
    return json.dumps({"imported": added, "changed": added > 0}).encode("utf-8")


def gmat_set_ai_enabled() -> bytes:
    """Persist the AI on/off choice to synced config (mirrors the client's
    localStorage override) so it follows the account across devices. Body:
    {"enabled": bool}."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    col.set_config("gmatAiEnabled", bool(body.get("enabled", False)))
    return json.dumps({"ok": True}).encode("utf-8")


def gmat_open_stats() -> bytes:
    """Open Anki's full statistics screen (the complete SRS graphs). Runs on the
    main GUI thread. GMATWiz surfaces a focused summary; this is the deep dive."""
    aqt.mw.taskman.run_on_main(aqt.mw.onStats)
    return b""


def gmat_open_decks() -> bytes:
    """Switch to Anki's deck browser - the free-study escape hatch (PRD)."""
    aqt.mw.taskman.run_on_main(lambda: aqt.mw.moveToState("deckBrowser"))
    return b""


# Desktop sync target defaults - match the phone app (ios/ContentView.swift) so
# desktop <-> phone sync through the same self-hosted GMATWiz server with no
# Preferences setup. Overridable via col config (gmatSyncEndpoint/User/Pass).
GMAT_SYNC_ENDPOINT = "http://127.0.0.1:27811/"
GMAT_SYNC_USER = "gmat"
GMAT_SYNC_PASS = "wiz"


def gmat_sync_now() -> bytes:
    """Trigger Anki's collection sync. On first use (no sync configured), point
    the desktop at the self-hosted GMATWiz server and log in automatically, so
    the Sync button 'just works' desktop<->phone without touching Preferences.
    If the user has already configured sync (e.g. AnkiWeb), we respect it."""
    col = aqt.mw.col
    endpoint = col.get_config("gmatSyncEndpoint", None) or GMAT_SYNC_ENDPOINT
    user = col.get_config("gmatSyncUser", None) or GMAT_SYNC_USER
    password = col.get_config("gmatSyncPass", None) or GMAT_SYNC_PASS

    # Log in off the GUI thread only if nothing is configured yet.
    if aqt.mw.pm.sync_auth() is None:
        try:
            auth = col.sync_login(user, password, endpoint)
            aqt.mw.pm.set_custom_sync_url(endpoint)
            aqt.mw.pm.set_sync_key(auth.hkey)
            aqt.mw.pm.set_sync_username(user)
        except Exception as exc:
            print(f"GMATWiz: auto sync-login failed ({exc}); is the server running?")

    aqt.mw.taskman.run_on_main(aqt.mw.on_sync_button_clicked)
    return b""


def gmat_stats() -> bytes:
    """A focused, GMAT-scoped activity summary for the in-app Progress view:
    today's work, streak, the review pipeline, and a 7-day due forecast. Computed
    from the collection (read-only); the full Anki graphs are one click away."""
    col = aqt.mw.col
    base = 'note:"GMAT PS"'

    def count(query: str) -> int:
        try:
            return len(col.find_cards(query))
        except Exception:
            return 0

    model = col.models.by_name("GMAT PS")
    if model is None:
        return json.dumps({"has_data": False}).encode("utf-8")
    mid = model["id"]
    scope = "cid in (select id from cards where nid in " "(select id from notes where mid=?))"

    try:
        cutoff = int(col.sched.day_cutoff)
    except Exception:
        cutoff = int(time.time())
    start_today = (cutoff - 86400) * 1000

    reviews_today = (
        col.db.scalar(
            f"select count() from revlog where id>=? and {scope}", start_today, mid
        )
        or 0
    )
    time_today_ms = (
        col.db.scalar(
            f"select coalesce(sum(time),0) from revlog where id>=? and {scope}",
            start_today,
            mid,
        )
        or 0
    )
    reviews_total = col.db.scalar(f"select count() from revlog where {scope}", mid) or 0

    # study streak: consecutive days (ending today or yesterday) with a review
    day_indices = set(
        col.db.list(
            f"select distinct cast((?-id/1000)/86400 as int) from revlog where {scope}",
            cutoff,
            mid,
        )
        or []
    )
    streak = 0
    i = 0 if 0 in day_indices else 1
    while i in day_indices:
        streak += 1
        i += 1

    # 7-day review sparkline (6 days ago .. today) and due forecast (today .. +6)
    spark = []
    for d in range(6, -1, -1):
        s = (cutoff - (d + 1) * 86400) * 1000
        e = (cutoff - d * 86400) * 1000
        spark.append(
            col.db.scalar(
                f"select count() from revlog where id>=? and id<? and {scope}", s, e, mid
            )
            or 0
        )
    forecast = [count(f"{base} -is:suspended prop:due={d}") for d in range(7)]

    return json.dumps(
        {
            "has_data": True,
            "reviews_today": reviews_today,
            "time_today_min": round(time_today_ms / 60000),
            "reviews_total": reviews_total,
            "streak": streak,
            "due_today": count(f"{base} is:due"),
            "forecast": forecast,
            "spark": spark,
            "pipeline": {
                "new": count(f"{base} is:new"),
                "learning": count(f"{base} is:learn"),
                "young": count(f"{base} -is:new -is:suspended prop:ivl>=1 prop:ivl<21"),
                "mature": count(f"{base} prop:ivl>=21"),
                "total": count(base),
            },
        }
    ).encode("utf-8")


# GMATWiz per-user state that syncs across devices (config JSON only; the SRS
# card/revlog state is not part of this Firestore state-sync).
GMAT_STATE_KEYS = [
    "gmatProfile",
    "gmatPlan",
    "gmatDiagnosis",
    "gmatMocks",
    "gmatOfficialScores",
    "gmatLearned",
    "gmatErrorLog",
    "gmatRepairTopics",
    "gmatTimedDrill",
    "gmatLessonScheduled",
    "gmatTestsTaken",
    "gmatAiEnabled",
    # 3-tier assessment layer: per-topic quiz session history (the mastery
    # gate) and the application-attempt log the Performance reader folds in
    # (quiz/milestone answers, which never touch the scheduler/revlog).
    "gmatQuizzes",
    "gmatApplication",
]


def gmat_export_state() -> bytes:
    """All GMATWiz per-user state (config JSON) for cross-device sync."""
    col = aqt.mw.col
    state = {k: col.get_config(k, None) for k in GMAT_STATE_KEYS}
    state["topicAwareScheduling"] = bool(col.get_config("topicAwareScheduling", False))
    return json.dumps({"state": state}).encode("utf-8")


def gmat_import_state() -> bytes:
    """Apply a synced state blob to this collection's config."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    state = body.get("state", {}) or {}
    for key in GMAT_STATE_KEYS:
        if state.get(key) is not None:
            col.set_config(key, state[key])
    if "topicAwareScheduling" in state:
        col.set_config("topicAwareScheduling", bool(state["topicAwareScheduling"]))
    return json.dumps({"ok": True}).encode("utf-8")


def gmat_reset_state() -> bytes:
    """Clear GMATWiz state so a new account starts at the diagnostic."""
    col = aqt.mw.col
    for key in GMAT_STATE_KEYS:
        try:
            col.remove_config(key)
        except Exception:
            col.set_config(key, None)
    col.set_config("topicAwareScheduling", False)
    return json.dumps({"ok": True}).encode("utf-8")


# ---- whole-collection Cloud Storage sync (desktop side) --------------------
#
# On top of the Firestore config sync above, the web/mobile layer keeps the
# ENTIRE collection FILE (cards + revlog = the full SRS state) in sync through
# Firebase Cloud Storage, so desktop and phone share one complete schedule. It
# drives three endpoints implemented here (iOS implements the same paths
# natively):
#   gmatColMeta    -> {"mod": <col.mod ms>}           last-writer-wins clock
#   gmatColExport  -> {"b64": "<base64 .anki2>"}       a CONSISTENT snapshot
#   gmatColReplace {"b64": "..."} -> {"ok": true}      back up + atomic swap
# Closing/replacing/reopening the collection may only happen on the GUI thread,
# but these handlers run on a media-server worker thread, so we hop to the main
# thread and block for the result.


def _run_on_main_and_wait(func: "Callable[[], object]") -> object:
    """Run func on the GUI (main) thread and block the calling worker thread
    until it finishes, propagating the return value or the exception it raised."""
    if threading.current_thread() is threading.main_thread():
        return func()
    done = threading.Event()
    box: dict = {}

    def wrapper() -> None:
        try:
            box["result"] = func()
        except BaseException as exc:  # re-raised on the caller thread below
            box["error"] = exc
        finally:
            done.set()

    aqt.mw.taskman.run_on_main(wrapper)
    done.wait()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def _silent_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _reopen_collection(col, path: str, backup: str) -> None:
    """Reopen the collection at path. If the freshly-swapped file won't open,
    restore the local backup and open that instead, so the app is never left
    without a collection. Reload the scheduler so it matches the (new) file."""
    try:
        col.reopen(after_full_sync=False)
    except Exception:
        try:
            if os.path.exists(backup):
                shutil.copy2(backup, path)
        except Exception:
            pass
        col.reopen(after_full_sync=False)
    try:
        col._load_scheduler()
    except Exception:
        pass


def gmat_col_meta() -> bytes:
    """The open collection's modification time in ms (Anki's col.mod). The Cloud
    Storage layer compares this against the remote object's stored col_mod to do
    last-writer-wins whole-collection sync."""
    col = aqt.mw.col
    try:
        mod = int(col.mod)
    except Exception:
        mod = int(col.db.scalar("select mod from col") or 0)
    return json.dumps({"mod": mod}).encode("utf-8")


def gmat_col_export() -> bytes:
    """A CONSISTENT base64 snapshot of the whole .anki2 file, produced on the GUI
    thread WITHOUT closing the live collection: fold the WAL back into the main
    db (wal_checkpoint TRUNCATE), copy the file to a temp path, then base64 it."""

    def snapshot() -> bytes:
        col = aqt.mw.col
        path = col.path
        # Fold any WAL frames into the main db so a plain file copy is a
        # complete, standalone snapshot (best-effort - the copy is valid either
        # way, this just avoids relying on sidecar files).
        try:
            col.db.execute("pragma wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        fd, tmp = tempfile.mkstemp(suffix=".anki2", dir=os.path.dirname(path))
        os.close(fd)
        try:
            shutil.copyfile(path, tmp)
            with open(tmp, "rb") as fh:
                return fh.read()
        finally:
            _silent_remove(tmp)

    data = _run_on_main_and_wait(snapshot)
    b64 = base64.b64encode(data).decode("ascii")
    return json.dumps({"b64": b64}).encode("utf-8")


def gmat_col_replace() -> bytes:
    """Replace the whole collection with an uploaded base64 .anki2 (a newer copy
    pulled from Cloud Storage). On the GUI thread: stage the incoming bytes on
    the same filesystem, close the collection, COPY the current file to
    <path>.bak-<ts> (never silently discard the overwritten data), drop stale
    WAL/SHM sidecars, atomically swap the new file in, then reopen + refresh.
    The collection is always reopened - and if the new file won't open, the
    local backup is restored - so the app is never left without a collection."""
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    try:
        new_bytes = base64.b64decode(body.get("b64") or "")
    except Exception:
        new_bytes = b""
    if not new_bytes:
        return json.dumps({"ok": False, "error": "empty payload"}).encode("utf-8")

    def replace() -> None:
        col = aqt.mw.col
        path = col.path
        folder = os.path.dirname(path)

        # 1) stage the incoming bytes next to the collection (same filesystem)
        #    so the final swap can be an atomic os.replace.
        fd, staged = tempfile.mkstemp(suffix=".anki2.new", dir=folder)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(new_bytes)
        except Exception:
            _silent_remove(staged)
            raise

        backup = f"{path}.bak-{int(time.time() * 1000)}"

        # 2) close so the file is unlocked, then swap under a guaranteed reopen.
        col.close(downgrade=False)
        try:
            if os.path.exists(path):
                shutil.copy2(path, backup)  # keep the overwritten copy recoverable
            # a leftover WAL/SHM from the OLD db would corrupt the new file.
            _silent_remove(path + "-wal")
            _silent_remove(path + "-shm")
            os.replace(staged, path)  # atomic on the same filesystem
        except Exception:
            _silent_remove(staged)
            # if we never got as far as writing the new file, restore the backup
            # so we reopen the original rather than a missing/half-written file.
            try:
                if not os.path.exists(path) and os.path.exists(backup):
                    shutil.copy2(backup, path)
            except Exception:
                pass
            raise
        finally:
            _reopen_collection(col, path, backup)

        try:
            aqt.mw.reset()  # refresh the GUI/webview against the new collection
        except Exception:
            pass

    _run_on_main_and_wait(replace)
    return json.dumps({"ok": True}).encode("utf-8")


def gmat_official_scores() -> bytes:
    """Return the user's logged official/practice-test scores (most recent first)."""
    col = aqt.mw.col
    scores = col.get_config("gmatOfficialScores", []) or []
    return json.dumps({"scores": list(reversed(scores))}).encode("utf-8")


def _gmat_current_projection(col) -> int | None:
    """The app's current RAW Quant projection (heuristic, pre-calibration), so a
    newly logged official score can be compared like-for-like."""
    try:
        readiness = _gmat_scores(col).get("readiness", {})
        if readiness.get("status") == "shown":
            return int(readiness.get("point"))
    except Exception as exc:
        print(f"GMATWiz: could not snapshot projection: {exc}")
    return None


def gmat_save_official_score() -> bytes:
    """Log a real practice-test score as calibration ground truth. Snapshots the
    app's current projection so the engine can measure its bias. Body: JSON with
    quant (60-90) and optional total/verbal/di/date."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    try:
        quant = int(body.get("quant", 0) or 0)
    except (TypeError, ValueError):
        quant = 0
    if not (60 <= quant <= 90):
        return json.dumps({"ok": False, "error": "Quant must be 60-90."}).encode("utf-8")

    def opt_int(key: str) -> int | None:
        try:
            v = int(body.get(key))
            return v
        except (TypeError, ValueError):
            return None

    entry = {
        "ts": int(time.time()),
        "date": str(body.get("date", "")),
        "quant": quant,
        "total": opt_int("total"),
        "verbal": opt_int("verbal"),
        "di": opt_int("di"),
        "projected_at_entry": _gmat_current_projection(col),
    }
    scores = col.get_config("gmatOfficialScores", []) or []
    scores.append(entry)
    col.set_config("gmatOfficialScores", scores[-50:])
    return json.dumps({"ok": True, "entry": entry}).encode("utf-8")


def _gmat_req_section() -> str:
    """Read the target section ('quant' | 'verbal') from the request; default quant."""
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    sec = str(body.get("section") or request.args.get("section") or "quant").lower()
    return sec if sec in ("verbal", "di") else "quant"


def gmat_pretest_questions() -> bytes:
    """Return a short diagnostic sampled across a section's topics.

    Section ('quant' | 'verbal' | 'di') and an optional `count` (default 12,
    clamped [6, 30]) are read from the request. One item per topic first, then
    filled at random up to `count`.
    """
    import random

    section = _gmat_req_section()
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    count = int(body.get("count") or request.args.get("count") or 12)
    count = max(6, min(30, count))
    by_topic = _gmat_pool_by_topic(section)
    picked: list = []
    seen: set = set()
    for notes in by_topic.values():
        choice = random.choice(notes)
        picked.append(choice)
        seen.add(id(choice))
    all_notes = [n for notes in by_topic.values() for n in notes]
    random.shuffle(all_notes)
    for note in all_notes:
        if len(picked) >= count:
            break
        if id(note) not in seen:
            picked.append(note)
            seen.add(id(note))
    picked = picked[:count]
    random.shuffle(picked)
    questions = [
        {
            "stem": f.get("Stem", ""),
            "options": {k: f.get(f"Option{k}", "") for k in "ABCDE"},
            "correct": f.get("Correct", ""),
            "topic": f.get("Topic", ""),
            "difficulty": f.get("Difficulty", ""),
            "passage": f.get("Passage", ""),
        }
        for f in picked
    ]
    return json.dumps({"questions": questions, "seconds": 45 * 60}).encode("utf-8")


def _gmat_build_section_plan(col, diagnosis: dict, section: str) -> dict:
    """Build a section plan dict from a topic->mastery diagnosis + the CURRENT
    profile (exam date / days-per-week / target). Pure: writes no config, so it
    can be reused both at diagnostic-submit time and when the profile changes
    (the profile is set AFTER the three diagnostics in the gated onboarding)."""
    from datetime import date, datetime

    def status(m: float) -> str:
        return "weak" if m < 0.5 else ("developing" if m < 0.8 else "strong")

    profile = col.get_config("gmatProfile", {}) or {}
    days_to_exam = None
    exam_date = profile.get("exam_date", "")
    if exam_date:
        try:
            days_to_exam = (
                datetime.strptime(exam_date, "%Y-%m-%d").date() - date.today()
            ).days
        except Exception:
            days_to_exam = None
    ranked = sorted(diagnosis.items(), key=lambda kv: kv[1])
    target_score = max(205, min(805, int(profile.get("target_score", 645) or 645)))
    return {
        "topics": [
            {"topic": t, "mastery": m, "status": status(m)} for t, m in ranked
        ],
        "days_per_week": int(profile.get("days_per_week", 5) or 5),
        "days_to_exam": days_to_exam,
        "created_ts": int(time.time()),
        "target_score": target_score,
        "mastery_bar": _gmat_mastery_bar(target_score),
        "section": section,
    }


def gmat_submit_pretest() -> bytes:
    """Turn diagnostic results into per-topic mastery + a study plan.

    Sets each topic's mastery via the Rust RPC (activating topic-aware
    scheduling), enables the toggle, and stores diagnosis + plan in config.
    """
    from collections import defaultdict
    from datetime import date, datetime

    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    results = body.get("results", []) or []
    section = _gmat_req_section()

    agg: dict = defaultdict(lambda: [0, 0])  # topic -> [correct, total]
    for r in results:
        topic = str(r.get("topic", ""))
        if not topic:
            continue
        agg[topic][1] += 1
        if r.get("correct"):
            agg[topic][0] += 1

    diagnosis: dict = {}
    for topic in _gmat_pool_by_topic(section).keys():
        correct, total = agg.get(topic, [0, 0])
        mastery = (correct / total) if total > 0 else 0.5
        diagnosis[topic] = round(mastery, 3)
        try:
            col._backend.set_topic_mastery(topic=topic, mastery=mastery)
        except Exception as exc:
            print(f"set_topic_mastery failed for {topic}: {exc}")

    # Now that mastery is populated, turn on topic-aware scheduling.
    col.set_config("topicAwareScheduling", True)

    plan = _gmat_build_section_plan(col, diagnosis, section)
    # Quant keeps the original config keys; Verbal + DI are parallel tracks.
    diag_key = {"verbal": "gmatDiagnosisVerbal", "di": "gmatDiagnosisDI"}.get(
        section, "gmatDiagnosis"
    )
    plan_key = {"verbal": "gmatPlanVerbal", "di": "gmatPlanDI"}.get(section, "gmatPlan")
    col.set_config(diag_key, diagnosis)
    col.set_config(plan_key, plan)
    return json.dumps({"diagnosis": diagnosis, "plan": plan, "section": section}).encode("utf-8")


def _gmat_pacing(col) -> dict:
    """Dated pacing + on/behind-track from profile + plan + learned progress.

    GOAL-DRIVEN: every lesson must be finished at least 10 calendar days before
    the exam (a HARD boundary), leaving the final 10 days for review + mocks.
    Lessons are paced across the study days that fall inside that learn window.
    A very late or dire start (already inside the last 10 days, or too many
    topics for the window) flips `late_start` and paces across ALL remaining
    study days instead, so lessons still get scheduled - even into the last 10.
    'behind_by' compares topics learned against the count you should have learned
    by today on an even pace from plan-creation to the exam-minus-10 deadline.
    """
    from datetime import date, datetime

    plan = col.get_config("gmatPlan", None) or {}
    profile = col.get_config("gmatProfile", {}) or {}
    topics = plan.get("topics", []) or []
    topic_ids = {t.get("topic") for t in topics}
    topics_total = len(topics)
    # "Learned" now means MASTERED (passed the topic quiz gate), NOT merely
    # lesson-done: a finished lesson without passing quizzes is still in
    # progress and counts toward remaining. This keeps pacing honest about how
    # much real competence is banked.
    topics_learned = len([t for t in topic_ids if t and _gmat_topic_mastered(col, t)])
    topics_remaining = max(0, topics_total - topics_learned)
    days_per_week = int(plan.get("days_per_week", profile.get("days_per_week", 5)) or 5)

    out = {
        "status": "no_pacing",
        "days_to_exam": None,
        "topics_total": topics_total,
        "topics_learned": topics_learned,
        "topics_remaining": topics_remaining,
        "behind_by": 0,
        "topics_per_study_day": 0.0,
        "study_days_remaining": None,
        "late_start": False,
    }

    exam_date = profile.get("exam_date", "") or ""
    if not topics_total or not exam_date:
        return out
    try:
        exam = datetime.strptime(exam_date, "%Y-%m-%d").date()
    except Exception:
        return out

    today = date.today()
    days_to_exam = (exam - today).days
    out["days_to_exam"] = days_to_exam
    study_days_remaining = max(0, round(max(0, days_to_exam) * days_per_week / 7.0))
    out["study_days_remaining"] = study_days_remaining

    if topics_remaining == 0:
        out["status"] = "learning_complete"
        return out

    # HARD BOUNDARY: finish every lesson >= 10 calendar days before the exam.
    learn_calendar_days = max(0, days_to_exam - 10)
    learn_days_remaining = round(learn_calendar_days * days_per_week / 7.0)
    if topics_remaining and learn_calendar_days > 0:
        learn_days_remaining = max(1, learn_days_remaining)

    # LATE-START EXCEPTION: already inside the final 10 days, or the learn window
    # is too tight to fit the remaining topics at a sane pace (~<=2 topics/study
    # day) -> pace across ALL remaining study days so lessons still get scheduled.
    late_start = False
    if learn_calendar_days <= 0 or (
        learn_days_remaining > 0 and topics_remaining / learn_days_remaining > 2.0
    ):
        late_start = True
        learn_days_remaining = study_days_remaining
        if topics_remaining and days_to_exam > 0:
            learn_days_remaining = max(1, learn_days_remaining)
    out["late_start"] = late_start

    out["topics_per_study_day"] = (
        round(topics_remaining / learn_days_remaining, 2)
        if learn_days_remaining
        else float(topics_remaining)
    )

    # expected progress by today: linear from plan creation to the exam-minus-10
    # deadline (the hard lessons-finish-by date), day-of-week cancels in the ratio
    created_ts = plan.get("created_ts")
    behind = 0
    if created_ts:
        created = date.fromtimestamp(created_ts)
        total_days = max(1, (exam - created).days - 10)
        elapsed = max(0, (today - created).days)
        frac = min(1.0, elapsed / total_days)
        expected_learned = round(topics_total * frac)
        behind = max(0, expected_learned - topics_learned)
    out["behind_by"] = behind
    out["status"] = "behind" if behind > 0 else "on_track"
    return out


# rough per-item minute costs used to size the daily session
_REVIEW_MIN = 1.5
_LESSON_MIN = 12.0
_PRACTICE_MIN = 2.0
# a short topic quiz (~6 timed questions) and a milestone checkpoint (~12-15)
_QUIZ_MIN = 8.0
_MILESTONE_MIN = 25.0


def gmat_today() -> bytes:
    """Assemble today's session: due reviews + next lesson(s) + weak practice,
    sized to the daily-minute budget, with on/behind-track pacing. Read-only."""
    try:
        data = _gmat_build_today(aqt.mw.col)
    except Exception as exc:
        print(f"GMATWiz: today unavailable: {exc}")
        data = {"has_plan": False, "pacing": None, "blocks": [], "daily_minutes": 0}
    return json.dumps(data).encode("utf-8")


def _gmat_build_today(col) -> dict:
    plan = col.get_config("gmatPlan", None)
    if not plan:
        return {"has_plan": False, "pacing": None, "blocks": [], "daily_minutes": 0}

    pacing = _gmat_pacing(col)
    learned = col.get_config("gmatLearned", {}) or {}
    topics = plan.get("topics", []) or []

    # due today, honoring the engine's daily limits + topic-aware order
    deck_id = col.decks.id("GMAT::Quant")
    if col.decks.get_current_id() != deck_id:
        col.decks.select(deck_id)
    queued = col.sched.get_queued_cards(fetch_limit=1)
    due_total = queued.new_count + queued.learning_count + queued.review_count

    # DERIVED daily budget (no longer user-set): enough room for today's paced
    # lessons + the due reviews + slack. It only sizes block-filling here; the
    # RETURNED daily_minutes is the sum of the blocks actually added below.
    reviews_est = round(due_total * _REVIEW_MIN) if due_total > 0 else 0
    topics_per_day = round(pacing.get("topics_per_study_day", 0) or 0)
    budget = float(max(30, topics_per_day * _LESSON_MIN + reviews_est + 20))

    # which weak topics have an authored lesson (so "Learn" links resolve)
    lesson_ids = {
        t.get("topic_id") for t in _load_lessons_index().get("topics", [])
    }

    blocks: list = []
    remaining_min = budget

    if due_total > 0:
        est = round(due_total * _REVIEW_MIN)
        blocks.append(
            {
                "kind": "review",
                "title": "Spaced review",
                "detail": f"{due_total} question(s) due today",
                "count": due_total,
                "est_minutes": est,
            }
        )
        remaining_min -= est

    # repair first: relearn topics whose misses were classified "concept gap"
    # (error log -> repair loop). Entries expire after 14 days.
    now_ts = int(time.time())
    repairs = {
        t: ts
        for t, ts in (col.get_config("gmatRepairTopics", {}) or {}).items()
        if now_ts - ts < 14 * 86400 and t in lesson_ids
    }
    for topic in list(repairs)[:2]:
        if remaining_min < _LESSON_MIN and blocks:
            break
        blocks.append(
            {
                "kind": "repair",
                "title": "Repair a concept gap",
                "detail": "you missed this on a concept - relearn, then re-apply",
                "topic": topic,
                "est_minutes": round(_LESSON_MIN),
            }
        )
        remaining_min -= _LESSON_MIN

    # next unlearned topics to learn today, weakest-first, paced
    lessons_target = max(1, round(pacing.get("topics_per_study_day", 0) or 0))
    to_learn = [
        t for t in topics
        if t.get("topic") not in learned and t.get("topic") in lesson_ids
    ]
    for entry in to_learn[:lessons_target]:
        if remaining_min < _LESSON_MIN and blocks:
            break
        blocks.append(
            {
                "kind": "learn",
                "title": "Learn a weak topic",
                "detail": _gmat_status(float(entry.get("mastery", 0.5)))
                + " · learn it before drilling",
                "topic": entry.get("topic"),
                "est_minutes": round(_LESSON_MIN),
            }
        )
        remaining_min -= _LESSON_MIN

    # TOPIC QUIZ (soft mastery gate): a lesson-done topic that isn't mastered yet
    # gets a short timed quiz to prove it. One passing session needs a spaced
    # re-quiz (>= 3 days later, distinct day) to reach the 2-pass gate; a recent
    # single pass waits for that spacing instead of re-quizzing today.
    quizzes_cfg = col.get_config("gmatQuizzes", {}) or {}
    quiz_topics: list = []
    for t in topics:
        tid = t.get("topic")
        if not tid or tid not in learned or tid not in lesson_ids:
            continue
        if _gmat_topic_mastered(col, tid):
            continue
        sessions = quizzes_cfg.get(tid, []) or []
        passing = [
            s for s in sessions
            if float(s.get("accuracy", 0) or 0) >= GMAT_QUIZ_PASS_ACCURACY
        ]
        if not passing:
            quiz_topics.append((tid, False))
        else:
            last_pass = max(int(s.get("ts", 0) or 0) for s in passing)
            if now_ts - last_pass >= GMAT_QUIZ_RESPACE_SECS:
                quiz_topics.append((tid, True))
    for tid, spaced in quiz_topics[:2]:
        if remaining_min < _QUIZ_MIN and blocks:
            break
        blocks.append(
            {
                "kind": "quiz",
                "title": "Topic quiz (spaced)" if spaced else "Topic quiz",
                "detail": (
                    f"confirm {topic_leaf(tid)} stuck - re-quiz to master"
                    if spaced
                    else f"prove {topic_leaf(tid)} - {GMAT_QUIZ_N} questions, timed"
                ),
                "topic": tid,
                "count": GMAT_QUIZ_N,
                "est_minutes": round(_QUIZ_MIN),
            }
        )
        remaining_min -= _QUIZ_MIN

    # fill the rest of the budget with targeted practice on the weakest learned topic
    learned_topics = [t for t in topics if t.get("topic") in learned]
    if remaining_min >= _PRACTICE_MIN and (learned_topics or due_total == 0):
        n = max(1, min(20, int(remaining_min // _PRACTICE_MIN)))
        weak = learned_topics[0] if learned_topics else (topics[0] if topics else None)
        drills = {
            t: ts
            for t, ts in (col.get_config("gmatTimedDrill", {}) or {}).items()
            if now_ts - ts < 14 * 86400
        }
        detail = (
            f"{n} extra on {topic_leaf(weak.get('topic'))}"
            if weak
            else f"{n} extra questions"
        )
        if drills:
            detail += f" · timed focus: {topic_leaf(next(iter(drills)))} (~2:08/q)"
        blocks.append(
            {
                "kind": "practice",
                "title": "Targeted practice",
                "detail": detail,
                "count": n,
                "topic": weak.get("topic") if weak else None,
                "est_minutes": round(n * _PRACTICE_MIN),
            }
        )

    # ONE timed test per day, chosen by priority: practice-test form > milestone
    # checkpoint > adaptive mock. gmatMocks now also holds milestone entries
    # (kind:"milestone"), so the practice-test/adaptive-mock cadence reads only
    # NON-milestone entries to stay exactly as before, while the milestone has
    # its own weekly cadence. The "already tested today" guard keeps it to one.
    mocks = col.get_config("gmatMocks", []) or []
    non_milestone = [m for m in mocks if m.get("kind") != "milestone"]
    milestone_mocks = [m for m in mocks if m.get("kind") == "milestone"]
    last_mock_ts = non_milestone[-1].get("ts", 0) if non_milestone else 0
    last_milestone_ts = milestone_mocks[-1].get("ts", 0) if milestone_mocks else 0
    try:
        _cutoff = int(col.sched.day_cutoff)
    except Exception:
        _cutoff = now_ts
    today_start_ts = _cutoff - 86400
    taken_timed_today = any(int(m.get("ts", 0) or 0) >= today_start_ts for m in mocks)

    days_to_exam = pacing.get("days_to_exam")
    learned_count = int(pacing.get("topics_learned") or 0)
    total = int(pacing.get("topics_total") or 0)
    # count of lesson-done topics (there's a pool to draw a milestone from)
    lesson_done_count = len([t for t in topics if t.get("topic") in learned])
    learning_ok = pacing.get("status") == "learning_complete" or (
        total > 0 and learned_count / total >= GMAT_TEST_MIN_LEARNED_FRAC
    )
    near_exam = days_to_exam is not None and days_to_exam <= GMAT_TEST_EXAM_WINDOW_DAYS

    timed_block = None
    # 1) practice-test form (unchanged cadence, near the exam)
    if days_to_exam is not None:
        next_form = _gmat_next_untaken_test(col)
        if next_form is not None:
            if days_to_exam <= 14:
                cadence_days = 4
            elif days_to_exam <= 21:
                cadence_days = 7
            else:
                cadence_days = 10
            if (
                (now_ts - last_mock_ts) > cadence_days * 86400
                and near_exam
                and learning_ok
            ):
                timed_block = {
                    "kind": "mock",
                    "title": "Practice test",
                    "detail": f"{next_form['label']} - 21 questions, timed",
                    "form_id": next_form["id"],
                    "label": next_form["label"],
                    "est_minutes": 45,
                }

    # 2) milestone checkpoint: roughly weekly once several topics are learned
    if timed_block is None and lesson_done_count >= GMAT_MILESTONE_MIN_TOPICS:
        milestone_due = (now_ts - last_milestone_ts) > 7 * 86400
        if milestone_due:
            timed_block = {
                "kind": "milestone",
                "title": "Milestone test",
                "detail": f"{GMAT_MILESTONE_N} questions, mixed across learned topics · timed",
                "count": GMAT_MILESTONE_N,
                "est_minutes": round(_MILESTONE_MIN),
            }

    # 3) adaptive mock section (existing fallback)
    if timed_block is None:
        mock_due = (
            pacing.get("status") == "learning_complete"
            or (
                days_to_exam is not None
                and days_to_exam <= 21
                and learning_ok
            )
        ) and (now_ts - last_mock_ts) > 7 * 86400
        if mock_due:
            timed_block = {
                "kind": "mock",
                "title": "Timed mock section",
                "detail": "21 questions · 45:00 · exam conditions, no feedback until the end",
                "count": 21,
                "est_minutes": 45,
            }

    if timed_block is not None and not taken_timed_today:
        blocks.append(timed_block)

    # Tag the Quant blocks, then append the additive Verbal track (when the user
    # has taken the Verbal diagnostic). Verbal is best-effort so a failure there
    # never breaks the Quant session.
    for b in blocks:
        b.setdefault("section", "quant")
    for sec in ("verbal", "di"):
        try:
            blocks.extend(_gmat_section_today_blocks(col, now_ts, sec))
        except Exception as exc:
            print(f"GMATWiz: {sec} today blocks unavailable: {exc}")

    return {
        "has_plan": True,
        "pacing": pacing,
        "blocks": blocks,
        "daily_minutes": sum(int(b.get("est_minutes", 0)) for b in blocks),
    }


def _gmat_section_today_blocks(col, now_ts: int, section: str) -> list:
    """The additive Verbal / Data Insights portion of Today for one section:
    spaced review, one lesson, one topic quiz, and targeted practice - each tagged
    with `section` so the client routes execution to the right deck / pool. Returns
    [] when the student hasn't taken that section's diagnostic yet."""
    plan_key = {"verbal": "gmatPlanVerbal", "di": "gmatPlanDI"}.get(section)
    if not plan_key:
        return []
    plan = col.get_config(plan_key, None)
    if not plan:
        return []
    label = "Data Insights" if section == "di" else "Verbal"
    deck = _gmat_deck_for_section(section)
    prefix = f"gmat::{section}"
    learned = col.get_config("gmatLearned", {}) or {}
    topics = plan.get("topics", []) or []
    lesson_ids = {
        t.get("topic_id")
        for t in _load_lessons_index().get("topics", [])
        if str(t.get("topic_id", "")).startswith(prefix)
    }
    blocks: list = []

    # spaced review (due from the section deck, topic-aware order)
    due_total = 0
    try:
        deck_id = col.decks.id(deck)
        if col.decks.get_current_id() != deck_id:
            col.decks.select(deck_id)
        queued = col.sched.get_queued_cards(fetch_limit=1)
        due_total = queued.new_count + queued.learning_count + queued.review_count
    except Exception:
        due_total = 0
    if due_total > 0:
        blocks.append(
            {
                "kind": "review",
                "section": section,
                "title": f"{label} spaced review",
                "detail": f"{due_total} question(s) due today",
                "count": due_total,
                "est_minutes": round(due_total * _REVIEW_MIN),
            }
        )

    # learn the weakest unlearned topic that has an authored lesson
    to_learn = [
        t for t in topics
        if t.get("topic") not in learned and t.get("topic") in lesson_ids
    ]
    if to_learn:
        entry = to_learn[0]
        blocks.append(
            {
                "kind": "learn",
                "section": section,
                "title": f"Learn a {label} topic",
                "detail": _gmat_status(float(entry.get("mastery", 0.5))) + f" · {label}",
                "topic": entry.get("topic"),
                "est_minutes": round(_LESSON_MIN),
            }
        )

    # one topic quiz for a lesson-done, not-yet-mastered topic
    quizzes_cfg = col.get_config("gmatQuizzes", {}) or {}
    for t in topics:
        tid = t.get("topic")
        if not tid or tid not in learned or tid not in lesson_ids:
            continue
        if _gmat_topic_mastered(col, tid):
            continue
        sessions = quizzes_cfg.get(tid, []) or []
        passing = [
            s for s in sessions
            if float(s.get("accuracy", 0) or 0) >= GMAT_QUIZ_PASS_ACCURACY
        ]
        spaced = False
        if passing:
            last_pass = max(int(s.get("ts", 0) or 0) for s in passing)
            if now_ts - last_pass < GMAT_QUIZ_RESPACE_SECS:
                continue
            spaced = True
        blocks.append(
            {
                "kind": "quiz",
                "section": section,
                "title": f"{label} quiz (spaced)" if spaced else f"{label} quiz",
                "detail": f"prove {topic_leaf(tid)} - {GMAT_QUIZ_N} questions, timed",
                "topic": tid,
                "count": GMAT_QUIZ_N,
                "est_minutes": round(_QUIZ_MIN),
            }
        )
        break

    # targeted practice on the weakest learned topic
    learned_topics = [t for t in topics if t.get("topic") in learned]
    if learned_topics:
        weak = learned_topics[0]
        n = 10
        blocks.append(
            {
                "kind": "practice",
                "section": section,
                "title": f"{label} targeted practice",
                "detail": f"{n} on {topic_leaf(weak.get('topic'))}",
                "count": n,
                "topic": weak.get("topic"),
                "est_minutes": round(n * _PRACTICE_MIN),
            }
        )

    return blocks


# --- forward study calendar (Progress tab) -----------------------------------
# A tentative day-by-day projection from today through the exam. Everything is
# DERIVED from the CURRENT plan/mastery/learned/quiz state, so each fetch
# recalibrates: mastering a topic drops it from the remaining set (fewer
# lessons, an earlier finish, more consolidation days); completing tomorrow's
# lesson early shifts the same state the Today builder reads. It parallels
# `_gmat_pacing` + `_gmat_build_today` (same 10-day hard boundary, late_start,
# topics-weakest-first, per-item minute costs), never a separate schedule.
_PRACTICE_TEST_MIN = 45.0
# nominal drill fill (questions) on a non-lesson study day -> minutes via _PRACTICE_MIN
_CAL_DRILL_N = 8
# how far ahead to project at most (guards a pathological far-future exam date)
_CAL_MAX_DAYS = 370
# practice-test spacing (calendar days) in the final stretch - the near-exam
# cadence from the Today builder (days_to_exam <= 14 -> every 4 days)
_CAL_TEST_CADENCE = 4


def _gmat_cal_review_min(learned: int) -> int:
    """Nominal spaced-review minutes for a projected study day, growing with how
    many topics are learned by then (more banked -> more cards in rotation).
    Reuses the Today per-review cost (_REVIEW_MIN); ~3 due cards per learned
    topic, capped so no day balloons."""
    nominal_due = min(30, 3 * learned + 2)
    return round(_REVIEW_MIN * nominal_due)


def gmat_calendar() -> bytes:
    """A tentative day-by-day study calendar from today through the exam. Read-only
    and derived from current state (recalibrates on every fetch). Returns
    {"days": []} when there's no plan/exam date (the UI shows an empty state)."""
    try:
        data = _gmat_build_calendar(aqt.mw.col)
    except Exception as exc:
        print(f"GMATWiz: calendar unavailable: {exc}")
        data = {
            "exam_date": "",
            "days_to_exam": None,
            "generated_ts": int(time.time()),
            "study_days": 0,
            "lessons_finish_date": None,
            "days": [],
        }
    return json.dumps(data).encode("utf-8")


def _gmat_build_calendar(col) -> dict:
    from collections import defaultdict
    from datetime import date, datetime, timedelta

    now_ts = int(time.time())
    empty = {
        "exam_date": "",
        "days_to_exam": None,
        "generated_ts": now_ts,
        "study_days": 0,
        "lessons_finish_date": None,
        "days": [],
    }
    plan = col.get_config("gmatPlan", None)
    profile = col.get_config("gmatProfile", {}) or {}
    if not plan:
        return empty
    exam_date = profile.get("exam_date", "") or ""
    if not exam_date:
        return empty
    try:
        exam = datetime.strptime(exam_date, "%Y-%m-%d").date()
    except Exception:
        return empty

    today = date.today()
    days_to_exam = (exam - today).days
    if days_to_exam < 0:
        # exam already passed: nothing to project forward
        return {**empty, "exam_date": exam_date, "days_to_exam": days_to_exam}

    pacing = _gmat_pacing(col)
    days_per_week = max(
        1, min(7, int(plan.get("days_per_week", profile.get("days_per_week", 5)) or 5))
    )
    late_start = bool(pacing.get("late_start"))

    # DERIVED from current mastery + learned state (so each fetch recalibrates):
    # remaining = UN-MASTERED topics weakest-first (plan.topics is already sorted;
    # the quiz-history gate is the single "mastered" definition). A topic that is
    # already lesson-done ("learned") but not yet mastered projects its mastery
    # quizzes only - no fresh lesson - exactly like the Today builder, so pulling
    # a lesson forward (jump-ahead) turns its future slot from lesson -> quiz.
    learned_cfg = col.get_config("gmatLearned", {}) or {}
    learned_ids = set(learned_cfg.keys()) if isinstance(learned_cfg, dict) else set()
    topics = plan.get("topics", []) or []
    remaining = [
        t.get("topic")
        for t in topics
        if t.get("topic") and not _gmat_topic_mastered(col, t.get("topic"))
    ]
    # lesson-done topics count toward "learned" for review scaling + the milestone
    # gate (mirrors the Today builder's lesson_done_count)
    lesson_done_start = sum(1 for t in topics if t.get("topic") in learned_ids)

    WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    # HARD boundary: lessons must finish by exam-10; the last 10 days are the
    # tests-only "final" stretch. Negative when we're already inside it (late).
    final_start = days_to_exam - 10

    def is_study(off: int) -> bool:
        # deterministic: the first `days_per_week` days of each rolling 7-day
        # block from today are study days
        return (off % 7) < days_per_week

    def next_study(off: int) -> "int | None":
        o = off + 1
        while o < days_to_exam:
            if is_study(o):
                return o
            o += 1
        return None

    def study_at_least(off: int) -> "int | None":
        o = max(0, off)
        while o < days_to_exam:
            if is_study(o):
                return o
            o += 1
        return None

    # eligible study days for placing lessons: the learn window, unless a late
    # start pushes lessons across ALL remaining study days (mirrors pacing)
    eligible = [
        o
        for o in range(0, days_to_exam)
        if is_study(o) and (late_start or o < final_start)
    ]

    lessons_by: dict = defaultdict(list)
    quizzes_by: dict = defaultdict(list)
    requizzes_by: dict = defaultdict(list)

    # spread the remaining topics EVENLY across the eligible study days (spacing
    # ~= eligible/remaining, i.e. ~topics_per_study_day/day on average). A
    # not-yet-taught topic gets a lesson, a quiz the next study day, and a spaced
    # re-quiz ~3 days on; an already-taught (learned) topic skips the lesson and
    # just gets its quiz + spaced re-quiz.
    respace_days = GMAT_QUIZ_RESPACE_SECS // 86400
    r = len(remaining)
    e = len(eligible)
    if r > 0 and e > 0:
        for k in range(r):
            di = min(e - 1, (k * e) // r)
            o = eligible[di]
            topic = remaining[k]
            if topic in learned_ids:
                quizzes_by[o].append(topic)
                rq_off = study_at_least(o + respace_days)
                if rq_off is not None:
                    requizzes_by[rq_off].append(topic)
            else:
                lessons_by[o].append(topic)
                q_off = next_study(o)
                if q_off is not None:
                    quizzes_by[q_off].append(topic)
                    rq_off = study_at_least(q_off + respace_days)
                    if rq_off is not None:
                        requizzes_by[rq_off].append(topic)

    last_lesson_off = max(lessons_by.keys()) if lessons_by else -1

    # --- Verbal + Data Insights (additive): project each section's un-mastered
    # topics across the SAME eligible study days, interleaved with Quant. Display-
    # only (the calendar is a tentative projection); each item is tagged with its
    # section so the UI can style/label it.
    sec_proj: dict = {}
    for sec in ("verbal", "di"):
        plan_s = col.get_config(
            {"verbal": "gmatPlanVerbal", "di": "gmatPlanDI"}[sec], None
        )
        s_lessons: dict = defaultdict(list)
        s_quizzes: dict = defaultdict(list)
        s_requizzes: dict = defaultdict(list)
        if plan_s:
            remaining_s = [
                t.get("topic")
                for t in (plan_s.get("topics", []) or [])
                if t.get("topic") and not _gmat_topic_mastered(col, t.get("topic"))
            ]
            rs = len(remaining_s)
            if rs > 0 and e > 0:
                for k in range(rs):
                    idx = min(e - 1, (k * e) // rs)
                    o = eligible[idx]
                    topic = remaining_s[k]
                    if topic in learned_ids:
                        s_quizzes[o].append(topic)
                        rq = study_at_least(o + respace_days)
                        if rq is not None:
                            s_requizzes[rq].append(topic)
                    else:
                        s_lessons[o].append(topic)
                        q_off = next_study(o)
                        if q_off is not None:
                            s_quizzes[q_off].append(topic)
                            rq = study_at_least(q_off + respace_days)
                            if rq is not None:
                                s_requizzes[rq].append(topic)
        if s_lessons:
            last_lesson_off = max([last_lesson_off, *s_lessons.keys()])
        sec_proj[sec] = (s_lessons, s_quizzes, s_requizzes)

    # cumulative topics learned by each offset (already lesson-done + lessons
    # placed up to and including that day) -> review scaling + the milestone gate
    prefix = [0] * (days_to_exam + 1)
    for o2, tps in lessons_by.items():
        if 0 <= o2 <= days_to_exam:
            prefix[o2] += len(tps)
    run = 0
    for i in range(days_to_exam + 1):
        run += prefix[i]
        prefix[i] = run

    def learned_upto(off: int) -> int:
        idx = min(max(off, 0), days_to_exam)
        return lesson_done_start + prefix[idx]

    # milestone ~ every 7th study day (learn/review window only) once >= 3 topics
    # are learned - the weekly checkpoint cadence from the Today builder
    milestones: set = set()
    s = 0
    for o in range(0, days_to_exam):
        if not is_study(o):
            continue
        s += 1
        if s % 7 == 0 and o < final_start and learned_upto(o) >= GMAT_MILESTONE_MIN_TOPICS:
            milestones.add(o)

    # practice tests spaced through the final stretch (tests-only), at the
    # near-exam cadence
    practice_tests: set = set()
    last_test = -_CAL_TEST_CADENCE - 1
    for o in range(max(0, final_start), days_to_exam):
        if not is_study(o):
            continue
        if o - last_test >= _CAL_TEST_CADENCE:
            practice_tests.add(o)
            last_test = o

    days_out: list = []
    end = min(days_to_exam, _CAL_MAX_DAYS)
    for off in range(0, end + 1):
        d = today + timedelta(days=off)
        is_exam = off == days_to_exam
        study = is_study(off) and not is_exam
        has_lesson = off in lessons_by or any(
            off in proj[0] for proj in sec_proj.values()
        )
        has_test = off in practice_tests
        has_ms = off in milestones
        items: list = []
        if is_exam:
            phase = "final"
        else:
            if study:
                items.append(
                    {
                        "kind": "review",
                        "topic": None,
                        "title": "Spaced review",
                        "est_minutes": _gmat_cal_review_min(learned_upto(off)),
                    }
                )
                for tp in lessons_by.get(off, []):
                    items.append(
                        {
                            "kind": "lesson",
                            "topic": tp,
                            "title": f"Learn {topic_leaf(tp)}",
                            "est_minutes": round(_LESSON_MIN),
                        }
                    )
                for tp in quizzes_by.get(off, []):
                    items.append(
                        {
                            "kind": "quiz",
                            "topic": tp,
                            "title": f"Quiz: {topic_leaf(tp)}",
                            "est_minutes": round(_QUIZ_MIN),
                        }
                    )
                for tp in requizzes_by.get(off, []):
                    items.append(
                        {
                            "kind": "requiz",
                            "topic": tp,
                            "title": f"Re-quiz: {topic_leaf(tp)}",
                            "est_minutes": round(_QUIZ_MIN),
                        }
                    )
                # Verbal + Data Insights (additive) projection for this day.
                for sec, (s_lessons, s_quizzes, s_requizzes) in sec_proj.items():
                    label = "Data Insights" if sec == "di" else "Verbal"
                    for tp in s_lessons.get(off, []):
                        items.append(
                            {
                                "kind": "lesson",
                                "section": sec,
                                "topic": tp,
                                "title": f"Learn {label}: {topic_leaf(tp)}",
                                "est_minutes": round(_LESSON_MIN),
                            }
                        )
                    for tp in s_quizzes.get(off, []):
                        items.append(
                            {
                                "kind": "quiz",
                                "section": sec,
                                "topic": tp,
                                "title": f"{label} quiz: {topic_leaf(tp)}",
                                "est_minutes": round(_QUIZ_MIN),
                            }
                        )
                    for tp in s_requizzes.get(off, []):
                        items.append(
                            {
                                "kind": "requiz",
                                "section": sec,
                                "topic": tp,
                                "title": f"{label} re-quiz: {topic_leaf(tp)}",
                                "est_minutes": round(_QUIZ_MIN),
                            }
                        )
                if has_ms:
                    items.append(
                        {
                            "kind": "milestone",
                            "topic": None,
                            "title": "Milestone checkpoint",
                            "est_minutes": round(_MILESTONE_MIN),
                        }
                    )
                if has_test:
                    items.append(
                        {
                            "kind": "practice_test",
                            "topic": None,
                            "title": "Practice test",
                            "est_minutes": round(_PRACTICE_TEST_MIN),
                        }
                    )
                # a non-lesson study day (no lesson/test/milestone) gets a drill fill
                if not has_lesson and not has_test and not has_ms:
                    items.append(
                        {
                            "kind": "drill",
                            "topic": None,
                            "title": "Targeted drill",
                            "est_minutes": round(_CAL_DRILL_N * _PRACTICE_MIN),
                        }
                    )
            else:
                items.append(
                    {"kind": "rest", "topic": None, "title": "Rest day", "est_minutes": 0}
                )
            # phase: content-first (a lesson day is always "learn"), else by window
            if has_lesson:
                phase = "learn"
            elif off >= final_start:
                phase = "final"
            elif off > last_lesson_off:
                phase = "review"
            else:
                phase = "learn"
        days_out.append(
            {
                "date": d.isoformat(),
                "day_offset": off,
                "weekday": WEEKDAYS[d.weekday()],
                "is_today": off == 0,
                "is_exam": is_exam,
                "is_study_day": study,
                "phase": phase,
                "est_minutes": sum(int(it.get("est_minutes", 0)) for it in items),
                "items": items,
            }
        )

    lessons_finish_date = (
        (today + timedelta(days=last_lesson_off)).isoformat()
        if last_lesson_off >= 0
        else None
    )
    study_days = sum(1 for o in range(0, days_to_exam) if is_study(o))
    return {
        "exam_date": exam_date,
        "days_to_exam": days_to_exam,
        "generated_ts": now_ts,
        "study_days": study_days,
        "lessons_finish_date": lessons_finish_date,
        "days": days_out,
    }


def topic_leaf(topic: str) -> str:
    leaf = (topic or "").split("::")[-1]
    return leaf.replace("_", " ").title() if leaf else "your weak topic"


def _gmat_lessons_dir() -> str:
    # qt/aqt/mediasrv.py -> aqt -> qt -> repo root; lessons at gmatwiz/lessons.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "gmatwiz", "lessons")


def _gmat_tests_dir() -> str:
    # sibling of _gmat_lessons_dir: the practice-test library at gmatwiz/tests.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "gmatwiz", "tests")


def _load_tests_index() -> dict:
    """The practice-test catalog ({"years": {...}}); empty if not authored yet."""
    path = os.path.join(_gmat_tests_dir(), "index.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"years": {}}


def _gmat_test_forms() -> list[dict]:
    """Flatten the tests index into a list of forms, each carrying its year."""
    index = _load_tests_index()
    forms: list[dict] = []
    for year, year_forms in (index.get("years", {}) or {}).items():
        for form in year_forms or []:
            entry = dict(form)
            entry.setdefault("year", year)
            entry["year"] = str(entry["year"])
            forms.append(entry)
    return forms


def _load_test_form(form_id: str) -> dict | None:
    """Read one authored form (`tests/<year>/<id>.json`); the year is resolved
    from the index so the caller only needs the form id."""
    if not form_id:
        return None
    year = None
    for form in _gmat_test_forms():
        if form.get("id") == form_id:
            year = str(form.get("year", ""))
            break
    if not year:
        return None
    path = os.path.join(_gmat_tests_dir(), year, f"{form_id}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _gmat_next_untaken_test(col) -> dict | None:
    """The next practice-test form the student hasn't taken (lowest id), or None."""
    taken = col.get_config("gmatTestsTaken", {}) or {}
    untaken = [f for f in _gmat_test_forms() if f.get("id") and f["id"] not in taken]
    if not untaken:
        return None
    untaken.sort(key=lambda f: f["id"])
    first = untaken[0]
    return {
        "id": first["id"],
        "year": str(first.get("year", "")),
        "label": first.get("label", first["id"]),
    }


def _load_lessons_index() -> dict:
    path = os.path.join(_gmat_lessons_dir(), "index.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"topics": []}


def gmat_lessons_index() -> bytes:
    """Return the lesson catalog merged with the student's mastery + learned state."""
    col = aqt.mw.col
    index = _load_lessons_index()
    plan = col.get_config("gmatPlan", None) or {}
    learned = col.get_config("gmatLearned", {}) or {}
    mastery_by_topic: dict = {}
    status_by_topic: dict = {}
    if isinstance(plan, dict):
        for t in plan.get("topics", []):
            mastery_by_topic[t.get("topic")] = t.get("mastery")
            status_by_topic[t.get("topic")] = t.get("status")
    topics = []
    for t in index.get("topics", []):
        tid = t.get("topic_id")
        topics.append(
            {
                "topic_id": tid,
                "title": t.get("title", ""),
                "domain": t.get("domain", ""),
                "mastery": mastery_by_topic.get(tid),
                "status": status_by_topic.get(tid),
                "learned": tid in learned,
                # the soft quiz gate: Study shows a "mastered" pill + gates the
                # on-demand quiz action off this (not merely lesson-done).
                "mastered": _gmat_topic_mastered(col, tid),
            }
        )
    # weakest first; unknown mastery (no diagnostic yet) goes last
    topics.sort(
        key=lambda x: (
            x["mastery"] is None,
            x["mastery"] if x["mastery"] is not None else 1.0,
        )
    )
    return json.dumps({"topics": topics}).encode("utf-8")


def _load_lesson_by_topic(topic_id: str) -> dict | None:
    index = _load_lessons_index()
    json_name = None
    for t in index.get("topics", []):
        if t.get("topic_id") == topic_id:
            json_name = t.get("json") or ((t.get("slug") or "") + ".json")
            break
    if not json_name:
        return None
    path = os.path.join(_gmat_lessons_dir(), json_name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def gmat_lesson() -> bytes:
    """Return the full authored lesson for a topic_id."""
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    lesson = _load_lesson_by_topic(str(body.get("topic_id", "")))
    return json.dumps({"lesson": lesson}).encode("utf-8")


def _schedule_lesson_items(col, topic_id: str) -> int:
    """Turn a completed lesson's you-do items into real GMAT PS cards so they
    enter the FSRS review queue. Idempotent per topic. Returns count added."""
    import anki.gmatwiz

    scheduled = col.get_config("gmatLessonScheduled", []) or []
    if topic_id in scheduled:
        return 0
    lesson = _load_lesson_by_topic(topic_id)
    if not lesson:
        return 0
    questions = []
    for item in lesson.get("you_do", []) or []:
        questions.append(
            {
                "stem": item.get("stem", ""),
                "options": item.get("options", {}) or {},
                "correct": item.get("correct", ""),
                "explanation": item.get("explanation", ""),
                "topic": topic_id,
                "difficulty": item.get("difficulty", "medium"),
                "source": "GMATWiz lesson",
                "passage": item.get("passage", "") or "",
            }
        )
    if not questions:
        return 0
    # Route lesson items to the matching notetype/deck per section.
    _sec = _gmat_section_of_topic(topic_id)
    if _sec == "verbal":
        added = anki.gmatwiz.import_verbal_questions(col, questions, "GMAT::Verbal")
    elif _sec == "di":
        added = anki.gmatwiz.import_di_questions(col, questions, "GMAT::DI")
    else:
        added = anki.gmatwiz.import_questions(col, questions, "GMAT::Quant")
    col.set_config("gmatLessonScheduled", scheduled + [topic_id])
    return added


def gmat_mark_learned() -> bytes:
    """Record lesson completion and schedule the topic's you-do items for review."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    topic_id = str(body.get("topic_id", ""))
    added = 0
    if topic_id:
        learned = col.get_config("gmatLearned", {}) or {}
        learned[topic_id] = int(time.time())
        col.set_config("gmatLearned", learned)
        try:
            added = _schedule_lesson_items(col, topic_id)
        except Exception as exc:
            print(f"GMATWiz: failed to schedule lesson items for {topic_id}: {exc}")
        # relearning the lesson completes any pending concept-gap repair
        repairs = col.get_config("gmatRepairTopics", {}) or {}
        if topic_id in repairs:
            del repairs[topic_id]
            col.set_config("gmatRepairTopics", repairs)
    return json.dumps({"scheduled": added}).encode("utf-8")


# Display-only mirror of rslib/src/gmatwiz.rs GMAT_TARGET_MS (the engine owns
# the persistent timing analytics; this only shapes the immediate mock report).
GMAT_MOCK_TARGET_MS = 128_000
# A full-length practice test only makes sense once the student has learned a
# meaningful slice of the syllabus AND is within striking distance of the exam -
# never on day one. (Tunable.)
GMAT_TEST_MIN_LEARNED_FRAC = 0.5
GMAT_TEST_EXAM_WINDOW_DAYS = 28


def gmat_mock_questions() -> bytes:
    """Question pool for a timed mock section: 21 questions / 45 minutes under
    exam conditions. Stratified by topic x difficulty, preferring questions the
    student has never seen, so the mock stays a held-out measurement."""
    import random

    col = aqt.mw.col
    seen_nids: set = set()
    try:
        rows = col.db.all(
            "select distinct c.nid from cards c join revlog r on r.cid = c.id"
        )
        seen_nids = {r[0] for r in rows}
    except Exception:
        pass

    pool: list = []
    for nid in col.find_notes('note:"GMAT PS"'):
        fields = dict(col.get_note(nid).items())
        pool.append(
            {
                "stem": fields.get("Stem", ""),
                "options": {k: fields.get(f"Option{k}", "") for k in "ABCDE"},
                "correct": fields.get("Correct", ""),
                "topic": fields.get("Topic", ""),
                "difficulty": fields.get("Difficulty", "medium") or "medium",
                "seen": nid in seen_nids,
            }
        )
    random.shuffle(pool)
    # unseen first so the client's adaptive picker naturally prefers held-out items
    pool.sort(key=lambda q: q["seen"])
    return json.dumps(
        {
            "pool": pool[:200],
            "count": 21,
            "seconds": 45 * 60,
            "target_ms": GMAT_MOCK_TARGET_MS,
        }
    ).encode("utf-8")


def gmat_topic_questions() -> bytes:
    """Question pool for a topic-scoped practice session, in the SAME shape as a
    mock pool so the practice card can be reused. The collection's GMAT PS notes
    filtered to one Topic, unseen items first. Fixed bank - AI generation to fill
    thin topics is a later phase."""
    import random

    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    topic = str(body.get("topic", "") or "")
    try:
        n = int(body.get("n", 10) or 10)
    except Exception:
        n = 10
    n = max(1, min(50, n))
    # The requested topic encodes its section (gmat::quant / gmat::verbal), so a
    # verbal practice/quiz pulls from GMAT Verbal notes; quant is unchanged.
    section = _gmat_section_of_topic(topic)
    notetype = _gmat_notetype_for_section(section)

    col = aqt.mw.col
    seen_nids: set = set()
    try:
        rows = col.db.all(
            "select distinct c.nid from cards c join revlog r on r.cid = c.id"
        )
        seen_nids = {r[0] for r in rows}
    except Exception:
        pass

    pool: list = []
    for nid in col.find_notes(f'note:"{notetype}"'):
        fields = dict(col.get_note(nid).items())
        if topic and fields.get("Topic", "") != topic:
            continue
        pool.append(
            {
                "stem": fields.get("Stem", ""),
                "options": {k: fields.get(f"Option{k}", "") for k in "ABCDE"},
                "correct": fields.get("Correct", ""),
                "topic": fields.get("Topic", ""),
                "difficulty": fields.get("Difficulty", "medium") or "medium",
                "seen": nid in seen_nids,
                "passage": fields.get("Passage", ""),
            }
        )
    # Bundled fallback (no notes imported yet for this section, e.g. verbal/di).
    if not pool and section in ("verbal", "di"):
        for f in _gmat_pool_by_topic(section).get(topic, []):
            pool.append(
                {
                    "stem": f.get("Stem", ""),
                    "options": {k: f.get(f"Option{k}", "") for k in "ABCDE"},
                    "correct": f.get("Correct", ""),
                    "topic": f.get("Topic", ""),
                    "difficulty": f.get("Difficulty", "medium") or "medium",
                    "seen": False,
                    "passage": f.get("Passage", ""),
                }
            )
    random.shuffle(pool)
    # unseen first so a fresh session prefers held-out items
    pool.sort(key=lambda q: q["seen"])
    sliced = pool[:n]
    return json.dumps(
        {
            "pool": sliced,
            "count": len(sliced),
            "seconds": 45 * 60,
            "target_ms": GMAT_MOCK_TARGET_MS,
        }
    ).encode("utf-8")


# Default milestone-test length (a periodic checkpoint, 12-15 questions mixed
# across learned topics); the client may request another n within these bounds.
GMAT_MILESTONE_N = 12
GMAT_MILESTONE_N_MAX = 25
# how many topics must be lesson-done before the weekly milestone starts showing
GMAT_MILESTONE_MIN_TOPICS = 3


def gmat_milestone_questions() -> bytes:
    """Question pool for a MILESTONE test: n questions (default 12) MIXED across
    the topics the student has learned (fallback: all topics), unseen-first, in
    the SAME shape as a mock pool so the timed-mock flow is reused verbatim. The
    client's adaptive picker naturally mixes topics from this pool."""
    import random

    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    try:
        n = int(body.get("n", GMAT_MILESTONE_N) or GMAT_MILESTONE_N)
    except Exception:
        n = GMAT_MILESTONE_N
    n = max(1, min(GMAT_MILESTONE_N_MAX, n))

    col = aqt.mw.col
    learned = set((col.get_config("gmatLearned", {}) or {}).keys())
    seen_nids: set = set()
    try:
        rows = col.db.all(
            "select distinct c.nid from cards c join revlog r on r.cid = c.id"
        )
        seen_nids = {r[0] for r in rows}
    except Exception:
        pass

    def build(restrict: set) -> list:
        out: list = []
        for nid in col.find_notes('note:"GMAT PS"'):
            fields = dict(col.get_note(nid).items())
            topic = fields.get("Topic", "")
            if restrict and topic not in restrict:
                continue
            out.append(
                {
                    "stem": fields.get("Stem", ""),
                    "options": {k: fields.get(f"Option{k}", "") for k in "ABCDE"},
                    "correct": fields.get("Correct", ""),
                    "topic": topic,
                    "difficulty": fields.get("Difficulty", "medium") or "medium",
                    "seen": nid in seen_nids,
                }
            )
        return out

    pool = build(learned)
    if not pool:
        # no learned-topic items yet (fresh account / thin bank): mix across all
        pool = build(set())
    random.shuffle(pool)
    pool.sort(key=lambda q: q["seen"])
    return json.dumps(
        {
            "pool": pool[:200],
            "count": min(n, len(pool)),
            "seconds": n * (GMAT_MOCK_TARGET_MS // 1000),
            "target_ms": GMAT_MOCK_TARGET_MS,
        }
    ).encode("utf-8")


# Tag applied to AI-generated PS notes so they're identifiable (and could be
# audited or bulk-removed) separately from the curated bank.
GMAT_AI_GENERATED_TAG = "gmatwiz::ai-generated"
# Named-source provenance stamped on every admitted AI item (traces the output
# back to the model + the quality gate it passed). Keep the model in sync with the
# Cloud Function default (functions/src/index.ts OPENAI_MODEL).
GMAT_AI_SOURCE = "AI-generated (gpt-4.1-mini) - 7f-checked"


def gmat_add_questions() -> bytes:
    """Admit AI-generated questions (already checkItem-gated on the client) into
    the fixed bank as real "GMAT PS" notes so FSRS schedules them. Reuses the
    existing note-add path (anki.gmatwiz.build_add_requests) and tags each note
    'gmatwiz::ai-generated'. Body: {"questions": [ {stem, options, correct,
    explanation, topic, difficulty}, ... ]}. Returns {"added": count}."""
    import anki.gmatwiz

    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    raw = body.get("questions", []) or []
    questions: list[dict] = []
    for q in raw:
        if not isinstance(q, dict):
            continue
        options = q.get("options") or {}
        if not q.get("stem") or not q.get("correct") or not isinstance(options, dict):
            continue
        questions.append(
            {
                "stem": str(q.get("stem", "")),
                "options": {k: str(options.get(k, "")) for k in "ABCDE"},
                "correct": str(q.get("correct", "")),
                "explanation": str(q.get("explanation", "")),
                "topic": str(q.get("topic", "")),
                "difficulty": str(q.get("difficulty", "medium") or "medium"),
                "source": GMAT_AI_SOURCE,
            }
        )
    if not questions:
        return json.dumps({"added": 0}).encode("utf-8")

    requests = anki.gmatwiz.build_add_requests(col, questions, "GMAT::Quant")
    for req in requests:
        req.note.tags.append(GMAT_AI_GENERATED_TAG)
    if requests:
        col.add_notes(requests)
    # Return the created cards (with card_id + content) so the client can serve
    # them immediately at the FRONT of the Drill queue AND record real reviews.
    cards_out: list[dict] = []
    for req in requests:
        note = req.note
        try:
            cids = list(col.card_ids_of_note(note.id))
        except Exception:
            cids = [c.id for c in note.cards()]
        if not cids:
            continue
        fields = dict(note.items())
        cards_out.append(
            {
                "card_id": cids[0],
                "stem": fields.get("Stem", ""),
                "options": {k: fields.get(f"Option{k}", "") for k in "ABCDE"},
                "correct": fields.get("Correct", ""),
                "explanation": fields.get("Explanation", ""),
                "topic": fields.get("Topic", ""),
                "difficulty": fields.get("Difficulty", "medium") or "medium",
            }
        )
    return json.dumps({"added": len(cards_out), "cards": cards_out}).encode("utf-8")


def gmat_submit_mock() -> bytes:
    """Store a finished mock, update the living plan from its answers, and
    return the report. Mock answers deliberately do NOT go through the
    scheduler (they would distort FSRS intervals); they live in gmatMocks and
    the engine folds them into Readiness as calibration evidence."""
    from collections import defaultdict

    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    results = body.get("results", []) or []
    n = len(results)
    if n == 0:
        return json.dumps({"ok": False}).encode("utf-8")

    # optional: which practice-test form produced these answers (year is accepted
    # for symmetry with the client but resolved from the index, so it's unused).
    form_id = str(body.get("form_id", "") or "")

    correct = sum(1 for r in results if r.get("correct"))
    accuracy = correct / n

    per_topic: dict = defaultdict(lambda: [0, 0])
    timed = [r for r in results if int(r.get("ms", 0) or 0) > 0]
    rushed_wrong = sum(
        1
        for r in timed
        if not r.get("correct") and int(r["ms"]) < GMAT_MOCK_TARGET_MS // 2
    )
    slow_correct = sum(
        1
        for r in timed
        if r.get("correct") and int(r["ms"]) > GMAT_MOCK_TARGET_MS * 3 // 2
    )
    avg_ms = int(sum(int(r["ms"]) for r in timed) / len(timed)) if timed else 0
    for r in results:
        topic = str(r.get("topic", ""))
        if not topic:
            continue
        per_topic[topic][1] += 1
        if r.get("correct"):
            per_topic[topic][0] += 1
        # every mock answer updates the living plan, like practice answers do
        _gmat_update_mastery(col, topic, bool(r.get("correct")))

    now_ts = int(time.time())
    mocks = col.get_config("gmatMocks", []) or []
    entry = {
        "ts": now_ts,
        "accuracy": round(accuracy, 4),
        "n": n,
        "timing": {
            "avg_ms": avg_ms,
            "rushed_wrong": rushed_wrong,
            "slow_correct": slow_correct,
        },
    }
    if form_id:
        entry["form_id"] = form_id
    mocks.append(entry)
    col.set_config("gmatMocks", mocks[-20:])

    # score the mock in the shared engine (single accuracy->Q implementation)
    q = None
    try:
        raw = col._backend.gmat_scores()
        scores = json.loads(getattr(raw, "val", raw))
        engine_mocks = scores.get("readiness", {}).get("mocks", []) or []
        if engine_mocks:
            q = engine_mocks[-1].get("q")
    except Exception as exc:
        print(f"GMATWiz: mock scoring unavailable: {exc}")

    # a practice-test form additionally records itself as taken (id -> score)
    if form_id:
        taken = col.get_config("gmatTestsTaken", {}) or {}
        taken[form_id] = {"ts": now_ts, "accuracy": round(accuracy, 4), "q": q}
        col.set_config("gmatTestsTaken", taken)

    return json.dumps(
        {
            "ok": True,
            "accuracy": round(accuracy, 4),
            "n": n,
            "q": q,
            "per_topic": [
                {"topic": t, "correct": c, "n": total}
                for t, (c, total) in sorted(
                    per_topic.items(), key=lambda kv: kv[1][0] / kv[1][1]
                )
            ],
            "timing": {
                "avg_ms": avg_ms,
                "rushed_wrong": rushed_wrong,
                "slow_correct": slow_correct,
                "target_ms": GMAT_MOCK_TARGET_MS,
            },
        }
    ).encode("utf-8")


def gmat_submit_quiz() -> bytes:
    """Store a finished assessment session (topic quiz or milestone test) and
    return its report, feeding all three scores.

    Body: { kind:"topic"|"milestone", topic?, results:[{topic, difficulty,
    correct, ms, stem, chosen, correct_key}] }.

    - topic quiz: append a session to gmatQuizzes[topic] (the mastery gate). A
      failed quiz (< pass bar) puts the topic back into repair (concept-gap
      mechanism) so it reschedules in Today; a quiz that just tips the topic to
      mastered clears its repair flag. Bypassable - never hard-blocks anything.
    - milestone: append to the EXISTING gmatMocks list with kind:"milestone" so
      Readiness folds it in via the unchanged gmatMocks reader.

    BOTH tiers move per-topic mastery harder than a drill (alpha 0.5) and count
    every answer as an APPLICATION attempt (gmatApplication) so Performance
    reflects them. Missed questions flow to the error log via the client's
    per-miss classification (the reused mock report), exactly like a mock."""
    from collections import defaultdict

    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    kind = str(body.get("kind", "topic") or "topic")
    results = body.get("results", []) or []
    n = len(results)
    if n == 0:
        return json.dumps({"ok": False}).encode("utf-8")

    correct = sum(1 for r in results if r.get("correct"))
    accuracy = correct / n

    per_topic: dict = defaultdict(lambda: [0, 0])
    timed = [r for r in results if int(r.get("ms", 0) or 0) > 0]
    rushed_wrong = sum(
        1 for r in timed if not r.get("correct") and int(r["ms"]) < GMAT_MOCK_TARGET_MS // 2
    )
    slow_correct = sum(
        1 for r in timed if r.get("correct") and int(r["ms"]) > GMAT_MOCK_TARGET_MS * 3 // 2
    )
    avg_ms = int(sum(int(r["ms"]) for r in timed) / len(timed)) if timed else 0
    for r in results:
        rtopic = str(r.get("topic", ""))
        if not rtopic:
            continue
        per_topic[rtopic][1] += 1
        if r.get("correct"):
            per_topic[rtopic][0] += 1
        # assessment answers move mastery harder than a drill (0.5), and every
        # answer is application evidence the Performance reader folds in
        _gmat_update_mastery(
            col, rtopic, bool(r.get("correct")), alpha=GMAT_QUIZ_MASTERY_ALPHA
        )
        _gmat_record_application(col, rtopic, bool(r.get("correct")), int(r.get("ms", 0) or 0))

    now_ts = int(time.time())
    mastered = None
    if kind == "milestone":
        mocks = col.get_config("gmatMocks", []) or []
        mocks.append(
            {
                "ts": now_ts,
                "kind": "milestone",
                "accuracy": round(accuracy, 4),
                "n": n,
                "timing": {
                    "avg_ms": avg_ms,
                    "rushed_wrong": rushed_wrong,
                    "slow_correct": slow_correct,
                },
            }
        )
        col.set_config("gmatMocks", mocks[-20:])
    else:
        topic = str(body.get("topic", "") or "")
        if not topic and per_topic:
            # infer the dominant topic if the client omitted it
            topic = max(per_topic.items(), key=lambda kv: kv[1][1])[0]
        if topic:
            quizzes = col.get_config("gmatQuizzes", {}) or {}
            sessions = quizzes.get(topic, []) or []
            sessions.append(
                {
                    "ts": now_ts,
                    "day": _gmat_day_bucket(col),
                    "accuracy": round(accuracy, 4),
                    "n": n,
                }
            )
            quizzes[topic] = sessions[-50:]
            col.set_config("gmatQuizzes", quizzes)
            mastered = _gmat_topic_mastered(col, topic)
            if accuracy < GMAT_QUIZ_PASS_ACCURACY:
                _gmat_apply_repair(col, topic, "concept_gap")
            elif mastered:
                repairs = col.get_config("gmatRepairTopics", {}) or {}
                if topic in repairs:
                    del repairs[topic]
                    col.set_config("gmatRepairTopics", repairs)

    # score in the shared engine (single accuracy->Q map); a milestone shows a Q
    # like a mock, a topic quiz reports its accuracy without a section score
    q = None
    if kind == "milestone":
        try:
            raw = col._backend.gmat_scores()
            scores = json.loads(getattr(raw, "val", raw))
            engine_mocks = scores.get("readiness", {}).get("mocks", []) or []
            if engine_mocks:
                q = engine_mocks[-1].get("q")
        except Exception as exc:
            print(f"GMATWiz: quiz scoring unavailable: {exc}")

    report: dict = {
        "ok": True,
        "kind": kind,
        "accuracy": round(accuracy, 4),
        "n": n,
        "q": q,
        "per_topic": [
            {"topic": t, "correct": c, "n": total}
            for t, (c, total) in sorted(
                per_topic.items(), key=lambda kv: kv[1][0] / kv[1][1]
            )
        ],
        "timing": {
            "avg_ms": avg_ms,
            "rushed_wrong": rushed_wrong,
            "slow_correct": slow_correct,
            "target_ms": GMAT_MOCK_TARGET_MS,
        },
    }
    if mastered is not None:
        report["mastered"] = bool(mastered)
    return json.dumps(report).encode("utf-8")


def gmat_tests() -> bytes:
    """The practice-test catalog grouped by year, merged with this student's
    taken/score status (from the gmatTestsTaken config). Empty if not authored."""
    col = aqt.mw.col
    index = _load_tests_index()
    taken = col.get_config("gmatTestsTaken", {}) or {}
    years_out: dict = {}
    for year, forms in (index.get("years", {}) or {}).items():
        out_forms = []
        for form in forms or []:
            fid = form.get("id")
            status = taken.get(fid) or {}
            out_forms.append(
                {
                    "id": fid,
                    "year": str(form.get("year", year)),
                    "label": form.get("label", fid),
                    "count": form.get("count", 21),
                    "topics": form.get("topics", {}) or {},
                    "sources": form.get("sources", []) or [],
                    "taken": fid in taken,
                    "accuracy": status.get("accuracy"),
                    "q": status.get("q"),
                    "ts": status.get("ts"),
                }
            )
        years_out[str(year)] = out_forms
    return json.dumps({"years": years_out}).encode("utf-8")


def gmat_test_questions() -> bytes:
    """One practice-test form's questions in the SAME shape as a mock pool (so
    the timed-mock flow is reused verbatim). Pool order is the form's item order."""
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    form_id = str(body.get("id", ""))
    form = _load_test_form(form_id)
    if not form:
        return json.dumps(
            {
                "pool": [],
                "count": 21,
                "seconds": 45 * 60,
                "target_ms": GMAT_MOCK_TARGET_MS,
            }
        ).encode("utf-8")
    pool = [
        {
            "stem": it.get("stem", ""),
            "options": it.get("options", {}) or {},
            "correct": it.get("correct", ""),
            "topic": it.get("topic", ""),
            "difficulty": it.get("difficulty", "medium") or "medium",
            "seen": False,
        }
        for it in (form.get("items", []) or [])
    ]
    return json.dumps(
        {
            "pool": pool,
            "count": len(pool),
            "seconds": form.get("seconds", 45 * 60),
            "target_ms": form.get("target_ms", GMAT_MOCK_TARGET_MS),
            "form_id": form.get("id", form_id),
            "label": form.get("label", ""),
        }
    ).encode("utf-8")


post_handler_list = [
    congrats_info,
    gmat_questions,
    gmat_next_card,
    gmat_answer_card,
    gmat_overview,
    gmat_error_log,
    gmat_log_error,
    gmat_set_error_takeaway,
    gmat_save_profile,
    gmat_ensure_content,
    gmat_set_ai_enabled,
    gmat_add_questions,
    gmat_pretest_questions,
    gmat_submit_pretest,
    gmat_lessons_index,
    gmat_lesson,
    gmat_mark_learned,
    gmat_today,
    gmat_calendar,
    gmat_mock_questions,
    gmat_topic_questions,
    gmat_milestone_questions,
    gmat_submit_mock,
    gmat_submit_quiz,
    gmat_tests,
    gmat_test_questions,
    gmat_official_scores,
    gmat_save_official_score,
    gmat_open_stats,
    gmat_open_decks,
    gmat_sync_now,
    gmat_stats,
    gmat_export_state,
    gmat_import_state,
    gmat_reset_state,
    gmat_col_meta,
    gmat_col_export,
    gmat_col_replace,
    get_deck_configs_for_update,
    update_deck_configs,
    get_scheduling_states_with_context,
    set_scheduling_states,
    change_notetype,
    import_done,
    import_csv,
    import_anki_package,
    import_json_file,
    import_json_string,
    search_in_browser,
    deck_options_require_close,
    deck_options_ready,
    save_custom_colours,
]


exposed_backend_list = [
    # CollectionService
    "latest_progress",
    "get_custom_colours",
    # DeckService
    "get_deck_names",
    # I18nService
    "i18n_resources",
    # ImportExportService
    "get_csv_metadata",
    "get_import_anki_package_presets",
    # NotesService
    "get_field_names",
    "get_note",
    # NotetypesService
    "get_notetype_names",
    "get_change_notetype_info",
    # StatsService
    "card_stats",
    "get_review_logs",
    "graphs",
    "get_graph_preferences",
    "set_graph_preferences",
    # TagsService
    "complete_tag",
    # ImageOcclusionService
    "get_image_for_occlusion",
    "add_image_occlusion_note",
    "get_image_occlusion_note",
    "update_image_occlusion_note",
    "get_image_occlusion_fields",
    # SchedulerService
    "compute_fsrs_params",
    "compute_optimal_retention",
    "set_topic_mastery",
    "set_wants_abort",
    "evaluate_params_legacy",
    "get_optimal_retention_parameters",
    "simulate_fsrs_review",
    "simulate_fsrs_workload",
    # DeckConfigService
    "get_ignored_before_count",
    "get_retention_workload",
]


def raw_backend_request(endpoint: str) -> Callable[[], bytes]:
    # check for key at startup
    from anki._backend import RustBackend

    assert hasattr(RustBackend, f"{endpoint}_raw")

    return lambda: getattr(aqt.mw.col._backend, f"{endpoint}_raw")(request.data)


# all methods in here require a collection
post_handlers = {
    stringcase.camelcase(handler.__name__): handler for handler in post_handler_list
} | {
    stringcase.camelcase(handler): raw_backend_request(handler)
    for handler in exposed_backend_list
}


def _extract_collection_post_request(path: str) -> DynamicRequest | NotFound:
    if not aqt.mw.col:
        return NotFound(message=f"collection not open, ignore request for {path}")
    if handler := post_handlers.get(path):
        # convert bytes/None into response
        def wrapped() -> Response:
            try:
                if data := handler():
                    response = flask.make_response(data)
                    response.headers["Content-Type"] = "application/binary"
                else:
                    response = _text_response(HTTPStatus.NO_CONTENT, "")
            except Exception as exc:
                print(traceback.format_exc())
                response = _text_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return response

        return wrapped
    else:
        return NotFound(message=f"{path} not found")


def _check_dynamic_request_permissions():
    if request.method == "GET":
        return

    def warn() -> None:
        show_warning(
            "Unexpected API access. Please report this message on the Anki forums."
        )

    # check content type header to ensure this isn't an opaque request from another origin
    if request.headers["Content-type"] != "application/binary":
        aqt.mw.taskman.run_on_main(warn)
        abort(403)

    # does page have access to entire API?
    if _have_api_access():
        return

    # whitelisted API endpoints for reviewer/previewer
    if request.path in (
        "/_anki/getSchedulingStatesWithContext",
        "/_anki/setSchedulingStates",
        "/_anki/i18nResources",
        "/_anki/congratsInfo",
        # GMATWiz renders in the main webview (no full API access), so its
        # read/record endpoints are whitelisted here, like the reviewer's.
        "/_anki/gmatOverview",
        "/_anki/gmatQuestions",
        "/_anki/gmatNextCard",
        "/_anki/gmatAnswerCard",
        "/_anki/gmatErrorLog",
        "/_anki/gmatLogError",
        "/_anki/gmatSetErrorTakeaway",
        "/_anki/gmatSaveProfile",
        "/_anki/gmatSetAiEnabled",
        "/_anki/gmatAddQuestions",
        "/_anki/gmatPretestQuestions",
        "/_anki/gmatSubmitPretest",
        "/_anki/gmatLessonsIndex",
        "/_anki/gmatLesson",
        "/_anki/gmatMarkLearned",
        "/_anki/gmatToday",
        "/_anki/gmatCalendar",
        "/_anki/gmatMockQuestions",
        "/_anki/gmatTopicQuestions",
        "/_anki/gmatMilestoneQuestions",
        "/_anki/gmatSubmitMock",
        "/_anki/gmatSubmitQuiz",
        "/_anki/gmatTests",
        "/_anki/gmatTestQuestions",
        "/_anki/gmatOfficialScores",
        "/_anki/gmatSaveOfficialScore",
        "/_anki/gmatOpenStats",
        "/_anki/gmatOpenDecks",
        "/_anki/gmatSyncNow",
        "/_anki/gmatStats",
        "/_anki/gmatExportState",
        "/_anki/gmatImportState",
        "/_anki/gmatResetState",
        "/_anki/gmatColMeta",
        "/_anki/gmatColExport",
        "/_anki/gmatColReplace",
        "/_anki/gmatEnsureContent",
    ):
        pass
    else:
        # other legacy pages may contain third-party JS, so we do not
        # allow them to access our API
        aqt.mw.taskman.run_on_main(warn)
        abort(403)


def _handle_dynamic_request(req: DynamicRequest) -> Response:
    _check_dynamic_request_permissions()
    try:
        return req()
    except Exception as e:
        return _text_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


def legacy_page_data() -> Response:
    id = int(request.args["id"])
    page = aqt.mw.mediaServer.get_page(id)
    if page:
        response = Response(page.html, mimetype="text/html")
        # Prevent JS in field content from being executed in the editor, as it would
        # have access to our internal API, and is a security risk.
        if page.context == PageContext.EDITOR:
            response.headers["Content-Security-Policy"] = (
                _editor_content_security_policy(aqt.mw.mediaServer.getPort())
            )
        return response
    else:
        return _text_response(HTTPStatus.NOT_FOUND, "page not found")


_APIKEY = secrets.token_urlsafe(32)


def _have_api_access() -> bool:
    return (
        request.headers.get("Authorization") == f"Bearer {_APIKEY}"
        or os.environ.get("ANKI_API_HOST") == "0.0.0.0"
    )


# this currently only handles a single method; in the future, idempotent
# requests like i18nResources should probably be moved here
def _extract_dynamic_get_request(path: str) -> DynamicRequest | None:
    if path == "legacyPageData":
        return legacy_page_data
    else:
        return None
