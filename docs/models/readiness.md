# Readiness model

> Source of truth: `gmat_readiness_json`, `gmat_total_readiness`, `gmat_accuracy_to_section`, and `gmat_sections_to_total` in [`rslib/src/gmatwiz.rs`](../../rslib/src/gmatwiz.rs). PRD §4 / §11 (Step 3–4). Shared verbatim by desktop and iOS.

## What it predicts

**"What score would the student get today, and how sure are we?"** Reported **per section** on the GMAT Focus **60–90** scale, then composed into a **GMAT Focus Total (205–805, 10-point steps)** with an explicit range and a confidence note. This is the second hard bridge, and it is gated hard: a confident number with no evidence is treated as a failure, not a feature.

## Inputs & method

- **Coverage** — per section, distinct leaf topics **with cards** ÷ that section's total (Quant `18`, Verbal `16`, DI `3`; `37` overall). This is the % of the official outline the deck actually covers.
- **Section score (60–90)** — a **documented heuristic** map from the section's held-out first-exposure **accuracy** (from the Performance model): anchors **0.40 → 70** and **0.90 → 88**, linearly interpolated and clamped to `[60, 90]` (`gmat_accuracy_to_section`). The Performance `point`/`low`/`high` accuracies map to the section's `point`/`low`/`high`.
- **Total (205–805)** — `gmat_sections_to_total`: normalize each section as `(s − 60) / 30` to `0..1`, **average the three**, map to `205 + avg × 600`, **round to the nearest 10**, clamp to `[205, 805]`. It is documented as a heuristic because GMAC's exact total formula is undisclosed — so the **per-section breakdown is always shown** next to the Total.

## Give-up / abstention rule (exact)

> **A section's Readiness is shown only if _all four_ conditions hold** — otherwise it abstains and lists exactly which are unmet, with the message _"A confident number with no evidence is just a guess."_:
> - topic **coverage ≥ 50%** (`READY_MIN_COVERAGE`), **and**
> - **≥ 200 graded reviews** (`READY_MIN_REVIEWS`), **and**
> - **≥ 50 application attempts** (`READY_MIN_ATTEMPTS`), **and**
> - memory **calibration ECE ≤ 0.10** (`READY_MAX_ECE`).
>
> **The GMAT Focus Total (205–805) abstains until _all three_ sections are individually shown** (`gmat_total_readiness`); while abstaining it names the sections still lacking evidence — _"A Total (205–805) needs enough evidence in all three sections."_ — and still exposes the per-section objects as `by_section`.

## Range, uncertainty & "how sure"

- **Range** — the section `low`/`high` come from mapping the Performance CI accuracies through the same 60–90 heuristic; the Total `low`/`high` compose the section lows/highs the same way.
- **"How sure" (`confidence`)** — `low` / `medium` / `high`, earned from evidence: broad coverage (≥ 80%) with many attempts (≥ 150) raises it to `medium`; **two or more logged official scores** can raise it to `high`. Real outcomes count for more than coverage alone.

## Official-score calibration offset (honesty rule)

Readiness is validated against the student's **real logged practice-test scores** (Quant today). When a score is logged, the app snapshots its raw projection at that moment (`projected_at_entry`). The engine then computes a **bias = mean(official − projected)** over paired entries and shows a **calibrated** headline (`point + bias`, clamped to 60–90) **while always keeping the raw heuristic and the mean residual visible**. The `method` string states plainly whether the number is calibrated ("shifted by ±N points, mean error M") or still the un-validated heuristic. A **`mock_gap`** — the distance between the projection and the latest timed mock — is displayed, not hidden.

## Evidence it reports

**When shown:** `status`, `section`, `point`, `low`, `high`, `scale`, `confidence`, `method`, `mocks`, `mock_gap`, `official`, `calibration` (`n`, `bias`, `residual`, calibrated `point`/`low`/`high`), `updated_ts`; the Total adds `total` and `by_section`. **When abstaining:** `status: "abstain"`, the `unmet` list, `reason`, any `mocks` / `official` logged so far, and `updated_ts`.
