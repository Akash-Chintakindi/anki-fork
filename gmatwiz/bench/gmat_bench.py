#!/usr/bin/env python3
"""One-command speed benchmark for GMATWiz on the shared 50,000-card deck.

Implements PRD 14.5 (the "make bench" one-command benchmark) and reports the
14.6 speed targets as p50 / p95 / worst-case (never a single cherry-picked
number), each with an HONEST PASS/FAIL on THIS machine:

  action                       measured as                                   target (p95)
  ---------------------------  --------------------------------------------  ------------
  Button press acknowledged    _backend.get_scheduling_states + build_answer  < 50 ms
  Next card after grading      answer_card + getCard                          < 100 ms
  Dashboard first load         first _backend.gmat_scores() on a fresh open   < 1000 ms
  Dashboard refresh            subsequent _backend.gmat_scores() calls        < 500 ms
  Sync of a normal session     self-hosted sync of a few-review delta         < 5000 ms
  Memory on 50k cards          peak RSS (ru_maxrss) for the whole run         (stated limit)

The dashboard path timed here is EXACTLY the one the app serves: qt/aqt/mediasrv.py
`_gmat_scores` calls `col._backend.gmat_scores()`.

Sync: if the self-hosted engine sync server (`python -m anki.syncserver`, the same
one tools/gmat-sync-server.sh runs) is reachable, we measure a REAL incremental
sync of a normal session. If it can't be started/reached we fall back to a clearly
labeled LOCAL proxy (save + close + reopen round-trip) and say so.

Run (drive the prebuilt engine; do NOT rebuild the project):
  PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python \
      gmatwiz/bench/gmat_bench.py --path out/bench/col.anki2
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import platform
import resource
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from time import perf_counter

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
_OUT_PYLIB = _REPO / "out" / "pylib"
_PYLIB = _REPO / "pylib"
for _p in (str(_OUT_PYLIB),):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from anki.collection import Collection  # noqa: E402
from anki.scheduler.v3 import CardAnswer  # noqa: E402
from anki.utils import int_time  # noqa: E402

DECK_NAME = "GMAT::Quant"
DEFAULT_MEMORY_LIMIT_MB = 2048  # stated desktop limit for the PASS/FAIL call
MAX_PER_DAY = 9999  # engine caps deck-config perDay at 9999 (above it reverts)

# Spec targets (PRD 14.6), compared against p95.
TARGETS_MS = {
    "button_ack": 50.0,
    "next_card": 100.0,
    "dash_first": 1000.0,
    "dash_refresh": 500.0,
    "sync_session": 5000.0,
}
LABELS = {
    "button_ack": "Button press acknowledged",
    "next_card": "Next card after grading",
    "dash_first": "Dashboard first load",
    "dash_refresh": "Dashboard refresh",
    "sync_session": "Sync of a normal session",
}


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
def percentile(values: list[float], p: float) -> float:
    """p-th percentile with linear interpolation (numpy 'linear' / type 7)."""
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (p / 100.0) * (len(s) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (rank - lo)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p50": float("nan"), "p95": float("nan"),
                "worst": float("nan"), "min": float("nan"), "mean": float("nan")}
    return {
        "n": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "worst": max(values),
        "min": min(values),
        "mean": sum(values) / len(values),
    }


# ---------------------------------------------------------------------------
# machine info
# ---------------------------------------------------------------------------
def _sysctl(key: str) -> str | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _total_ram_bytes() -> int | None:
    mem = _sysctl("hw.memsize")
    if mem:
        try:
            return int(mem)
        except ValueError:
            pass
    try:  # subprocess-free fallback (works even when sysctl is unavailable)
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def machine_info() -> dict:
    cpu = (
        _sysctl("machdep.cpu.brand_string")
        or platform.processor()
        or platform.machine()
        or "unknown"
    )
    mem_bytes = _total_ram_bytes()
    ram_gb = round(mem_bytes / (1024 ** 3), 1) if mem_bytes else None
    try:
        from anki.buildinfo import buildhash, version as _v

        anki_ver = f"{_v} ({buildhash})"
    except Exception:
        anki_ver = "?"
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "ram_gb": ram_gb,
        "python": platform.python_version(),
        "anki_version": anki_ver,
    }


def peak_rss_mb() -> float:
    """Peak resident set size of THIS process, in MB (handles macOS vs Linux)."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports kilobytes.
    if sys.platform == "darwin":
        return ru / (1024 ** 2)
    return ru / 1024.0


