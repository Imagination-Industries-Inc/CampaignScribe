"""Shared SpeakerEditor widget — a single-speaker editable form block.

Extracted into its own module so EditProfileWindow (and future callers)
can import it independently.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

ROLE_OPTIONS = ["Dungeon Master", "Player", "Non-Player", "Unknown"]


class SpeakerEditor(ttk.LabelFrame):
    """Editable form block for a single speaker."""

    def __init__(self, master, profile: dict[str, Any]):
        sid = profile.get("source_speaker_id", "?")
        title = f"{sid}"
        super().__init__(master, text=title)
        self.profile = dict(profile)
        self.include_var = tk.BooleanVar(value=bool(profile.get("include_in_tracking", 1)))
        self.name_var = tk.StringVar(value=profile.get("display_name", ""))
        self.char_var = tk.StringVar(value=profile.get("character_name", "") or "")
        self.class_var = tk.StringVar(value=profile.get("character_class", "") or "")
        self.role_var = tk.StringVar(value=profile.get("role") or "Player")
        self.notes_var = tk.StringVar(value=profile.get("notes", "") or "")
        self.confidence = profile.get("confidence", "medium")

        pad = {"padx": 6, "pady": 2}
        ttk.Checkbutton(self, text="Include", variable=self.include_var).grid(
            row=0, column=0, sticky="w", **pad
        )
        ttk.Label(self, text=f"Confidence: {self.confidence}").grid(
            row=0, column=1, sticky="w", **pad
        )
        ttk.Label(self, text="Display name:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.name_var, width=28).grid(
            row=1, column=1, sticky="w", **pad
        )
        ttk.Label(self, text="Role:").grid(row=1, column=2, sticky="w", **pad)
        ttk.Combobox(
            self, textvariable=self.role_var, state="readonly", values=ROLE_OPTIONS, width=18
        ).grid(row=1, column=3, sticky="w", **pad)
        ttk.Label(self, text="Character name:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.char_var, width=28).grid(
            row=2, column=1, sticky="w", **pad
        )
        ttk.Label(self, text="Character class:").grid(row=2, column=2, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.class_var, width=20).grid(
            row=2, column=3, sticky="w", **pad
        )

        ttk.Label(self, text="Notes:").grid(row=3, column=0, sticky="nw", **pad)
        self.notes_box = tk.Text(self, height=2, width=70, wrap="word")
        self.notes_box.insert("1.0", profile.get("notes", "") or "")
        self.notes_box.grid(row=3, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(self, text="Speech patterns:").grid(row=4, column=0, sticky="nw", **pad)
        self.patterns_box = tk.Text(self, height=4, width=70, wrap="word")
        self.patterns_box.insert("1.0", "\n".join(profile.get("speech_patterns") or []))
        self.patterns_box.grid(row=4, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(self, text="Sample quotes:").grid(row=5, column=0, sticky="nw", **pad)
        self.quotes_box = tk.Text(self, height=3, width=70, wrap="word")
        self.quotes_box.insert("1.0", "\n".join(profile.get("sample_quotes") or []))
        self.quotes_box.grid(row=5, column=1, columnspan=3, sticky="ew", **pad)

        for col in (1, 3):
            self.columnconfigure(col, weight=1)

    def collect(self) -> dict[str, Any]:
        patterns = [
            ln.strip() for ln in self.patterns_box.get("1.0", "end").splitlines() if ln.strip()
        ]
        quotes = [ln.strip() for ln in self.quotes_box.get("1.0", "end").splitlines() if ln.strip()]
        notes = self.notes_box.get("1.0", "end").strip()
        return {
            "source_speaker_id": self.profile.get("source_speaker_id", ""),
            "display_name": self.name_var.get().strip(),
            "character_name": self.char_var.get().strip(),
            "character_class": self.class_var.get().strip(),
            "role": self.role_var.get(),
            "include_in_tracking": 1 if self.include_var.get() else 0,
            "notes": notes,
            "speech_patterns": patterns,
            "sample_quotes": quotes,
            "confidence": self.profile.get("confidence", "medium"),
        }
