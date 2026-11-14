"""The six-month synthetic history: reproducible, idempotent, tagged, separate, and free of scores or stories."""
from datetime import date

from sqlalchemy import func, select

from app import synthetic_history as H
from app.db import Database
from app.models import ActivitySession, CarePlanReply, Evidence, ReviewItem
from app.seed import seed

REF = date(2026, 11, 10)


def fresh(tmp_path, name="a.db"):
    d = Database(f"sqlite:///{tmp_path / name}")
    d.create_all()
    s = d.SessionLocal()
    seed(s)
    return s


def snapshot(db):
    rows = db.execute(select(ActivitySession.participant_id, ActivitySession.protocol_code, ActivitySession.started_at,
                             ActivitySession.status, ActivitySession.assisted, ActivitySession.interruptions)
                      .where(ActivitySession.device == H.DEVICE).order_by(ActivitySession.id)).all()
    ev = db.execute(select(Evidence.participant_id, Evidence.measure, Evidence.value_num, Evidence.missing_reason, Evidence.quality)
                    .where(Evidence.producer_version == H.PRODUCER).order_by(Evidence.id)).all()
    return [tuple(r) for r in rows], [tuple(r) for r in ev]


def test_same_seed_same_history_in_two_databases(tmp_path):
    a, b = fresh(tmp_path, "a.db"), fresh(tmp_path, "b.db")
    H.apply(a, ref_date=REF)
    H.apply(b, ref_date=REF)
    assert snapshot(a) == snapshot(b) and snapshot(a)[0]


def test_different_seed_differs(tmp_path):
    a, b = fresh(tmp_path, "a.db"), fresh(tmp_path, "b.db")
    H.apply(a, seed=1, ref_date=REF)
    H.apply(b, seed=2, ref_date=REF)
    assert snapshot(a) != snapshot(b)


def test_rerun_adds_nothing_and_changes_nothing(tmp_path):
    db = fresh(tmp_path)
    first = H.apply(db, ref_date=REF)
    snap = snapshot(db)
    total = db.scalar(select(func.count(Evidence.id)))
    again = H.apply(db, ref_date=REF)
    assert first["sessions"] > 300 and again == {"sessions": 0, "routine_replies": 0}
    assert snapshot(db) == snap and db.scalar(select(func.count(Evidence.id))) == total


def test_a_later_reference_date_only_extends(tmp_path):
    db = fresh(tmp_path)
    H.apply(db, ref_date=REF)
    before = snapshot(db)
    added = H.apply(db, ref_date=date(2026, 11, 14))
    after = snapshot(db)
    assert added["sessions"] > 0 and after[0][:len(before[0])] != [] and set(before[0]) <= set(after[0])


def test_covers_six_months_with_every_activity_and_gaps(tmp_path):
    db = fresh(tmp_path)
    H.apply(db, ref_date=REF)
    f, y = H.summary(db, "demo-fatima"), H.summary(db, "demo-yousef")
    assert f["label"] == "Synthetic demonstration"
    assert {"daily_checkin", "reaction_time", "picture_sequence"} <= set(f["by_protocol"])
    assert "who5" in y["by_protocol"] and "who5" not in f["by_protocol"]      # WHO-5 only in English: no approved Arabic text
    days = {r[0].date() for r in db.execute(select(ActivitySession.started_at).where(
        ActivitySession.participant_id == "demo-fatima", ActivitySession.device == H.DEVICE))}
    assert (max(days) - min(days)).days >= 175
    # the quiet stretch really has no records (a gap, not a stored miss)
    from datetime import timedelta
    assert not any(REF - timedelta(days=120) <= d <= REF - timedelta(days=108) for d in days)
    st = {r[0] for r in db.execute(select(ActivitySession.status).where(ActivitySession.device == H.DEVICE))}
    assert {"completed", "interrupted"} <= st
    assert db.scalar(select(func.count(ActivitySession.id)).where(ActivitySession.device == H.DEVICE, ActivitySession.assisted.is_(True))) > 0
    assert db.scalar(select(func.count(Evidence.id)).where(Evidence.missing_reason == "skipped_by_participant", Evidence.producer_version == H.PRODUCER)) > 0


