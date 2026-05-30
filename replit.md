# Cherry Drama

An AI-powered drama recap generator that takes raw video files and produces narrated recap videos with Myanmar/Japanese TTS, burned-in subtitles, Cherry Drama logo watermark, and movie-poster thumbnails.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 8080)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run typecheck:libs` — build lib packages (run this before restarting api-server after lib changes)
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `python3 pipeline/worker.py` — run the Python pipeline worker daemon
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: React + Vite (artifacts/cherry-drama, port 18262, path /cherry-drama)
- API: Express 5 (artifacts/api-server, port 8080, path /api)
- DB: PostgreSQL + Drizzle ORM (lib/db)
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec in lib/api-spec/openapi.yaml)
- Build: esbuild (CJS bundle)
- Pipeline: Python 3 — edge-tts, Groq Whisper, Gemini 2.5-flash, FFmpeg, Pillow

## Where things live

- `lib/db/src/schema/index.ts` — DB schema (jobsTable)
- `lib/api-spec/openapi.yaml` — OpenAPI source of truth
- `lib/api-zod/src/generated/api.ts` — generated Zod schemas (do not edit)
- `artifacts/api-server/src/routes/jobs.ts` — all jobs API routes
- `artifacts/api-server/src/app.ts` — Express app, serves `/api/outputs` as static
- `artifacts/cherry-drama/src/` — React frontend
- `pipeline/pipeline.py` — main pipeline orchestrator
- `pipeline/worker.py` — daemon that polls DB for pending jobs
- `pipeline/progress.py` — sends PATCH /api/jobs/{id}/progress updates
- `pipeline/uploads/` — assembled video files awaiting processing
- `pipeline/outputs/job_{id}/` — recap.mp4 + thumbnail.jpg output files

## Architecture decisions

- **No Azure TTS**: Pipeline uses `edge-tts` (free, no key needed) for both Myanmar (my-MM-ThihaNeural) and Japanese (ja-JP-NanamiNeural).
- **API keys in memory**: Groq + Gemini keys are stored in a `Map<jobId, keys>` in the Express process and exposed to the worker via `GET /api/jobs/{id}/keys` (localhost-only, forbidden to external callers).
- **Chunked uploads**: Frontend splits large videos (up to 5 GB) into 5 MB chunks, POSTs each to `/api/jobs/upload-chunk`, then calls `/api/jobs/start` to assemble and enqueue.
- **Output serving**: Express serves `pipeline/outputs/` as static files at `/api/outputs/`, so output URLs like `/api/outputs/job_1/recap.mp4` work directly.
- **Worker as separate process**: Python worker polls DB every 10 s via psycopg2; progress updates go to Express API which updates the DB. Frontend polls `/api/jobs` to show live progress.
- **lib/api-zod exports only `generated/api`**: The `generated/types/` directory exists but is not exported from index.ts to avoid duplicate export conflicts with Zod schemas of the same name.

## Product

- Upload any drama/movie video file (MP4, MKV, AVI — up to 5 GB)
- AI transcribes, analyzes scenes, writes recap script
- Edge-TTS narrates in Myanmar or Japanese
- FFmpeg assembles a final recap video with subtitles and Cherry Drama watermark
- Movie-poster thumbnail generated automatically
- Processing Queue shows live progress; Recap Library shows completed recaps

## User preferences

- No Azure TTS, no emojis in UI
- Brand colors: #1a0a0f (dark background) and #C2185B (cherry red accent)

## Gotchas

- Always run `pnpm run typecheck:libs` before restarting the API server after any changes to `lib/db` or `lib/api-zod` — esbuild builds from source and will fail if lib exports are missing.
- After editing `openapi.yaml`, run `pnpm --filter @workspace/api-spec run codegen` then `pnpm run typecheck:libs` before restarting api-server.
- `pipeline/multer_temp/` and `pipeline/uploads_temp/` are created automatically by the API server on startup.
- The Pipeline Worker workflow must have `DATABASE_URL` in scope — it uses `$DATABASE_URL` shell expansion.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
