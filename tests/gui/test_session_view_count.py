# tests/gui/test_session_view_count.py
import tkinter as tk
import types

import pytest

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
    return types.SimpleNamespace(
        notebook=None,
        open_session_stage=lambda *a, **k: None,
        open_home=lambda: None,
    )


def _campaign(name, players):
    from app.core import library, speakers_io

    slug = library.create_campaign(name)
    doc = speakers_io.profiles_to_speakers_doc(
        name,
        "",
        [{"display_name": p, "role": "Player", "include_in_tracking": 1} for p in players],
        npcs=[],
    )
    library.add_version(slug, doc)
    return slug


def test_confirm_step_has_editable_preseeded_count(root):
    from app.data import db
    from app.ui.session_view import SessionView

    db.init_db()
    slug = _campaign("Strahd", ["Ann", "Bob", "Cara"])
    sid = db.create_session("Night 1", campaign_slug=slug)
    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        # Pre-seeds from the present roster (3) and is editable.
        assert int(view.count_spin_var.get()) == 3
        view.count_spin_var.set(4)
        assert view._run_params_for_transcribe() == {"expected_count": 4}
    finally:
        view.destroy()