# ---------------------------------------------------------------------------
# engine helpers
# ---------------------------------------------------------------------------
def _open(path: str) -> Collection:
    return Collection(path)


def _prepare(col: Collection) -> None:
    """Ensure the topic-aware toggle + generous limits are active, deck selected."""
    col.set_config("topicAwareScheduling", True)
    did = col.decks.id(DECK_NAME)
    col.decks.select(did)
    conf = col.decks.config_dict_for_deck_id(did)
    if conf["new"]["perDay"] < MAX_PER_DAY or conf["rev"]["perDay"] < MAX_PER_DAY:
        conf["new"]["perDay"] = MAX_PER_DAY
        conf["rev"]["perDay"] = MAX_PER_DAY
        col.decks.update_config(conf)


def _do_reviews(col: Collection, n: int) -> int:
    """Grade up to n cards (a normal session's worth). Returns count graded."""
    col.decks.select(col.decks.id(DECK_NAME))
    done = 0
    for _ in range(n):
        q = col.sched.get_queued_cards(fetch_limit=1)
        if not q.cards:
            break
        c = q.cards[0]
        col.sched.answer_card(
            CardAnswer(
                card_id=c.card.id,
                current_state=c.states.current,
                new_state=c.states.good,
                rating=CardAnswer.GOOD,
                answered_at_millis=int_time(1000),
                milliseconds_taken=1500,
            )
        )
        done += 1
    return done


# ---------------------------------------------------------------------------
# measurements
# ---------------------------------------------------------------------------
def measure_dashboard_first(path: str, reopens: int) -> list[float]:
    """Time the FIRST gmat_scores() after each fresh collection open."""
    samples: list[float] = []
    for _ in range(reopens):
        c = _open(path)
        try:
            t0 = perf_counter()
            c._backend.gmat_scores()
            samples.append((perf_counter() - t0) * 1000.0)
        finally:
            c.close()
    return samples


def measure_dashboard_refresh(col: Collection, count: int) -> list[float]:
    """Time repeated gmat_scores() calls on an already-open collection."""
    col._backend.gmat_scores()  # warm (this call is the 'first load' equivalent)
    samples: list[float] = []
    for _ in range(count):
        t0 = perf_counter()
        col._backend.gmat_scores()
        samples.append((perf_counter() - t0) * 1000.0)
    return samples


def measure_review_loop(path: str, iters: int, warmup: int):
    """Open a fresh copy and measure a review session.

    Returns (button_ack_ms, next_card_ms, cold_build_ms). cold_build_ms is the
    one-time cost of the FIRST getCard on a cold open (the session-start queue
    build over the 50k deck) - reported separately so steady-state next-card is
    not inflated by it and nothing is hidden.
    """
    button: list[float] = []
    nextc: list[float] = []

    col = _open(path)
    _prepare(col)
    try:
        t0 = perf_counter()
        card = col.sched.getCard()  # cold: builds the session queue over the deck
        cold_build_ms = (perf_counter() - t0) * 1000.0
        if card is None:
            raise RuntimeError("no cards in queue - is the deck built and schedulable?")

        button, nextc = _run_review_iters(col, card, iters, warmup)
    finally:
        col.close()
    return button, nextc, cold_build_ms


