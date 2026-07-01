// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import type { PageLoad } from "./$types";

export interface GmatQuestion {
    stem: string;
    options: Record<string, string>;
    correct: string;
    explanation: string;
    topic: string;
    difficulty: string;
}

// First-slice sample content. Later this loads from the GMAT::Quant deck via the
// shared engine (gmatwiz content -> notetype -> scheduler), per the PRD.
const sampleQuestions: GmatQuestion[] = [
    {
        stem: "If 2x + 3 = 11, what is the value of x?",
        options: { A: "2", B: "3", C: "4", D: "5", E: "6" },
        correct: "C",
        explanation: "Subtract 3 from both sides: 2x = 8. Divide by 2: x = 4.",
        topic: "Algebra \u00b7 Linear equations",
        difficulty: "easy",
    },
    {
        stem: "What is 15% of 80?",
        options: { A: "8", B: "10", C: "12", D: "14", E: "16" },
        correct: "C",
        explanation: "15% = 0.15, and 0.15 \u00d7 80 = 12.",
        topic: "Arithmetic \u00b7 Percents",
        difficulty: "easy",
    },
    {
        stem: "A shirt is discounted 20% to $48. What was the original price?",
        options: { A: "$56", B: "$58", C: "$60", D: "$62", E: "$64" },
        correct: "C",
        explanation: "$48 is 80% of the original. Original = 48 / 0.80 = $60.",
        topic: "Arithmetic \u00b7 Percents",
        difficulty: "medium",
    },
    {
        stem: "If the ratio of a to b is 3:5 and b = 20, what is a?",
        options: { A: "8", B: "10", C: "12", D: "15", E: "18" },
        correct: "C",
        explanation: "a/b = 3/5, so a = (3/5) \u00d7 20 = 12.",
        topic: "Arithmetic \u00b7 Ratios & proportions",
        difficulty: "easy",
    },
    {
        stem: "How many distinct arrangements are there of the letters in TEAM?",
        options: { A: "12", B: "16", C: "20", D: "24", E: "28" },
        correct: "D",
        explanation: "4 distinct letters arrange in 4! = 24 ways.",
        topic: "Arithmetic \u00b7 Counting",
        difficulty: "medium",
    },
    {
        stem: "If x\u00b2 = 49 and x < 0, what is x?",
        options: { A: "-9", B: "-7", C: "7", D: "9", E: "Cannot be determined" },
        correct: "B",
        explanation: "x\u00b2 = 49 gives x = \u00b17. Since x < 0, x = -7.",
        topic: "Algebra \u00b7 Quadratics",
        difficulty: "easy",
    },
];

async function fetchDeckQuestions(): Promise<GmatQuestion[]> {
    try {
        const res = await fetch("/_anki/gmatQuestions", {
            method: "POST",
            headers: { "Content-Type": "application/binary" },
            body: new Uint8Array(),
        });
        if (!res.ok) return [];
        const data = JSON.parse(await res.text());
        return Array.isArray(data?.questions) ? data.questions : [];
    } catch (_e) {
        return [];
    }
}

export const load = (async () => {
    const fromDeck = await fetchDeckQuestions();
    // Fall back to inline samples when the deck is empty or unavailable
    // (e.g. opened in a plain browser without the engine).
    const questions = fromDeck.length > 0 ? fromDeck : sampleQuestions;
    return { questions };
}) satisfies PageLoad;
