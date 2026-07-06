#!/usr/bin/env bash
# Challenge 7b sync test: 10+10 offline reviews reconcile with none lost/double-
# counted, then a same-card conflict resolves to a documented winner. Drives the
# self-hosted engine sync server + the real Rust sync. Writes proof/sync-test.txt.
#
# Usage: ./tools/gmat-sync-test.sh
# Drives the PREBUILT engine (out/pyenv + out/pylib); does NOT rebuild the project.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="out/pyenv/bin/python"
export PYTHONPATH="out/pylib"
export ANKI_TEST_MODE=1
if [ ! -x "$PY" ]; then
  echo "GMATWiz sync-test: prebuilt python not found at $PY (is the project built?)" >&2
  exit 1
fi
exec "$PY" tools/gmat-sync-test.py "$@"
