<!--
Copyright: GMATWiz contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

Application-first practice loop (PRD SPOV 2): the learner commits to an answer
BEFORE any explanation is revealed. Styling follows the GMATWiz "instrument"
design (gmatwiz/design): limestone surface, graphite ink, rationed verdigris.
Conservative CSS for the chrome77/es2020 webview (no gap/clamp/:has).
-->
<script lang="ts">
    import type { GmatQuestion } from "./+page";

    export let questions: GmatQuestion[] = [];

    let index = 0;
    let selected: string | null = null;
    let revealed = false;
    let answered = 0;
    let correctCount = 0;

    $: current = questions[index];
    $: optionEntries = current ? Object.entries(current.options) : [];
    $: isCorrect = revealed && selected === current.correct;
    $: accuracy = answered > 0 ? Math.round((correctCount / answered) * 100) : 0;

    function choose(key: string): void {
        if (revealed) return;
        selected = key;
    }

    function commit(): void {
        if (selected === null || revealed) return;
        revealed = true;
        answered += 1;
        if (selected === current.correct) correctCount += 1;
    }

    function next(): void {
        index = index < questions.length - 1 ? index + 1 : 0;
        selected = null;
        revealed = false;
    }

    function optionState(key: string): string {
        if (!revealed) return selected === key ? "is-selected" : "";
        if (key === current.correct) return "is-correct";
        if (key === selected) return "is-wrong";
        return "is-muted";
    }
</script>

