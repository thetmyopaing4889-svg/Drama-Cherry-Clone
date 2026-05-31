"""
pipeline.py — Orchestrates all steps for a single Cherry Drama recap job.
Called by worker.py.
"""
import os
import shutil
import traceback
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from progress import update_progress, get_job_api_keys
from steps.transcribe import transcribe_video, segments_to_srt
from steps.extract_frames import extract_key_frames
from steps.generate_script import analyze_scenes, generate_recap_script
from steps.tts_myanmar import generate_myanmar_audio
from steps.tts_japanese import generate_japanese_audio
from steps.compose_video import compose_full_video
from steps.generate_thumbnail import generate_thumbnail

PIPELINE_DIR = os.environ.get("PIPELINE_DIR", os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(PIPELINE_DIR, "uploads")
OUTPUTS_DIR = os.path.join(PIPELINE_DIR, "outputs")
TEMP_BASE = os.path.join(PIPELINE_DIR, "temp")


def run_pipeline(job_id: int, movie_title: str, language: str, video_filename: str) -> None:
    temp_dir = os.path.join(TEMP_BASE, f"job_{job_id}")
    output_dir = os.path.join(OUTPUTS_DIR, f"job_{job_id}")
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    video_path = os.path.join(UPLOADS_DIR, video_filename)
    output_video = os.path.join(output_dir, "recap.mp4")
    output_thumb = os.path.join(output_dir, "thumbnail.jpg")

    if not os.path.exists(video_path):
        update_progress(job_id, "failed", 0, "Failed",
                        error=f"Video file not found: {video_filename}")
        return

    try:
        # ── Fetch API keys ──────────────────────────────────────────────────
        update_progress(job_id, "processing", 2, "Loading API keys")
        try:
            keys = get_job_api_keys(job_id)
        except RuntimeError as exc:
            update_progress(job_id, "failed", 0, "Failed", error=str(exc))
            return

        groq_key = keys["groq"]
        gemini_key = keys["gemini"]
        provided_srt = keys.get("srt_content", "").strip()

        # ── Stage 1: Transcription (2 → 20%) ───────────────────────────────
        srt_path = os.path.join(temp_dir, "transcript.srt")

        if provided_srt:
            # Hybrid mode: user-provided SRT — skip Whisper transcription
            print(f"[pipeline] Job {job_id}: using user-provided SRT ({len(provided_srt)} chars), skipping Whisper.", flush=True)
            update_progress(job_id, "processing", 10, "Using provided subtitles")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(provided_srt)
            # Parse SRT into segments for script generation
            segments = _parse_srt(provided_srt)
            update_progress(job_id, "processing", 20, "Subtitles loaded")
        else:
            # Standard mode: Groq Whisper transcription
            update_progress(job_id, "processing", 5, "Transcribing audio")
            segments = transcribe_video(video_path, groq_key, temp_dir, language)
            srt_text = segments_to_srt(segments)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_text)
            update_progress(job_id, "processing", 20, "Transcription complete")

        # ── Stage 2: Scene Analysis (20 → 35%) ─────────────────────────────
        update_progress(job_id, "processing", 22, "Extracting key frames")
        frames_dir = os.path.join(temp_dir, "frames")
        frames = extract_key_frames(video_path, frames_dir, interval_seconds=60)

        update_progress(job_id, "processing", 28, "Analyzing scenes")
        scene_descriptions = analyze_scenes(frames, segments, gemini_key)

        # ── Stage 3: Script Generation (35 → 50%) ──────────────────────────
        update_progress(job_id, "processing", 35, "Writing recap script")
        script_data = generate_recap_script(
            movie_title, language, segments, scene_descriptions, gemini_key
        )
        hook_ts = float(script_data.get("hook_timestamp", 0))
        recommended = int(script_data.get("recommended_duration", 480))
        script_segments = script_data.get("script", [])

        if not script_segments:
            raise ValueError("Gemini returned an empty script. Try again or check your Gemini API key.")

        update_progress(job_id, "processing", 50, "Recap script ready")

        # ── Stage 4: TTS Voice Generation (50 → 70%) ───────────────────────
        update_progress(job_id, "processing", 52, "Generating narrator voice")
        audio_dir = os.path.join(temp_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        audio_files: list[str] = []

        for i, seg in enumerate(script_segments):
            audio_path = os.path.join(audio_dir, f"seg_{i:03d}.mp3")
            if language == "myanmar":
                generate_myanmar_audio(seg["text"], audio_path)
            else:
                generate_japanese_audio(seg["text"], audio_path)
            audio_files.append(audio_path)
            pct = 52 + int(18 * (i + 1) / len(script_segments))
            update_progress(job_id, "processing", pct, "Generating narrator voice")

        update_progress(job_id, "processing", 70, "Voice generation complete")

        # ── Stage 5: Video Composition (70 → 90%) ──────────────────────────
        update_progress(job_id, "processing", 72, "Composing final video")
        compose_full_video(
            source_video=video_path,
            script=script_segments,
            audio_segments=audio_files,
            srt_path=srt_path,
            movie_title=movie_title,
            hook_timestamp=hook_ts,
            temp_dir=temp_dir,
            output_path=output_video,
        )
        update_progress(job_id, "processing", 88, "Video composition done")

        # ── Stage 6: Thumbnail (88 → 100%) ─────────────────────────────────
        update_progress(job_id, "processing", 90, "Generating thumbnail")
        generate_thumbnail(video_path, movie_title, hook_ts, output_thumb)

        # ── Done ────────────────────────────────────────────────────────────
        output_url = f"/api/outputs/job_{job_id}/recap.mp4"
        thumb_url = f"/api/outputs/job_{job_id}/thumbnail.jpg"
        update_progress(
            job_id, "completed", 100, "Done",
            output_url=output_url,
            thumbnail_url=thumb_url,
            duration_seconds=recommended,
        )
        print(f"[pipeline] Job {job_id} completed successfully.", flush=True)

    except Exception as exc:
        error_detail = traceback.format_exc()
        brief = str(exc) if str(exc) else type(exc).__name__
        print(f"[pipeline] Job {job_id} FAILED:\n{error_detail}", flush=True)
        update_progress(job_id, "failed", 0, "Failed", error=brief)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _parse_srt(srt_text: str) -> list[dict]:
    """
    Parse SRT file content into [{start, end, text}] segment list.
    Timestamps are converted to seconds.
    """
    segments: list[dict] = []
    blocks = srt_text.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # Line 0: index, Line 1: timestamps, Line 2+: text
        ts_line = lines[1]
        text = " ".join(lines[2:]).strip()
        if " --> " not in ts_line:
            continue
        start_str, end_str = ts_line.split(" --> ", 1)
        start = _srt_ts_to_seconds(start_str.strip())
        end = _srt_ts_to_seconds(end_str.strip())
        if start is not None and end is not None and text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def _srt_ts_to_seconds(ts: str) -> float | None:
    """Convert SRT timestamp (HH:MM:SS,mmm) to seconds."""
    try:
        ts = ts.replace(",", ".")
        parts = ts.split(":")
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
    except Exception:
        return None
