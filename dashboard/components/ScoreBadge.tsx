import { cn } from "@/lib/utils";

export function scoreTone(score: number | null) {
  if (score === null || Number.isNaN(score)) {
    return "bg-zinc-800 text-zinc-200 border-zinc-700";
  }
  if (score < 4) {
    return "border-red-500/40 bg-red-500/10 text-red-300";
  }
  if (score < 7) {
    return "border-amber-500/40 bg-amber-500/10 text-amber-300";
  }
  return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
}

export function ScoreBadge({
  score,
  large = false,
}: {
  score: number | null;
  large?: boolean;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-1 font-medium tabular-nums",
        large ? "text-2xl" : "text-sm",
        scoreTone(score),
      )}
    >
      {score === null ? "--" : score.toFixed(2)}
    </div>
  );
}
