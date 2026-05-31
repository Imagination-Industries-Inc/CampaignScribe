"""Campaign speakers library: campaigns -> auto-versioned speakers.json files.

Tk-free. Storage is a managed folder tree under %APPDATA%\\CampaignScribe\\library:
    <slug>/manifest.json + <timestamp>.json version files (immutable).
The manifest holds metadata + the current-version pointer; if it is missing or
corrupt it is rebuilt from the version files on disk.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_app_data_dir
from app.core import speakers_io


def library_root() -> Path:
    path = get_app_data_dir() / "library"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "campaign"


def _campaign_dir(slug: str) -> Path:
    return library_root() / slug


def _unique_slug(display_name: str) -> str:
    base = _slugify(display_name)
    slug, n = base, 2
    while _campaign_dir(slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _manifest_path(slug: str) -> Path:
    return _campaign_dir(slug) / "manifest.json"


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _version_files(slug: str) -> list[str]:
    return sorted(p.name for p in _campaign_dir(slug).glob("*.json") if p.name != "manifest.json")


def _rebuild_manifest(slug: str) -> dict:
    files = _version_files(slug)
    versions = [{"file": f, "created_at": f[:-5], "label": None} for f in files]
    manifest = {
        "display_name": slug,
        "created_at": versions[0]["created_at"] if versions else "",
        "updated_at": versions[-1]["created_at"] if versions else "",
        "current": files[-1] if files else "",
        "versions": versions,
    }
    _atomic_write_json(_manifest_path(slug), manifest)
    return manifest


def _load_manifest(slug: str) -> dict:
    p = _manifest_path(slug)
    try:
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
        if not isinstance(m, dict) or "versions" not in m:
            raise ValueError("bad manifest")
        return m
    except (OSError, ValueError):
        return _rebuild_manifest(slug)


def list_campaigns() -> list[dict]:
    out = []
    for d in sorted(library_root().iterdir()):
        if not d.is_dir():
            continue
        m = _load_manifest(d.name)
        out.append(
            {
                "slug": d.name,
                "display_name": m.get("display_name") or d.name,
                "current": m.get("current", ""),
                "version_count": len(m.get("versions", [])),
                "updated_at": m.get("updated_at", ""),
            }
        )
    return out


def create_campaign(display_name: str) -> str:
    slug = _unique_slug(display_name)
    now = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(
        _manifest_path(slug),
        {
            "display_name": display_name.strip() or slug,
            "created_at": now,
            "updated_at": now,
            "current": "",
            "versions": [],
        },
    )
    return slug


def _new_version_filename(slug: str) -> str:
    base = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    name, n = f"{base}.json", 2
    while (_campaign_dir(slug) / name).exists():
        name, n = f"{base}-{n}.json", n + 1
    return name


def add_version(slug: str, doc: dict, label: str | None = None) -> str:
    if not _campaign_dir(slug).exists():
        raise FileNotFoundError(f"campaign not found: {slug}")
    fname = _new_version_filename(slug)
    speakers_io.save_speakers_json(str(_campaign_dir(slug) / fname), doc)
    m = _load_manifest(slug)
    now = datetime.now().isoformat(timespec="seconds")
    m.setdefault("versions", []).append({"file": fname, "created_at": now, "label": label})
    m["current"] = fname
    m["updated_at"] = now
    _atomic_write_json(_manifest_path(slug), m)
    return fname


def list_versions(slug: str) -> list[dict]:
    return list(_load_manifest(slug).get("versions", []))


def version_path(slug: str, version_file: str) -> Path:
    return _campaign_dir(slug) / version_file


def current_version_path(slug: str) -> Path:
    cur = _load_manifest(slug).get("current", "")
    if not cur:
        raise FileNotFoundError(f"campaign has no versions: {slug}")
    return version_path(slug, cur)


def get_version_doc(slug: str, version_file: str) -> dict:
    return speakers_io.load_speakers_json(str(version_path(slug, version_file)))


def get_current_doc(slug: str) -> dict:
    return speakers_io.load_speakers_json(str(current_version_path(slug)))


def set_current(slug: str, version_file: str) -> None:
    if not version_path(slug, version_file).exists():
        raise FileNotFoundError(version_file)
    m = _load_manifest(slug)
    m["current"] = version_file
    m["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(_manifest_path(slug), m)


def rename_campaign(slug: str, new_display_name: str) -> str:
    new_slug = _unique_slug(new_display_name)
    shutil.move(str(_campaign_dir(slug)), str(_campaign_dir(new_slug)))
    m = _load_manifest(new_slug)
    m["display_name"] = new_display_name.strip() or new_slug
    m["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _atomic_write_json(_manifest_path(new_slug), m)
    return new_slug


def delete_campaign(slug: str) -> None:
    shutil.rmtree(_campaign_dir(slug), ignore_errors=True)


def import_file(path: str, label: str = "imported") -> str:
    doc = speakers_io.load_speakers_json(path)
    name = (doc.get("campaign") or "").strip() or Path(path).stem
    slug = create_campaign(name)
    add_version(slug, doc, label=label)
    return slug


def export_version(slug: str, version_file: str, dest_path: str) -> None:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(version_path(slug, version_file), dest)
