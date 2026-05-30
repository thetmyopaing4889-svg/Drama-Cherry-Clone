import { pgTable, serial, text, integer, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const jobsTable = pgTable("jobs", {
  id: serial("id").primaryKey(),
  movieTitle: text("movie_title").notNull(),
  language: text("language").notNull(),
  videoFilename: text("video_filename"),
  status: text("status").notNull().default("pending"),
  progress: integer("progress").notNull().default(0),
  stage: text("stage").notNull().default("Waiting to start"),
  outputUrl: text("output_url"),
  thumbnailUrl: text("thumbnail_url"),
  durationSeconds: integer("duration_seconds"),
  recommendedDuration: integer("recommended_duration"),
  error: text("error"),
  groqKey: text("groq_key"),
  geminiKey: text("gemini_key"),
  createdAt: timestamp("created_at").notNull().defaultNow(),
  completedAt: timestamp("completed_at"),
});

export const insertJobSchema = createInsertSchema(jobsTable).omit({ id: true, createdAt: true });
export type InsertJob = z.infer<typeof insertJobSchema>;
export type Job = typeof jobsTable.$inferSelect;
