# Grove architecture

How the code is organized. For *what* we build and *why*, see [docs/](docs/README.md).

## Overview

```
Browser (static HTML + ES modules)
   │  same origin
   ▼
FastAPI app (app/backend/main.py)
   ├── /auth/*        built-in accounts, Cognito config, guest sessions
   ├── /coach/*       conversations + streaming replies (coach.py)
   ├── /me, /healthz
   └── /              static site (app/frontend), mounted last
        │
        ├── SQLAlchemy ──► Postgres (Neon) in production · SQLite locally
        └── llm.py ─────► Gemini or OpenAI-compatible API · offline answers if none
```

One service serves both the API and the website, so there's no CORS setup and one deploy.

## Backend (`app/backend`)

| File | Role |
|---|---|
| `main.py` | App setup, production config checks, auth (local tokens, Cognito, Turnstile), guest sessions, router wiring, static mount |
| `coach.py` | Coach API: list/read/delete conversations, `POST /coach/stream` (NDJSON events `meta`, `delta`, `done`) |
| `coach_prompt.py` | System prompt, evidence grounding, citation extraction, offline research-cited answers (pure functions) |
| `llm.py` | Provider chain: OpenAI-compatible → Gemini model list → none; streaming and one-shot |
| `auth.py`, `local_auth.py` | Token verification; scrypt passwords and HS256 tokens for built-in accounts |
| `encryption.py` | Fernet encryption for sensitive text (coach messages today; notes and body metrics later) |
| `models.py` | `users`, `local_credentials`, `coach_conversations`, `coach_messages`. Trackers add tables in their milestones |
| `manage_db.py` | Migrations; converts pre-Grove databases once (keeps accounts, drops the rest) |
| `account_cleanup.py` | Delete an account and everything it owns |

**Identity.** Every protected endpoint depends on `require_authenticated_user`, which returns the account email or
`guest_<token>`. Guest data lives in the in-memory guest session (one worker; it disappears on restart by design).

**Coach flow.** The request's conversation history (last 12 turns) and a system prompt built from the evidence library
go to `llm.stream`. The reply streams to the browser; the follow-up suggestions block (`<<<FOLLOWUPS>>>`) is held back,
then sent in `done` with `sources` (evidence IDs the reply cited, validated against the library). Signed-in messages
are stored encrypted.

## Evidence pipeline

```
docs/research/EVIDENCE.md ──scripts/build_evidence.py──► app/frontend/data/evidence.json
                                                          ├── research.html (public Research page)
                                                          ├── core.js renderWhy() ("Why this works" panels)
                                                          └── coach_prompt.py (grade A/B entries in the system prompt)
```
`test_evidence.py` fails if the JSON is stale or an entry is incomplete.

## Frontend (`app/frontend`)

| File | Role |
|---|---|
| `core.js` | API client (auth headers, 401 handling), identity helpers, safe Markdown, evidence loader, `renderWhy`, icons |
| `shell.js` | App shell: sidebar on desktop, tab bar on phones, top bar; sign-in guard |
| `app.css` | Design tokens (forest `#16271e`, leaf `#2f855a`, sun `#b0651e`), light/dark themes, all components |
| `index.html` | Public landing page |
| `research.html` | Public evidence library |
| `today.html`, `coach.html`, `profile.html` | App pages |
| `habits.html`, `books.html`, `training.html`, `feed.html` + `preview.js` | Upcoming trackers: what's coming, the research, and a coach shortcut |
| `login.html`, `signup.html`, `confirm.html`, `auth/` | Sign-in (built-in or Cognito) |

## Database

Alembic migrations live in `alembic/versions/` (baseline `g001`). Fresh databases, SQLite or Postgres, are created by
running the migrations. Change the schema by editing `models.py`, adding a migration, and checking `alembic check`
reports no drift.

## Deploy

`render.yaml` defines the Render web service. Start command: `manage_db.py upgrade`, then uvicorn on `$PORT`.
`.github/workflows/keep-awake.yml` pings `/healthz` every 10 minutes so the free instance doesn't sleep.
