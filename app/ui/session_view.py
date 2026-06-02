"""Session detail Toplevel: header, audio, pipeline stepper, ① confirm, ② review."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.core import library, speakers_io
from app.data import db
from app.ui.theme import BTN_ACCENT, BTN_GHOST, LBL_DIM, S_2, S_3

IGNORE_CHOICE = "__ignore__"
GUEST_CHOICE = "__guest__"


class SessionView(tk.Toplevel):
    def __init__(self, master, app_window, session_id: int):
        super().__init__(master)
        self.app = app_window
        self.session_id = session_id
        self.session = db.get_session(session_id) or {}
        self.slug = self.session.get("campaign_slug")
        self._roster: list[str] = []  # tracked player names from the profile
        self._absent: set[str] = set()  # names marked absent tonight
        self._guests: list[str] = []  # extra expected guests
        self._assignments: dict[str, str] = {}  # cluster id -> roster name / guest / __ignore__

        self.title(f"Session — {self.session.get('display_name', 'Untitled')}")
        self.geometry("760x640")
        pad = {"padx": S_3, "pady": S_2}

        bar = ttk.Frame(self)
        bar.pack(fill="x", **pad)
        ttk.Button(bar, text="◂ Home", style=BTN_GHOST, command=self._back_home).pack(side="left")
        self.name_var = tk.StringVar(value=self.session.get("display_name", ""))
        ttk.Entry(bar, textvariable=self.name_var, width=40).pack(side="left", padx=S_3)
        ttk.Button(bar, text="Rename", style=BTN_GHOST, command=self._rename).pack(side="left")
        self.status_var = tk.StringVar(value=self.session.get("status", "new"))
        ttk.Label(bar, textvariable=self.status_var, style=LBL_DIM).pack(side="right")

        # Audio
        audio_lf = ttk.LabelFrame(self, text="Audio")
        audio_lf.pack(fill="x", **pad)
        self.audio_box = tk.Listbox(audio_lf, height=3)
        self.audio_box.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ttk.Button(audio_lf, text="＋ add track", style=BTN_GHOST, command=self._add_track).pack(
            side="left", padx=4
        )
        for f in json.loads(self.session.get("source_audio_files") or "[]"):
            self.audio_box.insert("end", f)

        # ① Confirm who's here
        confirm_lf = ttk.LabelFrame(self, text="① Confirm who's here")
        confirm_lf.pack(fill="x", **pad)
        self.confirm_inner = ttk.Frame(confirm_lf)
        self.confirm_inner.pack(fill="x", padx=4, pady=4)
        self.count_var = tk.StringVar()
        ttk.Label(confirm_lf, textvariable=self.count_var, style=LBL_DIM).pack(anchor="w", padx=4)
        crow = ttk.Frame(confirm_lf)
        crow.pack(fill="x", padx=4, pady=4)
        ttk.Button(crow, text="＋ add guest", style=BTN_GHOST, command=self._add_guest_dialog).pack(
            side="left"
        )
        ttk.Button(
            crow,
            text="Start transcription ▸",
            style=BTN_ACCENT,
            command=self._start_transcription,
        ).pack(side="right")

        # ② Review speakers
        review_lf = ttk.LabelFrame(self, text="② Review speakers")
        review_lf.pack(fill="both", expand=True, **pad)
        self.review_inner = ttk.Frame(review_lf)
        self.review_inner.pack(fill="both", expand=True, padx=4, pady=4)
        rrow = ttk.Frame(review_lf)
        rrow.pack(fill="x", padx=4, pady=4)
        ttk.Button(
            rrow,
            text="Save changes to profile ▸",
            style=BTN_GHOST,
            command=self._save_to_profile,
        ).pack(side="right")

        self._load_roster()
        self._render_confirm()
        self._render_review()

    # ---------- roster / ① ----------

    def _load_roster(self) -> None:
        self._roster = []
        if not self.slug:
            return
        try:
            doc = library.get_current_doc(self.slug)
        except Exception:
            return
        self._roster = [
            p.get("player_name", "") for p in doc.get("players", []) if p.get("player_name")
        ]

    def _render_confirm(self) -> None:
        for w in list(self.confirm_inner.winfo_children()):
            w.destroy()
        self._absent_vars: dict[str, tk.BooleanVar] = {}
        for name in self._roster + self._guests:
            var = tk.BooleanVar(value=name not in self._absent)
            self._absent_vars[name] = var
            ttk.Checkbutton(
                self.confirm_inner,
                text=name,
                variable=var,
                command=lambda n=name: self._toggle_present(n),
            ).pack(anchor="w")
        self._update_count()

    def _toggle_present(self, name: str) -> None:
        if self._absent_vars[name].get():
            self._absent.discard(name)
        else:
            self._absent.add(name)
        self._update_count()

    def mark_absent(self, name: str) -> None:
        self._absent.add(name)
        self._render_confirm()

    def add_guest(self, name: str) -> None:
        self._guests.append(name)
        self._render_confirm()
        self._render_review()

    def _add_guest_dialog(self) -> None:
        from tkinter import simpledialog

        name = simpledialog.askstring("Add guest", "Guest name:", parent=self)
        if name and name.strip():
            self.add_guest(name.strip())

    def _update_count(self) -> None:
        self.count_var.set(f"Expected voices: {self.expected_speaker_count()}")

    def expected_speaker_count(self) -> int:
        present = [n for n in (self._roster + self._guests) if n not in self._absent]
        return len(present)

    # ---------- ② review ----------

    def _detected_clusters(self) -> list[str]:
        rows = db.get_speakers_for_session(self.session_id)
        if rows:
            return [r["source_speaker_id"] for r in rows if r.get("source_speaker_id")]
        n = self.session.get("num_speakers_detected") or 0
        return [f"SPEAKER_{i:02d}" for i in range(int(n))]

    def _render_review(self) -> None:
        for w in list(self.review_inner.winfo_children()):
            w.destroy()
        choices = [c for c in (self._roster + self._guests) if c not in self._absent]
        options = choices + [GUEST_CHOICE, IGNORE_CHOICE]
        self._review_vars: dict[str, tk.StringVar] = {}
        for cid in self._detected_clusters():
            row = ttk.Frame(self.review_inner)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=cid, width=16).pack(side="left")
            var = tk.StringVar(value=self._assignments.get(cid, ""))
            self._review_vars[cid] = var
            ttk.Combobox(row, textvariable=var, values=options, state="readonly", width=30).pack(
                side="left"
            )

    def assign_cluster(self, cluster_id: str, target: str) -> None:
        self._assignments[cluster_id] = target
        if hasattr(self, "_review_vars") and cluster_id in self._review_vars:
            self._review_vars[cluster_id].set(target)

    def _collect_assignments(self) -> dict[str, str]:
        out = dict(self._assignments)
        for cid, var in getattr(self, "_review_vars", {}).items():
            if var.get():
                out[cid] = var.get()
        return out

    def _save_session_mapping(self) -> None:
        db.delete_speakers_for_session(self.session_id)
        for cid, target in self._collect_assignments().items():
            ignore = target == IGNORE_CHOICE
            name = "" if target in (IGNORE_CHOICE, GUEST_CHOICE) else target
            db.add_speaker_profile(
                self.session_id,
                {
                    "source_speaker_id": cid,
                    "display_name": name,
                    "role": "Non-Player" if ignore else "Player",
                    "include_in_tracking": 0 if ignore else 1,
                },
            )

    def _save_to_profile(self) -> None:
        self._save_session_mapping()
        if not self.slug:
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "CampaignScribe", "This loose session has no campaign to update."
                ),
            )
            return
        rows = db.get_speakers_for_session(self.session_id)
        try:
            doc = library.get_current_doc(self.slug)
            npcs = doc.get("npcs", [])
            context = doc.get("context", "")
            campaign = doc.get("campaign", "")
        except Exception:
            npcs, context, campaign = [], "", ""
        speakers = [
            {
                "source_speaker_id": r["source_speaker_id"],
                "display_name": r["display_name"],
                "role": r.get("role", "Player"),
                "include_in_tracking": r.get("include_in_tracking", 1),
                "notes": r.get("notes", ""),
            }
            for r in rows
            if r.get("display_name") or not r.get("include_in_tracking", 1)
        ]
        new_doc = speakers_io.profiles_to_speakers_doc(campaign, context, speakers, npcs=npcs)
        library.add_version(self.slug, new_doc, label="from session")
        self.after(
            0,
            lambda: messagebox.showinfo("CampaignScribe", "Saved changes to the campaign profile."),
        )

    # ---------- misc ----------

    def _add_track(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Add audio track(s)",
            filetypes=[("Audio files", "*.wav *.mp3 *.m4a *.flac *.ogg *.mp4 *.webm")],
        )
        if not paths:
            return
        existing = json.loads(self.session.get("source_audio_files") or "[]")
        for p in paths:
            if p not in existing:
                existing.append(p)
                self.audio_box.insert("end", p)
        db.update_session(self.session_id, source_audio_files=json.dumps(existing))
        self.session["source_audio_files"] = json.dumps(existing)

    def _rename(self) -> None:
        new = self.name_var.get().strip()
        if new:
            db.update_session(self.session_id, display_name=new)
            self.title(f"Session — {new}")

    def _start_transcription(self) -> None:
        self._save_session_mapping()
        if hasattr(self.app, "open_session_stage"):
            self.app.open_session_stage(self.session_id, "transcribe")

    def _back_home(self) -> None:
        self.destroy()
        if hasattr(self.app, "open_home"):
            self.app.open_home()
