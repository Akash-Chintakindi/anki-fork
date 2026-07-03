// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// PRD S14.8 "7f" quality gate for generated items. Generators (features B/C)
// must call checkItem() before admitting a card — fail closed when AI is off.

import { generateJson, Schema } from "./ai";

export interface ItemCheck {
    pass: boolean;
    correctness: boolean;
    in_scope: boolean;
    well_formed: boolean;
    teaching_quality: number;
    reasons: string[];
}

const ITEM_CHECK_SCHEMA = Schema.object({
    properties: {
        pass: Schema.boolean(),
        correctness: Schema.boolean(),
        in_scope: Schema.boolean(),
        well_formed: Schema.boolean(),
        teaching_quality: Schema.number(),
        reasons: Schema.array({ items: Schema.string() }),
    },
});

const FAIL_CLOSED: ItemCheck = {
    pass: false,
    correctness: false,
    in_scope: false,
    well_formed: false,
    teaching_quality: 0,
    reasons: ["ai_unavailable"],
};

export async function checkItem(item: {
    stem: string;
    options: Record<string, string>;
    correct: string;
    explanation?: string;
    topic?: string;
}): Promise<ItemCheck> {
    const optionsText = Object.entries(item.options)
        .map(([k, v]) => `${k}: ${v}`)
        .join("\n");

    const prompt = [
        "You are a GMAT Quant item reviewer. Evaluate this multiple-choice question.",
        item.topic ? `Topic: ${item.topic}` : "",
        `Stem: ${item.stem}`,
        `Options:\n${optionsText}`,
        `Marked correct: ${item.correct}`,
        item.explanation ? `Explanation: ${item.explanation}` : "",
        "",
        "Solve the problem yourself, then return JSON with:",
        "- pass: true only if correctness, in_scope, well_formed are all true AND teaching_quality >= 7",
        "- correctness: the marked answer is mathematically correct",
        "- in_scope: appropriate GMAT Quant content",
        "- well_formed: stem and options are clear and unambiguous",
        "- teaching_quality: 0-10 pedagogical quality of the explanation (0 if missing)",
        "- reasons: short strings explaining any failures",
    ]
        .filter(Boolean)
        .join("\n");

    const result = await generateJson<ItemCheck>(prompt, ITEM_CHECK_SCHEMA);
    if (!result.ok) return FAIL_CLOSED;
    return result.value;
}
