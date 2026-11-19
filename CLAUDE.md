# Grove

A research-backed habit and personal-growth platform: Habits, Books and Training, with an AI Coach and a Feed.
Live at https://grove-gh85.onrender.com. Solo portfolio project.

## Start here
- `docs/README.md`: index of vision, roadmap, decisions, evidence library and feature specs
- `.claude/skills/research-backed`: every mechanic and claim must be backed by `docs/research/EVIDENCE.md`
- `.claude/skills/grove-feature`: the build checklist from spec to live site

## Rules
- Research first: no user-facing mechanic without an evidence ID or a "product choice" label. Never invent citations.
- Update the docs in the same change as the code (roadmap, decisions, specs).
- Never commit `.env` or secrets. Never push the old pre-Grove history.
- Run tests: `cd app/backend && ../../venv/bin/python -m pytest -q`
- Pushing to `main` deploys to Render automatically.
