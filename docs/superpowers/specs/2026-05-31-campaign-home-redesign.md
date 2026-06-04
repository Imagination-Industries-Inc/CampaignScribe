# Campaign Home & Session Redesign — Design (Spec 1 of 2)

- **Status:** Designed (brainstorm 2026-05-31), not yet implemented
- **Repo:** `Imagination-Industries-LLC/CampaignScribe` (`H:\git\CampaignScribe`)
- **Builds on:** #15 Campaign Speakers Library (PR #22, merged). Reuses `app/core/library.py` (campaigns + versioned speakers.json).
- **Decomposition:** This is **Spec 1 = the structure** — unified Campaign Home, campaign-owns-sessions data model, the session flow, and the Edit Profile screen, with **manual per-session voice assignment**. **Spec 2 (separate, later)** adds cross-session **voice-fingerprint auto-match**, which upgrades the manual assignment to zero-touch. Spec 1 must work and ship without Spec 2.

## Problem

The app has **two disconnected worlds** linked only by a free-text name string:

- **DB sessions** (`app/data/db.py`): one recording's work — audio, status, transcripts, summary, per-session discovered speakers. Created by Discover/Transcribe; surfaced in **History** and Build Profile's "Load Session."
- **Library campaigns** (`app/core/library.py`, new in #22): a named, versioned `speakers.json` profile. Surfaced in the **Campaigns** tab + `CampaignPicker`.

Nothing makes a campaign the **owner** of its sessions, so "manage a campaign and its sessions together" is impossible today. Build Profile is **session-first** (leads with a Session/speakers.json loader), which fights the campaign-first mental model and makes "Edit in Build Profile" feel broken. Discover, Build Profile, Campaigns, and History are four scattered entry points for what is really one workflow.

## Locked decisions (brainstorm 2026-05-31)

1. **Campaign is the top-level entity**, owning: a **versioned speaker profile** (the roster), a **list of sessions**, and an **NPC context list**.
2. **Loose/uncategorized sessions allowed** — a session's campaign link is nullable; loose sessions live in an "Uncategorized" bucket and can be filed into a campaign later. (Also covers one-shots.)
3. **Session-local speaker overrides** — a session has its own voice→person mapping layered on the campaign roster. Guests and one-off mislabels stay session-local; an explicit **"Save changes to profile"** promotes a change to a new campaign profile version.
4. **NPCs as summary context** — the campaign keeps a list of named NPCs (name + notes) fed to the summarizer; NPCs are **not** separately diarized.
5. **Ignored voices** — "ignore" is a remembered state on a voice (role = Ignore/Non-Player, not tracked), shown in a **grouped "Ignored voices" section**. Remembered so re-processing keeps them ignored instead of resurfacing them.
6. **Home = Layout A (sessions-forward)** — the campaign's roster collapses to a one-line summary + "Edit profile"; the **session list is the hero** with a prominent "＋ New session." Campaigns + History merge into Home.
7. **Session flow B+** — two lightweight checkpoints around the one expensive pass: **① Confirm who's here** (pre-run; seeds the expected speaker count for cleaner diarization) → **full Transcribe** → **② Review speakers** (post-run; verify auto/manual mapping, catch anyone missed) → Summarize → Refine.
8. **Manual voice assignment in Spec 1** — at ② the user assigns each detected voice-cluster to a roster member via a dropdown (candidates pre-seeded from ①). Cross-session **auto-match is Spec 2**.

## Information architecture / navigation

- **Tabs shrink** to: `Home · Transcribe · Summarize · Refine · ⚙`.
- **Home is the hub** (campaigns + sessions). The **Discover, Build Profile, Campaigns, and History tabs are removed**; their function moves into Home, the **Edit Profile** screen, and the **session flow**.
- **Transcribe / Summarize / Refine remain as screens but become _session-driven_** — they operate on the **active session** set when you open/create one from Home, and lose their `CampaignPicker`/file-browse row (the campaign + speakers come from the session context). Reached via the session's pipeline stepper (or directly, acting on the active session).
- **Edit Profile** is a screen reached from a campaign in Home — not a top-level tab.
- **`CampaignPicker` (from #22) is retired** — choosing a campaign's speakers.json is now implicit in the session context. The `library.py` engine + versioning stay.

## Data model

- **`sessions`**: add `campaign_slug TEXT NULL` (links to a `library` campaign; null = loose/uncategorized). Keep the existing free-text `campaign_name` for display. Migration: existing rows keep `campaign_name`; `campaign_slug` starts null (optionally back-linked by exact name match to an existing library campaign on first run — non-destructive).
- **Session-local speaker mapping**: reuse the existing per-session `speaker_profiles` rows as this recording's voices → assigned person/role/track-or-ignore. Seeded from the campaign roster at ①, edited at ②. This is the override layer; it does not touch the campaign profile unless promoted.
- **Campaign profile** (`library` speakers.json doc): extend the schema with (a) a per-speaker `ignore`/role state and (b) a campaign-level `npcs: [{name, notes}]` list. Versioning is unchanged (immutable timestamped versions + manifest).
- **No voice embeddings in Spec 1** — the campaign roster is people (names/characters/roles/ignored) + NPCs + context. Per-session voice→person assignment is manual. (Spec 2 adds stored fingerprints.)

## Screens

### Home (Layout A) — replaces Campaigns + History
- **Left:** search, campaign list, an **"Uncategorized" bucket** for loose sessions, **＋ New campaign**, **Import existing .json…**.
- **Right (selected campaign):** a one-line **roster summary** (`v4 · 5 players · 1 DM`) + **Edit profile ▸**; the **session list** (state chips: recorded/transcribed/summarized; open) with a prominent **＋ New session**; an NPC summary line. Folds in History's capabilities (per-campaign + Uncategorized session list, search, rename, reopen-into-stage, delete-record).

### Edit Profile — replaces Build Profile (campaign-scoped, versioned)
- **Top bar:** breadcrumb to Home, `Import…`, `Export copy…`, **Save as new version**.
- **Context** field (campaign tone/setting).
- **Players & DM:** one row per voice→person — name, character, class, **role** (Dungeon Master / Player / Non-Player), **include-in-tracking** toggle. **＋ Add player**, **⟲ Discover from audio…** (reuses the diarization + Claude profiling to seed/add voices).
- **Ignored voices:** a separate grouped section — detected-but-ignored voices (dashed/dimmed, `IGNORED` badge), each with **↑ Track as player** to promote.
- **NPCs:** tag list of names (+ notes) — summary context only.
- **Versions** panel: list with labels, **View** / **Set current**.

### Session detail + flow (B+)
- **Header:** breadcrumb (Home / Campaign / Session), editable session name, status pill.
- **Audio:** the recording(s); `＋ add track` (multi-track Discord/Craig); `Import transcript instead…`.
- **Pipeline stepper:** `Recorded → ① Confirm who's here → Transcribe → ② Review speakers → Summarize → Refine`, with artifacts + **Export** at each stage.
- **① Confirm who's here** (pre-run, no analysis): pre-filled from the campaign roster; mark someone **absent tonight**, **＋ add expected guest/player**; **expected-voice count auto-computed** and fed to diarization. **Start transcription ▸**.
- **② Review speakers** (post-run): each detected cluster → **assign to a roster member** (dropdown seeded from ①'s confirmed set) / **guest** / **ignore**. Writes the session-local mapping. **Save changes to profile ▸** promotes a real roster change to a new campaign version.

## Flows mapped to the use-case catalog

- **C (recurring, stable roster — primary):** Home → campaign → **＋ New session** → ① glance + Start → Transcribe → ② quick assign (candidates pre-listed) → Summarize. ~2–3 clicks.
- **A / B (cold start / new campaign):** ＋ New campaign → ＋ New session → *Discover from audio* to seed the roster → build profile → run.
- **D1/D2/D4 (roster changes):** Edit Profile (add player / untrack / change character) → new version; or promote from ②.
- **D3 (guest):** ① add expected guest, or ② mark guest — session-local, not promoted.
- **E (multi-campaign):** Home campaign list scopes everything.
- **F (revisit / re-summarize / batch):** Home session list (History folded in) → reopen a stage.
- **G (refine):** session Refine stage → appends a profile version.
- **H (import/export):** Edit Profile (profile) + session Export (transcript/summary).
- **I3 (multi-track):** audio track list. **I4 (mislabel):** ② override (session-local).

## Reused from #22 (unchanged)
- `app/core/library.py` — campaigns, immutable versioned speakers.json, atomic writes, manifest recovery. Spec 1 extends the **doc schema** (ignore/role state, `npcs`) but not the engine's storage mechanics.

## Out of scope
- **Spec 2:** cross-session voice-fingerprint auto-match (stored pyannote embeddings per roster member; similarity matching; drift handling). Spec 1's ② is fully manual.
- (Backlog) deeper multi-track diarization, OS folder watcher, cross-device sync, recording campaign+version onto each session row beyond `campaign_slug`.

## Risks & mitigations
- **Large restructure** touching many tabs + DB schema → sequence the build (data model + migration → Home → Edit Profile → session flow → stage rewiring → remove old tabs) behind the smoke tests; migration must preserve all existing sessions/campaigns.
- **Manual-assignment friction** for path C until Spec 2 → mitigated by ① pre-seeding the candidate list and expected count; assignment is dropdowns over a short known set.
- **Retiring `CampaignPicker`** right after shipping it in #22 → acceptable; the durable value (engine + versioning) stays, only the picker widget + its wiring are removed.
- **Tab-index churn** again → keep widget-based navigation; the smoke test asserts the new label order.

## Test plan
- **DB migration** (Tk-free): add `campaign_slug`; existing sessions/campaigns intact; loose (null) sessions supported; optional name back-link is non-destructive.
- **Library doc schema:** ignore/role state + `npcs` round-trip through `add_version`/`get_current_doc`; older versions still load.
- **Home (`@pytest.mark.gui`):** campaign list + Uncategorized render; New campaign/session; session list reflects state; reopen-into-stage.
- **Edit Profile (gui):** roster edit; ignored grouping + promote; NPC list; Save-as-new-version + Set current; import/export.
- **Session flow (gui):** ① seeds expected count + candidate set; ② manual assignment writes session-local mapping; Save-to-profile adds a version; loose-session path.
- **Stage screens** operate on the active session (no picker) and accept session context.
- **Smoke:** tab order `Home · Transcribe · Summarize · Refine`; AppWindow constructs; cross-tab navigation is widget-based.