def _run_review_iters(col: Collection, card, iters: int, warmup: int):
    button: list[float] = []
    nextc: list[float] = []

    # warmup (settle queue caches / learning queue) - not measured
    for _ in range(warmup):
        if card is None:
            card = col.sched.getCard()
            if card is None:
                break
        states = col._backend.get_scheduling_states(card.id)
        answer = col.sched.build_answer(card=card, states=states, rating=CardAnswer.GOOD)
        col.sched.answer_card(answer)
        card = col.sched.getCard()

    for _ in range(iters):
        if card is None:
            card = col.sched.getCard()
            if card is None:
                break
        # (a) button press acknowledged: compute next states + build the answer
        t0 = perf_counter()
        states = col._backend.get_scheduling_states(card.id)
        answer = col.sched.build_answer(card=card, states=states, rating=CardAnswer.GOOD)
        button.append((perf_counter() - t0) * 1000.0)

        # (b) next card after grading: apply the answer, fetch the next card
        t1 = perf_counter()
        col.sched.answer_card(answer)
        card = col.sched.getCard()
        nextc.append((perf_counter() - t1) * 1000.0)

    return button, nextc


# ---------------------------------------------------------------------------
# sync (real self-hosted server) with a labeled local proxy fallback
# ---------------------------------------------------------------------------
def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_port(host: str, port: int, proc, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False  # server died
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def measure_sync_real(path: str, cycles: int, reviews_per: int, timeout: float):
    """Measure REAL incremental syncs of a normal session against the self-hosted
    engine sync server. Returns (samples_ms, meta) or (None, meta) on failure."""
    meta: dict = {"mode": "real", "ok": False, "note": ""}
    workdir = tempfile.mkdtemp(prefix="gmatbench-sync-")
    copy_path = os.path.join(workdir, "synccopy.anki2")
    base = os.path.join(workdir, "server")
    os.makedirs(base, exist_ok=True)
    shutil.copy(path, copy_path)

    port = _free_port()
    host = "127.0.0.1"
    endpoint = f"http://{host}:{port}/"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [p for p in (str(_PYLIB), str(_OUT_PYLIB)) if os.path.isdir(p)]
    )
    env["SYNC_USER1"] = "gmat:wiz"
    env["SYNC_BASE"] = base
    env["SYNC_HOST"] = host
    env["SYNC_PORT"] = str(port)
    server_log = open(os.path.join(workdir, "server.log"), "w")
    python = sys.executable
    proc = subprocess.Popen(
        [python, "-m", "anki.syncserver"], env=env, stdout=server_log, stderr=server_log
    )
    col = None
    samples: list[float] = []
    try:
        if not _wait_port(host, port, proc, timeout):
            meta["note"] = "sync server did not become reachable"
            return None, meta

        col = _open(copy_path)
        auth = col.sync_login("gmat", "wiz", endpoint)
        out = col.sync_collection(auth, False)
        full = {out.FULL_SYNC, out.FULL_DOWNLOAD, out.FULL_UPLOAD}
        if out.required in full:
            # First sync of a brand-new collection requires a one-time full upload
            # of the 50k deck (timed as setup, NOT the < 5 s target). The same
            # collection handle stays usable for incremental syncs afterwards
            # (mirrors tools/../sync_proof.sh), so do NOT reopen here.
            t0 = perf_counter()
            col.full_upload_or_download(auth=auth, server_usn=None, upload=True)
            meta["full_upload_ms"] = (perf_counter() - t0) * 1000.0

        for _ in range(cycles):
            graded = _do_reviews(col, reviews_per)
            t0 = perf_counter()
            col.sync_collection(auth, False)
            samples.append((perf_counter() - t0) * 1000.0)
            if graded == 0:
                break

        meta["ok"] = True
        meta["note"] = (
            f"real self-hosted sync ({reviews_per} reviews/session); first full "
            f"upload of the 50k deck timed separately as setup, not the target."
        )
        return samples, meta
    except Exception as exc:  # noqa: BLE001 - degrade cleanly to the proxy
        meta["note"] = f"real sync unavailable: {exc}"
        return None, meta
    finally:
        try:
            if col is not None:
                col.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        server_log.close()


