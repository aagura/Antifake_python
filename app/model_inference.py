from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class InferenceOutput:
    model: str
    ai_probability: Optional[float]  # 0..1 или None
    detail: str


def run_frame_dummy(frame_paths: List[Path]) -> InferenceOutput:
    # Никаких случайных чисел. Это заглушка, чтобы отладить пайплайн.
    return InferenceOutput(
        model="frame_dummy",
        ai_probability=None,
        detail=f"dummy model, frames_seen={len(frame_paths)}",
    )