// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Shared AI plumbing. Generic JSON generation with graceful degradation —
// callers never receive thrown errors.
//
// The Gemini call is proxied through the `gmatGenerate` Firebase callable
// (Functions v2, us-central1) so the API key stays server-side and both the
// desktop and mobile builds share one path. The public interface (generateJson,
// getAiEnabled/setAiEnabled, aiEnabled, Schema) is unchanged, so coach.ts,
// aiChecker.ts, and the app shell keep working without edits.

import { getApps } from "firebase/app";
// `Schema` is a plain client-side schema BUILDER (no network); callers use it to
// declare a responseSchema which we forward to the callable untouched.
import { Schema } from "firebase/ai";
import { getFunctions, httpsCallable } from "firebase/functions";

import { authEnabled } from "./auth";

export { Schema };

export type AiResult<T> = { ok: true; value: T } | { ok: false; reason: string };

const AI_STORAGE_KEY = "gmatwiz.ai";
const FUNCTIONS_REGION = "us-central1";
const DEFAULT_TIMEOUT_MS = 20_000;

/** Request/response contract of the deployed `gmatGenerate` callable. */
interface GmatGenerateRequest {
    prompt: string;
    responseSchema?: unknown;
    model?: string;
}
interface GmatGenerateResponse {
    text: string;
}

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

/**
 * AI is OFF by default (it needs a Blaze project + the Firebase AI setup). It
 * turns on only when the user explicitly enables it — the localStorage override
 * (mirrored to synced config). Also requires Firebase to be configured so no
 * network call is ever attempted when the app runs auth-less.
 */
export function getAiEnabled(): boolean {
    if (!authEnabled || getApps().length === 0) return false;
    return readAiOverride() === true;
}

export const aiEnabled: boolean = getAiEnabled();

export function setAiEnabled(on: boolean): void {
    try {
        localStorage.setItem(AI_STORAGE_KEY, on ? "on" : "off");
    } catch (_e) {
        /* ignore */
    }
}

function reasonFromError(err: unknown): string {
    if (err instanceof Error) return err.message || "error";
    return String(err);
}

/**
 * The callable proxies to OpenAI, which wants a plain JSON Schema object. A
 * `firebase/ai` Schema instance carries that shape behind a `toJSON()`, so
 * normalize before sending; plain objects (or undefined) pass through untouched.
 */
function normalizeSchema(schema: unknown): unknown {
    const maybe = schema as { toJSON?: () => unknown } | null | undefined;
    if (maybe && typeof maybe.toJSON === "function") {
        try {
            return maybe.toJSON();
        } catch (_e) {
            return schema;
        }
    }
    return schema;
}

export async function generateJson<T>(
    prompt: string,
    schema: unknown,
    opts?: { timeoutMs?: number; model?: string },
): Promise<AiResult<T>> {
    if (!getAiEnabled()) {
        return { ok: false, reason: "disabled" };
    }

    const apps = getApps();
    if (apps.length === 0) {
        return { ok: false, reason: "unconfigured" };
    }

    const timeoutMs = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;

    try {
        const fns = getFunctions(apps[0], FUNCTIONS_REGION);
        const callable = httpsCallable<GmatGenerateRequest, GmatGenerateResponse>(
            fns,
            "gmatGenerate",
        );

        const work = (async () => {
            const res = await callable({
                prompt,
                responseSchema: normalizeSchema(schema),
                model: opts?.model,
            });
            const text = res.data?.text ?? "";
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
