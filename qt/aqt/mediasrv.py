# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import enum
import json
import logging
import mimetypes
import os
import re
import secrets
import sys
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
    try:
        raw = col._backend.gmat_scores()
        data = json.loads(getattr(raw, "val", raw))
        return {
            "memory": data.get("memory", _score_unavailable()),
            "performance": data.get("performance", _score_unavailable()),
            "readiness": data.get("readiness", _score_unavailable()),
            "topics_covered": data.get("topics_covered", 0),
            "topics_total": data.get("topics_total", GMAT_QUANT_TOPIC_TOTAL),
        }
    except Exception as exc:
        print(f"GMATWiz: score engine unavailable: {exc}")
        return {
            "memory": _score_unavailable(),
            "performance": _score_unavailable(),
            "readiness": _score_unavailable(),
            "topics_covered": 0,
            "topics_total": GMAT_QUANT_TOPIC_TOTAL,
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
    repair. Body: JSON entry with optional why/ms/guess/mock fields."""
    col = aqt.mw.col
    try:
        entry = json.loads(request.data or b"{}")
    except Exception:
        entry = {}
    topic = str(entry.get("topic", ""))
    why = str(entry.get("why", ""))
    _gmat_append_error(
        col,
        {
            "stem": str(entry.get("stem", ""))[:400],
            "topic": topic,
            "chosen": str(entry.get("chosen", "")),
            "correct": str(entry.get("correct", "")),
            "why": why,
            "ms": int(entry.get("ms", 0) or 0),
            "mock": bool(entry.get("mock", False)),
            "ts": int(time.time()),
        },
    )
    _gmat_apply_repair(col, topic, why)
    return b""


def gmat_next_card() -> bytes:
    """Return the next scheduled GMAT card from the REAL scheduler.

    Selecting the GMAT deck and calling get_queued_cards means the topic-aware
    ordering and daily limits from the engine apply. Read-only.
    """
    from anki.cards import Card

    col = aqt.mw.col
    deck_id = col.decks.id("GMAT::Quant")
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

    deck_id = col.decks.id("GMAT::Quant")
    if col.decks.get_current_id() != deck_id:
        col.decks.select(deck_id)
    queued = col.sched.get_queued_cards(fetch_limit=1)
    if not queued.cards or queued.cards[0].card.id != card_id:
        # queue moved on; do not answer the wrong card
        return b""
    states = queued.cards[0].states
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


def _gmat_status(mastery: float) -> str:
    return "weak" if mastery < 0.5 else ("developing" if mastery < 0.8 else "strong")


def _gmat_topic_of_card(col, card_id: int) -> str:
    try:
        note = col.get_card(card_id).note()
        return dict(note.items()).get("Topic", "") or ""
    except Exception:
        return ""


def _gmat_update_mastery(col, topic: str, correct: bool) -> None:
    """EMA-update one topic's mastery from a single practice answer and keep the
    stored plan + topic-aware scheduling in sync. No-op until a plan exists."""
    if not topic or not col.get_config("gmatPlan", None):
        return
    diagnosis = col.get_config("gmatDiagnosis", {}) or {}
    old = diagnosis.get(topic)
    old = 0.5 if old is None else float(old)
    new = round(
        (1 - GMAT_MASTERY_ALPHA) * old + GMAT_MASTERY_ALPHA * (1.0 if correct else 0.0),
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


def _gmat_notes_by_topic() -> dict:
    from collections import defaultdict

    col = aqt.mw.col
    by_topic: dict = defaultdict(list)
    for nid in col.find_notes('note:"GMAT PS"'):
        fields = dict(col.get_note(nid).items())
        topic = fields.get("Topic", "")
        if topic:
            by_topic[topic].append(fields)
    return by_topic


def gmat_save_profile() -> bytes:
    """Store the student's exam date + weekly availability."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    profile = {
        "exam_date": str(body.get("exam_date", "")),
        "days_per_week": int(body.get("days_per_week", 5) or 5),
        "minutes_per_day": int(body.get("minutes_per_day", 60) or 60),
    }
    col.set_config("gmatProfile", profile)
    return b""


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


