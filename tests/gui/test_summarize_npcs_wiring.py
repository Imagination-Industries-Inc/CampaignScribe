"""SummarizeTab forwards the active campaign's NPC names into the summarizer."""

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


def test_campaign_npcs_resolves_names(root):
    db.init_db()
    slug = library.create_campaign("Strahd")
    library.add_version(
        slug,
        speakers_io.profiles_to_speakers_doc(
            "Strahd",
            "",
            [],
            npcs=[{"name": "Strahd", "notes": ""}, {"name": "Ireena", "notes": ""}],
        ),
    )
    from app.ui.summarize_tab import SummarizeTab

    tab = SummarizeTab(root, types.SimpleNamespace(notebook=None))
    root.update_idletasks()
    tab.active_slug = slug
    assert tab._campaign_npcs() == ["Strahd", "Ireena"]


def test_campaign_npcs_empty_when_no_slug(root):
    db.init_db()
    from app.ui.summarize_tab import SummarizeTab

    tab = SummarizeTab(root, types.SimpleNamespace(notebook=None))
    root.update_idletasks()
    tab.active_slug = None
    assert tab._campaign_npcs() == []
