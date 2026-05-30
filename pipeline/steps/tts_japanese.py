"""
tts_japanese.py — Japanese narrator voice using edge-tts (free, no API key required).
Voice: ja-JP-NanamiNeural (female, natural)
       ja-JP-KeitaNeural (male) — change VOICE_NAME below to switch
"""
import asyncio
import edge_tts

VOICE_NAME = "ja-JP-NanamiNeural"


def generate_japanese_audio(text: str, output_path: str) -> None:
    """
    Generate MP3 audio from Japanese text using edge-tts.
    Saves the result to output_path (.mp3).
    Raises RuntimeError on failure.
    """
    asyncio.run(_generate_async(text, output_path))


async def _generate_async(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE_NAME, rate="-5%", pitch="-2Hz")
    await communicate.save(output_path)
