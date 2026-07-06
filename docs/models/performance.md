# Performance model

> Source of truth: `gmat_performance_json` in [`rslib/src/gmatwiz.rs`](../../rslib/src/gmatwiz.rs). PRD §4 / §11 (Step 2). Shared verbatim by desktop and iOS.

## What it predicts

**"Can the student answer a _new_, exam-style question that uses this fact — including ones never seen before?"** This is the first hard bridge past Memory: recalling a known card is not the same as solving a fresh problem. Performance is measured only on **first-exposure attempts**, never on repeat reviews, so it can't be inflated by memorizing specific cards.

## Inputs & method

Two first-exposure sources are folded into one attempt stream `(key, correct, ms, topic)`:

1. **First-exposure reviews** — `revlog` rows with `lastIvl = 0` and `ease` 1–4, scoped to GMAT cards via the card→topic map; `correct = ease ≥ 2`.
2. **The application log** (`gmatApplication`) — quiz / milestone answers that **never touch the scheduler / revlog**, scoped to the section (an `"all"` roll-up folds in every section for the headline).

From that stream:

- **Accuracy** = correct ÷ total attempts; **uncertainty** = its binomial standard error.
- **Per-topic weak spots** — accuracy per topic, kept only where a topic has **≥ 8** attempts (`PERF_MIN_PER_TOPIC`), sorted weakest-first, top 5.
- **Held-out check (beats a baseline)** — attempts are split by key (`% 10 < 7` train, `≥ 7` test). A **per-topic model** is scored against a **global-mean baseline** using the **Brier score** on the held-out test split; `beats_baseline = model_brier ≤ baseline_brier`.
- **Timing analytics** — against a `128 s` per-question target (`GMAT_TARGET_MS`, i.e. 21 Quant Q in 45 min): it separates **`rushed_wrong`** (wrong in under half the target — a careless signal) from **`slow_correct`** (right but over 1.5× the target — fragile knowledge).

## Give-up / abstention rule (exact)

> **Performance abstains until there are at least `50` first-exposure application attempts (`PERF_MIN_ATTEMPTS`).** Below that it shows **no score** — it returns `status: "abstain"` with the attempts so far, the required count (`50`), and the message _"Need 50 new-question attempts; you have N."_ (or _"No GMAT questions yet."_ when there is no bank at all). Separately, a **per-topic** weak-spot number is withheld until that topic has **≥ 8 attempts (`PERF_MIN_PER_TOPIC`)**.

## Range, uncertainty & "how sure"

- **Point** = `round(accuracy × 100)`.
- **Likely range** = 95% CI, `point ± 1.96 × SE`, clamped to `[0, 100]` (`low` / `high`).
- **"How sure"** = the **held-out `eval`** (does the per-topic model beat the global-mean baseline on unseen attempts?) plus the **`timing`** breakdown. If the model does not beat the baseline, `beats_baseline: false` is reported honestly rather than suppressed.

## Evidence it reports

`status`, `point`, `low`, `high`, `attempts`, `weak_topics` (topic, accuracy, `n`), `eval` (`baseline_brier`, `model_brier`, `beats_baseline`, `test_n`), `timing` (`n`, `avg_ms`, `target_ms`, `rushed_wrong`, `slow_correct`), and `updated_ts`. The overall headline also carries a `by_section` breakdown (Quant / Verbal / DI). Performance's `point`/`low`/`high` accuracy is the input the **Readiness** model maps onto a GMAT section score.
