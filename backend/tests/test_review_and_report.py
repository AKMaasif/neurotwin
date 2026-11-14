from conftest import consent, run_reaction


def open_items(client, headers, pid="demo-fatima"):
    return client.get(f"/api/participants/{pid}/review-items", headers=headers).json()


def test_keep_leaves_record_and_label_untouched(client, login):
    dr = login("demo-dr-layla")
    item = open_items(client, dr)[0]
    before = client.get(f"/api/evidence/{item['evidence_id']}", headers=dr).json()["evidence"]
    r = client.post(f"/api/review-items/{item['id']}/resolve", json={"note": "Call mid-task", "decision": "keep"},
                    headers=dr).json()
    assert r["decision"] == "keep"
    after = client.get(f"/api/evidence/{item['evidence_id']}", headers=dr).json()["evidence"]
    assert after["status"] == "current" and after["quality"] == before["quality"]


def test_exclude_session_level_withdraws_whole_session(client, login):
    dr = login("demo-dr-layla")
    item = next(i for i in open_items(client, dr) if i["reason"] == "interrupted_session")
    client.post(f"/api/review-items/{item['id']}/resolve", json={"note": "Too disrupted", "decision": "exclude"},
                headers=dr)
    ev = client.get("/api/participants/demo-fatima/evidence", headers=dr).json()
    in_session = [e for e in ev if e["session_id"] == item["session_id"]]
    assert in_session and all(e["status"] == "withdrawn" for e in in_session)
    assert all("Too disrupted" in e["change_reason"] for e in in_session)


def test_unknown_decision_refused(client, login):
    dr = login("demo-dr-layla")
    item = open_items(client, dr)[0]
    r = client.post(f"/api/review-items/{item['id']}/resolve", json={"note": "x", "decision": "approve"}, headers=dr)
    assert r.status_code == 422


def test_batch_is_all_or_nothing(client, login, yousef):
    dr = login("demo-dr-layla")
    consent(client, yousef)
    run_reaction(client, yousef, valid=2)   # Yousef has not shared with the clinician
    yousef_item = open_items(client, yousef, "demo-yousef")[0]
    fatima_item = open_items(client, dr)[0]
    r = client.post("/api/review-items/resolve-batch",
                    json={"ids": [fatima_item["id"], yousef_item["id"]], "note": "batch", "decision": "keep"}, headers=dr)
    assert r.status_code == 404
    assert any(i["id"] == fatima_item["id"] for i in open_items(client, dr)), "nothing resolved when one fails"
    ok = client.post("/api/review-items/resolve-batch", json={"ids": [fatima_item["id"]], "note": "batch"}, headers=dr)
    assert ok.status_code == 200 and ok.json()[0]["status"] == "resolved"


def test_report_counts_and_audits(client, login):
    dr = login("demo-dr-layla")
    rep = client.get("/api/participants/demo-fatima/report", headers=dr).json()
    assert rep["sessions"]["total"] == 12 and rep["sessions"]["assisted"] == 1
    rt = next(m for m in rep["measures"] if m["measure"] == "rt_median_ms")
    assert rt["records"] == 6 and rt["doubtful"] == 2 and rt["usable"] == 4
    assert all(v["quality"] != "unusable" for v in rt["values"])
    trail = client.get("/api/participants/demo-fatima/audit", headers=dr).json()
    assert any(a["action"] == "report.generated" for a in trail)
    assert "score" not in str(rep).lower()
    rt_change = next(c for c in rep["change"] if c["measure"] == "rt_median_ms")
    assert rt_change["status"] == "insufficient" and rt_change["include_doubtful"] is False


def test_report_needs_access(client, login):
    assert client.get("/api/participants/demo-fatima/report", headers=login("demo-mariam")).status_code == 404


def test_old_database_gets_new_column(tmp_path):
    import sqlite3
    from app.main import create_app
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE review_items (id INTEGER PRIMARY KEY, participant_id VARCHAR(40), evidence_id INTEGER,"
                " session_id INTEGER, reason VARCHAR(60), raised_by VARCHAR(80), status VARCHAR(10),"
                " resolved_by VARCHAR(40), resolution_note VARCHAR(500), created_at DATETIME, resolved_at DATETIME)")
    con.commit(); con.close()
    create_app(database_url=f"sqlite:///{path}", seed_demo=False, serve_frontend=False)
    cols = [r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(review_items)")]
    assert "decision" in cols


def test_old_demo_database_gets_sign_in_details(tmp_path):
    """A database made before passwords existed: demo accounts gain usernames and the demo password."""
    import sqlite3
    from fastapi.testclient import TestClient
    from app.main import create_app
    path = tmp_path / "old-users.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE users (id VARCHAR(40) PRIMARY KEY, display_name VARCHAR(120), role VARCHAR(20),"
                " language VARCHAR(5), is_demo BOOLEAN, created_at DATETIME)")
    con.execute("INSERT INTO users VALUES ('demo-omar', 'Omar', 'family', 'en', 1, '2026-11-01 00:00:00')")
    con.commit(); con.close()
    app = create_app(database_url=f"sqlite:///{path}", seed_demo=True, serve_frontend=False,
                     demo_password="upgrade-demo-password")
    r = TestClient(app).post("/api/auth/login", json={"username": "omar", "password": "upgrade-demo-password"})
    assert r.status_code == 200


def test_old_database_ends_with_every_current_table(tmp_path):
    """Guards the list of later-migration tables in Database.migrate: an old database must end with the same tables as a new one."""
    import sqlite3
    from app.db import Base
    from app.main import create_app
    from app import models  # noqa: F401
    path = tmp_path / "old2.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE review_items (id INTEGER PRIMARY KEY, participant_id VARCHAR(40), evidence_id INTEGER, session_id INTEGER, reason VARCHAR(60),"
                " raised_by VARCHAR(80), status VARCHAR(10), resolved_by VARCHAR(40), resolution_note VARCHAR(500), created_at DATETIME, resolved_at DATETIME)")
    con.commit(); con.close()
    create_app(database_url=f"sqlite:///{path}", seed_demo=False, serve_frontend=False)
    have = {r[0] for r in sqlite3.connect(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(Base.metadata.tables) <= have
