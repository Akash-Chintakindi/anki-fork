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

---

# Friday deliverables - "AI added and checked; phone syncs"

## AI eval + baseline (checklist items 3 + 4)

Full write-up + numbers: [`proof/ai-eval.txt`](ai-eval.txt). The eval scores topic
auto-tagging on a held-out labeled set (`gmatwiz/content/seed.json`, 42 gold items)
with a 0.6 ship cutoff, side-by-side against a keyword baseline and a tf-idf vector
baseline.

```bash
cd gmatwiz/content
# Full run incl. the AI tagger (uses the app's key from the Functions secret):
export OPENAI_API_KEY="$(npx -y firebase-tools@latest functions:secrets:access OPENAI_API_KEY --project gmatwiz)"
python3 eval_tagging.py            # prints the table; writes eval_report.json
# baselines-only (offline): python3 eval_tagging.py
```

The command prints a "RESULT: the AI tagger BEATS both baselines..." line and
`eval_report.json` records `ai_beats_baselines`. Screenshot/copy that table.

## AI provenance (checklist item 2 - "traces back to a named source")

- Generated Drill/Study questions carry an "AI-generated - checked" badge in the
  practice header, and are stored with `source = "AI-generated (gpt-4.1-mini) -
  7f-checked"` ([qt/aqt/mediasrv.py](../qt/aqt/mediasrv.py) `gmat_add_questions`).
- Each Error-Log Coach takeaway ends with a "Source: gpt-4.1-mini, grounded in
  this item's correct answer (+ official explanation)" line.
- Content tagging provenance (model + confidence per item) is in
  `gmatwiz/content/eval_report.json` / the `ai_ingest` report.

## Recording 4 - phone review shows up on desktop after sync

Proves two-way sync with no lost/double-counted reviews (revlog is append-only and
union-merged by the sync server).

1. Start the self-hosted sync server (leave it running):
   ```bash
   ./tools/gmat-sync-server.sh      # gmat:wiz @ 127.0.0.1:27811
   ```
2. Launch desktop (`./run`), note the review/revlog count in Progress.
3. On the phone (simulator), answer a few reviews, then tap Sync up.
4. On desktop, tap Sync (GMATWiz header) and show the new reviews/count appear.
5. Optional hard proof - revlog grew on both (quit each app first, it holds an
   exclusive lock):
   ```bash
   # desktop collection:
   sqlite3 "$HOME/Library/Application Support/Anki2/User 1/collection.anki2" \
     "select count() from revlog;"
   # phone collection:
   DB="$(xcrun simctl get_app_container booted com.gmatwiz.phone data)/Documents/gmat.anki2"
   sqlite3 "$DB" "select count() from revlog;"
   ```

Record the phone review -> sync -> the same review/count appearing on desktop.
(The Firebase Cloud Storage collection layer also syncs now that the bucket CORS
is set, but the sync-server path above is the one to record for the strict
no-lost/no-double-count claim.)

---

# Sunday deliverables - "prove it, and ship"

All of the models/tests below are **seeded and re-runnable** (spec Section 2). The
numbers are captured in each `proof/*.txt`; re-running reproduces them. See
[`proof/DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the full rubric-coverage script.

## Headline results (this commit)

| Area | Artifact | Result |
| --- | --- | --- |
| Study-feature ablation (Sec 8) | `proof/ablation.txt` | full **97.5%** vs ablation **95.4%** vs plain **95.3%**; full-ablation **+2.10 pts**, 95% CI **[+1.20, +3.04]** -> SUPPORTED |
| Memory calibration (Step 1) | `proof/model-eval.txt` + `proof/calibration.svg` | held-out **Brier 0.125**, **log-loss 0.421**, **ECE 0.043** -> calibrated (<= 0.10) |
| Performance vs baseline (Step 2) | `proof/model-eval.txt` | model Brier **0.164** < global-mean baseline **0.182** -> beats baseline |
| Paraphrase (7d) | `proof/paraphrase.txt` | memorizer memory **94.1%** vs performance **59.3%** = **34.8-pt gap**; control gap **0.0** |
| AI card check (7f) | `proof/ai-cardcheck.txt` | 50 gold + 50 generated, cutoff stated up front, failures blocked (mock-validated; live cmd embedded) |
| AI beats simpler method | `proof/ai-eval.txt` | tagging AI **81%** > keyword **69%** > vector **36%** on held-out |
| Leakage (7e) | `proof/leakage-check.txt` | **CLEAN**: pool 940, test 593, near-dup 0, leakage 0 |
| 50k benchmark (7h) | `proof/bench.txt` | button **0.06 ms** p95, next-card **0.39 ms**, sync **22 ms**, mem **193 MB** -> PASS; dashboard **~1.2 s** -> FAIL (honest) |
| Crash durability (7g) | `proof/crash-offline.txt` | 20 SIGKILLs mid-review -> **0 corrupted collections**, revlog monotonic; scores compute with AI off |
| Sync + conflict (7b) | `proof/sync-test.txt` | 10+10 offline -> **all 20 land once**, no dupes; same-card conflict -> both reviews kept, winner resolved, converged |

## Reproduce them all

```bash
cd anki-fork
PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python -m gmatwiz.eval.ablation
PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python -m gmatwiz.eval.model_eval
PYTHONPATH=out/pylib ANKI_TEST_MODE=1 out/pyenv/bin/python -m gmatwiz.eval.paraphrase
out/pyenv/bin/python gmatwiz/content/leakage_check.py
out/pyenv/bin/python gmatwiz/content/card_check.py --mock     # live: set OPENAI_API_KEY
./tools/gmat-bench.sh          # 50k p50/p95/worst
./tools/gmat-crash-test.sh     # 20x kill, 0 corruption
./tools/gmat-sync-test.sh      # 7b: 10+10 offline + conflict
```

## Models & docs (hand-in)

- Model one-pagers: [`docs/models/memory.md`](../docs/models/memory.md), [`performance.md`](../docs/models/performance.md), [`readiness.md`](../docs/models/readiness.md)
- Brainlift scaffold: [`docs/BRAINLIFT.md`](../docs/BRAINLIFT.md) (finish the narrative)
- Submission README: [`README.md`](../README.md) (exam stated, both-app build, architecture, Rust note, files touched, AGPL + Anki credit)

## Still requires YOU (credentials / manual)

- Record the 3-5 min demo video (see `DEMO_SCRIPT.md` Part 2).
- `git push` the new work to the public repo (`origin` = `Akash-Chintakindi/anki-fork`, currently ahead of remote).
- iOS device/TestFlight build: add your Apple `DEVELOPMENT_TEAM` to `ios/project.yml` (simulator already works).
- Optional live AI numbers: `export OPENAI_API_KEY="$(npx -y firebase-tools@latest functions:secrets:access OPENAI_API_KEY --project gmatwiz)"` then re-run `card_check.py` / `eval_tagging.py`.
