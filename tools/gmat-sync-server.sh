#!/usr/bin/env bash
# Run the self-hosted GMATWiz sync server (the engine's built-in Anki sync
# server). Desktop and the phone app sync the same collection through it.
#
# Usage:            ./tools/gmat-sync-server.sh
# Configure via env: GMAT_SYNC_USER (user:pass), GMAT_SYNC_PORT, GMAT_SYNC_BASE
#
# Point clients at:  http://127.0.0.1:${GMAT_SYNC_PORT:-27811}/
#   - Desktop: Preferences -> Syncing -> self-hosted sync server URL, then log
#     in with the user:pass below.
#   - Phone app: matches these defaults (see ios/ContentView.swift).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="pylib:out/pylib"
export SYNC_USER1="${GMAT_SYNC_USER:-gmat:wiz}"
export SYNC_BASE="${GMAT_SYNC_BASE:-$ROOT/out/syncserver}"
export SYNC_HOST="${GMAT_SYNC_HOST:-127.0.0.1}"
export SYNC_PORT="${GMAT_SYNC_PORT:-27811}"

mkdir -p "$SYNC_BASE"
echo "GMATWiz sync server: http://${SYNC_HOST}:${SYNC_PORT}/ (user: ${SYNC_USER1%%:*}, data: $SYNC_BASE)"
exec out/pyenv/bin/python -m anki.syncserver
