# Coach

**Status:** ⬜ Milestone 5 (prompt rewritten in Milestone 1) · **BCT-1:** feedback on behavior, problem solving, action planning

## Problem
Generic chatbots don't know what you actually did this week, and generic advice isn't research-based.

## Mechanics → evidence
| Mechanic | Evidence |
|---|---|
| Coach reads a summary of the user's habits, books and workouts (never raw notes without consent) | MON-1 |
| Weekly review: what went well, where it slipped, one specific adjustment written as an if-then plan | MON-1, HAB-2 |
| After a missed habit: problem-solve the obstacle, shrink the habit, no shaming | HAB-1, MOT-1 |
| Advice limited to the evidence library; coach cites evidence IDs it used, shown as "Sources" | research-backed rule |
| Hard limits: no diagnosis, no medication advice, no extreme diets; points to professionals | safety |

## Implementation notes
- Reuse the existing streaming chat, conversations and LLM fallback chain (Gemini 3.5 Flash → 3.1 Flash-Lite → offline).
- The system prompt receives a compact JSON summary and the list of evidence IDs + one-line findings.
- Offline fallback answers come from the habit templates and evidence summaries.

## Done when
Coach answers using the user's real data, produces a weekly review, and every factual claim shows a source ID.
