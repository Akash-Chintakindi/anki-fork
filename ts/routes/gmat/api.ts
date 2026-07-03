// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Data access for the GMATWiz app shell. Kept out of +page.ts because SvelteKit
// only allows load-style exports from +page.ts.

export interface GmatQuestion {
    stem: string;
    options: Record<string, string>;
    correct: string;
    explanation: string;
    topic: string;
    difficulty: string;
}

export interface CalibrationBin {
    label: string;
    observed: number;
    n: number;
}

export interface GmatMemory {
    status: "shown" | "abstain";
    point?: number;
    low?: number;
    high?: number;
    reviews: number;
    reviews_required?: number;
    reason?: string;
    target?: number;
    ece?: number;
    calibrated?: boolean;
    bins?: CalibrationBin[];
    updated_ts?: number;
}

export interface GmatProfile {
    exam_date: string;
    days_per_week: number;
    // Goal-driven: the target GMAT Focus total (clamped [205, 805]) replaces the
    // old minutes-per-day input; the per-topic mastery bar is derived from it.
    target_score: number;
}

export interface PlanTopic {
    topic: string;
    mastery: number;
    status: "weak" | "developing" | "strong";
}

export interface GmatPlan {
    topics: PlanTopic[];
    days_per_week: number;
    days_to_exam: number | null;
    created_ts: number;
    // derived from the profile's target_score at plan-build time
    target_score: number;
    mastery_bar: number;
}

export interface PerfEval {
    baseline_brier: number;
    model_brier: number;
    beats_baseline: boolean;
    test_n: number;
}

export interface TimingInfo {
    n: number;
    avg_ms: number;
    target_ms: number;
    rushed_wrong: number;
    slow_correct: number;
}

export interface GmatPerformance {
    status: "shown" | "abstain";
    point?: number;
    low?: number;
    high?: number;
    attempts: number;
    attempts_required?: number;
    reason?: string;
    weak_topics?: { topic: string; accuracy: number; n: number }[];
    eval?: PerfEval | null;
    timing?: TimingInfo | null;
    updated_ts?: number;
}

export interface MockEntry {
    ts: number;
    accuracy: number;
    n: number;
    q: number;
}

export interface OfficialScore {
    ts: number;
    date?: string;
    quant: number;
    total?: number | null;
    verbal?: number | null;
    di?: number | null;
    projected_at_entry?: number | null;
}

export interface Calibration {
    n: number;
    bias: number;
    residual: number;
    point: number;
    low: number;
    high: number;
}

export interface GmatReadiness {
    status: "shown" | "abstain";
    section?: string;
    point?: number;
    low?: number;
    high?: number;
    scale?: string;
    confidence?: string;
    method?: string;
    total_status?: string;
    total_reason?: string;
    unmet?: string[];
    reason?: string;
    mocks?: MockEntry[];
    mock_gap?: number | null;
    official?: OfficialScore[];
    calibration?: Calibration | null;
    updated_ts?: number;
}

export interface GmatOverview {
    deck: string;
    total: number;
    new: number;
    due: number;
    reviews: number;
    topics_covered: number;
    topics_total: number;
    memory: GmatMemory;
    performance: GmatPerformance;
    readiness: GmatReadiness;
    profile: GmatProfile | null;
    plan: GmatPlan | null;
}

export interface GmatPacing {
    status: "on_track" | "behind" | "learning_complete" | "no_pacing";
    days_to_exam: number | null;
    topics_total: number;
    topics_learned: number;
    topics_remaining: number;
    behind_by: number;
    topics_per_study_day: number;
    study_days_remaining: number | null;
    // true when we're inside the final 10 days (or too little runway) and pacing
    // falls back to all remaining study days instead of the exam-minus-10 window
    late_start: boolean;
}

export interface TodayBlock {
    kind: "review" | "learn" | "practice" | "repair" | "mock";
    title: string;
    detail: string;
    count?: number;
    topic?: string | null;
    // a "mock" block sourced from the practice-test library carries the form to run
    form_id?: string;
    label?: string;
    est_minutes: number;
}

