# Memory model

> Source of truth: `gmat_memory_json` in [`rslib/src/gmatwiz.rs`](../../rslib/src/gmatwiz.rs). PRD §4 / §11 (Step 1). Shared verbatim by desktop and iOS.

## What it predicts

**"Can the student recall this fact right now?"** Memory is FSRS's estimate of current recall probability across the GMAT cards. It is the one score Anki already answers well — so our job is not to invent it, but to **prove it is calibrated**: when the app implies ~90% recall, observed recall really is ~90%.

## Inputs & method

Computed entirely from the **review log** (`revlog`), no fabricated inputs:

- **Observed retention** = graded passes (`ease` 2–4) ÷ total graded reviews (`ease` 1–4).
- **Uncertainty** = the binomial standard error of that proportion.
- **Calibration** = a reliability diagram bucketed by the card's **previous interval** (`lastIvl`): `1-3d`, `4-7d`, `8-21d`, `22-60d`, `60d+`. For each bucket we record the observed pass rate and its `n`.
- **Expected Calibration Error (ECE)** = the `n`-weighted average gap between each bucket's observed rate and the **target retention** — the GMAT deck's own FSRS `desiredRetention` (default `0.90`), so calibration is measured against what the scheduler is actually aiming for.

## Give-up / abstention rule (exact)

> **Memory abstains until there are at least `150` graded reviews (`MEM_MIN_REVIEWS`).** Below that it shows **no score** — instead it returns `status: "abstain"` with the reviews so far, the required count (`150`), and the message _"Need 150 graded reviews; you have N."_ plus the single best next action (keep reviewing).

Notes on scope, honestly:

- This is the **overall** Memory gate that the engine enforces today. PRD §4 also specifies a **per-topic** memory display at **≥ 20 reviews in that topic**; the current engine reports **one overall calibrated Memory** (with the per-interval reliability breakdown above) rather than a separate per-topic memory number, so the per-topic memory display remains a PRD design target, not a shipped surface.
- Reaching the review count does **not** force a "calibrated" claim: the `calibrated` badge is a separate, evidence-based flag (ECE ≤ 0.10).

## Range, uncertainty & "how sure"

- **Point** = `round(observed × 100)`.
- **Likely range** = 95% CI, `point ± 1.96 × SE`, clamped to `[0, 100]` (fields `low` / `high`).
- **"How sure"** = the **`calibrated`** badge (true iff **ECE ≤ 0.10**) shown next to the raw **`ece`** value and the **`target`** retention. A large ECE is displayed, not hidden — an uncalibrated Memory says so out loud.

## Evidence it reports

`status`, `point`, `low`, `high`, `reviews` (total graded), `target` (retention %), `ece`, `calibrated`, the per-interval `bins` (`label`, `observed`, `n`) that form the reliability diagram, and `updated_ts`. Memory's calibration (its `reviews` count and `ece`) is also a **gate for Readiness** — Readiness will not show unless Memory is calibrated (ECE ≤ 0.10).
