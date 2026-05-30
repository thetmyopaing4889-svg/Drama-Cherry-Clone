"""
worker.py — Cherry Drama pipeline worker daemon.
Polls the database every 10 seconds for pending jobs and processes them.

Run:
    python3 pipeline/worker.py

Environment variables:
    DATABASE_URL   — Postgres connection string (required)
    API_BASE_URL   — Express API base URL (default: http://localhost:8080/api)
    PIPELINE_DIR   — Absolute path to this pipeline/ directory (default: auto-detect)
"""
import os
import sys
import time
import traceback

# Ensure pipeline/ is on sys.path so we can import pipeline.py, progress.py, etc.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from pipeline import run_pipeline

DB_URL = os.environ.get("DATABASE_URL", "")

if not DB_URL:
    print("[worker] ERROR: DATABASE_URL environment variable is not set.", flush=True)
    sys.exit(1)


def get_pending_job(conn):
    """Return the oldest pending job as (id, movie_title, language, video_filename) or None."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, movie_title, language, video_filename
            FROM jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """,
        )
        return cur.fetchone()


def connect_with_retry(max_attempts: int = 10) -> psycopg2.extensions.connection:
    for attempt in range(1, max_attempts + 1):
        try:
            conn = psycopg2.connect(DB_URL)
            conn.autocommit = True
            print("[worker] Connected to database.", flush=True)
            return conn
        except psycopg2.OperationalError as exc:
            wait = min(2 ** attempt, 30)
            print(
                f"[worker] DB connection attempt {attempt}/{max_attempts} failed: {exc}. "
                f"Retrying in {wait}s…",
                flush=True,
            )
            time.sleep(wait)
    print("[worker] Could not connect to database after maximum retries. Exiting.", flush=True)
    sys.exit(1)


def reset_stale_jobs(conn) -> None:
    """Reset any jobs stuck in 'processing' back to 'pending' on startup."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'pending', progress = 0, stage = 'Requeued after worker restart'
            WHERE status = 'processing'
            """,
        )
        count = cur.rowcount
    if count > 0:
        print(f"[worker] Reset {count} stale 'processing' job(s) back to 'pending'.", flush=True)


def main():
    print("[worker] Cherry Drama pipeline worker started.", flush=True)
    conn = connect_with_retry()
    reset_stale_jobs(conn)

    while True:
        try:
            job = get_pending_job(conn)
        except psycopg2.OperationalError:
            print("[worker] Lost DB connection — reconnecting…", flush=True)
            try:
                conn.close()
            except Exception:
                pass
            conn = connect_with_retry()
            continue

        if job:
            job_id, movie_title, language, video_filename = job
            print(
                f"[worker] Starting job {job_id}: '{movie_title}' ({language})",
                flush=True,
            )
            try:
                run_pipeline(job_id, movie_title, language, video_filename)
            except Exception:
                print(
                    f"[worker] Unhandled exception in job {job_id}:\n{traceback.format_exc()}",
                    flush=True,
                )
        else:
            time.sleep(10)


if __name__ == "__main__":
    main()
