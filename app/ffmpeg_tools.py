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
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
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


def extract_frames_uniform(
    job_id: str,
    video_path: Path,
    frames_count: int,
    base_dir: Path,
    target_width: int = 320,
) -> Dict[str, Any]:
    """
    Извлекает frames_count кадров равномерно по времени.
    Масштабирует по ширине до target_width (высота пропорционально, чётная).

    frames/<job_id>/frame_0001.jpg ... frame_0032.jpg

    Возвращает:
    {
      "duration_sec": float,
      "frames_extracted": int,
      "frames": [
        {index,t_sec,path,url,abs_path}, ...
      ]
    }
    """
    frames_dir = base_dir / "frames"
    out_dir = frames_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = ffprobe_duration_sec(video_path)
    if duration is None or duration <= 0.05:
        duration = 0.0

    frames_count = max(1, min(int(frames_count), 128))
    times: List[float] = []

    if duration > 0:
        # центр каждого интервала: (2i-1)/(2N)
        for i in range(1, frames_count + 1):
            t = duration * ((i * 2 - 1) / (frames_count * 2))
            t = max(0.05, min(duration - 0.05, t))
            times.append(t)
    else:
        times = [1.0]

    frames: List[Dict[str, Any]] = []
    for i, t in enumerate(times, start=1):
        out_file = out_dir / f"frame_{i:04d}.jpg"
        vf = f"scale={target_width}:-2"

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{t:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", vf,
            "-q:v", "2",
            str(out_file),
        ]

        p = _run(cmd)
        if p.returncode != 0 or not out_file.exists():
            try:
                out_file.unlink(missing_ok=True)
            except Exception:
                pass
            continue

        rel_for_url = out_file.relative_to(frames_dir).as_posix()
        frames.append(
            {
                "index": i,
                "t_sec": round(float(t), 3),
                "path": str(out_file.relative_to(base_dir)).replace("\\", "/"),
                "url": f"/frames/{rel_for_url}",
                "abs_path": str(out_file),
            }
        )

    return {
        "duration_sec": round(float(duration), 3) if duration else float(duration),
        "frames_extracted": int(len(frames)),
        "frames": frames,
    }