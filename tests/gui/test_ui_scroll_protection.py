"""UI clipping protection: scroll frames, minsize, and status-bar tooltip."""

from __future__ import annotations

import tkinter as tk
import types

import pytest

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


# ---------------------------------------------------------------------------
# Import-time check (no display required for the import itself)
# ---------------------------------------------------------------------------


def test_tooltip_importable():
    from app.ui.common import Tooltip, add_tooltip  # noqa: F401


# ---------------------------------------------------------------------------
# Tooltip construction (needs a root)
# ---------------------------------------------------------------------------


def test_add_tooltip_returns_tooltip_instance(root):
    from app.ui.common import Tooltip, add_tooltip

    lbl = tk.Label(root, text="hi")
    lbl.pack()
    root.update_idletasks()
    tip = add_tooltip(lbl, "some text")
    assert isinstance(tip, Tooltip)


def test_add_tooltip_callable_text(root):
    from app.ui.common import Tooltip, add_tooltip

    lbl = tk.Label(root, text="hi")
    lbl.pack()
    root.update_idletasks()
    tip = add_tooltip(lbl, lambda: "live text")
    assert isinstance(tip, Tooltip)


# ---------------------------------------------------------------------------
# Stage tabs: _scroll attribute + inner frame
# ---------------------------------------------------------------------------


def _make_app(root):
    """Minimal app namespace that satisfies tab constructors."""
    return types.SimpleNamespace(notebook=None)


def test_transcribe_tab_has_scroll_frame(root):
    db.init_db()
    from app.ui.transcribe_tab import TranscribeTab

    tab = TranscribeTab(root, _make_app(root))
    root.update_idletasks()
    assert hasattr(tab, "_scroll")
    assert tab._scroll.winfo_exists()
    assert tab._scroll.inner.winfo_exists()


def test_summarize_tab_has_scroll_frame(root):
    db.init_db()
    from app.ui.summarize_tab import SummarizeTab

    tab = SummarizeTab(root, _make_app(root))
    root.update_idletasks()
    assert hasattr(tab, "_scroll")
    assert tab._scroll.winfo_exists()
    assert tab._scroll.inner.winfo_exists()


def test_refine_tab_has_scroll_frame(root):
    db.init_db()
    from app.ui.refine_tab import RefineTab

    tab = RefineTab(root, _make_app(root))
    root.update_idletasks()
    assert hasattr(tab, "_scroll")
    assert tab._scroll.winfo_exists()
    assert tab._scroll.inner.winfo_exists()


# ---------------------------------------------------------------------------
# SessionView: _scroll attribute + window still exists
# ---------------------------------------------------------------------------


def test_session_view_has_scroll_frame(root):
    db.init_db()
    sid = db.create_session("Scroll Test")
    from app.ui.session_view import SessionView

    app = types.SimpleNamespace(open_session_stage=lambda *a: None, open_home=lambda: None)
    view = SessionView(root, app, sid)
    root.update_idletasks()
    assert hasattr(view, "_scroll")
    assert view._scroll.winfo_exists()
    assert view._scroll.inner.winfo_exists()
    assert view.winfo_exists()
    view.destroy()


# ---------------------------------------------------------------------------
# EditProfileWindow: minsize is set and window constructs
# ---------------------------------------------------------------------------


def test_edit_profile_window_constructs_and_exists(root):
    from app.core import library, speakers_io

    db.init_db()
    slug = library.create_campaign("MinTest")
    library.add_version(slug, speakers_io.empty_speakers_doc("MinTest"))
    from app.ui.edit_profile_window import EditProfileWindow

    app = types.SimpleNamespace(open_home=lambda: None)
    win = EditProfileWindow(root, app, slug)
    root.update_idletasks()
    assert win.winfo_exists()
    win.destroy()


# ---------------------------------------------------------------------------
# SessionView: minsize is set
# ---------------------------------------------------------------------------


def test_session_view_minsize(root):
    db.init_db()
    sid = db.create_session("Minsize Test")
    from app.ui.session_view import SessionView

    app = types.SimpleNamespace(open_session_stage=lambda *a: None, open_home=lambda: None)
    view = SessionView(root, app, sid)
    root.update_idletasks()
    min_w = view.minsize()[0]
    min_h = view.minsize()[1]
    assert min_w >= 600
    assert min_h >= 480
    view.destroy()
