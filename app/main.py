from __future__ import annotations

import time
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .ffmpeg_tools import extract_frames
from .storage import BASE_DIR, FRAMES_DIR, save_upload


app = FastAPI(title="Antifake Server", version="0.1.0")

# Раздача кадров по HTTP:
# /frames/<job_id>/frame_01.jpg
app.mount("/frames", StaticFiles(directory=str(FRAMES_DIR)), name="frames")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(
    file: UploadFile = File(...),
    frames_count: int = 5,
) -> JSONResponse:
    """
    Принимает видео, сохраняет, режет кадры, возвращает JSON.
    frames_count можно менять параметром ?frames_count=7
    """
    t0 = time.time()
    job_id = uuid4().hex

    try:
        stored_path = save_upload(job_id, file)

        frames_info = extract_frames(
            job_id=job_id,
            video_path=stored_path,
            frames_count=max(1, min(int(frames_count), 20)),
            base_dir=BASE_DIR,
        )

        elapsed_ms = int((time.time() - t0) * 1000)

        payload: Dict[str, Any] = {
            "status": "ok",
            "job_id": job_id,
            "stored_as": str(stored_path.relative_to(BASE_DIR)).replace("\\", "/"),
            "elapsed_ms": elapsed_ms,
            "frames": frames_info,
        }
        return JSONResponse(payload)

    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "job_id": job_id,
                "elapsed_ms": elapsed_ms,
                "error": str(e),
            },
        )
