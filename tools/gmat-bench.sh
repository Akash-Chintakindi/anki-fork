#!/usr/bin/env bash
# The single "make bench" command (PRD 14.5 / Challenge 7h): build the shared
# 50,000-card GMAT deck if it is missing, then run the speed benchmark and write
# p50/p95/worst-case + peak memory to proof/bench.txt.
#
# Usage:             ./tools/gmat-bench.sh                 # full 50k run
#                    ./tools/gmat-bench.sh --iters 500     # extra args -> gmat_bench.py
# Configure via env: GMAT_BENCH_COUNT (default 50000)
#                    GMAT_BENCH_SEED  (default 7)
#                    GMAT_BENCH_PATH  (default out/bench/col.anki2)
#                    GMAT_BENCH_SYNC  (default auto: real self-hosted sync, else proxy)
#
# Drives the PREBUILT engine (out/pyenv + out/pylib). It does NOT rebuild the
# project (no ./run, ninja, or cargo).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="out/pyenv/bin/python"
export PYTHONPATH="out/pylib"
export ANKI_TEST_MODE=1

COUNT="${GMAT_BENCH_COUNT:-50000}"
SEED="${GMAT_BENCH_SEED:-7}"
DECK="${GMAT_BENCH_PATH:-out/bench/col.anki2}"
SYNC="${GMAT_BENCH_SYNC:-auto}"

if [ ! -x "$PY" ]; then
  echo "GMATWiz bench: prebuilt python not found at $PY (is the project built?)" >&2
  exit 1
fi

echo "== GMATWiz bench [1/2]: build ${COUNT}-card deck at ${DECK} (idempotent) =="
"$PY" gmatwiz/bench/make_bench_deck.py --path "$DECK" --count "$COUNT" --seed "$SEED"

echo "== GMATWiz bench [2/2]: measure speed targets on the ${COUNT}-card deck =="
"$PY" gmatwiz/bench/gmat_bench.py --path "$DECK" --sync "$SYNC" "$@"

echo "== GMATWiz bench: done -> proof/bench.txt =="
