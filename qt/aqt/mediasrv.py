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
# Give-up rule thresholds (PRD Section 4).
GMAT_MEMORY_MIN_REVIEWS = 150


def _gmat_memory(col) -> dict:
    """Calibrated Memory model computed honestly from the review log.

    Point estimate = observed retention (share of graded reviews recalled), with
    a 95% confidence interval. Calibration is shown as a reliability diagram:
    observed retention within each past-interval bucket vs the scheduler's target
    retention. ECE = review-weighted mean gap between observed and target.
    Abstains (give-up rule) until GMAT_MEMORY_MIN_REVIEWS graded reviews exist.
    """
    import math

    total = (
        col.db.scalar("select count() from revlog where ease between 1 and 4") or 0
    )
    if total < GMAT_MEMORY_MIN_REVIEWS:
        return {
            "status": "abstain",
            "reviews": total,
            "reviews_required": GMAT_MEMORY_MIN_REVIEWS,
            "reason": f"Need {GMAT_MEMORY_MIN_REVIEWS} graded reviews; you have {total}.",
            "updated_ts": int(time.time()),
        }

    passed = (
        col.db.scalar("select count() from revlog where ease between 2 and 4") or 0
    )
    observed = passed / total
    se = math.sqrt(observed * (1 - observed) / total)
    low = max(0.0, observed - 1.96 * se)
    high = min(1.0, observed + 1.96 * se)

    try:
        conf = col.decks.config_dict_for_deck_id(col.decks.id("GMAT::Quant"))
        target = float(conf.get("desiredRetention", 0.9))
    except Exception:
        target = 0.9

    # reliability diagram: observed retention by past-interval bucket (days)
    rows = col.db.all(
        "select case "
        "when lastIvl<=3 then 0 when lastIvl<=7 then 1 when lastIvl<=21 then 2 "
        "when lastIvl<=60 then 3 else 4 end as b, "
        "count(), sum(case when ease between 2 and 4 then 1 else 0 end) "
        "from revlog where ease between 1 and 4 and lastIvl >= 1 "
        "group by b order by b"
    )
    labels = ["1-3d", "4-7d", "8-21d", "22-60d", "60d+"]
    bins = []
    binned_total = sum(r[1] for r in rows) or 1
    ece = 0.0
    for b, n, p in rows:
        obs = (p / n) if n else 0.0
        bins.append({"label": labels[int(b)], "observed": round(obs, 3), "n": n})
        ece += (n / binned_total) * abs(obs - target)

    return {
        "status": "shown",
        "point": round(observed * 100),
        "low": round(low * 100),
        "high": round(high * 100),
        "reviews": total,
        "target": round(target * 100),
        "ece": round(ece, 3),
        "calibrated": ece <= 0.10,
        "bins": bins,
        "updated_ts": int(time.time()),
    }


# Give-up thresholds (PRD Section 4).
GMAT_PERF_MIN_ATTEMPTS = 50
GMAT_PERF_MIN_PER_TOPIC = 8
GMAT_READY_MIN_COVERAGE = 50  # percent
GMAT_READY_MIN_REVIEWS = 200
GMAT_READY_MIN_ATTEMPTS = 50
GMAT_READY_MAX_ECE = 0.10


def _gmat_card_topics(col) -> dict:
    """Map GMAT card id -> topic. Bounded by the GMAT deck size."""
    cid_topic: dict = {}
    for nid in col.find_notes('note:"GMAT PS"'):
        note = col.get_note(nid)
        topic = dict(note.items()).get("Topic", "")
        for cid in note.card_ids():
            cid_topic[cid] = topic
    return cid_topic


