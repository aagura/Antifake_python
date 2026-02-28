from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def ffprobe_duration_sec(video_path: Path) -> Optional[float]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    p = _run(cmd)
    if p.returncode != 0:
        return None
    s = (p.stdout or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def extract_frames(
    job_id: str,
    video_path: Path,
    frames_count: int,
    base_dir: Path,
) -> Dict[str, Any]:
    """
    Извлекает N кадров равномерно по времени.
    Складывает в frames/<job_id>/frame_XX.jpg
    Возвращает:
      { "duration_sec": float, "frames": [ {index,t_sec,path,url}, ... ] }
    """
    frames_dir = base_dir / "frames"
    out_dir = frames_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = ffprobe_duration_sec(video_path)
    if duration is None or duration <= 0.05:
        duration = 0.0

    times: List[float] = []

    if duration > 0:
        # 10%,30%,50%,70%,90% при N=5 (через (2i-1)/(2N))
        for i in range(1, frames_count + 1):
            t = duration * ((i * 2 - 1) / (frames_count * 2))
            t = max(0.05, min(duration - 0.05, t))
            times.append(t)
    else:
        times = [1.0]

    frames: List[Dict[str, Any]] = []

    for i, t in enumerate(times, start=1):
        out_file = out_dir / f"frame_{i:02d}.jpg"

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_file),
        ]

        p = _run(cmd)
        if p.returncode != 0 or not out_file.exists():
            _safe_unlink(out_file)
            continue

        rel_for_url = out_file.relative_to(frames_dir).as_posix()  # "<job>/frame_01.jpg"
        frames.append(
            {
                "index": i,
                "t_sec": round(float(t), 3),
                "path": str(out_file.relative_to(base_dir)).replace("\\", "/"),
                "url": f"/frames/{rel_for_url}",
            }
        )

    return {
        "duration_sec": round(float(duration), 3) if duration else float(duration),
        "frames": frames,
    }
