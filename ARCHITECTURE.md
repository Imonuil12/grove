# Grove — System Architecture & Technical Specification

> **Version**: 2.0.0  
> **Last Updated**: 2026-11-14  

---

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture Diagram](#system-architecture-diagram)
- [Tech Stack](#tech-stack)
- [Directory Structure](#directory-structure)
- [Backend Services & API Specification](#backend-services--api-specification)
- [Chatbot Engine Architecture](#chatbot-engine-architecture)
- [Database Schema & Models](#database-schema--models)
- [Authentication & User State Flow](#authentication--user-state-flow)
- [Maintenance & Auto-Sync Workflow](#maintenance--auto-sync-workflow)

---

## Overview

Grove is an adaptive, AI-powered learning application. Its current curriculum is medical education, designed to teach patients about their prescriptions (e.g., Amoxicillin, Ibuprofen) in a style matching their individual learning preferences (**Archetypes**).

The system combines:
1. **Curated Clinical Knowledge Base**: SQL-backed facts, dosages, procedures, and rationales, initially seeded from `learning_data.py`.
2. **Patient Intake Safety Engine**: Automated cross-referencing of patient medical history (allergies, kidney disease, pregnancy status) to flag interaction risks.
3. **Adaptive LLM Personalization**: Streaming answers from OpenAI (`gpt-4o-mini`) with Google Gemini (`gemini-2.5-flash`) as fallback, grounded in the curriculum and the learner's progress, with deterministic rule-based fallbacks.
4. **Multi-Turn Conversation Memory**: Session-level history tracking in SQLite.

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND LAYER                              │
│                                                                        │
│   • index.html (Main App Shell + Sidebar + Tab Views + Floating Chat)   │
│   • chatbot.html (Dedicated Full-Screen Assistant UI)                   │
│   • script.js (State Management, UI Event Handlers, API Fetch)          │
│   • auth/ (AWS Cognito Authentication SDK)                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │  HTTP / JSON (Port 8000)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (main.py)                       │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                      API ROUTER LAYER                          │   │
│   │  GET  /drug-content/{drug}     POST /intake                    │   │
│   │  POST /chat                    GET  /chat/history/{username}   │   │
│   │  POST /initial-assessment      GET  /learning-plan/{drug}      │   │
│   │  POST /checkpoint              GET  /progress/{drug}           │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────┴────────────────────────────────┐   │
│   │                    CHATBOT ENGINE CORE                         │   │
│   │  1. Intent & Objective Retrieval (find_relevant_objective)    │   │
│   │  2. Safety Guardrail Engine (check_safety_warnings)            │   │
│   │  3. Multi-Turn Context Assembler (get_recent_history)          │   │
│   │  4. LLM Engine (llm.py + chat_prompt.py; OpenAI/Gemini/rules)  │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
└───────────────────────────────────┼────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       DATA & PERSISTENCE LAYER                         │
│                                                                        │
│   • SQLite Database (chatbot.db via SQLAlchemy)                        │
│     - Table: users (Cognito identity + unused legacy profile column)   │
│     - Tables: user_learning_state, user_lesson_runs (resume + XP)      │
│     - Tables: user_intakes, user_warnings (intake snapshots)           │
│     - Table: chat_messages (Multi-turn conversation history)           │
│     - Tables: user_objective_mastery, user_topic_mastery               │
│     - Tables: user_learning_queue, user_quiz_attempts/responses        │
│                                                                        │
│   • SQL curriculum (learning_data.py supplies starter seed records)    │
│     - Curated objectives for Amoxicillin and Ibuprofen                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology / Package | Role |
|---|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JS (ES Modules) | User Interface & Application Shell |
| **Backend** | Python 3.12, FastAPI, Uvicorn | RESTful API & Business Logic |
| **Database** | SQLite, SQLAlchemy ORM | Local Relational Data Persistence |
| **Schema migrations** | Alembic | Versioned schema upgrades and SQLite batch migrations |
| **AI / LLM** | OpenAI API (`openai`), Google Gemini (`google-genai`) | Archetype Persona Rewriting & Dynamic Q&A |
| **Authentication**| AWS Cognito (`amazon-cognito-identity-js`) | JWT Token Authentication & Identity |

---

## Directory Structure

```
grove/
├── ARCHITECTURE.md                  # 📜 System Architecture Specification (this document)
├── start.sh                         # 🚀 Orchestration script to run backend & frontend
├── alembic.ini                      # Migration configuration
├── alembic/                         # Versioned schema and migration instructions
├── .env                             # 🔑 Environment keys (API keys)
├── .agents/
│   └── rules/
│       └── architecture_docs.md     # 🤖 Customization rule for auto-updating documentation
│
└── app/                        # 📦 Production Application Code
    ├── backend/
    │   ├── main.py                  # FastAPI API Routes, Engine & LLM Logic
    │   ├── database.py              # SQLAlchemy Engine & Session Configuration
    │   ├── models.py                # Database Tables (Users, Intakes, ChatMessages, Mastery)
    │   ├── manage_db.py             # Apply migrations and seed starter curriculum
    │   ├── requirements.txt         # Backend dependencies, including Alembic
    │   ├── learning_data.py         # Starter curriculum seed source
    │   ├── curriculum.py            # Seed and query SQL curriculum
    │   ├── learning_store.py        # Relational state, attempts, queues, resume
    │   ├── chatbot.db               # SQLite data; schema managed by Alembic
    │
    └── frontend/
        ├── index.html               # Main App Shell (Sidebar, Tabs, Floating Chat)
        ├── chatbot.html             # Standalone Full-Page Learning Assistant
        ├── login.html / signup.html # Authentication Pages
        ├── script.js                # Frontend API Fetch, Chat Rendering, Tab Logic
        ├── style.css                # Design System & UI Styling
        └── auth/
            ├── authConfig.js        # AWS Cognito Credentials
            └── authService.js       # Authentication SDK Wrapper
```

---

## Backend Services & API Specification

Base URL: `http://127.0.0.1:8000`

### 1. Chatbot Endpoint
- **`POST /chat/stream`**: Main chat route. Streams NDJSON events: `meta` (conversation id, safety warning), `delta` (text chunks), `done` (final reply, follow-up `suggestions`, learning `actions`, conversation title). Accepts optional `page_context` (e.g. `lesson:Dosage`) and `archetype` (omitted = saved profile value).
- **`POST /chat`**: Same engine without streaming (used by the chat quiz); returns `response`, `safety_warning`, `suggestions`, `actions`, `conversation_id`.
- **`GET /chat/context/{drug}?username=`**: Learner snapshot for the chat UI: unit progress, mastered count, XP/streak/hearts, struggling topics, next unit, intake on file, personalized starter prompts.
- **`GET /conversations/{username}`**, **`PATCH /conversations/{id}`** (rename), **`DELETE /conversations/{id}`** (owner only).
- **`POST /preferences`**: Saves the learning style (archetype) and/or experience level immediately. Called by the intake chips, the full chatbot's style menu and the widget's style menu, so lessons, the chat quiz and the chatbot all use one setting.
  - **Request Body**:
    ```json
    {
      "username": "patient@example.com",
      "message": "What should I do if amoxicillin causes stomach upset?",
      "archetype": "Needs more explanations",
      "drug": "amoxicillin"
    }
    ```
  - **Response Body**:
    ```json
    {
      "response": "Amoxicillin can be taken with food or milk if it causes stomach upset...",
      "safety_warning": "⚠️ Safety Alert: User intake records indicate a history of Penicillin allergy.",
      "drug": "amoxicillin",
      "archetype": "Needs more explanations"
    }
    ```

### 2. Multi-Turn Chat History Endpoint
- **`GET /chat/history?drug=amoxicillin&limit=20`**: Returns history for the session identity, decrypting signed-in messages on read.
- **`GET /chat/history/{username}?conversation_id=&limit=20`**: Compatibility route for conversation-based clients; the username must match the session identity.
- **`GET /conversations/{username}`**, **`POST /conversations/new`**, and **`DELETE /conversations/{conversation_id}`** retain per-user conversation threads. Another user's threads cannot be read, appended to, or deleted.

### 3. Patient Intake Endpoint
- **`POST /intake`**: Stores patient medical profile (allergies, kidney disease, pregnancy status, current meds) and evaluates immediate warnings.

### 4. Learning & Progress Endpoints
- **`GET /drug-content/{drug}`**: Gets all curated lessons and objectives for a medication.
- **`POST /initial-assessment`**: Submits pre-quiz results to initialize mastery state.
- **`GET /learning-plan/{drug}?username=`**: Gets personalized queue of unmastered objectives.
- **`POST /checkpoint`**: Submits checkpoint quiz answers and updates mastery levels.
- **`GET /progress/{drug}?username=`**: Gets mastery breakdown by category (Facts, Dosage, Procedures, Rationales).

### 5. Authentication and Temporary Guest Sessions
- **`GET /auth/verify`**: Checks the supplied bearer token through the existing auth helper.
- **`GET /auth/config`** and **`POST /auth/turnstile`** preserve master's browser-check configuration and session flow.
- **`POST /auth/guest`** creates an opaque, expiring guest session; **`DELETE /auth/guest`** ends it.
- Learning and chat routes use `require_authenticated_user` for identity instead of trusting a body or query username. Existing development-mode and demo-token behavior is retained, not a new production-security guarantee.

---

## Chatbot Engine Architecture

```
User Input Query
       │
       ▼
1. Drug Context Detection ──► Identifies explicitly named drug or defaults to focused drug
       │
       ▼
2. Objective Retrieval ────► Matches query against the SQL curriculum
       │
       ▼
3. Patient Safety Engine ──► Evaluates patient Intake record (allergies, kidney disease, pregnancy)
       │
       ▼
4. Multi-Turn Context ─────► Fetches recent conversation turns from SQLite chat_messages table
       │
       ▼
5. Interactive LLM Engine ─► Generates archetype persona responses or politely handles off-topic queries
       │
       ▼
Output Response Payload (Returned to Frontend UI with optional Safety Alert Banners)
```

### Key Engine Features
- **LLM layer (`llm.py`)**: OpenAI (`gpt-4o-mini`, override with `OPENAI_MODEL`) first, Gemini (`gemini-3.5-flash`, falling back to `gemini-3.1-flash-lite`, via `google-genai`; override with `GEMINI_MODEL`) second, both with streaming and real multi-turn messages. With no working provider, `rule_based_response()` answers offline.
- **Personalized prompt (`chat_prompt.py`)**: Built from a learner snapshot (`build_learner_snapshot` in `main.py`): archetype + experience level, intake summary, per-unit progress, struggling concepts and missed quiz questions, the page the learner is on, and the drug's curriculum as grounding. The model appends follow-up suggestions after a `<<<FOLLOWUPS>>>` marker that the server strips before streaming.
- **Learning actions**: `suggest_actions()` links answers to the matching lesson, the learning path, or the intake form.
- **Learning styles**: each archetype is a required answer shape with a word budget (`ARCHETYPE_STYLES` in `chat_prompt.py`), so the four styles look clearly different. Chat clients don't send an archetype; the server always uses the saved one.
- **Live adaptation**: `conversation_signals()` reads the learner's recent messages (confused, wants depth, wants it shorter) and adjusts the next answer; completed units and weak spots also shape the prompt.
- **Connected to Focused and Game modes**: the widget runs on the Focused and Game pages and lessons. Lesson feedback has an "Ask the assistant" link that opens the widget with the question and the learner's answer. In the Focused chat quiz, help requests ("explain…", "hint", "I don't understand…", or questions) go to the chatbot with `page_context=chat-quiz:<unit>` and `quiz_question`, which tells the model to give hints, not the answer, and they share one conversation.
- **Frontend**: `chat-core.js` (engine: streaming, Markdown, history), `chatbot.html` (full page with history sidebar and "Your learning" panel), `chat-widget.js` (floating widget injected on index/focused/game/lesson pages), `chat.css`.
- **Off-Topic Query Handling & Redirection**: When users ask general or off-topic questions (e.g. weather, sports, general knowledge), the LLM provides a polite, brief response followed by a friendly reminder redirecting them to medication education.
- **No Mid-Sentence Truncation**: Replaced hardcoded string truncation (`[:120] + '...'`) with complete, fluid sentence generation.
- **Patient Safety Warnings**: Evaluates allergy history (Penicillin/Anaphylaxis), Kidney Disease, Pregnancy, and Drug Interactions (Warfarin/Blood thinners) to attach prominent red alert banners (`⚠️ PATIENT SAFETY WARNING`).
- **Shared Warning UI**: `chat-core.js` renders `safety_warning` above the reply as an accessible alert (also rebuilt when history reloads); `script.js` keeps `renderSafetyWarning` for the focused chat quiz. Warning text is inserted as text, not HTML.
- **Session Recovery and Lesson Routing**: The frontend can recover a missing display identity from stored Cognito claims without requiring a Turnstile token. API requests retain token refresh, ID/access-token fallback, guest handling, and existing 401 redirects. Focused chat quizzes continue to use `chat-quiz.html`; other lesson formats use `lesson.html`.

### Prevention and education framework

The Learning Path uses this sequence to organize the new topic outlines. It also describes the intended conversation flow for a chatbot grounded in those topics. The current chat engine uses the drug curriculum.

1. **Build awareness.** Explain what the condition is, why it matters over time, and which factors can affect risk. Connect a habit to a likely effect in plain language. Use a numerical risk estimate only when reliable evidence supports it for a relevant population.
2. **Explain prevention.** Distinguish steps that can reduce risk before disease from screening or monitoring that can catch problems early. Offer a few relevant options and direct personal screening or diagnosis questions to a healthcare professional.
3. **Support action and follow-up.** Suggest one optional swap or small step based on the learner’s preferences, access, and constraints. Ask how it went, recognize what worked, and help adjust the plan if it was difficult to repeat.

`app/frontend/learning-catalog.json` defines the navigation categories, including Drugs, and the topic codes and core skill labels for the planned outlines. The existing `manage_db.py upgrade` command seeds `Category` and `Topic` rows from the outlines and links condition topics to `Condition` through `TopicCondition`. Drug skill units continue to be seeded from `learning_data.py`.

`focused.html` and `game.html` are the layouts for every category. `learn-page.js` fills the shared topic picker and path panel. Drugs use `/path/{drug}`. Playable non-drug topics use `/topics/{topic_code}/path` and the same lesson player in `lesson.html`. Other topics render planned levels and a bonsai preview in Focused.

`learning_data.py` defines its objectives in `TOPIC_LESSONS`. `manage_db.py upgrade` seeds them under `condition:hypertension` with one quiz per skill. Topic progress comes from quiz attempts and responses for signed-in learners. Guests keep the same progress within their temporary session. Focused mini quizzes and Chat quiz share those questions and progress. Both drug and topic quiz help use `/chat` and the same AI provider configuration. Topic quiz help resolves the active question and lesson notes from the owned attempt, sends up to three prior help exchanges from the current page, and falls back to an authored hint when the provider is unavailable.

Medication courses are defined in `DRUG_DATABASE`. Each medication has a `Drug` row linked through `TopicDrug` to its skill topics, such as Amoxicillin: Facts. A non-drug subject such as High Blood Pressure starts with a `Topic` row and gets its playable content from `TOPIC_LESSONS`.

### Learning Archetypes Supported
1. **Needs more explanations**: Nurturing, step-by-step, simple language, uses gentle analogies.

2. **The Skeptic**: Evidence-backed, clinical mechanism details, direct.
3. **Trying not to get Worse**: Safety-first, consequence-focused, risk awareness.
4. **All In Until I'm Not**: Concise, minimal fluff, bullet-style core facts.

---

## Database Schema & Models

Database: `app/backend/chatbot.db` (SQLite), optionally overridden by a
process-level `DATABASE_URL`. Both the application and Alembic resolve the same
URL. Application SQLite connections enforce foreign keys.

### Schema lifecycle

Schema changes use Alembic; `main.py` checks the recorded revision before
serving requests and instructs developers to run `manage_db.py upgrade` when
migrations are missing. It no longer calls `Base.metadata.create_all()`.

The revision chain is `0001` (legacy profiles/chat), `0002` (pre-existing expanded
schema), `0003` (finalized relational constraints and fields), and `0004`
(preferences, per-drug queues, assessment groups, and resumable sessions). Existing
unversioned prototype databases are not imported; fresh setups start with an empty
SQLite file. The setup utility applies migrations and seeds starter curriculum.
Batch migrations use explicit transactions and validate foreign
keys before committing. See [migration workflow](alembic/README.md).

### Relational curriculum and learning schema

| Data | Tables and relationships |
| --- | --- |
| Curriculum organization | `categories` → `topics` → `lessons` and `quizzes` |
| Lesson text variants | `lesson_contents`, unique by lesson and experience level |
| Assessments | `quizzes` → `questions` → `answer_choices` / `accepted_keyword_sets` |
| Clinical domains | `drugs`, `drug_classes`, `drug_aliases`, `conditions`, `condition_aliases` |
| Topic associations | `topic_drugs`, `topic_conditions` |
| Risk/prevention | `risk_factors`, `condition_risk_factors`, `prevention_strategies`, `risk_factor_strategies` |
| Intake snapshots | `user_intakes` → `user_warnings`, linked to a user and optionally a drug |
| Lesson progress | `user_lesson_progress`, unique by user and lesson |
| Assessment history | `user_quiz_attempts` → `user_quiz_responses`, unique by attempt and question |
| Mastery | `user_topic_mastery`; `user_objective_mastery`, unique by user, lesson, and objective code |
| Preferences/gamification | `user_learning_state` with optimistic version checks; `user_badges` |
| Per-drug state | `user_drug_progress` and `user_learning_queue` for plans and review items |
| Resumable sessions | `user_lesson_runs` → `user_lesson_run_items` |
| Assessment groups | `assessment_submissions` groups category-specific quiz attempts; responses retain question snapshots |

Objective codes such as `F1` are not globally unique: the same code may exist
for different drugs. Lesson identity and topic context scope them. A lesson's
optional legacy `objective_code` identifies its primary objective; mastery can
track multiple objective codes within the lesson. Questions can link directly
to a lesson while retaining their objective code. Curriculum integration must
validate that question, lesson, and quiz belong to the appropriate topic.

Category names are unique within their domain, allowing a category name in
more than one domain. Lesson primary objective codes are unique within their
topic. Keyword groups have a unique order per question, cannot be empty, and
retain the current CSV representation for conversion to keyword lists. All
keywords in a group must match; any matching group passes the existing scorer.

Mastery labels are `Known` or `Unknown`, streaks cannot be negative, and crowns
range from 0 to 5. Scores and completion percentages range from 0 to 100. Intake
snapshots include the current demographic, lifestyle, sleep, activity, medical,
and experience-level fields; selected multi-value fields use JSON arrays.

Deleting curriculum referenced by progress, intake, or assessment history is
blocked by foreign keys instead of cascading into user history. Application
code should retire curriculum rather than delete it. User-owned data retains
the existing ORM ownership cascades.

**Integration status:** curriculum and all learning/profile endpoints now use
relational storage via `curriculum.py` and `learning_store.py`. Initial and
checkpoint submissions append quiz attempts and responses; practice answers
also retain history. Intake updates append snapshots. Mastery, lesson progress,
and topic aggregates are updated together. Progress is scoped per drug so
shared codes such as `F1` cannot overwrite another medication's records.

`manage_db.py upgrade` applies schema migrations and seeds starter curriculum.
Legacy JSON import/preservation code has been removed because old local intake
and progress were disposable. `users.profile_data` is an unused legacy column;
runtime progress never reads it. New users, or users without a learning-state
row, receive empty relational defaults on their first request. Repeating setup
preserves current relational records and SQL content edits.

Answer normalization and keyword scoring live directly in `main.py`.
The lesson endpoint's current-question check rejects repeated or out-of-order
answers. There is no separate scoring module or development-only test folder.
AWS Cognito accounts are independent of the local intake/progress database.

The endpoint paths and response shapes are preserved. The API adds explicit
HTTP 404 for unknown drugs/categories, HTTP 400 for replayed/out-of-order lesson
answers or premature completion, and HTTP 409 for concurrent stale writes.
Category ordering is read from `categories.display_order`; starter ordering
remains Facts → Dosage → Procedures → Rationales. Conversations and messages
continue to use their existing tables. Chat safety reads the latest relational
intake snapshot instead of stale legacy intake rows.

The master integration preserves focused learning, guest Freeplay, new persona
fallbacks, and expanded clinical interaction alerts. Registered users use
`learning_store.py`; compatibility wrappers in `main.py` must not reintroduce
JSON-profile writes. Guest mastery and queues are scoped per drug in temporary
memory; guest intake, attempts, progress, conversations, and messages do not
create persistent rows. Guest routes are registered before the direct-script
`uvicorn.run` call. Signed-in chat messages are Fernet-encrypted on write and
decrypted for API history and AI context. This encryption does not automatically
encrypt individual relational intake or progress columns.

### Table `users`
- `id` (INTEGER, Primary Key)
- `email` (TEXT, Unique) — Identity key from AWS Cognito
- `profile_data` (TEXT, JSON Blob) — Unused legacy column
- `created_at` (DATETIME)

### Table `intakes`
- `id` (INTEGER, Primary Key)
- `session_id` (TEXT, Index) — User email
- `penicillin_allergy` (BOOLEAN)
- `anaphylaxis_history` (BOOLEAN)
- `mono_suspected` (BOOLEAN)
- `kidney_disease` (BOOLEAN)
- `breastfeeding` (BOOLEAN)
- `pregnancy_status` (TEXT)
- `meds_text` (TEXT)

### Table `chat_messages`
- `id` (INTEGER, Primary Key)
- `session_id` (TEXT, Index)
- `sender` (TEXT) — "user" or "bot"
- `message` (TEXT)
- `drug` (TEXT)
- `archetype` (TEXT)
- `has_safety_warning` (BOOLEAN)
- `timestamp` (DATETIME)

### Table `mastery_records`
- `id` (INTEGER, Primary Key)
- `session_id` (TEXT)
- `topic` (TEXT) — "Amoxicillin" or "Ibuprofen"
- `objective_id` (TEXT) — E.g. "F1", "D1", "P1", "R1"
- `status` (TEXT) — "Known" or "Unknown"

---

## Authentication & User State Flow

1. **AWS Cognito Signup/Login**: User authenticates via AWS Cognito User Pool.
2. **JWT Storage**: Tokens (`accessToken`, `idToken`, `userEmail`) stored in browser `localStorage`.
3. **Session Identity**: Every protected route gets its identity from a Cognito token or a guest session, never from a username sent by the browser. Signed-out requests get 401 in every environment (there is no `dev_user`/`X-Dev-User` fallback anymore, so no placeholder accounts are created). Signed-out visitors see sign-in prompts; guests get temporary progress and chat, while saved chat history is account-only. `app/backend/account_cleanup.py` lists and removes placeholder accounts (`--list`, `--fake --yes`).
4. **Auto-Profile Creation**: On the first signed-in state request, FastAPI creates a `users` row and empty relational `user_learning_state`; writes commit or roll back with the request.
5. **Guest Mode**: Each guest receives an opaque token in tab-scoped `sessionStorage`, sent as `X-Guest-Session`. Progress and chat are isolated in memory, expire after four hours, and disappear on backend restart. Guests do not create SQLite learning rows.
   The login page and account menu both offer **Try without an account** and use `auth/guestSession.js` to create the same backend guest session before opening `index.html`. The former demo-patient button and fabricated Cognito token have been removed; normal Cognito login is unchanged.

**Existing security limitation:** `auth.verify_jwt_token` still contains an
unverified-token fallback. Local test scripts sign in with locally signed test tokens.
Those master behaviors were preserved during the database merge; they must
be hardened before deployment. Passing the offline demo and safety tests is
not validation of live Cognito configuration or production token security.

---

## Maintenance & Auto-Sync Workflow

> [!IMPORTANT]
> Whenever backend endpoints, database tables, or core chatbot features are added or updated in the codebase, the workspace customization rule [architecture_docs.md](.agents/rules/architecture_docs.md) ensures `ARCHITECTURE.md` is automatically updated to maintain codebase documentation integrity.