def gmat_pretest_questions() -> bytes:
    """Return a 21-question diagnostic sampled across all Quant topics."""
    import random

    by_topic = _gmat_notes_by_topic()
    picked: list = []
    seen: set = set()
    for notes in by_topic.values():
        choice = random.choice(notes)
        picked.append(choice)
        seen.add(id(choice))
    all_notes = [n for notes in by_topic.values() for n in notes]
    random.shuffle(all_notes)
    for note in all_notes:
        if len(picked) >= 21:
            break
        if id(note) not in seen:
            picked.append(note)
            seen.add(id(note))
    picked = picked[:21]
    random.shuffle(picked)
    questions = [
        {
            "stem": f.get("Stem", ""),
            "options": {k: f.get(f"Option{k}", "") for k in "ABCDE"},
            "correct": f.get("Correct", ""),
            "topic": f.get("Topic", ""),
            "difficulty": f.get("Difficulty", ""),
        }
        for f in picked
    ]
    return json.dumps({"questions": questions, "seconds": 45 * 60}).encode("utf-8")


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

    agg: dict = defaultdict(lambda: [0, 0])  # topic -> [correct, total]
    for r in results:
        topic = str(r.get("topic", ""))
        if not topic:
            continue
        agg[topic][1] += 1
        if r.get("correct"):
            agg[topic][0] += 1

    diagnosis: dict = {}
    for topic in _gmat_notes_by_topic().keys():
        correct, total = agg.get(topic, [0, 0])
        mastery = (correct / total) if total > 0 else 0.5
        diagnosis[topic] = round(mastery, 3)
        try:
            col._backend.set_topic_mastery(topic=topic, mastery=mastery)
        except Exception as exc:
            print(f"set_topic_mastery failed for {topic}: {exc}")

    # Now that mastery is populated, turn on topic-aware scheduling.
    col.set_config("topicAwareScheduling", True)

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
    plan = {
        "topics": [
            {"topic": t, "mastery": m, "status": status(m)} for t, m in ranked
        ],
        "daily_minutes": int(profile.get("minutes_per_day", 60) or 60),
        "days_per_week": int(profile.get("days_per_week", 5) or 5),
        "days_to_exam": days_to_exam,
        "created_ts": int(time.time()),
    }
    col.set_config("gmatDiagnosis", diagnosis)
    col.set_config("gmatPlan", plan)
    return json.dumps({"diagnosis": diagnosis, "plan": plan}).encode("utf-8")


def _gmat_pacing(col) -> dict:
    """Dated pacing + on/behind-track from profile + plan + learned progress.

    The learn phase is the first ~70% of the runway to the exam; the final ~30%
    is reserved for review/mixed practice (mirrors the learn-then-drill model).
    'behind_by' compares topics actually learned against the count you should
    have learned by today if you were on an even pace.
    """
    from datetime import date, datetime

    plan = col.get_config("gmatPlan", None) or {}
    profile = col.get_config("gmatProfile", {}) or {}
    learned = col.get_config("gmatLearned", {}) or {}
    topics = plan.get("topics", []) or []
    topic_ids = {t.get("topic") for t in topics}
    topics_total = len(topics)
    topics_learned = len([t for t in learned if t in topic_ids])
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

    # learning runway = first 70% of remaining study days (min 1 while any remain)
    learn_days_remaining = max(1, round(study_days_remaining * 0.7)) if study_days_remaining else 0
    out["topics_per_study_day"] = (
        round(topics_remaining / learn_days_remaining, 2) if learn_days_remaining else float(topics_remaining)
    )

    # expected progress by today (day-of-week cancels in the ratio, so use
    # calendar days between plan creation and the 70% learn deadline)
    created_ts = plan.get("created_ts")
    behind = 0
    if created_ts:
        created = date.fromtimestamp(created_ts)
        total_days = max(1, (exam - created).days)
        learn_deadline_days = max(1.0, total_days * 0.7)
        elapsed = max(0, (today - created).days)
        frac = min(1.0, elapsed / learn_deadline_days)
        expected_learned = round(topics_total * frac)
        behind = max(0, expected_learned - topics_learned)
    out["behind_by"] = behind
    out["status"] = "behind" if behind > 0 else "on_track"
    return out


