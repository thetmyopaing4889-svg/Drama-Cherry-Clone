---
name: Cherry Drama setup quirks
description: Non-obvious constraints discovered during initial setup of the Cherry Drama workspace.
---

## api-zod exports conflict

Orval generates two outputs: `generated/api.ts` (Zod schemas) and `generated/types/` (TS interfaces). Both export the same names (e.g. `CreateJobBody`). `lib/api-zod/src/index.ts` must only export from `./generated/api` — never re-add `export * from "./generated/types"` or tsc will error on duplicate exports.

**Why:** Orval is configured with both a `zod` output and a `types` output; they share schema names by design.

**How to apply:** After any codegen run, if typecheck:libs fails with "has already exported a member named", check index.ts and remove the types export.

## Build order requirement

esbuild in api-server builds from lib source files directly. If lib packages aren't compiled (tsc --build), esbuild errors "No matching export". Always run `pnpm run typecheck:libs` before restarting api-server after any lib change.

**Why:** The api-server build.mjs uses esbuild which reads TypeScript source directly but still needs the TypeScript declaration graph to resolve exports.

**How to apply:** After editing lib/db/schema or openapi.yaml+codegen, run typecheck:libs, then restart the api-server workflow.

## API keys architecture

Groq + Gemini keys are stored in a `Map<jobId, keys>` in the Express process (not the DB). The Python worker fetches them via `GET /api/jobs/{id}/keys` which is restricted to localhost only. Keys are deleted from the map when a job completes or fails.

## No Azure TTS

Pipeline uses edge-tts (free, no key needed): my-MM-ThihaNeural for Myanmar, ja-JP-NanamiNeural for Japanese. Do not add Azure dependencies.
