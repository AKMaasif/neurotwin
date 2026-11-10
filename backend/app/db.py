from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


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
        from . import models  # noqa: F401  (registers tables)
        Base.metadata.create_all(self.engine)
        self._add_missing_columns()

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
