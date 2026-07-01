#!/usr/bin/env bash
# Cross-compile the GMATWiz C FFI (the shared Anki Rust engine) for iOS and
# bundle it as an XCFramework that a Swift app can link.
#
# REQUIRES FULL XCODE (iOS SDK). Until Xcode is installed this will fail at the
# cargo build step with a missing-SDK / linker error - that is the only blocker.
#
# Usage (from anywhere):
#   ./ios/build-ios.sh
#
# Output: out/ios/GmatwizFFI.xcframework  (drag into your Xcode app target)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PROTOC="$ROOT/out/extracted/protoc/bin/protoc"
export CARGO_TARGET_DIR="$ROOT/out/rust"
# Match a modern deployment target so the C deps (zstd/ring/sqlite), which the
# SDK compiles for the current iOS, link cleanly (avoids the ___chkstk_darwin
# undefined-symbol you get when the default min target falls back to iOS 10).
export IPHONEOS_DEPLOYMENT_TARGET="${IPHONEOS_DEPLOYMENT_TARGET:-16.0}"
PROFILE="release"
FEATURES="rustls"
LIB="libgmatwiz_ffi.a"
OUT="$ROOT/out/ios"
HDR="$OUT/headers"

mkdir -p "$HDR"
cp "$ROOT/ffi/include/gmatwiz_ffi.h" "$HDR/"
cp "$ROOT/ios/module.modulemap" "$HDR/"

# Device (arm64) and Simulator (arm64).
cargo build -p gmatwiz_ffi --features "$FEATURES" --release --target aarch64-apple-ios
cargo build -p gmatwiz_ffi --features "$FEATURES" --release --target aarch64-apple-ios-sim

DEVICE_LIB="$CARGO_TARGET_DIR/aarch64-apple-ios/$PROFILE/$LIB"
SIM_LIB="$CARGO_TARGET_DIR/aarch64-apple-ios-sim/$PROFILE/$LIB"

rm -rf "$OUT/GmatwizFFI.xcframework"
xcodebuild -create-xcframework \
  -library "$DEVICE_LIB" -headers "$HDR" \
  -library "$SIM_LIB" -headers "$HDR" \
  -output "$OUT/GmatwizFFI.xcframework"

echo "Created $OUT/GmatwizFFI.xcframework"
