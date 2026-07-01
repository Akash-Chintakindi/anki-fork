<!--
Copyright: GMATWiz contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

GMATWiz app shell. A single SvelteKit surface with internal navigation between
Home, Practice, Dashboard and Error Log. Visual language follows
gmatwiz/design (limestone paper, graphite ink, rationed verdigris, the serif
"tutor" voice and mono "instrument" readouts). Conservative CSS for the
chrome77/es2020 webview.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import type {
        GmatOverview,
        ScheduledCard,
        Counts,
        ErrorEntry,
        PretestQuestion,
        Lesson,
        LessonItem,
        LessonTopic,
    } from "./api";
    import {
        logError,
        refreshOverview,
        fetchErrorLog,
        fetchNextCard,
        answerCard,
        saveProfile,
        fetchPretest,
        submitPretest,
        topicLabel,
        fetchLessonsIndex,
        fetchLesson,
        markLearned,
        renderMath,
    } from "./api";

    export let overview: GmatOverview;

    type View =
        | "home"
        | "practice"
        | "dashboard"
        | "errors"
        | "onboarding"
        | "pretest"
        | "plan"
        | "learn"
        | "lesson";
    let view: View = "home";

    // ---- teaching / lesson state ----
    let lessonTopics: LessonTopic[] = [];
    let lesson: Lesson | null = null;
    let lessonPhase: "intro" | "ido" | "wedo" | "youdo" | "done" = "intro";
    let lessonIdx = 0;
    let lessonSelected: string | null = null;
    let lessonRevealed = false;
    let lessonLoading = false;

    // ---- onboarding / diagnostic state ----
    let examDate = "";
    let daysPerWeek = 5;
    let minutesPerDay = 60;
    let pretestQs: PretestQuestion[] = [];
    let pretestIdx = 0;
    let pretestSelected: string | null = null;
    let pretestResults: { topic: string; correct: boolean }[] = [];
    let pretestSecondsLeft = 0;
    let pretestTimer = 0;
    let submitting = false;

    // ---- practice state (backed by the REAL scheduler) ----
    let card: ScheduledCard | null = null;
    let counts: Counts = { new: 0, learning: 0, review: 0 };
    let selected: string | null = null;
    let revealed = false;
    let loading = false;
    let started = 0;
    let answered = 0;
    let correctCount = 0;

    $: optionEntries = card ? Object.entries(card.options) : [];
    $: sessionAccuracy = answered > 0 ? Math.round((correctCount / answered) * 100) : 0;
    $: remaining = counts.new + counts.learning + counts.review;
    $: coveragePct = overview.topics_total
        ? Math.round((100 * overview.topics_covered) / overview.topics_total)
        : 0;

    // ---- lesson derivations ----
    $: lessonItem =
        lesson == null
            ? null
            : lessonPhase === "ido"
              ? lesson.i_do
              : lessonPhase === "wedo"
                ? lesson.we_do[lessonIdx]
                : lessonPhase === "youdo"
                  ? lesson.you_do[lessonIdx]
                  : null;
    $: lessonOptions = lessonItem ? Object.entries((lessonItem as LessonItem).options) : [];
    $: recommendedLearn =
        lessonTopics.find((t) => !t.learned && t.mastery !== null && t.mastery < 0.8) ||
        null;

    let errors: ErrorEntry[] = [];

    async function loadNextCard(): Promise<void> {
        loading = true;
        selected = null;
        revealed = false;
        const result = await fetchNextCard();
        card = result.card;
        counts = result.counts;
        started = Date.now();
        loading = false;
    }

    async function go(next: View): Promise<void> {
        stopTimer();
        view = next;
        if (next === "practice") await loadNextCard();
        if (next === "errors") errors = await fetchErrorLog();
        if (next === "learn") lessonTopics = (await fetchLessonsIndex()).topics;
        if (next === "home" || next === "dashboard") {
            const fresh = await refreshOverview();
            if (fresh) overview = fresh;
            if (next === "home" && overview.plan) {
                lessonTopics = (await fetchLessonsIndex()).topics;
            }
        }
    }

    function choose(key: string): void {
        if (!revealed) selected = key;
    }

    async function commit(): Promise<void> {
        if (selected === null || revealed || !card) return;
        revealed = true;
        answered += 1;
        const isCorrect = selected === card.correct;
        if (isCorrect) {
            correctCount += 1;
        } else {
            await logError({
                stem: card.stem,
                topic: card.topic,
                chosen: selected,
                correct: card.correct,
            });
        }
        // Record a REAL review through the scheduler (Good if right, Again if wrong).
        await answerCard(card.card_id, isCorrect, Date.now() - started);
    }

    function optionState(key: string): string {
        if (!revealed) return selected === key ? "sel" : "";
        if (card && key === card.correct) return "correct";
        if (key === selected) return "wrong";
        return "muted";
    }

    // ---- diagnostic / plan flow ----
    function fmtTime(s: number): string {
        const safe = Math.max(0, s);
        const m = Math.floor(safe / 60);
        const sec = safe % 60;
        return `${m}:${sec.toString().padStart(2, "0")}`;
    }

    function stopTimer(): void {
        if (pretestTimer) {
            clearInterval(pretestTimer);
            pretestTimer = 0;
        }
    }

    function startDiagnostic(): void {
        if (overview.profile) {
            examDate = overview.profile.exam_date || "";
            daysPerWeek = overview.profile.days_per_week || 5;
            minutesPerDay = overview.profile.minutes_per_day || 60;
        }
        view = "onboarding";
    }

    async function beginPretest(): Promise<void> {
        await saveProfile({
            exam_date: examDate,
            days_per_week: daysPerWeek,
            minutes_per_day: minutesPerDay,
        });
        const result = await fetchPretest();
        pretestQs = result.questions;
        pretestIdx = 0;
        pretestResults = [];
        pretestSelected = null;
        pretestSecondsLeft = result.seconds;
        view = "pretest";
        stopTimer();
        pretestTimer = window.setInterval(() => {
            pretestSecondsLeft -= 1;
            if (pretestSecondsLeft <= 0) {
                finishPretest();
            }
        }, 1000);
    }

    function choosePretest(key: string): void {
        pretestSelected = key;
    }

    async function nextPretest(): Promise<void> {
        const q = pretestQs[pretestIdx];
        if (q) {
            pretestResults = [
                ...pretestResults,
                { topic: q.topic, correct: pretestSelected === q.correct },
            ];
        }
        pretestSelected = null;
        if (pretestIdx < pretestQs.length - 1) {
            pretestIdx += 1;
        } else {
            await finishPretest();
        }
    }

    async function finishPretest(): Promise<void> {
        if (submitting) return;
        submitting = true;
        stopTimer();
        await submitPretest(pretestResults);
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
        submitting = false;
        view = "plan";
    }

    $: pretestCurrent = pretestQs[pretestIdx];
    $: pretestOptions = pretestCurrent ? Object.entries(pretestCurrent.options) : [];

    // ---- lesson loop (I-do -> we-do -> you-do) ----
    async function openLesson(topicId: string): Promise<void> {
        stopTimer();
        lessonLoading = true;
        view = "lesson";
        lesson = await fetchLesson(topicId);
        lessonPhase = "intro";
        lessonIdx = 0;
        lessonSelected = null;
        lessonRevealed = false;
        lessonLoading = false;
    }

    function chooseLesson(key: string): void {
        if (!lessonRevealed) lessonSelected = key;
    }

    async function checkLesson(): Promise<void> {
        if (lessonSelected === null || lessonRevealed || !lessonItem) return;
        lessonRevealed = true;
        if (lessonPhase === "youdo" && lessonSelected !== lessonItem.correct) {
            await logError({
                stem: lessonItem.stem,
                topic: lesson?.topic_id ?? "",
                chosen: lessonSelected,
                correct: lessonItem.correct,
            });
        }
    }

    function lessonOptionState(key: string): string {
        if (!lessonRevealed) return lessonSelected === key ? "sel" : "";
        if (lessonItem && key === lessonItem.correct) return "correct";
        if (key === lessonSelected) return "wrong";
        return "muted";
    }

    async function advanceLesson(): Promise<void> {
        if (!lesson) return;
        lessonSelected = null;
        lessonRevealed = false;
        if (lessonPhase === "intro") {
            lessonPhase = "ido";
        } else if (lessonPhase === "ido") {
            lessonPhase = lesson.we_do.length
                ? "wedo"
                : lesson.you_do.length
                  ? "youdo"
                  : "done";
            lessonIdx = 0;
        } else if (lessonPhase === "wedo") {
            if (lessonIdx < lesson.we_do.length - 1) {
                lessonIdx += 1;
            } else {
                lessonPhase = lesson.you_do.length ? "youdo" : "done";
                lessonIdx = 0;
            }
        } else if (lessonPhase === "youdo") {
            if (lessonIdx < lesson.you_do.length - 1) {
                lessonIdx += 1;
            } else {
                lessonPhase = "done";
            }
        }
        if (lessonPhase === "done") {
            await markLearned(lesson.topic_id);
        }
    }

    async function finishLesson(target: View): Promise<void> {
        lessonTopics = (await fetchLessonsIndex()).topics;
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
        await go(target);
    }

    onMount(() => {
        if (overview.plan) {
            fetchLessonsIndex().then((r) => (lessonTopics = r.topics));
        }
    });
