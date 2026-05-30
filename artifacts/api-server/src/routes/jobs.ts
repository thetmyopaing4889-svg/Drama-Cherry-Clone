import { Router, Request, Response } from "express";
import multer from "multer";
import { db, jobsTable } from "@workspace/db";
import { eq, desc, count } from "drizzle-orm";
import fs from "fs";
import path from "path";
import {
  CreateJobBody,
  UpdateJobProgressBody,
  GetJobParams,
  DeleteJobParams,
  UpdateJobProgressParams,
} from "@workspace/api-zod";

const PIPELINE_DIR = process.env["PIPELINE_DIR"] ?? path.join(__dirname, "../../../pipeline");
const MULTER_TEMP = path.join(PIPELINE_DIR, "multer_temp");
const UPLOADS_TEMP = path.join(PIPELINE_DIR, "uploads_temp");
const UPLOADS_DIR = path.join(PIPELINE_DIR, "uploads");

for (const dir of [MULTER_TEMP, UPLOADS_TEMP, UPLOADS_DIR]) {
  fs.mkdirSync(dir, { recursive: true });
}

const jobApiKeys = new Map<number, { groq: string; gemini: string }>();

const upload = multer({
  dest: MULTER_TEMP,
  limits: { fileSize: 10 * 1024 * 1024 },
});

const router = Router();

router.post(
  "/jobs/upload-chunk",
  upload.single("chunk"),
  async (req: Request, res: Response) => {
    const { uploadId, chunkIndex } = req.body as { uploadId?: string; chunkIndex?: string };

    if (!uploadId || chunkIndex === undefined) {
      res.status(400).json({ error: "Missing uploadId or chunkIndex" });
      return;
    }
    if (!req.file) {
      res.status(400).json({ error: "Missing chunk file" });
      return;
    }

    const safeId = uploadId.replace(/[^a-zA-Z0-9-]/g, "");
    const chunkDir = path.join(UPLOADS_TEMP, safeId);
    fs.mkdirSync(chunkDir, { recursive: true });

    const destPath = path.join(chunkDir, `chunk_${Number(chunkIndex)}`);
    fs.renameSync(req.file.path, destPath);

    res.json({ received: Number(chunkIndex) });
  }
);

router.post("/jobs/start", async (req: Request, res: Response) => {
  const { uploadId, movieTitle, language, filename, totalChunks } = req.body as {
    uploadId?: string;
    movieTitle?: string;
    language?: string;
    filename?: string;
    totalChunks?: number | string;
  };

  if (!uploadId || !movieTitle || !language || !filename || totalChunks === undefined) {
    res.status(400).json({ error: "Missing required fields: uploadId, movieTitle, language, filename, totalChunks" });
    return;
  }

  const groqKey = (req.headers["x-groq-key"] as string | undefined) ?? "";
  const geminiKey = (req.headers["x-gemini-key"] as string | undefined) ?? "";

  if (!groqKey || !geminiKey) {
    res.status(400).json({
      error: "Missing API keys. Please set Groq API Key and Gemini API Key in Settings before starting.",
    });
    return;
  }

  const safeId = uploadId.replace(/[^a-zA-Z0-9-]/g, "");
  const chunkDir = path.join(UPLOADS_TEMP, safeId);
  const safeFilename = filename.replace(/[^a-zA-Z0-9._-]/g, "_");
  const finalFilename = `${safeId}_${safeFilename}`;
  const finalPath = path.join(UPLOADS_DIR, finalFilename);
  const numChunks = Number(totalChunks);

  try {
    const writeStream = fs.createWriteStream(finalPath);

    for (let i = 0; i < numChunks; i++) {
      const chunkPath = path.join(chunkDir, `chunk_${i}`);
      if (!fs.existsSync(chunkPath)) {
        writeStream.destroy();
        try { fs.unlinkSync(finalPath); } catch {}
        res.status(400).json({ error: `Missing chunk ${i + 1} of ${numChunks}. Upload may be incomplete — please try again.` });
        return;
      }
      await new Promise<void>((resolve, reject) => {
        const rs = fs.createReadStream(chunkPath);
        rs.pipe(writeStream, { end: false });
        rs.on("end", resolve);
        rs.on("error", reject);
      });
    }

    await new Promise<void>((resolve, reject) => {
      writeStream.end();
      writeStream.on("finish", resolve);
      writeStream.on("error", reject);
    });

    fs.rmSync(chunkDir, { recursive: true, force: true });
  } catch (err) {
    try { fs.unlinkSync(finalPath); } catch {}
    const msg = err instanceof Error ? err.message : "Unknown error";
    res.status(500).json({ error: `Failed to merge file chunks: ${msg}` });
    return;
  }

  const [job] = await db
    .insert(jobsTable)
    .values({
      movieTitle,
      language,
      videoFilename: finalFilename,
      status: "pending",
      progress: 0,
      stage: "Waiting to start",
    })
    .returning();

  jobApiKeys.set(job.id, { groq: groqKey, gemini: geminiKey });

  req.log.info({ jobId: job.id, movieTitle, language }, "Job created and queued");

  res.status(201).json(formatJob(job));
});

