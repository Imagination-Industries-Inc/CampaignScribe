"""HomeTab: campaign list + Uncategorized, session list, new campaign/session."""

from __future__ import annotations

import tkinter as tk
import types

import pytest

from app.core import library
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


def _app():
    calls = {"edit": [], "session": []}
    app = types.SimpleNamespace(
        notebook=None,
        open_edit_profile=lambda slug: calls["edit"].append(slug),
        open_session=lambda sid: calls["session"].append(sid),
    )
    app._calls = calls
    return app


def test_home_lists_campaigns_and_uncategorized(root):
    db.init_db()
    library.create_campaign("Strahd")
    from app.ui.home_tab import HomeTab

    home = HomeTab(root, _app())
    root.update_idletasks()
    labels = [home.campaign_list.get(i) for i in range(home.campaign_list.size())]
    assert any("Strahd" in s for s in labels)
    assert any("Uncategorized" in s for s in labels)


def test_selecting_campaign_lists_its_sessions(root):
    db.init_db()
    slug = library.create_campaign("Strahd")
    db.create_session("Night 1", campaign_name="Strahd", campaign_slug=slug)
    db.create_session("Loose")
    from app.ui.home_tab import HomeTab

    home = HomeTab(root, _app())
    root.update_idletasks()
    home.select_campaign(slug)
    root.update_idletasks()
    names = [home.session_tree.set(i, "name") for i in home.session_tree.get_children()]
    assert "Night 1" in names
    assert "Loose" not in names


def test_uncategorized_lists_loose_sessions(root):
    db.init_db()
    slug = library.create_campaign("Strahd")
    db.create_session("Night 1", campaign_slug=slug)
    db.create_session("Loose")
    from app.ui.home_tab import HomeTab

    home = HomeTab(root, _app())
    root.update_idletasks()
    home.select_uncategorized()
    root.update_idletasks()
    names = [home.session_tree.set(i, "name") for i in home.session_tree.get_children()]
    assert names == ["Loose"]


def test_new_session_creates_linked_record_and_opens(root):
    db.init_db()
    slug = library.create_campaign("Strahd")
    app = _app()
    from app.ui.home_tab import HomeTab

    home = HomeTab(root, app)
    root.update_idletasks()
    home.select_campaign(slug)
    sid = home._new_session()  # returns the new session id
    assert sid is not None
    assert db.get_session(sid)["campaign_slug"] == slug
    assert app._calls["session"] == [sid]


def test_edit_profile_button_invokes_app(root):
    db.init_db()
    slug = library.create_campaign("Strahd")
    app = _app()
    from app.ui.home_tab import HomeTab

    home = HomeTab(root, app)
    root.update_idletasks()
    home.select_campaign(slug)
    home._edit_profile()
    assert app._calls["edit"] == [slug]


def test_delete_session_record_removes_row(root):
    db.init_db()
    slug = library.create_campaign("Strahd")
    sid = db.create_session("Night 1", campaign_slug=slug)
    from app.ui.home_tab import HomeTab

    home = HomeTab(root, _app())
    root.update_idletasks()
    home.select_campaign(slug)
    home.selected_session_id = sid
    home._delete_session(confirm=False)
    assert db.get_session(sid) is None
