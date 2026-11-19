# Roadmap

Every milestone ships to the live site on its own. Status: ✅ done · 🚧 in progress · ⬜ not started.

## ✅ Phase 0: Own the code and deploy
- Remove company ownership, rebrand to Grove, built-in accounts, free AI provider, Postgres support
- Live at https://grove-gh85.onrender.com (Render + Neon, kept awake by a scheduled ping)

## 🚧 Milestone 1: Foundation
Goal: the medical product is gone and the new app shell is in place.
- [ ] Remove medication content: drug lessons, safety warnings, drug and condition tables, medical intake
- [ ] New navigation: Today · Habits · Books · Training · Coach · Feed · Profile
- [ ] Today page (empty states that point to each tracker)
- [ ] New database tables for habits, check-ins, books, reading sessions, notes, workouts, body metrics
- [ ] Coach prompt rewritten as a general growth coach (full rewrite in Milestone 5)
- [ ] Landing page and About rewritten for the new agenda, with a "The research" section
- **Done when:** no medical wording anywhere, every nav item opens a real page, tests pass, deployed.

## ⬜ Milestone 2: Habits + reminders → [features/habits.md](features/habits.md)
## ⬜ Milestone 3: Books → [features/books.md](features/books.md)
## ⬜ Milestone 4: Training + body metrics → [features/training.md](features/training.md)
## ⬜ Milestone 5: Coach rewrite + weekly review → [features/coach.md](features/coach.md)
## ⬜ Milestone 6: Feed → [features/feed.md](features/feed.md)

## Later (not scheduled)
- Food database search (USDA FoodData Central)
- Email reminders
- Native-feeling mobile install (PWA polish)
- Public "Research" page generated from the evidence library