router.get("/jobs/:id/keys", (req: Request, res: Response) => {
  const ip = req.ip ?? req.socket.remoteAddress ?? "";
  const isLocal = ["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(ip);
  if (!isLocal) {
    res.status(403).json({ error: "Forbidden" });
    return;
  }

  const id = Number(req.params.id);
  if (Number.isNaN(id)) {
    res.status(400).json({ error: "Invalid id" });
    return;
  }

  const keys = jobApiKeys.get(id);
  if (!keys) {
    res.status(404).json({ error: "API keys not found for this job. They may have expired or the job was already completed." });
    return;
  }

  res.json(keys);
});

router.get("/jobs", async (req, res) => {
  const jobs = await db
    .select()
    .from(jobsTable)
    .orderBy(desc(jobsTable.createdAt));
  res.json(jobs.map(formatJob));
});

router.get("/jobs/stats", async (req, res) => {
  const rows = await db
    .select({ status: jobsTable.status, cnt: count() })
    .from(jobsTable)
    .groupBy(jobsTable.status);

  const stats = { total: 0, completed: 0, processing: 0, failed: 0, pending: 0 };
  for (const row of rows) {
    const n = Number(row.cnt);
    stats.total += n;
    if (row.status === "completed") stats.completed += n;
    else if (row.status === "processing") stats.processing += n;
    else if (row.status === "failed") stats.failed += n;
    else if (row.status === "pending") stats.pending += n;
  }
  res.json(stats);
});

router.get("/jobs/:id", async (req, res) => {
  const parsed = GetJobParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) { res.status(400).json({ error: "Invalid id" }); return; }

  const [job] = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.id, parsed.data.id));

  if (!job) { res.status(404).json({ error: "Job not found" }); return; }
  res.json(formatJob(job));
});

router.post("/jobs", async (req, res) => {
  const parsed = CreateJobBody.safeParse(req.body);
  if (!parsed.success) { res.status(400).json({ error: "Invalid input" }); return; }

  const [job] = await db
    .insert(jobsTable)
    .values({
      movieTitle: parsed.data.movieTitle,
      language: parsed.data.language,
      videoFilename: parsed.data.videoFilename ?? null,
      status: "pending",
      progress: 0,
      stage: "Waiting to start",
    })
    .returning();

  res.status(201).json(formatJob(job));
});

router.delete("/jobs/:id", async (req, res) => {
  const parsed = DeleteJobParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) { res.status(400).json({ error: "Invalid id" }); return; }

  await db.delete(jobsTable).where(eq(jobsTable.id, parsed.data.id));
  jobApiKeys.delete(parsed.data.id);
  res.status(204).send();
});

router.patch("/jobs/:id/progress", async (req, res) => {
  const paramParsed = UpdateJobProgressParams.safeParse({ id: Number(req.params.id) });
  if (!paramParsed.success) { res.status(400).json({ error: "Invalid id" }); return; }

  const bodyParsed = UpdateJobProgressBody.safeParse(req.body);
  if (!bodyParsed.success) { res.status(400).json({ error: "Invalid body" }); return; }

  const updates: Record<string, unknown> = {};
  const b = bodyParsed.data;
  if (b.status !== undefined) updates.status = b.status;
  if (b.progress !== undefined) updates.progress = b.progress;
  if (b.stage !== undefined) updates.stage = b.stage;
  if (b.outputUrl !== undefined) updates.outputUrl = b.outputUrl;
  if (b.thumbnailUrl !== undefined) updates.thumbnailUrl = b.thumbnailUrl;
  if (b.durationSeconds !== undefined) updates.durationSeconds = b.durationSeconds;
  if (b.recommendedDuration !== undefined) updates.recommendedDuration = b.recommendedDuration;
  if (b.error !== undefined) updates.error = b.error;
  if (b.status === "completed" || b.status === "failed") {
    updates.completedAt = new Date();
    jobApiKeys.delete(paramParsed.data.id);
  }

  const [job] = await db
    .update(jobsTable)
    .set(updates)
    .where(eq(jobsTable.id, paramParsed.data.id))
    .returning();

  if (!job) { res.status(404).json({ error: "Job not found" }); return; }
  res.json(formatJob(job));
});

function formatJob(job: typeof jobsTable.$inferSelect) {
  return {
    id: job.id,
    movieTitle: job.movieTitle,
    language: job.language,
    status: job.status,
    progress: job.progress,
    stage: job.stage,
    outputUrl: job.outputUrl ?? null,
    thumbnailUrl: job.thumbnailUrl ?? null,
    durationSeconds: job.durationSeconds ?? null,
    recommendedDuration: job.recommendedDuration ?? null,
    error: job.error ?? null,
    createdAt: job.createdAt.toISOString(),
    completedAt: job.completedAt?.toISOString() ?? null,
  };
}

export default router;
