<!--
  GMAT Wiz - the contextual guide character. Renders a friendly 3D wizard with a
  themed speech bubble that pops in at key moments (first diagnostic, daily login,
  Error Log info, study-before-today). Presentational only: the parent owns WHEN it
  shows and WHAT it says (body is slotted, so rich content keeps the parent's
  styles). Sits fixed bottom-left, above app content; dismissible; idle-floats
  unless the user prefers reduced motion.
-->
<script lang="ts">
    import wizardPng from "./assets/wizard-guide.png";

    interface WizardAction {
        label: string;
        primary?: boolean;
        run: () => void;
    }

    export let title = "";
    export let actions: WizardAction[] = [];
    export let onDismiss: () => void = () => {};
</script>

<div class="wiz" role="dialog" aria-label={title || "GMAT Wiz guide"}>
    <img class="wiz-avatar" src={wizardPng} alt="GMAT Wiz" draggable="false" />
    <div class="wiz-bubble">
        <button class="wiz-close" aria-label="Dismiss" on:click={onDismiss}>&times;</button>
        {#if title}
            <p class="wiz-title">{title}</p>
        {/if}
        <div class="wiz-body">
            <slot />
        </div>
        {#if actions.length}
            <div class="wiz-actions">
                {#each actions as a}
                    <button class="wiz-btn" class:primary={a.primary} on:click={a.run}>
                        {a.label}
                    </button>
                {/each}
            </div>
        {/if}
    </div>
</div>

<style>
    /* Inherits the --gw theme tokens (rendered inside .gw). */
    .wiz {
        position: fixed;
        left: 20px;
        bottom: 20px;
        z-index: 1100;
        display: flex;
        align-items: flex-end;
        max-width: min(460px, calc(100vw - 40px));
        pointer-events: none; /* only the bubble is interactive */
    }
    .wiz-avatar {
        width: 138px;
        height: auto;
        flex: none;
        margin-right: -18px;
        margin-bottom: -4px;
        filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.5));
        animation: wiz-float 4.5s ease-in-out infinite;
        user-select: none;
    }
    .wiz-bubble {
        position: relative;
        pointer-events: auto;
        max-width: 320px;
        margin-bottom: 14px;
        padding: 14px 16px;
        background: var(--paper-2);
        border: 1px solid var(--line-strong);
        border-radius: 16px;
        box-shadow: var(--shadow);
        color: var(--ink);
        animation: wiz-pop 0.24s ease-out both;
    }
    /* little speech-bubble tail pointing back at the wizard */
    .wiz-bubble::before {
        content: "";
        position: absolute;
        left: -7px;
        bottom: 20px;
        width: 13px;
        height: 13px;
        background: var(--paper-2);
        border-left: 1px solid var(--line-strong);
        border-bottom: 1px solid var(--line-strong);
        transform: rotate(45deg);
    }
    .wiz-close {
        position: absolute;
        top: 5px;
        right: 8px;
        border: none;
        background: none;
        color: var(--ink-faint);
        font-size: 19px;
        line-height: 1;
        cursor: pointer;
        padding: 2px 4px;
    }
    .wiz-close:hover {
        color: var(--ink);
    }
    .wiz-title {
        font-family: var(--voice);
        font-size: 15px;
        margin: 0 0 6px;
        padding-right: 18px;
        color: var(--gold);
    }
    .wiz-body {
        font-size: 13px;
        line-height: 1.55;
        color: var(--ink-soft);
    }
    .wiz-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
    }
    .wiz-btn {
        appearance: none;
        border: 1px solid var(--line-strong);
        background: var(--surface);
        color: var(--ink);
        border-radius: 999px;
        padding: 6px 14px;
        font-size: 13px;
        cursor: pointer;
    }
    .wiz-btn:hover {
        border-color: var(--indicator);
    }
    .wiz-btn.primary {
        background: var(--indicator);
        border-color: var(--indicator);
        color: #fff;
    }
    @keyframes wiz-float {
        0%,
        100% {
            transform: translateY(0);
        }
        50% {
            transform: translateY(-8px);
        }
    }
    @keyframes wiz-pop {
        from {
            opacity: 0;
            transform: translateY(8px) scale(0.96);
        }
        to {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .wiz-avatar {
            animation: none;
        }
        .wiz-bubble {
            animation: none;
        }
    }
    @media (max-width: 560px) {
        .wiz {
            left: 12px;
            bottom: 12px;
        }
        .wiz-avatar {
            width: 100px;
            margin-right: -14px;
        }
        .wiz-bubble {
            max-width: 220px;
        }
    }
</style>
