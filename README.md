<p align="center"><img src="app/frontend/assets/grove-logo.svg" alt="Grove" height="64"></p>

# Grove

> Build the habits behind a healthy, capable life (reading, training, sleep and focus) with methods that research shows work.

**Live demo:** [grove-gh85.onrender.com](https://grove-gh85.onrender.com) · **The research:** [grove-gh85.onrender.com/research.html](https://grove-gh85.onrender.com/research.html)

---

## What it is

Grove is three trackers built on one loop (**plan → do → log → reflect → share**), plus two features that work across all three:

| | What it does | Built on |
|---|---|---|
| **Habits** | "After I [cue], I will [tiny action]" plans, daily check-ins, a 66-day growth arc, "never miss twice", reminders | HAB-1, HAB-2, HAB-3, REM-1 |
| **Books** | Books and reading sessions, notes, recall questions from your own notes on a spaced schedule | LRN-1, LRN-2, LRN-3 |
| **Training** | Lifts and runs, a weekly 150-minute ring, progressive overload, weight as a 7-day trend | FIT-1, FIT-2, WT-1 |
| **Coach** | An AI coach that turns goals into small plans and cites the research behind its advice | MON-1, HAB-2 |
| **Feed** | Milestones from your real logs, shared with followers | SOC-1, MON-1 |

**Research-backed by design.** Every mechanic links to an entry in the [evidence library](docs/research/EVIDENCE.md)
(graded A/B/C), which also powers the in-app "Why this works" panels, the public Research page, and the coach's citations.

**Status:** Milestone 1 (foundation) is live: the new app shell, Today page, research-grounded Coach and Research page.
Habits, Books, Training and Feed ship next. See the [roadmap](docs/ROADMAP.md).

## Docs

- [docs/](docs/README.md): vision, roadmap, decisions, evidence library, feature specs
- [ARCHITECTURE.md](ARCHITECTURE.md): how the code is organized
- [.claude/skills/](.claude/skills/): the `research-backed` and `grove-feature` playbooks

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Database | PostgreSQL (Neon) in production, SQLite locally |
| AI | Gemini (3.5 Flash → 3.1 Flash-Lite fallback) or any OpenAI-compatible API, with offline answers |
| Frontend | Vanilla HTML, CSS and ES modules, no build step |
| Auth | Built-in email/password (scrypt + signed tokens) or AWS Cognito; temporary guest sessions |
| Hosting | Render (one service serves the API and the site), GitHub Actions keep-awake ping |

## Run it locally

Requires Python 3.12.

```bash
git clone https://github.com/Imonuil12/grove.git && cd grove
python3.12 -m venv venv && source venv/bin/activate
pip install -r app/backend/requirements.txt
cp .env.example .env            # optional: add GEMINI_API_KEY for AI answers
python app/backend/manage_db.py upgrade
cd app/backend && uvicorn main:app --port 8000
```

Open http://127.0.0.1:8000. API docs are at `/docs`. Without an AI key, the coach answers from built-in,
research-cited replies.

Tests: `cd app/backend && python -m pytest -q`

## Authentication

Picked automatically by `GET /auth/config`:

- **Built-in accounts (default)** while `COGNITO_USER_POOL_ID` is empty: scrypt-hashed passwords, HS256 tokens signed
  with `JWT_SECRET`, rate-limited sign-up and login.
- **AWS Cognito** when `COGNITO_REGION`, `COGNITO_USER_POOL_ID` and `COGNITO_CLIENT_ID` are set.
- **Guests** get an in-memory session that ends when the tab closes.

## Deploy (Render + Neon, free)

1. Create a Postgres database at [neon.tech](https://neon.tech).
2. In [Render](https://render.com) choose **New → Blueprint** and select this repo. `render.yaml` creates the service
   and generates `JWT_SECRET` and `SESSION_ENCRYPTION_KEY`.
3. Set `DATABASE_URL` (the Neon connection string) and optionally `GEMINI_API_KEY`, then deploy.

Each start runs `manage_db.py upgrade`. With `APP_ENV=production` the app refuses to start without its secrets and
rejects unsigned tokens. `GET /healthz` is the health check.

## Configuration

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres or SQLite URL; defaults to `app/backend/chatbot.db` |
| `JWT_SECRET`, `SESSION_ENCRYPTION_KEY` | Required in production |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini key; model is a comma-separated fallback list (default `gemini-3.5-flash,gemini-3.1-flash-lite`) |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | Any OpenAI-compatible provider (OpenAI, Groq, Ollama) |
| `COGNITO_*` | Optional AWS Cognito instead of built-in accounts |

## License

All rights reserved for now. A license will be chosen before public release.
