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
        GmatQuestion,
        ScheduledCard,
        Counts,
        ErrorEntry,
        ErrorWhy,
        PretestQuestion,
        Lesson,
        LessonItem,
        LessonTopic,
        TodaySession,
        TodayBlock,
        GmatPacing,
        StudyCalendar,
        CalendarDay,
        CalendarItem,
        MockQuestion,
        MockResult,
        MockReport,
        OfficialScore,
        GmatStats,
        TestLibrary,
    } from "./api";
    import {
        logError,
        saveErrorTakeaway,
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
        fetchToday,
        fetchCalendar,
        fetchMockPool,
        fetchTopicQuestions,
        fetchMilestoneQuestions,
        submitMock,
        submitQuiz,
        fetchTests,
        fetchTestQuestions,
        fetchOfficialScores,
        saveOfficialScore,
        fetchStats,
        openFullStats,
        openDecks,
        renderMath,
        setAiEnabledRemote,
        addGeneratedQuestions,
    } from "./api";
    import { authEnabled, onUser, signIn, signUp, signOutUser, type AuthUser } from "./auth";
    import { getAiEnabled, setAiEnabled, generateJson, Schema } from "./ai";
    import { checkItem } from "./aiChecker";
    import { coachMiss } from "./coach";
    import { pullAccountState, scheduleStatePush, startAutoSync, stopAutoSync } from "./sync";
    import {
        pullCollectionOnLogin,
        scheduleCollectionUpload,
        uploadCollection,
    } from "./colsync";

    export let overview: GmatOverview;

    // 6-tab shell: Today(home) / Study / Drill / Progress(dashboard) / Error Log
    // (errors) / Sign-out. "study" folds in the old "learn" topic list; "drill"
    // is the renamed FSRS practice; "lesson" is the standalone lesson player.
    type View =
        | "home"
        | "study"
        | "drill"
        | "dashboard"
        | "errors"
        | "onboarding"
        | "pretest"
        | "plan"
        | "lesson"
        | "mock"
        | "tests";
    let view: View = "home";

    // Context passed to the reusable lesson/practice snippets so the same markup
    // renders standalone (a whole view) AND inline (inside Today / Study), with a
    // context-appropriate "back" control on completion.
    type InlineCtx = { onExit: () => void; exitLabel: string };

    // ---- progress (integrated Stats) ----
    let stats: GmatStats | null = null;

    // ---- auth (Firebase; dormant until firebaseConfig has a real apiKey) ----
    let authUser: AuthUser | null = null;
    let authReady = !authEnabled; // when disabled: ready, no gate
    let authMode: "signin" | "signup" = "signin";
    let authEmail = "";
    let authPassword = "";
    let authError = "";
    let authBusy = false;

    async function submitAuth(): Promise<void> {
        if (authBusy || !authEmail || !authPassword) return;
        authError = "";
        authBusy = true;
        try {
            if (authMode === "signin") {
                await signIn(authEmail, authPassword);
            } else {
                await signUp(authEmail, authPassword);
            }
            authPassword = "";
        } catch (e) {
            authError = (e as Error).message;
        }
        authBusy = false;
    }

    async function doSignOut(): Promise<void> {
        // Push the whole collection up before auth is torn down (Cloud Storage
        // rejects writes once signed out). Best-effort - never block sign-out.
        if (authUser) {
            try {
                await uploadCollection(authUser.uid);
            } catch (e) {
                console.error("GMATWiz collection upload on sign-out failed", e);
            }
        }
        await signOutUser();
    }

    /** Debounced push of this device's state to the signed-in account. */
    function pushIfAuthed(): void {
        if (authUser) scheduleStatePush(authUser.uid);
    }

    /** Reconcile the local AI override with the synced config: a value stored on
        the account (any device) wins over the local default. Then refresh the
        reactive mirror the template reads. */
    function reconcileAiFlag(): void {
        if (typeof overview.gmatAiEnabled === "boolean") {
            setAiEnabled(overview.gmatAiEnabled);
        }
        aiOn = getAiEnabled();
    }

    /** Flip AI on/off: persist locally (localStorage) AND mirror to synced config
        so the choice follows the account. Best-effort; never blocks the UI. */
    async function toggleAi(): Promise<void> {
        if (aiBusy) return;
        aiBusy = true;
        const next = !aiOn;
        setAiEnabled(next);
        // getAiEnabled() re-applies the Firebase-configured guard, so the switch
        // honestly stays off if AI can't run here.
        aiOn = getAiEnabled();
        try {
            await setAiEnabledRemote(next);
            pushIfAuthed();
        } catch (_e) {
            /* the local override still holds; sync is best-effort */
        }
        aiBusy = false;
    }

    // Ambient "spellfall": GMAT math glyphs drifting behind the app (the
    // subject's own vernacular as magic), plus soft floating gold orbs.
    // Precomputed so it's stable + cheap; paused under prefers-reduced-motion.
    const rand = (i: number, n: number) =>
        ((Math.sin(i * 12.9898 + n * 78.233) * 43758.5453) % 1 + 1) % 1;
    const SKY_CHARS = "× ÷ √ π % ∑ ∞ + − = ² ³ ½ ¼ ✦ ✧ ⋆ ✶ 7 3 x π".split(" ");
    const skyGlyphs = Array.from({ length: 34 }, (_, i) => ({
        ch: SKY_CHARS[Math.floor(rand(i, 1) * SKY_CHARS.length)],
        x: Math.round(rand(i, 2) * 100),
        size: 14 + Math.round(rand(i, 3) * 28),
        dur: 13 + Math.round(rand(i, 4) * 22),
        delay: -Math.round(rand(i, 5) * 34),
        gold: rand(i, 6) > 0.28, // mostly gold, a few amethyst
    }));
    const skyOrbs = Array.from({ length: 9 }, (_, i) => ({
        x: Math.round(rand(i + 100, 2) * 100),
        size: 90 + Math.round(rand(i + 100, 3) * 180),
        dur: 26 + Math.round(rand(i + 100, 4) * 26),
        delay: -Math.round(rand(i + 100, 5) * 40),
        gold: rand(i + 100, 6) > 0.4,
    }));

    // ---- official/practice-test scores (calibration) ----
    let officialScores: OfficialScore[] = [];
    let osQuant = "";
    let osTotal = "";
    let osDate = "";
    let osSaving = false;
    let osError = "";

    // ---- today's assembled session ----
    let today: TodaySession | null = null;
    $: todayEst = today
        ? today.blocks.reduce((sum, b) => sum + b.est_minutes, 0)
        : 0;

    // ---- forward study calendar (Progress tab + jump-ahead) ----
    // Derived server-side from CURRENT state, so re-fetching recalibrates it.
    let calendar: StudyCalendar | null = null;
    // group the projected days into rows of 7 (aligned to the study/rest cycle)
    // for the week-by-week grid
    $: calendarWeeks = calendar
        ? chunk(calendar.days, 7)
        : ([] as CalendarDay[][]);
    // the next FUTURE day that carries a lesson - powers "Start tomorrow's plan"
    $: nextLessonDay =
        calendar?.days.find(
            (d) => d.day_offset > 0 && d.items.some((it) => it.kind === "lesson"),
        ) ?? null;
    $: nextLessonItem =
        nextLessonDay?.items.find((it) => it.kind === "lesson") ?? null;

    function chunk<T>(arr: T[], n: number): T[][] {
        const out: T[][] = [];
        for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
        return out;
    }

    /** Short, human date like "Aug 4" from a YYYY-MM-DD string (local, no TZ shift). */
    function shortDate(iso: string): string {
        const [y, m, d] = iso.split("-").map((x) => parseInt(x, 10));
        if (!y || !m || !d) return iso;
        const months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ];
        return `${months[m - 1]} ${d}`;
    }

    // one glyph per calendar item kind, in the app's mono "instrument" voice
    const CAL_ITEM_GLYPH: Record<string, string> = {
        lesson: "\u2748", // teach
        quiz: "\u2713", // check
        requiz: "\u21BB", // spaced re-check
        milestone: "\u25C6", // checkpoint
        review: "\u25CB", // spaced review
        drill: "\u25B8", // practice
        practice_test: "\u25A3", // full test
        rest: "\u00B7", // rest
    };

    /** Short chip label for a calendar item (the topic name for teach/quiz, a
        plain word otherwise) - the title carries the full text on hover. */
    function calChipLabel(it: CalendarItem): string {
        if (
            (it.kind === "lesson" || it.kind === "quiz" || it.kind === "requiz") &&
            it.topic
        ) {
            return topicLabel(it.topic);
        }
        const words: Record<string, string> = {
            milestone: "Milestone",
            practice_test: "Practice test",
            review: "Review",
            drill: "Drill",
            rest: "Rest",
        };
        return words[it.kind] ?? it.title;
    }

    // A new account (no plan yet) must take the diagnostic before the rest of
    // the app unlocks: sign up -> diagnostic -> dashboard + everything else.
    $: locked = !overview.plan;

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
    let targetScore = 645;
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
    // error-log capture: a wrong answer must be classified before moving on
    let pendingWhy = false;
    let guessLogged = false;
    let answerMs = 0;
    let practiceElapsed = 0;
    let practiceTimer = 0;
    const TARGET_SECS = 128; // GMAT Focus Quant pace: 45 min / 21 questions
    // Topic-quiz length (mirrors GMAT_QUIZ_N on both engines): 7 so a single
    // miss still clears the 85% mastery bar (6/7 = 85.7% >= 0.85).
    const QUIZ_N = 7;

    // The practice card feeds from two sources: the real scheduler (infinite
    // Drill + Today's review/practice blocks) or a fixed topic-scoped pool
    // (Study -> Practice). `activeQuestion` normalizes whichever is current so the
    // same card markup + why-capture serves both.
    type PracticeMode = "scheduler" | "topic";
    let practiceMode: PracticeMode = "scheduler";
    let topicPool: MockQuestion[] = [];
    let topicIdx = 0;
    let topicLabelText = "";
    // The taxonomy id backing the current topic/ephemeral session, so
    // "Generate more" can keep targeting it (topicLabelText is only display).
    let practiceTopicId = "";
    // AI front-queue (Drill/scheduler mode): generated questions are served
    // BEFORE the scheduler card, so "Generate with AI" injects them as the next
    // few questions. On desktop they are admitted as real cards (card_id set) and
    // answered as REAL FSRS reviews; on mobile (no importer) card_id is null and
    // they're practice-only. Either way, wrong answers hit the error log.
    interface FrontItem {
        card_id: number | null;
        stem: string;
        options: Record<string, string>;
        correct: string;
        explanation: string;
        topic: string;
        difficulty: string;
    }
    let aiFront: FrontItem[] = [];
    $: servingFront = practiceMode === "scheduler" && aiFront.length > 0;

    // ---- AI features (default OFF; user opt-in, mirrored to synced config) ----
    let aiOn = false; // reactive mirror of getAiEnabled() for the template
    let aiBusy = false; // toggle request in flight
    // On-demand hybrid generation (Drill + Study). Never runs when AI is off.
    let aiGenerating = false;
    let aiNote = ""; // soft, themed status line (success or "AI unavailable")
    let aiNoteOk = false; // true => success note (added/generated), false => problem

    // ---- per-session review (drives the End-session summary) ----
    interface SessionAnswer {
        stem: string;
        topic: string;
        chosen: string;
        correct: string;
        isCorrect: boolean;
    }
    let sessionLog: SessionAnswer[] = [];
    let sessionEnded = false;
    $: sessionRight = sessionLog.filter((a) => a.isCorrect).length;
    $: sessionWrong = sessionLog.length - sessionRight;
    $: sessionPct = sessionLog.length
        ? Math.round((100 * sessionRight) / sessionLog.length)
        : 0;

    interface ActiveQuestion {
        stem: string;
        options: Record<string, string>;
        correct: string;
        explanation: string;
        topic: string;
        difficulty: string;
    }
    $: activeQuestion =
        practiceMode === "topic"
            ? topicPool[topicIdx]
                ? ({
                      stem: topicPool[topicIdx].stem,
                      options: topicPool[topicIdx].options,
                      correct: topicPool[topicIdx].correct,
                      explanation: topicPool[topicIdx].explanation ?? "",
                      topic: topicPool[topicIdx].topic,
                      difficulty: topicPool[topicIdx].difficulty,
                  } as ActiveQuestion)
                : null
            : aiFront.length > 0
              ? ({
                    stem: aiFront[0].stem,
                    options: aiFront[0].options,
                    correct: aiFront[0].correct,
                    explanation: aiFront[0].explanation ?? "",
                    topic: aiFront[0].topic,
                    difficulty: aiFront[0].difficulty,
                } as ActiveQuestion)
              : card
                ? ({
                      stem: card.stem,
                      options: card.options,
                      correct: card.correct,
                      explanation: card.explanation,
                      topic: card.topic,
                      difficulty: card.difficulty,
                  } as ActiveQuestion)
                : null;
    $: queueRemaining =
        practiceMode === "topic"
            ? Math.max(0, topicPool.length - topicIdx)
            : remaining + aiFront.length;
    $: isLastTopicQ =
        practiceMode === "topic" && topicIdx >= topicPool.length - 1;

    // ---- inline task execution (Today runs its tasks without leaving the tab) --
    // The block currently running inline on the Today tab (null = show the list).
    let todayActive: TodayBlock | null = null;
    // The topic currently being practiced inline on the Study tab (null = list).
    let studyActive: string | null = null;
    // Locally-tracked completed Today blocks (keyed) so finished tasks read as
    // done and the "done for today" state can trigger even for the always-present
    // targeted-practice block that the backend keeps re-emitting.
    let todayDone = new Set<string>();
    function blockKey(b: TodayBlock): string {
        return `${b.kind}:${b.topic ?? ""}:${b.form_id ?? ""}`;
    }
    $: allTodayDone =
        !!today &&
        today.blocks.length > 0 &&
        today.blocks.every((b) => todayDone.has(blockKey(b)));
    $: firstPendingBlock = today
        ? today.blocks.find((b) => !todayDone.has(blockKey(b))) ?? null
        : null;

    // Study is section-split; only Quant exists in Phase 2, so every authored
    // lesson topic is a Quant topic. A later section would filter on domain here.
    $: quantTopics = lessonTopics;

    // ---- mock exam state (timed, exam conditions, no mid-test feedback) ----
    // Exam-accurate: adaptive selection, bookmark/flag, a pre-submit review
    // screen, and up to 3 answer changes in review (GMAT Focus rules).
    type MockPhase = "intro" | "run" | "review" | "report";
    interface MockItem {
        q: MockQuestion;
        answer: string | null;
        flagged: boolean;
        ms: number;
        firstShownAt: number;
    }
    const MOCK_MAX_CHANGES = 3;
    let mockPhase: MockPhase = "intro";
    let mockPool: MockQuestion[] = [];
    let mockCount = 21;
    let mockSecondsLeft = 0;
    let mockTimer = 0;
    let mockItems: MockItem[] = [];
    let mockPos = 0;
    let mockDiffIdx = 1; // 0 easy, 1 medium, 2 hard - simple adaptive ladder
    let mockChangesLeft = MOCK_MAX_CHANGES;
    let mockReport: MockReport | null = null;
    let mockWhy: (ErrorWhy | null)[] = []; // per-miss classification on the report
    let mockSubmitting = false;
    let mockMissResults: MockResult[] = []; // misses to classify on the report
    // when this mock is a fixed practice-test form (vs. the adaptive mock), the
    // form is served in order and recorded as taken on submit.
    let mockFormId: string | null = null;
    let mockFormYear: string | null = null;
    let mockLabel = "";
    // The timed flow serves three assessment tiers: a full "mock"/practice test,
    // a single-topic "quiz" (soft mastery gate), and a mixed "milestone" check.
    // quiz/milestone submit via gmatSubmitQuiz; the run/review/report UI is shared.
    type MockKind = "mock" | "quiz" | "milestone";
    let mockKind: MockKind = "mock";
    let mockQuizTopic = ""; // topic id for a "quiz"
    let mockQuizLabel = ""; // display label for a "quiz"/"milestone"
    let mockReturnView: View = "home"; // where "Done" returns (Today vs Study)

    // ---- practice-test library (full-length timed forms, grouped by year) ----
    let tests: TestLibrary | null = null;
    $: testYears = tests
        ? Object.keys(tests.years).sort((a, b) => b.localeCompare(a))
        : [];

    $: optionEntries = activeQuestion ? Object.entries(activeQuestion.options) : [];
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

    let errors: ErrorEntry[] = [];

    /** (Re)start the per-question pace timer used by both practice modes. */
    function restartPracticeTimer(): void {
        if (practiceTimer) clearInterval(practiceTimer);
        practiceElapsed = 0;
        practiceTimer = window.setInterval(() => {
            if (!revealed) practiceElapsed += 1;
        }, 1000);
    }

    async function loadNextCard(): Promise<void> {
        // any scheduler-backed load returns us to scheduler mode (e.g. Drill nav
        // after a topic session)
        practiceMode = "scheduler";
        loading = true;
        selected = null;
        revealed = false;
        pendingWhy = false;
        guessLogged = false;
        const result = await fetchNextCard();
        card = result.card;
        counts = result.counts;
        started = Date.now();
        restartPracticeTimer();
        loading = false;
    }

    /** Start a fresh scheduler-backed drill session (resets the running tally). */
    async function startDrill(): Promise<void> {
        answered = 0;
        correctCount = 0;
        practiceTopicId = "";
        resetSession();
        await loadNextCard();
    }

    /** Clear the per-session review + generation notes at the start of a session. */
    function resetSession(): void {
        sessionLog = [];
        sessionEnded = false;
        aiNote = "";
        aiNoteOk = false;
        aiFront = [];
    }

    /** End the running practice session and show its review summary. */
    function endSession(): void {
        sessionEnded = true;
        stopTimer();
    }

    /** Advance within a topic-scoped (fixed pool) practice session. */
    function advanceTopic(): void {
        selected = null;
        revealed = false;
        pendingWhy = false;
        guessLogged = false;
        topicIdx += 1;
        started = Date.now();
        restartPracticeTimer();
    }

    /** "Next" for whichever practice mode is running. */
    async function practiceNext(): Promise<void> {
        if (practiceMode === "topic") {
            advanceTopic();
        } else if (aiFront.length > 0) {
            // Consume the front-queue AI question, then fall back to the
            // already-loaded scheduler card when it's empty.
            aiFront = aiFront.slice(1);
            selected = null;
            revealed = false;
            pendingWhy = false;
            guessLogged = false;
            started = Date.now();
            restartPracticeTimer();
        } else {
            await loadNextCard();
        }
    }

    async function go(next: View): Promise<void> {
        stopTimer();
        // navigating via the nav always leaves any inline task in progress
        todayActive = null;
        studyActive = null;
        // Until the diagnostic produces a plan, only the Today gate is reachable.
        if (
            locked &&
            ["study", "drill", "lesson", "dashboard", "errors", "tests"].includes(next)
        ) {
            next = "home";
        }
        view = next;
        if (next === "drill") await startDrill();
        if (next === "tests") tests = await fetchTests();
        if (next === "errors") {
            errors = await fetchErrorLog();
            if (!lessonTopics.length) {
                lessonTopics = (await fetchLessonsIndex()).topics;
            }
        }
        if (next === "study") lessonTopics = (await fetchLessonsIndex()).topics;
        if (next === "home" || next === "dashboard") {
            const fresh = await refreshOverview();
            if (fresh) overview = fresh;
            reconcileAiFlag();
            if (next === "home" && overview.plan) {
                lessonTopics = (await fetchLessonsIndex()).topics;
                today = await fetchToday();
                calendar = await fetchCalendar();
            }
            if (next === "dashboard") {
                officialScores = await fetchOfficialScores();
                stats = await fetchStats();
                calendar = await fetchCalendar();
            }
        }
    }

    async function submitOfficialScore(): Promise<void> {
        const quant = parseInt(osQuant, 10);
        if (Number.isNaN(quant) || quant < 60 || quant > 90) {
            osError = "Enter a Quant score between 60 and 90.";
            return;
        }
        osSaving = true;
        osError = "";
        const total = osTotal ? parseInt(osTotal, 10) : null;
        const res = await saveOfficialScore({ quant, total, date: osDate });
        osSaving = false;
        if (!res.ok) {
            osError = res.error || "Could not save.";
            return;
        }
        osQuant = "";
        osTotal = "";
        osDate = "";
        officialScores = await fetchOfficialScores();
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
        pushIfAuthed();
    }

    async function startBlock(block: TodayBlock): Promise<void> {
        stopTimer();
        // The timed tiers (mock / topic quiz / milestone) stay full-screen (their
        // own intro/run/review/report phases). Everything else runs INLINE so the
        // nav stays on "Today".
        if (block.kind === "mock") {
            // a library-sourced block runs its specific form; otherwise adaptive mock
            await startMock(block.form_id);
            return;
        }
        if (block.kind === "quiz" && block.topic) {
            await startQuiz(block.topic, topicLabel(block.topic), "home");
            return;
        }
        if (block.kind === "milestone") {
            await startMilestone(block.count ?? 12, "home");
            return;
        }
        todayActive = block;
        if ((block.kind === "learn" || block.kind === "repair") && block.topic) {
            await loadLesson(block.topic);
        } else {
            // review / practice -> the scheduler-backed drill card, inline
            practiceMode = "scheduler";
            practiceTopicId = "";
            answered = 0;
            correctCount = 0;
            resetSession();
            await loadNextCard();
        }
    }

    /** Finish (or step out of) the inline Today task and return to the task list,
        refreshing so completed work drops off and progress updates. A lesson only
        counts as done once its player reaches the "done" phase; a drill counts as
        done whenever the student steps back (there is no natural end to it). */
    async function backToToday(): Promise<void> {
        if (todayActive) {
            const isLesson =
                todayActive.kind === "learn" || todayActive.kind === "repair";
            if (!isLesson || lessonPhase === "done") {
                todayDone = new Set(todayDone).add(blockKey(todayActive));
            }
        }
        todayActive = null;
        stopTimer();
        today = await fetchToday();
        calendar = await fetchCalendar();
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
    }

    /** "You're done for today" -> keep the momentum with extra spaced practice,
        inline on the Today tab (no plan advance - just more reps). */
    async function jumpAhead(): Promise<void> {
        await startBlock({
            kind: "practice",
            title: "Extra practice",
            detail: "getting ahead",
            est_minutes: 0,
        });
    }

    /** JUMP-AHEAD: pull the NEXT scheduled study day's lesson forward and run it
        inline today, reusing the lesson snippet. Because the calendar + Today are
        both derived from live state, completing it (markLearned) is reflected on
        the next fetch - the lesson simply moves up, nothing is double-counted. */
    async function startTomorrow(): Promise<void> {
        const topic = nextLessonItem?.topic;
        if (!topic) {
            // nothing new left to learn - fall back to extra practice
            await jumpAhead();
            return;
        }
        await startBlock({
            kind: "learn",
            title: `Learn: ${topicLabel(topic)}`,
            detail: "pulled forward from tomorrow's plan",
            topic,
            est_minutes: 12,
        });
    }

    /** Start an inline, topic-scoped practice session on the Study tab (fixed
        bank via gmatTopicQuestions), reusing the practice card + why-capture. */
    async function startTopicPractice(topic: string, label: string): Promise<void> {
        stopTimer();
        practiceMode = "topic";
        practiceTopicId = topic;
        topicLabelText = label;
        topicPool = [];
        topicIdx = 0;
        answered = 0;
        correctCount = 0;
        selected = null;
        revealed = false;
        pendingWhy = false;
        guessLogged = false;
        resetSession();
        loading = true;
        studyActive = topic;
        const data = await fetchTopicQuestions(topic, 10);
        topicPool = data.pool;
        started = Date.now();
        restartPracticeTimer();
        loading = false;
    }

    /** Leave the inline Study practice session and refresh topic mastery. */
    async function backToStudy(): Promise<void> {
        studyActive = null;
        practiceMode = "scheduler";
        stopTimer();
        lessonTopics = (await fetchLessonsIndex()).topics;
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
    }

    // ---- hybrid AI generation (Drill + Study) --------------------------------
    // Structured shape for one generated PS item (passed to generateJson as the
    // responseSchema and forwarded verbatim to the gmatGenerate proxy).
    const AI_GEN_SCHEMA = Schema.array({
        items: Schema.object({
            properties: {
                stem: Schema.string(),
                options: Schema.object({
                    properties: {
                        A: Schema.string(),
                        B: Schema.string(),
                        C: Schema.string(),
                        D: Schema.string(),
                        E: Schema.string(),
                    },
                }),
                correct: Schema.string(),
                explanation: Schema.string(),
                topic: Schema.string(),
                difficulty: Schema.string(),
            },
        }),
    });
    const AI_BATCH_SIZE = 4;
    const KEYS = ["A", "B", "C", "D", "E"];

    /** Map a topic's current mastery onto a target difficulty for generation. */
    function topicDifficulty(topicId: string): string {
        const t = (overview.plan?.topics ?? []).find((x) => x.topic === topicId);
        const m = t?.mastery ?? 0.5;
        return m < 0.4 ? "easy" : m < 0.7 ? "medium" : "hard";
    }

    /** The single weakest planned topic (weakest-first), for Drill generation. */
    function weakestTopic(): { id: string; label: string; difficulty: string } | null {
        const topics = [...(overview.plan?.topics ?? [])].sort(
            (a, b) => a.mastery - b.mastery,
        );
        const t = topics[0];
        if (!t) return null;
        return { id: t.topic, label: topicLabel(t.topic), difficulty: topicDifficulty(t.topic) };
    }

    function genPrompt(label: string, difficulty: string, n: number): string {
        return [
            `Create ${n} ORIGINAL GMAT Focus Quant Problem Solving questions on the topic "${label}".`,
            "Scope is strict: arithmetic and algebra only. NO geometry, NO coordinate geometry,",
            "NO Data Sufficiency, and NO questions that need a figure, chart, or table.",
            "Each question must:",
            "- be self-contained and solvable by hand (no calculator);",
            "- have exactly five options keyed A, B, C, D, E with exactly one correct answer;",
            `- match ${difficulty} difficulty;`,
            "- include a concise worked explanation that derives the correct answer;",
            "- be original — do not reproduce copyrighted or official GMAT items.",
            `Set each item's "topic" to "${label}" and "difficulty" to "${difficulty}".`,
            "Return a JSON array of objects with fields: stem, options {A,B,C,D,E}, correct,",
            "explanation, topic, difficulty.",
        ].join("\n");
    }

    /** Defensive normalize: enforce 5 non-empty options + a valid correct key,
        and force the taxonomy topic id so mastery tracking stays consistent. */
    function normalizeGen(
        raw: GmatQuestion,
        topicId: string,
        difficulty: string,
    ): GmatQuestion | null {
        if (!raw || typeof raw !== "object") return null;
        const src = (raw.options ?? {}) as Record<string, string>;
        const options: Record<string, string> = {};
        for (const k of KEYS) {
            const v = src[k];
            if (typeof v !== "string" || !v.trim()) return null;
            options[k] = v;
        }
        const correct = String(raw.correct ?? "").trim().toUpperCase();
        if (correct.length !== 1 || !KEYS.includes(correct)) return null;
        const stem = String(raw.stem ?? "").trim();
        if (!stem) return null;
        return {
            stem,
            options,
            correct,
            explanation: String(raw.explanation ?? ""),
            topic: topicId,
            difficulty: String(raw.difficulty ?? difficulty) || difficulty,
        };
    }

    /** Generate a batch and keep only items that PASS the 7f checker (fail-closed
        when AI is unavailable). Never throws. */
    async function generateChecked(
        topicId: string,
        label: string,
        difficulty: string,
        n: number,
    ): Promise<GmatQuestion[]> {
        const res = await generateJson<GmatQuestion[]>(
            genPrompt(label, difficulty, n),
            AI_GEN_SCHEMA,
        );
        if (!res.ok || !Array.isArray(res.value)) return [];
        const items: GmatQuestion[] = [];
        for (const raw of res.value) {
            const item = normalizeGen(raw, topicId, difficulty);
            if (item) items.push(item);
        }
        if (items.length === 0) return [];
        const checks = await Promise.all(
            items.map((it) =>
                checkItem({
                    stem: it.stem,
                    options: it.options,
                    correct: it.correct,
                    explanation: it.explanation,
                    topic: it.topic,
                }),
            ),
        );
        return items.filter((_, i) => checks[i].pass);
    }

    function toMock(q: GmatQuestion): MockQuestion {
        return {
            stem: q.stem,
            options: q.options,
            correct: q.correct,
            topic: q.topic,
            difficulty: q.difficulty,
            seen: false,
            explanation: q.explanation,
        };
    }

    /** Append more generated items to the current ephemeral/topic pool and resume
        (the button only shows when the pool is exhausted, so this steps forward). */
    function appendEphemeral(items: GmatQuestion[]): void {
        topicPool = [...topicPool, ...items.map(toMock)];
        selected = null;
        revealed = false;
        pendingWhy = false;
        guessLogged = false;
        started = Date.now();
        restartPracticeTimer();
    }

    /** On-demand generation for whichever practice mode is running. Targets the
        current topic (Study/ephemeral) or the weakest planned topic (Drill). */
    async function generateMore(): Promise<void> {
        if (aiGenerating) return;
        aiNote = "";
        aiNoteOk = false;
        if (!aiOn) {
            aiNote = "AI is off — turn it on in Progress to generate questions.";
            return;
        }
        const target =
            practiceMode === "topic" && practiceTopicId
                ? {
                      id: practiceTopicId,
                      label: topicLabelText || topicLabel(practiceTopicId),
                      difficulty: topicDifficulty(practiceTopicId),
                  }
                : weakestTopic();
        if (!target) {
            aiNote = "No target topic yet — take your diagnostic first.";
            return;
        }
        aiGenerating = true;
        let survivors: GmatQuestion[] = [];
        try {
            survivors = await generateChecked(
                target.id,
                target.label,
                target.difficulty,
                AI_BATCH_SIZE,
            );
        } catch (_e) {
            survivors = [];
        }
        if (survivors.length === 0) {
            aiNote = "AI unavailable — couldn't generate usable questions. Using your fixed bank.";
            aiGenerating = false;
            return;
        }
        const n = survivors.length;
        const plural = n === 1 ? "" : "s";
        if (practiceMode === "topic") {
            // Study / ephemeral session: append and continue.
            appendEphemeral(survivors);
            aiNote = `Generated ${n} fresh AI question${plural} for this session.`;
        } else {
            // Drill: admit them to the bank as real spaced cards, then push those
            // to the FRONT so they're the immediate next questions AND get real
            // reviews. Mobile (no importer) returns no cards -> practice-only.
            let admitted: FrontItem[] = [];
            try {
                const res = await addGeneratedQuestions(survivors);
                admitted = (res.cards ?? []).map((c) => ({
                    card_id: c.card_id,
                    stem: c.stem,
                    options: c.options,
                    correct: c.correct,
                    explanation: c.explanation,
                    topic: c.topic,
                    difficulty: c.difficulty,
                }));
            } catch (_e) {
                admitted = [];
            }
            const front: FrontItem[] =
                admitted.length > 0
                    ? admitted
                    : survivors.map((q) => ({
                          card_id: null,
                          stem: q.stem,
                          options: q.options,
                          correct: q.correct,
                          explanation: q.explanation ?? "",
                          topic: q.topic,
                          difficulty: q.difficulty,
                      }));
            aiFront = [...front, ...aiFront];
            selected = null;
            revealed = false;
            pendingWhy = false;
            guessLogged = false;
            started = Date.now();
            restartPracticeTimer();
            aiNote =
                admitted.length > 0
                    ? `Added ${front.length} AI question${plural} to your bank — up next.`
                    : `Generated ${front.length} AI question${plural} — up next (this session).`;
            pushIfAuthed();
        }
        aiNoteOk = true;
        aiGenerating = false;
    }

    function paceLabel(p: GmatPacing): string {
        if (p.status === "on_track") return "On track";
        if (p.status === "behind") return "Behind pace";
        if (p.status === "learning_complete") return "Learning complete";
        return "";
    }

    function choose(key: string): void {
        if (!revealed) selected = key;
    }

    async function commit(): Promise<void> {
        if (selected === null || revealed || !activeQuestion) return;
        revealed = true;
        answered += 1;
        answerMs = Date.now() - started;
        const isCorrect = selected === activeQuestion.correct;
        // Record the answer for the End-session review (both practice modes).
        sessionLog = [
            ...sessionLog,
            {
                stem: activeQuestion.stem,
                topic: activeQuestion.topic,
                chosen: selected,
                correct: activeQuestion.correct,
                isCorrect,
            },
        ];
        if (isCorrect) {
            correctCount += 1;
        } else {
            // Error log is required: classify the miss before the next question.
            pendingWhy = true;
        }
        // A scheduler card records a REAL review (Good if right, Again if wrong).
        // A fixed topic-pool question has no card to schedule; a wrong answer is
        // still logged to the error log via classifyMiss below.
        if (practiceMode === "scheduler" && aiFront.length > 0) {
            // Front-queue AI card: record a REAL review when it was admitted to
            // the bank (desktop, card_id set); mobile ephemeral items have no id.
            const fid = aiFront[0].card_id;
            if (fid != null) {
                await answerCard(fid, isCorrect, answerMs);
                pushIfAuthed();
            }
        } else if (practiceMode === "scheduler" && card) {
            await answerCard(card.card_id, isCorrect, answerMs);
            pushIfAuthed();
        }
    }

    /** One-prompt error-log capture: why did the miss happen? */
    async function classifyMiss(why: ErrorWhy): Promise<void> {
        if (!activeQuestion || selected === null) return;
        pendingWhy = false;
        await logError({
            stem: activeQuestion.stem,
            topic: activeQuestion.topic,
            chosen: selected,
            correct: activeQuestion.correct,
            why,
            ms: answerMs,
            options: activeQuestion.options,
            explanation: activeQuestion.explanation || undefined,
        });
        pushIfAuthed();
    }

    /** Correct, but only by guessing - honesty beats a lucky streak. */
    async function markGuess(): Promise<void> {
        if (!activeQuestion || selected === null || guessLogged) return;
        guessLogged = true;
        await logError({
            stem: activeQuestion.stem,
            topic: activeQuestion.topic,
            chosen: selected,
            correct: activeQuestion.correct,
            why: "guess",
            ms: answerMs,
            options: activeQuestion.options,
            explanation: activeQuestion.explanation || undefined,
        });
        pushIfAuthed();
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
        if (practiceTimer) {
            clearInterval(practiceTimer);
            practiceTimer = 0;
        }
        if (mockTimer) {
            clearInterval(mockTimer);
            mockTimer = 0;
        }
    }

    function startDiagnostic(): void {
        if (overview.profile) {
            examDate = overview.profile.exam_date || "";
            daysPerWeek = overview.profile.days_per_week || 5;
            targetScore = overview.profile.target_score || 645;
        }
        view = "onboarding";
    }

    async function beginPretest(): Promise<void> {
        await saveProfile({
            exam_date: examDate,
            days_per_week: daysPerWeek,
            target_score: targetScore,
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
        pushIfAuthed();
        submitting = false;
        view = "plan";
    }

    $: pretestCurrent = pretestQs[pretestIdx];
    $: pretestOptions = pretestCurrent ? Object.entries(pretestCurrent.options) : [];

    // ---- lesson loop (I-do -> we-do -> you-do) ----
    /** Load a lesson's state WITHOUT switching views, so the lesson player can
        render inline on the Today tab as well as in its own view. */
    async function loadLesson(topicId: string): Promise<void> {
        stopTimer();
        lessonLoading = true;
        lesson = await fetchLesson(topicId);
        lessonPhase = "intro";
        lessonIdx = 0;
        lessonSelected = null;
        lessonRevealed = false;
        lessonLoading = false;
    }

    /** Open the standalone lesson player (Study -> Learn, error-log repair). */
    async function openLesson(topicId: string): Promise<void> {
        view = "lesson";
        await loadLesson(topicId);
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
                options: lessonItem.options,
                explanation: lessonItem.explanation || undefined,
            });
        }
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
        pushIfAuthed();
        await go(target);
    }

    // ---- error log: filters + repair-now + AI coach ----
    let errorFilter: "all" | ErrorWhy = "all";
    let errInfoOpen = false; // toggles the "how error types work" explainer
    let coachLoadingTs: number | null = null;
    let coachUnavailableTs: Record<number, boolean> = {};
    $: filteredErrors =
        errorFilter === "all" ? errors : errors.filter((e) => (e.why || "") === errorFilter);
    $: hasLessonFor = new Set(lessonTopics.map((t) => t.topic_id));

    async function repairNow(e: ErrorEntry): Promise<void> {
        // Concept gaps get the lesson again; everything else gets applied practice.
        if (e.why === "concept_gap" && e.topic && hasLessonFor.has(e.topic)) {
            await openLesson(e.topic);
        } else {
            await go("drill");
        }
    }

    function mockMissOptions(miss: MockResult): Record<string, string> | undefined {
        const it = mockItems.find(
            (x) => x.q.stem === miss.stem && (x.answer ?? "") === miss.chosen,
        );
        return it?.q.options;
    }

    async function coachErrorEntry(e: ErrorEntry): Promise<void> {
        if (coachLoadingTs !== null) return;
        coachLoadingTs = e.ts;
        coachUnavailableTs = { ...coachUnavailableTs, [e.ts]: false };
        const result = await coachMiss(e);
        coachLoadingTs = null;
        if (result.ok) {
            await saveErrorTakeaway(e.ts, result.value);
            errors = errors.map((err) =>
                err.ts === e.ts ? { ...err, ai_takeaway: result.value } : err,
            );
        } else {
            coachUnavailableTs = { ...coachUnavailableTs, [e.ts]: true };
        }
    }

    // ---- mock exam (timed section, exam conditions) ----
    // With no formId this is the adaptive mock (pool + adaptive ladder). With a
    // formId it runs a fixed practice-test form: the same timed UI, but the pool
    // is served in its given order and the result is recorded against the form.
    async function startMock(formId?: string, year?: string): Promise<void> {
        stopTimer();
        mockPhase = "intro";
        mockReport = null;
        mockKind = "mock";
        mockReturnView = "home";
        view = "mock";
        if (formId) {
            mockFormId = formId;
            mockFormYear = year ?? null;
            const data = await fetchTestQuestions(formId);
            mockPool = data.pool;
            mockCount = data.pool.length || data.count;
            mockSecondsLeft = data.seconds;
            mockLabel = data.label ?? "";
        } else {
            mockFormId = null;
            mockFormYear = null;
            mockLabel = "";
            const data = await fetchMockPool();
            mockPool = data.pool;
            mockCount = Math.min(data.count, data.pool.length);
            mockSecondsLeft = data.seconds;
        }
    }

    /** A single-topic quiz (soft mastery gate) run through the timed-mock flow:
        7 questions, lighter clock, submitted via gmatSubmitQuiz. */
    async function startQuiz(
        topic: string,
        label: string,
        returnView: View,
    ): Promise<void> {
        stopTimer();
        mockPhase = "intro";
        mockReport = null;
        mockKind = "quiz";
        mockReturnView = returnView;
        mockFormId = null;
        mockFormYear = null;
        mockLabel = "";
        mockQuizTopic = topic;
        mockQuizLabel = label;
        view = "mock";
        const data = await fetchTopicQuestions(topic, QUIZ_N);
        mockPool = data.pool;
        mockCount = Math.min(QUIZ_N, data.pool.length);
        // lighter than a full section: ~2:08/question
        mockSecondsLeft = Math.max(1, mockCount) * TARGET_SECS;
    }

    /** A milestone checkpoint (mixed across learned topics) through the timed
        flow: ~12 questions, timed, submitted via gmatSubmitQuiz. */
    async function startMilestone(count = 12, returnView: View = "home"): Promise<void> {
        stopTimer();
        mockPhase = "intro";
        mockReport = null;
        mockKind = "milestone";
        mockReturnView = returnView;
        mockFormId = null;
        mockFormYear = null;
        mockLabel = "";
        mockQuizTopic = "";
        mockQuizLabel = "";
        view = "mock";
        const data = await fetchMilestoneQuestions(count);
        mockPool = data.pool;
        mockCount = Math.min(data.count, data.pool.length);
        mockSecondsLeft = data.seconds;
    }

    const MOCK_DIFFS = ["easy", "medium", "hard"];

    /** Simple adaptive ladder: correct -> harder, wrong -> easier. Prefers the
        least-used topic at the current difficulty; falls back gracefully.
        For a fixed practice-test form we bypass the ladder entirely and serve the
        pool in its given order (one at a time, reusing the timer/flag machinery). */
    function pickMockQuestion(): MockQuestion | null {
        if (!mockPool.length) return null;
        if (mockFormId) {
            return mockPool[mockItems.length] ?? null;
        }
        const wantDiff = MOCK_DIFFS[mockDiffIdx];
        const usage = new Map<string, number>();
        for (const it of mockItems) {
            usage.set(it.q.topic, (usage.get(it.q.topic) ?? 0) + 1);
        }
        const byPreference = [...mockPool].sort((a, b) => {
            const diffA = a.difficulty === wantDiff ? 0 : 1;
            const diffB = b.difficulty === wantDiff ? 0 : 1;
            if (diffA !== diffB) return diffA - diffB;
            return (usage.get(a.topic) ?? 0) - (usage.get(b.topic) ?? 0);
        });
        const picked = byPreference[0];
        mockPool = mockPool.filter((q) => q !== picked);
        return picked;
    }

    function beginMock(): void {
        mockItems = [];
        mockPos = 0;
        mockDiffIdx = 1;
        mockChangesLeft = MOCK_MAX_CHANGES;
        mockPhase = "run";
        const first = pickMockQuestion();
        if (first) {
            mockItems = [{ q: first, answer: null, flagged: false, ms: 0, firstShownAt: Date.now() }];
        }
        stopTimer();
        mockTimer = window.setInterval(() => {
            mockSecondsLeft -= 1;
            if (mockSecondsLeft <= 0) void finishMock();
        }, 1000);
    }

    $: mockCurrentItem = mockItems[mockPos] ?? null;
    $: mockAnswered = mockItems.filter((it) => it.answer !== null).length;

    /** Select/change an answer. First answer is free and sets the adaptive
        ladder; any later change (here or in review) costs one of 3 edits. */
    function selectMockAnswer(key: string): void {
        const it = mockItems[mockPos];
        if (!it) return;
        if (it.answer === null) {
            it.answer = key;
            it.ms = Date.now() - it.firstShownAt;
            const correct = key === it.q.correct;
            mockDiffIdx = correct ? Math.min(2, mockDiffIdx + 1) : Math.max(0, mockDiffIdx - 1);
        } else if (key !== it.answer) {
            if (mockChangesLeft <= 0) return;
            mockChangesLeft -= 1;
            it.answer = key;
        }
        mockItems = [...mockItems];
    }

    function toggleMockFlag(): void {
        const it = mockItems[mockPos];
        if (!it) return;
        it.flagged = !it.flagged;
        mockItems = [...mockItems];
    }

    /** Advance: pick the next adaptive question the first time we reach a new
        slot; otherwise move within already-seen questions; at the end -> review. */
    function advanceMock(): void {
        if (mockPos === mockItems.length - 1 && mockItems.length < mockCount) {
            const next = pickMockQuestion();
            if (!next) {
                mockPhase = "review";
                return;
            }
            mockItems = [
                ...mockItems,
                { q: next, answer: null, flagged: false, ms: 0, firstShownAt: Date.now() },
            ];
            mockPos += 1;
        } else if (mockPos < mockItems.length - 1) {
            mockPos += 1;
        } else {
            mockPhase = "review";
        }
    }

    function backMock(): void {
        if (mockPos > 0) mockPos -= 1;
    }

    function reviewJump(i: number): void {
        mockPos = i;
        mockPhase = "run";
    }

    async function finishMock(): Promise<void> {
        if (mockSubmitting || mockPhase === "report") return;
        mockSubmitting = true;
        stopTimer();
        const results: MockResult[] = mockItems.map((it) => ({
            topic: it.q.topic,
            difficulty: it.q.difficulty,
            correct: it.answer === it.q.correct,
            ms: it.ms,
            stem: it.q.stem,
            chosen: it.answer ?? "",
            correct_key: it.q.correct,
        }));
        if (mockKind === "quiz") {
            mockReport = await submitQuiz({
                kind: "topic",
                topic: mockQuizTopic,
                results,
            });
        } else if (mockKind === "milestone") {
            mockReport = await submitQuiz({ kind: "milestone", results });
        } else {
            mockReport = await submitMock(
                results,
                mockFormId ?? undefined,
                mockFormYear ?? undefined,
            );
        }
        mockMissResults = results.filter((r) => !r.correct);
        mockWhy = mockMissResults.map(() => null);
        mockPhase = "report";
        mockSubmitting = false;
    }

    $: mockMisses = mockMissResults;
    $: mockAllClassified = mockWhy.every((w) => w !== null);

    async function classifyMockMiss(idx: number, why: ErrorWhy): Promise<void> {
        const miss = mockMisses[idx];
        if (!miss || mockWhy[idx] !== null) return;
        mockWhy[idx] = why;
        mockWhy = [...mockWhy];
        await logError({
            stem: miss.stem,
            topic: miss.topic,
            chosen: miss.chosen,
            correct: miss.correct_key,
            why,
            ms: miss.ms,
            mock: true,
            options: mockMissOptions(miss),
        });
    }

    async function finishMockReport(): Promise<void> {
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
        pushIfAuthed();
        // quiz/milestone return to wherever they were launched (Study vs Today);
        // a plain mock/practice-test returns to Today.
        await go(mockReturnView);
    }

    /** Refresh the on-screen data from local state WITHOUT changing the current
     * view - used both after login and when auto-sync applies a remote change,
     * so a background sync never yanks you out of what you're doing. */
    async function applyRemoteState(): Promise<void> {
        const fresh = await refreshOverview();
        if (fresh) overview = fresh;
        reconcileAiFlag();
        if (overview.plan) {
            lessonTopics = (await fetchLessonsIndex()).topics;
            today = await fetchToday();
            calendar = await fetchCalendar();
        }
    }

    onMount(() => {
        reconcileAiFlag();
        const unsub = onUser(async (u) => {
            authUser = u;
            authReady = true;
            if (!u) {
                stopAutoSync();
                return;
            }
            // Load this account's data (or reset to a fresh start if brand-new),
            // then refresh the app so the right screen/plan shows on this device.
            try {
                await pullAccountState(u.uid);
            } catch (e) {
                console.error("GMATWiz account load failed", e);
            }
            // Then reconcile the WHOLE collection file (cards + revlog) via Cloud
            // Storage - AFTER the config pull, so config + collection both land.
            // Guarded internally; a Storage/network failure never breaks login.
            await pullCollectionOnLogin(u.uid);
            await applyRemoteState();
            view = "home";
            // Cross-device sync runs automatically: pull newer remote state on a
            // short interval; local changes still push on mutation.
            startAutoSync(u.uid, () => void applyRemoteState());
        });
        if (overview.plan) {
            fetchLessonsIndex().then((r) => (lessonTopics = r.topics));
            fetchToday().then((t) => (today = t));
            fetchCalendar().then((c) => (calendar = c));
        }
        // Push the whole collection up when the page is hidden or unloaded
        // (tab switch, app backgrounded on mobile, window close). Debounced so
        // rapid events coalesce; a no-op when signed out.
        const uploadOnLeave = (): void => {
            if (authUser) scheduleCollectionUpload(authUser.uid);
        };
        const onVisibility = (): void => {
            if (document.visibilityState === "hidden") uploadOnLeave();
        };
        document.addEventListener("visibilitychange", onVisibility);
        window.addEventListener("pagehide", uploadOnLeave);
        window.addEventListener("beforeunload", uploadOnLeave);
        return () => {
            unsub();
            stopAutoSync();
            document.removeEventListener("visibilitychange", onVisibility);
            window.removeEventListener("pagehide", uploadOnLeave);
            window.removeEventListener("beforeunload", uploadOnLeave);
        };
    });