export interface TodaySession {
    has_plan: boolean;
    pacing: GmatPacing | null;
    blocks: TodayBlock[];
    // DERIVED (no longer user-set): the sum of est_minutes of today's blocks
    daily_minutes: number;
}

export interface PretestQuestion {
    stem: string;
    options: Record<string, string>;
    correct: string;
    topic: string;
    difficulty: string;
}

/** Why a question was missed - the one-prompt error-log classification. */
export type ErrorWhy = "careless" | "concept_gap" | "timing" | "guess" | "";

export interface CoachTakeaway {
    root_cause: string;
    rule: string;
    check: string;
    next_action: string;
}

export interface ErrorEntry {
    stem: string;
    topic: string;
    chosen: string;
    correct: string;
    why?: ErrorWhy;
    ms?: number;
    mock?: boolean;
    options?: Record<string, string>;
    explanation?: string;
    ai_takeaway?: CoachTakeaway;
    ts: number;
}

export interface ScheduledCard {
    card_id: number;
    stem: string;
    options: Record<string, string>;
    correct: string;
    explanation: string;
    topic: string;
    difficulty: string;
}

export interface Counts {
    new: number;
    learning: number;
    review: number;
}

export interface NextCardResult {
    card: ScheduledCard | null;
    counts: Counts;
}

export const EMPTY_OVERVIEW: GmatOverview = {
    deck: "GMAT::Quant",
    total: 0,
    new: 0,
    due: 0,
    reviews: 0,
    topics_covered: 0,
    topics_total: 18,
    memory: { status: "abstain", reviews: 0, reviews_required: 150 },
    performance: { status: "abstain", attempts: 0, attempts_required: 50 },
    readiness: { status: "abstain", unmet: [] },
    profile: null,
    plan: null,
};

const BINARY = { "Content-Type": "application/binary" };

async function postJson<T>(method: string, fallback: T, body?: unknown): Promise<T> {
    try {
        const res = await fetch(`/_anki/${method}`, {
            method: "POST",
            headers: BINARY,
            body: body === undefined ? new Uint8Array() : JSON.stringify(body),
        });
        if (!res.ok) return fallback;
        const text = await res.text();
        return text ? (JSON.parse(text) as T) : fallback;
    } catch (_e) {
        return fallback;
    }
}

export async function fetchOverview(): Promise<GmatOverview> {
    return postJson<GmatOverview>("gmatOverview", EMPTY_OVERVIEW);
}

export async function fetchQuestions(): Promise<GmatQuestion[]> {
    const data = await postJson<{ questions: GmatQuestion[] }>("gmatQuestions", {
        questions: [],
    });
    return data.questions ?? [];
}

export async function refreshOverview(): Promise<GmatOverview | null> {
    return postJson<GmatOverview | null>("gmatOverview", null);
}

export async function logError(entry: {
    stem: string;
    topic: string;
    chosen: string;
    correct: string;
    why?: ErrorWhy;
    ms?: number;
    mock?: boolean;
    options?: Record<string, string>;
    explanation?: string;
}): Promise<void> {
    await postJson("gmatLogError", null, entry);
}

export async function fetchErrorLog(): Promise<ErrorEntry[]> {
    const data = await postJson<{ entries: ErrorEntry[] }>("gmatErrorLog", {
        entries: [],
    });
    return data.entries ?? [];
}

export async function saveErrorTakeaway(ts: number, takeaway: CoachTakeaway): Promise<void> {
    await postJson("gmatSetErrorTakeaway", null, { ts, takeaway });
}

export async function fetchNextCard(): Promise<NextCardResult> {
    return postJson<NextCardResult>("gmatNextCard", {
        card: null,
        counts: { new: 0, learning: 0, review: 0 },
    });
}

export async function answerCard(
    cardId: number,
    correct: boolean,
    ms: number,
): Promise<void> {
    await postJson("gmatAnswerCard", null, { card_id: cardId, correct, ms });
}

export async function saveProfile(profile: GmatProfile): Promise<void> {
    await postJson("gmatSaveProfile", null, profile);
}

export async function fetchToday(): Promise<TodaySession> {
    return postJson<TodaySession>("gmatToday", {
        has_plan: false,
        pacing: null,
        blocks: [],
        daily_minutes: 0,
    });
}

