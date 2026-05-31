"""theme.resolve_variant routing + variant→color, and apply_theme honoring config."""

from __future__ import annotations

import pytest

from app.ui import theme


@pytest.fixture(autouse=True)
def restore_variant():
    prev = theme._active_variant
    yield
    theme.set_theme_variant(prev)


def test_resolve_variant_dark_and_light():
    assert theme.resolve_variant("dark") == "dark"
    assert theme.resolve_variant("light") == "light"


def test_resolve_variant_unknown_defaults_to_dark():
    assert theme.resolve_variant("banana") == "dark"


def test_resolve_variant_system_uses_detector(monkeypatch):
    monkeypatch.setattr(theme, "_detect_system_variant", lambda: "light")
    assert theme.resolve_variant("system") == "light"
    monkeypatch.setattr(theme, "_detect_system_variant", lambda: "dark")
    assert theme.resolve_variant("system") == "dark"


def test_detect_system_variant_returns_valid_variant():
    # On any platform/runner it must return one of the two valid variants
    # (never None, never "system").
    assert theme._detect_system_variant() in ("dark", "light")


def test_set_variant_switches_palette_colors():
    theme.set_theme_variant("light")
    assert theme.color("BG") == "#ECE6D3"
    theme.set_theme_variant("dark")
    assert theme.color("BG") == "#0D1018"
