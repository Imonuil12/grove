from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

import os

import env_config  # noqa: F401  (DATABASE_URL may come from .env)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chatbot.db")


def normalize_database_url(url: str) -> str:
    """Hosting providers hand out postgres:// URLs; SQLAlchemy needs a driver name."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


SQLALCHEMY_DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL") or f"sqlite:///{DB_PATH}")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite:") else {},
    pool_pre_ping=not SQLALCHEMY_DATABASE_URL.startswith("sqlite:"),
)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def require_current_schema():
    """Fail before serving requests if this database has not been migrated."""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    heads = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    if current != heads:
        raise RuntimeError(
            "Database schema is not current. Stop the backend and run from the repository root: "
            "python app/backend/manage_db.py upgrade"
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