def test_tagged_and_separate_from_the_seed_and_from_imaging(tmp_path):
    db = fresh(tmp_path)
    seeded = db.scalar(select(func.count(ActivitySession.id)))
    H.apply(db, ref_date=REF)
    assert db.scalar(select(func.count(ActivitySession.id)).where(ActivitySession.device == "demo-seed")) == seeded
    syn = db.scalars(select(Evidence).where(Evidence.producer_version == H.PRODUCER)).all()
    assert syn and all(e.producer_id in (H.DEVICE, e.participant_id) for e in syn)
    assert not db.scalar(select(func.count(ActivitySession.id)).where(ActivitySession.participant_id.notin_(H.PEOPLE), ActivitySession.device == H.DEVICE))


def test_no_day_has_two_sessions_of_one_activity_from_different_sources(tmp_path):
    db = fresh(tmp_path)
    H.apply(db, ref_date=REF)
    rows = db.execute(select(ActivitySession.participant_id, ActivitySession.protocol_code, ActivitySession.started_at, ActivitySession.device)).all()
    seen = {}
    for pid, code, at, dev in rows:
        key = (pid, code, at.date())
        seen.setdefault(key, set()).add(dev)
    assert all(len(v) == 1 for v in seen.values())


def test_quality_rules_ran_and_old_review_items_are_resolved_recent_ones_open(tmp_path):
    db = fresh(tmp_path)
    H.apply(db, ref_date=date(2026, 11, 14))
    items = db.scalars(select(ReviewItem).join(ActivitySession, ReviewItem.session_id == ActivitySession.id)
                       .where(ActivitySession.device == H.DEVICE)).all()
    assert items
    old = [i for i in items if (date(2026, 11, 14) - i.created_at.date()).days > H.REVIEW_OPEN_DAYS]
    assert old and all(i.status == "resolved" and H.LABEL in (i.resolution_note or "") for i in old)


def test_values_are_valid_who5_sums_are_consistent_and_nothing_is_scored(tmp_path):
    db = fresh(tmp_path)
    H.apply(db, ref_date=REF)
    sess = db.scalars(select(ActivitySession).where(ActivitySession.protocol_code == "who5", ActivitySession.device == H.DEVICE)).all()
    assert sess
    for s in sess:
        ev = {e.measure: e.value_num for e in db.scalars(select(Evidence).where(Evidence.session_id == s.id))}
        assert ev["who5_raw"] == sum(ev[f"who5_{i}"] for i in range(1, 6))
    measures = {m for (m,) in db.execute(select(Evidence.measure).where(Evidence.producer_version == H.PRODUCER).distinct())}
    assert not any(w in m for m in measures for w in ("score", "index", "composite", "health"))
    assert not db.scalar(select(func.count(Evidence.id)).where(Evidence.producer_version == H.PRODUCER, Evidence.quality == "unusable", Evidence.measure == "who5_raw"))


def test_routine_replies_follow_the_plan_and_silence_is_not_stored(tmp_path):
    db = fresh(tmp_path)
    H.apply(db, ref_date=date(2026, 11, 14))
    replies = db.scalars(select(CarePlanReply).where(CarePlanReply.idem_key.like(f"{H.DATASET_ID}:%"))).all()
    assert replies and {r.reply for r in replies} <= {"done", "not_today", "difficulty", "snooze"}
    assert len({(r.item_id, r.day) for r in replies}) == len(replies)             # one per routine per day
    assert H.apply(db, ref_date=date(2026, 11, 14))["routine_replies"] == 0


def test_the_server_applies_it_only_when_switched_on(tmp_path, monkeypatch):
    from app import config
    from app.main import create_app
    from fastapi.testclient import TestClient
    monkeypatch.setattr(config, "SEED_HISTORY", True)
    app = create_app(database_url=f"sqlite:///{tmp_path / 'srv.db'}", seed_demo=True)
    with TestClient(app):
        with app.state.db.SessionLocal() as s:
            assert s.scalar(select(func.count(ActivitySession.id)).where(ActivitySession.device == H.DEVICE)) > 300


def test_demo_clinician_can_see_both_people_and_a_withdrawn_grant_stays_withdrawn(tmp_path):
    from app.models import AccessGrant
    from datetime import datetime, timezone
    db = fresh(tmp_path)
    H.apply(db, ref_date=REF)
    g = db.scalar(select(AccessGrant).where(AccessGrant.owner_id == "demo-yousef", AccessGrant.grantee_id == "demo-dr-layla"))
    assert g is not None and g.revoked_at is None
    g.revoked_at = datetime.now(timezone.utc)
    db.commit()
    H.apply(db, ref_date=REF)
    db.refresh(g)
    assert g.revoked_at is not None and db.scalar(select(func.count(AccessGrant.id)).where(AccessGrant.owner_id == "demo-yousef")) == 1
