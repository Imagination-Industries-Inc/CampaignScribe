# Diarization Accuracy Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the DM two per-session levers in the session ① step — a Merge↔Split "voice separation" control (community-1 VBx clustering threshold) and the roster-derived expected-voice count wired in as a soft N±1 range — both feeding the diarization pass to reduce missed/merged voices.

**Architecture:** Pure mapping logic (step→threshold, count→window) lives as Tk-free module functions in `app/core/transcriber.py`, unit-tested in isolation. `transcribe_file` gains explicit `min_speakers`/`max_speakers`/`separation_threshold` params with a best-effort clustering-threshold override that always falls back to the untouched pipeline. The ① step (`SessionView`) renders the controls and threads their values through the existing `open_session_stage → load_for_session` handoff (in-memory, no DB/schema change). A global default lives in Settings/config.

**Tech Stack:** Python 3.11, Tkinter/ttk, whisperx 3.8 (`DiarizationPipeline`), pyannote community-1 (`SpeakerDiarization` + `VBxClustering`), pytest. Use `.venv\Scripts\python`. Windows/PowerShell 5.1.

**Spec:** `docs/superpowers/specs/2026-06-05-diarization-accuracy-controls-design.md`

---

## Conventions for the implementer
- Run everything with the venv python: `.venv\Scripts\python -m pytest ...`, `.venv\Scripts\python -m ruff ...`.
- Two CI lanes: **Tk-free unit tests** run on Linux (no numpy/ML stack — guard numpy-needing tests with `pytest.importorskip("numpy")`); **GUI tests** are `@pytest.mark.gui` (Windows lane). The mapping functions in Tasks 1–2 are plain-Python (no numpy) and need no importorskip.
- Best-effort rule: any code touching the live pyannote pipeline must be wrapped so a failure logs via `config.log_exception(...)` and degrades to current behavior — it must NEVER break a transcribe.
- Commit messages: plain, single-line, no AI attribution. ruff-clean before every commit (`.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m ruff format .`).

---

## Task 0: Feasibility spike (USER-RUN — gates all UI tasks)

**This is not a code task.** Like the Spec 2 voiceprint spike, the user runs it on real audio. No downstream UI task proceeds until it passes. It produces three outputs the later tasks consume: the **attribute path** to the clustering threshold, the **pretrained default value** (`DEFAULT_THRESHOLD`), and confirmation of **direction + a useful delta**.

**Files:**
- Create (throwaway, deleted after): `scripts/spike_clustering_threshold.py`
- After it passes: capture the recipe in `docs/superpowers/notes/2026-06-05-clustering-threshold-spike.md` and delete the script.

- [ ] **Step 1: Write the spike script**

```python
# scripts/spike_clustering_threshold.py — THROWAWAY. Confirms the community-1 VBx
# clustering threshold can be overridden on the loaded pipeline and that it moves
# the detected-speaker count in the expected direction on real audio.
import sys, warnings
warnings.filterwarnings("ignore")
from app.core.transcriber import TranscriptionPipeline, load  # load=convert handled below
from app import config

WAV = sys.argv[1] if len(sys.argv) > 1 else r"H:\CS Test Audio\testaudio.wav"

p = TranscriptionPipeline(hf_token=config.get_huggingface_token())
p._load_models()
pipe = p._diarize.model                      # inner pyannote SpeakerDiarization
clustering = pipe.clustering                 # VBxClustering
print("clustering type:", type(clustering).__name__)
print("pretrained threshold (DEFAULT_THRESHOLD):", getattr(clustering, "threshold", "MISSING"))

for thr in (None, 0.55, 0.65, 0.75):
    if thr is not None:
        clustering.threshold = float(thr)
    seg, _emb = p._diarize(WAV, return_embeddings=True)
    n = seg["speaker"].nunique() if hasattr(seg, "nunique") else len(set(seg["speaker"]))
    print(f"threshold={thr!s:>5}  ->  {n} speakers")
```

