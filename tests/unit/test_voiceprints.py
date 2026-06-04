"""voiceprints store: running-mean centroid, persistence, multi-person."""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from app.core import library, voiceprints  # noqa: E402


def _slug() -> str:
    return library.create_campaign("Strahd")


def test_empty_load_returns_empty_dict():
    slug = _slug()
    assert voiceprints.load(slug) == {}
    assert voiceprints.get_centroids(slug) == {}


def test_update_first_sample_is_the_vector_normalized():
    slug = _slug()
    voiceprints.update(slug, "Mike", np.array([3.0, 4.0], dtype="float32"))  # norm 5
    cen = voiceprints.get_centroids(slug)["Mike"]
    assert np.allclose(np.linalg.norm(cen), 1.0, atol=1e-5)
    assert np.allclose(cen, np.array([0.6, 0.8]), atol=1e-5)


def test_update_running_mean_then_normalize():
    slug = _slug()
    # running mean is computed on the RAW vectors: new = (old*count + emb)/(count+1)
    voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
    voiceprints.update(slug, "Mike", np.array([0.0, 1.0], dtype="float32"))
    cen = voiceprints.get_centroids(slug)["Mike"]
    # raw mean (0.5, 0.5) -> normalized (0.7071, 0.7071)
    assert np.allclose(cen, np.array([0.70710678, 0.70710678]), atol=1e-5)
    assert voiceprints.load(slug)["Mike"]["count"] == 2


def test_persistence_round_trip_across_calls():
    slug = _slug()
    voiceprints.update(slug, "Mike", np.array([1.0, 2.0, 3.0], dtype="float32"))
    reloaded = voiceprints.load(slug)  # fresh read from disk
    assert "Mike" in reloaded
    assert reloaded["Mike"]["count"] == 1
    assert reloaded["Mike"]["centroid"].shape == (3,)


def test_multiple_people_kept_separate():
    slug = _slug()
    voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
    voiceprints.update(slug, "Jo", np.array([0.0, 1.0], dtype="float32"))
    cen = voiceprints.get_centroids(slug)
    assert set(cen) == {"Mike", "Jo"}
    assert np.allclose(cen["Mike"], [1.0, 0.0], atol=1e-5)
