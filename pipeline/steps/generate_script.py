"""
generate_script.py — Gemini 2.5-flash scene analysis + recap script generation.

Uses:
  - Gemini Vision to describe key frames + nearby dialogue.
  - Gemini text model to generate the full narrator recap script as JSON.
"""
import json
import re
from google import genai
from PIL import Image


GEMINI_MODEL = "gemini-2.5-flash"
MAX_FRAMES_FOR_ANALYSIS = 10


def analyze_scenes(
    frames: list[tuple[float, str]],
    segments: list[dict],
    gemini_key: str,
) -> str:
    """
    Analyze key frames with Gemini Vision.

    Args:
        frames: [(timestamp_sec, image_path), ...]
        segments: [{start, end, text}, ...]
    Returns:
        Combined scene description string.
    """
    client = genai.Client(api_key=gemini_key)

    scene_parts: list[str] = []
    for timestamp, img_path in frames[:MAX_FRAMES_FOR_ANALYSIS]:
        img = Image.open(img_path).convert("RGB")

        nearby = [
            s["text"] for s in segments
            if abs(s["start"] - timestamp) < 90
        ]
        dialogue_ctx = " ".join(nearby[:6]).strip()

        prompt = (
            f"This is a frame from minute {int(timestamp // 60)} of a movie/drama.\n"
            f"Nearby dialogue: \"{dialogue_ctx}\"\n"
            "Describe in 2-3 sentences: who is in the scene, what is happening, "
            "and the emotional tone. Be concise and factual."
        )

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, img],
            )
            scene_parts.append(f"[Minute {int(timestamp // 60)}] {response.text.strip()}")
        except Exception as exc:
            print(f"[generate_script] Skipping frame at {timestamp}s due to error: {exc}", flush=True)

    return "\n\n".join(scene_parts)


def _extract_json(text: str) -> str:
    """Strip markdown code fences and return raw JSON string."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def generate_recap_script(
    movie_title: str,
    language: str,
    segments: list[dict],
    scene_descriptions: str,
    gemini_key: str,
) -> dict:
    """
    Generate the full recap script using Gemini 2.5-flash.

    Returns dict:
    {
      "hook_timestamp": float,          # seconds into video for the hook clip
      "recommended_duration": int,      # total recap length in seconds
      "script": [
        {
          "text": str,                  # narrator text
          "clip_start": float,          # timestamp in original video
          "clip_end": float,
          "duration": float             # clip_end - clip_start
        },
        ...
      ],
      "outro_text": str
    }
    """
    client = genai.Client(api_key=gemini_key)

    lang_instruction = (
        "Write ALL narrator text in Myanmar language (Burmese script မြန်မာဘာသာ)."
        if language == "myanmar"
        else "Write ALL narrator text in Japanese language (日本語)."
    )

    transcript_json = json.dumps(segments[:120], ensure_ascii=False)

    prompt = f"""You are a professional YouTube drama recap creator for "Cherry Drama" channel.

Movie/Drama: {movie_title}
{lang_instruction}

TRANSCRIPT (with timestamps in seconds):
{transcript_json}

SCENE DESCRIPTIONS:
{scene_descriptions}

Create a complete recap script. Return ONLY valid JSON — no markdown fences, no explanation — in exactly this format:
{{
  "hook_timestamp": <float — seconds into video of the most dramatic/shocking single moment>,
  "recommended_duration": <integer — total recap length in seconds, between 180 and 900>,
  "script": [
    {{
      "text": "<narrator text in the target language — dramatic, engaging, story-driven>",
      "clip_start": <float — timestamp in original video to start this clip>,
      "clip_end": <float — timestamp in original video to end this clip>,
      "duration": <float — clip_end minus clip_start>
    }}
  ],
  "outro_text": "<closing narrator line encouraging viewers to subscribe to Cherry Drama>"
}}

Rules:
- hook_timestamp: the single most emotionally intense or shocking moment
- script: 8 to 15 segments covering full story arc (setup → conflict → climax → resolution)
- Each segment text: narrator style, dramatic, 1-3 sentences, in the target language
- clip_start/clip_end: use real timestamps from the transcript
- clip durations: 5-30 seconds per segment
- Total duration should match recommended_duration
- outro_text: in target language, encourage subscription
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    raw = response.text

    try:
        return json.loads(_extract_json(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON for the recap script. "
            f"Parse error: {exc}\nRaw response (first 500 chars): {raw[:500]}"
        ) from exc
