#!/usr/bin/env bash
# Copy the bundled web UI + GMATWiz content into ios/Resources so xcodegen can
# add them to the app bundle as folder references (preserving directory layout).
#
# Sources (produced by a desktop build):
#   out/qt/_aqt/data/web/sveltekit/   -> the built SvelteKit "GMATWiz" SPA
#   gmatwiz/lessons, gmatwiz/content  -> lesson + question data (resourceDir)
#
# Run this BEFORE `xcodegen generate` / `xcodebuild` (like build-ios.sh for the
# xcframework). The copied trees are git-ignored build artifacts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WEB_SRC="out/qt/_aqt/data/web/sveltekit"
WEB_DST="ios/Resources/web/sveltekit"
GMAT_DST="ios/Resources/gmatwiz"

if [ ! -f "$WEB_SRC/index.html" ]; then
  echo "ERROR: built SvelteKit app not found at $WEB_SRC" >&2
  echo "       Run a desktop build first so out/qt/_aqt/data/web/sveltekit exists." >&2
  exit 1
fi

rm -rf "ios/Resources/web" "$GMAT_DST"
mkdir -p "$WEB_DST" "$GMAT_DST/lessons" "$GMAT_DST/content"

# The web SPA: copy verbatim (index.html + _app/immutable/...).
rsync -a "$WEB_SRC/" "$WEB_DST/"

# Lesson + content data (the resourceDir). Skip build-time tooling and raw
# scrape datasets; the engine only reads the JSON/HTML at runtime.
rsync -a --exclude '__pycache__' --exclude '*.py' \
  "gmatwiz/lessons/" "$GMAT_DST/lessons/"
rsync -a --exclude '__pycache__' --exclude '*.py' --exclude 'raw' \
  "gmatwiz/content/" "$GMAT_DST/content/"

echo "Synced iOS resources:"
echo "  $WEB_DST"
echo "  $GMAT_DST/{lessons,content}"
