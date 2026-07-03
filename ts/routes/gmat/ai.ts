// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Shared Firebase AI Logic (Gemini) plumbing. Generic JSON generation with
// graceful degradation — callers never receive thrown errors.

import { getApps } from "firebase/app";
import { getAI, getGenerativeModel, GoogleAIBackend, Schema } from "firebase/ai";

import { authEnabled } from "./auth";

export { Schema };

export type AiResult<T> = { ok: true; value: T } | { ok: false; reason: string };

const AI_STORAGE_KEY = "gmatwiz.ai";
const DEFAULT_MODEL = "gemini-flash-latest";
const DEFAULT_TIMEOUT_MS = 15_000;

let aiInstance: ReturnType<typeof getAI> | null = null;

function readAiOverride(): boolean | null {
    try {
        const v = localStorage.getItem(AI_STORAGE_KEY);
        if (v === "on") return true;
        if (v === "off") return false;
    } catch (_e) {
        /* private browsing / SSR */
    }
    return null;
}

/** Firebase configured and AI not explicitly turned off in localStorage. */
export function getAiEnabled(): boolean {
    if (!authEnabled || getApps().length === 0) return false;
    const override = readAiOverride();
    if (override !== null) return override;
    return true;
}

export const aiEnabled: boolean = getAiEnabled();

export function setAiEnabled(on: boolean): void {
    try {
        localStorage.setItem(AI_STORAGE_KEY, on ? "on" : "off");
    } catch (_e) {
        /* ignore */
    }
}

function getAiInstance(): ReturnType<typeof getAI> | null {
    if (getApps().length === 0) return null;
    if (!aiInstance) {
        aiInstance = getAI(getApps()[0], { backend: new GoogleAIBackend() });
    }
    return aiInstance;
}

function reasonFromError(err: unknown): string {
    if (err instanceof Error) return err.message || "error";
    return String(err);
}

export async function generateJson<T>(
    prompt: string,
    schema: unknown,
    opts?: { timeoutMs?: number; model?: string },
): Promise<AiResult<T>> {
    if (!getAiEnabled()) {
        return { ok: false, reason: "disabled" };
    }

    const ai = getAiInstance();
    if (!ai) {
        return { ok: false, reason: "unconfigured" };
    }

    const timeoutMs = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const modelName = opts?.model ?? DEFAULT_MODEL;

    try {
        const model = getGenerativeModel(ai, {
            model: modelName,
            generationConfig: {
                responseMimeType: "application/json",
                responseSchema: schema as never,
            },
        });

        const work = (async () => {
            const result = await model.generateContent(prompt);
            const text = result.response.text();
            return JSON.parse(text) as T;
        })();

        const value = await Promise.race([
            work,
            new Promise<never>((_resolve, reject) => {
                setTimeout(() => reject(new Error("timeout")), timeoutMs);
            }),
        ]);

        return { ok: true, value };
    } catch (err) {
        return { ok: false, reason: reasonFromError(err) };
    }
}