def measure_sync_proxy(path: str, cycles: int, reviews_per: int):
    """Labeled LOCAL proxy: time save + close + reopen of a normal-session delta.
    This is NOT a network sync; it measures the local persist/round-trip cost."""
    meta = {
        "mode": "proxy",
        "ok": True,
        "note": (
            "LOCAL proxy (no network): per cycle = grade a few cards (auto-saved "
            "per answer) then close + reopen the collection. Stands in for the "
            "commit + session round-trip cost when the self-hosted sync server is "
            "not reachable; it is NOT a network sync."
        ),
    }
    workdir = tempfile.mkdtemp(prefix="gmatbench-proxy-")
    copy_path = os.path.join(workdir, "proxycopy.anki2")
    shutil.copy(path, copy_path)
    samples: list[float] = []
    col = _open(copy_path)
    try:
        for _ in range(cycles):
            _do_reviews(col, reviews_per)
            t0 = perf_counter()
            col.close()  # flushes + releases (answers were already auto-saved)
            col = _open(copy_path)  # re-establish the session
            samples.append((perf_counter() - t0) * 1000.0)
        return samples, meta
    finally:
        try:
            col.close()
        except Exception:
            pass


def measure_sync(path: str, mode: str, cycles: int, reviews_per: int, timeout: float):
    if mode in ("real", "auto"):
        samples, meta = measure_sync_real(path, cycles, reviews_per, timeout)
        if samples:
            return samples, meta
        if mode == "real":
            return samples, meta
        # auto: fall back to proxy
        proxy_samples, proxy_meta = measure_sync_proxy(path, cycles, reviews_per)
        proxy_meta["note"] += f"  [real sync skipped: {meta.get('note','')}]"
        return proxy_samples, proxy_meta
    if mode == "proxy":
        return measure_sync_proxy(path, cycles, reviews_per)
    return None, {"mode": "off", "ok": False, "note": "sync measurement disabled"}


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def _fmt_ms(v: float) -> str:
    if v != v:  # nan
        return "   -  "
    return f"{v:8.2f}"


def verdict(p95: float, target: float) -> str:
    if p95 != p95:
        return "N/A "
    return "PASS" if p95 <= target else "FAIL"


def build_report(args, info, deck, results, sync_samples, sync_meta, peak_mb, cold_build_ms) -> dict:
    stats = {k: summarize(v) for k, v in results.items()}
    sync_stats = summarize(sync_samples or [])
    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "machine": info,
        "deck": deck,
        "iterations": {
            "review_iters": args.iters,
            "reopens": args.reopens,
            "refresh": args.refresh,
            "sync_cycles": args.sync_cycles,
            "reviews_per_session": args.reviews_per,
        },
        "targets_ms": TARGETS_MS,
        "results_ms": {
            **{k: stats[k] for k in ("button_ack", "next_card", "dash_first", "dash_refresh")},
            "sync_session": sync_stats,
        },
        "cold_queue_build_ms": round(cold_build_ms, 2),
        "sync": sync_meta | {"full_upload_ms": sync_meta.get("full_upload_ms")},
        "memory": {
            "peak_rss_mb": round(peak_mb, 1),
            "limit_mb": args.memory_limit_mb,
            "pass": peak_mb <= args.memory_limit_mb,
        },
    }


