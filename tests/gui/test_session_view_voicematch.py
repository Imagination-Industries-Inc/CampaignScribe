"""② pre-fills assignments + confidence chips via voiceprints."""

from __future__ import annotations

import tkinter as tk
import types

import pytest

np = pytest.importorskip("numpy")

from app.core import library, speakers_io, voiceprints  # noqa: E402
from app.data import db  # noqa: E402

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
        open_session_stage=lambda *a: None,
        open_home=lambda: None,
    )


def _campaign_with_mike():
    slug = library.create_campaign("Strahd")
    doc = speakers_io.profiles_to_speakers_doc(
        "Strahd",
        "",
        [
            {"display_name": "Mike", "role": "Player", "include_in_tracking": 1},
            {"display_name": "Jo", "role": "Player", "include_in_tracking": 1},
        ],
        npcs=[],
    )
    library.add_version(slug, doc)
    return slug


def test_review_prefills_from_matcher(root):
    db.init_db()
    slug = _campaign_with_mike()
    mike_vec = np.array([1.0, 0.0, 0.0], dtype="float32")
    voiceprints.update(slug, "Mike", mike_vec)
    sid = db.create_session("Night 1", campaign_slug=slug)
    db.add_speaker_profile(
        sid,
        {"source_speaker_id": "SPEAKER_00", "display_name": "", "include_in_tracking": 1},
    )
    voiceprints.stash_session_embeddings(
        sid, {"SPEAKER_00": np.array([0.98, 0.05, 0.0], dtype="float32")}
    )
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        # SPEAKER_00 should be pre-assigned to Mike (high cosine > 0.70 threshold)
        assignments = view._collect_assignments()
        assert assignments.get("SPEAKER_00") == "Mike"
    finally:
        view.destroy()


def test_review_prefills_matched_person_via_review_var(root):
    """Cross-check: the StringVar itself is set (not just _assignments)."""
    db.init_db()
    slug = _campaign_with_mike()
    voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
    sid = db.create_session("Night 2", campaign_slug=slug)
    db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
    db.update_session(sid, num_speakers_detected=1)
    voiceprints.stash_session_embeddings(
        sid, {"SPEAKER_00": np.array([0.95, 0.05], dtype="float32")}
    )
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        assert view._review_vars["SPEAKER_00"].get() == "Mike"
    finally:
        view.destroy()


def test_below_threshold_cluster_stays_unassigned(root):
    """Cluster orthogonal to Mike's fingerprint must NOT be pre-filled."""
    db.init_db()
    slug = _campaign_with_mike()
    voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
    sid = db.create_session("Night 3", campaign_slug=slug)
    db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
    db.update_session(sid, num_speakers_detected=1)
    # Orthogonal vector -> cosine 0.0, well below threshold 0.70
    voiceprints.stash_session_embeddings(sid, {"SPEAKER_00": np.array([0.0, 1.0], dtype="float32")})
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        assert view._review_vars["SPEAKER_00"].get() == ""
    finally:
        view.destroy()


def test_no_embeddings_stashed_stays_manual(root):
    """When no embeddings are stashed, ② behaves exactly as before (manual)."""
    db.init_db()
    slug = _campaign_with_mike()
    voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
    sid = db.create_session("Night 4", campaign_slug=slug)
    db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
    # Deliberately NOT stashing any embeddings
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        assert view._review_vars["SPEAKER_00"].get() == ""
    finally:
        view.destroy()


def test_no_slug_stays_manual(root):
    """Loose session (no campaign slug) must not crash and must show blank."""
    db.init_db()
    sid = db.create_session("One-shot")  # null slug
    db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
    db.update_session(sid, num_speakers_detected=1)
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        assert view._review_vars.get("SPEAKER_00", tk.StringVar()).get() == ""
    finally:
        view.destroy()


def test_confidence_chip_label_present_when_matched(root):
    """A chip label should exist and contain the person name and score."""
    db.init_db()
    slug = _campaign_with_mike()
    voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
    sid = db.create_session("Night 5", campaign_slug=slug)
    db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
    voiceprints.stash_session_embeddings(
        sid, {"SPEAKER_00": np.array([0.95, 0.05], dtype="float32")}
    )
    from app.ui.session_view import SessionView

    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        lbl = view._chip_labels.get("SPEAKER_00")
        assert lbl is not None, "_chip_labels['SPEAKER_00'] was not created"
        chip_text = lbl.cget("text")
        assert "Mike" in chip_text
        assert "." in chip_text  # score like 0.99
    finally:
        view.destroy()
