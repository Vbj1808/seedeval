import { CheckResultCard } from "@/components/CheckResultCard";
import { FrameCritiqueList } from "@/components/FrameCritiqueList";
import { ProgressStream } from "@/components/ProgressStream";
import { ScoreBadge } from "@/components/ScoreBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { getRun } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await getRun(id);

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-8 lg:px-8">
        <header className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-4xl">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Run {run.id}</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
                {run.prompt}
              </h1>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Overall</p>
              <div className="mt-3">
                <ScoreBadge score={run.overall_score} large />
              </div>
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            Model: {run.model} · Status: {run.status} · Cost: ${run.total_cost_usd.toFixed(2)} ·
            Latency: {run.total_latency_s.toFixed(1)}s
          </div>
        </header>

        <ProgressStream runId={run.id} initialDone={run.status === "done"} />

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            {run.video_path ? (
              <video
                className="aspect-video w-full bg-black"
                src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/${run.video_path}`}
                controls
                loop
                autoPlay
                muted
              />
            ) : (
              <div className="flex aspect-video items-center justify-center bg-black text-sm text-muted-foreground">
                Video pending
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-card p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Verdict</p>
            <div className="mt-3 text-sm leading-6 text-foreground">
              {run.verdict ? (
                run.verdict
              ) : (
                <div className="space-y-3">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-11/12" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          {run.check_results.map((check) => (
            <CheckResultCard key={check.id} check={check} />
          ))}
        </section>

        <section className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-medium text-foreground">Flagged Frames</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Frames with critiques from the adherence judge.
              </p>
            </div>
          </div>
          <div className="mt-4">
            <FrameCritiqueList critiques={run.frame_critiques} />
          </div>
        </section>
      </div>
    </main>
  );
}