- [ ] **Step 2: USER runs it** — `.venv\Scripts\python scripts\spike_clustering_threshold.py "H:\CS Test Audio\<clip>.wav"` and reports back:
  1. The printed `clustering type` and that `pretrained threshold` is a real float (the `DEFAULT_THRESHOLD`).
  2. The speaker count at each threshold — confirming **lower threshold → more speakers** (monotonic) and that the swing across 0.55→0.75 is at least ±1 speaker (a useful effect).
  3. The exact attribute path that worked (`pipe.clustering.threshold`, or a corrected path if different).

- [ ] **Step 3: Gate decision.**
  - **Pass** (override takes, direction monotonic, useful swing): record `DEFAULT_THRESHOLD`, the attribute path, and a starting delta (default ±0.05 per step) in the notes file; proceed to Task 1.
  - **Fail** (no effect / wrong direction / path missing): STOP. Do not build UI. Re-brainstorm (e.g. a different VBx parameter or approach B). Capture the negative result in the notes file.

- [ ] **Step 4: Capture recipe + delete script**

```bash
git add docs/superpowers/notes/2026-06-05-clustering-threshold-spike.md
git rm scripts/spike_clustering_threshold.py
git commit -m "Spike: confirm community-1 VBx clustering threshold override (notes; script removed)"
```

> The remaining tasks use these provisional constants, to be **calibrated** to the spike's measured numbers in Task 1 Step 3: `DEFAULT_THRESHOLD = 0.65`, attribute path `self._diarize.model.clustering.threshold`, per-step delta `0.05`. The code is complete and runnable with the provisional values; calibration only adjusts the numbers.

---

## Task 1: Separation step→threshold mapping (Tk-free, pure)

**Files:**
- Modify: `app/core/transcriber.py` (add module-level constants + two pure functions near the top, after the imports / `coerce_embeddings`)
- Modify: `app/config.py` (add `diarization_separation` default)
- Test: `tests/unit/test_diarization_separation.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_diarization_separation.py
import pytest
from app.core import transcriber as tr


def test_steps_order_and_membership():
    assert tr.SEPARATION_STEPS == ["Split more", "Split", "Normal", "Merge", "Merge more"]


def test_normal_means_no_override():
    assert tr.separation_threshold("Normal") is None


def test_split_lowers_merge_raises_threshold():
    split = tr.separation_threshold("Split")
    merge = tr.separation_threshold("Merge")
    assert split < tr.DEFAULT_THRESHOLD < merge


def test_more_steps_are_stronger():
    assert tr.separation_threshold("Split more") < tr.separation_threshold("Split")
    assert tr.separation_threshold("Merge more") > tr.separation_threshold("Merge")


def test_threshold_is_clamped_to_bounds():
    for step in tr.SEPARATION_STEPS:
        v = tr.separation_threshold(step)
        if v is not None:
            assert tr.THRESHOLD_BOUNDS[0] <= v <= tr.THRESHOLD_BOUNDS[1]


def test_unknown_step_is_treated_as_normal():
    assert tr.separation_threshold("nonsense") is None


def test_display_value_is_absolute_for_every_step():
    # The UI shows a number for every step, including Normal (the pretrained default).
    assert tr.separation_display_value("Normal") == pytest.approx(tr.DEFAULT_THRESHOLD)
    assert tr.separation_display_value("Split more") < tr.separation_display_value("Merge more")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/unit/test_diarization_separation.py -v`
Expected: FAIL with `AttributeError: module 'app.core.transcriber' has no attribute 'SEPARATION_STEPS'`.

- [ ] **Step 3: Implement the mapping in `app/core/transcriber.py`**

Add near the top of the module (after the imports and `coerce_embeddings`):

