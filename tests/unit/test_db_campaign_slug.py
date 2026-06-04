"""sessions.campaign_slug: migration, create/update, and slug filtering."""

from __future__ import annotations

import sqlite3

from app.config import get_db_path
from app.data import db


def test_fresh_db_has_campaign_slug_column():
    db.init_db()
    with sqlite3.connect(str(get_db_path())) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(sessions)")}
    assert "campaign_slug" in cols


def test_create_session_with_slug_persists():
    db.init_db()
    sid = db.create_session("S1", campaign_name="Strahd", campaign_slug="strahd")
    s = db.get_session(sid)
    assert s["campaign_slug"] == "strahd"


def test_create_session_defaults_slug_to_null():
    db.init_db()
    sid = db.create_session("Loose")
    assert db.get_session(sid)["campaign_slug"] is None


def test_update_session_sets_slug():
    db.init_db()
    sid = db.create_session("S1")
    db.update_session(sid, campaign_slug="strahd")
    assert db.get_session(sid)["campaign_slug"] == "strahd"


def test_list_sessions_filters_by_slug():
    db.init_db()
    a = db.create_session("A", campaign_slug="strahd")
    db.create_session("B", campaign_slug="wildemount")
    loose = db.create_session("C")
    got = {s["id"] for s in db.list_sessions(campaign_slug="strahd")}
    assert got == {a}
    loose_ids = {s["id"] for s in db.list_sessions(campaign_slug=db.UNCATEGORIZED)}
    assert loose in loose_ids
    assert a not in loose_ids


def test_list_sessions_no_filter_returns_all():
    db.init_db()
    db.create_session("A", campaign_slug="strahd")
    db.create_session("B")
    assert len(db.list_sessions()) == 2


def test_migration_preserves_existing_rows_and_adds_null_slug(tmp_path, monkeypatch):
    # Simulate a pre-migration (v1) DB: baseline schema WITHOUT campaign_slug.
    dbp = get_db_path()
    dbp.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(dbp)) as c:
        c.execute(
            "CREATE TABLE sessions ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " display_name TEXT NOT NULL DEFAULT 'Untitled Session',"
            " campaign_name TEXT, status TEXT DEFAULT 'new')"
        )
        c.execute("INSERT INTO sessions(display_name, campaign_name) VALUES ('Old', 'Strahd')")
        c.execute("PRAGMA user_version = 1")
        c.commit()
    db.init_db()  # must run _m2 in place, not drop the row
    rows = db.list_sessions()
    assert len(rows) == 1
    assert rows[0]["display_name"] == "Old"
    assert rows[0]["campaign_slug"] is None
