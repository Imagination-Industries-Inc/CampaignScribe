# Voice Auto-Match Implementation Plan (Spec 2 of the Campaign Home redesign)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Task 0 is a feasibility spike that GATES everything — do not start Task 3+ until the spike has passed (see Task 0).**

**Goal:** Give each roster member a per-campaign **voice fingerprint** learned silently from the DM's own ② Review confirmations, then use it to **pre-fill** the ② Review Speakers step in future sessions with a confidence chip per cluster. A fully-recognized roster becomes a one-glance confirm; below-threshold clusters stay manual. No separate enrollment screen, no silent auto-apply (the ② checkpoint always shows).

**Architecture (4 parts, per spec):**
1. **Embedding extraction** (`app/core/transcriber.py`) — during a session's diarization pass, produce one centroid embedding vector per detected speaker cluster (`SPEAKER_xx`). Preferred approach **A** = pyannote `return_embeddings` in the same pass (no extra model/audio pass); fallback **B** = a separate `pyannote.audio.Inference` embedding pass. **The spike (Task 0) decides A vs B.**
2. **Fingerprint store** (`app/core/voiceprints.py`, Tk-free, pure-numpy) — per-campaign, per-person running-mean centroids persisted to `_campaign_dir(slug)/fingerprints.npz` + a `fingerprints.json` sidecar for `count`/`updated_at`.
3. **Matcher** (in `voiceprints.py`) — cosine similarity of this session's cluster embeddings vs the campaign's roster centroids; best person + score per cluster; below threshold → `(None, score)`.
4. **② integration + learning loop** (`app/ui/session_view.py`) — pre-fill the ② dropdowns from `voiceprints.match(...)`; on confirm/override in `_save_session_mapping`, feed each confirmed (cluster embedding → chosen person) back via `voiceprints.update(...)`. Cluster embeddings flow in-memory from the Transcribe worker to the view via a module-level session stash (never persisted to the DB).