def write_proof(report: dict, out_path: str) -> None:
    info = report["machine"]
    deck = report["deck"]
    res = report["results_ms"]

    def row(key):
        s = res[key]
        return (
            f"{LABELS[key]:<28}{s['n']:>6}"
            f"{_fmt_ms(s['p50'])}{_fmt_ms(s['p95'])}{_fmt_ms(s['worst'])}"
            f"{TARGETS_MS[key]:>10.0f}   {verdict(s['p95'], TARGETS_MS[key])}"
        )

    order = ["button_ack", "next_card", "dash_first", "dash_refresh", "sync_session"]
    lines = []
    lines.append("=" * 79)
    lines.append("GMATWiz - ONE-COMMAND SPEED BENCHMARK  (Challenge 7h; PRD 14.5 / 14.6)")
    lines.append("=" * 79)
    lines.append(
        "What this proves: on a SHARED 50,000-card deck, each interactive action is\n"
        "measured over many iterations and reported as p50 / p95 / worst-case (no\n"
        "cherry-picked number), each with an honest PASS/FAIL vs its PRD 14.6 target\n"
        "on THIS machine. The dashboard path timed is the exact one the app serves\n"
        "(qt/aqt/mediasrv.py _gmat_scores -> col._backend.gmat_scores())."
    )
    lines.append("")
    lines.append("-" * 79)
    lines.append("REPRODUCE")
    lines.append("-" * 79)
    lines.append("  # one command (builds the 50k deck if missing, then benchmarks):")
    lines.append("  ./tools/gmat-bench.sh")
    lines.append("")
    lines.append("  # or drive the prebuilt engine directly (do NOT rebuild the project):")
    lines.append(
        "  PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python \\\n"
        "      gmatwiz/bench/make_bench_deck.py --path out/bench/col.anki2 --count 50000 --seed 7"
    )
    lines.append(
        "  PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python \\\n"
        "      gmatwiz/bench/gmat_bench.py --path out/bench/col.anki2"
    )
    lines.append("")
    lines.append("-" * 79)
    lines.append("MACHINE")
    lines.append("-" * 79)
    lines.append(f"  platform     : {info['platform']}")
    lines.append(f"  cpu          : {info['cpu']}  ({info['logical_cpus']} logical cores)")
    lines.append(f"  ram          : {info['ram_gb']} GB")
    lines.append(f"  python       : {info['python']}   anki: {info['anki_version']}")
    lines.append(f"  generated_at : {report['generated_at']}")
    lines.append("")
    lines.append("-" * 79)
    lines.append("DECK UNDER TEST")
    lines.append("-" * 79)
    lines.append(
        f"  {deck['cards']} cards / {deck['notes']} notes in {DECK_NAME}, across "
        f"{deck['topics']} Quant leaves"
    )
    lines.append(
        f"  full deck composition: new={deck['new']}  review={deck['review']}  "
        f"learning={deck['learning']}  revlog={deck['revlog']}"
    )
    lines.append(
        f"  active session queue (engine caps perDay at {MAX_PER_DAY}): "
        f"new={deck.get('queued_new')}  review={deck.get('queued_review')}  "
        f"learning={deck.get('queued_learning')}"
    )
    lines.append(
        f"  topic-aware scheduling: {'ON' if deck['topic_aware'] else 'off'}  "
        f"(per-topic mastery set so the review reorder path does real work)"
    )
    lines.append("")
    lines.append("-" * 79)
    lines.append("RESULTS  (milliseconds; PASS/FAIL is p95 vs target on THIS machine)")
    lines.append("-" * 79)
    lines.append(
        f"{'action':<28}{'n':>6}{'p50':>8}{'p95':>8}{'worst':>8}{'target':>10}   verdict"
    )
    lines.append("-" * 79)
    for key in order:
        lines.append(row(key))
    lines.append("-" * 79)

    mem = report["memory"]
    mem_verdict = "PASS" if mem["pass"] else "FAIL"
    lines.append(
        f"{'Memory (peak RSS, 50k)':<28}{'':>6}{'':>8}{'':>8}"
        f"{mem['peak_rss_mb']:>8.0f}{mem['limit_mb']:>10.0f}   {mem_verdict}   (MB)"
    )
    lines.append("")
    lines.append(
        f"Informational: cold session-start queue build (first getCard over the deck) "
        f"= {report['cold_queue_build_ms']:.1f} ms."
    )
    lines.append(
        "  (One-time per session; excluded from steady-state 'next card' above so that "
        "metric\n   is not inflated. Shown here so the 50k-scale scheduling cost is not hidden.)"
    )
    lines.append("")
    lines.append("-" * 79)
    lines.append("SYNC DETAIL")
    lines.append("-" * 79)
    sync = report["sync"]
    lines.append(f"  mode measured : {sync['mode']}  (ok={sync['ok']})")
    if sync.get("full_upload_ms"):
        lines.append(
            f"  first full upload of the 50k deck: {sync['full_upload_ms']:.0f} ms "
            f"(one-time setup, NOT the < 5 s target)"
        )
    lines.append(f"  note          : {sync['note']}")
    lines.append("")
    lines.append("-" * 79)
    lines.append("HONEST INTERPRETATION")
    lines.append("-" * 79)
    lines.append(_interpretation(report))
    lines.append("=" * 79)
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _interpretation(report: dict) -> str:
    res = report["results_ms"]
    parts = []
    passed = []
    failed = []
    for key in ("button_ack", "next_card", "dash_first", "dash_refresh", "sync_session"):
        s = res[key]
        if s["n"] == 0:
            continue
        (passed if s["p95"] <= TARGETS_MS[key] else failed).append(LABELS[key])
    if passed:
        parts.append("PASS on this machine: " + "; ".join(passed) + ".")
    if failed:
        parts.append("FAIL on this machine: " + "; ".join(failed) + ".")
    mem = report["memory"]
    parts.append(
        f"Peak memory for the whole 50k run was {mem['peak_rss_mb']:.0f} MB against a "
        f"stated {mem['limit_mb']} MB desktop limit ({'within' if mem['pass'] else 'over'} limit)."
    )
    parts.append(
        "Numbers are wall-clock in the Python-driven engine (same Rust core desktop\n"
        "and phone share); worst-case includes cold caches and GC pauses, which is why\n"
        "it is reported alongside p50/p95 rather than hidden. p95 is the target metric."
    )
    if report["sync"]["mode"] == "proxy":
        parts.append(
            "Sync shows the LOCAL proxy (save+close+reopen), not a network sync, because\n"
            "the self-hosted server was not reachable in this run; rerun where 127.0.0.1\n"
            "sync is allowed to record a real incremental-sync number."
        )
    return "\n".join(parts)


