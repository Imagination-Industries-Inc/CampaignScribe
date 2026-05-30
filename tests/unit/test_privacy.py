"""Tests for app.core.privacy: PRIVACY.md loader, fallback, and constants."""

from __future__ import annotations

from app.core import privacy


def test_load_privacy_text_reads_repo_privacy_md():
    text = privacy.load_privacy_text()
    assert "Stays on your computer" in text
    assert "Anthropic Claude API" in text
    assert "does NOT" in text or "What CampaignScribe does NOT do" in text


def test_load_privacy_text_matches_repo_file():
    # The dialog's single source of truth IS PRIVACY.md.
    from pathlib import Path

    repo_md = Path(privacy.__file__).resolve().parents[2] / "PRIVACY.md"
    assert repo_md.exists()
    assert privacy.load_privacy_text() == repo_md.read_text(encoding="utf-8")


def test_load_privacy_text_falls_back_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(privacy, "_privacy_md_path", lambda: tmp_path / "nope.md")
    text = privacy.load_privacy_text()
    assert "Anthropic" in text
    assert text.strip()  # non-empty embedded fallback


def test_urls_are_https():
    assert privacy.ANTHROPIC_PRIVACY_URL.startswith("https://")
    assert privacy.PRIVACY_MD_URL.startswith("https://")


def test_inline_note_strings_reference_anthropic_and_help():
    for note in (privacy.NOTE_SAMPLES, privacy.NOTE_TRANSCRIPT):
        assert "Anthropic Claude API" in note
        assert "Privacy & Data" in note
