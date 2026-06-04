"""Per-campaign voice fingerprints: running-mean centroids, local-only.

Tk-free, pure numpy. Persists to <campaign_dir>/fingerprints.npz (float32
raw running-mean vectors) + a fingerprints.json sidecar (per-person count +
updated_at). Reuses app.core.library for the per-campaign folder. Never
uploaded; never written into the versioned speakers.json docs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.core import library

_NPZ = "fingerprints.npz"
_JSON = "fingerprints.json"


def _paths(slug: str) -> tuple[Path, Path]:
    d = library._campaign_dir(slug)
    return d / _NPZ, d / _JSON


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype="float32")
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v


def load(slug: str) -> dict[str, dict[str, Any]]:
    """Return {person: {"centroid": float32[D] (L2-normalized), "raw": float32[D],
    "count": int, "updated_at": iso}}. Empty dict when no store exists."""
    npz_path, json_path = _paths(slug)
    if not npz_path.exists():
        return {}
    meta: dict[str, Any] = {}
    if json_path.exists():
        try:
            meta = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
    out: dict[str, dict[str, Any]] = {}
    with np.load(npz_path) as data:
        for person in data.files:
            raw = np.asarray(data[person], dtype="float32")
            m = meta.get(person, {})
            out[person] = {
                "centroid": _normalize(raw),
                "raw": raw,
                "count": int(m.get("count", 1)),
                "updated_at": m.get("updated_at", ""),
            }
    return out


def _save(slug: str, store: dict[str, dict[str, Any]]) -> None:
    npz_path, json_path = _paths(slug)
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {p: np.asarray(rec["raw"], dtype="float32") for p, rec in store.items()}
    np.savez(npz_path, **arrays)
    meta = {
        p: {"count": int(rec["count"]), "updated_at": rec["updated_at"]} for p, rec in store.items()
    }
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def update(slug: str, person: str, embedding: np.ndarray) -> None:
    """Incrementally fold one cluster embedding into person's running-mean
    centroid: new_raw = (old_raw*count + emb) / (count+1). Stored normalized
    for cosine via get_centroids."""
    emb = np.asarray(embedding, dtype="float32")
    store = load(slug)
    rec = store.get(person)
    if rec is None:
        new_raw, new_count = emb.copy(), 1
    else:
        count = int(rec["count"])
        new_raw = (rec["raw"] * count + emb) / (count + 1)
        new_count = count + 1
    store[person] = {
        "centroid": _normalize(new_raw),
        "raw": new_raw,
        "count": new_count,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(slug, store)


def get_centroids(slug: str) -> dict[str, np.ndarray]:
    """{person: L2-normalized centroid vector} for cosine matching."""
    return {p: rec["centroid"] for p, rec in load(slug).items()}
