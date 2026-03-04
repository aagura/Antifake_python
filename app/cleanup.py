from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .storage import cleanup_old_jobs


@dataclass
class CleanupConfig:
    interval_seconds: int = 15 * 60       # каждые 15 минут
    ttl_seconds: int = 6 * 60 * 60        # хранить 6 часов


class CleanupService:
    def __init__(self, uploads_dir: Path, frames_dir: Path, config: CleanupConfig):
        self.uploads_dir = uploads_dir
        self.frames_dir = frames_dir
        self.config = config
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        try:
            await self._task
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        # небольшой сдвиг после старта
        await asyncio.sleep(2.0)

        while not self._stop_event.is_set():
            try:
                cutoff = time.time() - self.config.ttl_seconds
                cleanup_old_jobs(
                    uploads_dir=self.uploads_dir,
                    frames_dir=self.frames_dir,
                    older_than_epoch=cutoff,
                )
            except Exception:
                # уборщик не должен ронять сервер
                pass

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.config.interval_seconds)
            except asyncio.TimeoutError:
                continue