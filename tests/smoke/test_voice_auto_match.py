"""End-to-end: empty store -> confirm learns -> next session pre-fills from the learned fingerprint."""

from __future__ import annotations

import tkinter as tk
import types

import pytest

np = pytest.importorskip("numpy")
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


def _session_with_cluster(slug, cluster, emb):
    from app.core import voiceprints
    from app.data import db

    sid = db.create_session("S", campaign_slug=slug)
    db.add_speaker_profile(
        sid,
        {"source_speaker_id": cluster, "display_name": "", "include_in_tracking": 1},
    )
    voiceprints.stash_session_embeddings(sid, {cluster: np.asarray(emb, dtype="float32")})
    return sid


def test_learn_then_prefill_across_sessions(root):
    from app.core import library, speakers_io, voiceprints
    from app.data import db
    from app.ui.session_view import SessionView

    db.init_db()
    slug = library.create_campaign("Strahd")
    library.add_version(
        slug,
        speakers_io.profiles_to_speakers_doc(
            "Strahd",
            "",
            [{"display_name": "Mike", "role": "Player", "include_in_tracking": 1}],
            npcs=[],
        ),
    )

    # Session 1: no fingerprint yet -> nothing pre-filled; DM confirms SPEAKER_00 = Mike -> learns
    sid1 = _session_with_cluster(slug, "SPEAKER_00", [1.0, 0.0, 0.0])
    v1 = SessionView(root, _app(), sid1)
    root.update_idletasks()
    try:
        # No fingerprints stored yet — cluster must not be pre-filled
        pre = v1._collect_assignments().get("SPEAKER_00")
        assert pre in (None, ""), f"Expected no pre-fill but got {pre!r}"
        v1.assign_cluster("SPEAKER_00", "Mike")
        v1._save_session_mapping()
    finally:
        v1.destroy()

    # After session 1 save, Mike's centroid should now exist in the store
    assert "Mike" in voiceprints.get_centroids(slug), (
        "Session 1 confirm did not learn Mike's fingerprint"
    )

    # Session 2: a DIFFERENT diarization label (SPEAKER_03) but nearly the same voice -> pre-fills Mike
    sid2 = _session_with_cluster(slug, "SPEAKER_03", [0.97, 0.05, 0.0])
    v2 = SessionView(root, _app(), sid2)
    root.update_idletasks()
    try:
        matched = v2._collect_assignments().get("SPEAKER_03")
        assert matched == "Mike", (
            f"Session 2 with a different diarization label should auto-match Mike, got {matched!r}"
        )
    finally:
        v2.destroy()
