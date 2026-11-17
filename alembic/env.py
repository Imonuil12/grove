"""Run migrations without importing FastAPI or initializing AI providers."""
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "backend"))
from database import Base, SQLALCHEMY_DATABASE_URL
import models  # Register all tables; never import main.py here.

config = context.config
target_metadata = config.attributes.get("target_metadata", Base.metadata)

if context.is_offline_mode():
    raise RuntimeError("SQLite batch migrations require a connection; omit --sql.")


def run(connection):
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        # Batch migrations rebuild referenced tables. FK enforcement is only
        # disabled on this connection; validate all references before commit.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        connection.exec_driver_sql("BEGIN")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
        compare_server_default=True,
        transactional_ddl=sqlite,
    )
    try:
        with context.begin_transaction():
            context.run_migrations()
            if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchone():
                raise RuntimeError("Invalid foreign keys; migration rolled back.")
        if sqlite:
            connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


provided_connection = config.attributes.get("connection")
if provided_connection is not None:
    run(provided_connection)
else:
    url = config.get_main_option("sqlalchemy.url") or SQLALCHEMY_DATABASE_URL
    migration_engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with migration_engine.connect() as connection:
            run(connection)
    finally:
        migration_engine.dispose()
