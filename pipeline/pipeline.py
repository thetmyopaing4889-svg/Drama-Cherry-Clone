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
from steps.generate_script import generate_recap
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

        # ── Stage 1: Transcription (2 → 20%) ───────────────────────────────
        update_progress(job_id, "processing", 5, "Transcribing audio with Whisper")
        segments = transcribe_video(video_path, groq_key, temp_dir, language)

        srt_text = segments_to_srt(segments)
        srt_path = os.path.join(temp_dir, "transcript.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_text)

        update_progress(job_id, "processing", 20, "Transcription complete")

        # ── Stage 2: Extract key frames (20 → 28%) ─────────────────────────
        update_progress(job_id, "processing", 22, "Extracting key frames")
        frames_dir = os.path.join(temp_dir, "frames")
        frames = extract_key_frames(video_path, frames_dir, interval_seconds=60)

        # ── Stage 3: Single Gemini call — scene analysis + recap script (28 → 50%) ──
        update_progress(job_id, "processing", 28, "Analyzing scenes + writing recap script")
        script_data = generate_recap(
            movie_title=movie_title,
            language=language,
            frames=frames,
            segments=segments,
            gemini_key=gemini_key,
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
            movie_title=movie_title,
            hook_timestamp=hook_ts,
            temp_dir=temp_dir,
            output_path=output_video,
            language=language,
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