</script>

<div class="gw">
    <div class="sky" aria-hidden="true">
        {#each skyOrbs as o}
            <span
                class="orb"
                class:orb-amethyst={!o.gold}
                style="left:{o.x}%;width:{o.size}px;height:{o.size}px;animation-duration:{o.dur}s;animation-delay:{o.delay}s"
            ></span>
        {/each}
        {#each skyGlyphs as g}
            <span
                class="glyph"
                style="left:{g.x}%;font-size:{g.size}px;animation-duration:{g.dur}s;animation-delay:{g.delay}s;color:{g.gold
                    ? 'var(--gold)'
                    : 'var(--indicator)'}"
            >{g.ch}</span>
        {/each}
    </div>
    {#if authEnabled && !authUser}
        {#if !authReady}
            <main class="col"><p class="lede">Loading…</p></main>
        {:else}
            <main class="col auth-screen">
                <div class="auth-brand">
                    <svg class="sigil sigil-lg" viewBox="0 0 48 48" aria-hidden="true">
                        <ellipse class="hat-brim" cx="24" cy="39" rx="18" ry="4.6" />
                        <path
                            class="hat-cone"
                            d="M24 6 C 22.4 6 21.4 7.3 21 9 L 14.6 38 L 33.4 38 L 27 9 C 26.6 7.3 25.6 6 24 6 Z"
                        />
                        <path class="hat-band" d="M15.6 33 L 32.4 33 L 33.2 37.6 L 14.8 37.6 Z" />
                        <path
                            class="hat-star"
                            d="M24 13 l1.3 3.2 3.4 .3 -2.6 2.3 .8 3.4 -2.9-1.8 -2.9 1.8 .8-3.4 -2.6-2.3 3.4-.3 Z"
                        />
                    </svg>
                    <span class="wordmark">
                        <span class="wm-gmat">GMAT</span><span class="wm-wiz">Wiz</span>
                    </span>
                </div>
                <p class="lede auth-lede">
                    Sign in to sync your plan, progress, and reviews across every device.
                </p>
                <section class="action-card auth-card">
                    <div class="auth-tabs">
                        <button
                            class:active={authMode === "signin"}
                            on:click={() => {
                                authMode = "signin";
                                authError = "";
                            }}>Sign in</button
                        >
                        <button
                            class:active={authMode === "signup"}
                            on:click={() => {
                                authMode = "signup";
                                authError = "";
                            }}>Create account</button
                        >
                    </div>
                    <label class="field">
                        <span class="field-label">Email</span>
                        <input type="email" autocomplete="email" bind:value={authEmail} />
                    </label>
                    <label class="field">
                        <span class="field-label">Password</span>
                        <input
                            type="password"
                            autocomplete={authMode === "signin" ? "current-password" : "new-password"}
                            bind:value={authPassword}
                            on:keydown={(e) => e.key === "Enter" && submitAuth()}
                        />
                    </label>
                    {#if authError}<p class="warn-text">{authError}</p>{/if}
                    <button
                        class="primary"
                        disabled={authBusy || !authEmail || !authPassword}
                        on:click={submitAuth}
                    >
                        {authBusy
                            ? "Please wait…"
                            : authMode === "signin"
                              ? "Sign in"
                              : "Create account"}
                    </button>
                </section>
            </main>
        {/if}
    {:else}
    <header class="topbar">
        <div class="brand">
            <svg class="sigil" viewBox="0 0 48 48" aria-hidden="true">
                <ellipse class="hat-brim" cx="24" cy="39" rx="18" ry="4.6" />
                <path
                    class="hat-cone"
                    d="M24 6 C 22.4 6 21.4 7.3 21 9 L 14.6 38 L 33.4 38 L 27 9 C 26.6 7.3 25.6 6 24 6 Z"
                />
                <path class="hat-band" d="M15.6 33 L 32.4 33 L 33.2 37.6 L 14.8 37.6 Z" />
                <path
                    class="hat-star"
                    d="M24 13 l1.3 3.2 3.4 .3 -2.6 2.3 .8 3.4 -2.9-1.8 -2.9 1.8 .8-3.4 -2.6-2.3 3.4-.3 Z"
                />
                <circle class="hat-spark" cx="34" cy="15" r="1.1" />
                <circle class="hat-spark" cx="12.5" cy="22" r="0.9" />
            </svg>
            <span class="wordmark">
                <span class="wm-gmat">GMAT</span><span class="wm-wiz">Wiz</span>
            </span>
        </div>
        <nav class="nav">
            <button class:active={view === "home"} on:click={() => go("home")}>Today</button>
            {#if !locked}
                <button
                    class:active={view === "study" || view === "lesson"}
                    on:click={() => go("study")}>Study</button
                >
                <button class:active={view === "drill"} on:click={() => go("drill")}>Drill</button>
                <button
                    class:active={view === "dashboard"}
                    on:click={() => go("dashboard")}>Progress</button
                >
                <button class:active={view === "errors"} on:click={() => go("errors")}>Error Log</button>
            {/if}
            <span class="nav-spacer" aria-hidden="true"></span>
            {#if authEnabled && authUser}
                <button class="nav-util" on:click={doSignOut} title={authUser.email ?? "Sign out"}>
                    Sign out
                </button>
            {/if}
        </nav>
    </header>

    <!-- Reusable practice card: rendered standalone (Drill view) AND inline
         (Today's review/practice blocks, Study -> Practice). Reads the shared
         practice state; `ctx` supplies a context-appropriate "back" control. -->
    {#snippet practiceCard(ctx: InlineCtx | null)}
        {#if ctx}
            <button class="ghost back-inline" on:click={ctx.onExit}>&larr; {ctx.exitLabel}</button>
        {/if}
        {#if sessionEnded}
            <section class="q-card summary-card">
                <p class="eyebrow">Session review</p>
                <h1 class="stem">
                    You answered {sessionLog.length} question{sessionLog.length === 1 ? "" : "s"}.
                </h1>
                <p class="summary-tally">
                    <span class="tally-ok">{sessionRight} right</span>
                    &middot; <span class="tally-no">{sessionWrong} wrong</span>
                    {#if sessionLog.length}&middot; {sessionPct}% accurate{/if}
                </p>
                {#if sessionLog.length}
                    <ul class="summary-list">
                        {#each sessionLog as a}
                            <li class="summary-row {a.isCorrect ? 'ok' : 'no'}">
                                <span class="sr-mark">{a.isCorrect ? "✓" : "✗"}</span>
                                <div class="sr-main">
                                    <span class="pill">{a.topic ? topicLabel(a.topic) : "Quant"}</span>
                                    <span class="sr-stem">{a.stem}</span>
                                </div>
                                <span class="sr-ans">
                                    {a.isCorrect ? a.correct : `${a.chosen} \u2192 ${a.correct}`}
                                </span>
                            </li>
                        {/each}
                    </ul>
                {:else}
                    <p class="explain">No questions answered this session.</p>
                {/if}
                <div class="summary-actions">
                    {#if practiceMode === "scheduler" || !ctx}
                        <button class="primary" on:click={startDrill}>Start a new session</button>
                    {/if}
                    {#if ctx}
                        <button class="ghost" on:click={ctx.onExit}>{ctx.exitLabel}</button>
                    {/if}
                </div>
            </section>
        {:else}
        <div class="session-meter">
            <span class="readout">{answered}</span> answered
            {#if answered > 0}
                &middot; <span class="readout">{sessionAccuracy}%</span> accurate
            {/if}
            {#if queueRemaining > 0}
                &middot;
                <span class="muted">{queueRemaining} {practiceMode === "topic" ? "left" : "in queue"}</span>
            {/if}
            {#if activeQuestion && !revealed}
                &middot;
                <span class="readout" class:overpace={practiceElapsed > TARGET_SECS}>
                    {fmtTime(practiceElapsed)}
                </span>
                <span class="muted">/ {fmtTime(TARGET_SECS)} pace</span>
            {/if}
        </div>
        {#if activeQuestion || answered > 0}
            <div class="session-controls">
                {#if aiOn && practiceMode === "scheduler" && activeQuestion}
                    <button class="ghost" disabled={aiGenerating} on:click={generateMore}>
                        {aiGenerating ? "Generating…" : "Generate with AI"}
                    </button>
                {/if}
                <button class="ghost end-session" on:click={endSession}>End session</button>
            </div>
        {/if}
        {#if aiNote && activeQuestion}
            <p class="ai-note" class:ok={aiNoteOk} class:muted={!aiNoteOk}>{aiNote}</p>
        {/if}

        {#if loading}
            <section class="q-card empty"><p>Loading&hellip;</p></section>
        {:else if activeQuestion}
            <section class="q-card">
                <div class="q-head">
                    <span class="eyebrow">
                        {activeQuestion.topic ? topicLabel(activeQuestion.topic) : "GMAT Quant"}
                    </span>
                    <span class="pill diff-{activeQuestion.difficulty}">{activeQuestion.difficulty}</span>
                </div>
                <h1 class="stem">{@html renderMath(activeQuestion.stem)}</h1>

                <ul class="opts">
                    {#each optionEntries as [key, value]}
                        <li>
                            <button
                                class="opt"
                                class:sel={!revealed && selected === key}
                                class:correct={revealed && activeQuestion && activeQuestion.correct === key}
                                class:wrong={revealed && selected === key && !(activeQuestion && activeQuestion.correct === key)}
                                class:muted={revealed && !(activeQuestion && activeQuestion.correct === key) && selected !== key}
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
                    <div class="verdict {selected === activeQuestion.correct ? 'ok' : 'no'}">
                        <strong>{selected === activeQuestion.correct ? "Correct" : "Not yet"}</strong>
                        <span class="muted">
                            Answer: {activeQuestion.correct} &middot; took {fmtTime(
                                Math.round(answerMs / 1000),
                            )}
                        </span>
                    </div>
                    {#if activeQuestion.explanation}
                        <p class="explain">{@html renderMath(activeQuestion.explanation)}</p>
                    {/if}
                    {#if pendingWhy}
                        <div class="why-box">
                            <p class="why-q">Why did you miss it? (goes in your error log)</p>
                            <div class="why-chips">
                                <button class="why-chip" on:click={() => classifyMiss("careless")}>
                                    Careless slip
                                </button>
                                <button class="why-chip" on:click={() => classifyMiss("concept_gap")}>
                                    Concept gap
                                </button>
                                <button class="why-chip" on:click={() => classifyMiss("timing")}>
                                    Ran out of time
                                </button>
                            </div>
                        </div>
                    {:else}
                        {#if selected === activeQuestion.correct && !guessLogged}
                            <button class="ghost guess-link" on:click={markGuess}>
                                Honestly? I guessed.
                            </button>
                        {:else if guessLogged}
                            <p class="muted">Logged as a guess &mdash; it will resurface.</p>
                        {/if}
                        <button class="primary" on:click={practiceNext}>
                            {practiceMode === "topic" && isLastTopicQ ? "Finish" : "Next question"}
                        </button>
                    {/if}
                {/if}
            </section>
        {:else}
            <section class="q-card empty">
                {#if practiceMode === "topic"}
                    {#if topicPool.length === 0}
                        <p class="eyebrow">Nothing to practice yet</p>
                        <h1 class="stem">No bank questions for {topicLabelText}.</h1>
                        <p class="explain">
                            The fixed bank has nothing tagged here right now.{#if aiOn} Generate a few
                            with AI, or try another topic.{:else} Turn on AI in Progress to generate
                            targeted questions, or try another topic.{/if}
                        </p>
                    {:else}
                        <p class="eyebrow">Session complete</p>
                        <h1 class="stem">Nice work on {topicLabelText}.</h1>
                        <p class="explain">
                            You worked through {answered} question{answered === 1 ? "" : "s"}{#if answered > 0}
                                &middot; {sessionAccuracy}% correct{/if}. Any misses are in your error
                            log for repair.
                        </p>
                    {/if}
                {:else}
                    <p class="eyebrow">Queue clear</p>
                    <h1 class="stem">You're caught up for now.</h1>
                    <p class="explain">
                        No scheduled cards are due.{#if aiOn} Generate fresh questions on your weakest
                        topic, or come back later for review.{:else} Come back later for scheduled
                        review, or import more GMAT Quant from the Tools menu.{/if}
                    </p>
                {/if}
                {#if aiOn}
                    <button class="primary gen-btn" disabled={aiGenerating} on:click={generateMore}>
                        {aiGenerating ? "Generating…" : "Generate more with AI"}
                    </button>
                {/if}
                {#if aiNote}<p class="ai-note" class:ok={aiNoteOk} class:muted={!aiNoteOk}>{aiNote}</p>{/if}
                {#if ctx}
                    <button class="ghost" on:click={ctx.onExit}>{ctx.exitLabel}</button>
                {/if}
            </section>
        {/if}
        {/if}
    {/snippet}

    <!-- Reusable lesson player: rendered standalone (lesson view) AND inline
         (Today's learn/repair blocks). `ctx` swaps the completion controls. -->
    {#snippet lessonPlayer(ctx: InlineCtx | null)}
        {#if lessonLoading}
            <section class="q-card empty"><p>Loading lesson&hellip;</p></section>
        {:else if lesson}
            {#if ctx}
                <button class="ghost back-inline" on:click={ctx.onExit}>&larr; {ctx.exitLabel}</button>
            {/if}
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
                    {#if lessonItem.think_aloud_steps?.length}
                        <p class="eyebrow">Think aloud</p>
                        <ol class="steps">
                            {#each lessonItem.think_aloud_steps as s}
                                <li>{@html renderMath(s)}</li>
                            {/each}
                        </ol>
                    {/if}
                    <div class="verdict ok">
                        <strong>Answer: {lessonItem.correct}</strong>
                        <span>{@html renderMath(lessonItem.options[lessonItem.correct])}</span>
                    </div>
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
                                    class="opt"
                                    class:sel={!lessonRevealed && lessonSelected === key}
                                    class:correct={lessonRevealed && lessonItem.correct === key}
                                    class:wrong={lessonRevealed &&
                                        lessonSelected === key &&
                                        lessonItem.correct !== key}
                                    class:muted={lessonRevealed &&
                                        lessonItem.correct !== key &&
                                        lessonSelected !== key}
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
                    {#if ctx}
                        <button class="primary" on:click={ctx.onExit}>{ctx.exitLabel}</button>
                    {:else}
                        <button class="primary" on:click={() => finishLesson("drill")}>
                            Practice this topic
                        </button>
                        <button class="ghost" on:click={() => finishLesson("study")}>
                            Back to Study
                        </button>
                    {/if}
                </section>
            {/if}
        {:else}
            <section class="q-card empty"><p>Lesson not found.</p></section>
        {/if}
    {/snippet}

    {#if view === "home"}
        <main class="col">
            {#if todayActive}
                <!-- A Today task runs INLINE here; the "Today" nav stays active. -->
                {#if todayActive.kind === "learn" || todayActive.kind === "repair"}
                    {@render lessonPlayer({ onExit: backToToday, exitLabel: "Back to today" })}
                {:else}
                    {@render practiceCard({ onExit: backToToday, exitLabel: "Back to today" })}
                {/if}
            {:else}
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
                        </div>
                        <h2 class="action-title">Take your diagnostic</h2>
                        <p class="muted">
                            A 21-question timed diagnostic builds your personalized plan and targets
                            your weak topics.
                        </p>
                        <button class="primary" on:click={startDiagnostic}>Start diagnostic</button>
                    {:else if today && today.blocks.length > 0}
                        {#if allTodayDone}
                            <div class="action-head">
                                <span class="eyebrow">Today's session</span>
                                <span class="pill cal-ok">complete</span>
                            </div>
                            <h2 class="action-title">You're done for today.</h2>
                            {#if nextLessonItem}
                                <p class="muted">
                                    Every task on today's plan is finished. Rest &mdash; or pull
                                    tomorrow's lesson forward and get ahead. Your plan recalibrates
                                    as you go.
                                </p>
                                <button class="primary" on:click={startTomorrow}>
                                    Start tomorrow's plan: {topicLabel(nextLessonItem.topic ?? "")}
                                </button>
                                <button class="ghost" on:click={jumpAhead}>Extra practice instead</button>
                            {:else}
                                <p class="muted">
                                    Every task on today's plan is finished, and there's nothing new
                                    left to learn. Rest &mdash; or keep sharp with extra spaced practice.
                                </p>
                                <button class="primary" on:click={jumpAhead}>Extra practice</button>
                            {/if}
                            <button class="ghost" on:click={() => go("plan")}>View full plan</button>
                        {:else}
                            <div class="action-head">
                                <span class="eyebrow">Today's session</span>
                                <span class="pill">~{todayEst} min today</span>
                            </div>
                            <h2 class="action-title">Do this, in order.</h2>
                            <ol class="today-list">
                                {#each today.blocks as b, i}
                                    {@const done = todayDone.has(blockKey(b))}
                                    <li class="today-block kind-{b.kind}" class:done>
                                        <span class="tb-index">{done ? "\u2713" : i + 1}</span>
                                        <div class="tb-body">
                                            <span class="tb-title">
                                                {b.kind === "learn" && b.topic
                                                    ? `Learn: ${topicLabel(b.topic)}`
                                                    : b.kind === "repair" && b.topic
                                                      ? `Repair: ${topicLabel(b.topic)}`
                                                      : b.kind === "quiz" && b.topic
                                                        ? `Quiz: ${topicLabel(b.topic)}`
                                                        : b.title}
                                            </span>
                                            <span class="tb-detail">{b.detail}</span>
                                        </div>
                                        <span class="tb-min">{b.est_minutes}m</span>
                                        <button
                                            class="tb-go"
                                            disabled={done}
                                            on:click={() => startBlock(b)}
                                        >
                                            {done
                                                ? "Done"
                                                : b.kind === "learn" || b.kind === "repair"
                                                  ? "Learn"
                                                  : b.kind === "mock" ||
                                                      b.kind === "milestone" ||
                                                      b.kind === "quiz"
                                                    ? "Begin"
                                                    : "Start"}
                                        </button>
                                    </li>
                                {/each}
                            </ol>
                            <button
                                class="primary"
                                disabled={!firstPendingBlock}
                                on:click={() => firstPendingBlock && startBlock(firstPendingBlock)}
                            >
                                {todayDone.size > 0 ? "Continue today" : "Start today"}
                            </button>
                            <button class="ghost" on:click={() => go("plan")}>View full plan</button>
                        {/if}
                    {:else}
                        <div class="action-head">
                            <span class="eyebrow">Today's session</span>
                            <span class="pill">{overview.deck}</span>
                        </div>
                        <h2 class="action-title">You're caught up.</h2>
                        <p class="muted">
                            No reviews are due and there's nothing new to learn today. Rest, or get
                            ahead with extra practice.
                        </p>
                        <button class="primary" on:click={() => go("drill")}>Practice anyway</button>
                        <button class="ghost" on:click={() => go("plan")}>View full plan</button>
                    {/if}
                </section>

                {#if today && today.pacing && today.pacing.status !== "no_pacing"}
                    {@const p = today.pacing}
                    <section class="pace pace-{p.status}">
                        <div class="pace-top">
                            <span class="pace-status">{paceLabel(p)}</span>
                            {#if p.days_to_exam !== null}
                                <span class="pace-days">{p.days_to_exam} days to exam</span>
                            {/if}
                        </div>
                        <div class="pace-bar" aria-hidden="true">
                            <span
                                class="pace-fill"
                                style="width:{p.topics_total
                                    ? Math.round((100 * p.topics_learned) / p.topics_total)
                                    : 0}%"
                            ></span>
                        </div>
                        <p class="pace-detail">
                            {p.topics_learned}/{p.topics_total} topics learned{#if p.behind_by > 0}
                                &middot; {p.behind_by} behind pace &mdash; do a lesson today{:else if p.status === "learning_complete"}
                                &middot; now consolidate with review + practice{:else}
                                &middot; keep it up{/if}
                        </p>
                    </section>
                {/if}

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
            {/if}
        </main>
    {:else if view === "drill"}
        <main class="col">
            <!-- The infinite, scheduler-backed drill: the same card the Today tab
                 and Study -> Practice render, here with no "back" (it never ends). -->
            {@render practiceCard(null)}
        </main>
    {:else if view === "dashboard"}
        <main class="col-wide">
            <p class="eyebrow">Progress &mdash; three honest questions</p>
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
                        {#if overview.performance.timing && overview.performance.timing.n > 0}
                            {@const t = overview.performance.timing}
                            <p class="muted">
                                Pace: avg {fmtTime(Math.round(t.avg_ms / 1000))}/question (target
                                {fmtTime(Math.round(t.target_ms / 1000))}) &middot;
                                <span class="warn-text">{t.rushed_wrong} fast-but-wrong</span>
                                (careless) &middot;
                                <span class="warn-text">{t.slow_correct} slow-but-correct</span>
                                (fragile &mdash; right, but not at exam pace)
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
                        {@const cal = overview.readiness.calibration}
                        {#if cal}
                            <div class="needle-wrap">
                                <span class="readout-lg">Q{cal.point}</span>
                                <span class="pill cal-ok">calibrated</span>
                                <span class="band">
                                    range Q{cal.low}&ndash;Q{cal.high} &middot;
                                    {overview.readiness.confidence} confidence
                                </span>
                            </div>
                            <p class="muted">
                                Raw model said Q{overview.readiness.point}; shifted
                                {cal.bias >= 0 ? "+" : ""}{cal.bias} from your {cal.n} official
                                score{cal.n > 1 ? "s" : ""} (avg error {cal.residual}).
                            </p>
                        {:else}
                            <div class="needle-wrap">
                                <span class="readout-lg">Q{overview.readiness.point}</span>
                                <span class="band">
                                    range Q{overview.readiness.low}&ndash;Q{overview.readiness.high} &middot;
                                    {overview.readiness.confidence} confidence
                                </span>
                            </div>
                        {/if}
                        <p class="muted">{overview.readiness.scale}. {overview.readiness.method}</p>
                        {#if overview.readiness.mocks?.length}
                            {@const lastMock =
                                overview.readiness.mocks[overview.readiness.mocks.length - 1]}
                            <p class="muted">
                                Mocks: {overview.readiness.mocks
                                    .slice(-3)
                                    .map((m) => `Q${m.q}`)
                                    .join(" → ")}
                                (last: {Math.round(lastMock.accuracy * 100)}% of {lastMock.n})
                                {#if overview.readiness.mock_gap != null && Math.abs(overview.readiness.mock_gap) > 4}
                                    &middot; <span class="warn-text">
                                        projection is {Math.abs(overview.readiness.mock_gap)} points
                                        {overview.readiness.mock_gap > 0 ? "above" : "below"} your last
                                        mock &mdash; trust the range, not the point
                                    </span>
                                {/if}
                            </p>
                        {:else}
                            <p class="muted">
                                No timed mocks yet &mdash; a mock section is the only way to check
                                this projection against exam conditions.
                            </p>
                            <button class="ghost" on:click={() => startMock()}>Take a timed mock</button>
                        {/if}
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
                            {#if overview.readiness.mocks?.length}
                                <p class="muted">
                                    Mock history: {overview.readiness.mocks
                                        .slice(-3)
                                        .map((m) => `Q${m.q}`)
                                        .join(" → ")}
                                </p>
                            {/if}
                        </div>
                    {/if}
                </section>
            </div>

            <!-- Forward study calendar: the tentative run-up to the exam, derived
                 live so it recalibrates as topics are mastered / pulled forward. -->
            <section class="calendar">
                <div class="cal-head">
                    <span class="eyebrow">The run-up &mdash; your plan to exam day</span>
                    <span class="pill">tentative &middot; recalibrates</span>
                </div>
                {#if calendar && calendar.days.length}
                    <p class="cal-lede">
                        {calendar.study_days} study day{calendar.study_days === 1 ? "" : "s"}
                        to your exam{#if calendar.days_to_exam !== null}
                            ({calendar.days_to_exam} days away){/if}.
                        {#if calendar.lessons_finish_date}
                            New lessons wrap up by <strong>{shortDate(calendar.lessons_finish_date)}</strong>
                            &mdash; then the last stretch is review and timed tests.
                        {:else}
                            Lessons are done &mdash; the run-up is consolidation and timed tests.
                        {/if}
                    </p>
                    <div class="cal-legend">
                        <span class="cal-leg phase-learn">Learn</span>
                        <span class="cal-leg phase-review">Review</span>
                        <span class="cal-leg phase-final">Final 10 &middot; tests only</span>
                    </div>
                    <div class="cal-weeks">
                        {#each calendarWeeks as week, wi}
                            <div class="cal-week">
                                <span class="cal-week-label">Wk {wi + 1}</span>
                                <div class="cal-row">
                                    {#each week as d (d.day_offset)}
                                        <div
                                            class="cal-day phase-{d.phase}"
                                            class:today={d.is_today}
                                            class:exam={d.is_exam}
                                            class:rest={!d.is_study_day && !d.is_exam}
                                        >
                                            <div class="cal-day-top">
                                                <span class="cal-dow">{d.weekday}</span>
                                                <span class="cal-date">{shortDate(d.date)}</span>
                                            </div>
                                            {#if d.is_today}
                                                <span class="cal-flag">Today</span>
                                            {/if}
                                            {#if d.is_exam}
                                                <div class="cal-exam">
                                                    <span class="cal-exam-g">&#9733;</span>
                                                    <span>Exam day</span>
                                                </div>
                                            {:else if d.is_study_day}
                                                <ul class="cal-items">
                                                    {#each d.items as it}
                                                        <li
                                                            class="cal-chip chip-{it.kind}"
                                                            title="{it.title} &middot; ~{it.est_minutes} min"
                                                        >
                                                            <span class="cal-chip-g">{CAL_ITEM_GLYPH[it.kind]}</span>
                                                            <span class="cal-chip-t">{calChipLabel(it)}</span>
                                                        </li>
                                                    {/each}
                                                </ul>
                                                {#if d.est_minutes > 0}
                                                    <span class="cal-min">~{d.est_minutes}m</span>
                                                {/if}
                                            {:else}
                                                <div class="cal-rest">Rest</div>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            </div>
                        {/each}
                    </div>
                {:else}
                    <p class="muted">
                        Your day-by-day plan appears here once your exam date is set. It's built from
                        where you are now and updates every time you master a topic or get ahead.
                    </p>
                {/if}
            </section>

            <section class="action-card tests-cta">
                <div class="action-head">
                    <span class="eyebrow">Practice tests</span>
                    <span class="pill">full-length</span>
                </div>
                <p class="muted">
                    Sit a complete timed section under exam conditions &mdash; the truest check on
                    your Readiness projection, form by form.
                </p>
                <button class="primary" on:click={() => go("tests")}>Browse practice tests</button>
            </section>

            <section class="coverage">
                <div class="coverage-head">
                    <span class="eyebrow">Topic coverage</span>
                    <span class="readout">{overview.topics_covered}/{overview.topics_total}</span>
                </div>
                <div class="bar"><div class="bar-fill" style="width:{coveragePct}%"></div></div>
            </section>

            <div class="activity">
                <p class="eyebrow">Activity</p>
                {#if stats && stats.has_data}
                    <div class="mini-grid">
                        <div class="mini">
                            <span class="mini-n">{stats.reviews_today}</span>
                            <span class="mini-l">reviews today</span>
                        </div>
                        <div class="mini">
                            <span class="mini-n">{stats.streak}</span>
                            <span class="mini-l">day streak</span>
                        </div>
                        <div class="mini">
                            <span class="mini-n">{stats.time_today_min}m</span>
                            <span class="mini-l">time today</span>
                        </div>
                    </div>

                    <section class="progress-card">
                        <div class="coverage-head">
                            <span class="eyebrow">Last 7 days</span>
                            <span class="muted">{stats.reviews_total} reviews all-time</span>
                        </div>
                        <div class="spark">
                            {#each stats.spark as c}
                                {@const peak = Math.max(1, ...stats.spark)}
                                <div class="spark-col" title="{c} reviews">
                                    <div class="spark-bar" style="height:{Math.round((100 * c) / peak)}%"></div>
                                </div>
                            {/each}
                        </div>
                    </section>

                    <section class="progress-card">
                        <div class="coverage-head">
                            <span class="eyebrow">Review pipeline</span>
                            <span class="muted">{stats.pipeline.total} cards</span>
                        </div>
                        <div class="pipe">
                            {#each [["new", stats.pipeline.new], ["learning", stats.pipeline.learning], ["young", stats.pipeline.young], ["mature", stats.pipeline.mature]] as [label, val]}
                                <div class="pipe-row">
                                    <span class="pipe-label">{label}</span>
                                    <div class="pipe-track">
                                        <div
                                            class="pipe-fill pipe-{label}"
                                            style="width:{stats.pipeline.total
                                                ? Math.round((100 * Number(val)) / stats.pipeline.total)
                                                : 0}%"
                                        ></div>
                                    </div>
                                    <span class="pipe-n">{val}</span>
                                </div>
                            {/each}
                        </div>
                    </section>

                    <section class="progress-card">
                        <div class="coverage-head">
                            <span class="eyebrow">Due next 7 days</span>
                            <span class="muted">{stats.due_today} due today</span>
                        </div>
                        <div class="spark">
                            {#each stats.forecast as c, i}
                                {@const peak = Math.max(1, ...stats.forecast)}
                                <div class="spark-col" title="{c} due">
                                    <div class="spark-bar cast" style="height:{Math.round((100 * c) / peak)}%"></div>
                                    <span class="spark-x">{i === 0 ? "today" : `+${i}`}</span>
                                </div>
                            {/each}
                        </div>
                    </section>
                {:else}
                    <section class="q-card empty">
                        <p>No review history yet. Do some Practice and your activity shows up here.</p>
                    </section>
                {/if}
                <div class="progress-actions">
                    <button class="ghost" on:click={() => openFullStats()}>Open full Anki stats</button>
                    <button class="ghost" on:click={() => openDecks()}>Free study (all decks)</button>
                </div>
            </div>

            <section class="official">
                <div class="coverage-head">
                    <span class="eyebrow">Practice-test scores</span>
                    <span class="muted">calibrates your Readiness projection</span>
                </div>
                <p class="muted">
                    Took a real GMAT practice test (e.g. an official mba.com exam)? Log the Quant
                    section score and we'll correct the projection to match your real results.
                </p>
                <div class="os-form">
                    <label>
                        <span class="os-label">Quant (60&ndash;90)</span>
                        <input class="os-input" type="number" min="60" max="90" bind:value={osQuant} />
                    </label>
                    <label>
                        <span class="os-label">Total (opt.)</span>
                        <input class="os-input" type="number" min="205" max="805" bind:value={osTotal} />
                    </label>
                    <label>
                        <span class="os-label">Date (opt.)</span>
                        <input class="os-input" type="date" bind:value={osDate} />
                    </label>
                    <button class="primary os-save" disabled={osSaving} on:click={submitOfficialScore}>
                        {osSaving ? "Saving…" : "Log score"}
                    </button>
                </div>
                {#if osError}<p class="warn-text">{osError}</p>{/if}
                {#if officialScores.length}
                    <ul class="os-list">
                        {#each officialScores as s}
                            <li class="os-item">
                                <span class="readout">Q{s.quant}</span>
                                {#if s.total}<span class="muted">total {s.total}</span>{/if}
                                {#if s.date}<span class="muted">{s.date}</span>{/if}
                                {#if s.projected_at_entry != null}
                                    <span class="muted">
                                        (app said Q{s.projected_at_entry} &middot;
                                        {s.quant - s.projected_at_entry >= 0 ? "+" : ""}{s.quant -
                                            s.projected_at_entry})
                                    </span>
                                {:else}
                                    <span class="muted">(logged before a projection existed)</span>
                                {/if}
                            </li>
                        {/each}
                    </ul>
                {/if}
            </section>

            <section class="action-card ai-card">
                <div class="action-head">
                    <span class="eyebrow">AI features</span>
                    <button
                        class="ai-switch"
                        class:on={aiOn}
                        role="switch"
                        aria-checked={aiOn}
                        aria-label="AI question generation and coaching"
                        disabled={aiBusy}
                        on:click={toggleAi}
                    >
                        <span class="ai-track"><span class="ai-knob"></span></span>
                        <span class="ai-state">{aiOn ? "On" : "Off"}</span>
                    </button>
                </div>
                <p class="ai-title">AI question generation &amp; coaching</p>
                <p class="muted">
                    When on, Drill and Study can generate fresh questions on your weakest topics,
                    and the Error Log can coach each miss. Off by default &mdash; it needs the
                    Firebase AI setup (a Blaze project with the Gemini API enabled). Reviews,
                    scores, and the fixed question bank work the same either way.
                </p>
                {#if aiOn}
                    <p class="ai-hint">
                        AI is on. Every generated question is quality-checked before it's added.
                    </p>
                {/if}
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
                    <span class="field-label">Target GMAT score</span>
                    <input type="number" min="205" max="805" step="5" bind:value={targetScore} />
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
                    Target {overview.plan.target_score} &middot; {overview.plan.days_per_week} days/week{#if today} &middot; ~{today.daily_minutes} min today{/if}.
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
                    <button class="primary" on:click={() => go("drill")}>
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
    {:else if view === "study"}
        <main class="col">
            {#if studyActive}
                <!-- Topic-scoped practice runs INLINE here; nav stays on "Study". -->
                {@render practiceCard({ onExit: backToStudy, exitLabel: "Back to study" })}
            {:else}
                <p class="eyebrow">Study</p>
                <h1 class="display">Teach first, then apply.</h1>
                <p class="lede">
                    Learn a topic with a worked example and guided practice, then apply it with
                    targeted questions. Weakest topics come first.
                </p>
                {#if lessonTopics.length === 0}
                    <section class="q-card empty">
                        <p>
                            Take your diagnostic first (Today tab) to prioritize topics, or import
                            GMAT Quant from the Tools menu.
                        </p>
                    </section>
                {:else}
                    <section class="action-card">
                        <div class="action-head">
                            <span class="eyebrow">Quant</span>
                            <span class="pill">{quantTopics.length} topics</span>
                        </div>
                        <ul class="study-list">
                            {#each quantTopics as t}
                                <li class="study-row" class:mastered={t.mastered}>
                                    <div class="sr-body">
                                        <span class="sr-name">
                                            {t.title}
                                            {#if t.mastered}
                                                <span class="pill mastered-pill">&check; mastered</span>
                                            {:else if t.learned}
                                                <span class="pill learned-pill">learned</span>
                                            {/if}
                                        </span>
                                        <span class="sr-meta">
                                            <span class="focus-bar">
                                                <span
                                                    class="focus-fill"
                                                    style="width:{Math.round((t.mastery ?? 0) * 100)}%"
                                                ></span>
                                            </span>
                                            {#if t.status}
                                                <span class="focus-status s-{t.status}">{t.status}</span>
                                            {/if}
                                        </span>
                                    </div>
                                    <div class="sr-actions">
                                        <button class="tb-go" on:click={() => openLesson(t.topic_id)}>
                                            {t.learned ? "Review" : "Learn"}
                                        </button>
                                        <button
                                            class="tb-go"
                                            on:click={() => startTopicPractice(t.topic_id, t.title)}
                                        >
                                            Practice
                                        </button>
                                        <button
                                            class="tb-go"
                                            on:click={() => startQuiz(t.topic_id, t.title, "study")}
                                        >
                                            Quiz
                                        </button>
                                    </div>
                                </li>
                            {/each}
                        </ul>
                    </section>
                    <p class="muted">
                        Verbal and Data Insights arrive later; Quant is the focus for now.
                    </p>
                {/if}
            {/if}
        </main>
    {:else if view === "lesson"}
        <main class="col">
            {@render lessonPlayer(null)}
        </main>
    {:else if view === "mock"}
        <main class="col">
            {#if mockPhase === "intro"}
                {#if mockKind === "quiz"}
                    <p class="eyebrow">Topic quiz &mdash; mastery check</p>
                    <h1 class="display">Prove you've got {mockQuizLabel}.</h1>
                    <p class="lede">
                        A short, timed check on one topic. Pass it twice on two different days
                        (85%+) and the topic counts as mastered. Miss and it stays in your plan for
                        repair &mdash; no penalty for trying.
                    </p>
                {:else if mockKind === "milestone"}
                    <p class="eyebrow">Milestone test &mdash; checkpoint</p>
                    <h1 class="display">A checkpoint across what you've learned.</h1>
                    <p class="lede">
                        A timed, mixed set drawn from your learned topics &mdash; a periodic read on
                        whether it's holding together. It feeds Readiness like a mock does.
                    </p>
                {:else}
                    <p class="eyebrow">
                        {#if mockFormId}
                            Practice test{#if mockLabel} &middot; {mockLabel}{/if}
                        {:else}
                            Mock section &mdash; exam conditions
                        {/if}
                    </p>
                    <h1 class="display">45 minutes. 21 questions. No feedback.</h1>
                    <p class="lede">
                        This simulates the GMAT Focus Quant section: timed, adaptive (harder when
                        you're right, easier when you're wrong), and sealed &mdash; no answers until
                        the end. It's also how we check the Readiness projection against reality.
                    </p>
                {/if}
                <section class="action-card">
                    <div class="action-head">
                        <span class="eyebrow">Ready?</span>
                        <span class="pill">
                            {Math.min(mockCount, mockPool.length)} questions &middot;
                            {fmtTime(mockSecondsLeft)}
                        </span>
                    </div>
                    <p class="muted">
                        Aim for ~2:08 per question. Flag anything to revisit, then review and change
                        up to 3 answers before you submit &mdash; just like the real section.
                        Guessing beats leaving blanks, but you'll classify every miss afterwards.
                    </p>
                    <p class="muted">Quant only for now (Verbal + Data Insights come later).</p>
                    <button
                        class="primary"
                        disabled={mockPool.length === 0}
                        on:click={beginMock}
                    >
                        Start the clock
                    </button>
                    <button class="ghost" on:click={() => go(mockReturnView)}>Not now</button>
                </section>
            {:else if mockPhase === "run"}
                <div class="session-meter">
                    <span class="readout" class:overpace={mockSecondsLeft < 300}>
                        {fmtTime(mockSecondsLeft)}
                    </span>
                    left &middot; question
                    <span class="readout">{mockPos + 1}</span>
                    of {mockCount}
                    &middot; <span class="muted">{mockAnswered} answered</span>
                    {#if mockChangesLeft < 3}
                        &middot; <span class="muted">{mockChangesLeft} edits left</span>
                    {/if}
                </div>
                {#if mockCurrentItem}
                    <section class="q-card">
                        <div class="q-head">
                            <span class="eyebrow">GMAT Quant &middot; timed</span>
                            <div class="q-head-right">
                                <button
                                    class="flag-btn"
                                    class:on={mockCurrentItem.flagged}
                                    on:click={toggleMockFlag}
                                >
                                    {mockCurrentItem.flagged ? "\u2691 Flagged" : "\u2690 Flag"}
                                </button>
                                <span class="pill diff-{mockCurrentItem.q.difficulty}">
                                    {mockCurrentItem.q.difficulty}
                                </span>
                            </div>
                        </div>
                        <h1 class="stem">{@html renderMath(mockCurrentItem.q.stem)}</h1>
                        <ul class="opts">
                            {#each Object.entries(mockCurrentItem.q.options) as [key, value]}
                                <li>
                                    <button
                                        class="opt {mockCurrentItem.answer === key ? 'sel' : ''}"
                                        on:click={() => selectMockAnswer(key)}
                                    >
                                        <span class="opt-key">{key}</span>
                                        <span>{@html renderMath(value)}</span>
                                    </button>
                                </li>
                            {/each}
                        </ul>
                        <div class="mock-nav">
                            <button class="ghost" disabled={mockPos === 0} on:click={backMock}>
                                Back
                            </button>
                            <button class="primary" on:click={advanceMock}>
                                {mockPos === mockCount - 1 ? "Review section" : "Next"}
                            </button>
                        </div>
                        <p class="seal">Sealed until you submit &mdash; exam conditions.</p>
                    </section>
                {/if}
            {:else if mockPhase === "review"}
                <div class="session-meter">
                    <span class="readout" class:overpace={mockSecondsLeft < 300}>
                        {fmtTime(mockSecondsLeft)}
                    </span>
                    left &middot; <span class="readout">{mockAnswered}</span>/{mockCount} answered
                    &middot; <span class="muted">{mockChangesLeft} edits left</span>
                </div>
                <section class="q-card">
                    <div class="q-head">
                        <span class="eyebrow">Review before you submit</span>
                    </div>
                    <p class="muted">
                        Tap any question to revisit it. You can change up to 3 answers. Unanswered and
                        flagged questions are marked.
                    </p>
                    <ol class="review-grid">
                        {#each mockItems as it, i}
                            <li>
                                <button
                                    class="review-cell {it.answer === null ? 'unanswered' : 'answered'}"
                                    class:flagged={it.flagged}
                                    on:click={() => reviewJump(i)}
                                >
                                    <span class="rc-n">{i + 1}</span>
                                    <span class="rc-state">
                                        {it.answer ?? "\u2014"}{it.flagged ? " \u2691" : ""}
                                    </span>
                                </button>
                            </li>
                        {/each}
                    </ol>
                    <button class="primary" on:click={finishMock} disabled={mockSubmitting}>
                        {mockSubmitting ? "Scoring…" : "Submit section"}
                    </button>
                    {#if mockAnswered < mockCount}
                        <p class="warn-text">
                            {mockCount - mockAnswered} unanswered will be scored as wrong.
                        </p>
                    {/if}
                </section>
            {:else if mockReport}
                <p class="eyebrow">
                    {#if mockKind === "quiz"}
                        Topic quiz report{#if mockQuizLabel} &middot; {mockQuizLabel}{/if}
                    {:else if mockKind === "milestone"}
                        Milestone report
                    {:else}
                        Mock report
                    {/if}
                </p>
                <h1 class="display">
                    {#if mockKind === "quiz"}
                        {#if mockReport.mastered}Mastered{:else}Not yet{/if}
                    {:else if mockReport.q != null}Q{mockReport.q}{:else}Done.{/if}
                    <span class="muted-display">
                        &middot; {Math.round(mockReport.accuracy * 100)}% of {mockReport.n}
                    </span>
                </h1>
                {#if mockKind === "quiz"}
                    <p class="lede">
                        {#if mockReport.mastered}
                            You've cleared the gate for {mockQuizLabel} &mdash; two passes on two
                            days. It now counts as mastered in your plan.
                        {:else if mockReport.accuracy >= 0.85}
                            A pass. One more on a different day (85%+) and {mockQuizLabel} is
                            mastered &mdash; we'll bring it back after a short gap.
                        {:else}
                            Not there yet. {mockQuizLabel} goes back into repair &mdash; relearn it,
                            then re-quiz. No penalty for the attempt.
                        {/if}
                    </p>
                {:else}
                    <p class="lede">
                        Estimated from this section alone, on the same transparent scale as
                        Readiness. One {mockKind === "milestone" ? "checkpoint" : "mock"} is a data
                        point, not a verdict.
                    </p>
                {/if}
                <section class="action-card">
                    <div class="action-head">
                        <span class="eyebrow">Pace</span>
                        <span class="pill">
                            avg {fmtTime(Math.round(mockReport.timing.avg_ms / 1000))}/q
                        </span>
                    </div>
                    <p class="muted">
                        {mockReport.timing.rushed_wrong} fast-but-wrong (careless) &middot;
                        {mockReport.timing.slow_correct} slow-but-correct (fragile) &middot; target
                        {fmtTime(Math.round(mockReport.timing.target_ms / 1000))}/question
                    </p>
                    {#if mockReport.per_topic.length}
                        <p class="muted">
                            Weakest topics this section: {mockReport.per_topic
                                .slice(0, 3)
                                .map((t) => `${topicLabel(t.topic)} (${t.correct}/${t.n})`)
                                .join(", ")}
                        </p>
                    {/if}
                </section>

                {#if mockMisses.length > 0}
                    <section class="action-card">
                        <div class="action-head">
                            <span class="eyebrow">Error log &mdash; required</span>
                            <span class="pill">
                                {mockWhy.filter((w) => w !== null).length}/{mockMisses.length} classified
                            </span>
                        </div>
                        <p class="muted">Classify every miss before you finish. Why did it happen?</p>
                        <ul class="err-list">
                            {#each mockMisses as m, i}
                                <li class="err">
                                    <div class="err-top">
                                        <span class="pill">{topicLabel(m.topic)}</span>
                                        <span class="muted">
                                            chose {m.chosen} &middot; correct {m.correct_key} &middot;
                                            {fmtTime(Math.round(m.ms / 1000))}
                                        </span>
                                    </div>
                                    <p class="err-stem">{@html renderMath(m.stem)}</p>
                                    {#if mockWhy[i] === null}
                                        <div class="why-chips">
                                            <button class="why-chip" on:click={() => classifyMockMiss(i, "careless")}>
                                                Careless slip
                                            </button>
                                            <button class="why-chip" on:click={() => classifyMockMiss(i, "concept_gap")}>
                                                Concept gap
                                            </button>
                                            <button class="why-chip" on:click={() => classifyMockMiss(i, "timing")}>
                                                Ran out of time
                                            </button>
                                        </div>
                                    {:else}
                                        <span class="pill why-{mockWhy[i]}">{(mockWhy[i] || "").replace("_", " ")}</span>
                                    {/if}
                                </li>
                            {/each}
                        </ul>
                    </section>
                {/if}
                <button class="primary" disabled={!mockAllClassified} on:click={finishMockReport}>
                    {mockAllClassified ? "Done - back to Today" : "Classify every miss first"}
                </button>
            {/if}
        </main>
    {:else if view === "tests"}
        <main class="col">
            <p class="eyebrow">Practice tests &mdash; full-length, timed</p>
            <h1 class="display">Sit a real one.</h1>
            <p class="lede">
                Complete 21-question sections under exam conditions. Each form runs on the same
                timed engine as a mock and calibrates your Readiness against reality.
            </p>
            {#if !tests || testYears.length === 0}
                <section class="q-card empty">
                    <p>No practice tests available yet. New forms show up here as they're added.</p>
                </section>
            {:else}
                {#each testYears as year}
                    <section class="action-card">
                        <div class="action-head">
                            <span class="eyebrow">{year}</span>
                            <span class="pill">{tests.years[year].length} forms</span>
                        </div>
                        <ul class="test-list">
                            {#each tests.years[year] as f}
                                <li class="test-row" class:taken={f.taken}>
                                    <div class="test-meta">
                                        <span class="test-label">{f.label}</span>
                                        <span class="muted">
                                            {f.count} questions &middot; timed 45:00
                                        </span>
                                    </div>
                                    {#if f.taken}
                                        <div class="test-score">
                                            {#if f.q != null}
                                                <span class="readout">Q{f.q}</span>
                                            {/if}
                                            {#if f.accuracy != null}
                                                <span class="muted">
                                                    {Math.round(f.accuracy * 100)}%
                                                </span>
                                            {/if}
                                            <button
                                                class="tb-go"
                                                on:click={() => startMock(f.id, f.year)}
                                            >
                                                Retake
                                            </button>
                                        </div>
                                    {:else}
                                        <button
                                            class="primary test-start"
                                            on:click={() => startMock(f.id, f.year)}
                                        >
                                            Start
                                        </button>
                                    {/if}
                                </li>
                            {/each}
                        </ul>
                    </section>
                {/each}
            {/if}
        </main>
    {:else}
        <main class="col">
            <p class="eyebrow">Error log &mdash; required review</p>
            <div class="err-header">
                <h1 class="display">Your mistakes, made useful.</h1>
                <button
                    class="info-btn"
                    aria-label="How error types work"
                    aria-expanded={errInfoOpen}
                    on:click={() => (errInfoOpen = !errInfoOpen)}
                >
                    i
                </button>
            </div>
            <p class="lede">Understanding the pattern behind a miss is how you stop repeating it.</p>

            {#if errInfoOpen}
                <section class="err-explainer">
                    <p class="eyebrow">How each label steers your plan</p>
                    <p class="ex-base">
                        <strong>Every wrong answer</strong>, before you pick a reason: the
                        scheduler logs an <em>Again</em> so the card resurfaces soon, and that
                        topic's mastery takes one step down (a small EMA nudge).
                    </p>
                    <ul class="ex-list">
                        <li>
                            <span class="pill why-careless">silly mistake</span>
                            <span
                                >Logged only &mdash; no extra penalty. Trust the automatic
                                resurfacing to catch it.</span
                            >
                        </li>
                        <li>
                            <span class="pill why-concept_gap">conceptual</span>
                            <span
                                >An <strong>extra</strong> mastery penalty, your lesson for that
                                topic is re-queued, and a high-priority
                                <strong>Repair</strong> block is added to Today.</span
                            >
                        </li>
                        <li>
                            <span class="pill why-timing">time</span>
                            <span
                                >No mastery change; schedules a timed drill (~2:08 per question
                                pace) in Today's practice.</span
                            >
                        </li>
                        <li>
                            <span class="pill why-guess">guessed</span>
                            <span
                                >The &ldquo;I guessed&rdquo; link on a correct answer cancels the
                                lucky-correct mastery bump, so your score stays honest.</span
                            >
                        </li>
                    </ul>
                </section>
            {/if}

            {#if errors.length === 0}
                <section class="q-card empty">
                    <p>No logged errors yet. Missed questions in Practice appear here automatically.</p>
                </section>
            {:else}
                <div class="err-filters">
                    {#each [["all", "All"], ["careless", "Careless"], ["concept_gap", "Concept gap"], ["timing", "Timing"], ["guess", "Guessed"]] as [key, label]}
                        <button
                            class="why-chip"
                            class:active={errorFilter === key}
                            on:click={() => (errorFilter = key as "all" | ErrorWhy)}
                        >
                            {label}
                        </button>
                    {/each}
                </div>
                <ul class="err-list">
                    {#each filteredErrors as e}
                        <li class="err">
                            <div class="err-top">
                                <span class="pill">{topicLabel(e.topic) || "Quant"}</span>
                                {#if e.why}
                                    <span class="pill why-{e.why}">{e.why.replace("_", " ")}</span>
                                {/if}
                                {#if e.mock}
                                    <span class="pill">mock</span>
                                {/if}
                                <span class="muted">
                                    chose {e.chosen} &middot; correct {e.correct}
                                    {#if e.ms}&middot; {fmtTime(Math.round(e.ms / 1000))}{/if}
                                </span>
                            </div>
                            <p class="err-stem">{e.stem}</p>
                            {#if e.ai_takeaway}
                                <section class="q-card coach-card">
                                    <p class="eyebrow">Why you missed it</p>
                                    <p class="explain">{e.ai_takeaway.root_cause}</p>
                                    <p class="eyebrow">The rule</p>
                                    <p class="explain">{e.ai_takeaway.rule}</p>
                                    <p class="eyebrow">10-second check</p>
                                    <p class="explain">{e.ai_takeaway.check}</p>
                                    <p class="eyebrow">Next</p>
                                    <p class="explain">{e.ai_takeaway.next_action}</p>
                                </section>
                            {:else if aiOn}
                                {#if coachLoadingTs === e.ts}
                                    <p class="muted">Coaching&hellip;</p>
                                {:else}
                                    <button class="tb-go coach-btn" on:click={() => coachErrorEntry(e)}>
                                        Coach this miss
                                    </button>
                                {/if}
                                {#if coachUnavailableTs[e.ts]}
                                    <p class="muted coach-unavail">AI coaching unavailable</p>
                                {/if}
                            {/if}
                            <button class="tb-go" on:click={() => repairNow(e)}>
                                {e.why === "concept_gap" && e.topic && hasLessonFor.has(e.topic)
                                    ? "Repair now: relearn"
                                    : "Repair now: practice"}
                            </button>
                        </li>
                    {/each}
                </ul>
            {/if}
        </main>
    {/if}
    {/if}
</div>

<style>
    /*
      GMATWiz "Arcane Academy" theme. Every color/font is a token so a light
      mode is later just a second token set on .gw. Palette: deep indigo night,
      parchment ink, arcane gold (brand) and amethyst (primary action), with
      ember/emerald reserved for wrong/right. Signature: a faded "spellfall" of
      GMAT math glyphs drifting behind the content.
    */
    .gw {
        --paper: #130e2b;
        --paper-2: #1c1445;
        --surface: #221a46;
        --surface-2: #2b2159;
        --sunk: #191234;
        --ink: #efeaff;
        --ink-soft: #c4b8ea;
        --ink-faint: #8f83b8;
        /* amethyst = primary action / selection */
        --indicator: #9a6bf5;
        --indicator-ink: #7c4de0;
        --indicator-tint: rgba(154, 107, 245, 0.16);
        /* ember = wrong / repair */
        --clay-ink: #ec7a70;
        --clay-tint: rgba(236, 122, 112, 0.15);
        /* gold = brand / accents */
        --gold: #f2c879;
        --gold-ink: #e8b84b;
        --brass-ink: #e8b84b;
        --brass-tint: rgba(232, 184, 75, 0.14);
        /* emerald = correct / good */
        --emerald: #57d9a8;
        --emerald-ink: #3fb98a;
        --emerald-tint: rgba(87, 217, 168, 0.18);
        --line: rgba(240, 205, 130, 0.16);
        --line-strong: rgba(240, 205, 130, 0.36);
        --shadow: 0 12px 34px rgba(0, 0, 0, 0.5);
        --glow: 0 0 26px rgba(154, 107, 245, 0.4);
        --gold-glow: 0 0 20px rgba(240, 200, 120, 0.35);
        --voice: "Hoefler Text", "Baskerville", "Iowan Old Style", Georgia, serif;
        --script: "Snell Roundhand", "Zapfino", "Apple Chancery", "Segoe Script", cursive;
        --ui: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;

        position: relative;
        box-sizing: border-box;
        min-height: 100vh;
        margin: 0;
        background:
            radial-gradient(120% 80% at 82% -10%, var(--paper-2) 0%, transparent 55%),
            radial-gradient(90% 60% at 10% 0%, rgba(154, 107, 245, 0.12) 0%, transparent 45%),
            var(--paper);
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
    /* ambient spellfall behind everything */
    .sky {
        position: fixed;
        inset: 0;
        overflow: hidden;
        pointer-events: none;
        z-index: 0;
    }
    .glyph {
        position: absolute;
        top: 0;
        font-family: var(--mono);
        opacity: 0;
        animation-name: spellfall;
        animation-timing-function: linear;
        animation-iteration-count: infinite;
        text-shadow: 0 0 14px currentColor;
        will-change: transform, opacity;
    }
    @keyframes spellfall {
        0% {
            transform: translateY(-12vh) rotate(0deg);
            opacity: 0;
        }
        12% {
            opacity: 0.3;
        }
        88% {
            opacity: 0.3;
        }
        100% {
            transform: translateY(112vh) rotate(45deg);
            opacity: 0;
        }
    }
    /* soft floating gold orbs (bokeh) rising through the night */
    .orb {
        position: absolute;
        bottom: -18%;
        border-radius: 50%;
        background: radial-gradient(
            circle at 35% 35%,
            rgba(242, 200, 121, 0.5),
            rgba(242, 200, 121, 0.12) 45%,
            transparent 70%
        );
        filter: blur(2px);
        opacity: 0;
        animation-name: floatup;
        animation-timing-function: linear;
        animation-iteration-count: infinite;
        will-change: transform, opacity;
    }
    .orb-amethyst {
        background: radial-gradient(
            circle at 35% 35%,
            rgba(154, 107, 245, 0.5),
            rgba(154, 107, 245, 0.12) 45%,
            transparent 70%
        );
    }
    @keyframes floatup {
        0% {
            transform: translateY(20vh) scale(0.85);
            opacity: 0;
        }
        20% {
            opacity: 0.5;
        }
        80% {
            opacity: 0.5;
        }
        100% {
            transform: translateY(-120vh) scale(1.1);
            opacity: 0;
        }
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .sigil {
        width: 34px;
        height: 34px;
        flex: none;
        filter: drop-shadow(var(--gold-glow));
    }
    .hat-brim,
    .hat-cone {
        fill: var(--indicator);
    }
    .hat-band,
    .hat-star,
    .hat-spark {
        fill: var(--gold);
    }
    .wordmark {
        display: inline-flex;
        align-items: baseline;
    }
    .wm-gmat {
        font-family: var(--voice);
        font-weight: 700;
        font-size: 22px;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--gold);
    }
    .wm-wiz {
        font-family: var(--script);
        font-size: 30px;
        line-height: 0.8;
        color: var(--indicator);
        margin-left: 6px;
        transform: rotate(-5deg);
        text-shadow: var(--glow);
    }

    /* sign-in gate */
    .auth-screen {
        max-width: 440px;
    }
    .auth-brand {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
        margin: 48px 0 6px;
    }
    .sigil-lg {
        width: 56px;
        height: 56px;
    }
    .auth-brand .wm-gmat {
        font-size: 28px;
    }
    .auth-brand .wm-wiz {
        font-size: 40px;
    }
    .auth-lede {
        text-align: center;
        margin-bottom: 24px;
    }
    .auth-card {
        margin-bottom: 0;
    }
    .auth-tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 16px;
    }
    .auth-tabs button {
        appearance: none;
        flex: 1;
        background: none;
        border: 1px solid var(--line-strong);
        color: var(--ink-soft);
        font-family: var(--ui);
        font-size: 14px;
        font-weight: 600;
        padding: 9px 12px;
        border-radius: 9px;
        cursor: pointer;
    }
    .auth-tabs button.active {
        border-color: var(--gold-ink);
        color: var(--gold);
        background: var(--brass-tint);
    }
    .nav {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
    }
    .nav-spacer {
        width: 10px;
    }
    .nav-util {
        appearance: none;
        background: none;
        font-family: var(--ui);
        font-size: 14px;
        color: var(--ink-soft);
        padding: 6px 12px;
        border: 1px solid var(--line-strong);
        border-radius: 8px;
        cursor: pointer;
    }
    .nav-util:hover {
        color: var(--indicator-ink);
        border-color: var(--indicator-ink);
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
        color: var(--gold);
        font-weight: 600;
        text-shadow: 0 0 14px rgba(240, 200, 120, 0.4);
    }
    .nav button:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }

    .col {
        position: relative;
        z-index: 1;
        max-width: 720px;
        margin: 0 auto;
        padding: 32px 24px 64px;
    }
    .col-wide {
        position: relative;
        z-index: 1;
        max-width: 1040px;
        margin: 0 auto;
        padding: 32px 24px 64px;
    }
    .activity {
        margin-top: 26px;
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
        box-shadow: var(--shadow);
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
        border: 1px solid var(--gold-ink);
        background: linear-gradient(180deg, var(--indicator) 0%, var(--indicator-ink) 100%);
        color: #fff;
        font-family: var(--ui);
        font-size: 15px;
        font-weight: 600;
        padding: 11px 22px;
        border-radius: 10px;
        cursor: pointer;
        box-shadow: var(--glow);
    }
    .primary:hover:not(:disabled) {
        background: linear-gradient(180deg, #ac82ff 0%, var(--indicator) 100%);
        box-shadow: 0 0 30px rgba(154, 107, 245, 0.55);
    }
    .primary:disabled {
        opacity: 0.45;
        cursor: default;
    }
    .primary:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }

    .today-list {
        list-style: none;
        margin: 6px 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .today-block {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        border: 1px solid var(--line);
        border-left: 3px solid var(--line-strong);
        border-radius: 12px;
        background: var(--surface);
    }
    .today-block.kind-review { border-left-color: var(--indicator-ink); }
    .today-block.kind-learn { border-left-color: var(--brass-ink, #9a6b1f); }
    .today-block.kind-practice { border-left-color: var(--clay-ink, #b4531f); }
    .today-block.kind-repair { border-left-color: var(--clay-ink, #8c4233); }
    .today-block.kind-mock { border-left-color: var(--ink); }
    /* assessment tiers: quiz = mastery gate (emerald), milestone = checkpoint (gold) */
    .today-block.kind-quiz { border-left-color: var(--emerald-ink, #3fb98a); }
    .today-block.kind-milestone { border-left-color: var(--gold-ink, #e8b84b); }
    .tb-index {
        flex: none;
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        border: 1px solid var(--line-strong);
        font-family: var(--mono);
        font-size: 12px;
        color: var(--ink-soft);
    }
    .tb-body {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .tb-title {
        font-family: var(--ui);
        font-weight: 600;
        font-size: 15px;
    }
    .tb-detail {
        font-size: 12.5px;
        color: var(--ink-faint);
    }
    .tb-min {
        flex: none;
        font-family: var(--mono);
        font-size: 12px;
        color: var(--ink-faint);
    }
    .tb-go {
        appearance: none;
        flex: none;
        border: 1px solid var(--line-strong);
        background: var(--surface);
        color: var(--ink-soft);
        font-family: var(--ui);
        font-size: 13px;
        font-weight: 600;
        padding: 6px 12px;
        border-radius: 8px;
        cursor: pointer;
    }
    .tb-go:hover:not(:disabled) {
        border-color: var(--indicator-ink);
        color: var(--indicator-ink);
    }
    .tb-go:disabled {
        opacity: 0.5;
        cursor: default;
        border-color: var(--line);
        color: var(--ink-faint);
    }

    /* a completed Today task: dimmed, checkmarked, its button locked */
    .today-block.done {
        opacity: 0.62;
        border-left-color: var(--emerald-ink);
    }
    .today-block.done .tb-index {
        color: var(--emerald);
        border-color: var(--emerald-ink);
    }

    /* the inline "back" control shared by lesson/practice snippets. `button`
       raises specificity above the later `.ghost` rule so the margin sticks. */
    button.back-inline {
        margin: 0 0 14px 0;
    }

    /* Study tab: topic rows with a mastery bar + Learn/Practice actions */
    .study-list {
        list-style: none;
        margin: 6px 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .study-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        border: 1px solid var(--line);
        border-left: 3px solid var(--brass-ink, #9a6b1f);
        border-radius: 12px;
        background: var(--surface);
    }
    .sr-body {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .sr-name {
        font-family: var(--ui);
        font-weight: 600;
        font-size: 15px;
    }
    .sr-meta {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .sr-meta .focus-bar {
        flex: 1 1 auto;
        margin: 0;
    }
    .sr-actions {
        flex: none;
        display: flex;
        gap: 8px;
    }

    /* error-log why-capture + filters */
    .why-box {
        margin-top: 14px;
        padding: 12px 14px;
        border: 1px solid var(--clay-ink);
        border-radius: 10px;
        background: var(--clay-tint);
    }
    .why-q {
        margin: 0 0 8px;
        font-weight: 600;
        font-size: 14px;
    }
    .why-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .why-chip {
        appearance: none;
        border: 1px solid var(--line-strong);
        background: var(--surface);
        color: var(--ink-soft);
        font-family: var(--ui);
        font-size: 13px;
        font-weight: 600;
        padding: 6px 12px;
        border-radius: 999px;
        cursor: pointer;
    }
    .why-chip:hover,
    .why-chip.active {
        border-color: var(--indicator-ink);
        color: var(--indicator-ink);
    }
    .guess-link {
        display: inline-block;
        margin-right: 10px;
    }
    .err-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 14px;
    }
    .why-careless { background: var(--brass-tint); }
    .why-concept_gap { background: var(--clay-tint); }
    .why-timing { background: var(--indicator-tint); }
    .why-guess { background: var(--sunk); }

    /* error-log explainer (the "i" toggle) */
    .err-header {
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }
    .err-header .display {
        flex: 1;
        min-width: 0;
    }
    .info-btn {
        appearance: none;
        flex: none;
        width: 28px;
        height: 28px;
        margin-top: 4px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        border: 1px solid var(--line-strong);
        background: var(--surface);
        color: var(--gold-ink);
        font-family: var(--voice);
        font-style: italic;
        font-size: 16px;
        font-weight: 700;
        line-height: 1;
        cursor: pointer;
    }
    .info-btn:hover,
    .info-btn[aria-expanded="true"] {
        border-color: var(--gold-ink);
        color: var(--gold);
        box-shadow: var(--gold-glow);
    }
    .err-explainer {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: var(--shadow);
        margin-bottom: 22px;
    }
    .ex-base {
        font-size: 14px;
        line-height: 1.55;
        color: var(--ink-soft);
        margin: 0 0 14px;
    }
    .ex-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .ex-list li {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        font-size: 13.5px;
        line-height: 1.5;
        color: var(--ink-soft);
    }
    .ex-list .pill {
        flex: none;
        margin-top: 1px;
    }

    /* practice-test library */
    .tests-cta {
        border-left: 3px solid var(--gold-ink);
    }
    .test-list {
        list-style: none;
        margin: 6px 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .test-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        border: 1px solid var(--line);
        border-left: 3px solid var(--line-strong);
        border-radius: 12px;
        background: var(--surface);
    }
    .test-row.taken {
        border-left-color: var(--emerald-ink);
    }
    .test-meta {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .test-label {
        font-family: var(--ui);
        font-weight: 600;
        font-size: 15px;
    }
    .test-score {
        flex: none;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .test-start {
        flex: none;
        margin-top: 0;
    }
    .overpace {
        color: var(--clay-ink);
    }
    .warn-text {
        color: var(--clay-ink);
    }
    .muted-display {
        color: var(--ink-faint);
        font-size: 0.6em;
    }

    .official {
        margin-top: 22px;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 16px 18px;
    }
    .os-form {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 12px;
        margin-top: 10px;
    }
    .os-form label {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .os-label {
        font-size: 12px;
        color: var(--ink-faint);
    }
    .os-input {
        font-family: var(--mono);
        font-size: 15px;
        padding: 8px 10px;
        border: 1px solid var(--line-strong);
        border-radius: 8px;
        background: var(--paper);
        color: var(--ink);
        width: 130px;
    }
    .os-save {
        margin-top: 0;
    }
    .os-list {
        list-style: none;
        margin: 14px 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .os-item {
        display: flex;
        align-items: baseline;
        gap: 10px;
        padding: 6px 0;
        border-top: 1px solid var(--line);
    }

    /* progress (integrated stats) */
    .progress-card {
        margin-top: 16px;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 16px 18px;
    }
    .spark {
        display: flex;
        align-items: flex-end;
        gap: 6px;
        height: 88px;
        margin-top: 12px;
    }
    .spark-col {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-end;
        height: 100%;
        gap: 4px;
    }
    .spark-bar {
        width: 100%;
        min-height: 2px;
        background: var(--indicator);
        border-radius: 4px 4px 0 0;
    }
    .spark-bar.cast {
        background: var(--brass-ink, #9a6b1f);
        opacity: 0.7;
    }
    .spark-x {
        font-family: var(--mono);
        font-size: 10px;
        color: var(--ink-faint);
    }
    .pipe {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 12px;
    }
    .pipe-row {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .pipe-label {
        width: 68px;
        font-size: 13px;
        color: var(--ink-soft);
    }
    .pipe-track {
        flex: 1;
        height: 10px;
        background: var(--line);
        border-radius: 999px;
        overflow: hidden;
    }
    .pipe-fill {
        height: 100%;
        border-radius: 999px;
        background: var(--indicator);
    }
    .pipe-new { background: var(--ink-faint); }
    .pipe-learning { background: var(--clay-ink, #b4531f); }
    .pipe-young { background: var(--brass-ink, #9a6b1f); }
    .pipe-mature { background: var(--indicator); }
    .pipe-n {
        width: 40px;
        text-align: right;
        font-family: var(--mono);
        font-size: 13px;
        color: var(--ink-soft);
    }
    .progress-actions {
        display: flex;
        gap: 10px;
        margin-top: 18px;
    }

    /* mock exam: flag, nav, review grid */
    .q-head-right {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .flag-btn {
        appearance: none;
        border: 1px solid var(--line-strong);
        background: var(--surface);
        color: var(--ink-soft);
        font-family: var(--ui);
        font-size: 12px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 999px;
        cursor: pointer;
    }
    .flag-btn.on {
        border-color: var(--clay-ink);
        color: var(--clay-ink);
        background: var(--clay-tint);
    }
    .mock-nav {
        display: flex;
        gap: 10px;
        align-items: center;
        margin-top: 16px;
    }
    .mock-nav .primary {
        margin-top: 0;
    }
    .review-grid {
        list-style: none;
        margin: 12px 0 16px;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
        gap: 8px;
    }
    .review-cell {
        width: 100%;
        appearance: none;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        padding: 8px 4px;
        border: 1px solid var(--line-strong);
        border-radius: 8px;
        background: var(--surface);
        color: var(--ink);
    }
    .review-cell.answered {
        background: var(--indicator-tint);
        border-color: var(--indicator-ink);
    }
    .review-cell.unanswered {
        background: var(--sunk);
    }
    .review-cell.flagged {
        border-color: var(--clay-ink);
        border-width: 2px;
    }
    .rc-n {
        font-family: var(--mono);
        font-size: 11px;
        color: var(--ink-faint);
    }
    .rc-state {
        font-family: var(--mono);
        font-size: 14px;
        font-weight: 600;
    }

    .pace {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 22px;
    }
    .pace-top {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
    }
    .pace-status {
        font-family: var(--mono);
        font-size: 12px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--indicator-ink);
    }
    .pace-days {
        font-family: var(--mono);
        font-size: 12px;
        color: var(--ink-faint);
    }
    .pace-bar {
        height: 6px;
        border-radius: 999px;
        background: var(--line);
        margin: 10px 0 8px;
        overflow: hidden;
    }
    .pace-fill {
        display: block;
        height: 100%;
        background: var(--indicator);
        border-radius: 999px;
    }
    .pace-detail {
        margin: 0;
        font-size: 12.5px;
        color: var(--ink-faint);
    }
    .pace-behind .pace-status {
        color: var(--clay-ink, #b4531f);
    }
    .pace-behind .pace-fill {
        background: var(--clay-ink, #b4531f);
    }

    /* --- forward study calendar (Progress) ------------------------------- */
    .calendar {
        margin-bottom: 22px;
    }
    .cal-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }
    .cal-lede {
        font-size: 14px;
        line-height: 1.55;
        color: var(--ink-soft);
        margin: 0 0 12px;
    }
    .cal-lede strong {
        color: var(--gold);
        font-weight: 600;
    }
    .cal-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        margin-bottom: 14px;
    }
    .cal-leg {
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--ink-faint);
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .cal-leg::before {
        content: "";
        width: 10px;
        height: 10px;
        border-radius: 3px;
        background: var(--line-strong);
    }
    .cal-leg.phase-learn::before {
        background: var(--indicator);
    }
    .cal-leg.phase-review::before {
        background: var(--brass-ink);
    }
    .cal-leg.phase-final::before {
        background: var(--emerald-ink);
    }

    .cal-weeks {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .cal-week {
        display: flex;
        align-items: stretch;
        gap: 10px;
    }
    .cal-week-label {
        flex: none;
        width: 34px;
        padding-top: 6px;
        font-family: var(--mono);
        font-size: 11px;
        color: var(--ink-faint);
        text-align: right;
    }
    .cal-row {
        flex: 1;
        min-width: 0;
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 6px;
    }
    .cal-day {
        min-width: 0;
        min-height: 86px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
        border: 1px solid var(--line);
        border-top: 3px solid var(--line-strong);
        border-radius: 10px;
        background: var(--surface);
        position: relative;
    }
    .cal-day.phase-learn {
        border-top-color: var(--indicator);
    }
    .cal-day.phase-review {
        border-top-color: var(--brass-ink);
    }
    /* the tests-only final stretch reads as a distinct emerald band */
    .cal-day.phase-final {
        border-top-color: var(--emerald-ink);
        background:
            linear-gradient(180deg, var(--emerald-tint) 0%, transparent 62%),
            var(--sunk);
    }
    .cal-day.today {
        border-color: var(--indicator);
        box-shadow: var(--glow);
    }
    .cal-day.exam {
        border-color: var(--gold-ink);
        border-top-color: var(--gold-ink);
        background:
            radial-gradient(120% 80% at 50% 0%, var(--brass-tint) 0%, transparent 70%),
            var(--surface);
        text-align: center;
    }
    .cal-day.rest {
        background: transparent;
        border-style: dashed;
        border-top-style: solid;
        opacity: 0.6;
    }
    .cal-day-top {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 4px;
    }
    .cal-dow {
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.04em;
        color: var(--ink-faint);
        text-transform: uppercase;
    }
    .cal-date {
        font-family: var(--mono);
        font-size: 11px;
        color: var(--ink-soft);
    }
    .cal-flag {
        align-self: flex-start;
        font-family: var(--mono);
        font-size: 10px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #fff;
        background: var(--indicator);
        border-radius: 999px;
        padding: 1px 7px;
    }
    .cal-items {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 3px;
        flex: 1;
    }
    .cal-chip {
        display: flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
        font-size: 11px;
        line-height: 1.3;
        color: var(--ink-soft);
        border-radius: 6px;
        padding: 2px 5px;
        background: var(--sunk);
        border-left: 2px solid var(--line-strong);
    }
    .cal-chip-g {
        flex: none;
        font-family: var(--mono);
        font-size: 10px;
        opacity: 0.9;
    }
    .cal-chip-t {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .cal-chip.chip-lesson {
        border-left-color: var(--brass-ink);
        color: var(--ink);
    }
    .cal-chip.chip-quiz {
        border-left-color: var(--emerald-ink);
    }
    .cal-chip.chip-requiz {
        border-left-color: var(--emerald-ink);
        opacity: 0.85;
    }
    .cal-chip.chip-milestone {
        border-left-color: var(--gold-ink);
        color: var(--gold);
    }
    .cal-chip.chip-practice_test {
        border-left-color: var(--emerald-ink);
        color: var(--ink);
        background: var(--emerald-tint);
    }
    .cal-chip.chip-review {
        border-left-color: var(--line-strong);
        color: var(--ink-faint);
    }
    .cal-chip.chip-drill {
        border-left-color: var(--indicator-ink);
    }
    .cal-min {
        font-family: var(--mono);
        font-size: 10px;
        color: var(--ink-faint);
        align-self: flex-end;
    }
    .cal-rest {
        font-family: var(--mono);
        font-size: 11px;
        color: var(--ink-faint);
        margin: auto 0;
    }
    .cal-exam {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        margin: auto 0;
        font-family: var(--voice);
        font-size: 13px;
        color: var(--gold);
    }
    .cal-exam-g {
        font-size: 20px;
        filter: drop-shadow(var(--gold-glow));
    }
    @media (max-width: 720px) {
        .cal-week-label {
            width: 22px;
            font-size: 10px;
        }
        .cal-row {
            gap: 4px;
        }
        .cal-day {
            min-height: 70px;
            padding: 5px;
        }
        .cal-chip-t {
            display: none;
        }
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
        color: var(--gold);
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
        color: var(--gold);
        font-weight: 600;
    }

    .q-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 22px;
        box-shadow: var(--shadow);
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
    /* selected but not yet committed: unmistakable amethyst with a glow */
    .opt.sel {
        border-color: var(--indicator) !important;
        background: var(--indicator-tint) !important;
        box-shadow: 0 0 0 1px var(--indicator), var(--glow) !important;
    }
    .opt.sel .opt-key {
        background: var(--indicator) !important;
        color: #fff !important;
        border-color: var(--indicator) !important;
    }
    /* after reveal: correct = emerald, your wrong pick = ember */
    .opt.correct {
        border-color: var(--emerald) !important;
        background: var(--emerald-tint) !important;
        box-shadow: 0 0 0 1px var(--emerald) !important;
    }
    .opt.correct .opt-key {
        background: var(--emerald) !important;
        color: #10231c !important;
        border-color: var(--emerald) !important;
    }
    .opt.correct::after {
        content: "correct";
        margin-left: auto;
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--emerald);
    }
    .opt.wrong {
        border-color: var(--clay-ink) !important;
        background: var(--clay-tint) !important;
        box-shadow: 0 0 0 1px var(--clay-ink) !important;
    }
    .opt.wrong .opt-key {
        background: var(--clay-ink) !important;
        color: #2a1210 !important;
        border-color: var(--clay-ink) !important;
    }
    .opt.wrong::after {
        content: "your pick";
        margin-left: auto;
        font-family: var(--mono);
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--clay-ink);
    }
    .opt.muted {
        opacity: 0.45;
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
        background: var(--emerald-tint);
        border-color: var(--emerald);
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
        color: var(--gold);
        text-shadow: var(--gold-glow);
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
    /* Study: soft-gate state on a topic */
    .mastered-pill {
        background: var(--emerald-tint);
        border-color: var(--emerald-ink);
        color: var(--emerald-ink);
    }
    .learned-pill {
        background: var(--brass-tint);
        border-color: var(--brass-ink);
        color: var(--gold-ink);
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
    .coach-card {
        margin: 10px 0;
        padding: 12px 14px;
    }
    .coach-card .eyebrow {
        margin: 8px 0 4px;
    }
    .coach-card .eyebrow:first-child {
        margin-top: 0;
    }
    .coach-card .explain {
        margin: 0 0 4px;
    }
    .coach-btn {
        margin: 8px 0 0;
    }
    .coach-unavail {
        margin: 6px 0 0;
        font-size: 13px;
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
        color: var(--brass-ink);
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

    /* AI features toggle card (Progress) */
    .ai-title {
        font-family: var(--voice);
        font-size: 20px;
        margin: 2px 0 8px;
    }
    .ai-hint {
        margin-top: 10px;
        color: var(--emerald);
    }
    .ai-switch {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 0;
        border: none;
        background: none;
        cursor: pointer;
        font-family: var(--ui);
        font-size: 13px;
        font-weight: 600;
        color: var(--ink-faint);
    }
    .ai-switch:disabled {
        opacity: 0.6;
        cursor: default;
    }
    .ai-track {
        position: relative;
        width: 44px;
        height: 24px;
        border-radius: 999px;
        background: var(--sunk);
        border: 1px solid var(--line-strong);
        transition:
            background 0.15s ease,
            border-color 0.15s ease;
    }
    .ai-knob {
        position: absolute;
        top: 2px;
        left: 2px;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: var(--ink-soft);
        transition:
            left 0.15s ease,
            background 0.15s ease;
    }
    .ai-switch.on .ai-track {
        background: linear-gradient(180deg, var(--indicator) 0%, var(--indicator-ink) 100%);
        border-color: var(--gold-ink);
        box-shadow: var(--glow);
    }
    .ai-switch.on .ai-knob {
        left: 22px;
        background: #fff;
    }
    .ai-switch.on .ai-state {
        color: var(--indicator);
    }
    .ai-switch:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 3px;
        border-radius: 4px;
    }

    /* generation affordance + soft "AI unavailable" note */
    .gen-btn {
        margin-top: 16px;
    }
    .ai-note {
        margin-top: 12px;
    }
    .ai-note.ok {
        color: var(--emerald-ink, var(--emerald));
        font-weight: 600;
    }

    /* End-session control + review summary */
    .session-controls {
        display: flex;
        justify-content: flex-end;
        margin: -4px 0 12px;
    }
    button.end-session {
        font-size: 13px;
    }
    .summary-tally {
        font-family: var(--mono);
        font-size: 15px;
        color: var(--ink-soft);
        margin: 6px 0 16px;
    }
    .tally-ok {
        color: var(--emerald);
    }
    .tally-no {
        color: var(--clay-ink);
    }
    .summary-list {
        list-style: none;
        margin: 0 0 18px;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 360px;
        overflow-y: auto;
    }
    .summary-row {
        display: grid;
        grid-template-columns: 20px 1fr auto;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border: 1px solid var(--line);
        border-left: 3px solid var(--line-strong);
        border-radius: 10px;
        background: var(--surface);
    }
    .summary-row.ok {
        border-left-color: var(--emerald-ink);
    }
    .summary-row.no {
        border-left-color: var(--clay-ink);
    }
    .summary-row .sr-mark {
        font-family: var(--mono);
        font-weight: 700;
        text-align: center;
    }
    .summary-row.ok .sr-mark {
        color: var(--emerald);
    }
    .summary-row.no .sr-mark {
        color: var(--clay-ink);
    }
    .sr-main {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .summary-row .sr-stem {
        font-size: 13px;
        color: var(--ink-soft);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .summary-row .sr-ans {
        font-family: var(--mono);
        font-size: 12px;
        color: var(--ink-faint);
        white-space: nowrap;
    }
    .summary-actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }

    @media (max-width: 720px) {
        .score-grid {
            grid-template-columns: 1fr;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .glyph {
            animation: none;
            opacity: 0.14;
        }
        .orb {
            animation: none;
            opacity: 0.28;
        }
    }
</style>
