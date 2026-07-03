// Copyright: GMATWiz contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Firebase Cloud Functions (v2) OpenAI proxy for GMATWiz.
//
// The GMATWiz web app renders on desktop and inside an iOS webview. Neither can
// embed an OpenAI key, so every OpenAI call is funneled through this single
// callable Function, which holds the key as a Functions secret. It is a generic
// "generate JSON from a prompt" endpoint shared by BOTH the AI question
// generator and the error-log coach.
//
// LOCKED CALLABLE CONTRACT (the app's ts/routes/gmat/ai.ts is wired to this):
//   name:     gmatGenerate           (Functions v2 onCall)
//   request:  { prompt: string, responseSchema?: object, model?: string }
//   response: { text: string }       (raw model text; JSON string when a schema
//                                      was requested — the client JSON.parses it)
//   failure:  throw HttpsError        (the client degrades to its fixed bank)

import { initializeApp } from "firebase-admin/app";
import * as logger from "firebase-functions/logger";
import { defineSecret, defineString } from "firebase-functions/params";
import { HttpsError, onCall } from "firebase-functions/v2/https";
import OpenAI from "openai";

initializeApp();

// --- Configuration ----------------------------------------------------------

// The OpenAI API key. Stored as a Functions secret so it is NEVER in code, in
// config, or in the deployed bundle. Set it once with:
//   firebase functions:secrets:set OPENAI_API_KEY
const OPENAI_API_KEY = defineSecret("OPENAI_API_KEY");

// Default model. Overridable at deploy time WITHOUT a code change via env/config
// (e.g. `OPENAI_MODEL="gpt-5-mini"` in functions/.env), and per-call via the
// request's `model` field. `gpt-4.1-mini` is a current, cost-effective,
// low-latency model that supports Structured Outputs AND a custom temperature,
// so the knobs below always apply cleanly. It is intentionally NOT a deprecated
// model, and is fully overridable.
const OPENAI_MODEL = defineString("OPENAI_MODEL", { default: "gpt-4.1-mini" });
const FALLBACK_MODEL = "gpt-4.1-mini";

// Reasonable knobs for exam-question generation; modest to bound cost. A lower
// temperature keeps generated GMAT items consistent and well-formed.
const MAX_OUTPUT_TOKENS = 2048;
const TEMPERATURE = 0.7;

// App Check: GMATWiz is designed to use Firebase App Check to keep this key-
// holding endpoint from being called by anything other than the real apps.
// It is NOT enforced by default because the web/iOS clients are not yet wired to
// send App Check tokens (enforcing now would reject every legitimate call and
// AI would silently never work). Once App Check is registered on the clients
// (web reCAPTCHA + iOS App Attest), enable enforcement by setting an env var —
// no code change needed:
//   functions/.env ->  GMAT_ENFORCE_APP_CHECK=true
// TODO(app-check): default this to true after the clients ship App Check tokens.
const ENFORCE_APP_CHECK = process.env.GMAT_ENFORCE_APP_CHECK === "true";

const SYSTEM_PROMPT =
  "You are GMATWiz's content engine. Produce accurate, exam-appropriate GMAT " +
  "material. When a JSON schema is supplied, respond with JSON that conforms to " +
  "it exactly and output nothing else.";

// --- Contract types ---------------------------------------------------------

interface GmatGenerateRequest {
  prompt?: unknown;
  responseSchema?: unknown;
  model?: unknown;
}

interface GmatGenerateResponse {
  text: string;
}

// --- Callable ---------------------------------------------------------------

