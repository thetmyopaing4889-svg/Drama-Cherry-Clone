"""
compose_video.py — Assemble the final Cherry Drama recap video using FFmpeg.

Output structure:
  [0:00–0:15]  Hook clip          — AI-selected dramatic scene
  [0:15–0:20]  Logo intro (5s)    — Cherry Drama logo + movie title on dark bg
  [0:20–END]   Recap segments     — Scene clips + narrator TTS audio
                                     + burned-in subtitles
                                     + logo corner watermark

Copyright-safe transforms applied to each clip:
  - Speed: +3%  (setpts=0.97*PTS + atempo=1.03)
  - Saturation: +10%
  - Crop: 1% border removed
"""
import os
import json
import subprocess
import glob

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../assets/logo.jpg")
INTRO_DURATION = 5
HOOK_DURATION = 15
SPEED_FACTOR = 0.97  # setpts=0.97*PTS gives 1/0.97 ≈ 3% speed-up


def _fmt_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _generate_recap_srt(script: list[dict], recap_srt_path: str) -> None:
    """
    Write an SRT file with narrator text timed to match the assembled recap video.

    Assembled timeline:
      [0, HOOK_DURATION)            — hook clip (no subtitle)
      [HOOK_DURATION, +INTRO_DURATION) — intro slide (no subtitle)
      [HOOK_DURATION+INTRO_DURATION, …) — scene clips, each sped up by SPEED_FACTOR
    """
    lines: list[str] = []
    current = float(HOOK_DURATION + INTRO_DURATION)

    for i, seg in enumerate(script, 1):
        clip_start = float(seg.get("clip_start", 0))
        clip_end = float(seg.get("clip_end", clip_start + 10))
        clip_dur = max(0.5, clip_end - clip_start) * SPEED_FACTOR

        lines.append(str(i))
        lines.append(f"{_fmt_ts(current)} --> {_fmt_ts(current + clip_dur)}")
        lines.append(seg.get("text", "").strip())
        lines.append("")

        current += clip_dur

    with open(recap_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(cmd: list[str], label: str = "") -> None:
    """Run an FFmpeg command; raise with helpful output on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed{' (' + label + ')' if label else ''}:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR: {result.stderr[-2000:]}"
        )


def _get_duration(path: str) -> float:
    """Return duration of a media file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def extract_clip(video_path: str, start: float, end: float, output_path: str) -> None:
    """Extract a clip from the source video between start and end seconds."""
    duration = max(0.5, end - start)
    _run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", video_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ],
        f"extract clip {start:.1f}-{end:.1f}s",
    )


def apply_copyright_transform(clip_path: str, output_path: str) -> None:
    """Apply copyright fingerprint-reducing transforms to a clip."""
    _run(
        [
            "ffmpeg", "-y", "-i", clip_path,
            "-vf", "crop=iw*0.99:ih*0.99,eq=saturation=1.1:contrast=1.05,setpts=0.97*PTS",
            "-af", "atempo=1.03,aresample=44100",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ],
        "copyright transform",
    )


def create_logo_intro(movie_title: str, temp_dir: str) -> str:
    """
    Create a 5-second intro clip: dark maroon background + logo centered + title.
    Returns path to the intro .mp4 file.
    """
    output_path = os.path.join(temp_dir, "intro.mp4")

    if os.path.exists(LOGO_PATH):
        # Scale logo to max 400px wide, overlay on colored background with title
        safe_title = movie_title.replace("'", "\\'").replace(":", "\\:")
        _run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=#1a0a0f:s=1920x1080:d={INTRO_DURATION}",
                "-loop", "1", "-i", LOGO_PATH,
                "-filter_complex",
                (
                    "[1:v]scale=400:-1[logo];"
                    "[0:v][logo]overlay=(W-w)/2:(H-h)/2-60:enable='between(t,0,5)'[bg];"
                    f"[bg]drawtext=text='{safe_title}':"
                    "fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h+250)/2:"
                    "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    "shadowcolor=black:shadowx=2:shadowy=2[v]"
                ),
                "-map", "[v]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-t", str(INTRO_DURATION),
                "-an",
                output_path,
            ],
            "logo intro",
        )
    else:
        # Fallback: colored background with title only
        safe_title = movie_title.replace("'", "\\'").replace(":", "\\:")
        _run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=#1a0a0f:s=1920x1080:d={INTRO_DURATION}",
                "-vf",
                (
                    f"drawtext=text='Cherry Drama':"
                    "fontsize=36:fontcolor=#C2185B:x=(w-text_w)/2:y=(h-text_h)/2-60:"
                    "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,"
                    f"drawtext=text='{safe_title}':"
                    "fontsize=52:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2+20:"
                    "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                ),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-t", str(INTRO_DURATION),
                "-an",
                output_path,
            ],
            "text-only intro",
        )

    return output_path


def add_silent_audio(clip_path: str, output_path: str, duration: float) -> None:
    """Add silent audio track to a video-only clip."""
    _run(
        [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={duration}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ],
        "add silent audio",
    )


def concat_clips(clip_paths: list[str], output_path: str) -> None:
    """Concatenate a list of video clips using FFmpeg concat demuxer."""
    list_file = output_path + ".txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    _run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ],
        "concat clips",
    )
    os.unlink(list_file)


def concat_audio(audio_paths: list[str], output_path: str) -> None:
    """Concatenate multiple audio files into one MP3."""
    list_file = output_path + ".txt"
    with open(list_file, "w") as f:
        for p in audio_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    _run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:a", "libmp3lame", "-q:a", "4",
            output_path,
        ],
        "concat audio",
    )
    os.unlink(list_file)


