#!/usr/bin/env bash
# GMATWiz 7g proof: crash-durability (20 SIGKILLs mid-review, zero corruption)
# + offline/AI-degrade (scores still compute with AI off). Drives the PREBUILT
# engine - does NOT rebuild anything.
#
# Usage:            ./tools/gmat-crash-test.sh
# Writes:           proof/crash-offline.txt  +  proof/crash-offline.json
# Env overrides:    GMAT_CRASH_RUNS (default 20), GMAT_CRASH_SEED (default 1234)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="out/pyenv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "error: prebuilt python not found at $PY (build the project first)" >&2
  exit 1
fi

# Prove the offline/degrade claim honestly: run with no AI key in the env.
unset OPENAI_API_KEY GEMINI_API_KEY || true

echo "GMATWiz 7g crash + offline/degrade proof -> proof/crash-offline.txt"
PYTHONPATH="out/pylib" ANKI_TEST_MODE=1 "$PY" tools/gmat-crash-test.py \
  --runs "${GMAT_CRASH_RUNS:-20}" \
  --seed "${GMAT_CRASH_SEED:-1234}" \
  "$@"
