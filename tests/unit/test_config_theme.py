"""theme_mode persists through config save/load and survives the key allowlist."""

from __future__ import annotations

from app import config


def test_theme_mode_default_is_dark():
    assert config.DEFAULT_CONFIG["theme_mode"] == "dark"


def test_theme_mode_persists_through_allowlist():
    config.save_config({"theme_mode": "light"})
    assert config.load_config()["theme_mode"] == "light"


def test_theme_mode_falls_back_to_default_when_absent():
    # A config file missing theme_mode loads the default.
    import json

    config.get_config_path().write_text(json.dumps({"default_num_speakers": 4}), encoding="utf-8")
    assert config.load_config()["theme_mode"] == "dark"
