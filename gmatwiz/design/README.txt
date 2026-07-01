===============================================================================
GMATWiz — UI DESIGN PROTOTYPE
Design lead deliverable. Static, self-contained HTML/CSS (vanilla JS where
needed). No external CDNs, no fetched web fonts. Prototype only — nothing here
is wired into ts/ or the Anki backend.
===============================================================================

-------------------------------------------------------------------------------
DESIGN THESIS (the 3-sentence version)
-------------------------------------------------------------------------------
GMATWiz is a precision instrument for competence, not a hype machine: it reports
a reading, a margin of error, and has the discipline to say "not yet" when the
data is thin. Where every competitor sells a confident number on day one, our
interface makes the confidence interval the hero and treats abstention as a
designed, dignified state — so the product's honesty rule becomes its look and
feel. Everything else stays quiet and calm, so the one place we spend boldness —
the measured reading — is the thing you remember.

-------------------------------------------------------------------------------
THE SINGLE SIGNATURE ELEMENT — "The Measure"
-------------------------------------------------------------------------------
An engraved scale carrying a confidence BAND and a precise point indicator (the
"needle"), rendered like the dial of a fine measuring tool.

  - The band spans the likely range (e.g. 78–86%). Its WIDTH encodes uncertainty:
    wider = less sure. As evidence accumulates, the band visibly narrows.
  - The needle is the point estimate, with a small mono readout flag.
  - Confidence is encoded redundantly (width + a text label + filled pips), never
    by color alone — so it survives color-blindness and grayscale.
  - ABSTENTION STATE: when data is below threshold, the needle disappears and the
    band becomes a dashed ghost reading "NOT ENOUGH DATA," followed by a checklist
    of exactly which conditions are unmet and the single best next action. The app
    literally refuses to point at a number it can't defend.

The Measure recurs at three scales: the hero of the Dashboard (Memory shown,
Performance + Readiness abstaining), a glance in the top bar, and a miniature
"engraved ruler" inside the wordmark. Tick marks are reused as a structural motif
(daily-goal meter, review progress, coverage map) — and each tick always equals a
real unit (one review, one topic), so structure encodes quantity instead of
decorating it.

