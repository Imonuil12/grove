# Database setup and schema updates

Alembic manages the database schema. `models.py` describes the desired tables;
`alembic/versions/` contains the versioned operations that create or update them.
Keep these files in the repository for future database changes.

## Setup

With the backend stopped, run from the repository root:

```powershell
python -m pip install -r .\app\backend\requirements.txt
python .\app\backend\manage_db.py upgrade
python .\app\backend\manage_db.py status
python .\app\backend\main.py
```

The setup command applies pending migrations and seeds missing starter curriculum.
It does not import legacy JSON, preserve old intake answers, or create migration
backups. Repeating it preserves existing relational records and SQL content edits.

The default database is `app/backend/chatbot.db`. `DATABASE_URL` can
override the application/Alembic connection. To initialize a separate SQLite file:

```powershell
python .\app\backend\manage_db.py --database .\new-test.db upgrade
```

A fresh database needs no old user records for AWS login to work. Verified
accounts live in AWS Cognito; the backend creates a local user row and empty
relational learning state when that user first accesses a profile feature.

Unversioned legacy databases are no longer adopted or imported. Use a fresh
SQLite file if starting from one of the old prototype databases. Existing
databases with an Alembic revision continue to upgrade normally.

## Future schema changes

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
# Review the generated upgrade and downgrade operations.
python .\app\backend\manage_db.py upgrade
python -m alembic check
```

Raw `python -m alembic upgrade head` applies schema changes only.
`manage_db.py upgrade` also seeds the curriculum, making it the usual setup
command. Alembic paths resolve relative to `alembic.ini`, not the terminal's
working directory.

Name new constraints and review generated migrations, especially changes to
check constraints and existing data. SQLite batch migrations rebuild tables
inside explicit transactions and check foreign keys before commit. Offline
`--sql` generation is not supported by this migration environment.

## Existing revision history

| Revision | Purpose |
| --- | --- |
| `0001` | Original profile, session, intake, mastery, queue, and chat tables |
| `0002` | Expanded relational curriculum and learning tables |
| `0003` | Mastery constraints, complete intake fields, lesson variants, question links |
| `0004` | Preferences, badges, per-drug progress/queues, lesson sessions, assessment groups |

These revisions are retained because the local database already uses them.
They define schema changes and do not backfill old intake or lesson records.

## Runtime files

- `main.py`: API routes, answer scoring, and current-question validation.
- `curriculum.py`: SQL curriculum queries and repeatable starter-data seeding.
- `learning_store.py`: Relational intake, progress, attempts, preferences, and sessions.
- `learning_data.py`: Version-controlled starter curriculum, read only by the seeder.
- `models.py`: SQLAlchemy table and relationship definitions.
- `database.py`: Database connections and migration-version checks.

The standalone `scoring.py`, JSON backfill, development requirements, and
migration/relational test files were removed. Answer checking remains in
`main.py`; replay prevention remains in the lesson-answer endpoint. Future
intake and learning progress still save in relational rows. The legacy
`users.profile_data` column is unused and is not a source of current state.
