# Diarization Accuracy Controls — Design

- **Status:** Designed (brainstorm 2026-06-05), spike-gated — not yet implemented
- **Repo:** `Imagination-Industries-LLC/CampaignScribe` (`H:\git\CampaignScribe`). Branch: `feature/diarization-accuracy-controls`.
- **Builds on:** Spec 1 (Campaign Home redesign — the session flow's ① "Confirm who's here" step) and Spec 2 (Voice Auto-Match, single-pass diarization). Touches `app/core/transcriber.py` diarization, `app/ui/session_view.py` (① step), `app/ui/settings_dialog.py`, `app/config.py`.
- **Planning issues:** private board #51 (clustering sensitivity) + #52 (prominent expected-voice count). This one design covers both — they are two levers on the same problem.

## Problem
Real-world use surfaced a diarization-accuracy failure: in one session a speaker was **missed** (their audio got merged into another speaker), and in a later session two people were **merged into one voice**. Both are diarization clustering errors — the pass under-/over-segments speakers. The app today gives the DM almost no usable control over this:

1. **Clustering sensitivity is fixed.** The community-1 pipeline runs with its pretrained clustering settings; there is no way to tell it "split more — you merged two people" or "merge more — you over-split one person."
2. **The expected-voice count is computed but ignored.** The session ① "Confirm who's here" step already derives `expected_speaker_count()` (roster + guests − absent), but the transcribe pass does **not** use it — it reads the Transcribe tab's own spinbox, seeded from a static `default_num_speakers = 5`. The accurate, roster-derived number never reaches diarization, and the current binding (when a count is used) forces **exactly** N speakers.

## What this adds
Two **per-session** levers in the ① step, both feeding the diarization pass:
- **Voice separation** — a stepped Merge↔Split control mapped to the community-1 clustering threshold.
- **Expected-voice count** — the roster-derived count, made prominent and actually wired to the run as a **soft range** (N±1).

## Locked decisions (brainstorm 2026-06-05)
1. **Scope: per-session, in the ① step**, with a **global default in Settings**. Fits the real bug ("this session merged Bob & Carol — bump separation and re-run") without forcing a global change that affects every campaign.
2. **Separation control: labeled steps + show the number.** Primary control is a small stepped `Merge more · Normal · Split more` selector (likely 5 steps); the resulting threshold value is displayed beside it for transparency. "Normal" = the pretrained default (no override).
3. **Count binding: soft range N±1** (`min_speakers = N-1`, `max_speakers = N+1`, clamped ≥1), replacing the current exact `min=max=N`. Forgiving of one present-but-silent person or one surprise voice; the separation knob handles finer correction.
4. **Spike-gates the build** (Task 0, run by the user on real audio) — like the Spec 2 voiceprint spike. No UI is built until the spike confirms the clustering override is real and effective.
5. **Best-effort guards.** A bad threshold override or count must never break a transcribe — every touchpoint falls back to the untouched pipeline / unconstrained diarization, the same guard pattern used for embedding extraction.
6. **No persistence/schema changes.** Both controls are pure inputs to diarization. No DB columns, no store, no migration. The global default is a `config.py` key; the per-session values are in-memory for the run.

## Feasibility (what the code investigation found)
- Community-1's pipeline is `pyannote.audio.pipelines.SpeakerDiarization` with `clustering = VBxClustering` (variational-Bayes, **not** pyannote-3.1's agglomerative clustering). VBx exposes tunable hyperparameters including **`threshold`** (declared search range `Uniform(0.5, 0.8)`), plus `Fa` / `Fb` acoustic factors we will **not** touch.
- The pretrained pipeline ships with `threshold` already instantiated to a trained value. The plan overrides only `threshold` on the loaded inner pipeline (`self._diarize.model`), leaving everything else intact.
- **Direction (to be spike-confirmed):** in cosine-distance clustering, a lower threshold merges fewer clusters → **more speakers (split more)**; a higher threshold → **fewer speakers (merge more)**. VBx refines on top of the threshold-seeded init, so the spike must verify monotonicity and that the effect is visible on real audio before the step→threshold mapping is fixed.

## The spike (Task 0 — gates all UI work)
A throwaway script (deleted after, recipe captured in a `docs/superpowers/notes/` note, exactly as the voiceprint spike did):
1. Load community-1 (reuse `TranscriptionPipeline._load_models` / `self._diarize.model`).
2. Read and print the pretrained `threshold` (the "Normal" anchor).
3. Re-run diarization on a real multi-speaker clip (`H:\CS Test Audio\...`) at a few threshold values around the default (e.g. 0.55 / 0.65 / 0.75), printing the detected speaker count each time.
4. **Pass criteria:** the override takes effect (count changes with threshold), the direction is monotonic (lower → more speakers), and the swing is useful on real audio.
5. **Output:** the concrete step→threshold mapping (which values to attach to `Split more … Merge more`) — feeds Task for the separation control. If the spike fails (threshold has no usable effect on community-1/VBx), stop and re-brainstorm before building UI.

