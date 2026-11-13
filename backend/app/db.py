from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


BASELINE = "0001"  # the schema as it was before Alembic was added


def make_engine(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        """Kept for callers that still use the old name: it now runs the migrations."""
        self.migrate()

    def migrate(self) -> None:
        """Bring the database to the newest schema with Alembic (migrations/versions).

        A fresh database is built by the migrations from nothing. A database made before Alembic existed (it has tables but no
        alembic_version) is first given any columns the old start-up helper added, then marked as the baseline revision, then upgraded."""
        from pathlib import Path

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import inspect
        from . import models  # noqa: F401  (registers tables)
        tables = set(inspect(self.engine).get_table_names())
        legacy = "alembic_version" not in tables and bool(tables)
        if legacy:
            # Tables an old start-up never made are made now, except the ones the first migration after the baseline owns.
            newer = {"care_plans", "plan_responses", "patient_preferences"}
            Base.metadata.create_all(self.engine, tables=[t for n, t in Base.metadata.tables.items() if n not in newer])
            self._add_missing_columns()
        cfg = Config()
        cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        with self.engine.begin() as conn:
            cfg.attributes["connection"] = conn
            if legacy:
                command.stamp(cfg, BASELINE)
            command.upgrade(cfg, "head")

    def _add_missing_columns(self) -> None:
        """Columns added after a database was first made. Additive only: nothing is dropped or rewritten."""
        from sqlalchemy import inspect, text
        added = {"review_items": {"decision": "VARCHAR(10)"},
                 "users": {"username": "VARCHAR(60)", "password_hash": "VARCHAR(300)"}}
        insp = inspect(self.engine)
        with self.engine.begin() as conn:
            for table, cols in added.items():
                have = {c["name"] for c in insp.get_columns(table)}
                for name, ddl in cols.items():
                    if name not in have:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))

    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