<div class="gw">
    <header class="gw-top">
        <div class="gw-brand">GMATWiz <span class="gw-brand-sub">Practice</span></div>
        <div class="gw-meter" aria-label="Session progress">
            <span class="gw-meter-n">{answered}</span>
            <span class="gw-meter-l">answered</span>
            {#if answered > 0}
                <span class="gw-meter-dot">&middot;</span>
                <span class="gw-meter-n">{accuracy}%</span>
                <span class="gw-meter-l">accurate</span>
            {/if}
        </div>
    </header>

    {#if current}
        <main class="gw-card">
            <div class="gw-eyebrow">
                <span>{current.topic}</span>
                <span class="gw-diff gw-diff-{current.difficulty}">{current.difficulty}</span>
            </div>

            <h1 class="gw-stem">{current.stem}</h1>

            <ul class="gw-options">
                {#each optionEntries as [key, value]}
                    <li>
                        <button
                            type="button"
                            class="gw-option {optionState(key)}"
                            aria-pressed={selected === key}
                            disabled={revealed}
                            on:click={() => choose(key)}
                        >
                            <span class="gw-key">{key}</span>
                            <span class="gw-val">{value}</span>
                        </button>
                    </li>
                {/each}
            </ul>

            {#if !revealed}
                <div class="gw-actions">
                    <button
                        type="button"
                        class="gw-primary"
                        disabled={selected === null}
                        on:click={commit}
                    >
                        Commit answer
                    </button>
                    <p class="gw-seal">Explanation stays sealed until you commit.</p>
                </div>
            {:else}
                <section class="gw-feedback {isCorrect ? 'is-correct' : 'is-wrong'}">
                    <div class="gw-verdict">
                        {isCorrect ? "Correct" : "Not yet"}
                        <span class="gw-answer">Answer: {current.correct}</span>
                    </div>
                    <p class="gw-explain">{current.explanation}</p>
                </section>
                <div class="gw-actions">
                    <button type="button" class="gw-primary" on:click={next}>
                        Next question
                    </button>
                </div>
            {/if}
        </main>
    {:else}
        <main class="gw-card">
            <p>No questions loaded.</p>
        </main>
    {/if}
</div>

<style>
    .gw {
        --paper: #eae6dd;
        --surface: #f4f1e9;
        --ink: #211f19;
        --ink-soft: #5f5849;
        --ink-faint: #8c8472;
        --indicator: #2e6e5e;
        --indicator-ink: #245a4b;
        --indicator-tint: #dce7e1;
        --clay-ink: #8c4233;
        --clay-tint: #f0ded7;
        --brass-tint: #ece0c2;
        --line: #d3cbbc;
        --line-strong: #bcb2a0;

        box-sizing: border-box;
        min-height: 100vh;
        margin: 0;
        padding: 24px 20px 56px;
        background: var(--paper);
        color: var(--ink);
        font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
    }
    .gw *,
    .gw *::before,
    .gw *::after {
        box-sizing: border-box;
    }

    .gw-top {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        max-width: 640px;
        margin: 0 auto 18px;
    }
    .gw-brand {
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .gw-brand-sub {
        color: var(--ink-faint);
        font-weight: 500;
    }
    .gw-meter-n {
        font-weight: 700;
        color: var(--indicator-ink);
    }
    .gw-meter-l {
        color: var(--ink-faint);
        font-size: 13px;
        margin-left: 3px;
    }
    .gw-meter-dot {
        color: var(--line-strong);
        margin: 0 6px;
    }

    .gw-card {
        max-width: 640px;
        margin: 0 auto;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 22px 22px 24px;
        box-shadow: 0 6px 18px rgba(33, 31, 25, 0.08);
    }

    .gw-eyebrow {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 13px;
        color: var(--ink-soft);
        margin-bottom: 12px;
    }
    .gw-diff {
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid var(--line-strong);
        color: var(--ink-soft);
    }
    .gw-diff-easy { background: var(--indicator-tint); }
    .gw-diff-medium { background: var(--brass-tint); }
    .gw-diff-hard { background: var(--clay-tint); }

    .gw-stem {
        font-family: Georgia, "Times New Roman", serif;
        font-size: 22px;
        line-height: 1.4;
        font-weight: 600;
        margin: 0 0 18px;
    }

    .gw-options {
        list-style: none;
        margin: 0 0 18px;
        padding: 0;
    }
    .gw-options li {
        margin-bottom: 10px;
    }
    .gw-option {
        display: flex;
        align-items: center;
        width: 100%;
        text-align: left;
        padding: 12px 14px;
        border: 1px solid var(--line-strong);
        border-radius: 10px;
        background: var(--paper);
        color: var(--ink);
        font-size: 16px;
        cursor: pointer;
        transition: border-color 0.12s ease, background 0.12s ease;
    }
    .gw-option:hover:not(:disabled) {
        border-color: var(--indicator);
    }
    .gw-option:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }
    .gw-option:disabled {
        cursor: default;
    }
    .gw-key {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        margin-right: 12px;
        border-radius: 6px;
        border: 1px solid var(--line-strong);
        font-weight: 700;
        font-size: 13px;
        color: var(--ink-soft);
        background: var(--surface);
    }
    .gw-option.is-selected {
        border-color: var(--indicator);
        background: var(--indicator-tint);
    }
    .gw-option.is-correct {
        border-color: var(--indicator);
        background: var(--indicator-tint);
    }
    .gw-option.is-correct .gw-key {
        background: var(--indicator);
        color: #fff;
        border-color: var(--indicator);
    }
    .gw-option.is-wrong {
        border-color: var(--clay-ink);
        background: var(--clay-tint);
    }
    .gw-option.is-muted {
        opacity: 0.6;
    }

    .gw-actions {
        margin-top: 6px;
    }
    .gw-primary {
        appearance: none;
        border: 1px solid var(--indicator-ink);
        background: var(--indicator);
        color: #fff;
        font-size: 15px;
        font-weight: 600;
        padding: 11px 20px;
        border-radius: 10px;
        cursor: pointer;
    }
    .gw-primary:hover:not(:disabled) {
        background: var(--indicator-ink);
    }
    .gw-primary:focus-visible {
        outline: 2px solid var(--indicator-ink);
        outline-offset: 2px;
    }
    .gw-primary:disabled {
        opacity: 0.45;
        cursor: default;
    }
    .gw-seal {
        margin: 10px 2px 0;
        font-size: 13px;
        color: var(--ink-faint);
    }

    .gw-feedback {
        border-radius: 10px;
        padding: 14px 16px;
        margin: 4px 0 16px;
        border: 1px solid var(--line-strong);
    }
    .gw-feedback.is-correct {
        background: var(--indicator-tint);
        border-color: var(--indicator);
    }
    .gw-feedback.is-wrong {
        background: var(--clay-tint);
        border-color: var(--clay-ink);
    }
    .gw-verdict {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .gw-answer {
        font-weight: 600;
        font-size: 13px;
        color: var(--ink-soft);
    }
    .gw-explain {
        margin: 0;
        line-height: 1.5;
        color: var(--ink);
    }

    @media (prefers-reduced-motion: reduce) {
        .gw-option,
        .gw-primary {
            transition: none;
        }
    }
</style>