# rough per-item minute costs used to size the daily session
_REVIEW_MIN = 1.5
_LESSON_MIN = 12.0
_PRACTICE_MIN = 2.0


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
    daily_minutes = float(plan.get("daily_minutes", 60) or 60)
    learned = col.get_config("gmatLearned", {}) or {}
    topics = plan.get("topics", []) or []

    # due today, honoring the engine's daily limits + topic-aware order
    deck_id = col.decks.id("GMAT::Quant")
    if col.decks.get_current_id() != deck_id:
        col.decks.select(deck_id)
    queued = col.sched.get_queued_cards(fetch_limit=1)
    due_total = queued.new_count + queued.learning_count + queued.review_count

    # which weak topics have an authored lesson (so "Learn" links resolve)
    lesson_ids = {
        t.get("topic_id") for t in _load_lessons_index().get("topics", [])
    }

    blocks: list = []
    remaining_min = daily_minutes

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

    # suggest a timed mock when the learning runway is done or the exam is
    # close, at most every 7 days (the app decides when to simulate the exam)
    mocks = col.get_config("gmatMocks", []) or []
    last_mock_ts = mocks[-1].get("ts", 0) if mocks else 0
    days_to_exam = pacing.get("days_to_exam")
    mock_due = (
        pacing.get("status") == "learning_complete"
        or (days_to_exam is not None and days_to_exam <= 21)
    ) and (now_ts - last_mock_ts) > 7 * 86400
    if mock_due:
        blocks.append(
            {
                "kind": "mock",
                "title": "Timed mock section",
                "detail": "21 questions · 45:00 · exam conditions, no feedback until the end",
                "count": 21,
                "est_minutes": 45,
            }
        )

    return {
        "has_plan": True,
        "pacing": pacing,
        "blocks": blocks,
        "daily_minutes": round(daily_minutes),
    }


def topic_leaf(topic: str) -> str:
    leaf = (topic or "").split("::")[-1]
    return leaf.replace("_", " ").title() if leaf else "your weak topic"


def _gmat_lessons_dir() -> str:
    # qt/aqt/mediasrv.py -> aqt -> qt -> repo root; lessons at gmatwiz/lessons.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "gmatwiz", "lessons")


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
            }
        )
    if not questions:
        return 0
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

    mocks = col.get_config("gmatMocks", []) or []
    mocks.append(
        {
            "ts": int(time.time()),
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


post_handler_list = [
    congrats_info,
    gmat_questions,
    gmat_next_card,
    gmat_answer_card,
    gmat_overview,
    gmat_error_log,
    gmat_log_error,
    gmat_save_profile,
    gmat_pretest_questions,
    gmat_submit_pretest,
    gmat_lessons_index,
    gmat_lesson,
    gmat_mark_learned,
    gmat_today,
    gmat_mock_questions,
    gmat_submit_mock,
    gmat_official_scores,
    gmat_save_official_score,
    gmat_open_stats,
    gmat_open_decks,
    gmat_sync_now,
    gmat_stats,
    gmat_export_state,
    gmat_import_state,
    gmat_reset_state,
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
        "/_anki/gmatSaveProfile",
        "/_anki/gmatPretestQuestions",
        "/_anki/gmatSubmitPretest",
        "/_anki/gmatLessonsIndex",
        "/_anki/gmatLesson",
        "/_anki/gmatMarkLearned",
        "/_anki/gmatToday",
        "/_anki/gmatMockQuestions",
        "/_anki/gmatSubmitMock",
        "/_anki/gmatOfficialScores",
        "/_anki/gmatSaveOfficialScore",
        "/_anki/gmatOpenStats",
        "/_anki/gmatOpenDecks",
        "/_anki/gmatSyncNow",
        "/_anki/gmatStats",
        "/_anki/gmatExportState",
        "/_anki/gmatImportState",
        "/_anki/gmatResetState",
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
