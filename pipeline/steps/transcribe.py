"""
transcribe.py — Audio extraction + Whisper transcription via Groq API.

Strategy for large files (> 25 MB audio limit):
  1. Extract audio from video using FFmpeg at 32 kbps mono 16 kHz.
     A 2-hour film becomes ~28 MB — most films fit in one request.
  2. If audio file is >= 23 MB, split into ~22 MB chunks with 10-second
     overlap, transcribe each chunk, and stitch segments back together.
  3. Returns list of {start, end, text} dicts with correct timestamps.
"""
import os
import subprocess
import json
import math

from groq import Groq

WHISPER_MODEL = "whisper-large-v3-turbo"
MAX_AUDIO_BYTES = 23 * 1024 * 1024   # 23 MB — safe limit under Groq's 25 MB cap
CHUNK_OVERLAP_SEC = 10               # seconds of overlap between chunks


def _fmt_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def _get_video_duration(video_path: str) -> float:
    """Return video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _extract_audio(video_path: str, output_path: str, start: float = 0, duration: float | None = None) -> None:
    """Extract mono 16kHz 32kbps MP3 audio from video, optionally from a time slice."""
    cmd = ["ffmpeg", "-y"]
    if start > 0:
        cmd += ["-ss", str(start)]
    cmd += ["-i", video_path]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k", output_path]
    subprocess.run(cmd, check=True, capture_output=True)


def _transcribe_audio_file(audio_path: str, groq_key: str, language: str) -> list[dict]:
    """Transcribe a single audio file with Groq Whisper. Returns segment list."""
    client = Groq(api_key=groq_key)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f),
            model=WHISPER_MODEL,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            language=language,
        )
    segs = response.segments or []
    result = []
    for seg in segs:
        if isinstance(seg, dict):
            result.append({
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": str(seg.get("text", "")).strip(),
            })
        else:
            result.append({
                "start": float(seg.start),
                "end": float(seg.end),
                "text": str(seg.text).strip(),
            })
    return result


def transcribe_video(
    video_path: str,
    groq_key: str,
    temp_dir: str,
    language: str = "my",
) -> list[dict]:
    """
    Full transcription pipeline.
    Returns list of {start, end, text} with timestamps relative to video start.
    """
    groq_language = "my" if language == "myanmar" else "ja"

    # Step 1: Extract full audio
    full_audio = os.path.join(temp_dir, "audio_full.mp3")
    _extract_audio(video_path, full_audio)

    audio_size = os.path.getsize(full_audio)

    if audio_size < MAX_AUDIO_BYTES:
        # Small enough — transcribe in one shot
        return _transcribe_audio_file(full_audio, groq_key, groq_language)

    # Large file — split into chunks
    print(
        f"[transcribe] Audio is {audio_size / 1e6:.1f} MB — splitting into chunks.",
        flush=True,
    )
    video_duration = _get_video_duration(video_path)

    # Calculate chunk duration based on file size
    # At 32kbps mono 16kHz: bytes_per_sec ≈ 4000 bytes/s
    bytes_per_sec = audio_size / video_duration
    chunk_duration = MAX_AUDIO_BYTES / bytes_per_sec

    num_chunks = math.ceil(video_duration / (chunk_duration - CHUNK_OVERLAP_SEC))
    all_segments: list[dict] = []
    seen_texts: set[str] = set()

    for i in range(num_chunks):
        chunk_start = max(0.0, i * (chunk_duration - CHUNK_OVERLAP_SEC))
        chunk_len = min(chunk_duration, video_duration - chunk_start)
        if chunk_len <= 0:
            break

        chunk_audio = os.path.join(temp_dir, f"chunk_{i:03d}.mp3")
        _extract_audio(video_path, chunk_audio, start=chunk_start, duration=chunk_len)

        print(f"[transcribe] Chunk {i + 1}/{num_chunks}: {chunk_start:.0f}s – {chunk_start + chunk_len:.0f}s", flush=True)
        chunk_segs = _transcribe_audio_file(chunk_audio, groq_key, groq_language)
        os.unlink(chunk_audio)

        # Adjust timestamps and deduplicate overlap
        for seg in chunk_segs:
            abs_start = chunk_start + seg["start"]
            abs_end = chunk_start + seg["end"]
            text = seg["text"].strip()

            # Skip segments in the overlap zone that were already added
            if i > 0 and abs_start < chunk_start + CHUNK_OVERLAP_SEC:
                if text in seen_texts:
                    continue

            all_segments.append({
                "start": round(abs_start, 3),
                "end": round(abs_end, 3),
                "text": text,
            })
            seen_texts.add(text)

    # Sort by start time
    all_segments.sort(key=lambda s: s["start"])
    return all_segments