export const gmatGenerate = onCall(
  {
    secrets: [OPENAI_API_KEY],
    enforceAppCheck: ENFORCE_APP_CHECK,
    region: "us-central1",
    timeoutSeconds: 120,
    memory: "256MiB",
  },
  async (request): Promise<GmatGenerateResponse> => {
    const data = (request.data ?? {}) as GmatGenerateRequest;

    const prompt = typeof data.prompt === "string" ? data.prompt.trim() : "";
    if (!prompt) {
      throw new HttpsError(
        "invalid-argument",
        "`prompt` (a non-empty string) is required.",
      );
    }

    const responseSchema =
      data.responseSchema &&
      typeof data.responseSchema === "object" &&
      !Array.isArray(data.responseSchema)
        ? (data.responseSchema as Record<string, unknown>)
        : undefined;

    // model param (per-call) -> env/config default -> sensible modern default.
    const model =
      (typeof data.model === "string" && data.model.trim()) ||
      OPENAI_MODEL.value() ||
      FALLBACK_MODEL;

    // Construct the client at runtime: the secret is only available then.
    const client = new OpenAI({ apiKey: OPENAI_API_KEY.value() });

    const params: OpenAI.Chat.Completions.ChatCompletionCreateParamsNonStreaming =
      {
        model,
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: prompt },
        ],
        max_completion_tokens: MAX_OUTPUT_TOKENS,
        temperature: TEMPERATURE,
      };

    if (responseSchema) {
      // OpenAI Structured Outputs: guarantees `text` is valid JSON matching the
      // schema, so the client can JSON.parse it safely.
      params.response_format = {
        type: "json_schema",
        json_schema: {
          name: "gmat_response",
          schema: toStrictJsonSchema(responseSchema),
          strict: true,
        },
      };
    }

    let completion: OpenAI.Chat.Completions.ChatCompletion;
    try {
      completion = await createWithFallback(client, params);
    } catch (err) {
      // Surface the real OpenAI cause (status/code/type) under non-`message`
      // keys so the structured logger doesn't swallow them.
      const e = err as { status?: number; code?: unknown; type?: unknown };
      logger.error("gmatGenerate: OpenAI request failed", {
        model,
        openaiStatus: e?.status ?? null,
        openaiCode: e?.code ?? null,
        openaiType: e?.type ?? null,
        detail: errMessage(err),
      });
      // The client treats any failure as "degrade to fixed bank". Include the
      // status/code so it is visible in the callable error too (safe metadata).
      throw new HttpsError(
        "internal",
        `AI generation failed (status ${e?.status ?? "?"}, code ${String(e?.code ?? "?")}).`,
      );
    }

    const text = completion.choices[0]?.message?.content ?? "";
    if (!text) {
      throw new HttpsError("internal", "AI returned an empty response.");
    }

    return { text };
  },
);

// --- Helpers ----------------------------------------------------------------

function errMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

// Some models (notably GPT-5 reasoning models) reject a non-default temperature.
// If the default model is overridden to one of those, retry once without the
// temperature so `model` overrides work out of the box.
async function createWithFallback(
  client: OpenAI,
  params: OpenAI.Chat.Completions.ChatCompletionCreateParamsNonStreaming,
): Promise<OpenAI.Chat.Completions.ChatCompletion> {
  try {
    return await client.chat.completions.create(params);
  } catch (err) {
    if (params.temperature !== undefined && isUnsupportedParam(err, "temperature")) {
      const retry = { ...params };
      delete retry.temperature;
      return await client.chat.completions.create(retry);
    }
    throw err;
  }
}

function isUnsupportedParam(err: unknown, param: string): boolean {
  if (err instanceof OpenAI.APIError) {
    if (err.param === param) return true;
    const msg = (err.message ?? "").toLowerCase();
    return err.status === 400 && msg.includes(param);
  }
  return false;
}

// OpenAI strict Structured Outputs require every object node to set
// `additionalProperties: false` and to list all of its properties in
// `required`. Client-supplied JSON schemas may omit these, so normalize the
// schema recursively. (If a schema uses features strict mode does not support,
// the OpenAI call 400s, we throw, and the client degrades cleanly.)
function toStrictJsonSchema(
  schema: Record<string, unknown>,
): Record<string, unknown> {
  return normalizeSchema(schema) as Record<string, unknown>;
}

function normalizeSchema(node: unknown): unknown {
  if (Array.isArray(node)) {
    return node.map((item) => normalizeSchema(item));
  }
  if (node === null || typeof node !== "object") {
    return node;
  }

  const src = node as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(src)) {
    out[key] = normalizeSchema(value);
  }

  const looksLikeObjectSchema =
    out.type === "object" ||
    (out.properties !== undefined && typeof out.properties === "object");
  if (looksLikeObjectSchema) {
    if (out.additionalProperties === undefined) {
      out.additionalProperties = false;
    }
    const props = out.properties as Record<string, unknown> | undefined;
    if (props && typeof props === "object") {
      out.required = Object.keys(props);
    }
  }
  return out;
}
