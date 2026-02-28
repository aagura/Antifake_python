from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOADS_DIR = BASE_DIR / "uploads"
FRAMES_DIR = BASE_DIR / "frames"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(job_id: str, up: UploadFile) -> Path:
    """
    Сохраняет UploadFile в uploads/<job_id>.<ext>
    """
    suffix = ""
    if up.filename:
        suffix = Path(up.filename).suffix.lower()
        if len(suffix) > 10:
            suffix = ""

    allowed = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
    if suffix not in allowed:
        suffix = ".mp4"

    out_path = UPLOADS_DIR / f"{job_id}{suffix}"

    with out_path.open("wb") as f:
        shutil.copyfileobj(up.file, f)

    return out_path
