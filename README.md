<p align="center"><img src="app/frontend/assets/grove-logo.svg" alt="Grove" height="64"></p>

# Grove

> Grow every part of yourself: mind, body, craft and spirit. Learn what actually works, practice it daily, measure your progress, and share the wins.

**Live demo:** [grove-gh85.onrender.com](https://grove-gh85.onrender.com) (free hosting: the first visit after a quiet spell can take about a minute to wake up)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Authentication](#authentication)
- [Deploy](#deploy)
- [AI provider](#ai-provider)
- [API Reference](#api-reference)
- [Learning Archetypes](#learning-archetypes)
- [Database Schema](#database-schema)
- [Configuration](#configuration)

---

## Overview

Grove is a personal growth platform. It pairs an **adaptive learning engine** (a short check-in finds what you already know, then lessons fill the gaps) with an **AI coach** that adapts to how you like to learn.

**Status:** in active development toward version 1.0. The branding and look are Grove; the lesson content is still the original health and medication curriculum, which the next phase replaces with growth domains (Mind, Body, Craft, Reason, Spirit, Character), daily practices, benchmarks and a social feed for sharing achievements.

What already works:
- A **structured lesson system** that assesses prior knowledge and fills gaps
- An **AI coach** (any OpenAI-compatible model or Gemini, with offline answers as a fallback) that streams personalized replies
- **Learning styles** that change how answers are shaped
- **Progress tracking**, plus Focused mode (a growing bonsai) and Game mode (XP, streaks, companions)

---

## Key Features

### 🎯 Adaptive Learning Engine
- Patients complete an **Initial Quiz** before any lessons begin
- The system identifies which learning objectives the patient already knows vs. doesn't know
- A personalized **Learning Plan** is generated based on knowledge gaps
- Patients work through **Lessons** covering Facts, Dosage, Procedures, and Rationales
- A **Checkpoint Quiz** tests retained knowledge and re-queues missed objectives

### 🤖 AI Learning Assistant
- Floating chat widget on every learning page (`chat-widget.js`) and a full-screen assistant at `chatbot.html`, sharing one engine (`chat-core.js`, `chat.css`)
- Streams replies as they are written; saved, searchable chat history with rename/delete, continued across the widget and the full page
- Personalized with the user's **archetype**, experience level, health intake, learning-path progress and missed quiz questions
- Tutors, not just answers: quizzes one question at a time, reviews weak spots, suggests follow-ups, and links to the right lesson
- Clinical safety alerts on drug interactions and contraindications; works for signed-in users and guests

### 📋 Patient Intake Form
- Collects allergy history (penicillin, anaphylaxis), medical conditions, and current medications
- Generates personalized **safety warnings** based on intake responses (e.g., flags warfarin interactions, pregnancy status, kidney disease)
- Intake data is stored per-user in the SQLite database

### 📈 Progress Tracking
- Real-time mastery stats (Known vs. Unknown objectives) displayed per drug
- Breakdown by category: Facts, Dosage, Procedures, Rationales
- Tracks last quiz results and lesson queue state

### 🔐 User Authentication (AWS Cognito)
- Email/password signup with email verification
- Secure JWT tokens managed by AWS Cognito
- Auto-confirmation flow: email is pre-filled on the verification code page
- Cognito pool configured in one place (`.env`), served to the browser via `/auth/config`

### 🗄️ SQLite Database Persistence
- User learning profiles stored in `chatbot.db` via SQLAlchemy
- Auto-creates a profile for any new Cognito user on first login
- Eliminates the fragile flat-file JSON storage approach
- Supports concurrent users without data corruption risk

### 🧹 Clean Navigation UX
- Sidebar uses **Fitts's Law** (large, close targets) and **Gestalt principles** (visual grouping)
- Icon-labeled menu items with active-state left-border highlight
- Drug and Archetype settings pinned to a dedicated bottom section of the sidebar

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, Vanilla CSS, JavaScript (ES Modules) |
| **Backend** | Python 3, FastAPI, Uvicorn |
| **Database** | SQLite via SQLAlchemy ORM, versioned with Alembic |
| **AI / LLM** | OpenAI `gpt-4o-mini` (`openai`), fallback Google Gemini 2.5 Flash (`google-genai`), rule-based offline fallback |
| **Authentication** | AWS Cognito (`amazon-cognito-identity-js`) |
| **Alt Frontend** | Streamlit (prototype / admin dashboard) |

---

## Project Structure

```
medical_chatbot/
│
├── app/                        # ✅ Main production app
│   ├── backend/
│   │   ├── main.py                  # FastAPI application & all API routes
│   │   ├── database.py              # SQLAlchemy engine & session setup
│   │   ├── models.py                # SQLite table definitions (User, Session, etc.)
│   │   ├── learning_data.py         # Starter curriculum seed source
│   │   ├── curriculum.py            # Repeatable seeding and SQL curriculum reads
│   │   ├── learning_store.py        # Relational profile, progress, and history
│   │   ├── manage_db.py             # Apply migrations and seed starter curriculum
│   │   ├── requirements.txt         # Python dependencies
│   │   └── chatbot.db               # Local SQLite data; schema managed by Alembic
│   │
│   └── frontend/
│       ├── index.html               # Main app shell (sidebar + tab content)
│       ├── chatbot.html             # Full-page Learning Assistant
│       ├── login.html               # Login page (AWS Cognito)
│       ├── signup.html              # Signup page (AWS Cognito)
│       ├── confirm.html             # Email verification page
│       ├── script.js                # All frontend logic (tabs, chat, quiz, intake)
│       ├── style.css                # Complete design system & UI styles
│       └── auth/
│           ├── authConfig.js        # ⚙️ AWS Cognito pool keys (edit here to switch pools)
│           └── authService.js       # Cognito SDK wrapper (signup, login, confirm, logout)
│
├── alembic.ini                      # Migration configuration
├── alembic/                         # Migration environment and frozen revisions
├── .env                             # Environment variables (gitignored)
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.12 (`brew install python@3.12` on macOS)
- A terminal / command line

### 1. Clone the repository
```bash
git clone https://github.com/Imonuil12/grove.git
cd grove
```

### 2. Set up environment variables
Copy `.env.example` to `.env` in the project root (this is the only `.env` the backend reads) and fill in the keys:
```env
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_google_gemini_api_key   # optional fallback
```
> Get a free Gemini API key at: https://aistudio.google.com/app/apikey

### 3. Install Python dependencies
```bash
python3.12 -m venv venv && source venv/bin/activate
python -m pip install -r app/backend/requirements.txt
```

### 4. Initialize or upgrade the database

With the backend stopped, run from the repository root:

```bash
python app/backend/manage_db.py status
python app/backend/manage_db.py upgrade
```

The setup command applies schema migrations and seeds missing curriculum. It
can be repeated without overwriting current relational progress or SQL content
edits. Legacy JSON profiles are not imported. See [migration instructions](alembic/README.md)
for revisions, alternate databases, future changes, and recovery.

`chatbot.db` must remain untracked. A branch that still tracks an old SQLite
file can bring that file back during a merge or branch switch; `.gitignore`
does not override an already tracked file. An unversioned legacy database
cannot be upgraded by the current setup command. Keep any data you need before
choosing a fresh database; do not simply stamp the legacy schema as current.

Signed-in learning state uses relational rows, not `users.profile_data`.
Guest Freeplay uses temporary, isolated in-memory state and chat history;
guest progress is not written to SQLite and disappears when the session ends.
Signed-in chat messages retain Fernet encryption at rest. Relational intake
and progress columns are not automatically encrypted by that chat helper.

### 5. Start the backend server
```bash
cd app/backend
python3 main.py
```
> The API will be available at: **http://127.0.0.1:8000**  
> Interactive API docs: **http://127.0.0.1:8000/docs**

### 6. Start the frontend server
Open a new terminal tab:
```bash
cd app/frontend
python3 -m http.server 5500
```
> The app will be available at: **http://127.0.0.1:5500/index.html**

---

## Authentication

Two providers, picked automatically by `GET /auth/config`:

- **Built-in accounts (default).** Used while `COGNITO_USER_POOL_ID` is empty.
  Email/password accounts live in the `local_credentials` table (scrypt-hashed
  passwords). `POST /auth/local/signup` and `POST /auth/local/login` return an
  HS256 token signed with `JWT_SECRET`. No email confirmation step.
- **AWS Cognito.** Set `COGNITO_REGION`, `COGNITO_USER_POOL_ID` and
  `COGNITO_CLIENT_ID` (plus optional `COGNITO_DOMAIN` / `COGNITO_REDIRECT_URI`)
  in `.env`. Signup then sends a verification code (`confirm.html`).

Either way the token is stored in `localStorage` and sent as a Bearer token, and
the backend creates the learner profile on first use. Guests can also try the
app without an account (temporary, in-memory progress).

## AI provider

The chatbot tries an OpenAI-compatible API, then Gemini, then built-in offline
answers. Free options: a Gemini key from Google AI Studio, Groq's free tier
(`OPENAI_BASE_URL=https://api.groq.com/openai/v1`), or Ollama running locally
(`OPENAI_BASE_URL=http://localhost:11434/v1`). See `.env.example`.

---

## Deploy

Grove runs as **one web service**: FastAPI serves the API and the website from
the same origin. Production uses PostgreSQL; local development uses SQLite.

**Render + Neon (free):**
1. Create a free Postgres database at [neon.tech](https://neon.tech) and copy its connection string.
2. In [Render](https://render.com), choose **New → Blueprint** and select this repository. `render.yaml`
   creates the service and generates `JWT_SECRET` and `SESSION_ENCRYPTION_KEY`.
3. Paste the Neon string into `DATABASE_URL` (and optionally a free `GEMINI_API_KEY`), then deploy.

On every start the service migrates and seeds the database (`manage_db.py upgrade`), then serves on `$PORT`.
`GET /healthz` is the health check. With `APP_ENV=production` the app refuses to start without its secrets,
rejects unsigned tokens, and rate-limits sign-up and login.

---

## API Reference

Base URL: `http://127.0.0.1:8000`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/drug-content/{drug}` | Get all lessons and questions for a drug (`amoxicillin` or `ibuprofen`) |
| `POST` | `/intake` | Submit patient intake form and get safety warnings |
| `POST` | `/chat` | Send a message to the AI learning assistant |
| `POST` | `/initial-assessment` | Submit quiz answers to seed mastery records |
| `GET` | `/learning-plan/{drug}?username=` | Get the personalized lesson queue |
| `POST` | `/checkpoint` | Submit checkpoint quiz answers and update mastery |
| `GET` | `/progress/{drug}?username=` | Get mastery stats by category |
| `GET` | `/profile/{username}` | Get full user profile and state |

### Example: Chat Request
```json
POST /chat
{
  "message": "What are the side effects of amoxicillin?",
  "archetype": "The Skeptic",
  "drug": "amoxicillin",
  "username": "patient@example.com"
}
```

### Example: Chat Response
```json
{
  "response": "Based on the clinical data for Amoxicillin: common side effects include stomach upset, nausea, and diarrhea. Serious allergic reactions — hives, swelling, difficulty breathing — require immediate medical attention."
}
```

---

## Learning Archetypes

The archetype system is the core personalization mechanism. Each user selects how they prefer to receive information, and the Gemini AI rewrites every response accordingly.

| Archetype | Description | Response Style |
|---|---|---|
| **Needs more explanations** | Patient who wants step-by-step clarity | Nurturing, detailed, simple language |
| **The Skeptic** | Patient who demands evidence | Evidence-based, direct, no fluff |
| **Trying not to get Worse** | Patient motivated by avoiding harm | Safety-first, risk-focused phrasing |
| **All In Until I'm Not** | Highly motivated, detail-hungry patient | Comprehensive, technical, encouraging |

---

## Database Schema

The active database is `app/backend/chatbot.db`. Run
`python app/backend/manage_db.py upgrade` before starting the backend;
schema changes are managed by Alembic rather than `create_all()`.

The API reads curriculum, intake, progress, assessment history, preferences,
and active lesson sessions from relational records. `learning_data.py` is only
used to seed starter content. `users.profile_data` is an unused legacy column;
new progress does not update it. Progress is scoped per user and drug.

Live tables include `user_learning_state`, `user_badges`, `user_intakes`,
`user_warnings`, `user_objective_mastery`, `user_topic_mastery`,
`user_lesson_progress`, `assessment_submissions`, `user_quiz_attempts`,
`user_quiz_responses`, `user_drug_progress`, `user_learning_queue`,
`user_lesson_runs`, and `user_lesson_run_items`. The legacy tables below are
retained for compatibility with old data, rather than used as active storage.

```
users
  id           INTEGER PRIMARY KEY
  email        TEXT UNIQUE          ← identity from AWS Cognito
  profile_data TEXT                 ← unused legacy column
  created_at   DATETIME

sessions
  id           INTEGER PRIMARY KEY
  session_id   TEXT UNIQUE
  topic        TEXT
  archetype    TEXT
  has_done_intake BOOLEAN
  created_at   DATETIME

intakes
  id, session_id, penicillin_allergy, anaphylaxis_history,
  mono_suspected, kidney_disease, breastfeeding,
  pregnancy_status, meds_text

mastery_records
  id, session_id, topic, objective_id, status (Known/Unknown)

assessment_queue
  id, session_id, objective_id, order_index, is_current
```

---

## Configuration

| Variable | File | Description |
|---|---|---|
| `OPENAI_API_KEY` | `.env` | OpenAI key (primary chatbot model) |
| `GEMINI_API_KEY` | `.env` | Google Gemini key (fallback chatbot model) |
| `OPENAI_MODEL` / `GEMINI_MODEL` | `.env` | Optional model overrides (`gpt-4o-mini`; Gemini takes a comma-separated fallback list, default `gemini-3.5-flash,gemini-3.1-flash-lite`) |
| `DATABASE_URL` | Process environment | Optional SQLAlchemy URL; defaults to `app/backend/chatbot.db` |
| `COGNITO_REGION` / `COGNITO_USER_POOL_ID` / `COGNITO_CLIENT_ID` | `.env` | Your AWS Cognito pool and app client (served to the browser via `/auth/config`) |
| `COGNITO_DOMAIN` / `COGNITO_REDIRECT_URI` | `.env` | Optional Cognito hosted UI settings (for federated login) |
| `API_BASE_URL` | `auth/authConfig.js` | Backend base URL (default: `http://127.0.0.1:8000`) |

---

## License

All rights reserved for now. A license will be chosen before public release.