## Architecture / components

### `app/core/transcriber.py`
- New helper to apply a clustering threshold override to the loaded pipeline, best-effort:
  - `set_clustering_threshold(value: float | None)` — when `value is None` (the "Normal" step), leave the pipeline at its pretrained default; otherwise override the inner pipeline's clustering `threshold`. Wrapped in try/except; logs and no-ops on failure so transcription is unaffected.
- `transcribe_file(...)` changes its speaker-count interface so the **caller** owns the window, removing the internal `min=max=num_speakers` exact-lock. Concretely: accept explicit `min_speakers: int | None = None` and `max_speakers: int | None = None` (plus a back-compat `num_speakers` that maps to `min=max=N` so existing callers keep working until updated). Also accept `separation_threshold: float | None = None`, applied via `set_clustering_threshold(...)` before the diarization call. The single-pass `return_embeddings=True` call from Spec 2 is otherwise unchanged.
- **Caller responsibilities:**
  - Session-driven run (SessionView): passes `min_speakers = max(1, N-1)`, `max_speakers = N+1`, plus the session's `separation_threshold`.
  - Standalone Transcribe tab (loose-file, non-session): **keeps its current exact behavior** — passes its spinbox integer as `num_speakers` (→ exact), no separation override. This path's behavior is intentionally unchanged to limit risk.

### `app/ui/session_view.py` (① "Confirm who's here")
- Make the expected-voice count **prominent** (it already renders "Expected voices: N" — promote it to an editable, clearly-labeled field pre-seeded from `expected_speaker_count()`, so it is hard to skip).
- Add the **voice separation** stepped control + threshold readout, defaulting to the Settings global default.
- When the session drives a transcribe, thread both values (`N` → soft range, `separation step` → threshold) into `transcribe_file`.

### `app/ui/settings_dialog.py` + `app/config.py`
- New `config.py` default key: `diarization_separation` (a **step index/name**, not a raw float — portable if the model changes), default = "Normal". (The step→threshold mapping lives in one place, e.g. a small table in `transcriber.py`, fed by the spike.)
- Settings exposes the global default separation (next to the existing discovery model + sample dial).
- `default_num_speakers` remains the loose-file spinbox seed; session-driven runs use the roster-derived count instead.

## Data flow (one session, session-driven)
1. ① "Confirm who's here": count pre-seeds from roster+guests−absent (editable); separation defaults to the Settings global (nudgeable).
2. DM starts the transcribe → SessionView passes `(N, separation_step)` to the run.
3. `transcribe_file`: maps `separation_step → threshold` (None for Normal), calls `set_clustering_threshold(threshold)`, sets `min/max_speakers = N∓1`, runs the single diarization pass.
4. Diarization returns clusters constrained by the count window and the separation threshold → fewer missed/merged voices → flows into ② Review (and Spec 2 voice pre-fill) unchanged.

## Out of scope (deferred)
- Tuning `Fa` / `Fb` or any VBx parameter other than `threshold`.
- Per-campaign persisted separation/count (chosen scope is per-session + global default).
- Auto-suggesting a separation nudge from detected-vs-expected count mismatch (possible future "we found 6 but you expected 4 — split less?" hint).
- Re-running diarization in place from ② without re-transcribing (a re-diarize-only fast path is a separate perf item).

## Risks & mitigations
- **Threshold override may not take on the pretrained VBx pipeline** → the spike resolves this before any UI; best-effort guard means failure degrades to today's behavior, never a crash.
- **Wrong direction / confusing labels** → spike confirms direction; "Normal" is always the safe pretrained default and the prominent anchor.
- **Soft range too loose/tight** → N±1 is a conservative window; the separation knob is the finer tool. Tunable later if needed.
- **Two overlapping controls** (count + separation both affect cluster count) → documented in-UI; the count is the coarse constraint, separation the fine correction. "Normal + accurate count" is the expected default path.

## Test plan
- **Unit (Tk-free, Linux lane):** step→threshold mapping table (each step yields the expected value; "Normal" → None); the N±1 range math (incl. clamp at N=1 and N unset); `set_clustering_threshold` no-ops safely on a stub pipeline that raises.
- **GUI (`@pytest.mark.gui`, Windows lane):** ① renders the prominent count field + separation stepper with the threshold readout; starting a session-driven transcribe passes the right `(min/max_speakers, threshold)` into a stubbed `transcribe_file`.
- **Spike (manual, gating):** real-audio threshold sweep — override takes, direction monotonic, useful swing. Not a committed test; recipe captured in `docs/superpowers/notes/`.
