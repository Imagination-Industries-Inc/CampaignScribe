"""SessionView: ① expected count from roster, ② manual assignment + promote."""

from __future__ import annotations

import tkinter as tk
import types

import pytest

from app.core import library, speakers_io
from app.data import db

pytestmark = pytest.mark.gui


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"No display: {e}")
    r.withdraw()
    try:
        yield r
    finally:
        r.destroy()


def _campaign_with_two_players():
    slug = library.create_campaign("Strahd")
    doc = speakers_io.profiles_to_speakers_doc(
        "Strahd",
        "",
        [
            {"display_name": "Mike", "role": "Player", "include_in_tracking": 1},
            {"display_name": "Jo", "role": "Player", "include_in_tracking": 1},
        ],
        npcs=[],
    )
    library.add_version(slug, doc)
    return slug


def _app():
    return types.SimpleNamespace(
        notebook=None, open_session_stage=lambda sid, stage: None, open_home=lambda: None
    )


def test_confirm_seeds_expected_count_from_roster(root):
    db.init_db()
    slug = _campaign_with_two_players()
    sid = db.create_session("Night 1", campaign_slug=slug)
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    assert view.expected_speaker_count() == 2  # Mike + Jo, none marked absent


def test_marking_absent_reduces_expected_count(root):
    db.init_db()
    slug = _campaign_with_two_players()
    sid = db.create_session("Night 1", campaign_slug=slug)
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    view.mark_absent("Jo")
    assert view.expected_speaker_count() == 1


def test_add_guest_increases_expected_count(root):
    db.init_db()
    slug = _campaign_with_two_players()
    sid = db.create_session("Night 1", campaign_slug=slug)
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    view.add_guest("Visitor")
    assert view.expected_speaker_count() == 3


def test_review_assignment_writes_session_local_mapping(root):
    db.init_db()
    slug = _campaign_with_two_players()
    sid = db.create_session("Night 1", campaign_slug=slug)
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    view.assign_cluster("SPEAKER_00", "Mike")
    view.assign_cluster("SPEAKER_01", "__ignore__")
    view._save_session_mapping()
    rows = db.get_speakers_for_session(sid)
    by_src = {r["source_speaker_id"]: r for r in rows}
    assert by_src["SPEAKER_00"]["display_name"] == "Mike"
    assert by_src["SPEAKER_01"]["include_in_tracking"] == 0


def test_save_to_profile_adds_version(root):
    db.init_db()
    slug = _campaign_with_two_players()
    sid = db.create_session("Night 1", campaign_slug=slug)
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    view.assign_cluster("SPEAKER_00", "Mike")
    before = len(library.list_versions(slug))
    view._save_to_profile()
    assert len(library.list_versions(slug)) == before + 1


def test_loose_session_has_no_roster_but_constructs(root):
    db.init_db()
    sid = db.create_session("One-shot")  # null slug
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    assert view.expected_speaker_count() == 0
