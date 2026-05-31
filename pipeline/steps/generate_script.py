"""
generate_script.py — Gemini 2.5-flash scene analysis + recap script generation.

Uses:
  - Gemini Vision to describe ALL key frames in a SINGLE API call (avoids rate limits).
  - Gemini text model to generate the full narrator recap script as JSON.
  - Exponential backoff on 429/RESOURCE_EXHAUSTED errors.
"""
import json
import re
import time
from google import genai
from PIL import Image


GEMINI_MODEL = "gemini-2.5-flash"
MAX_FRAMES_FOR_ANALYSIS = 10


def _gemini_with_retry(client, model: str, contents, max_retries: int = 4):
    """Call Gemini generate_content with retry on rate-limit (429) errors."""
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=model, contents=contents)
        except Exception as exc:
            err = str(exc)
            is_rate_limit = "429" in err or "RESOURCE_EXHAUSTED" in err or "rate" in err.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait = 60 * (attempt + 1)  # 60 s, 120 s, 180 s
                print(
                    f"[generate_script] Gemini rate limit — waiting {wait}s "
                    f"(attempt {attempt + 1}/{max_retries})…",
                    flush=True,
                )
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini API: max retries exceeded on rate limit.")


def analyze_scenes(
    frames: list[tuple[float, str]],
    segments: list[dict],
    gemini_key: str,
) -> str:
    """
    Analyze key frames with Gemini Vision using a SINGLE API call.

    Args:
        frames: [(timestamp_sec, image_path), ...]
        segments: [{start, end, text}, ...]
    Returns:
        Combined scene description string.
    """
    if not frames:
        return ""

    client = genai.Client(api_key=gemini_key)

    # Build one prompt with all frames interleaved with text labels
    contents: list = []
    for timestamp, img_path in frames[:MAX_FRAMES_FOR_ANALYSIS]:
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            continue

        nearby = [
            s["text"] for s in segments
            if abs(s["start"] - timestamp) < 90
        ]
        dialogue_ctx = " ".join(nearby[:4]).strip()[:200]
        label = f"[Frame at minute {int(timestamp // 60)}]"
        if dialogue_ctx:
            label += f" Nearby dialogue: \"{dialogue_ctx}\""
        contents.append(label)
        contents.append(img)

    if not contents:
        return ""

    contents.append(
        "For each frame above, write ONE sentence describing: "
        "who is in the scene, what is happening, and the emotional tone. "
        "Format strictly as: [Minute X] <your description>"
    )

    try:
        response = _gemini_with_retry(client, GEMINI_MODEL, contents)
        return response.text.strip()
    except Exception as exc:
        print(f"[generate_script] Scene analysis failed (continuing): {exc}", flush=True)
        return ""


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
      "hook_timestamp": float,
      "recommended_duration": int,
      "script": [
        {
          "text": str,
          "clip_start": float,
          "clip_end": float,
          "duration": float
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

    response = _gemini_with_retry(client, GEMINI_MODEL, prompt)

    try:
        raw = response.text
    except Exception as exc:
        raise ValueError(
            f"Gemini response has no text content (possibly blocked by safety filters): {exc}"
        ) from exc

    try:
        return json.loads(_extract_json(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON for the recap script. "
            f"Parse error: {exc}\nRaw response (first 500 chars): {raw[:500]}"
        ) from exc