-------------------------------------------------------------------------------
THE ONE JUSTIFIED AESTHETIC RISK
-------------------------------------------------------------------------------
Treat the entire app as a calm measuring instrument and SUPPRESS the single big
score that every prep dashboard leads with. The hero is an interval (often an
empty one). The risk: "instrument" can read cold, and an abstaining hero ("No
score yet") is a counterintuitive thing to show first. It is justified because
the product's entire differentiator IS honest measurement under uncertainty
(the honesty rule + abstention gate in PRD §4). We de-risk the coldness with warm
limestone paper, a human serif "tutor" voice, generous spacing, and soft
instrument housings (rounded, never broadsheet-sterile) — so it feels like a
well-made handheld instrument, not a lab readout.

-------------------------------------------------------------------------------
PALETTE  (see tokens.css for the full system + dark theme)
-------------------------------------------------------------------------------
  Limestone  #EAE6DD   canvas — warm, slightly grey (deliberately NOT cream-yellow)
  Graphite   #211F19   text + engravings
  Verdigris  #2E6E5E   THE indicator — needle, primary action, "correct", "go"
  Clay       #A8503F   needs-repair / incorrect — used softly, never punitive
  Brass      #8A6A22   earned mastery glow — rationed warmth (no streaks/confetti)
  Slate      #56666C   uncertainty / abstention / info — calm, never alarming

Verdigris is the only saturated color and is rationed hard. Abstention is slate,
never red: not knowing is honest, not a failure.

-------------------------------------------------------------------------------
TYPOGRAPHY — three voices for the app's three jobs
-------------------------------------------------------------------------------
  Voice    serif  (Georgia / Iowan / Palatino)   the tutor: headlines, questions
  Readout  mono   (SF Mono / Menlo / Consolas)   the instrument: every number,
                                                  range, axis label, timer, eyebrow
  UI       sans   (system-ui)                     quiet chrome: nav, buttons

All three are system-available — no CDNs, safe on the chrome77 webview. The mono
"readout" voice (tabular numerals everywhere a number appears) is the memorable
typographic move and reinforces the measurement identity. The serif is low-
contrast and bookish on purpose — the opposite of the high-contrast Didone
display that AI design defaults to.

-------------------------------------------------------------------------------
HOW IT SERVES THE PRINCIPLES
-------------------------------------------------------------------------------
SPOV 1 — Structure is the product (the app decides what to do next):
  - Today shows exactly ONE next action, with a "Why this:" rationale line (the
    app explains its decision: weakest topic with due reviews). No menu of choices
    to agonize over.
  - The lesson loop renders I-do -> we-do -> you-do as an explicit, ordered
    sequence; the current stage is the only lit one. Numbered/marked structure is
    used ONLY where order genuinely carries meaning (onboarding steps, the loop).
  - The Dashboard's "Best next thing to study" turns measurement straight into
    direction.

SPOV 2 — Application over lessons (toggleable application-first mode):
  - The home screen is a problem to solve, not a lesson to read.
  - The explanation is physically SEALED (a lock motif) until the learner attempts
    — making "explanations appear after an attempt" a tactile, visible rule rather
    than a setting buried in config.
  - A miss flows immediately into the one-prompt error capture, then scheduled
    re-practice.

Anti-grind:
  - The daily goal is a quiet tick-meter with a permanent "Short on time? Set today
    aside" escape. No streaks, no flames, no guilt copy ("...nothing breaks a
    streak, because there isn't one").
  - "Levels" move on application accuracy across spaced sessions, not on hours
    logged — progress is earned competence, not grind.
  - Calm warm palette, low cognitive load, generous whitespace, subtle motion.

The honesty rule (PRD §4):
  - Every reading shows point + range + evidence + what's missing + calibration +
    last-updated + the best next step. See the Dashboard's Memory card.
  - Two of three scores ABSTAIN at MVP, each listing the exact unmet thresholds
    (e.g. Readiness needs coverage >=50% [42%], >=200 reviews [231], >=50 attempts
    [31], ECE <=0.10 [0.04]). Abstention is presented as correct behavior.

-------------------------------------------------------------------------------
SCREENS (one self-contained .html each)
-------------------------------------------------------------------------------
  index.html         Cover / design-system gallery + links to all screens.
  onboarding.html    Onboarding + pretest. Opens on The Measure abstaining (the
                     thesis, immediately). Exam date, weekly time, framed 20-min
                     diagnostic, a real application-first sample item.
  today.html         Today/Home. One dominant next action + rationale; bypassable
                     daily rhythm; quiet secondary rows (due reviews, error log).
  lesson.html        Lesson loop. I-do/we-do/you-do; sealed explanation that
                     unseals only after an attempt; miss -> one-prompt capture.
                     (Vanilla JS handles select -> submit -> reveal.)
  review.html        Distraction-free review. Chrome shrinks to a thin progress
                     rule; show-answer (Space) then calm Again/Hard/Good/Easy.
  error-log.html     Required-review surface, framed kindly. One sharp "why did
                     this happen?" prompt with 5 error types + takeaway; per-item
                     "Repair now"; filter by result/topic.
  dashboard.html     Memory (SHOWN, honest) + Performance (ABSTAIN) + Readiness
                     (ABSTAIN), each a separate Measure; coverage map where each
                     cell is one real Quant leaf topic; "best next thing to study."

Real GMAT Quant (Problem Solving) content is used throughout — quadratic word
problems, number properties, successive percents, roots of a quadratic — not
lorem ipsum, per the brief to ground it in the subject.

-------------------------------------------------------------------------------
QUALITY FLOOR
-------------------------------------------------------------------------------
  - Responsive to ~360px: columns collapse, nav hides, the scale axis + coverage
    grid reflow (see app.css media queries).
  - Visible keyboard focus on every interactive element (conservative :focus ring
    so it works on chrome77, where :focus-visible is absent).
  - prefers-reduced-motion: all transitions/animations reduced to ~0 (the band's
    "measuring" expansion and the unseal animation are the only motion).
  - prefers-color-scheme: dark theme included ("instrument at night").
  - Meaning never by color alone: results carry text labels; confidence carries
    pips + width + text; coverage states carry titles.

-------------------------------------------------------------------------------
chrome77 / es2020 DISCIPLINE (per context.txt — embedded Chromium is pinned low)
-------------------------------------------------------------------------------
Deliberately avoided: clamp()/min()/max(), :has(), container queries, CSS
nesting, color-mix(), backdrop-filter, and flexbox `gap`. Vertical rhythm uses a
".stack > * + *" margin pattern; gaps use CSS grid (supported in chrome77).
JS is tiny, classic, and es2020-safe. This maps cleanly onto the SvelteKit +
SASS-tokens stack later without rework.

-------------------------------------------------------------------------------
LATER: ANKI / SVELTEKIT INTEGRATION (not done here, by instruction)
-------------------------------------------------------------------------------
tokens.css is the source of truth and ends with an ANKI INTEGRATION MAP: how to
alias GMATWiz tokens onto Anki's CSS vars (--canvas -> --paper, --fg -> --ink,
--border -> --line, --canvas-elevated -> --surface, ...) so the app inherits
Anki light/dark for free, while brand colors (verdigris/clay/brass) stay
GMATWiz-owned. The intended path: tokens.css -> ts/lib/sass/_root-vars.scss;
app.css components -> ts/lib/components/*; each screen -> a ts/routes/<page>/.
The prototypes use literal hex so they render with the GMATWiz identity when
opened directly instead of inheriting Anki greys.

-------------------------------------------------------------------------------
HOW TO VIEW
-------------------------------------------------------------------------------
Open index.html in any modern browser (double-click). All assets are local and
relative; everything works offline.
===============================================================================