```python
# --- Diarization clustering sensitivity (community-1 VBxClustering.threshold) ---
# Calibrated from the Task 0 spike. Lower threshold -> more speakers (split more);
# higher -> fewer (merge more). "Normal" applies NO override (pretrained default).
DEFAULT_THRESHOLD = 0.65            # spike: pretrained VBx threshold (calibrate to measured)
THRESHOLD_BOUNDS = (0.5, 0.8)       # VBx declared search range
_STEP_DELTA = 0.05                  # per-step nudge (calibrate to measured sensitivity)

SEPARATION_STEPS = ["Split more", "Split", "Normal", "Merge", "Merge more"]
_SEPARATION_DELTAS = {
    "Split more": -2 * _STEP_DELTA,
    "Split": -1 * _STEP_DELTA,
    "Normal": 0.0,
    "Merge": +1 * _STEP_DELTA,
    "Merge more": +2 * _STEP_DELTA,
}


def _clamp_threshold(value: float) -> float:
    lo, hi = THRESHOLD_BOUNDS
    return max(lo, min(hi, value))


def separation_display_value(step: str) -> float:
    """Absolute threshold to SHOW for a step (Normal -> the pretrained default)."""
    return _clamp_threshold(DEFAULT_THRESHOLD + _SEPARATION_DELTAS.get(step, 0.0))


def separation_threshold(step: str | None) -> float | None:
    """Threshold to APPLY for a step. 'Normal'/unknown -> None (no override)."""
    if not step or step == "Normal" or step not in _SEPARATION_DELTAS:
        return None
    return _clamp_threshold(DEFAULT_THRESHOLD + _SEPARATION_DELTAS[step])
```

In `app/config.py`, add to `DEFAULT_CONFIG` (after `voice_match_threshold`):

```python
    "diarization_separation": "Normal",  # default voice-separation step (see transcriber.SEPARATION_STEPS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_diarization_separation.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Calibrate to spike output** — replace `DEFAULT_THRESHOLD` and `_STEP_DELTA` with the values measured in Task 0 (if they differ from the provisional 0.65 / 0.05). Re-run the test (it asserts relationships, not absolute numbers, so it stays green). If the spike found a different attribute path, note it for Task 2.

- [ ] **Step 6: Commit**

```bash
git add app/core/transcriber.py app/config.py tests/unit/test_diarization_separation.py
git commit -m "Diarization: separation step->threshold mapping + config default"
```

---

## Task 2: transcriber — count window + best-effort threshold override

**Files:**
- Modify: `app/core/transcriber.py` (`transcribe_file` signature + body around lines 162-202; add `speaker_count_window` module fn + `set_clustering_threshold` method)
- Test: `tests/unit/test_transcriber_diar_inputs.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_transcriber_diar_inputs.py
from app.core import transcriber as tr


def test_count_window_exact_from_num_speakers():
    assert tr.speaker_count_window(num_speakers=5) == {"min_speakers": 5, "max_speakers": 5}


def test_count_window_explicit_range_wins():
    assert tr.speaker_count_window(num_speakers=5, min_speakers=4, max_speakers=6) == {
        "min_speakers": 4,
        "max_speakers": 6,
    }


def test_count_window_unconstrained_is_empty():
    assert tr.speaker_count_window() == {}
    assert tr.speaker_count_window(num_speakers=0) == {}


def test_count_window_clamps_floor_to_one():
    # N-1 must never drop below 1
    assert tr.speaker_count_window(min_speakers=0, max_speakers=2) == {"max_speakers": 2}


def test_run_kwargs_soft_window_from_expected_count():
    kw = tr.diarization_run_kwargs(5, 9, "Split")
    assert kw["min_speakers"] == 4 and kw["max_speakers"] == 6
    assert kw["separation_threshold"] == tr.separation_threshold("Split")


def test_run_kwargs_falls_back_to_exact_count():
    assert tr.diarization_run_kwargs(0, 7, "Normal") == {"num_speakers": 7, "separation_threshold": None}


def test_run_kwargs_floor_at_one():
    kw = tr.diarization_run_kwargs(1, 5, "Normal")
    assert kw["min_speakers"] == 1 and kw["max_speakers"] == 2


class _RaisingClustering:
    @property
    def threshold(self):
        return 0.65

    @threshold.setter
    def threshold(self, v):
        raise RuntimeError("boom")


class _Model:
    def __init__(self, clustering):
        self.clustering = clustering


class _Diarize:
    def __init__(self, clustering):
        self.model = _Model(clustering)


class _OkClustering:
    threshold = 0.65


def test_set_clustering_threshold_applies_value():
    p = tr.TranscriptionPipeline.__new__(tr.TranscriptionPipeline)
    c = _OkClustering()
    p._diarize = _Diarize(c)
    p.set_clustering_threshold(0.58)
    assert c.threshold == 0.58


