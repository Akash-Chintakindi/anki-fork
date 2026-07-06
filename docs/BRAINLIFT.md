# GMATWiz Brainlift

> **Scaffold.** This document is seeded from [`PRD.md`](../PRD.md) §2 (Founding principles) and the learning-science sources cited there. The headings and bullet skeletons are in place; fill in the `TODO (your narrative — per Patrick's outline)` placeholders with your own writing. Nothing below is final prose.

A Brainlift captures the **spiky points of view (SPOVs)** — the non-consensus, defensible beliefs — that drive every product and architecture decision, plus the evidence that earns them.

---

## 0. Purpose

- One paragraph: what this Brainlift is and why the two SPOVs below are the spine of GMATWiz.
- The bet in one sentence: *reuse Anki's learning-structure engine and turn it into a GMAT competence engine.*

> TODO (your narrative — per Patrick's outline)

---

## 1. SPOV 1 — Structure is the product

> "The problem is not content, motivation, or difficulty. The problem is **learning structure**."

- **Claim.** The app — not the student — must decide *what to do next*: when to review, when to slow down, when to advance, and when to simulate the exam.
- **Why it's spiky.** Most prep sells content and motivation; we argue those are commodities and that structure is the scarce, decisive variable.
- **How GMATWiz embodies it.** Pretest → diagnosis → mastery-based plan → adaptive daily session; topic-aware scheduling surfaces weak topics first; the home screen always shows the single next action.

> TODO (your narrative — per Patrick's outline)

**Evidence base (expand each into your own words):**

- **Rosenshine — Principles of Instruction.** Small steps, guided practice, high success rate, systematic review. → TODO (your narrative — per Patrick's outline)
- **Clark / Kirschner / Sweller — why minimally-guided instruction fails; cognitive load.** Novices need strong guidance, not discovery. → TODO (your narrative — per Patrick's outline)
- **Bloom / Guskey — mastery learning.** Don't advance until the current unit is mastered. → TODO (your narrative — per Patrick's outline)
- **Black & Wiliam — formative assessment.** Frequent low-stakes checks that feed back into what to study next. → TODO (your narrative — per Patrick's outline)
- **Gagné — nine events of instruction.** The staged structure of an effective lesson. → TODO (your narrative — per Patrick's outline)

---

## 2. SPOV 2 — Application over lessons

> "'Learning' the content does not mean anything. **Application is everything.** Lessons create confidence; application creates competence."

- **Claim.** A lesson is *incomplete* until the learner has practiced, retrieved after a delay, repaired mistakes, and demonstrated the skill under mixed conditions.
- **Why it's spiky.** Passive lesson consumption feels like progress but manufactures false confidence; we treat it as unfinished work.
- **How GMATWiz embodies it.** Application-first loop (explanations revealed *after* an attempt), spaced retrieval on the FSRS engine, a required error-log repair loop, interleaved mixed sets.
- **Implemented as a toggle.** SPOV 2 (application-first mode) is a feature flag — and the **ablation target** (PRD §14) so the belief can be tested, not just asserted.

> TODO (your narrative — per Patrick's outline)

**Evidence base (expand each into your own words):**

- **Dunlosky et al. 2013 — what works.** Practice testing and distributed practice are top-tier; rereading/highlighting are weak. → TODO (your narrative — per Patrick's outline)
- **Roediger & Karpicke — the testing effect.** Retrieval practice beats restudy for long-term retention. → TODO (your narrative — per Patrick's outline)
- **Karpicke & Roediger (Science) — retrieval for learning.** Retrieval *is* the learning event, not just its measurement. → TODO (your narrative — per Patrick's outline)

---

## 3. Supporting commitments (from the Brainlift)

Skeleton — flesh out each into a short rationale + how it shows up in the build:

- **Diagnostic pretest first**, then a personalized, **mastery-based** plan (2–3 months is the consensus window for a strong score). → TODO (your narrative — per Patrick's outline)
- **Error logs are required, not optional** — capture *why* a miss happened and what to do next time; the app requires periodic review. → TODO (your narrative — per Patrick's outline)
- **Official questions are scarce** — reserve them for late-stage checkpoints; learn on authored/non-official content. → TODO (your narrative — per Patrick's outline)
- **I do → we do → you do** (worked example → guided → independent), high structure first and faded later; ~85% accuracy before independent practice (Archer). → TODO (your narrative — per Patrick's outline)
- **Anti-grind** — autonomous motivation, low cognitive load, one clear next action, bypassable daily goals, sleep/burnout awareness. → TODO (your narrative — per Patrick's outline)

---

## 4. From SPOVs to the build (traceability)

Map each belief to concrete, checkable decisions. Skeleton table — complete the right column:

| Belief | Where it lives in GMATWiz | Notes |
| --- | --- | --- |
| Structure is the product | topic-aware scheduling, plan/pacing engine, "one next action" home | TODO (your narrative — per Patrick's outline) |
| Application over lessons | application-first loop, error-log repair, spaced retrieval | TODO (your narrative — per Patrick's outline) |
| Honesty over vanity metrics | 3 abstaining scores + give-up rule ([`docs/models/`](models/)) | TODO (your narrative — per Patrick's outline) |

---

## 5. How we test the beliefs (not just assert them)

- **Ablation of SPOV 2** — application-first ON vs OFF vs plain Anki; pre-registered hypothesis + primary metric (PRD §14.1). → TODO (your narrative — per Patrick's outline)
- **Paraphrase test** — memory vs performance gap on reworded items (PRD §14.2). → TODO (your narrative — per Patrick's outline)
- **Honesty rule** — every score names its evidence, is checked on held-out data, and beats a simpler baseline (PRD §11). → TODO (your narrative — per Patrick's outline)

---

## 6. Open questions / where I might be wrong

- Steelman the opposite view of each SPOV, then respond.

> TODO (your narrative — per Patrick's outline)

---

## Sources

Fill in full citations (author, title, year, link) for each work referenced above:

- Rosenshine, B. — *Principles of Instruction.* → TODO (your narrative — per Patrick's outline)
- Kirschner, Sweller & Clark — *Why Minimal Guidance During Instruction Does Not Work.* → TODO (your narrative — per Patrick's outline)
- Sweller — *Cognitive Load Theory.* → TODO (your narrative — per Patrick's outline)
- Bloom / Guskey — *Mastery Learning.* → TODO (your narrative — per Patrick's outline)
- Black & Wiliam — *Assessment and Classroom Learning / Inside the Black Box.* → TODO (your narrative — per Patrick's outline)
- Gagné — *The Conditions of Learning (nine events).* → TODO (your narrative — per Patrick's outline)
- Dunlosky et al. (2013) — *Improving Students' Learning With Effective Learning Techniques.* → TODO (your narrative — per Patrick's outline)
- Roediger & Karpicke — *Test-Enhanced Learning* / Karpicke & Roediger (*Science*). → TODO (your narrative — per Patrick's outline)
- Archer & Hughes — *Explicit Instruction.* → TODO (your narrative — per Patrick's outline)
