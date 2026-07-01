# GMATWiz - Things to do AFTER Xcode is installed

The desktop gating work is done and verified. The shared Rust engine already
compiles and runs through the C FFI on the host (`gmatwiz_buildhash` returned the
real engine hash `b00308e5`). The ONLY thing blocked is cross-compiling that
engine for iOS, which needs the iOS SDK from full Xcode.

## 0. Install + select Xcode (one-time)
- [ ] Install Xcode from the App Store; open it once to finish component install.
- [ ] `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`
- [ ] `sudo xcodebuild -license accept`
- [ ] Verify: `xcrun --sdk iphonesimulator --show-sdk-path` prints a path (not empty).

## A. Cross-compile the shared engine for iOS
- [ ] Run `./ios/build-ios.sh` from the repo root.
  - Cross-compiles `gmatwiz_ffi` for `aarch64-apple-ios` + `aarch64-apple-ios-sim`
    (targets already installed) and bundles `out/ios/GmatwizFFI.xcframework`.
  - If a C dependency (rusqlite/bundled sqlite, zstd-sys, xz2) fails to cross-compile,
    fix the iOS toolchain/sysroot config and re-run (note the error for triage).

## A2. Minimal Swift app on the shared engine
- [ ] Create an Xcode app target "GMATWizPhone" (SwiftUI).
- [ ] Add `out/ios/GmatwizFFI.xcframework`, `ios/GmatwizEngine.swift`, `ios/ContentView.swift`.
- [ ] Build + run on the simulator; confirm it shows the engine greeting + a buildhash
      that MATCHES the desktop build (proves one shared engine).
- [ ] Load the GMAT Quant deck and run a real review session via the shared engine
      (`gmatwiz_backend_open` + `gmatwiz_backend_command`), not a Swift reimplementation.

## B. Commit the gating + scaffold work
- [ ] Create a branch (e.g., `gmatwiz/gating`) and commit: the new `GmatwizHello`
      Rust RPC, the `ffi/` crate, the `ios/` scaffold, `PRD.md`/`PRD.pdf`,
      `context.txt`, and the `gmatwiz/` content/design/lessons. (Currently uncommitted on `main`.)

## C. Then continue the PRD roadmap
- [ ] Phase 3: implement topic-aware scheduling in Rust (3 Rust tests + 1 Python test,
      undo intact) and confirm it ships to the phone build too (shared engine).
- [ ] Phase 7: stand up the self-hosted Anki Sync Server (`rslib/sync`) for
      desktop <-> phone sync; run the 7b offline conflict test.
- [ ] MVP proof: desktop installer (`./tools/build-installer`) + phone build, both with AI off.

## Notes
- iOS Rust targets installed: `aarch64-apple-ios`, `aarch64-apple-ios-sim`.
- Engine FFI host smoke test: `ffi/test/smoke.c` -> built/ran clean.
- Do NOT rewrite the scheduler in Swift; Swift is UI only and calls the shared Rust engine.
