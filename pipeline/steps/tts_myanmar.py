"""
tts_myanmar.py — Myanmar narrator voice using edge-tts (free, no API key required).
Voice: my-MM-ThihaNeural (male, dramatic)
       my-MM-NilarNeural (female, warm) — change VOICE_NAME below to switch
"""
import asyncio
import edge_tts

VOICE_NAME = "my-MM-ThihaNeural"


def generate_myanmar_audio(text: str, output_path: str) -> None:
    """
    Generate MP3 audio from Myanmar text using edge-tts.
    Saves the result to output_path (.mp3).
    Raises RuntimeError on failure.
    """
    asyncio.run(_generate_async(text, output_path))


async def _generate_async(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE_NAME, rate="-5%", pitch="-2Hz")
    await communicate.save(output_path)
