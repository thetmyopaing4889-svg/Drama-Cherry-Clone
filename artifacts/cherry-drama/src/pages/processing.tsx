import { useEffect, useState } from "react";
import { Layout } from "@/components/layout";
import { useListJobs, useDeleteJob, getListJobsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { Trash2, Clock, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

function StatusBadge({ status }: { status: string }) {
  if (status === "completed") return <Badge className="bg-green-600/20 text-green-400 border-green-600/30">Completed</Badge>;
  if (status === "failed") return <Badge className="bg-red-600/20 text-red-400 border-red-600/30">Failed</Badge>;
  if (status === "processing") return <Badge className="bg-primary/20 text-primary border-primary/30">Processing</Badge>;
  return <Badge className="bg-muted text-muted-foreground border-border">Pending</Badge>;
}

function ErrorDetail({ error }: { error: string }) {
  const [expanded, setExpanded] = useState(false);

  const isRateLimit = error.includes("429") || error.includes("RESOURCE_EXHAUSTED");
  const isKeyError = error.includes("API keys") || error.includes("404");
  const isQuota = error.includes("quota") || error.includes("quota exceeded");

  let summary = error;
  if (isRateLimit || isQuota) summary = "Gemini API rate limit exceeded. The pipeline will retry automatically after a cooldown.";
  else if (isKeyError) summary = "API keys were not found. Delete this job and re-upload with valid keys.";
  else if (error.length > 120) summary = error.slice(0, 120) + "…";

  return (
    <div className="mt-3 rounded-lg bg-red-950/40 border border-red-600/20 text-xs text-red-300 overflow-hidden">
      <div
        className="flex items-start justify-between gap-2 p-3 cursor-pointer select-none"
        onClick={() => setExpanded(v => !v)}
      >
        <span className="leading-relaxed">{summary}</span>
        {error.length > 120 && (
          <span className="shrink-0 text-red-400/60 mt-0.5">
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </span>
        )}
      </div>
      {expanded && error.length > 120 && (
        <div className="px-3 pb-3 text-red-400/70 font-mono text-[11px] whitespace-pre-wrap break-all border-t border-red-600/20 pt-2">
          {error}
        </div>
      )}
    </div>
  );
}

export default function ProcessingPage() {
  const { data: jobs, isLoading } = useListJobs();
  const deleteJob = useDeleteJob();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  useEffect(() => {
    const hasActive = jobs?.some(j => j.status === "pending" || j.status === "processing");
    if (!hasActive) return;
    const id = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() });
    }, 3000);
    return () => clearInterval(id);
  }, [jobs, queryClient]);

  const handleDelete = (id: number) => {
    deleteJob.mutate({ id }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() });
        toast({ title: "Job deleted" });
      }
    });
  };

  const activeJobs = jobs?.filter(j => j.status === "pending" || j.status === "processing") ?? [];
  const doneJobs = jobs?.filter(j => j.status === "completed" || j.status === "failed") ?? [];

  return (
    <Layout>
      <div className="max-w-4xl mx-auto w-full p-8 pt-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2 font-serif tracking-wide">Processing Queue</h1>
          <p className="text-muted-foreground">Track your recap jobs in real time.</p>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        )}

        {!isLoading && jobs?.length === 0 && (
          <div className="text-center py-16 text-muted-foreground">
            <Clock className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg">No jobs yet. Upload a video to get started.</p>
          </div>
        )}

        {activeJobs.length > 0 && (
          <section className="mb-8">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">Active</h2>
            <div className="space-y-4">
              {activeJobs.map(job => (
                <Card key={job.id} className="bg-card/60 border-primary/20 backdrop-blur-sm">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <div className="font-semibold text-white text-lg">{job.movieTitle}</div>
                        <div className="text-sm text-muted-foreground mt-0.5">
                          {job.language === "myanmar" ? "Myanmar" : "Japanese"} Recap
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={job.status} />
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => handleDelete(job.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{job.stage}</span>
                        <span className="text-white font-medium">{job.progress}%</span>
                      </div>
                      <Progress value={job.progress} className="h-2" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        {doneJobs.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">Recent</h2>
            <div className="space-y-3">
              {doneJobs.slice(0, 20).map(job => (
                <Card key={job.id} className={`border-border ${job.status === "failed" ? "bg-red-950/10" : "bg-card/30"}`}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {job.status === "completed"
                          ? <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
                          : <XCircle className="h-5 w-5 text-red-500 shrink-0" />}
                        <div>
                          <div className="font-medium text-white">{job.movieTitle}</div>
                          <div className="text-xs text-muted-foreground">
                            {job.language === "myanmar" ? "Myanmar" : "Japanese"} &middot; {new Date(job.createdAt).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={job.status} />
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => handleDelete(job.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    {job.status === "failed" && job.error && (
                      <ErrorDetail error={job.error} />
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}
      </div>
    </Layout>
  );
}
