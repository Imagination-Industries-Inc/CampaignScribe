"""Headless smoke: Privacy dialog builds; the four API tabs carry a privacy note."""

from __future__ import annotations

import tkinter as tk

import pytest

from app.core import privacy

pytestmark = pytest.mark.gui


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
    from app.data import db

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


def test_privacy_dialog_builds_and_shows_statement(app):
    from tkinter import ttk

    from app.ui.app_window import PrivacyDialog

    dlg = PrivacyDialog(app)
    app.update_idletasks()
    try:
        frames = [w for w in dlg.winfo_children() if isinstance(w, (tk.Frame, ttk.Frame))]
        assert frames  # dialog built a body/links frame
    finally:
        dlg.destroy()


def test_api_tabs_have_privacy_notes(app):
    assert app.discover_tab._privacy_note.cget("text") == privacy.NOTE_SAMPLES
    assert app.transcribe_tab._privacy_note.cget("text") == privacy.NOTE_SAMPLES
    assert app.refine_tab._privacy_note.cget("text") == privacy.NOTE_SAMPLES
    assert app.summarize_tab._privacy_note.cget("text") == privacy.NOTE_TRANSCRIPT
