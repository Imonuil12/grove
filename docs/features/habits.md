# Habits

**Status:** ⬜ Milestone 2 · **Behavior change techniques (BCT-1):** goal setting, action planning, self-monitoring, prompts/cues

## Problem
People set vague goals ("read more"), rely on willpower, and quit after breaking a streak.

## Mechanics → evidence
| Mechanic | Evidence |
|---|---|
| Every habit is written as "After I [cue], I will [tiny action] at [place/time]" | HAB-2, HAB-3 |
| Start tiny (2 pages, 2 push-ups); suggest growing it once check-ins are steady | HAB-4 (C, design input) |
| One-tap daily check-in, with an optional "how automatic did it feel?" 1–5 rating | MON-1, HAB-1 |
| 66-day growth arc per habit, drawn as a branch of the bonsai | HAB-1 |
| "Never miss twice": one missed day is shown as normal; two in a row prompts a gentle restart plan | HAB-1, MOT-1 |
| Reminder at the planned time (Web Push + in-app) | REM-1, HAB-3 |
| Templates: read, meditate, sleep by a set time, walk, drink water, stretch, journal | SLP-1, MND-1, FIT-1 |

## User stories
- I create a habit from a template or from scratch, filling in cue, action, place and time.
- Each day I see today's habits on **Today** and check them off in one tap.
- I see how close each habit is to "automatic" along the 66-day arc.
- I get a notification at my planned time if I haven't checked in.

## Data
- `habits`: id, user_id, title, domain (mind/body/craft/spirit/character), cue, action, place, time_of_day,
  days_of_week, tiny_version, target_version, template_key, created_at, archived_at
- `habit_checkins`: id, habit_id, date, done (bool), automaticity (1–5, nullable), note
- `reminder_subscriptions`: id, user_id, push_endpoint, keys (encrypted), created_at

## API (sketch)
`GET/POST /habits` · `PATCH/DELETE /habits/{id}` · `POST /habits/{id}/checkins` · `GET /habits/{id}/arc` ·
`POST /reminders/subscribe`

## Out of scope (v1)
Email reminders, habit sharing between users.

## Done when
A user can create a habit with a plan, check in daily, see the arc, and receive a reminder; tests cover the
"never miss twice" logic; the evidence IDs above appear in the in-app "Why this works" panel.
