"""End-to-end: back-link migration + create campaign → session → run a stage."""

from __future__ import annotations

import tkinter as tk

import pytest

from app.core import library
from app.data import db

pytestmark = pytest.mark.gui


def test_backlink_links_named_sessions_to_campaigns():
    db.init_db()
    slug = library.create_campaign("Strahd")
    sid = db.create_session(
        "Night 1", campaign_name="strahd"
    )  # null slug, name match (case-insensitive)
    from app.ui import app_window

    app_window.backlink_sessions_to_campaigns()
    assert db.get_session(sid)["campaign_slug"] == slug


def test_backlink_leaves_unmatched_sessions_loose():
    db.init_db()
    sid = db.create_session("One-shot", campaign_name="No Such Campaign")
    from app.ui import app_window

    app_window.backlink_sessions_to_campaigns()
    assert db.get_session(sid)["campaign_slug"] is None


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(
        "app.ui.app_window.check_gpu",
        lambda: {
            "recommendation": "cpu_unavailable",
            "torch_version": None,
            "error": "stub",
            "smi_gpu_name": None,
        },
    )
    db.init_db()
    try:
        from app.ui.app_window import AppWindow

        win = AppWindow()
    except tk.TclError as e:
        pytest.skip(f"No display: {e}")
    win.withdraw()
    win.update_idletasks()
    try:
        yield win
    finally:
        win.destroy()


def test_new_session_runs_through_open_session_stage(app):
    slug = library.create_campaign("Strahd")
    from app.core import speakers_io

    library.add_version(slug, speakers_io.empty_speakers_doc("Strahd"))
    sid = db.create_session("Night 1", campaign_slug=slug)
    app.open_session_stage(sid, "transcribe")
    assert app.transcribe_tab.session_id == sid
    assert app.notebook.select() == str(app.transcribe_tab)
