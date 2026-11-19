# Training

**Status:** ⬜ Milestone 4 · **BCT-1:** goal setting, self-monitoring, graded tasks, feedback on behavior

## Problem
People train without a plan, can't tell if they're progressing, and get discouraged by daily weight swings.

## Mechanics → evidence
| Mechanic | Evidence |
|---|---|
| Weekly ring: 150 active minutes + 2 strength days (user can raise it) | FIT-1 |
| Strength log: exercise, sets, reps, weight; personal records | MON-1 |
| "Add weight" suggestion when target reps are exceeded | FIT-2 |
| Runs and cardio: distance, time, pace; beginner run/walk plan | FIT-1, RUN-1 (C) |
| Weight log shown as a 7-day average trend | WT-1 |
| Optional daily calories and protein (quick log); protein target ~1.6 g/kg for strength trainees | FIT-3 |
| "Why this matters for your brain" note on cardio | COG-1 (word carefully) |

## Safety
Not medical advice. No calorie target below public guidance; no targets for users who say they are under 18.
Show a "talk to a professional" note for injuries, pregnancy, or medical conditions.

## Data
- `workouts`: id, user_id, date, kind (strength/run/cardio/mobility), duration_min, perceived_effort (1–10), note
- `workout_sets`: id, workout_id, exercise, set_no, reps, weight_kg
- `cardio_entries`: id, workout_id, distance_km, duration_sec
- `body_metrics`: id, user_id, date, weight_kg, calories, protein_g (all optional, encrypted)

## API (sketch)
`GET/POST /workouts` · `GET /workouts/summary?week=` · `GET /exercises/{name}/history` · `GET/POST /body-metrics` ·
`GET /body-metrics/trend`

## Done when
Log a lift and a run, see the weekly ring, PRs and the weight trend; overload suggestion and trend math have tests.