export interface GmatStats {
    has_data: boolean;
    reviews_today: number;
    time_today_min: number;
    reviews_total: number;
    streak: number;
    due_today: number;
    forecast: number[];
    spark: number[];
    pipeline: {
        new: number;
        learning: number;
        young: number;
        mature: number;
        total: number;
    };
}

export async function fetchStats(): Promise<GmatStats> {
    return postJson<GmatStats>("gmatStats", {
        has_data: false,
        reviews_today: 0,
        time_today_min: 0,
        reviews_total: 0,
        streak: 0,
        due_today: 0,
        forecast: [],
        spark: [],
        pipeline: { new: 0, learning: 0, young: 0, mature: 0, total: 0 },
    });
}

/** Open Anki's full stats screen (deep-dive graphs). */
export async function openFullStats(): Promise<void> {
    await postJson("gmatOpenStats", null);
}

/** Switch to Anki's deck browser - free-study escape hatch. */
export async function openDecks(): Promise<void> {
    await postJson("gmatOpenDecks", null);
}

/** Trigger Anki's desktop collection sync. */
export async function syncNow(): Promise<void> {
    await postJson("gmatSyncNow", null);
}

// ---- cross-device state (config JSON) sync ----

export type GmatState = Record<string, unknown>;

/** Export this device's GMATWiz state (plan/progress/mocks/errors/... as config). */
export async function exportState(): Promise<GmatState> {
    const data = await postJson<{ state: GmatState }>("gmatExportState", { state: {} });
    return data.state ?? {};
}

/** Apply a synced state blob to this device's collection. */
export async function importState(state: GmatState): Promise<void> {
    await postJson("gmatImportState", null, { state });
}

/** Clear GMATWiz state so a new account starts at the diagnostic. */
export async function resetState(): Promise<void> {
    await postJson("gmatResetState", null);
}

export async function fetchOfficialScores(): Promise<OfficialScore[]> {
    const data = await postJson<{ scores: OfficialScore[] }>("gmatOfficialScores", {
        scores: [],
    });
    return data.scores ?? [];
}

export async function saveOfficialScore(entry: {
    date?: string;
    quant: number;
    total?: number | null;
    verbal?: number | null;
    di?: number | null;
}): Promise<{ ok: boolean; error?: string }> {
    return postJson("gmatSaveOfficialScore", { ok: false }, entry);
}

export async function fetchPretest(): Promise<{
    questions: PretestQuestion[];
    seconds: number;
}> {
    return postJson("gmatPretestQuestions", { questions: [], seconds: 2700 });
}

export async function submitPretest(
    results: { topic: string; correct: boolean }[],
): Promise<{ diagnosis: Record<string, number>; plan: GmatPlan | null }> {
    return postJson(
        "gmatSubmitPretest",
        { diagnosis: {}, plan: null },
        { results },
    );
}

