import Link from "next/link";

import { ScoreBadge } from "@/components/ScoreBadge";
import { RunSummary } from "@/lib/types";

function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.max(0, Math.round(diffMs / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function RunCard({ run }: { run: RunSummary }) {
  return (
    <Link
      href={`/runs/${run.id}`}
      className="grid grid-cols-[minmax(0,1.8fr)_140px_140px_120px_140px] gap-4 px-4 py-4 text-sm transition-colors hover:bg-accent/40"
    >
      <div className="min-w-0">
        <div className="truncate text-foreground">{run.prompt}</div>
      </div>
      <div className="truncate text-muted-foreground">{run.model}</div>
      <div>
        <ScoreBadge score={run.overall_score} />
      </div>
      <div className="capitalize text-muted-foreground">{run.status}</div>
      <div className="text-muted-foreground">{relativeTime(run.created_at)}</div>
    </Link>
  );
}
