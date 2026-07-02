# GMATWiz - Wednesday Proof Pack

This folder holds the runnable proof for the "Due Wednesday" checklist. The
text logs below were generated automatically; the three screen recordings are
the only things you have to capture yourself (nobody can screen-record your
machine for you). Commit hash + all test/build logs are already here.

## What's already generated (in this folder)

| File | Proves |
| --- | --- |
| `commit.txt` | The exact commit under test (`HEAD bea02fa3b`, branch `gmatwiz`) + recent history. |
| `build.log` | `./ninja pylib qt` builds cleanly (incremental; see clean-build note below). |
| `rust-tests.txt` | 6 Rust unit tests pass (4 scheduler `topic_aware` + 2 `gmatwiz`). |
| `python-test.txt` | 2 Python tests pass, incl. the one that drives the Rust `set_topic_mastery` change end to end. |
| `installer.log` | The macOS `.dmg` builds from this commit: `out/installer/dist/anki-26.05-mac-apple.dmg` (~218 MB). |

Reproduce the logs any time:

```bash
cd anki-fork

# Rust unit tests
export PROTOC="$PWD/out/extracted/protoc/bin/protoc"
export CARGO_TARGET_DIR="$PWD/out/rust"
cargo test -p anki --features rustls scheduler::topic_aware
cargo test -p anki --features rustls gmatwiz::test

# Python test that calls the Rust change
PYTHONPATH="out/pylib" ANKI_TEST_MODE=1 out/pyenv/bin/python \
  -m pytest -p no:cacheprovider pylib/tests/test_gmatwiz.py -v

# Installer (.dmg)
./ninja wheels:anki wheels:aqt && ./ninja installer:package
ls -lh out/installer/dist
```

---

## Recording 1 - Clean build from source

`build.log` here is an *incremental* build (the tree was already built this
session). For the graded "clean-build recording", record a from-scratch build:

```bash
cd anki-fork
rm -rf out            # wipe every build output
./tools/install-n2    # first run only: fetch the ninja build tool
./run                 # builds Rust + Python wheels + SvelteKit, then launches
```

Record the terminal from `rm -rf out` through the app window opening. Expect
~10-20 min (it compiles the Rust engine, the wheels, and the web UI). When the
window opens it lands directly on the GMATWiz screen - that's the payoff shot.

---

## Recording 2 - Installer on a clean machine

Artifact to install: `out/installer/dist/anki-26.05-mac-apple.dmg` (built from
this commit; see `installer.log`).

The installed app bundle is `Anki.app` (the fork keeps Anki's bundle id) and it
opens straight into the GMATWiz UI. On a **clean** target - a fresh macOS user
account, a spare Mac, or a macOS VM with no dev tools:

1. Copy the `.dmg` over and double-click it.
2. Drag `Anki` into `Applications`.
3. Launch it. Because the build is ad-hoc signed, Gatekeeper warns on first
   open - right-click the app -> **Open** -> **Open**, or clear the quarantine
   flag first:
   ```bash
   xattr -dr com.apple.quarantine /Applications/Anki.app
   ```
4. Show it booting into GMATWiz with no Python/Xcode/toolchain installed.

Record from opening the `.dmg` through GMATWiz loading.

---

## Recording 3 - Real review session on the phone

The app is already built this session. Boot the simulator, (re)install, launch,
start the screen capture, then tap through a few reviews:

```bash
cd anki-fork
xcrun simctl boot "iPhone 17" 2>/dev/null; open -a Simulator
xcrun simctl install booted \
  ios/build/Build/Products/Debug-iphonesimulator/GMATWizPhone.app
xcrun simctl launch booted com.gmatwiz.phone

# start recording (Ctrl-C in this terminal to stop)
xcrun simctl io booted recordVideo --codec=h264 proof/phone-review.mov
```

To rebuild the app first (if needed):

```bash
xcodegen generate --spec ios/project.yml
xcodebuild -project ios/GMATWizPhone.xcodeproj -scheme GMATWizPhone \
  -sdk iphonesimulator -configuration Debug -derivedDataPath ios/build \
  -destination 'platform=iOS Simulator,name=iPhone 17' build
```

Answer several questions so the review loop is visible. Optional: prove the
reviews are real (revlog grows). Quit the app first - it holds an exclusive DB
lock:

```bash
DB="$(xcrun simctl get_app_container booted com.gmatwiz.phone data)/Documents/gmat.anki2"
sqlite3 "$DB" "select count() from revlog;"
```

---

## Checklist mapping (from the brief)

- Anki forked + builds from source -> Recording 1 + `build.log`
- Rust change end-to-end, 3 Rust unit tests, 1 Python test -> `rust-tests.txt` (6 tests) + `python-test.txt`
- Review loop on the exam deck -> visible in Recording 1 (desktop Practice) and Recording 3 (phone)
- Memory model, honest score (range + give-up rule) -> visible in the Progress tab; logic in `rslib/src/gmatwiz.rs::gmat_memory_json`
- Installer on a clean machine -> `installer.log` + Recording 2
- Phone builds/runs + real review on the shared engine -> Recording 3
- Proof: commit hash (`commit.txt`) + the recordings + test/build logs
