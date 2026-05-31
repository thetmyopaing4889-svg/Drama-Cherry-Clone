"""
generate_script.py — Single Gemini 2.5-flash call: scene analysis + recap script.

All frames + transcript are sent in ONE multimodal request.
Exponential backoff on 429/RESOURCE_EXHAUSTED errors.
"""
import json
import re
import time
from google import genai
from PIL import Image


GEMINI_MODEL = "gemini-2.5-flash"
MAX_FRAMES = 8


def _gemini_with_retry(client, model: str, contents, max_retries: int = 4):
    """Call Gemini generate_content with retry on rate-limit (429) errors."""
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=model, contents=contents)
        except Exception as exc:
            err = str(exc)
            is_rate_limit = "429" in err or "RESOURCE_EXHAUSTED" in err or "rate" in err.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait = 60 * (attempt + 1)
                print(
                    f"[generate_script] Gemini rate limit — waiting {wait}s "
                    f"(attempt {attempt + 1}/{max_retries})…",
                    flush=True,
                )
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini API: max retries exceeded on rate limit.")


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


def generate_recap(
    movie_title: str,
    language: str,
    frames: list[tuple[float, str]],
    segments: list[dict],
    gemini_key: str,
) -> dict:
    """
    Analyze scene frames + transcript and generate the full recap script
    in a SINGLE Gemini multimodal API call.

    Returns:
    {
      "hook_timestamp": float,
      "recommended_duration": int,
      "script": [
        {"text": str, "clip_start": float, "clip_end": float, "duration": float},
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

    # ── Build multimodal content: frames first, then transcript + instructions ──
    contents: list = []

    # Include up to MAX_FRAMES key frames as images
    for timestamp, img_path in frames[:MAX_FRAMES]:
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            continue
        nearby = [
            s["text"] for s in segments
            if abs(s.get("start", 0) - timestamp) < 90
        ]
        dialogue_ctx = " ".join(nearby[:3]).strip()[:150]
        label = f"[Scene at minute {int(timestamp // 60)}]"
        if dialogue_ctx:
            label += f' Nearby dialogue: "{dialogue_ctx}"'
        contents.append(label)
        contents.append(img)

    # Transcript JSON (up to 120 segments to keep prompt size reasonable)
    transcript_json = json.dumps(segments[:120], ensure_ascii=False)

    # Full instructions + output format
    contents.append(f"""You are a professional YouTube drama recap creator for "Cherry Drama" channel.

Movie/Drama: {movie_title}
{lang_instruction}

TRANSCRIPT (timestamps in seconds):
{transcript_json}

Look at the scene images above and read the transcript carefully.
Create a complete dramatic recap. Return ONLY valid JSON — no markdown, no explanation — in exactly this format:
{{
  "hook_timestamp": <float — seconds of the most dramatic/shocking single moment>,
  "recommended_duration": <integer — total recap length in seconds, 180–900>,
  "script": [
    {{
      "text": "<narrator text in the target language — dramatic, engaging, 1–3 sentences>",
      "clip_start": <float — timestamp in original video to start this clip>,
      "clip_end": <float — timestamp in original video to end this clip>,
      "duration": <float — clip_end minus clip_start>
    }}
  ],
  "outro_text": "<closing line in target language encouraging viewers to subscribe to Cherry Drama>"
}}

Rules:
- hook_timestamp: the single most emotionally intense or shocking moment
- script: 8–15 segments covering full story arc (setup → conflict → climax → resolution)
- Each text: narrator style, dramatic, in the target language
- clip_start/clip_end: use real timestamps from the transcript
- Each clip: 5–30 seconds
- Total duration matches recommended_duration
""")

    response = _gemini_with_retry(client, GEMINI_MODEL, contents)

    try:
        raw = response.text
    except Exception as exc:
        raise ValueError(
            f"Gemini response has no text (possibly blocked by safety filters): {exc}"
        ) from exc

    try:
        result = json.loads(_extract_json(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON. "
            f"Parse error: {exc}\nRaw response (first 500 chars): {raw[:500]}"
        ) from exc

    if not result.get("script"):
        raise ValueError("Gemini returned an empty script. Try again or check your Gemini API key.")

    return result
