"""known_npcs threads campaign NPCs into the summary prompt sent to Claude."""

from __future__ import annotations

from app.core import summarizer


def _prompt_of(client) -> str:
    assert client.calls, "messages.create was never called"
    return client.calls[0]["messages"][0]["content"]


def test_summarize_part_includes_known_npcs(fake_claude):
    client = fake_claude(["a part summary"])
    summarizer.summarize_part(
        "TRANSCRIPT TEXT",
        {"campaign": "Strahd", "context": "", "players": []},
        "Summarize this session.",
        "sk-test",
        part_number=1,
        known_npcs=["Strahd", "Ireena"],
    )
    prompt = _prompt_of(client)
    assert "Known NPCs in this campaign:" in prompt
    assert "Strahd" in prompt
    assert "Ireena" in prompt


def test_summarize_part_without_npcs_is_unchanged(fake_claude):
    client_a = fake_claude(["s"])
    summarizer.summarize_part(
        "T", {"campaign": "C", "context": "", "players": []}, "P", "sk", part_number=1
    )
    base_prompt = _prompt_of(client_a)
    assert "Known NPCs in this campaign:" not in base_prompt

    client_b = fake_claude(["s"])
    summarizer.summarize_part(
        "T", {"campaign": "C", "context": "", "players": []}, "P", "sk",
        part_number=1, known_npcs=[],
    )
    assert _prompt_of(client_b) == base_prompt  # empty list == None == unchanged


def test_consolidate_includes_known_npcs(fake_claude):
    client = fake_claude(["SESSION NAME: X\n\nbody"])
    summarizer.consolidate_summaries(
        ["part 1 summary"],
        {"campaign": "Strahd", "context": ""},
        "sk-test",
        known_npcs=["Strahd"],
    )
    assert "Strahd" in _prompt_of(client)
    assert "Known NPCs in this campaign:" in _prompt_of(client)
