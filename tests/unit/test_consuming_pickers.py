"""Each consuming tab embeds a CampaignPicker and resolves a campaign path."""

from __future__ import annotations

import tkinter as tk
import types

import pytest

from app.core import library

pytestmark = pytest.mark.gui

DOC = {
    "campaign": "Strahd",
    "context": "",
    "players": [],
    "known_non_players": [],
    "fallback_policy": {},
}


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


def _stub_app():
    return types.SimpleNamespace(notebook=None)


@pytest.mark.parametrize(
    "modpath,clsname",
    [
        ("app.ui.transcribe_tab", "TranscribeTab"),
        ("app.ui.summarize_tab", "SummarizeTab"),
        ("app.ui.refine_tab", "RefineTab"),
    ],
)
def test_tab_has_picker_resolving_campaign(root, modpath, clsname):
    import importlib

    from app.data import db

    db.init_db()
    slug = library.create_campaign("Strahd")
    library.add_version(slug, DOC)
    mod = importlib.import_module(modpath)
    tab = getattr(mod, clsname)(root, _stub_app())
    root.update_idletasks()
    assert hasattr(tab, "picker")
    tab.picker.refresh()
    # selecting the campaign resolves to its current version file
    assert tab.picker.selected_path() == str(library.current_version_path(slug))
