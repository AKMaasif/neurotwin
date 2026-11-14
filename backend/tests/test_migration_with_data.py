"""A database made before the acceptance migration, with routines and the person's replies already in it, must upgrade cleanly.
(SQLite rebuilds a table to change it; with foreign keys on, that fails if other tables point at rows in it.)"""
from sqlalchemy import text

from app.db import Base, Database


def legacy_db_with_data(tmp_path):
    """The schema exactly as it was at the baseline revision, with a routine and a reply already stored."""
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'old.db'}"
    db = Database(url)
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with db.engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0001")
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO users (id, role, display_name, language, is_demo, created_at) VALUES ('p1','participant','P One','en',1,'2026-01-01'),('c1','clinician','Dr C','en',1,'2026-01-01')"))
        c.execute(text("INSERT INTO care_plan_items (participant_id, created_by, text_en, day_part, weekdays, status, created_at) "
                       "VALUES ('p1','c1','Walk','morning','[]','active','2026-01-02')"))
        c.execute(text("INSERT INTO care_plan_replies (item_id, participant_id, day, reply, at) VALUES (1,'p1','2026-01-03','done','2026-01-03')"))
    return db, url


def test_old_database_with_routines_and_replies_upgrades_and_keeps_them(tmp_path):
    db, url = legacy_db_with_data(tmp_path)
    db.engine.dispose()
    fresh = Database(url)
    fresh.migrate()
    with fresh.engine.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1                    # protection is back on for normal use
        assert c.execute(text("SELECT COUNT(*) FROM care_plan_items")).scalar() == 1
        assert c.execute(text("SELECT COUNT(*) FROM care_plan_replies")).scalar() == 1
        assert c.execute(text("SELECT COUNT(*) FROM care_plans WHERE legacy = 1 AND status = 'accepted'")).scalar() == 1
        assert c.execute(text("PRAGMA foreign_key_check")).all() == []


def test_database_made_before_alembic_existed_with_data_upgrades_too(tmp_path):
    """The same, through the adoption path (tables exist, no alembic_version), which is how an older local database arrives."""
    db, url = legacy_db_with_data(tmp_path)
    with db.engine.begin() as c:
        c.execute(text("DROP TABLE alembic_version"))
    db.engine.dispose()
    fresh = Database(url)
    fresh.migrate()
    with fresh.engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM care_plan_replies")).scalar() == 1
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0007"
        assert c.execute(text("PRAGMA foreign_key_check")).all() == []