def _gmat_performance(col) -> dict:
    """Performance model: can the student answer a NEW exam-style question?

    Distinct from Memory (retention of already-seen cards): here we score only
    FIRST-EXPOSURE attempts (revlog rows with lastIvl == 0). Point = observed
    first-try accuracy with a 95% CI. Includes a held-out (train/test) check of a
    per-topic model vs a global-mean baseline (Brier score), per PRD Step 2.
    Abstains until GMAT_PERF_MIN_ATTEMPTS attempts (give-up rule).
    """
    import math

    cid_topic = _gmat_card_topics(col)
    now = int(time.time())
    if not cid_topic:
        return {
            "status": "abstain",
            "attempts": 0,
            "attempts_required": GMAT_PERF_MIN_ATTEMPTS,
            "reason": "No GMAT questions yet - import GMAT Quant.",
            "updated_ts": now,
        }

    rows = col.db.all(
        "select cid, ease from revlog where lastIvl = 0 and ease between 1 and 4"
    )
    attempts = [(cid, 1 if ease >= 2 else 0) for cid, ease in rows if cid in cid_topic]
    total = len(attempts)
    if total < GMAT_PERF_MIN_ATTEMPTS:
        return {
            "status": "abstain",
            "attempts": total,
            "attempts_required": GMAT_PERF_MIN_ATTEMPTS,
            "reason": f"Need {GMAT_PERF_MIN_ATTEMPTS} new-question attempts; you have {total}.",
            "updated_ts": now,
        }

    correct = sum(ok for _, ok in attempts)
    acc = correct / total
    se = math.sqrt(acc * (1 - acc) / total)

    # per-topic accuracy (only where the give-up per-topic threshold is met)
    per_topic: dict = {}
    for cid, ok in attempts:
        pt = per_topic.setdefault(cid_topic[cid], [0, 0])
        pt[0] += ok
        pt[1] += 1
    weak_topics = sorted(
        (
            {"topic": t, "accuracy": round(c / n, 3), "n": n}
            for t, (c, n) in per_topic.items()
            if n >= GMAT_PERF_MIN_PER_TOPIC
        ),
        key=lambda x: x["accuracy"],
    )

    # held-out eval: per-topic model vs global-mean baseline (Brier, lower=better)
    train = [(cid, ok) for cid, ok in attempts if (cid % 10) < 7]
    test = [(cid, ok) for cid, ok in attempts if (cid % 10) >= 7]
    eval_out = None
    if train and test:
        g_mean = sum(ok for _, ok in train) / len(train)
        topic_mean: dict = {}
        tt: dict = {}
        for cid, ok in train:
            m = tt.setdefault(cid_topic[cid], [0, 0])
            m[0] += ok
            m[1] += 1
        for t, (c, n) in tt.items():
            topic_mean[t] = c / n
        base_brier = sum((g_mean - ok) ** 2 for _, ok in test) / len(test)
        model_brier = sum(
            (topic_mean.get(cid_topic[cid], g_mean) - ok) ** 2 for cid, ok in test
        ) / len(test)
        eval_out = {
            "baseline_brier": round(base_brier, 4),
            "model_brier": round(model_brier, 4),
            "beats_baseline": model_brier <= base_brier,
            "test_n": len(test),
        }

    return {
        "status": "shown",
        "point": round(acc * 100),
        "low": round(max(0.0, acc - 1.96 * se) * 100),
        "high": round(min(1.0, acc + 1.96 * se) * 100),
        "attempts": total,
        "weak_topics": weak_topics[:5],
        "eval": eval_out,
        "updated_ts": now,
    }


def _accuracy_to_quant_score(acc: float) -> float:
    """Transparent (heuristic, not yet validated) map: first-exposure accuracy
    -> GMAT Focus Quant section score (60-90). Anchors: 0.40->70, 0.90->88."""
    score = 70.0 + (acc - 0.40) * (88.0 - 70.0) / (0.90 - 0.40)
    return max(60.0, min(90.0, score))


def _gmat_readiness(col, memory: dict, performance: dict, coverage_pct: float) -> dict:
    """Readiness: projected GMAT Focus QUANT section score (60-90) with a range.

    Gated by the full give-up rule (PRD Section 4). Honest by construction: the
    total (205-805) is abstained because we have no Verbal/Data Insights data,
    and the accuracy->score mapping is a documented heuristic not yet validated
    against official practice-test scores (PRD Step 4).
    """
    now = int(time.time())
    reviews = memory.get("reviews", 0)
    attempts = performance.get("attempts", 0)
    ece = memory.get("ece")
    unmet = []
    if coverage_pct < GMAT_READY_MIN_COVERAGE:
        unmet.append(
            f"topic coverage {round(coverage_pct)}% (need {GMAT_READY_MIN_COVERAGE}%)"
        )
    if reviews < GMAT_READY_MIN_REVIEWS:
        unmet.append(f"{reviews} reviews (need {GMAT_READY_MIN_REVIEWS})")
    if attempts < GMAT_READY_MIN_ATTEMPTS:
        unmet.append(f"{attempts} application attempts (need {GMAT_READY_MIN_ATTEMPTS})")
    if ece is None or ece > GMAT_READY_MAX_ECE:
        unmet.append("memory not yet calibrated (ECE <= 0.10)")

    if unmet:
        return {
            "status": "abstain",
            "unmet": unmet,
            "reason": "A confident number with no evidence is just a guess.",
            "updated_ts": now,
        }

    acc = performance["point"] / 100.0
    acc_low = performance["low"] / 100.0
    acc_high = performance["high"] / 100.0
    point = round(_accuracy_to_quant_score(acc))
    low = round(_accuracy_to_quant_score(acc_low))
    high = round(_accuracy_to_quant_score(acc_high))
    confidence = "low"
    if coverage_pct >= 80 and attempts >= 150:
        confidence = "medium"
    return {
        "status": "shown",
        "section": "Quant",
        "point": point,
        "low": low,
        "high": high,
        "scale": "GMAT Focus Quant section (60-90)",
        "confidence": confidence,
        "method": "Heuristic map from held-out first-exposure accuracy; not yet "
        "validated against official practice-test scores.",
        "total_status": "abstain",
        "total_reason": "Total (205-805) needs Verbal + Data Insights data (not yet in scope).",
        "updated_ts": now,
    }