</script>

<div class="gw">
    <header class="topbar">
        <div class="brand">
            <span class="mark">GMAT<span class="mark-accent">Wiz</span></span>
            <span class="ruler" aria-hidden="true"></span>
        </div>
        <nav class="nav">
            <button class:active={view === "home"} on:click={() => go("home")}>Today</button>
            <button
                class:active={view === "learn" || view === "lesson"}
                on:click={() => go("learn")}>Learn</button
            >
            <button class:active={view === "practice"} on:click={() => go("practice")}>Practice</button>
            <button class:active={view === "dashboard"} on:click={() => go("dashboard")}>Readiness</button>
            <button class:active={view === "errors"} on:click={() => go("errors")}>Error Log</button>
        </nav>
    </header>

    {#if view === "home"}
        <main class="col">
            <p class="eyebrow">Today</p>
            <h1 class="display">The work that builds competence.</h1>
            <p class="lede">
                Lessons create confidence. Application creates competence. Your next move is a
                problem to solve, not a page to read.
            </p>

            <section class="action-card">
                {#if overview.total === 0}
                    <div class="action-head">
                        <span class="eyebrow">Get started</span>
                        <span class="pill">{overview.deck}</span>
                    </div>
                    <h2 class="action-title">Import your GMAT Quant questions</h2>
                    <p class="muted">
                        Use Tools &rarr; Import GMAT Quant, then take your diagnostic.
                    </p>
                {:else if !overview.plan}
                    <div class="action-head">
                        <span class="eyebrow">Next action</span>
                        <span class="pill">{overview.total} questions</span>
                    </div>
                    <h2 class="action-title">Take your diagnostic</h2>
                    <p class="muted">
                        A 21-question timed diagnostic builds your personalized plan and targets
                        your weak topics.
                    </p>
                    <button class="primary" on:click={startDiagnostic}>Start diagnostic</button>
                {:else if recommendedLearn}
                    <div class="action-head">
                        <span class="eyebrow">Today's focus</span>
                        <span class="pill">weak topic</span>
                    </div>
                    <h2 class="action-title">Learn: {topicLabel(recommendedLearn.topic_id)}</h2>
                    <p class="muted">
                        A weak topic from your diagnostic. Learn it first, then practice &mdash;
                        don't drill blind.{#if overview.plan.days_to_exam !== null}
                            &middot; {overview.plan.days_to_exam} days to exam{/if}
                    </p>
                    <button class="primary" on:click={() => openLesson(recommendedLearn.topic_id)}>
                        Start lesson
                    </button>
                    <button class="ghost" on:click={() => go("practice")}>Skip to practice</button>
                {:else}
                    <div class="action-head">
                        <span class="eyebrow">Today's focus</span>
                        <span class="pill">{overview.deck}</span>
                    </div>
                    <h2 class="action-title">
                        Focus: {overview.plan.topics
                            .slice(0, 3)
                            .map((t) => topicLabel(t.topic))
                            .join(", ")}
                    </h2>
                    <p class="muted">
                        {overview.plan.daily_minutes} min/day{#if overview.plan.days_to_exam !== null}
                            &middot; {overview.plan.days_to_exam} days to exam{/if}
                        &middot; weak topics resurface first
                    </p>
                    <button class="primary" on:click={() => go("practice")}>Start practice</button>
                    <button class="ghost" on:click={() => go("plan")}>View full plan</button>
                {/if}
            </section>

            <div class="mini-grid">
                <div class="mini">
                    <span class="mini-n">{overview.total}</span>
                    <span class="mini-l">in bank</span>
                </div>
                <div class="mini">
                    <span class="mini-n">{coveragePct}%</span>
                    <span class="mini-l">coverage</span>
                </div>
                <div class="mini">
                    <span class="mini-n">{overview.reviews}</span>
                    <span class="mini-l">reviews</span>
                </div>
            </div>
        </main>
    {:else if view === "practice"}
        <main class="col">
            <div class="session-meter">
                <span class="readout">{answered}</span> answered
                {#if answered > 0}
                    &middot; <span class="readout">{sessionAccuracy}%</span> accurate
                {/if}
                {#if remaining > 0}
                    &middot; <span class="muted">{remaining} in queue</span>
                {/if}
            </div>

            {#if loading}
                <section class="q-card empty"><p>Loading&hellip;</p></section>
            {:else if card}
                <section class="q-card">
                    <div class="q-head">
                        <span class="eyebrow">{card.topic || "GMAT Quant"}</span>
                        <span class="pill diff-{card.difficulty}">{card.difficulty}</span>
                    </div>
                    <h1 class="stem">{@html renderMath(card.stem)}</h1>

                    <ul class="opts">
                        {#each optionEntries as [key, value]}
                            <li>
                                <button
                                    class="opt {optionState(key)}"
                                    disabled={revealed}
                                    on:click={() => choose(key)}
                                >
                                    <span class="opt-key">{key}</span>
                                    <span>{@html renderMath(value)}</span>
                                </button>
                            </li>
                        {/each}
                    </ul>

                    {#if !revealed}
                        <button class="primary" disabled={selected === null} on:click={commit}>
                            Commit answer
                        </button>
                        <p class="seal">The explanation stays sealed until you commit.</p>
                    {:else}
                        <div class="verdict {selected === card.correct ? 'ok' : 'no'}">
                            <strong>{selected === card.correct ? "Correct" : "Not yet"}</strong>
                            <span class="muted">Answer: {card.correct}</span>
                        </div>
                        <p class="explain">{@html renderMath(card.explanation)}</p>
                        <button class="primary" on:click={loadNextCard}>Next question</button>
                    {/if}
                </section>
            {:else}
                <section class="q-card empty">
                    <p>
                        You're caught up for now. Import GMAT Quant from the Tools menu, or come
                        back later for scheduled review.
                    </p>
                </section>
            {/if}
        </main>
    {:else if view === "dashboard"}
        <main class="col-wide">
            <p class="eyebrow">Readiness &mdash; three separate questions</p>
            <h1 class="display">What we actually know.</h1>

            <div class="score-grid">
                <!-- Memory -->
                <section class="measure">
                    <span class="eyebrow">Memory</span>
                    <p class="measure-q">Can you recall a fact right now?</p>
                    {#if overview.memory.status === "shown"}
                        <div class="needle-wrap">
                            <span class="readout-lg">{overview.memory.point}%</span>
                            <span class="band">
                                range {overview.memory.low}&ndash;{overview.memory.high}% &middot;
                                {overview.memory.reviews} reviews
                            </span>
                        </div>
                        <div class="calib">
                            <div class="calib-head">
                                <span class="eyebrow">Calibration</span>
                                <span class="pill {overview.memory.calibrated ? 'cal-ok' : 'cal-warn'}">
                                    {overview.memory.calibrated ? "calibrated" : "drift"} &middot; ECE
                                    {overview.memory.ece}
                                </span>
                            </div>
                            <p class="muted">
                                Target {overview.memory.target}% retention (dashed line). Bars are your
                                actual recall by past interval &mdash; near the line means well-calibrated.
                            </p>
                            <div class="calib-bars">
                                {#each overview.memory.bins ?? [] as b}
                                    <div class="calib-col" title="{b.n} reviews">
                                        <div class="calib-track">
                                            <div
                                                class="calib-target"
                                                style="bottom:{overview.memory.target}%"
                                            ></div>
                                            <div
                                                class="calib-fill"
                                                style="height:{Math.round(b.observed * 100)}%"
                                            ></div>
                                        </div>
                                        <span class="calib-pct">{Math.round(b.observed * 100)}%</span>
                                        <span class="calib-x">{b.label}</span>
                                    </div>
                                {/each}
                            </div>
                        </div>
                    {:else}
                        <div class="abstain">
                            <span class="abstain-mark">— · —</span>
                            <p class="abstain-title">Not enough data</p>
                            <p class="muted">
                                Needs {overview.memory.reviews_required} graded reviews; you have
                                {overview.memory.reviews}.
                            </p>
                            <p class="next">Best next step: practice today's questions.</p>
                        </div>
                    {/if}
                </section>

                <!-- Performance -->
                <section class="measure">
                    <span class="eyebrow">Performance</span>
                    <p class="measure-q">Can you answer a new exam-style question?</p>
                    {#if overview.performance.status === "shown"}
                        <div class="needle-wrap">
                            <span class="readout-lg">{overview.performance.point}%</span>
                            <span class="band">
                                range {overview.performance.low}&ndash;{overview.performance.high}% &middot;
                                {overview.performance.attempts} new-question attempts
                            </span>
                        </div>
                        {#if overview.performance.eval}
                            <p class="muted">
                                Held-out check: per-topic model Brier {overview.performance.eval.model_brier}
                                vs baseline {overview.performance.eval.baseline_brier} on
                                {overview.performance.eval.test_n} items &mdash;
                                {overview.performance.eval.beats_baseline
                                    ? "beats the simple baseline."
                                    : "not yet beating the baseline."}
                            </p>
                        {/if}
                        {#if overview.performance.weak_topics?.length}
                            <p class="next">
                                Weakest: {overview.performance.weak_topics
                                    .slice(0, 3)
                                    .map((t) => topicLabel(t.topic))
                                    .join(", ")}
                            </p>
                        {/if}
                    {:else}
                        <div class="abstain">
                            <span class="abstain-mark">— · —</span>
                            <p class="abstain-title">Not enough data</p>
                            <p class="muted">{overview.performance.reason}</p>
                            <p class="next">Best next step: build a streak of timed practice.</p>
                        </div>
                    {/if}
                </section>

                <!-- Readiness -->
                <section class="measure">
                    <span class="eyebrow">Readiness</span>
                    <p class="measure-q">What score would you get today?</p>
                    {#if overview.readiness.status === "shown"}
                        <div class="needle-wrap">
                            <span class="readout-lg">Q{overview.readiness.point}</span>
                            <span class="band">
                                range Q{overview.readiness.low}&ndash;Q{overview.readiness.high} &middot;
                                {overview.readiness.confidence} confidence
                            </span>
                        </div>
                        <p class="muted">{overview.readiness.scale}. {overview.readiness.method}</p>
                        <p class="next">Total (205-805): {overview.readiness.total_reason}</p>
                    {:else}
                        <div class="abstain">
                            <span class="abstain-mark">— · —</span>
                            <p class="abstain-title">Not enough data</p>
                            {#if overview.readiness.unmet?.length}
                                <ul class="unmet">
                                    {#each overview.readiness.unmet as u}
                                        <li>{u}</li>
                                    {/each}
                                </ul>
                            {/if}
                            <p class="next">{overview.readiness.reason}</p>
                        </div>
                    {/if}
                </section>
            </div>

            <section class="coverage">
                <div class="coverage-head">
                    <span class="eyebrow">Topic coverage</span>
                    <span class="readout">{overview.topics_covered}/{overview.topics_total}</span>
                </div>
                <div class="bar"><div class="bar-fill" style="width:{coveragePct}%"></div></div>
            </section>
        </main>
    {:else if view === "onboarding"}
        <main class="col">
            <p class="eyebrow">Diagnostic</p>
            <h1 class="display">Let's find your starting point.</h1>
            <p class="lede">
                A short, timed Quant diagnostic (21 questions, 45 minutes) calibrates every
                topic so your plan targets your real weak spots. Set aside a quiet block of time.
            </p>
            <section class="action-card">
                <label class="field">
                    <span class="field-label">Exam date</span>
                    <input type="date" bind:value={examDate} />
                </label>
                <label class="field">
                    <span class="field-label">Study days per week</span>
                    <input type="number" min="1" max="7" bind:value={daysPerWeek} />
                </label>
                <label class="field">
                    <span class="field-label">Minutes per day</span>
                    <input type="number" min="10" max="600" step="5" bind:value={minutesPerDay} />
                </label>
                <button class="primary" on:click={beginPretest}>Begin diagnostic</button>
                <p class="seal">No explanations during the diagnostic &mdash; it only measures.</p>
            </section>
        </main>
    {:else if view === "pretest"}
        <main class="col">
            <div class="session-meter">
                <span class="readout">{pretestIdx + 1}</span> / {pretestQs.length}
                &middot; <span class="readout">{fmtTime(pretestSecondsLeft)}</span> left
            </div>
            {#if submitting}
                <section class="q-card empty"><p>Scoring your diagnostic&hellip;</p></section>
            {:else if pretestCurrent}
                <section class="q-card">
                    <div class="q-head">
                        <span class="eyebrow">Diagnostic</span>
                        <span class="pill diff-{pretestCurrent.difficulty}">{pretestCurrent.difficulty}</span>
                    </div>
                    <h1 class="stem">{@html renderMath(pretestCurrent.stem)}</h1>
                    <ul class="opts">
                        {#each pretestOptions as [key, value]}
                            <li>
                                <button
                                    class="opt {pretestSelected === key ? 'sel' : ''}"
                                    on:click={() => choosePretest(key)}
                                >
                                    <span class="opt-key">{key}</span>
                                    <span>{@html renderMath(value)}</span>
                                </button>
                            </li>
                        {/each}
                    </ul>
                    <button
                        class="primary"
                        disabled={pretestSelected === null}
                        on:click={nextPretest}
                    >
                        {pretestIdx < pretestQs.length - 1 ? "Next" : "Finish diagnostic"}
                    </button>
                </section>
            {:else}
                <section class="q-card empty">
                    <p>No diagnostic questions available. Import GMAT Quant first.</p>
                </section>
            {/if}
        </main>
    {:else if view === "plan"}
        <main class="col">
            <p class="eyebrow">Your plan</p>
            <h1 class="display">Built around your weak spots.</h1>
            {#if overview.plan}
                <p class="lede">
                    {#if overview.plan.days_to_exam !== null}
                        {overview.plan.days_to_exam} days to exam &middot;
                    {/if}
                    {overview.plan.daily_minutes} min/day, {overview.plan.days_per_week} days/week.
                    Weakest topics come first and are scheduled to resurface sooner.
                </p>
                <section class="action-card">
                    <span class="eyebrow">Focus first</span>
                    <ul class="focus-list">
                        {#each overview.plan.topics.slice(0, 5) as t}
                            <li>
                                <span class="focus-name">{topicLabel(t.topic)}</span>
                                <span class="focus-bar">
                                    <span class="focus-fill" style="width:{Math.round(t.mastery * 100)}%"></span>
                                </span>
                                <span class="focus-status s-{t.status}">{t.status}</span>
                            </li>
                        {/each}
                    </ul>
                    <button class="primary" on:click={() => go("practice")}>
                        Start studying my plan
                    </button>
                </section>
                <details class="all-topics">
                    <summary>All {overview.plan.topics.length} topics</summary>
                    <ul class="focus-list">
                        {#each overview.plan.topics as t}
                            <li>
                                <span class="focus-name">{topicLabel(t.topic)}</span>
                                <span class="focus-bar">
                                    <span class="focus-fill" style="width:{Math.round(t.mastery * 100)}%"></span>
                                </span>
                                <span class="focus-status s-{t.status}">{t.status}</span>
                            </li>
                        {/each}
                    </ul>
                </details>
            {:else}
                <p class="lede">No plan yet. Take your diagnostic from the Today tab.</p>
            {/if}
        </main>
    {:else if view === "learn"}
        <main class="col">
            <p class="eyebrow">Learn</p>
            <h1 class="display">Teach first, then apply.</h1>
            <p class="lede">
                Short worked examples and guided practice, weakest topics first. Each lesson ends
                by dropping you into real spaced practice.
            </p>
            {#if lessonTopics.length === 0}
                <section class="q-card empty">
                    <p>
                        Take your diagnostic first (Today tab) to prioritize topics, or import GMAT
                        Quant from the Tools menu.
                    </p>
                </section>
            {:else}
                <ul class="focus-list">
                    {#each lessonTopics as t}
                        <li>
                            <span class="focus-name">
                                {t.title}{#if t.learned} &check;{/if}
                            </span>
                            <span class="focus-bar">
                                <span class="focus-fill" style="width:{Math.round((t.mastery ?? 0) * 100)}%"></span>
                            </span>
                            <button class="ghost" on:click={() => openLesson(t.topic_id)}>
                                {t.learned ? "Review" : "Learn"}
                            </button>
                        </li>
                    {/each}
                </ul>
            {/if}
        </main>
    {:else if view === "lesson"}
        <main class="col">
            {#if lessonLoading}
                <section class="q-card empty"><p>Loading lesson&hellip;</p></section>
            {:else if lesson}
                <div class="session-meter">
                    <span class="readout">{lesson.title}</span> &middot;
                    {#if lessonPhase === "intro"}Overview
                    {:else if lessonPhase === "ido"}I do
                    {:else if lessonPhase === "wedo"}We do {lessonIdx + 1}/{lesson.we_do.length}
                    {:else if lessonPhase === "youdo"}You do {lessonIdx + 1}/{lesson.you_do.length}
                    {:else}Complete{/if}
                </div>

                {#if lessonPhase === "intro"}
                    <section class="q-card">
                        <p class="eyebrow">{lesson.domain}</p>
                        <h1 class="stem">{lesson.title}</h1>
                        {#if lesson.opening?.learning_intention}
                            <p class="explain">{@html renderMath(lesson.opening.learning_intention)}</p>
                        {/if}
                        {#if lesson.learning_objectives?.length}
                            <ul class="obj-list">
                                {#each lesson.learning_objectives as o}
                                    <li>{@html renderMath(o)}</li>
                                {/each}
                            </ul>
                        {/if}
                        <button class="primary" on:click={advanceLesson}>Start lesson</button>
                    </section>
                {:else if lessonPhase === "ido" && lessonItem}
                    <section class="q-card">
                        <p class="eyebrow">Worked example (I do)</p>
                        <h1 class="stem">{@html renderMath(lessonItem.stem)}</h1>
                        <ul class="opts">
                            {#each lessonOptions as [key, value]}
                                <li>
                                    <div class="opt {key === lessonItem.correct ? 'correct' : 'muted'}">
                                        <span class="opt-key">{key}</span>
                                        <span>{@html renderMath(value)}</span>
                                    </div>
                                </li>
                            {/each}
                        </ul>
                        {#if lessonItem.think_aloud_steps?.length}
                            <p class="eyebrow">Think aloud</p>
                            <ol class="steps">
                                {#each lessonItem.think_aloud_steps as s}
                                    <li>{@html renderMath(s)}</li>
                                {/each}
                            </ol>
                        {/if}
                        {#if lessonItem.key_takeaway}
                            <p class="explain">
                                <strong>Takeaway:</strong> {@html renderMath(lessonItem.key_takeaway)}
                            </p>
                        {/if}
                        <button class="primary" on:click={advanceLesson}>Continue</button>
                    </section>
                {:else if (lessonPhase === "wedo" || lessonPhase === "youdo") && lessonItem}
                    <section class="q-card">
                        <p class="eyebrow">
                            {lessonPhase === "wedo" ? "Guided practice (we do)" : "Your turn (you do)"}
                        </p>
                        <h1 class="stem">{@html renderMath(lessonItem.stem)}</h1>
                        <ul class="opts">
                            {#each lessonOptions as [key, value]}
                                <li>
                                    <button
                                        class="opt {lessonOptionState(key)}"
                                        disabled={lessonRevealed}
                                        on:click={() => chooseLesson(key)}
                                    >
                                        <span class="opt-key">{key}</span>
                                        <span>{@html renderMath(value)}</span>
                                    </button>
                                </li>
                            {/each}
                        </ul>
                        {#if !lessonRevealed}
                            <button
                                class="primary"
                                disabled={lessonSelected === null}
                                on:click={checkLesson}
                            >
                                Check
                            </button>
                            {#if lessonPhase === "wedo" && lessonItem.scaffold_hints?.length}
                                <details class="all-topics">
                                    <summary>Need a hint?</summary>
                                    <ul class="steps">
                                        {#each lessonItem.scaffold_hints as h}
                                            <li>{@html renderMath(h)}</li>
                                        {/each}
                                    </ul>
                                </details>
                            {/if}
                        {:else}
                            <div class="verdict {lessonSelected === lessonItem.correct ? 'ok' : 'no'}">
                                <strong>{lessonSelected === lessonItem.correct ? "Correct" : "Not yet"}</strong>
                                <span class="muted">Answer: {lessonItem.correct}</span>
                            </div>
                            {#if lessonPhase === "wedo" && lessonItem.immediate_feedback}
                                <p class="explain">
                                    {@html renderMath(
                                        lessonSelected === lessonItem.correct
                                            ? lessonItem.immediate_feedback.if_correct ?? ""
                                            : lessonItem.immediate_feedback.if_incorrect ?? "",
                                    )}
                                </p>
                            {/if}
                            <p class="explain">{@html renderMath(lessonItem.explanation)}</p>
                            <button class="primary" on:click={advanceLesson}>Next</button>
                        {/if}
                    </section>
                {:else}
                    <section class="q-card">
                        <p class="eyebrow">Lesson complete</p>
                        <h1 class="stem">Nice work on {lesson.title}.</h1>
                        <p class="explain">
                            You've been through the worked example, guided practice, and independent
                            questions. Now lock it in with spaced practice.
                        </p>
                        <button class="primary" on:click={() => finishLesson("practice")}>
                            Practice this topic
                        </button>
                        <button class="ghost" on:click={() => finishLesson("learn")}>Back to Learn</button>
                    </section>
                {/if}
            {:else}
                <section class="q-card empty"><p>Lesson not found.</p></section>
            {/if}
        </main>
    {:else}
        <main class="col">
            <p class="eyebrow">Error log &mdash; required review</p>
            <h1 class="display">Your mistakes, made useful.</h1>
            <p class="lede">Understanding the pattern behind a miss is how you stop repeating it.</p>

            {#if errors.length === 0}
                <section class="q-card empty">
                    <p>No logged errors yet. Missed questions in Practice appear here automatically.</p>
                </section>
            {:else}
                <ul class="err-list">
                    {#each errors as e}
                        <li class="err">
                            <div class="err-top">
                                <span class="pill">{e.topic || "Quant"}</span>
                                <span class="muted">chose {e.chosen} &middot; correct {e.correct}</span>
                            </div>
                            <p class="err-stem">{e.stem}</p>
                        </li>
                    {/each}
                </ul>
            {/if}
        </main>
    {/if}
</div>

<style>
    .gw {
        --paper: #eae6dd;
        --surface: #f4f1e9;
        --sunk: #e1dbcf;
        --ink: #211f19;
        --ink-soft: #5f5849;
        --ink-faint: #8c8472;
        --indicator: #2e6e5e;
        --indicator-ink: #245a4b;
        --indicator-tint: #dce7e1;
        --clay-ink: #8c4233;
        --clay-tint: #f0ded7;
        --brass-tint: #ece0c2;
        --line: #d3cbbc;
        --line-strong: #bcb2a0;
        --voice: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
        --ui: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;

        box-sizing: border-box;
        min-height: 100vh;
        margin: 0;
        background: var(--paper);
        color: var(--ink);
        font-family: var(--ui);
        -webkit-font-smoothing: antialiased;
    }
    .gw *,
    .gw *::before,
    .gw *::after {
        box-sizing: border-box;
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 24px;
        border-bottom: 1px solid var(--line);
        background: var(--surface);
        position: sticky;
        top: 0;
        z-index: 5;
    }
    .brand {
        display: flex;
        align-items: center;
    }
    .mark {
        font-family: var(--voice);
        font-weight: 700;
        font-size: 20px;
        letter-spacing: 0.01em;
    }
    .mark-accent {
        color: var(--indicator-ink);
    }
    .ruler {
        display: inline-block;
        width: 64px;
        height: 12px;
        margin-left: 12px;
        background-image: repeating-linear-gradient(
            90deg,
            var(--line-strong) 0,
            var(--line-strong) 1px,
            transparent 1px,
            transparent 8px
        );
        opacity: 0.8;
    }
    .nav button {
        appearance: none;
        background: none;
        border: none;
        font-family: var(--ui);
        font-size: 14px;
        color: var(--ink-soft);
        padding: 6px 10px;
        margin-left: 2px;
        border-radius: 8px;
        cursor: pointer;
    }
    .nav button:hover {
        color: var(--ink);
        background: var(--paper);
    }
    .nav button.active {
        color: var(--indicator-ink);
        font-weight: 600;
    }
    .nav button:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }

    .col {
        max-width: 720px;
        margin: 0 auto;
        padding: 32px 24px 64px;
    }
    .col-wide {
        max-width: 1040px;
        margin: 0 auto;
        padding: 32px 24px 64px;
    }

    .eyebrow {
        font-family: var(--mono);
        font-size: 12px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--ink-faint);
        margin: 0 0 10px;
    }
    .display {
        font-family: var(--voice);
        font-size: 34px;
        line-height: 1.15;
        margin: 0 0 12px;
        font-weight: 700;
    }
    .lede {
        font-size: 18px;
        line-height: 1.6;
        color: var(--ink-soft);
        margin: 0 0 28px;
    }
    .muted {
        color: var(--ink-faint);
        font-size: 13px;
    }

    .action-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 22px;
        box-shadow: 0 6px 18px rgba(33, 31, 25, 0.08);
        margin-bottom: 22px;
    }
    .action-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
    }
    .action-title {
        font-family: var(--voice);
        font-size: 22px;
        margin: 0 0 6px;
    }
    .pill {
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 3px 9px;
        border-radius: 999px;
        border: 1px solid var(--line-strong);
        color: var(--ink-soft);
    }
    .diff-easy { background: var(--indicator-tint); }
    .diff-medium { background: var(--brass-tint); }
    .diff-hard { background: var(--clay-tint); }

    .primary {
        appearance: none;
        margin-top: 16px;
        border: 1px solid var(--indicator-ink);
        background: var(--indicator);
        color: #fff;
        font-family: var(--ui);
        font-size: 15px;
        font-weight: 600;
        padding: 11px 22px;
        border-radius: 10px;
        cursor: pointer;
    }
    .primary:hover:not(:disabled) {
        background: var(--indicator-ink);
    }
    .primary:disabled {
        opacity: 0.45;
        cursor: default;
    }
    .primary:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }

    .mini-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        grid-gap: 12px;
    }
    .mini {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .mini-n {
        display: block;
        font-family: var(--mono);
        font-size: 28px;
        color: var(--indicator-ink);
    }
    .mini-l {
        font-size: 12px;
        color: var(--ink-faint);
    }

    .session-meter {
        font-size: 14px;
        color: var(--ink-soft);
        margin-bottom: 14px;
    }
    .readout {
        font-family: var(--mono);
        color: var(--indicator-ink);
        font-weight: 600;
    }

    .q-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 22px;
        box-shadow: 0 6px 18px rgba(33, 31, 25, 0.08);
    }
    .q-card.empty {
        color: var(--ink-soft);
    }
    .q-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .stem {
        font-family: var(--voice);
        font-size: 22px;
        line-height: 1.4;
        margin: 0 0 18px;
        font-weight: 600;
    }
    .opts {
        list-style: none;
        margin: 0 0 16px;
        padding: 0;
    }
    .opts li {
        margin-bottom: 10px;
    }
    /* !important defeats Anki's global `button` night-mode styling (base.scss),
       so the selected / correct / wrong states are always visible. */
    .opt {
        display: flex;
        align-items: center;
        width: 100%;
        text-align: left;
        padding: 12px 14px;
        border: 2px solid var(--line-strong) !important;
        border-radius: 10px;
        background: var(--paper) !important;
        color: var(--ink) !important;
        font-size: 16px;
        cursor: pointer;
    }
    .opt:hover:not(:disabled) {
        border-color: var(--indicator) !important;
    }
    .opt:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }
    .opt-key {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        margin-right: 12px;
        border-radius: 6px;
        border: 1px solid var(--line-strong);
        font-family: var(--mono);
        font-size: 13px;
        color: var(--ink-soft) !important;
        background: var(--surface) !important;
    }
    .opt.sel {
        border-color: var(--indicator) !important;
        background: var(--indicator-tint) !important;
    }
    .opt.sel .opt-key {
        background: var(--indicator) !important;
        color: #fff !important;
        border-color: var(--indicator) !important;
    }
    .opt.correct {
        border-color: var(--indicator) !important;
        background: var(--indicator-tint) !important;
    }
    .opt.correct .opt-key {
        background: var(--indicator) !important;
        color: #fff !important;
        border-color: var(--indicator) !important;
    }
    .opt.wrong {
        border-color: var(--clay-ink) !important;
        background: var(--clay-tint) !important;
    }
    .opt.wrong .opt-key {
        background: var(--clay-ink) !important;
        color: #fff !important;
        border-color: var(--clay-ink) !important;
    }
    .opt.muted {
        opacity: 0.5;
    }

    .seal {
        margin: 10px 2px 0;
        font-size: 13px;
        color: var(--ink-faint);
    }
    .verdict {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid var(--line-strong);
        margin-bottom: 10px;
    }
    .verdict.ok {
        background: var(--indicator-tint);
        border-color: var(--indicator);
    }
    .verdict.no {
        background: var(--clay-tint);
        border-color: var(--clay-ink);
    }
    .explain {
        line-height: 1.55;
        margin: 0 0 6px;
    }

    .score-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        grid-gap: 16px;
        margin-bottom: 24px;
    }
    .measure {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 20px;
    }
    .measure-q {
        font-family: var(--voice);
        font-size: 16px;
        color: var(--ink);
        margin: 4px 0 16px;
    }
    .needle-wrap {
        border-top: 1px solid var(--line);
        padding-top: 14px;
    }
    .readout-lg {
        display: block;
        font-family: var(--mono);
        font-size: 52px;
        line-height: 1;
        color: var(--indicator-ink);
    }
    .band {
        font-family: var(--mono);
        font-size: 13px;
        color: var(--ink-faint);
    }
    .calib {
        border-top: 1px solid var(--line);
        margin-top: 14px;
        padding-top: 12px;
    }
    .calib-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    .cal-ok {
        background: var(--indicator-tint);
        border-color: var(--indicator);
        color: var(--indicator-ink);
    }
    .cal-warn {
        background: var(--clay-tint);
        border-color: var(--clay-ink);
        color: var(--clay-ink);
    }
    .calib-bars {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        margin-top: 10px;
    }
    .calib-col {
        flex: 1 1 0;
        text-align: center;
        margin: 0 2px;
    }
    .calib-track {
        position: relative;
        height: 84px;
        border-radius: 6px 6px 0 0;
        background: var(--sunk);
        overflow: hidden;
    }
    .calib-fill {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        background: var(--indicator);
    }
    .calib-target {
        position: absolute;
        left: 0;
        right: 0;
        height: 0;
        border-top: 2px dashed var(--clay-ink);
        z-index: 1;
    }
    .calib-pct {
        display: block;
        font-family: var(--mono);
        font-size: 11px;
        color: var(--ink-soft);
        margin-top: 4px;
    }
    .calib-x {
        display: block;
        font-size: 10px;
        color: var(--ink-faint);
    }

    .abstain {
        border-top: 1px solid var(--line);
        padding-top: 14px;
    }
    .abstain-mark {
        font-family: var(--mono);
        font-size: 28px;
        letter-spacing: 0.2em;
        color: var(--ink-faint);
    }
    .abstain-title {
        font-weight: 600;
        margin: 6px 0 4px;
        color: var(--ink-soft);
    }
    .unmet {
        margin: 4px 0 0 16px;
        padding: 0;
        font-size: 12px;
        color: var(--ink-faint);
        line-height: 1.5;
    }
    .next {
        margin-top: 10px;
        font-size: 13px;
        color: var(--indicator-ink);
    }

    .coverage {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 20px;
    }
    .coverage-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .bar {
        height: 10px;
        background: var(--sunk);
        border-radius: 999px;
        overflow: hidden;
    }
    .bar-fill {
        height: 100%;
        background: var(--indicator);
        border-radius: 999px;
    }

    .err-list {
        list-style: none;
        margin: 0;
        padding: 0;
    }
    .err {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .err-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
    }
    .err-stem {
        margin: 0;
        line-height: 1.5;
    }

    .ghost {
        appearance: none;
        margin: 10px 0 0 10px;
        border: 1px solid var(--line-strong);
        background: transparent;
        color: var(--ink-soft);
        font-family: var(--ui);
        font-size: 14px;
        padding: 10px 16px;
        border-radius: 10px;
        cursor: pointer;
    }
    .ghost:hover {
        border-color: var(--indicator);
        color: var(--ink);
    }

    .field {
        display: block;
        margin-bottom: 14px;
    }
    .field-label {
        display: block;
        font-size: 13px;
        color: var(--ink-soft);
        margin-bottom: 6px;
    }
    .field input {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--line-strong);
        border-radius: 8px;
        background: var(--paper);
        color: var(--ink);
        font-family: var(--ui);
        font-size: 15px;
    }
    .field input:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 1px;
    }

    .focus-list {
        list-style: none;
        margin: 12px 0 4px;
        padding: 0;
    }
    .focus-list li {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    .focus-name {
        flex: 0 0 40%;
        font-size: 14px;
    }
    .focus-bar {
        flex: 1 1 auto;
        height: 8px;
        margin: 0 10px;
        background: var(--sunk);
        border-radius: 999px;
        overflow: hidden;
    }
    .focus-fill {
        display: block;
        height: 100%;
        background: var(--indicator);
        border-radius: 999px;
    }
    .focus-status {
        flex: 0 0 auto;
        font-family: var(--mono);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .s-weak {
        color: var(--clay-ink);
    }
    .s-developing {
        color: var(--brass-tint);
        color: #8a6a22;
    }
    .s-strong {
        color: var(--indicator-ink);
    }
    .all-topics {
        margin-top: 16px;
    }
    .all-topics summary {
        cursor: pointer;
        font-size: 14px;
        color: var(--ink-soft);
    }
    .obj-list,
    .steps {
        margin: 6px 0 16px 18px;
        line-height: 1.55;
        color: var(--ink);
    }
    .obj-list li,
    .steps li {
        margin-bottom: 4px;
    }
    .obj-list sup,
    .steps sup,
    .stem sup,
    .opt sup,
    .explain sup {
        font-size: 0.72em;
    }

    @media (max-width: 720px) {
        .score-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
