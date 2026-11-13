"""Alembic environment. The app runs migrations itself at start-up (db.Database.migrate) with its own connection;
the command line (`alembic upgrade head`) uses NEUROTWIN_DATABASE_URL."""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (registers tables)
from app.db import Base

config = context.config
target_metadata = Base.metadata


def run() -> None:
    conn = config.attributes.get("connection")
    if conn is None:
        url = os.environ.get("NEUROTWIN_DATABASE_URL")
        if not url:
            raise SystemExit("Set NEUROTWIN_DATABASE_URL to run migrations from the command line.")
        engine = create_engine(url)
        with engine.connect() as c:
            _migrate(c)
            c.commit()
    else:
        _migrate(conn)


def _migrate(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=connection.dialect.name == "sqlite", compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


run()
