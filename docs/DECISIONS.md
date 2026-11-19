# Decisions

Newest first. Each entry: date, decision, why, and what it affects. Reverse a decision with a new entry, don't edit old ones.

## 2026-11-18: Fresh schema baseline; tracker tables ship with their tracker
- **Decision:** The old medication migrations were replaced by one Grove baseline (`g001`). Existing databases are
  converted once: accounts and passwords are kept, all medication tables are dropped. Habits, Books, Training and
  Feed tables are added in their own milestones instead of up front.
- **Why:** Designing tables before their feature is built leads to churn; one migration per feature keeps history clear.

## 2026-11-18: Upcoming trackers ship as research previews
- **Decision:** Until a tracker is built, its page shows what's coming, its evidence, and a button that asks the coach
  for a plan. No fake data.
- **Why:** Every nav item works on day one, and the demo stays honest about what exists.

## 2026-11-18: Product redesign around Habits, Books, Training
- **Decision:** Remove the medication-education product entirely. Grove is three trackers (Habits, Books,
  Training) plus a Coach and a Feed, as described in [VISION.md](VISION.md).
- **Why:** The agenda is habit development and whole-person growth, not medication education.
- **Affects:** All pages, the curriculum and drug tables, the chat prompt, and the old lesson engine
  (removed; Books builds its own recall questions).

## 2026-11-18: Everything we build is research-backed
- **Decision:** Every user-facing mechanic links to an evidence ID, or is labeled a product choice.
  Marketing claims may only use findings graded A or B in the evidence library.
- **Why:** Real impact, and trust when we advertise. Users can see the research behind the app.
- **Affects:** Every feature spec, all marketing and in-app copy. Enforced by the `research-backed` skill.

## 2026-11-18: Calories are a quick log, not a food database (v1)
- **Decision:** Users type calories and protein for the day (or per meal). No food search.
- **Why:** A food database (for example USDA FoodData Central) is a large project. Quick logging delivers the
  self-monitoring benefit now; we can add search later.

## 2026-11-18: Feed is followers-only by default
- **Decision:** Posts are visible to followers. Public profiles are opt-in.
- **Why:** Accountability works through people you know (see SOC-1) and private-by-default protects users.

## 2026-11-18: Reminders use browser notifications first
- **Decision:** Web Push notifications plus in-app reminders. Email reminders later.
- **Why:** Free and needs no third-party account. Limitation: on iPhone it works only when Grove is added to the home screen.

## 2026-11-18: Keep both Focused (bonsai) and Game (XP) modes
- **Decision:** Users choose a calm view or a playful one. Both read the same data.
- **Why:** Gamification helps some users and not others (see GAM-1); letting people choose respects autonomy (MOT-1).

## 2026-11-18: Hosting stays on Render, kept awake by a scheduled ping
- **Decision:** Render free web service + Neon Postgres; a GitHub Actions job pings `/healthz` every 10 minutes.
- **Why:** Moving to Vercel would require moving guest sessions and rate limits out of memory. Revisit if traffic grows.