/** Human-readable label for a topic id like "gmat::quant::algebra::quadratics". */
export function topicLabel(topic: string): string {
    const parts = topic.split("::");
    const leaf = parts[parts.length - 1] || topic;
    return leaf.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---- Lessons (teaching loop) ----

export interface LessonItem {
    stem: string;
    options: Record<string, string>;
    correct: string;
    explanation: string;
    difficulty?: string;
    think_aloud_steps?: string[];
    key_takeaway?: string;
    scaffold_hints?: string[];
    immediate_feedback?: { if_correct?: string; if_incorrect?: string };
    topic?: string;
}

export interface Lesson {
    topic_id: string;
    title: string;
    domain: string;
    learning_objectives?: string[];
    opening?: {
        learning_intention?: string;
        success_criteria?: string[];
    };
    i_do: LessonItem;
    we_do: LessonItem[];
    you_do: LessonItem[];
}

export interface LessonTopic {
    topic_id: string;
    title: string;
    domain: string;
    mastery: number | null;
    status: string | null;
    learned: boolean;
}

export async function fetchLessonsIndex(): Promise<{ topics: LessonTopic[] }> {
    return postJson("gmatLessonsIndex", { topics: [] });
}

export async function fetchLesson(topicId: string): Promise<Lesson | null> {
    const data = await postJson<{ lesson: Lesson | null }>(
        "gmatLesson",
        { lesson: null },
        { topic_id: topicId },
    );
    return data.lesson;
}

export async function markLearned(topicId: string): Promise<void> {
    await postJson("gmatMarkLearned", null, { topic_id: topicId });
}

// ---- Mock exams (timed, exam-condition sections) ----

export interface MockQuestion {
    stem: string;
    options: Record<string, string>;
    correct: string;
    topic: string;
    difficulty: string;
    seen: boolean;
}

export interface MockPool {
    pool: MockQuestion[];
    count: number;
    seconds: number;
    target_ms: number;
}

export interface MockResult {
    topic: string;
    difficulty: string;
    correct: boolean;
    ms: number;
    stem: string;
    chosen: string;
    correct_key: string;
}

export interface MockReport {
    ok: boolean;
    accuracy: number;
    n: number;
    q: number | null;
    per_topic: { topic: string; correct: number; n: number }[];
    timing: {
        avg_ms: number;
        rushed_wrong: number;
        slow_correct: number;
        target_ms: number;
    };
}

export async function fetchMockPool(): Promise<MockPool> {
    return postJson<MockPool>("gmatMockQuestions", {
        pool: [],
        count: 21,
        seconds: 2700,
        target_ms: 128000,
    });
}

/**
 * A topic-scoped practice pool in the SAME shape as a mock pool (so the practice
 * card can be reused), filtered to `topic` from the fixed question bank. `n` caps
 * the session length. AI generation to fill gaps is a later phase.
 */
export async function fetchTopicQuestions(topic: string, n: number): Promise<MockPool> {
    return postJson<MockPool>(
        "gmatTopicQuestions",
        { pool: [], count: 0, seconds: 2700, target_ms: 128000 },
        { topic, n },
    );
}

export async function submitMock(
    results: MockResult[],
    formId?: string,
    year?: string,
): Promise<MockReport | null> {
    // form_id/year are optional: when present the submission also records the
    // practice-test form as taken (back-compatible - a plain mock omits them).
    return postJson<MockReport | null>("gmatSubmitMock", null, {
        results,
        form_id: formId,
        year,
    });
}

// ---- Practice-test library (full-length timed forms, grouped by year) ----

export interface TestFormMeta {
    id: string;
    year: string;
    label: string;
    count: number;
    topics: Record<string, number>;
    sources: string[];
    taken: boolean;
    accuracy: number | null;
    q: number | null;
    ts: number | null;
}

export interface TestLibrary {
    years: Record<string, TestFormMeta[]>;
}

/** The practice-test catalog merged with this student's taken/score status. */
export async function fetchTests(): Promise<TestLibrary> {
    return postJson<TestLibrary>("gmatTests", { years: {} });
}

/**
 * A form's questions in the SAME shape as a mock pool (so the timed-mock flow
 * can be reused verbatim), plus which form produced them. Pool order is fixed.
 */
export async function fetchTestQuestions(
    id: string,
): Promise<MockPool & { form_id?: string; label?: string }> {
    return postJson<MockPool & { form_id?: string; label?: string }>(
        "gmatTestQuestions",
        { pool: [], count: 21, seconds: 2700, target_ms: 128000 },
        { id },
    );
}

/**
 * Render simple math notation as HTML: caret exponents (x^2, x^{2}) and the
 * scraped "x2" style (a variable letter directly followed by digits) become
 * superscripts. Input is HTML-escaped first, so the result is safe for {@html}.
 */
export function renderMath(text: string): string {
    const escaped = (text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    return (
        escaped
            // caret: x^2, x^{2}, 2^10
            .replace(/\^\{([^}]+)\}/g, "<sup>$1</sup>")
            .replace(/\^(-?\d+)/g, "<sup>$1</sup>")
            // scraped AQuA-RAT style: a single variable letter immediately
            // followed by digits (e.g. x2, a3) -> exponent. Conservative: only
            // a lone letter (not part of a longer word) followed by 1-2 digits.
            .replace(/(^|[^A-Za-z0-9])([a-zA-Z])(\d{1,2})(?![A-Za-z0-9])/g,
                "$1$2<sup>$3</sup>")
    );
}
