"""Apply schema migrations and seed starter curriculum.

Run from the repository root:
    python app/backend/manage_db.py status
    python app/backend/manage_db.py upgrade
"""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from curriculum import seed_curriculum
from database import SQLALCHEMY_DATABASE_URL

ROOT = Path(__file__).resolve().parents[2]


def migration_config(url):
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade_database(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    url = "sqlite:///" + path.as_posix()
    target = create_engine(url)
    event.listen(target, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    try:
        with target.connect() as connection:
            tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
            if tables and not MigrationContext.configure(connection).get_current_heads():
                raise RuntimeError("This is an unversioned legacy database. Use a fresh SQLite file; legacy data import has been removed.")
        command.upgrade(migration_config(url), "head")
        with Session(target) as session, session.begin():
            seed_curriculum(session)
        print(f"Database ready; starter curriculum seeded: {path}")
    finally:
        target.dispose()


def upgrade_server_database(url):
    """Migrate and seed a non-SQLite database (e.g. Postgres) in place."""
    target = create_engine(url)
    try:
        config = migration_config(url)
        with target.connect() as connection:
            versioned = bool(MigrationContext.configure(connection).get_current_heads())
            tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if not versioned and not tables:
            # Fresh server database: the early migrations are SQLite-specific,
            # so build the current schema from the models and mark it as head.
            import models  # noqa: F401  (registers every table)
            from database import Base
            Base.metadata.create_all(target)
            command.stamp(config, "head")
        elif not versioned:
            raise RuntimeError("Database has tables but no migration version; refusing to touch it.")
        else:
            command.upgrade(config, "head")
        with Session(target) as session, session.begin():
            seed_curriculum(session)
        print(f"Database ready; starter curriculum seeded: {make_url(url).render_as_string(hide_password=True)}")
    finally:
        target.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="Optional SQLite file")
    parser.add_argument("action", choices=("status", "upgrade"))
    args = parser.parse_args()
    url = make_url(SQLALCHEMY_DATABASE_URL)
    if args.database is None and url.get_backend_name() != "sqlite":
        if args.action == "upgrade":
            upgrade_server_database(SQLALCHEMY_DATABASE_URL)
        else:
            from sqlalchemy import text
            engine = create_engine(SQLALCHEMY_DATABASE_URL)
            with engine.connect() as connection:
                print("Revision: " + (", ".join(MigrationContext.configure(connection).get_current_heads()) or "unversioned"))
            engine.dispose()
        return
    if args.database is None and (not url.database or url.database == ":memory:"):
        parser.error("Use --database for a SQLite file.")
    path = (args.database or Path(url.database)).resolve()
    if args.action == "upgrade":
        upgrade_database(path)
    elif not path.exists():
        print(f"Database does not exist yet: {path}")
    else:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            has_version = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone()
            versions = connection.execute("SELECT version_num FROM alembic_version").fetchall() if has_version else []
            print(f"Database: {path}")
            print("Revision: " + (", ".join(row[0] for row in versions) or "unversioned"))


if __name__ == "__main__":
    main()