def test_set_clustering_threshold_none_is_noop():
    p = tr.TranscriptionPipeline.__new__(tr.TranscriptionPipeline)
    c = _OkClustering()
    p._diarize = _Diarize(c)
    p.set_clustering_threshold(None)
    assert c.threshold == 0.65


def test_set_clustering_threshold_swallows_errors():
    p = tr.TranscriptionPipeline.__new__(tr.TranscriptionPipeline)
    p._diarize = _Diarize(_RaisingClustering())
    # Must not raise even though the setter raises.
    p.set_clustering_threshold(0.58)


def test_set_clustering_threshold_no_diarize_is_noop():
    p = tr.TranscriptionPipeline.__new__(tr.TranscriptionPipeline)
    p._diarize = None
    p.set_clustering_threshold(0.58)  # no AttributeError
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/unit/test_transcriber_diar_inputs.py -v`
Expected: FAIL with `AttributeError: module 'app.core.transcriber' has no attribute 'speaker_count_window'`.

- [ ] **Step 3: Implement in `app/core/transcriber.py`**

Add a module-level function (near the mapping functions from Task 1):

```python
def speaker_count_window(
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> dict:
    """Build diarization min/max_speakers kwargs. Explicit min/max win; otherwise
    num_speakers (>0) locks an exact count (min=max=N). Floors at 1. {} = unconstrained."""
    lo = min_speakers if min_speakers is not None else (num_speakers if (num_speakers or 0) > 0 else None)
    hi = max_speakers if max_speakers is not None else (num_speakers if (num_speakers or 0) > 0 else None)
    out: dict[str, int] = {}
    if lo is not None and lo >= 1:
        out["min_speakers"] = int(lo)
    if hi is not None and hi >= 1:
        out["max_speakers"] = int(hi)
    return out


def diarization_run_kwargs(
    expected_count: int | None,
    fallback_count: int,
    separation_step: str | None,
) -> dict:
    """Translate UI run-params into transcribe_file kwargs. expected_count>0 -> soft
    window (max(1,N-1)..N+1); otherwise the exact fallback_count (loose-file spinbox).
    separation_step -> separation_threshold (None for 'Normal'). Pure / Tk-free."""
    n = int(expected_count or 0)
    if n > 0:
        kw: dict = {"min_speakers": max(1, n - 1), "max_speakers": n + 1}
    else:
        kw = {"num_speakers": int(fallback_count)}
    kw["separation_threshold"] = separation_threshold(separation_step)
    return kw
```

Add a method on `TranscriptionPipeline` (place it just above `close`):

```python
    def set_clustering_threshold(self, value: float | None) -> None:
        """Best-effort override of community-1's VBx clustering threshold on the
        loaded pipeline. value=None (or no pipeline) -> leave the pretrained default.
        Never raises: a failure logs and degrades to default clustering."""
        if value is None or self._diarize is None:
            return
        try:
            pipe = getattr(self._diarize, "model", None)
            clustering = getattr(pipe, "clustering", None)
            if clustering is not None and hasattr(clustering, "threshold"):
                clustering.threshold = float(value)
        except Exception as e:  # noqa: BLE001 - clustering override is best-effort
            from app import config

            config.log_exception("transcriber.set_clustering_threshold", e)
```

Change `transcribe_file`'s signature (line ~162) to:

```python
    def transcribe_file(
        self,
        wav_path: str,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        separation_threshold: float | None = None,
        progress: Callable[[str, float], None] | None = None,
    ) -> list[dict[str, Any]]:
```

Replace the diarization kwargs block (current lines ~192-202) with:

```python
        if progress:
            progress("Diarizing speakers", 0.75)
        kwargs: dict[str, Any] = speaker_count_window(num_speakers, min_speakers, max_speakers)
        self.set_clustering_threshold(separation_threshold)
        try:
            diarize_segments, _spk_emb = self._diarize(wav_path, return_embeddings=True, **kwargs)
            self._last_speaker_embeddings = coerce_embeddings(_spk_emb)
        except Exception:  # noqa: BLE001 - embeddings are best-effort; never break the transcript
            diarize_segments = self._diarize(wav_path, **kwargs)  # proven path, no embeddings
            self._last_speaker_embeddings = {}
        result = whisperx.assign_word_speakers(diarize_segments, result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_transcriber_diar_inputs.py -v`
Expected: PASS (12 tests).

- [ ] **Step 5: Commit**

```bash
git add app/core/transcriber.py tests/unit/test_transcriber_diar_inputs.py
git commit -m "Diarization: caller-owned speaker-count window + best-effort clustering override in transcribe_file"
```

---

## Task 3: Settings — global default voice separation

**Files:**
- Modify: `app/ui/settings_dialog.py` (add a "Default voice separation" Combobox; save it in `_save`)
- Test: `tests/gui/test_settings_separation.py` (new, `@pytest.mark.gui`)

- [ ] **Step 1: Write the failing test**

```python
# tests/gui/test_settings_separation.py
import tkinter as tk

import pytest

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


def test_settings_exposes_separation_default(root):
    from app.core import transcriber as tr
    from app.ui import settings_dialog

    dlg = settings_dialog.SettingsDialog(root)
    try:
        assert dlg.separation_var.get() in tr.SEPARATION_STEPS
    finally:
        dlg.destroy()
```

> Fixture pattern matches the existing `tests/gui/test_session_view_voicematch.py` (a per-file `root` fixture that skips when there's no display). `isolate_appdata` (autouse in `tests/conftest.py`) already isolates config, so the dialog reads default config — no extra config fixture needed.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/gui/test_settings_separation.py -v`
Expected: FAIL with `AttributeError: 'SettingsDialog' object has no attribute 'separation_var'`.

- [ ] **Step 3: Implement in `app/ui/settings_dialog.py`**

In `__init__`, after the "Default # speakers" block (around line 75, before the Theme row), add a new row (follow the existing `row += 1` / grid / `**pad` pattern):

```python
        row += 1
        ttk.Label(self, text="Default voice separation:").grid(row=row, column=0, sticky="w", **pad)
        from app.core import transcriber as _tr

        self.separation_var = tk.StringVar(value=cfg.get("diarization_separation", "Normal"))
        ttk.Combobox(
            self,
            textvariable=self.separation_var,
            values=_tr.SEPARATION_STEPS,
            state="readonly",
            width=12,
        ).grid(row=row, column=1, sticky="w", **pad)
        ttk.Label(self, text="(Merge ↔ Split how readily voices are told apart)", style=LBL_DIM).grid(
            row=row, column=2, sticky="w", **pad
        )
```

(If `LBL_DIM` is not already imported in this file, import it from `app.ui.theme`, matching the other tabs.)

In `_save` (around line 167, alongside the other `cfg[...] = ...` assignments before `save_config`):

```python
            cfg["diarization_separation"] = self.separation_var.get()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/gui/test_settings_separation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ui/settings_dialog.py tests/gui/test_settings_separation.py
git commit -m "Settings: default voice-separation control"
```

---

## Task 4: SessionView ① — prominent editable count + separation stepper

**Files:**
- Modify: `app/ui/session_view.py` (replace the count label with an editable spinbox; add the separation stepper + threshold readout; build the run-params dict)
- Test: `tests/gui/test_session_view_diar_controls.py` (new, `@pytest.mark.gui`)

- [ ] **Step 1: Write the failing test**

```python
# tests/gui/test_session_view_diar_controls.py
import tkinter as tk
import types

import pytest

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


def _campaign(name, players):
    from app.core import library, speakers_io

    slug = library.create_campaign(name)
    doc = speakers_io.profiles_to_speakers_doc(
        name,
        "",
        [{"display_name": p, "role": "Player", "include_in_tracking": 1} for p in players],
        npcs=[],
    )
    library.add_version(slug, doc)
    return slug


def test_confirm_step_has_count_and_separation(root):
    from app.core import transcriber as tr
    from app.data import db
    from app.ui.session_view import SessionView

    db.init_db()
    slug = _campaign("Strahd", ["Ann", "Bob", "Cara"])
    sid = db.create_session("Night 1", campaign_slug=slug)
    view = SessionView(root, _app(), sid)
    root.update_idletasks()
    try:
        # Count spinbox pre-seeds from the present roster (3).
        assert int(view.count_spin_var.get()) == 3
        # Separation stepper defaults to the config default and is a valid step.
        assert view.separation_var.get() in tr.SEPARATION_STEPS
        # run_params reflects the controls.
        rp = view._run_params_for_transcribe()
        assert rp["expected_count"] == 3
        assert rp["separation"] in tr.SEPARATION_STEPS
    finally:
        view.destroy()
```

> Mirrors the proven setup in `tests/gui/test_session_view_voicematch.py` (`root` fixture, `_app()` SimpleNamespace, `library.create_campaign` + `speakers_io.profiles_to_speakers_doc` + `library.add_version`, `db.create_session`). `profiles_to_speakers_doc` maps each `display_name` to the `player_name` that `SessionView._load_roster` reads, so the roster is the three players.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/gui/test_session_view_diar_controls.py -v`
Expected: FAIL with `AttributeError: 'SessionView' object has no attribute 'count_spin_var'`.

- [ ] **Step 3: Implement in `app/ui/session_view.py`**

(a) In `__init__`, import the transcriber mapping at the top of the file (with the other `from app.core import ...`):

```python
from app.core import library, speakers_io, transcriber
```

(b) Replace the count label (line 70-71) and add the separation row. Change the ① block so that after `self.confirm_inner` is packed:

```python
        self.count_var = tk.StringVar()
        ttk.Label(confirm_lf, textvariable=self.count_var, style=LBL_DIM).pack(anchor="w", padx=4)

        # Expected-voice count (editable, pre-seeded from the present roster) — drives a soft N±1 window.
        countrow = ttk.Frame(confirm_lf)
        countrow.pack(fill="x", padx=4, pady=2)
        ttk.Label(countrow, text="Expected voices:").pack(side="left")
        self.count_spin_var = tk.IntVar(value=self.expected_speaker_count())
        ttk.Spinbox(countrow, from_=1, to=20, textvariable=self.count_spin_var, width=6).pack(
            side="left", padx=6
        )

        # Voice separation (Merge ↔ Split) — community-1 clustering sensitivity for THIS run.
        seprow = ttk.Frame(confirm_lf)
        seprow.pack(fill="x", padx=4, pady=2)
        ttk.Label(seprow, text="Voice separation:").pack(side="left")
        self.separation_var = tk.StringVar(
            value=config.load_config().get("diarization_separation", "Normal")
        )
        sep_combo = ttk.Combobox(
            seprow,
            textvariable=self.separation_var,
            values=transcriber.SEPARATION_STEPS,
            state="readonly",
            width=12,
        )
        sep_combo.pack(side="left", padx=6)
        self.sep_readout_var = tk.StringVar()
        ttk.Label(seprow, textvariable=self.sep_readout_var, style=LBL_DIM).pack(side="left", padx=4)
        sep_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_sep_readout())
        self._update_sep_readout()
```

Keep the existing `count_var` "Expected voices: N" label as the live roster tally (it updates on present/absent toggles); the new spinbox is the editable value actually used. In `_update_count`, also re-seed the spinbox from the roster tally so toggling presence keeps it in sync:

```python
    def _update_count(self) -> None:
        n = self.expected_speaker_count()
        self.count_var.set(f"Present in roster: {n}")
        if hasattr(self, "count_spin_var"):
            self.count_spin_var.set(n)
```

(c) Add the readout helper and the run-params builder (anywhere in the class, e.g. after `expected_speaker_count`):

```python
    def _update_sep_readout(self) -> None:
        val = transcriber.separation_display_value(self.separation_var.get())
        self.sep_readout_var.set(f"threshold ≈ {val:.2f}")

    def _run_params_for_transcribe(self) -> dict:
        return {
            "expected_count": int(self.count_spin_var.get() or 0),
            "separation": self.separation_var.get(),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/gui/test_session_view_diar_controls.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ui/session_view.py tests/gui/test_session_view_diar_controls.py
git commit -m "SessionView ①: editable expected-count + voice-separation control with threshold readout"
```

---

## Task 5: Thread ① controls into the transcribe run (+ loose-file fallback)

**Files:**
- Modify: `app/ui/session_view.py` (`_start_transcription` passes run-params)
- Modify: `app/ui/app_window.py` (`open_session_stage` forwards run-params)
- Modify: `app/ui/transcribe_tab.py` (`load_for_session` stores run-params; `_worker` uses count window + separation; loose-file path uses the global default separation)
- Test: `tests/gui/test_transcribe_run_params.py` (new, `@pytest.mark.gui`)

- [ ] **Step 1: Write the failing test**

```python
# tests/gui/test_transcribe_run_params.py
import tkinter as tk
import types

import pytest

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


def _campaign(name, players):
    from app.core import library, speakers_io

    slug = library.create_campaign(name)
    doc = speakers_io.profiles_to_speakers_doc(
        name,
        "",
        [{"display_name": p, "role": "Player", "include_in_tracking": 1} for p in players],
        npcs=[],
    )
    library.add_version(slug, doc)
    return slug


def test_start_transcription_hands_run_params_to_stage(root):
    """SessionView ① -> open_session_stage carries the editable count + separation."""
    from app.core import transcriber as tr
    from app.data import db
    from app.ui.session_view import SessionView

    db.init_db()
    slug = _campaign("Strahd", ["Ann", "Bob", "Cara"])
    sid = db.create_session("Night 1", campaign_slug=slug)

    captured = {}
    app = types.SimpleNamespace(
        notebook=None,
        open_home=lambda: None,
        open_session_stage=lambda s, stage, run_params=None: captured.update(
            sid=s, stage=stage, run_params=run_params
        ),
    )
    view = SessionView(root, app, sid)
    root.update_idletasks()
    try:
        view._start_transcription()
        assert captured["stage"] == "transcribe"
        assert captured["run_params"]["expected_count"] == 3
        assert captured["run_params"]["separation"] in tr.SEPARATION_STEPS
    finally:
        view.destroy()
```

> This tests the SessionView→`open_session_stage` handoff (reliably constructable). The TranscribeTab-side translation (`_diar_kwargs_for_run`) is a thin wrapper over `transcriber.diarization_run_kwargs`, already unit-tested in Task 2; its end-to-end effect is covered by manual validation.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/gui/test_transcribe_run_params.py -v`
Expected: FAIL — current `_start_transcription` calls `open_session_stage(sid, "transcribe")` with no `run_params`, so `captured["run_params"]` is `None` (TypeError on subscript / missing key).

- [ ] **Step 3: Implement.**

(a) `app/ui/session_view.py` `_start_transcription` (line 390-393):

```python
    def _start_transcription(self) -> None:
        if self.app and hasattr(self.app, "open_session_stage"):
            self.app.open_session_stage(
                self.session_id, "transcribe", run_params=self._run_params_for_transcribe()
            )
```

(b) `app/ui/app_window.py` `open_session_stage` (line 399): add the param and forward it:

```python
    def open_session_stage(self, session_id: int, stage: str, run_params: dict | None = None):
        from app.data import db

        session = db.get_session(session_id)
        tab = {
            "transcribe": self.transcribe_tab,
            "summarize": self.summarize_tab,
            "refine": self.refine_tab,
        }.get(stage, self.transcribe_tab)
        if session is not None and hasattr(tab, "load_for_session"):
            tab.load_for_session(session, run_params=run_params)
        self.notebook.select(tab)
```

(c) `app/ui/transcribe_tab.py`:
- `load_for_session` (line 182): accept and store run-params.

```python
    def load_for_session(self, session: dict, run_params: dict | None = None) -> None:
        """Set the active session and derive speakers.json from its campaign_slug
        (current library version), falling back to the session's stored path."""
        self._run_params = run_params or {}
        self.session_id = int(session["id"])
        self.active_slug = session.get("campaign_slug")
        self.speakers_path = self._resolve_speakers_path(session)
        self.load_session(self.session_id)
```

- Initialize `self._run_params = {}` in `__init__` (near line 43 where `self.session_id` is set).
- Add the testable derivation helper (anywhere on the class):

```python
    def _diar_kwargs_for_run(self, run_params: dict) -> dict:
        """Thin wrapper: translate ① run-params (or the loose-file spinbox) into
        transcribe_file kwargs via the tested pure helper. Session run -> soft N±1;
        loose-file -> exact spinbox. Separation defaults to the global config step."""
        from app.core import transcriber

        step = run_params.get("separation") or config.load_config().get(
            "diarization_separation", "Normal"
        )
        return transcriber.diarization_run_kwargs(
            run_params.get("expected_count") or 0, int(self.spk_var.get()), step
        )
```

- In `_worker`, replace the transcribe call (lines 433-434):

```python
                segments = pipeline.transcribe_file(
                    wav,
                    progress=progress_cb,
                    **self._diar_kwargs_for_run(getattr(self, "_run_params", {}) or {}),
                )
```

- After the run completes (where the session is done — near the end of `_worker`/`load_session` reset), clear `self._run_params = {}` so a later manual transcribe of the same tab doesn't silently reuse stale ① values. Place `self._run_params = {}` right after the transcribe loop finishes (after line ~469 block that persists detected speakers is fine, or in `load_session`). Simplest: reset at the top of `load_session` so only `load_for_session` (which sets it after) carries params:

```python
    def load_session(self, sid: int, refresh: bool = True) -> None:
        # ... existing body ...
        self.session_id = sid
        # NB: load_for_session sets _run_params AFTER calling us; manual reopen clears it.
        if not getattr(self, "_run_params", None):
            self._run_params = {}
```

> Ordering note: `load_for_session` sets `self._run_params` BEFORE calling `self.load_session`, and `load_session` only resets when empty — so the ① params survive. A manual `load_session` (session dropdown / History reopen) leaves `_run_params` empty → loose-file/default behavior. Verify this ordering holds when implementing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/gui/test_transcribe_run_params.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add app/ui/session_view.py app/ui/app_window.py app/ui/transcribe_tab.py tests/gui/test_transcribe_run_params.py
git commit -m "Wire ① expected-count (soft N±1) + voice separation into the transcribe run"
```

---

## Task 6: Full-suite verification + docs

**Files:**
- Modify: `PRIVACY.md` only if needed (no new data flow — clustering/count are local inputs; likely no change). Skip if nothing applies.

- [ ] **Step 1: Run the full suite**

Run: `.venv\Scripts\python -m pytest -q`
Expected: all green (prior 194 + the new unit/GUI tests; 0 failures). Investigate any failure before proceeding.

- [ ] **Step 2: Lint + format**

Run: `.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m ruff format --check .`
Expected: clean.

- [ ] **Step 3: Grep for leftover exact-lock assumptions**

Run: `git grep -n "min_speakers\|max_speakers\|separation_threshold\|_run_params" app/`
Expected: every diarization caller now goes through `_diar_kwargs_for_run` / `speaker_count_window`; no stray `min=max=N` outside `speaker_count_window`.

- [ ] **Step 4: Commit any doc touch-ups** (if PRIVACY.md changed; otherwise skip).

```bash
git add -A && git commit -m "Diarization accuracy controls: docs touch-ups"
```

---

## Manual validation (USER, after the build)
Real-audio confirmation the automated tests can't cover:
1. Open a session with a roster → ① shows the editable **Expected voices** spinbox (pre-seeded) and the **Voice separation** stepper with a `threshold ≈ 0.NN` readout.
2. Transcribe at **Normal** → result matches today's behavior (no regression).
3. On a session that previously **merged two people**, set separation to **Split** (or **Split more**) and re-transcribe → the two voices separate (more clusters in ② Review).
4. Confirm a bad value can't break a run: the transcript always completes; ② Review and the Spec 2 voice pre-fill still work.

---

## Self-review notes (against the spec)
- Spec "spike-gates the build" → Task 0 (user-run, gating). ✓
- Spec separation control "labeled steps + show the number", per-session in ① + Settings default → Tasks 1/3/4. ✓
- Spec count "roster-derived, prominent, soft N±1, supersedes default-5 for session runs; loose-file unchanged-ish" → Tasks 4/5 (`_diar_kwargs_for_run`). Note: loose-file now also applies the **global default** separation (Normal → None → identical to today); this is a deliberate, consistent refinement of the spec's "no separation override" (which only diverges if the user changes the global default). ✓
- Spec "best-effort, never break transcription" → `set_clustering_threshold` try/except + embeddings fallback unchanged. ✓
- Spec "no DB/schema/migration" → run-params threaded in-memory through `open_session_stage`/`load_for_session`. ✓
