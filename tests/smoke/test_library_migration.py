"""One-time 'import your last speakers.json' migration prompt."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.gui


def _make_window(monkeypatch):
    import tkinter as tk

    monkeypatch.setattr(
        "app.ui.app_window.check_gpu",
        lambda: {
            "recommendation": "cpu_unavailable",
            "torch_version": None,
            "error": "stubbed",
            "smi_gpu_name": None,
        },
    )
    from app.data import db

    db.init_db()
    try:
        from app.ui.app_window import AppWindow

        win = AppWindow()
    except tk.TclError as e:
        pytest.skip(f"No display available for Tk: {e}")
    win.withdraw()
    win.update_idletasks()
    return win


def test_prompt_imports_last_speakers_json_when_accepted(monkeypatch, tmp_path):
    from app import config
    from app.core import library
    from app.ui import app_window

    # a real last_speakers_json on disk, empty library, not yet prompted
    f = tmp_path / "last.json"
    f.write_text(json.dumps({"campaign": "Wildemount", "players": []}), encoding="utf-8")
    cfg = config.load_config()
    cfg["last_speakers_json"] = str(f)
    cfg["library_import_prompted"] = False
    config.save_config(cfg)
    monkeypatch.setattr(app_window.messagebox, "askyesno", lambda *a, **k: True)
    win = _make_window(monkeypatch)
    try:
        win._maybe_offer_library_import()
        slugs = [r["slug"] for r in library.list_campaigns()]
        assert "wildemount" in slugs
        assert config.load_config()["library_import_prompted"] is True
    finally:
        win.destroy()


def test_prompt_declined_marks_prompted_without_importing(monkeypatch, tmp_path):
    from app import config
    from app.core import library
    from app.ui import app_window

    f = tmp_path / "last.json"
    f.write_text(json.dumps({"campaign": "Wildemount", "players": []}), encoding="utf-8")
    cfg = config.load_config()
    cfg["last_speakers_json"] = str(f)
    cfg["library_import_prompted"] = False
    config.save_config(cfg)
    monkeypatch.setattr(app_window.messagebox, "askyesno", lambda *a, **k: False)
    win = _make_window(monkeypatch)
    try:
        win._maybe_offer_library_import()
        assert library.list_campaigns() == []
        assert config.load_config()["library_import_prompted"] is True
    finally:
        win.destroy()


def test_no_prompt_when_already_prompted(monkeypatch, tmp_path):
    from app import config
    from app.core import library
    from app.ui import app_window

    f = tmp_path / "last.json"
    f.write_text(json.dumps({"campaign": "Wildemount", "players": []}), encoding="utf-8")
    cfg = config.load_config()
    cfg["last_speakers_json"] = str(f)
    cfg["library_import_prompted"] = True  # already done
    config.save_config(cfg)
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        return True

    monkeypatch.setattr(app_window.messagebox, "askyesno", _boom)
    win = _make_window(monkeypatch)
    try:
        win._maybe_offer_library_import()
        assert called["n"] == 0  # never asked
        assert library.list_campaigns() == []
    finally:
        win.destroy()


def test_no_prompt_when_campaigns_already_exist(monkeypatch, tmp_path):
    from app import config
    from app.core import library
    from app.ui import app_window

    f = tmp_path / "last.json"
    f.write_text(json.dumps({"campaign": "Wildemount", "players": []}), encoding="utf-8")
    library.create_campaign("Existing")  # library NOT empty
    cfg = config.load_config()
    cfg["last_speakers_json"] = str(f)
    cfg["library_import_prompted"] = False
    config.save_config(cfg)
    called = {"n": 0}
    monkeypatch.setattr(
        app_window.messagebox,
        "askyesno",
        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or True,
    )
    win = _make_window(monkeypatch)
    try:
        win._maybe_offer_library_import()
        assert called["n"] == 0
        # flag is set so we don't keep re-checking on every launch
        assert config.load_config()["library_import_prompted"] is True
    finally:
        win.destroy()
