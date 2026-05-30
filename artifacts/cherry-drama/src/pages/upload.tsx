import { useState, useRef, useCallback } from "react";
import { useLocation, Link } from "wouter";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  UploadCloud, FileVideo, Sparkles, AlertCircle, CheckCircle2, Loader2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const CHUNK_SIZE = 5 * 1024 * 1024;

const STORAGE_KEYS = {
  groq: "GROQ_API_KEY",
  gemini: "GEMINI_API_KEY",
} as const;

function getApiKeys() {
  return {
    groq: localStorage.getItem(STORAGE_KEYS.groq) ?? "",
    gemini: localStorage.getItem(STORAGE_KEYS.gemini) ?? "",
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(0)} KB/s`;
  return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`;
}

type Phase = "idle" | "uploading" | "starting" | "done";

export default function UploadPage() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();

  const [movieTitle, setMovieTitle] = useState("");
  const [language, setLanguage] = useState<"myanmar" | "japanese">("myanmar");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadSpeed, setUploadSpeed] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cancelRef = useRef(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped?.type.startsWith("video/")) {
      setFile(dropped);
      setErrorMsg(null);
    } else {
      setErrorMsg("Please select a valid video file (MP4, MKV, AVI, MOV).");
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setErrorMsg(null);
    }
  };

  const uploadInChunks = useCallback(
    async (
      uploadId: string,
      f: File,
      onProgress: (pct: number, speed: number) => void,
    ): Promise<boolean> => {
      const totalChunks = Math.ceil(f.size / CHUNK_SIZE);
      const startTime = Date.now();
      let uploaded = 0;

      for (let i = 0; i < totalChunks; i++) {
        if (cancelRef.current) return false;

        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, f.size);
        const chunk = f.slice(start, end);

        const form = new FormData();
        form.append("chunk", chunk, f.name);
        form.append("uploadId", uploadId);
        form.append("chunkIndex", String(i));
        form.append("totalChunks", String(totalChunks));

        let ok = false;
        for (let attempt = 0; attempt < 3; attempt++) {
          try {
            const resp = await fetch("/api/jobs/upload-chunk", {
              method: "POST",
              body: form,
            });
            if (!resp.ok) {
              const body = await resp.json().catch(() => ({}));
              throw new Error((body as { error?: string }).error ?? `HTTP ${resp.status}`);
            }
            ok = true;
            break;
          } catch (e) {
            if (attempt === 2) {
              setErrorMsg(
                `Upload failed at chunk ${i + 1}/${totalChunks}: ${
                  e instanceof Error ? e.message : "Network error"
                }. Please try again.`,
              );
              return false;
            }
            await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
          }
        }
        if (!ok) return false;

        uploaded += end - start;
        const elapsed = Math.max((Date.now() - startTime) / 1000, 0.001);
        onProgress(Math.round((uploaded / f.size) * 100), uploaded / elapsed);
      }
      return true;
    },
    [],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!movieTitle.trim()) {
      setErrorMsg("Please enter a movie or drama title.");
      return;
    }
    if (!file) {
      setErrorMsg("Please select a video file.");
      return;
    }

    const keys = getApiKeys();
    const missingKeys: string[] = [];
    if (!keys.groq) missingKeys.push("Groq API Key");
    if (!keys.gemini) missingKeys.push("Gemini API Key");

    if (missingKeys.length > 0) {
      setErrorMsg(
        `Missing API keys: ${missingKeys.join(", ")}. Please go to Settings and add them first.`,
      );
      return;
    }

    const uploadId = crypto.randomUUID();
    cancelRef.current = false;

    setPhase("uploading");
    setUploadPct(0);
    setUploadSpeed(0);

    const success = await uploadInChunks(uploadId, file, (pct, speed) => {
      setUploadPct(pct);
      setUploadSpeed(speed);
    });

    if (!success) {
      setPhase("idle");
      return;
    }

    setPhase("starting");

    try {
      const resp = await fetch("/api/jobs/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-groq-key": keys.groq,
          "x-gemini-key": keys.gemini,
        },
        body: JSON.stringify({
          uploadId,
          movieTitle: movieTitle.trim(),
          language,
          filename: file.name,
          totalChunks: Math.ceil(file.size / CHUNK_SIZE),
        }),
      });

      const body = await resp.json();

      if (!resp.ok) {
        const msg = (body as { error?: string }).error ?? `Server error (${resp.status})`;
        setErrorMsg(msg);
        setPhase("idle");
        return;
      }

      setPhase("done");
      toast({ title: "Recap job started", description: `"${movieTitle}" is now in the processing queue.` });
      setLocation("/processing");
    } catch (e) {
      setErrorMsg(
        `Failed to start job: ${e instanceof Error ? e.message : "Network error"}. Please try again.`,
      );
      setPhase("idle");
    }
  };

  const isRunning = phase === "uploading" || phase === "starting";
  const keys = getApiKeys();
  const missingKeys = [
    !keys.groq && "Groq",
    !keys.gemini && "Gemini",
  ].filter(Boolean) as string[];

  return (
    <Layout>
      <div className="max-w-4xl mx-auto w-full p-8 pt-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2 font-serif tracking-wide">
            Create New Recap
          </h1>
          <p className="text-muted-foreground">
            Upload your source video and let our AI generate a complete dramatic recap.
          </p>
        </div>

        {missingKeys.length > 0 && phase === "idle" && (
          <div className="mb-6 p-4 rounded-xl bg-amber-900/20 border border-amber-600/30 text-amber-300 text-sm flex gap-3 items-start">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <strong>API keys missing:</strong> {missingKeys.join(", ")}.{" "}
              <Link href="/settings" className="underline hover:text-amber-200 transition-colors">
                Go to Settings to add them
              </Link>{" "}
              before uploading.
            </div>
          </div>
        )}

        {errorMsg && (
          <div className="mb-6 p-4 rounded-xl bg-red-900/20 border border-red-600/30 text-red-300 text-sm flex gap-3 items-start">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="md:col-span-2 space-y-6">
              <Card className="border-primary/20 bg-card/50 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-xl">Source Video</CardTitle>
                  <CardDescription>Upload the episode or movie file (MP4, MKV, AVI — up to 5 GB)</CardDescription>
                </CardHeader>
                <CardContent>
                  {isRunning ? (
                    <div className="space-y-4 p-6 border-2 border-primary/30 rounded-xl bg-card/60">
                      <div className="flex items-center gap-3">
                        <Loader2 className="h-5 w-5 animate-spin text-primary shrink-0" />
                        <span className="text-white font-medium">
                          {phase === "uploading"
                            ? `Uploading ${file?.name}…`
                            : "Starting pipeline…"}
                        </span>
                      </div>

                      {phase === "uploading" && (
                        <>
                          <Progress value={uploadPct} className="h-3" />
                          <div className="flex justify-between text-sm text-muted-foreground">
                            <span>{uploadPct}% — {formatBytes(Math.round((uploadPct / 100) * (file?.size ?? 0)))} / {formatBytes(file?.size ?? 0)}</span>
                            <span>{formatSpeed(uploadSpeed)}</span>
                          </div>
                        </>
                      )}

                      {phase === "starting" && (
                        <div className="text-sm text-muted-foreground">
                          Merging chunks and queuing your job…
                        </div>
                      )}
                    </div>
                  ) : (
                    <div
                      className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-200 ${
                        isDragging
                          ? "border-primary bg-primary/10"
                          : file
                          ? "border-primary/50 bg-card/80"
                          : "border-border hover:border-primary/50 hover:bg-card/80"
                      }`}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onDrop={handleDrop}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        accept="video/*"
                        className="hidden"
                      />

                      {file ? (
                        <div className="flex flex-col items-center justify-center space-y-3">
                          <div className="h-16 w-16 rounded-full bg-primary/20 flex items-center justify-center">
                            <FileVideo className="h-8 w-8 text-primary" />
                          </div>
                          <div className="text-white font-medium">{file.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {formatBytes(file.size)}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="mt-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              setFile(null);
                              setErrorMsg(null);
                            }}
                          >
                            Remove
                          </Button>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center space-y-4">
                          <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                            <UploadCloud className="h-8 w-8 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="text-base font-medium text-white">
                              Click or drag video here
                            </p>
                            <p className="text-sm text-muted-foreground mt-1">
                              MP4, MKV, AVI up to 5 GB — uploads in 5 MB chunks
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="bg-card/50 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-xl">Recap Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-3">
                    <Label htmlFor="title" className="text-base">
                      Movie or Drama Title
                    </Label>
                    <Input
                      id="title"
                      placeholder="e.g. Crash Landing on You, Shogun..."
                      value={movieTitle}
                      onChange={(e) => setMovieTitle(e.target.value)}
                      className="bg-background/50 h-12 text-lg"
                      disabled={isRunning}
                    />
                  </div>

                  <div className="space-y-3">
                    <Label className="text-base">Output Language</Label>
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        type="button"
                        onClick={() => setLanguage("myanmar")}
                        disabled={isRunning}
                        className={`flex items-center justify-center space-x-3 p-4 rounded-lg border-2 transition-all ${
                          language === "myanmar"
                            ? "border-primary bg-primary/10 text-white"
                            : "border-border bg-background/50 text-muted-foreground hover:border-primary/30"
                        } disabled:opacity-50`}
                      >
                        <div className="h-6 w-8 rounded overflow-hidden relative border border-white/20">
                          <div className="absolute inset-0 bg-yellow-400 h-1/3"></div>
                          <div className="absolute top-1/3 inset-x-0 bg-green-500 h-1/3"></div>
                          <div className="absolute bottom-0 inset-x-0 bg-red-500 h-1/3"></div>
                        </div>
                        <span className="font-semibold">Myanmar</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setLanguage("japanese")}
                        disabled={isRunning}
                        className={`flex items-center justify-center space-x-3 p-4 rounded-lg border-2 transition-all ${
                          language === "japanese"
                            ? "border-primary bg-primary/10 text-white"
                            : "border-border bg-background/50 text-muted-foreground hover:border-primary/30"
                        } disabled:opacity-50`}
                      >
                        <div className="h-6 w-8 rounded overflow-hidden relative border border-white/20 bg-white">
                          <div className="absolute inset-0 flex items-center justify-center">
                            <div className="h-4 w-4 bg-red-600 rounded-full"></div>
                          </div>
                        </div>
                        <span className="font-semibold">Japanese</span>
                      </button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card className="bg-primary/5 border-primary/20">
                <CardHeader>
                  <CardTitle className="flex items-center text-lg text-primary">
                    <Sparkles className="mr-2 h-5 w-5" />
                    AI Pipeline
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-xs text-muted-foreground">
                  {[
                    ["1", "Audio extract + Whisper transcription"],
                    ["2", "Key frame scene analysis (Gemini)"],
                    ["3", "Recap script generation (Gemini 2.5)"],
                    ["4", "Narrator voice synthesis (Edge TTS)"],
                    ["5", "Video assembly + subtitles (FFmpeg)"],
                    ["6", "Thumbnail generation"],
                  ].map(([n, label]) => (
                    <div key={n} className="flex items-center gap-2">
                      <span className="h-5 w-5 rounded-full bg-primary/20 text-primary flex items-center justify-center text-[10px] font-bold shrink-0">
                        {n}
                      </span>
                      <span>{label}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <div className="space-y-2">
                {[
                  { label: "Groq API Key", ok: !!keys.groq },
                  { label: "Gemini API Key", ok: !!keys.gemini },
                ].map(({ label, ok }) => (
                  <div
                    key={label}
                    className={`flex items-center gap-2 text-xs rounded-lg px-3 py-2 ${
                      ok
                        ? "bg-green-900/20 border border-green-600/30 text-green-400"
                        : "bg-red-900/20 border border-red-600/30 text-red-400"
                    }`}
                  >
                    {ok ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>{label}</span>
                  </div>
                ))}
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full h-14 text-lg font-bold shadow-[0_0_20px_rgba(194,24,91,0.4)] hover:shadow-[0_0_30px_rgba(194,24,91,0.6)] transition-all"
                disabled={isRunning || missingKeys.length > 0}
              >
                {isRunning ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    {phase === "uploading" ? `Uploading ${uploadPct}%` : "Starting…"}
                  </span>
                ) : (
                  "Start Recap"
                )}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </Layout>
  );
}