def replace_audio(video_path: str, audio_path: str, output_path: str) -> None:
    """Replace video audio track with the provided audio file."""
    _run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ],
        "replace audio",
    )


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> None:
    """Burn SRT subtitles into the video."""
    safe_srt = srt_path.replace("\\", "/").replace("'", "\\'").replace(":", "\\:")
    _run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf",
            (
                f"subtitles='{safe_srt}':"
                "force_style='FontName=DejaVu Sans,FontSize=24,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "BackColour=&H80000000,Bold=1,Outline=2,Shadow=1,"
                "Alignment=2,MarginV=30'"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ],
        "burn subtitles",
    )


def add_logo_watermark(video_path: str, output_path: str) -> None:
    """
    Overlay Cherry Drama logo as a corner watermark (bottom-right, 70% opacity).
    If logo file doesn't exist, copies the video unchanged.
    """
    if not os.path.exists(LOGO_PATH):
        import shutil
        shutil.copy2(video_path, output_path)
        return

    _run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", LOGO_PATH,
            "-filter_complex",
            (
                "[1:v]scale=120:-1,format=rgba,"
                "colorchannelmixer=aa=0.7[logo];"
                "[0:v][logo]overlay=W-w-20:H-h-20[v]"
            ),
            "-map", "[v]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ],
        "logo watermark",
    )


# ── Main composition function ─────────────────────────────────────────────────

def compose_full_video(
    source_video: str,
    script: list[dict],
    audio_segments: list[str],
    srt_path: str,
    movie_title: str,
    hook_timestamp: float,
    temp_dir: str,
    output_path: str,
) -> None:
    """
    Compose the full Cherry Drama recap video.

    Args:
        source_video:    Path to the original video file.
        script:          List of {text, clip_start, clip_end, duration} dicts.
        audio_segments:  List of TTS audio file paths (one per script segment).
        srt_path:        Path to the full transcript SRT (for subtitle overlay).
        movie_title:     Title used in the intro slide.
        hook_timestamp:  Timestamp of the dramatic hook clip (seconds).
        temp_dir:        Temporary directory for intermediate files.
        output_path:     Where to save the final recap.mp4.
    """
    clips_dir = os.path.join(temp_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    all_video_clips: list[str] = []

    # ── 1. Hook clip ──────────────────────────────────────────────────────────
    hook_raw = os.path.join(clips_dir, "hook_raw.mp4")
    hook_transformed = os.path.join(clips_dir, "hook.mp4")
    hook_silent = os.path.join(clips_dir, "hook_silent.mp4")

    extract_clip(source_video, hook_timestamp, hook_timestamp + HOOK_DURATION, hook_raw)
    apply_copyright_transform(hook_raw, hook_transformed)
    add_silent_audio(hook_transformed, hook_silent, HOOK_DURATION)
    os.unlink(hook_raw)
    os.unlink(hook_transformed)
    all_video_clips.append(hook_silent)

    # ── 2. Logo intro ─────────────────────────────────────────────────────────
    intro_path = create_logo_intro(movie_title, temp_dir)
    intro_with_audio = os.path.join(clips_dir, "intro_audio.mp4")
    add_silent_audio(intro_path, intro_with_audio, INTRO_DURATION)
    all_video_clips.append(intro_with_audio)

    # ── 3. Scene clips (video only, no audio yet) ─────────────────────────────
    scene_clips: list[str] = []
    for i, seg in enumerate(script):
        raw_path = os.path.join(clips_dir, f"scene_raw_{i:03d}.mp4")
        transformed_path = os.path.join(clips_dir, f"scene_{i:03d}.mp4")

        c_start = float(seg.get("clip_start", 0))
        c_end = float(seg.get("clip_end", c_start + 10))

        extract_clip(source_video, c_start, c_end, raw_path)
        apply_copyright_transform(raw_path, transformed_path)
        os.unlink(raw_path)
        scene_clips.append(transformed_path)

    # ── 4. Concatenate scene clips + merge with TTS audio ─────────────────────
    if scene_clips:
        scenes_concat = os.path.join(temp_dir, "scenes_concat.mp4")
        concat_clips(scene_clips, scenes_concat)
        for p in scene_clips:
            try: os.unlink(p)
            except OSError: pass

        tts_concat = os.path.join(temp_dir, "tts_concat.mp3")
        concat_audio(audio_segments, tts_concat)

        scenes_with_tts = os.path.join(temp_dir, "scenes_tts.mp4")
        replace_audio(scenes_concat, tts_concat, scenes_with_tts)
        os.unlink(scenes_concat)
        os.unlink(tts_concat)
        all_video_clips.append(scenes_with_tts)

    # ── 5. Concatenate hook + intro + scenes ──────────────────────────────────
    assembled = os.path.join(temp_dir, "assembled.mp4")
    concat_clips(all_video_clips, assembled)
    for p in all_video_clips:
        try: os.unlink(p)
        except OSError: pass

    # ── 6. Burn subtitles (narrator text timed to recap video) ────────────────
    recap_srt_path = os.path.join(temp_dir, "recap.srt")
    _generate_recap_srt(script, recap_srt_path)
    with_subs = os.path.join(temp_dir, "with_subs.mp4")
    try:
        burn_subtitles(assembled, recap_srt_path, with_subs)
        os.unlink(assembled)
    except RuntimeError as exc:
        # Subtitle burning is best-effort — fall back to no subtitles
        print(f"[compose_video] Subtitle burn failed (continuing without): {exc}", flush=True)
        import shutil
        shutil.move(assembled, with_subs)

    # ── 7. Add logo corner watermark ──────────────────────────────────────────
    add_logo_watermark(with_subs, output_path)
    try: os.unlink(with_subs)
    except OSError: pass

    print(f"[compose_video] Final video saved: {output_path}", flush=True)
