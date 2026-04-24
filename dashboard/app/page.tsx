import { NewRunForm } from "@/components/NewRunForm";
import { RunCard } from "@/components/RunCard";
import { listRuns } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const runs = await listRuns();

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-8 lg:px-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">SeedEval</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Evaluation harness for ByteDance Seedance. Run generations, inspect failure modes,
            and stream progress while the checks execute.
          </p>
        </header>

        <section className="grid gap-8 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
          <div className="rounded-lg border border-border bg-card p-5">
            <h2 className="text-sm font-medium text-foreground">New Run</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Start an eval and jump straight to the live run detail view.
            </p>
            <div className="mt-4">
              <NewRunForm />
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="grid grid-cols-[minmax(0,1.8fr)_140px_140px_120px_140px] gap-4 border-b border-border px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <div>Prompt</div>
              <div>Model</div>
              <div>Overall</div>
              <div>Status</div>
              <div>Created</div>
            </div>
            <div className="divide-y divide-border">
              {runs.map((run) => (
                <RunCard key={run.id} run={run} />
              ))}
              {runs.length === 0 ? (
                <div className="px-4 py-10 text-sm text-muted-foreground">No runs yet.</div>
              ) : null}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
