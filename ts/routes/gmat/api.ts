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
    minutes_per_day: number;
}

export interface PlanTopic {
    topic: string;
    mastery: number;
    status: "weak" | "developing" | "strong";
}

export interface GmatPlan {
    topics: PlanTopic[];
    daily_minutes: number;
    days_per_week: number;
    days_to_exam: number | null;
    created_ts: number;
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
}

export interface TodayBlock {
    kind: "review" | "learn" | "practice" | "repair" | "mock";
    title: string;
    detail: string;
    count?: number;
    topic?: string | null;
    est_minutes: number;
}

export interface TodaySession {
    has_plan: boolean;
    pacing: GmatPacing | null;
    blocks: TodayBlock[];
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

export interface ErrorEntry {
    stem: string;
    topic: string;
    chosen: string;
    correct: string;
    why?: ErrorWhy;
    ms?: number;
    mock?: boolean;
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
}): Promise<void> {
    await postJson("gmatLogError", null, entry);
}

export async function fetchErrorLog(): Promise<ErrorEntry[]> {
    const data = await postJson<{ entries: ErrorEntry[] }>("gmatErrorLog", {
        entries: [],
    });
    return data.entries ?? [];
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

export async function submitMock(results: MockResult[]): Promise<MockReport | null> {
    return postJson<MockReport | null>("gmatSubmitMock", null, { results });
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
