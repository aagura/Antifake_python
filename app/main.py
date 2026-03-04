from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .cleanup import CleanupConfig, CleanupService
from .ffmpeg_tools import extract_frames_uniform
from .model_inference import run_frame_dummy
from .storage import BASE_DIR, FRAMES_DIR, UPLOADS_DIR, cleanup_old_jobs, delete_job, save_upload

cleanup_service: CleanupService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cleanup_service
    cleanup_service = CleanupService(
        uploads_dir=UPLOADS_DIR,
        frames_dir=FRAMES_DIR,
        config=CleanupConfig(
            interval_seconds=15 * 60,
            ttl_seconds=6 * 60 * 60,
        ),
    )
    cleanup_service.start()
    yield
    if cleanup_service is not None:
        await cleanup_service.stop()
        cleanup_service = None


app = FastAPI(title="Antifake Server", version="0.4.0", lifespan=lifespan)

# /frames/<job_id>/frame_0001.jpg
app.mount("/frames", StaticFiles(directory=str(FRAMES_DIR)), name="frames")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(
    file: UploadFile = File(...),
    frames_count: int = 32,
    model: str = "frame_dummy",
) -> JSONResponse:
    """
    Шаг 1:
      - кадры равномерно по времени
      - frames_count по умолчанию 32
      - scale width=320px

    Шаг 2:
      - model=frame_dummy
      - ai_probability = null
      - возвращаем duration_sec и frames_extracted
    """
    t0 = time.time()
    job_id = uuid4().hex

    try:
        stored_path = save_upload(job_id, file)

        frames_info = extract_frames_uniform(
            job_id=job_id,
            video_path=stored_path,
            frames_count=max(1, min(int(frames_count), 128)),
            base_dir=BASE_DIR,
            target_width=320,
        )

        abs_paths: List[str] = [f.get("abs_path", "") for f in (frames_info.get("frames") or [])]
        frame_paths = [Path(p) for p in abs_paths if p]

        # Шаг 2: заглушка модели
        if model == "frame_dummy":
            inf = run_frame_dummy(frame_paths)
        else:
            # пока других моделей нет — честный fallback
            inf = run_frame_dummy(frame_paths)
            inf.model = model  # type: ignore[attr-defined]  # безопасно для dataclass? нет, поэтому не делаем
            # Вместо этого просто игнорируем и возвращаем dummy с пометкой:
            inf = run_frame_dummy(frame_paths)
            inf = type(inf)(
                model=model,
                ai_probability=None,
                detail=f"unknown model '{model}', fallback to frame_dummy",
            )

        elapsed_ms = int((time.time() - t0) * 1000)

        payload: Dict[str, Any] = {
            "status": "ok",
            "job_id": job_id,
            "stored_as": str(stored_path.relative_to(BASE_DIR)).replace("\\", "/"),
            "elapsed_ms": elapsed_ms,

            "frames": frames_info,
            "duration_sec": frames_info.get("duration_sec"),
            "frames_extracted": frames_info.get("frames_extracted", 0),

            "model": inf.model,
            "ai_probability": inf.ai_probability,
            "model_detail": inf.detail,
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


@app.delete("/jobs/{job_id}")
def delete_job_endpoint(job_id: str) -> Dict[str, Any]:
    deleted = delete_job(job_id)
    return {"status": "ok", "deleted": bool(deleted), "job_id": job_id}


@app.post("/cleanup")
def cleanup_endpoint(older_than_minutes: int = 360) -> Dict[str, Any]:
    cutoff = time.time() - max(1, int(older_than_minutes)) * 60
    removed = cleanup_old_jobs(uploads_dir=UPLOADS_DIR, frames_dir=FRAMES_DIR, older_than_epoch=cutoff)
    return {"status": "ok", "removed_jobs": removed, "older_than_minutes": int(older_than_minutes)}