def gmat_overview() -> bytes:
    """Headline stats for the GMATWiz home + dashboard (honesty rule)."""
    col = aqt.mw.col
    try:
        total = len(col.find_cards('note:"GMAT PS"'))
        new = len(col.find_cards('note:"GMAT PS" is:new'))
        due = len(col.find_cards('note:"GMAT PS" (is:due OR is:learn)'))
    except Exception:
        total = new = due = 0

    topics = set()
    try:
        for nid in col.find_notes('note:"GMAT PS"'):
            topic = dict(col.get_note(nid).items()).get("Topic", "")
            if topic:
                topics.add(topic)
    except Exception:
        pass

    reviews = col.db.scalar("select count() from revlog") or 0
    coverage_pct = (
        100.0 * len(topics) / GMAT_QUANT_TOPIC_TOTAL if GMAT_QUANT_TOPIC_TOTAL else 0.0
    )
    memory = _gmat_memory(col)
    performance = _gmat_performance(col)
    readiness = _gmat_readiness(col, memory, performance, coverage_pct)

    return json.dumps(
        {
            "deck": "GMAT::Quant",
            "total": total,
            "new": new,
            "due": due,
            "reviews": reviews,
            "topics_covered": len(topics),
            "topics_total": GMAT_QUANT_TOPIC_TOTAL,
            "memory": memory,
            "performance": performance,
            "readiness": readiness,
            "profile": col.get_config("gmatProfile", None),
            "plan": col.get_config("gmatPlan", None),
        }
    ).encode("utf-8")


def gmat_error_log() -> bytes:
    """Return the student's logged errors (most recent first)."""
    col = aqt.mw.col
    entries = col.get_config("gmatErrorLog", []) or []
    return json.dumps({"entries": list(reversed(entries))}).encode("utf-8")


def gmat_log_error() -> bytes:
    """Append a missed question to the error log. Body: JSON entry."""
    col = aqt.mw.col
    try:
        entry = json.loads(request.data or b"{}")
    except Exception:
        entry = {}
    entries = col.get_config("gmatErrorLog", []) or []
    entries.append(
        {
            "stem": str(entry.get("stem", ""))[:400],
            "topic": str(entry.get("topic", "")),
            "chosen": str(entry.get("chosen", "")),
            "correct": str(entry.get("correct", "")),
            "ts": int(time.time()),
        }
    )
    col.set_config("gmatErrorLog", entries[-500:])
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
    return b""


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


def gmat_lesson() -> bytes:
    """Return the full authored lesson for a topic_id."""
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    topic_id = str(body.get("topic_id", ""))
    index = _load_lessons_index()
    json_name = None
    for t in index.get("topics", []):
        if t.get("topic_id") == topic_id:
            json_name = t.get("json") or ((t.get("slug") or "") + ".json")
            break
    if not json_name:
        return json.dumps({"lesson": None}).encode("utf-8")
    path = os.path.join(_gmat_lessons_dir(), json_name)
    try:
        with open(path, encoding="utf-8") as f:
            lesson = json.load(f)
    except Exception:
        lesson = None
    return json.dumps({"lesson": lesson}).encode("utf-8")


def gmat_mark_learned() -> bytes:
    """Record that the student completed a topic's lesson."""
    col = aqt.mw.col
    try:
        body = json.loads(request.data or b"{}")
    except Exception:
        body = {}
    topic_id = str(body.get("topic_id", ""))
    if topic_id:
        learned = col.get_config("gmatLearned", {}) or {}
        learned[topic_id] = int(time.time())
        col.set_config("gmatLearned", learned)
    return b""


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
