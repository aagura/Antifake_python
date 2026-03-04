from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

# Корень репозитория: Antifake_python/
BASE_DIR = Path(__file__).resolve().parent.parent

UPLOADS_DIR = BASE_DIR / "uploads"
FRAMES_DIR = BASE_DIR / "frames"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(job_id: str, file: UploadFile) -> Path:
    """
    Сохраняет загруженный файл в uploads/<job_id>.<ext>
    Возвращает путь к сохраненному файлу.
    """
    original = (file.filename or "").strip()
    ext = ""
    if "." in original:
        ext = "." + original.split(".")[-1][:10].lower()

    out_path = UPLOADS_DIR / f"{job_id}{ext or '.mp4'}"

    with out_path.open("wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    now = time.time()
    os.utime(out_path, (now, now))
    return out_path


def job_frames_dir(job_id: str) -> Path:
    return FRAMES_DIR / job_id


def delete_job(job_id: str) -> bool:
    """
    Удаляет uploads/<job_id>.* и frames/<job_id>/.
    Возвращает True, если что-то было удалено.
    """
    deleted_any = False

    # uploads/<job_id>.*
    for p in UPLOADS_DIR.glob(f"{job_id}.*"):
        try:
            p.unlink(missing_ok=True)
            deleted_any = True
        except Exception:
            pass

    # frames/<job_id>/
    fdir = job_frames_dir(job_id)
    if fdir.exists() and fdir.is_dir():
        try:
            shutil.rmtree(fdir, ignore_errors=True)
            deleted_any = True
        except Exception:
            pass

    return deleted_any


def _mtime(path: Path) -> Optional[float]:
    try:
        return float(path.stat().st_mtime)
    except Exception:
        return None


def cleanup_old_jobs(uploads_dir: Path, frames_dir: Path, older_than_epoch: float) -> int:
    """
    Удаляет всё, что старше older_than_epoch по mtime:
      - frames/<job_id>/ (по папке)
      - uploads/<job_id>.* (и "висячие" файлы)
    Возвращает примерно количество удалённых job'ов.
    """
    removed = 0

    # 1) frames/<job_id>/
    if frames_dir.exists():
        for job_dir in frames_dir.iterdir():
            if not job_dir.is_dir():
                continue
            mtime = _mtime(job_dir)
            if mtime is not None and mtime < older_than_epoch:
                job_id = job_dir.name
                if delete_job(job_id):
                    removed += 1

    # 2) uploads/* (на всякий случай)
    if uploads_dir.exists():
        for up in uploads_dir.iterdir():
            if not up.is_file():
                continue
            mtime = _mtime(up)
            if mtime is not None and mtime < older_than_epoch:
                try:
                    up.unlink(missing_ok=True)
                    removed += 1
                except Exception:
                    pass

    return removed