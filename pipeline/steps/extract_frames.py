"""
extract_frames.py — Extract one JPEG key frame per interval using FFmpeg.
Returns list of (timestamp_seconds, image_path) tuples.
"""
import os
import glob
import subprocess


def extract_key_frames(
    video_path: str,
    output_dir: str,
    interval_seconds: int = 60,
) -> list[tuple[float, str]]:
    """
    Extract one frame every `interval_seconds` from the video.
    Returns [(timestamp_sec, image_path), ...] sorted by timestamp.
    """
    os.makedirs(output_dir, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"fps=1/{interval_seconds}",
            "-q:v", "3",
            os.path.join(output_dir, "frame_%04d.jpg"),
        ],
        check=True,
        capture_output=True,
    )

    frame_paths = sorted(glob.glob(os.path.join(output_dir, "frame_*.jpg")))
    return [
        (float(i * interval_seconds), path)
        for i, path in enumerate(frame_paths)
    ]