**Tech Stack:** Python 3.11, numpy (a transitive dep of the ML stack; **NOT** in `requirements-dev.txt`, so Tk-free numpy tests use `pytest.importorskip("numpy")` to skip on the Linux/CI lane — same convention as `tests/unit/test_audio_sample.py`'s ffmpeg importorskip), Tkinter/ttk + `app.ui.theme`, `app.core.library` for per-campaign dirs, pyannote/whisperx for extraction. stdlib + numpy only in `voiceprints.py` (no Tk).

**Repo:** Imagination-Industries-LLC/CampaignScribe (`H:\git\CampaignScribe`). Branch: `feature/voice-auto-match` (already cut off `main`, which includes the merged Campaign Home redesign / Spec 1, PR #23). Spec 2 of 2. **Interpreter:** `.venv\Scripts\python` (Windows / PowerShell 5.1).

---

## Pre-flight (do first, at execution time)
- [ ] **Confirm branch.** `git branch --show-current` must print `feature/voice-auto-match`. It is already cut off `main` (which contains the merged Spec 1 Campaign Home redesign). `git log --oneline -3` should show the Spec-2 design-spec commit and `main`'s Spec-1 merge below it.
- [ ] **Rebase if behind.** `git fetch origin && git rebase origin/main`. Resolve any conflicts preserving both Spec 1 (on `main`) and this branch's design-spec commit.
- [ ] **Green baseline.** Run `.venv\Scripts\python -m pytest -q`. Confirm a fully green suite BEFORE starting. The Windows lane runs `@pytest.mark.gui` tests; the Linux CI lane installs only `requirements-dev.txt` (no numpy/torch/pyannote), skips `gui`, and runs `tests/unit/` only — which is why numpy-dependent unit tests must `pytest.importorskip("numpy")`.
- [ ] **Read the spec.** `docs/superpowers/specs/2026-06-04-voice-auto-match-design.md` is the source of truth. Every section maps to a task below (see Self-Review spec-coverage map).
- [ ] **Confirm the spike audio.** Task 0 needs a real multi-speaker clip the USER provides; do not invent synthetic audio for it. If no clip is available, the whole feature is blocked at Task 0.

## Ground rules (bake into every task)
- Plain single-line commit messages. **NO** AI-attribution trailer (no `Co-Authored-By`, no "built with Claude Code"). Functional Anthropic Claude API references are fine.
- Never introduce the string "MeetingScribe" anywhere (use "CampaignScribe Script version" only if a predecessor reference is ever needed).
- `ruff check .` AND `ruff format --check .` must be clean before each commit; full `pytest` green before each commit.
- Any subprocess call must pass `creationflags=subprocess.CREATE_NO_WINDOW` (via `app.core.proc.CREATE_NO_WINDOW`). No new subprocess is expected in this feature, but if the spike adds one, it must use the flag.
- **Do NOT touch GPU/device selection** (`transcriber.check_gpu`, `TranscriptionPipeline.device`/`compute_type`). Embedding extraction inherits the pipeline's existing device — never re-probe or override it.
- Reuse `app/core/library.py` (`_campaign_dir(slug)`) for the per-campaign fingerprint folder — do NOT reimplement the library storage layout.
- Tk-free logic → `tests/unit/` (Linux lane; `pytest.importorskip("numpy")` for any numpy test). GUI → `@pytest.mark.gui` with the `root` fixture that `pytest.skip`s on `tk.TclError` (Windows lane).
- Fingerprints are **per-campaign and local-only**; never upload, never write them into the versioned `speakers.json` docs.

## File Structure (created / modified)
| File | Responsibility |
| --- | --- |
| `scripts/spike_embeddings.py` *(create, THROWAWAY — delete after Task 0)* | Standalone feasibility spike: run diarization via approach A (`return_embeddings=True`), print embedding dim D + same-person-high / cross-person-low cosine. Produces the A-vs-B DECISION. Not committed as product code; deleted once the note is written. |
| `docs/superpowers/notes/2026-06-04-voiceprint-spike.md` *(create in Task 0)* | Records the spike DECISION (A confirmed or fall back to B), the measured D, and the exact pyannote API recipe Task 3 must follow. |
| `app/core/voiceprints.py` *(create)* | Tk-free, pure-numpy store + matcher + session stash. `load`, `update`, `get_centroids`, `match`, `stash_session_embeddings`, `pop_session_embeddings`, `peek_session_embeddings`. Persists to `_campaign_dir(slug)/fingerprints.npz` + `fingerprints.json` sidecar. |
| `app/core/transcriber.py` *(modify)* | Add a path that returns `{cluster_label: np.ndarray}` per-cluster embeddings from the diarization pass (approach A per the spike; B noted). Keep `transcribe_file`'s existing return shape; add a `return_embeddings: bool = False` flag that, when set, returns `(segments, embeddings)`. Do NOT touch device/compute selection. |
| `app/config.py` *(modify)* | Add `voice_match_threshold` (0.70) and `voice_match_enabled` (True) to `DEFAULT_CONFIG`. |
| `app/ui/transcribe_tab.py` *(modify)* | In `_worker`, after `_persist_detected_speakers`, when `voice_match_enabled`, extract per-cluster embeddings (Task 3) and `voiceprints.stash_session_embeddings(self.session_id, ...)`. |
| `app/ui/session_view.py` *(modify)* | ② pre-fill from `voiceprints.match(...)` on open (confidence chip per row); learning loop in `_save_session_mapping` feeding `voiceprints.update(...)` for confirmed roster assignments. |
| `PRIVACY.md` *(modify)* | One line: per-campaign voice fingerprints are derived and stored locally only; never uploaded. (Flows automatically into the in-app Help → Privacy & Data dialog, which renders `privacy.load_privacy_text()` = PRIVACY.md.) |
| `tests/unit/test_voiceprints.py` *(create)* | Tk-free, `importorskip numpy`: running-mean update, persistence round-trip, empty/no-file load, multi-person, matcher exact/threshold/empty/ranking, stash/pop cache. |
| `tests/gui/test_session_view_voicematch.py` *(create)* | `@pytest.mark.gui`: ② pre-fills the matched person's StringVar from a stashed synthetic embedding + a known fingerprint; learning loop persists the chosen person on save. |
| `tests/smoke/test_voice_auto_match.py` *(create)* | End-to-end with synthetic embeddings: empty store → confirm → store learns → second match pre-fills. |

---

### Task 0 — Feasibility spike (GATES EVERYTHING; throwaway, NOT TDD; run BY THE USER/operator with real audio)

**This task is NOT test-driven and commits NO product code.** Its deliverable is a DECISION + a recipe note. The agent executing the plan **pauses here**: the spike must be run against a **real multi-speaker clip the USER provides** (synthetic audio will not validate embedding quality). Do not proceed to Task 3+ until this passes.

**Files:** Create `scripts/spike_embeddings.py` (throwaway — delete at the end of this task). Create `docs/superpowers/notes/2026-06-04-voiceprint-spike.md`.

- [ ] **Step 1: Write the spike script.** `scripts/spike_embeddings.py`, a standalone script (run directly with `.venv\Scripts\python scripts\spike_embeddings.py <clip.wav>`). Ground it in `transcriber.py`: build the diarization pipeline the same way `TranscriptionPipeline._load_models` does (`from whisperx.diarize import DiarizationPipeline`, `token=` for the HF token, default model `pyannote/speaker-diarization-community-1`), but reach the underlying pyannote `SpeakerDiarization` pipeline so it can be called with `return_embeddings=True`. Sketch (approach A):
  ```python
  # scripts/spike_embeddings.py  — THROWAWAY. Delete after recording the decision.
  import sys
  import numpy as np
  from app import config
  from whisperx.diarize import DiarizationPipeline

  def main(wav_path: str) -> None:
      hf = config.get_huggingface_token()
      dia = DiarizationPipeline(token=hf, device="cpu")  # device irrelevant for the spike
      inner = getattr(dia, "model", None) or getattr(dia, "pipeline", dia)  # reach pyannote pipeline
      # Approach A: pyannote SpeakerDiarization supports return_embeddings on __call__.
      diarization, embeddings = inner(wav_path, return_embeddings=True)
      # `embeddings` is a (num_speakers, D) array aligned to sorted speaker labels.
      labels = sorted(diarization.labels())
      print("num speakers:", len(labels), "labels:", labels)
      print("embeddings shape:", np.asarray(embeddings).shape)  # -> D is shape[1]
      vecs = {lab: np.asarray(embeddings)[i] for i, lab in enumerate(labels)}

      def cos(a, b):
          a = a / (np.linalg.norm(a) + 1e-9); b = b / (np.linalg.norm(b) + 1e-9)
          return float(a @ b)

      # USER edits these two pairs to point at known same/different speaker labels:
      print("same-ish pairs / cross pairs cosine:")
      for la in labels:
          for lb in labels:
              if la < lb:
                  print(f"  {la} vs {lb}: {cos(vecs[la], vecs[lb]):.3f}")
  if __name__ == "__main__":
      main(sys.argv[1])
  ```
  Note: the exact attribute path to the inner pyannote pipeline and the precise `return_embeddings` return signature are **what the spike is for** — adjust against the installed `pyannote.audio==4.0.4` / `whisperx==3.8.5`. If `return_embeddings` is unsupported or the labels don't line up with the `SPEAKER_xx` labels whisperx assigns, **approach A fails** → record B.
- [ ] **Step 2: Run it (USER / operator, real audio).** `.venv\Scripts\python scripts\spike_embeddings.py <a real multi-speaker clip>`. Confirm: (a) it prints embedding dimension **D**; (b) two segments/speakers known to be the **same** person score a **high** cosine and **different** people score **low** (sanity threshold ~0.70 separates them). This is a **manual validation gate**, not an automated assertion.
- [ ] **Step 3: Record the DECISION.** Write `docs/superpowers/notes/2026-06-04-voiceprint-spike.md` capturing: **A confirmed** (with the exact working API recipe: the inner-pipeline attribute path, the `return_embeddings` call, the shape/label alignment, measured **D**), OR **fall back to B** (separate `pyannote.audio.Inference` embedding model — `pyannote/embedding` or a wespeaker model — crop to each speaker's merged segments, average → centroid; note the extra model + HF license). Task 3 implements whichever the note says.
- [ ] **Step 4: GATE.** State in the note: "Task 3+ may proceed." If the spike did not cleanly separate same vs different speakers at all, STOP and escalate — the feature is infeasible as specified.
- [ ] **Step 5: Delete the throwaway.** `git rm`/delete `scripts/spike_embeddings.py` (it is not product code). Commit ONLY the note: `git add docs/superpowers/notes/2026-06-04-voiceprint-spike.md && git commit -m "Add voiceprint feasibility spike decision note"`.

> **Tasks 1 and 2 are independent of the spike** (pure numpy logic on synthetic vectors) and MAY be implemented in parallel with / before Task 0 completing. **Tasks 3–7 MUST wait for the Task 0 gate.**

---

### Task 1 — `voiceprints.py` store (Tk-free, full TDD; spike-independent)

**Files:** Create `app/core/voiceprints.py`; Create `tests/unit/test_voiceprints.py`.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_voiceprints.py`). `importorskip("numpy")` so the Linux lane skips cleanly.
  ```python
  """voiceprints store: running-mean centroid, persistence, multi-person."""
  from __future__ import annotations

  import pytest

  np = pytest.importorskip("numpy")

  from app.core import library, voiceprints


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
  ```
- [ ] **Step 2: Run (FAIL).** `.venv\Scripts\python -m pytest tests/unit/test_voiceprints.py -q` — fails to import `voiceprints`.
- [ ] **Step 3: Implement** `app/core/voiceprints.py` (store half; matcher comes in Task 2).
  ```python
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
      meta = {p: {"count": int(rec["count"]), "updated_at": rec["updated_at"]} for p, rec in store.items()}
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
  ```
- [ ] **Step 4: Run (PASS).** `.venv\Scripts\python -m pytest tests/unit/test_voiceprints.py -q`. Then `ruff check app/core/voiceprints.py tests/unit/test_voiceprints.py && ruff format --check .`.
- [ ] **Step 5: Commit.** `git add app/core/voiceprints.py tests/unit/test_voiceprints.py && git commit -m "Add per-campaign voiceprint store with running-mean centroids"`.

---

### Task 2 — Matcher + config (Tk-free TDD)

**Files:** Modify `app/core/voiceprints.py`; Modify `app/config.py`; extend `tests/unit/test_voiceprints.py`; extend an existing config test (or add to `tests/unit/test_voiceprints.py`) for the new keys.

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/test_voiceprints.py`).
  ```python
  def test_match_picks_the_right_person():
      slug = _slug()
      voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
      voiceprints.update(slug, "Jo", np.array([0.0, 1.0], dtype="float32"))
      clusters = {"SPEAKER_00": np.array([0.9, 0.1], dtype="float32")}
      res = voiceprints.match(slug, clusters, threshold=0.70)
      person, score = res["SPEAKER_00"]
      assert person == "Mike"
      assert score >= 0.70

  def test_match_below_threshold_returns_none():
      slug = _slug()
      voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
      clusters = {"SPEAKER_00": np.array([0.0, 1.0], dtype="float32")}  # orthogonal -> cos 0
      person, score = voiceprints.match(slug, clusters, threshold=0.70)["SPEAKER_00"]
      assert person is None
      assert score < 0.70

  def test_match_empty_store_all_none():
      slug = _slug()
      clusters = {"SPEAKER_00": np.array([1.0, 0.0], dtype="float32")}
      person, score = voiceprints.match(slug, clusters, threshold=0.70)["SPEAKER_00"]
      assert person is None

  def test_match_ranks_among_multiple_people():
      slug = _slug()
      voiceprints.update(slug, "Mike", np.array([1.0, 0.0, 0.0], dtype="float32"))
      voiceprints.update(slug, "Jo", np.array([0.0, 1.0, 0.0], dtype="float32"))
      voiceprints.update(slug, "Sam", np.array([0.0, 0.0, 1.0], dtype="float32"))
      clusters = {"A": np.array([0.1, 0.95, 0.1], dtype="float32")}
      assert voiceprints.match(slug, clusters, threshold=0.70)["A"][0] == "Jo"
  ```
  And the config keys (Tk-free):
  ```python
  def test_config_has_voice_match_keys():
      from app import config
      assert config.DEFAULT_CONFIG.get("voice_match_enabled") is True
      assert 0.0 < config.DEFAULT_CONFIG.get("voice_match_threshold") < 1.0
  ```
- [ ] **Step 2: Run (FAIL).** `match` undefined; config keys missing.
- [ ] **Step 3: Implement.** Append `match` to `voiceprints.py`:
  ```python
  def match(
      slug: str,
      cluster_embeddings: dict[str, np.ndarray],
      threshold: float,
  ) -> dict[str, tuple[str | None, float]]:
      """Cosine each cluster vs each person centroid. Returns
      {cluster: (best_person, score)}; (None, best_score) when below threshold
      or no fingerprints exist (best_score 0.0 for an empty store)."""
      centroids = get_centroids(slug)
      out: dict[str, tuple[str | None, float]] = {}
      for cid, emb in cluster_embeddings.items():
          q = _normalize(emb)
          best_person: str | None = None
          best_score = 0.0
          for person, cen in centroids.items():
              score = float(q @ cen)  # both L2-normalized -> cosine
              if score > best_score:
                  best_person, best_score = person, score
          out[cid] = (best_person, best_score) if best_score >= threshold else (None, best_score)
      return out
  ```
  Add to `DEFAULT_CONFIG` in `app/config.py` (after `discover_whisper_model`):
  ```python
      "voice_match_enabled": True,
      "voice_match_threshold": 0.70,  # cosine; below -> cluster stays manual in ②
  ```
- [ ] **Step 4: Run (PASS).** `.venv\Scripts\python -m pytest tests/unit/test_voiceprints.py -q`. Then `ruff check . && ruff format --check .`.
- [ ] **Step 5: Commit.** `git add app/core/voiceprints.py app/config.py tests/unit/test_voiceprints.py && git commit -m "Add voiceprint cosine matcher and voice-match config defaults"`.

---

### Task 3 — Embedding extraction in `transcriber.py` (SPIKE-DEPENDENT — gated by Task 0)

**Do not start until the Task 0 note says "Task 3+ may proceed." Implement approach A if the note confirms A; implement B if the note says fall back to B.** Do NOT touch device/compute selection.

**Files:** Modify `app/core/transcriber.py`; add a light Tk-free test to `tests/unit/test_voiceprints.py` or a new `tests/unit/test_transcriber_embeddings.py`.

- [ ] **Step 1: Write the failing test** (light — the real model/audio path is exercised manually via the spike; here we test only the mapping/normalization glue by monkeypatching the diarization call). `importorskip("numpy")`.
  ```python
  def test_transcribe_file_returns_embeddings_mapping(monkeypatch):
      np = pytest.importorskip("numpy")
      from app.core import transcriber

      pipe = transcriber.TranscriptionPipeline.__new__(transcriber.TranscriptionPipeline)
      # Monkeypatch the new helper so we assert label->vector mapping, not models.
      fake = {"SPEAKER_00": np.array([1.0, 0.0], dtype="float32"),
              "SPEAKER_01": np.array([0.0, 1.0], dtype="float32")}
      monkeypatch.setattr(pipe, "_extract_cluster_embeddings", lambda *a, **k: fake, raising=False)
      emb = pipe._extract_cluster_embeddings("ignored.wav")
      assert set(emb) == {"SPEAKER_00", "SPEAKER_01"}
      assert emb["SPEAKER_00"].shape == (2,)
  ```
  > The concrete pyannote call lives behind `_extract_cluster_embeddings`; its exact body comes from the Task 0 note. The automated test stays light (mapping shape only); real-model validation was the spike.
- [ ] **Step 2: Run (FAIL).** `_extract_cluster_embeddings` undefined.
- [ ] **Step 3: Implement (approach A; B is the documented fallback).** Add a private `_extract_cluster_embeddings(self, wav_path, num_speakers=None) -> dict[str, np.ndarray]` that runs the diarization pass with `return_embeddings=True` (per the Task 0 recipe), mapping each pyannote speaker label to the **same `SPEAKER_xx` label whisperx assigns** (the spike confirms the labels align; if not, map via the diarization segment order). Then extend `transcribe_file` to optionally also return embeddings WITHOUT changing the default shape:
  ```python
  def transcribe_file(
      self,
      wav_path: str,
      num_speakers: int | None = None,
      progress: Callable[[str, float], None] | None = None,
      return_embeddings: bool = False,
  ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
      ...  # existing body unchanged, builds `normalized`
      if return_embeddings:
          try:
              embeddings = self._extract_cluster_embeddings(wav_path, num_speakers=num_speakers)
          except Exception as e:
              from app import config as _cfg
              _cfg.log_exception("transcriber._extract_cluster_embeddings", e)
              embeddings = {}
          return normalized, embeddings
      return normalized
  ```
  Approach **A** reuses the same diarization result already produced in `transcribe_file` (no extra model load, no extra audio pass) — prefer storing the diarization output so `_extract_cluster_embeddings` does not re-run diarization. Approach **B** (only if the note says so): a separate `pyannote.audio.Inference` embedding model cropped to each speaker's merged segments, averaged → centroid. Either way: **inherit `self.device`; never re-probe GPU.**
- [ ] **Step 4: Run (PASS).** `.venv\Scripts\python -m pytest tests/unit/test_voiceprints.py tests/unit/test_transcriber_embeddings.py -q`. `ruff check . && ruff format --check .`. (Full real-audio path is validated manually — the spike already did this.)
- [ ] **Step 5: Commit.** `git add app/core/transcriber.py tests/unit/test_transcriber_embeddings.py && git commit -m "Extract per-cluster voice embeddings from the diarization pass"`.

---

### Task 4 — Wire extraction → session (stash/pop cache)

**Files:** Modify `app/core/voiceprints.py` (in-memory session cache); Modify `app/ui/transcribe_tab.py` (`_worker`); extend `tests/unit/test_voiceprints.py` for stash/pop.

- [ ] **Step 1: Write the failing test** (Tk-free; `importorskip numpy` already at top).
  ```python
  def test_stash_and_pop_session_embeddings():
      np = pytest.importorskip("numpy")
      emb = {"SPEAKER_00": np.array([1.0, 0.0], dtype="float32")}
      voiceprints.stash_session_embeddings(42, emb)
      assert voiceprints.peek_session_embeddings(42) is not None  # peek does not consume
      popped = voiceprints.pop_session_embeddings(42)
      assert set(popped) == {"SPEAKER_00"}
      assert voiceprints.pop_session_embeddings(42) is None  # consumed

  def test_pop_missing_session_returns_none():
      assert voiceprints.pop_session_embeddings(999999) is None
  ```
- [ ] **Step 2: Run (FAIL).**
- [ ] **Step 3: Implement.** Module-level dict in `voiceprints.py`:
  ```python
  _SESSION_EMBEDDINGS: dict[int, dict[str, np.ndarray]] = {}

  def stash_session_embeddings(session_id: int, embeddings: dict[str, np.ndarray]) -> None:
      _SESSION_EMBEDDINGS[int(session_id)] = dict(embeddings)

  def peek_session_embeddings(session_id: int) -> dict[str, np.ndarray] | None:
      return _SESSION_EMBEDDINGS.get(int(session_id))

  def pop_session_embeddings(session_id: int) -> dict[str, np.ndarray] | None:
      return _SESSION_EMBEDDINGS.pop(int(session_id), None)
  ```
  Then wire `transcribe_tab._worker`: change the per-file `transcribe_file(...)` call to request embeddings when enabled, accumulate them across files (keep the last non-empty per label), and stash after `_persist_detected_speakers`:
  ```python
  cfg = config.load_config()
  want_emb = bool(cfg.get("voice_match_enabled", True))
  ...
  # inside the per-file loop, replacing the existing transcribe_file call:
  if want_emb:
      segments, file_emb = pipeline.transcribe_file(
          wav, num_speakers=int(self.spk_var.get()), progress=progress_cb,
          return_embeddings=True,
      )
      run_embeddings.update(file_emb or {})
  else:
      segments = pipeline.transcribe_file(
          wav, num_speakers=int(self.spk_var.get()), progress=progress_cb,
      )
  ...
  # after `self._persist_detected_speakers(self.session_id, all_segments)`:
  if want_emb and self.session_id and run_embeddings:
      try:
          from app.core import voiceprints
          voiceprints.stash_session_embeddings(self.session_id, run_embeddings)
      except Exception:
          pass
  ```
  (Initialize `run_embeddings: dict[str, Any] = {}` before the loop.) The worker wiring itself is integration-level — covered by the Task 7 smoke; the unit test here covers stash/pop only.
- [ ] **Step 4: Run (PASS).** `.venv\Scripts\python -m pytest tests/unit/test_voiceprints.py -q`. `ruff check . && ruff format --check .`. Sanity-import the tab: `.venv\Scripts\python -c "import app.ui.transcribe_tab"`.
- [ ] **Step 5: Commit.** `git add app/core/voiceprints.py app/ui/transcribe_tab.py tests/unit/test_voiceprints.py && git commit -m "Stash per-session cluster embeddings from the transcribe worker"`.

---

### Task 5 — ② pre-fill (gui TDD, `session_view.py`)

**Files:** Modify `app/ui/session_view.py`; Create `tests/gui/test_session_view_voicematch.py`.

- [ ] **Step 1: Write the failing gui test** (`@pytest.mark.gui`, reuse the `root` fixture pattern from `tests/gui/test_session_view.py`).
  ```python
  """② pre-fills assignments + learns from confirmations via voiceprints."""
  from __future__ import annotations

  import tkinter as tk
  import types

  import pytest

  np = pytest.importorskip("numpy")

  from app.core import library, speakers_io, voiceprints
  from app.data import db

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
      return types.SimpleNamespace(notebook=None, open_session_stage=lambda *a: None, open_home=lambda: None)


  def _campaign_with_mike():
      slug = library.create_campaign("Strahd")
      doc = speakers_io.profiles_to_speakers_doc(
          "Strahd", "",
          [{"display_name": "Mike", "role": "Player", "include_in_tracking": 1},
           {"display_name": "Jo", "role": "Player", "include_in_tracking": 1}],
          npcs=[])
      library.add_version(slug, doc)
      return slug


  def test_review_prefills_matched_person(root):
      db.init_db()
      slug = _campaign_with_mike()
      voiceprints.update(slug, "Mike", np.array([1.0, 0.0], dtype="float32"))
      sid = db.create_session("Night 2", campaign_slug=slug)
      db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
      db.update_session(sid, num_speakers_detected=1)
      voiceprints.stash_session_embeddings(sid, {"SPEAKER_00": np.array([0.95, 0.05], dtype="float32")})
      from app.ui.session_view import SessionView
      view = SessionView(root, _app(), sid)
      root.update_idletasks()
      assert view._review_vars["SPEAKER_00"].get() == "Mike"  # pre-filled by matcher
  ```
- [ ] **Step 2: Run (FAIL).** `.venv\Scripts\python -m pytest tests/gui/test_session_view_voicematch.py -q` — var is unset.
- [ ] **Step 3: Implement** in `session_view.py`. After `_render_review` builds `self._review_vars`, run the matcher and pre-set vars + a confidence chip. Add a `_prefill_from_voicematch()` and call it at the end of `_render_review` (and keep the cluster→embedding map for Task 6):
  ```python
  from app import config
  from app.core import voiceprints

  def _prefill_from_voicematch(self) -> None:
      self._cluster_embeddings = {}
      self._match_scores = {}
      cfg = config.load_config()
      if not cfg.get("voice_match_enabled", True) or not self.slug:
          return
      emb = voiceprints.peek_session_embeddings(self.session_id)  # peek: keep for learning loop
      if not emb:
          return
      self._cluster_embeddings = emb
      threshold = float(cfg.get("voice_match_threshold", 0.70))
      results = voiceprints.match(self.slug, emb, threshold)
      for cid, (person, score) in results.items():
          self._match_scores[cid] = (person, score)
          var = self._review_vars.get(cid)
          if var is None:
              continue
          if person and score >= threshold and not var.get():
              var.set(person)  # pre-fill; below-threshold rows stay unknown
          chip = f"{person} · {score:.2f}" if person else "⚠ no match"
          lbl = self._chip_labels.get(cid)
          if lbl is not None:
              lbl.config(text=chip)
  ```
  In `_render_review`, add a per-row chip Label (store it in `self._chip_labels[cid]`) next to the combobox, then call `self._prefill_from_voicematch()` after the loop. Keep below-threshold rows blank/unknown.
- [ ] **Step 4: Run (PASS).** `.venv\Scripts\python -m pytest tests/gui/test_session_view_voicematch.py -q`. `ruff check . && ruff format --check .`.
- [ ] **Step 5: Commit.** `git add app/ui/session_view.py tests/gui/test_session_view_voicematch.py && git commit -m "Pre-fill Review speakers from voice fingerprint matches"`.

---

### Task 6 — ② learning loop (gui TDD)

**Files:** Modify `app/ui/session_view.py` (`_save_session_mapping`); extend `tests/gui/test_session_view_voicematch.py`.

- [ ] **Step 1: Write the failing gui test.**
  ```python
  def test_confirm_updates_chosen_person_fingerprint(root):
      db.init_db()
      slug = _campaign_with_mike()  # no Mike fingerprint yet
      sid = db.create_session("Night 1", campaign_slug=slug)
      db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
      db.update_session(sid, num_speakers_detected=1)
      voiceprints.stash_session_embeddings(sid, {"SPEAKER_00": np.array([1.0, 0.0], dtype="float32")})
      from app.ui.session_view import SessionView
      view = SessionView(root, _app(), sid)
      root.update_idletasks()
      view.assign_cluster("SPEAKER_00", "Mike")  # DM confirms/overrides to Mike
      view._save_session_mapping()
      assert "Mike" in voiceprints.get_centroids(slug)  # store learned the chosen person

  def test_guest_and_ignore_do_not_learn(root):
      db.init_db()
      slug = _campaign_with_mike()
      sid = db.create_session("Night 1", campaign_slug=slug)
      db.add_speaker_profile(sid, {"source_speaker_id": "SPEAKER_00", "display_name": ""})
      db.update_session(sid, num_speakers_detected=1)
      voiceprints.stash_session_embeddings(sid, {"SPEAKER_00": np.array([1.0, 0.0], dtype="float32")})
      from app.ui.session_view import GUEST_CHOICE, SessionView
      view = SessionView(root, _app(), sid)
      root.update_idletasks()
      view.assign_cluster("SPEAKER_00", GUEST_CHOICE)  # session-local, must NOT pollute fingerprints
      view._save_session_mapping()
      assert voiceprints.get_centroids(slug) == {}
  ```
- [ ] **Step 2: Run (FAIL).**
- [ ] **Step 3: Implement.** At the end of `_save_session_mapping`, after persisting the DB rows, fold confirmed roster assignments back into the store. Only **real roster persons** (not `GUEST_CHOICE`/`IGNORE_CHOICE`/empty) that have a cluster embedding learn — overrides update the CHOSEN person:
  ```python
  # learning loop — capture only user-confirmed roster assignments (D6)
  if self.slug and config.load_config().get("voice_match_enabled", True):
      emb_map = getattr(self, "_cluster_embeddings", {}) or voiceprints.peek_session_embeddings(self.session_id) or {}
      roster = set(self._roster)  # real campaign people only; guests excluded
      for cid, target in self._collect_assignments().items():
          if target in (IGNORE_CHOICE, GUEST_CHOICE) or not target:
              continue
          if target in roster and cid in emb_map:
              try:
                  voiceprints.update(self.slug, target, emb_map[cid])
              except Exception:
                  pass
      voiceprints.pop_session_embeddings(self.session_id)  # consume once learned
  ```
  Note: guests are intentionally excluded (they are not in `self._roster`), matching the existing promote rule that guests stay session-local.
- [ ] **Step 4: Run (PASS).** `.venv\Scripts\python -m pytest tests/gui/test_session_view_voicematch.py -q`. `ruff check . && ruff format --check .`.
- [ ] **Step 5: Commit.** `git add app/ui/session_view.py tests/gui/test_session_view_voicematch.py && git commit -m "Learn voice fingerprints from confirmed Review speaker assignments"`.

---

### Task 7 — Privacy + final smoke

**Files:** Modify `PRIVACY.md`; Create `tests/smoke/test_voice_auto_match.py`; full-suite + ruff gate.

- [ ] **Step 1: Write the failing smoke test** (`tests/smoke/test_voice_auto_match.py`) — end-to-end with synthetic embeddings (no Tk, no models). `importorskip numpy`.
  ```python
  """End-to-end: empty store -> confirm -> learns -> second match pre-fills."""
  from __future__ import annotations

  import pytest

  np = pytest.importorskip("numpy")

  from app.core import library, voiceprints


  def test_learn_then_recognize_cycle():
      slug = library.create_campaign("Strahd")
      vec = np.array([0.3, 0.4, 0.5], dtype="float32")
      # 1) empty store: no match
      assert voiceprints.match(slug, {"S0": vec}, 0.70)["S0"][0] is None
      # 2) DM confirms S0 = Mike -> store learns
      voiceprints.update(slug, "Mike", vec)
      # 3) next session: a near-identical cluster now recognizes Mike
      near = vec + np.array([0.01, -0.01, 0.0], dtype="float32")
      person, score = voiceprints.match(slug, {"S0": near}, 0.70)["S0"]
      assert person == "Mike" and score >= 0.70
  ```
  Also assert the PRIVACY.md line is present (so the privacy doc stays in sync; the in-app dialog renders this file via `privacy.load_privacy_text()`):
  ```python
  def test_privacy_md_mentions_local_voice_fingerprints():
      from app.core import privacy
      text = privacy.load_privacy_text().lower()
      assert "voice fingerprint" in text or "voice fingerprints" in text
  ```
- [ ] **Step 2: Run (FAIL).** PRIVACY.md line missing → second test fails.
- [ ] **Step 3: Implement.** Add one bullet to PRIVACY.md under "Stays on your computer (never sent anywhere)":
  ```
  - **Per-campaign voice fingerprints** — compact numeric voice signatures derived locally from your own ② Review confirmations to auto-match returning speakers. Stored locally per campaign; never uploaded.
  ```
  No code change to the dialog is needed — `PrivacyDialog` (in `app/ui/app_window.py`) and `privacy.load_privacy_text()` already render PRIVACY.md as the single source of truth.
- [ ] **Step 4: Run (PASS) + full gate.** `.venv\Scripts\python -m pytest tests/smoke/test_voice_auto_match.py -q`, then the **full suite** `.venv\Scripts\python -m pytest -q` (Windows lane = gui + unit + smoke all green), then `ruff check . && ruff format --check .`. Grep the diff for the forbidden string: `git diff main --stat` and confirm no "MeetingScribe" / AI-attribution trailer was introduced.
- [ ] **Step 5: Commit.** `git add PRIVACY.md tests/smoke/test_voice_auto_match.py && git commit -m "Document local-only voice fingerprints and add auto-match smoke test"`.

---

## Self-Review (during planning)

**Spec-coverage map** (every section of `2026-06-04-voice-auto-match-design.md` → task):

| Spec section | Task(s) |
| --- | --- |
| Locked decision 1 (learn from confirmations) | Task 6 |
| Locked decision 2 (pre-fill + confirm, chip, no silent auto-apply) | Task 5 |
| Locked decision 3 (spike first; A preferred, B fallback) | Task 0, Task 3 |
| Locked decision 4 (separate store, NOT in speakers.json) | Task 1 (npz + json sidecar in campaign dir) |
| Locked decision 5 (running-mean centroid + count) | Task 1 (`update`) |
| Locked decision 6 (capture only user-confirmed) | Task 6 (roster-only, guest/ignore excluded) |
| Locked decision 7 (privacy: local-only, PRIVACY.md line) | Task 7 |
| Architecture 1 — embedding extraction (transcriber.py) | Task 3 |
| Architecture 2 — fingerprint store (voiceprints.py) | Task 1 |
| Architecture 3 — matcher (cosine, threshold, unknown) | Task 2 |
| Architecture 4 — ② integration + learning loop | Task 5, Task 6 |
| Embedding-extraction fork (A/B, spike resolves) | Task 0 → Task 3 |
| Data model — `fingerprints.npz` + `fingerprints.json` sidecar, person_key = display name | Task 1 |
| Data model — D agnostic | Task 1 (store agnostic to vector length) |
| Data model — per-cluster embedding in-memory, not persisted to DB | Task 4 (session stash) |
| Config — `voice_match_threshold` (~0.70), `voice_match_enabled` (True) | Task 2 |
| Data flow (one session) steps 1–5 | Task 3 → 4 → 5 → 6 (full cycle) + Task 7 smoke |
| UX — confidence chip / pre-select / override-corrects-chosen | Task 5 (chip) + Task 6 (override updates chosen) |
| UX — Edit Profile "voice learned ✓ (N)" + "forget voice" | **Deferred** — spec marks "nice-to-have / can defer"; `count` is stored (Task 1) so a future indicator/reset is cheap. NOT a task here. |
| Out of scope (multi-embedding, cross-campaign, rename-stable IDs, auto-skip ②, anti-spoofing) | Honored — none implemented; rename-orphan is graceful (next confirmation re-learns). |
| Test plan — unit / gui / spike | Task 1/2/4 (unit) + Task 5/6 (gui) + Task 0 (manual spike) + Task 7 (smoke) |
| Risks — spike gates; pollution mitigated by confirm+running-mean; threshold configurable; local-only; perf (A) | Task 0 gate, Task 6 (confirm-only + running-mean), Task 2 (config), Task 7 (privacy), Task 3 (A preferred) |

**Unmapped spec requirements:** The only spec item not given its own task is the **Edit Profile "voice learned ✓ (N samples)" indicator + "forget voice" reset** — the spec itself labels it "optional, low priority… Nice-to-have; can defer." The plan stores the `count` so it can be added later without rework. Everything else maps to a task.

**Placeholder scan:** No `TODO`/`...`/`PLACEHOLDER` in committed code blocks. The only `...` appears inside the Task 3 `transcribe_file` sketch to denote "existing unchanged body" (explicitly labeled), and the Task 0 spike body is deliberately exploratory and **deleted** before any commit. All test bodies are concrete and runnable.

**Name/type consistency check (verified across all tasks):**
- `voiceprints.update(slug, person, embedding)` — Task 1 def; called in Task 6.
- `voiceprints.match(slug, cluster_embeddings, threshold) -> {cid: (person|None, score)}` — Task 2 def; called in Task 5.
- `voiceprints.get_centroids(slug) -> {person: vec}` — Task 1 def; asserted in Tasks 1/2/6/7.
- `voiceprints.load(slug) -> dict` — Task 1 def; asserted in Task 1.
- `voiceprints.stash_session_embeddings` / `pop_session_embeddings` / `peek_session_embeddings(session_id)` — Task 4 def; used in Task 4 (worker), Task 5 (peek), Task 6 (peek + pop).
- `voice_match_threshold` (0.70) / `voice_match_enabled` (True) — Task 2 in `DEFAULT_CONFIG`; read in Tasks 4/5/6.
- `fingerprints.npz` (raw running-mean vectors) + `fingerprints.json` (count/updated_at sidecar) under `library._campaign_dir(slug)` — Task 1; consistent everywhere.
- `transcribe_file(..., return_embeddings=False)` flag returning `(segments, embeddings)` — Task 3 def; used in Task 4 worker.
- `_extract_cluster_embeddings` — Task 3 private method.
- Reuses existing `IGNORE_CHOICE` / `GUEST_CHOICE` / `self._roster` / `self._review_vars` / `_collect_assignments` from `session_view.py` — verified against the current file.

**numpy / importorskip decision:** numpy is **NOT** listed in `requirements-dev.txt` (it is only a transitive dependency of the ML stack in `requirements.txt`, installed via `setup_venv.bat`). Therefore every Tk-free numpy test (`tests/unit/test_voiceprints.py`, the Task 3 mapping test, the Task 7 smoke) opens with `np = pytest.importorskip("numpy")` so the Linux CI lane (which installs only `requirements-dev.txt`) skips them cleanly — same convention `tests/unit/test_audio_sample.py` uses for `ffmpeg`. The config-keys test (Task 2) and gui tests run without that guard where they don't touch numpy directly (gui tests still importorskip numpy because they build synthetic vectors).
