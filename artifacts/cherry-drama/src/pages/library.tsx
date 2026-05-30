import { Layout } from "@/components/layout";
import { useListJobs, useDeleteJob, getListJobsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download, Trash2, Film, Clock } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return "--";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function LibraryPage() {
  const { data: jobs } = useListJobs();
  const deleteJob = useDeleteJob();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const completed = jobs?.filter(j => j.status === "completed") ?? [];

  const handleDelete = (id: number) => {
    deleteJob.mutate({ id }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() });
        toast({ title: "Recap deleted" });
      }
    });
  };

  return (
    <Layout>
      <div className="max-w-6xl mx-auto w-full p-8 pt-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2 font-serif tracking-wide">Recap Library</h1>
          <p className="text-muted-foreground">{completed.length} completed recap{completed.length !== 1 ? "s" : ""}</p>
        </div>

        {completed.length === 0 && (
          <div className="text-center py-24 text-muted-foreground">
            <Film className="h-16 w-16 mx-auto mb-4 opacity-20" />
            <p className="text-xl font-medium mb-2">No recaps yet</p>
            <p className="text-sm">Completed recaps will appear here.</p>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {completed.map(job => (
            <div key={job.id} className="group bg-card/50 border border-border rounded-xl overflow-hidden hover:border-primary/40 transition-all">
              <div className="aspect-video bg-gradient-to-br from-[#2a0f18] to-[#1a0a0f] relative overflow-hidden">
                {job.thumbnailUrl ? (
                  <img src={job.thumbnailUrl} alt={job.movieTitle} className="w-full h-full object-cover" />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <Film className="h-10 w-10 text-primary/40 mx-auto mb-2" />
                      <span className="text-xs text-muted-foreground">No thumbnail</span>
                    </div>
                  </div>
                )}
                <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-0.5 rounded flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDuration(job.durationSeconds)}
                </div>
              </div>
              <div className="p-4">
                <div className="font-semibold text-white mb-1 truncate">{job.movieTitle}</div>
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs border-primary/30 text-primary bg-primary/10">
                    {job.language === "myanmar" ? "Myanmar" : "Japanese"}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{new Date(job.createdAt).toLocaleDateString()}</span>
                </div>
                <div className="mt-3 flex gap-2">
                  {job.outputUrl ? (
                    <Button asChild size="sm" className="flex-1 h-8 text-xs">
                      <a href={job.outputUrl} download>
                        <Download className="mr-1.5 h-3.5 w-3.5" />
                        Download
                      </a>
                    </Button>
                  ) : (
                    <Button size="sm" className="flex-1 h-8 text-xs" disabled>
                      <Download className="mr-1.5 h-3.5 w-3.5" />
                      No output
                    </Button>
                  )}
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive shrink-0" onClick={() => handleDelete(job.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
}
