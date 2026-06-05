"""extract_speaker_embeddings maps DiarizeOutput.speaker_embeddings to sorted labels."""

from __future__ import annotations

import types

import pytest

np = pytest.importorskip("numpy")


class _Ann:
    def labels(self):
        return {"SPEAKER_01", "SPEAKER_00"}  # unordered on purpose


class _Out:
    speaker_diarization = _Ann()
    speaker_embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32")  # row0->SPEAKER_00


def _pipeline_with_fake_pipe(pipe):
    from app.core import transcriber

    tp = transcriber.TranscriptionPipeline.__new__(transcriber.TranscriptionPipeline)
    tp._diarize = types.SimpleNamespace(model=pipe)
    tp._load_models = lambda: None  # skip real model loading
    return tp


def test_extract_maps_embeddings_to_sorted_labels():
    tp = _pipeline_with_fake_pipe(lambda audio: _Out())
    emb = tp.extract_speaker_embeddings({"waveform": None, "sample_rate": 16000})
    assert set(emb) == {"SPEAKER_00", "SPEAKER_01"}
    assert np.allclose(emb["SPEAKER_00"], [1.0, 0.0])  # row 0 == sorted-first label
    assert np.allclose(emb["SPEAKER_01"], [0.0, 1.0])


def test_extract_returns_empty_on_pipeline_error():
    def boom(audio):
        raise RuntimeError("pipeline blew up")

    tp = _pipeline_with_fake_pipe(boom)
    assert tp.extract_speaker_embeddings({"waveform": None, "sample_rate": 16000}) == {}


def test_extract_returns_empty_on_shape_mismatch():
    class _Bad:
        speaker_diarization = _Ann()  # 2 labels
        speaker_embeddings = np.array([[1.0, 0.0]], dtype="float32")  # 1 row

    tp = _pipeline_with_fake_pipe(lambda audio: _Bad())
    assert tp.extract_speaker_embeddings({"waveform": None, "sample_rate": 16000}) == {}
