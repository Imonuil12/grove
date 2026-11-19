---
name: grove-feature
description: The build playbook for Grove. Use when starting, implementing or finishing any Grove feature or milestone (Habits, Books, Training, Coach, Feed, Today, or new ones), so the work follows the spec, stays research-backed, is tested, documented and deployed to the live site.
---

# Building a Grove feature

Grove is built in milestones (`docs/ROADMAP.md`). Each one ships to the live site on its own.

## 1. Before writing code
1. Read `docs/VISION.md`, `docs/ROADMAP.md`, and the feature spec in `docs/features/<feature>.md`.
   If there is no spec, write one first (copy the structure of `docs/features/habits.md`).
2. Apply the `research-backed` skill: every mechanic has an evidence ID or is labeled "product choice."
3. Check `docs/DECISIONS.md` for decisions that constrain the work (privacy defaults, reminders, hosting).
4. Mark the milestone 🚧 in `ROADMAP.md`.

## 2. Backend (`app/backend`)
- Models go in `models.py`; every schema change gets an Alembic migration in `alembic/versions/`
  (number it after the latest). Fresh Postgres databases are built from the models, so keep them in sync
  (`alembic check` must show no drift).
- Sensitive free text (notes, journal entries, body metrics) is encrypted with `encryption.py`.
- Endpoints go in `main.py` (or a new router module once a feature is large), protected with
  `require_authenticated_user`. Guests may use features; their data lives only for the guest session.
- Put evidence-based rules (arc length, "never miss twice", spaced intervals, overload) in small pure
  functions with an evidence-ID comment, so they are easy to test.

## 3. Frontend (`app/frontend`)
- Vanilla HTML/CSS/JS. Reuse `style.css` tokens: forest `#16271e`, leaf `#2f855a`, sun amber `#b0651e`.
- API calls use the shared `BASE_URL` logic in `script.js` (same origin in production).
- Every tracker page has: an empty state that tells the user the first step, and a "Why this works" panel
  listing evidence IDs with plain-language findings.
- Check the page at phone width (375px) and in both Focused and Game modes.

## 4. Tests
- Add pytest tests next to the code (`app/backend/test_<feature>.py`) for the evidence-based logic and the API.
- Run all tests: `cd app/backend && ../../venv/bin/python -m pytest -q`.

## 5. Verify in the browser
Run locally (`.claude/launch.json` has `backend` on port 8001, serving the frontend), click through the
feature, and check the console for errors.

## 6. Ship
1. Update `ROADMAP.md` (tick items), `DECISIONS.md` (new decisions), the spec status, and `ARCHITECTURE.md`
   if the structure changed.
2. Commit with a clear message, push to `main`. Render deploys automatically.
3. Confirm https://grove-gh85.onrender.com/healthz and click through the feature on the live site.
