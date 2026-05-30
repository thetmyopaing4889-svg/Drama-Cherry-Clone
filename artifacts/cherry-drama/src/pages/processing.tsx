import { useEffect } from "react";
import { Layout } from "@/components/layout";
import { useListJobs, useDeleteJob, getListJobsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { Trash2, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const STAGE_LABELS: Record<string, string> = {
  "Waiting to start": "Waiting to start",
  "Transcribing": "Transcribing audio",
  "Analyzing scenes": "Analyzing scenes",
  "Writing recap script": "Writing recap script",
  "Generating voice": "Generating narrator voice",
  "Composing video": "Composing final video",
  "Done": "Done",
};

function StatusBadge({ status }: { status: string }) {
  if (status === "completed") return <Badge className="bg-green-600/20 text-green-400 border-green-600/30">Completed</Badge>;
  if (status === "failed") return <Badge className="bg-red-600/20 text-red-400 border-red-600/30">Failed</Badge>;
  if (status === "processing") return <Badge className="bg-primary/20 text-primary border-primary/30">Processing</Badge>;
  return <Badge className="bg-muted text-muted-foreground border-border">Pending</Badge>;
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
                        <span className="text-muted-foreground">{STAGE_LABELS[job.stage] ?? job.stage}</span>
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
              {doneJobs.slice(0, 10).map(job => (
                <Card key={job.id} className="bg-card/30 border-border">
                  <CardContent className="p-4 flex items-center justify-between">
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
