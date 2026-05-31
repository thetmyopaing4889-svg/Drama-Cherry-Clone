"""
progress.py — Sends job progress updates to the Express API server.
All pipeline steps call update_progress() to report their status.
"""
import os
import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080/api")


def update_progress(
    job_id: int,
    status: str,
    progress: int,
    stage: str,
    output_url: str | None = None,
    thumbnail_url: str | None = None,
    duration_seconds: int | None = None,
    error: str | None = None,
) -> None:
    """
    Send a progress update to the API server.
    Fails silently — a network error here should not crash the pipeline.
    """
    payload: dict = {
        "status": status,
        "progress": progress,
        "stage": stage,
    }
    if output_url is not None:
        payload["outputUrl"] = output_url
    if thumbnail_url is not None:
        payload["thumbnailUrl"] = thumbnail_url
    if duration_seconds is not None:
        payload["durationSeconds"] = duration_seconds
    if error is not None:
        payload["error"] = error

    try:
        requests.patch(
            f"{API_BASE_URL}/jobs/{job_id}/progress",
            json=payload,
            timeout=10,
        )
    except Exception as exc:
        print(f"[progress] Warning: could not send update for job {job_id}: {exc}")


def get_job_api_keys(job_id: int) -> dict:
    """
    Fetch API keys and optional SRT content stored in the DB for this job.
    Returns dict with keys: groq, gemini, srt_content (may be empty string).
    Raises RuntimeError if keys cannot be retrieved.
    """
    try:
        resp = requests.get(
            f"{API_BASE_URL}/jobs/{job_id}/keys",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        groq = data.get("groq", "")
        gemini = data.get("gemini", "")
        if not groq or not gemini:
            raise RuntimeError("One or more API keys are empty. Please check Settings.")
        return {
            "groq": groq,
            "gemini": gemini,
            "srt_content": data.get("srtContent") or "",
        }
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not retrieve API keys from server: {exc}") from exc
