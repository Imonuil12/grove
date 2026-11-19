"""Apply schema migrations.

Run from the repository root:
    python app/backend/manage_db.py status
    python app/backend/manage_db.py upgrade
    python app/backend/manage_db.py --database path/to.db upgrade   # a specific SQLite file

Databases created by the pre-Grove medication app (migration revisions
0001-0005) are converted once: accounts and passwords are kept, every other
table is dropped, and the Grove schema is created.
"""
import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url

from database import SQLALCHEMY_DATABASE_URL, normalize_database_url

ROOT = Path(__file__).resolve().parents[2]
LEGACY_REVISIONS = {"0001", "0002", "0003", "0004", "0005"}
KEPT_TABLES = ("users", "local_credentials")


def migration_config(url):
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def make_engine(url):
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    return engine


def safe_url(url):
    return make_url(url).render_as_string(hide_password=True)


def convert_legacy(engine, url):
    """Keep accounts from the medication app, drop everything else, build Grove."""
    legacy = MetaData()
    legacy.reflect(engine)
    saved = {}
    with engine.connect() as connection:
        for name in KEPT_TABLES:
            if name in legacy.tables:
                saved[name] = [dict(row._mapping) for row in connection.execute(select(legacy.tables[name]))]
    with engine.begin() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        legacy.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    command.upgrade(migration_config(url), "head")

    grove = MetaData()
    grove.reflect(engine)
    with engine.begin() as connection:
        for name in KEPT_TABLES:
            table = grove.tables[name]
            rows = [{key: value for key, value in row.items() if key in table.c} for row in saved.get(name, [])]
            if rows:
                connection.execute(table.insert(), rows)
        if connection.dialect.name == "postgresql":
            for name, key in (("users", "id"), ("local_credentials", "credential_id")):
                connection.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{name}', '{key}'), "
                    f"COALESCE((SELECT MAX({key}) FROM {name}), 0) + 1, false)"))
    print(f"Converted pre-Grove database; kept {len(saved.get('users', []))} accounts.")


def upgrade(url):
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            heads = set(MigrationContext.configure(connection).get_current_heads())
            tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if heads & LEGACY_REVISIONS:
            convert_legacy(engine, url)
        elif not heads and tables:
            raise RuntimeError("Database has tables but no migration version; refusing to touch it.")
        else:
            command.upgrade(migration_config(url), "head")
        print(f"Database ready: {safe_url(url)}")
    finally:
        engine.dispose()


def status(url):
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            heads = MigrationContext.configure(connection).get_current_heads()
        print(f"Database: {safe_url(url)}")
        print("Revision: " + (", ".join(heads) or "unversioned"))
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, help="Optional SQLite file")
    parser.add_argument("action", choices=("status", "upgrade"))
    args = parser.parse_args()
    if args.database:
        path = args.database.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        url = "sqlite:///" + path.as_posix()
    else:
        url = normalize_database_url(SQLALCHEMY_DATABASE_URL)
    upgrade(url) if args.action == "upgrade" else status(url)


if __name__ == "__main__":
    main()