def print_table(report: dict) -> None:
    res = report["results_ms"]
    print()
    print("GMATWiz speed benchmark (50k deck)  -  p50 / p95 / worst (ms)")
    print("-" * 79)
    print(f"{'action':<28}{'n':>6}{'p50':>8}{'p95':>8}{'worst':>8}{'target':>10}   verdict")
    print("-" * 79)
    for key in ("button_ack", "next_card", "dash_first", "dash_refresh", "sync_session"):
        s = res[key]
        print(
            f"{LABELS[key]:<28}{s['n']:>6}{_fmt_ms(s['p50'])}{_fmt_ms(s['p95'])}"
            f"{_fmt_ms(s['worst'])}{TARGETS_MS[key]:>10.0f}   {verdict(s['p95'], TARGETS_MS[key])}"
        )
    print("-" * 79)
    mem = report["memory"]
    print(
        f"{'Memory (peak RSS, 50k)':<28}{'':>6}{'':>8}{'':>8}"
        f"{mem['peak_rss_mb']:>8.0f}{mem['limit_mb']:>10.0f}   "
        f"{'PASS' if mem['pass'] else 'FAIL'}   (MB)"
    )
    print("-" * 79)
    print(
        f"cold session-start queue build (informational): "
        f"{report['cold_queue_build_ms']:.1f} ms"
    )
    print()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def collect_deck_info(col: Collection) -> dict:
    q_new, q_learning, q_review = col.sched.counts()  # gathered (capped at perDay)
    try:
        topics = len([t for t in col.tags.all() if t.startswith("gmat::")])
    except Exception:
        topics = 0
    # DB-level composition of the full 50k (not capped by perDay).
    db_new = col.db.scalar("select count() from cards where queue=0") or 0
    db_review = col.db.scalar("select count() from cards where queue=2") or 0
    db_learn = col.db.scalar("select count() from cards where queue in (1,3)") or 0
    return {
        "cards": col.card_count(),
        "notes": col.note_count(),
        "new": db_new,
        "learning": db_learn,
        "review": db_review,
        "queued_new": q_new,
        "queued_learning": q_learning,
        "queued_review": q_review,
        "revlog": col.db.scalar("select count() from revlog") or 0,
        "topics": topics,
        "topic_aware": bool(col.get_config("topicAwareScheduling", False)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GMATWiz 50k speed benchmark.")
    parser.add_argument(
        "--path",
        default=str(_REPO / "out" / "bench" / "col.anki2"),
        help="Path to the built 50k .anki2 deck.",
    )
    parser.add_argument("--iters", type=int, default=3000, help="Review-loop iterations.")
    parser.add_argument("--warmup", type=int, default=50, help="Un-timed warmup reviews.")
    parser.add_argument("--reopens", type=int, default=8, help="Dashboard first-load samples (fresh opens).")
    parser.add_argument("--refresh", type=int, default=50, help="Dashboard refresh samples.")
    parser.add_argument("--sync", choices=["auto", "real", "proxy", "off"], default="auto")
    parser.add_argument("--sync-cycles", type=int, default=6, help="Sync sessions to time.")
    parser.add_argument("--reviews-per", type=int, default=5, help="Reviews per synced session.")
    parser.add_argument("--sync-timeout", type=float, default=30.0, help="Sync server startup timeout (s).")
    parser.add_argument("--memory-limit-mb", type=int, default=DEFAULT_MEMORY_LIMIT_MB)
    parser.add_argument("--out", default=str(_REPO / "proof" / "bench.txt"))
    parser.add_argument("--json", default=str(_REPO / "proof" / "bench_report.json"))
    args = parser.parse_args(argv)

    if not os.path.isfile(args.path):
        print(f"Deck not found: {args.path}\nBuild it first with make_bench_deck.py "
              f"or run tools/gmat-bench.sh", file=sys.stderr)
        return 2

    info = machine_info()
    print(f"Machine: {info['cpu']} / {info['ram_gb']}GB / py{info['python']}")

    # 1) Dashboard first load (fresh opens) - measured on the pristine canonical
    #    deck before anything mutates it. gmat_scores() is read-only (no save()).
    print(f"[1/5] dashboard first-load x{args.reopens} (fresh opens) ...", flush=True)
    dash_first = measure_dashboard_first(args.path, args.reopens)

    # Work on a copy for the mutating measurements (refresh + review loop) so the
    # canonical 50k deck stays pristine and the benchmark is repeatable.
    work_dir = tempfile.mkdtemp(prefix="gmatbench-work-")
    work_path = os.path.join(work_dir, "work.anki2")
    shutil.copy(args.path, work_path)
    col = _open(work_path)
    _prepare(col)
    deck = collect_deck_info(col)
    print(f"      deck: {deck['cards']} cards (new={deck['new']} rev={deck['review']} "
          f"lrn={deck['learning']}), revlog={deck['revlog']}, topic_aware={deck['topic_aware']}")

    # 2) Dashboard refresh
    print(f"[2/5] dashboard refresh x{args.refresh} ...", flush=True)
    dash_refresh = measure_dashboard_refresh(col, args.refresh)
    col.close()

    # 3) button-ack + next-card (reopens the copy fresh -> also times the cold
    #    session-start queue build over the 50k deck)
    print(f"[3/5] review loop x{args.iters} (button-ack + next-card) ...", flush=True)
    button, nextc, cold_build_ms = measure_review_loop(work_path, args.iters, args.warmup)
    print(f"      cold queue build (session start): {cold_build_ms:.1f} ms")

    # 4) sync of a normal session
    print(f"[4/5] sync ({args.sync}) x{args.sync_cycles} sessions ...", flush=True)
    sync_samples, sync_meta = measure_sync(
        args.path, args.sync, args.sync_cycles, args.reviews_per, args.sync_timeout
    )

    # 5) memory (peak over the whole run)
    peak_mb = peak_rss_mb()
    print(f"[5/5] peak RSS: {peak_mb:.0f} MB")

    results = {
        "button_ack": button,
        "next_card": nextc,
        "dash_first": dash_first,
        "dash_refresh": dash_refresh,
    }
    report = build_report(
        args, info, deck, results, sync_samples, sync_meta, peak_mb, cold_build_ms
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    write_proof(report, args.out)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
        fh.write("\n")

    print_table(report)
    print(f"Wrote proof -> {args.out}")
    print(f"Wrote report -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
