// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// AI Error-Log Coach — structured takeaways for logged misses.

import type { AiResult } from "./ai";
import { generateJson, Schema } from "./ai";
import type { CoachTakeaway, ErrorEntry } from "./api";

export type { CoachTakeaway };

const COACH_SCHEMA = Schema.object({
    properties: {
        root_cause: Schema.string(),
        rule: Schema.string(),
        check: Schema.string(),
        next_action: Schema.string(),
    },
});

const WHY_LABELS: Record<string, string> = {
    careless: "careless slip",
    concept_gap: "concept gap",
    timing: "ran out of time / too slow",
    guess: "guessed (did not know)",
};

function formatOptions(options?: Record<string, string>): string {
    if (!options || !Object.keys(options).length) return "";
    return Object.entries(options)
        .map(([k, v]) => `  ${k}: ${v}`)
        .join("\n");
}

function buildCoachPrompt(e: ErrorEntry): string {
    const whyLabel = e.why ? (WHY_LABELS[e.why] ?? e.why) : "unspecified";
    const optionsBlock = formatOptions(e.options);
    const lines = [
        "You are a GMAT Quant tutor coaching a student on a missed question.",
        "First solve the problem from the stem and options. The marked correct answer is authoritative — explain using that reasoning, do not invent new facts or change the correct letter.",
        "",
        `Topic: ${e.topic || "Quant"}`,
        `Stem: ${e.stem}`,
    ];
    if (optionsBlock) {
        lines.push("Options:", optionsBlock);
    }
    lines.push(
        `Student chose: ${e.chosen}`,
        `Correct answer: ${e.correct}`,
        `Student's self-tag for why they missed it: ${whyLabel}`,
    );
    if (e.ms && e.ms > 0) {
        lines.push(`Time spent: ${Math.round(e.ms / 1000)} seconds`);
    }
    if (e.explanation) {
        lines.push(`Official explanation: ${e.explanation}`);
    }
    lines.push(
        "",
        "Return JSON with exactly these fields (each 1-2 sentences, direct and actionable):",
        "- root_cause: why THIS student likely missed it given their chosen answer and self-tag",
        "- rule: the core concept or rule they should remember",
        "- check: a 10-second sanity check they can use on similar problems",
        "- next_action: one concrete next step (practice focus, habit, or review)",
    );
    return lines.join("\n");
}

export async function coachMiss(e: ErrorEntry): Promise<AiResult<CoachTakeaway>> {
    return generateJson<CoachTakeaway>(buildCoachPrompt(e), COACH_SCHEMA);
}
