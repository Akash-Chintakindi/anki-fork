# GMATWiz Cloud Functions — OpenAI proxy

A single Firebase **callable** Function, `gmatGenerate`, that holds the OpenAI
API key server-side and turns a prompt into JSON. The GMATWiz web app (desktop +
iOS webview) cannot embed an OpenAI key, so all OpenAI traffic goes through here.
The same endpoint serves **both** AI question-generation and the error-log coach
— it is a generic "generate JSON from a prompt" service.

## Callable contract (locked)

- **Name:** `gmatGenerate` (Firebase Functions v2 `onCall`), region `us-central1`.
- **Request `data`:**
  ```ts
  {
    prompt: string,            // required
    responseSchema?: object,   // optional JSON schema -> Structured Outputs
    model?: string             // optional per-call model override
  }
  ```
- **Response:** `{ text: string }` — the model's raw response text. When
  `responseSchema` is supplied, `text` is a JSON string that conforms to the
  schema, so the client can `JSON.parse(text)` safely.
- **Failure:** throws `HttpsError`. The client treats any failure as
  "degrade to the fixed question bank", so nothing crashes.

## Model selection

Resolution order (first match wins):

1. The request's `model` field (per-call override).
2. The `OPENAI_MODEL` env/config value (deploy-time default, no code change).
3. The built-in default: **`gpt-4.1-mini`** — current, cost-effective, supports
   Structured Outputs and a custom temperature.

To change the default without editing code, set `OPENAI_MODEL` (see
`.env.example`). `max_completion_tokens` (2048) and `temperature` (0.7) are tuned
for exam-question generation; if you override the model to a GPT-5 reasoning
model that rejects a custom temperature, the Function automatically retries once
without it.

## The OpenAI key (secret)

The key is read from a Functions **secret** named `OPENAI_API_KEY` via
`defineSecret` — it is never in source, config, or the deployed bundle.

## App Check

`enforceAppCheck` is driven by the `GMAT_ENFORCE_APP_CHECK` env var and defaults
to **off**, because the web/iOS clients do not yet send App Check tokens
(enforcing now would reject every call). Once App Check is registered on the
clients, enable enforcement with no code change:

```
# functions/.env
GMAT_ENFORCE_APP_CHECK=true
```

## Go-live steps (one-time)

> Deployment needs the **Blaze** (pay-as-you-go) plan and the OpenAI secret.

1. **Upgrade the `gmatwiz` Firebase project to Blaze** (Firebase console →
   Usage & billing → Modify plan). Cloud Functions require Blaze.
2. **Set the OpenAI key secret:**
   ```bash
   firebase functions:secrets:set OPENAI_API_KEY
   # paste the sk-... key when prompted
   ```
3. **Install deps and build:**
   ```bash
   cd functions
   npm install
   npm run build      # -> compiles to functions/lib
   ```
4. **Deploy the Function:**
   ```bash
   firebase deploy --only functions
   ```
   (First deploy may prompt to enable required Google Cloud APIs — accept.)

### Optional
- Change the default model: set `OPENAI_MODEL` (see `.env.example`) and redeploy.
- Turn on App Check once clients send tokens: set `GMAT_ENFORCE_APP_CHECK=true`.
- Deploy Firestore rules too: `firebase deploy --only firestore:rules`.
