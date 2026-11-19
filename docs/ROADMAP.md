# Roadmap

Every milestone ships to the live site on its own. Status: ✅ done · 🚧 in progress · ⬜ not started.

## ✅ Phase 0: Own the code and deploy
- Remove company ownership, rebrand to Grove, built-in accounts, free AI provider, Postgres support
- Live at https://grove-gh85.onrender.com (Render + Neon, kept awake by a scheduled ping)

## ✅ Milestone 1: Foundation (2026-11-18)
Goal: the medical product is gone and the new app shell is in place.
- [x] Remove medication content: drug lessons, safety warnings, drug and condition tables, medical intake
- [x] New navigation: Today · Habits · Books · Training · Coach · Feed · Profile (sidebar on desktop, tab bar on phones)
- [x] Today page with empty states that point to each tracker
- [x] Database reset to a Grove baseline (accounts kept); tracker tables arrive with each tracker (see DECISIONS)
- [x] Coach rebuilt: research-grounded prompt, cited sources, follow-up suggestions, research-cited offline answers
- [x] New landing page and a public Research page generated from the evidence library
- [x] Upcoming trackers show what's coming, the research behind it, and a coach shortcut

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
