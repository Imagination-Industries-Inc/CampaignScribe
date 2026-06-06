"""coerce_embeddings converts raw {label: list} dicts to {label: np.ndarray(float32)}."""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")


def test_coerce_embeddings_to_float32_arrays():
    from app.core import transcriber

    out = transcriber.coerce_embeddings({"SPEAKER_00": [1.0, 2.0], "SPEAKER_01": [3.0, 4.0]})
    assert set(out) == {"SPEAKER_00", "SPEAKER_01"}
    assert out["SPEAKER_00"].dtype == np.float32
    assert out["SPEAKER_00"].tolist() == [1.0, 2.0]


def test_coerce_embeddings_empty():
    from app.core import transcriber

    assert transcriber.coerce_embeddings({}) == {}
    assert transcriber.coerce_embeddings(None) == {}
