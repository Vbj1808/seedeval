import { FrameCritique } from "@/lib/types";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function FrameCritiqueList({ critiques }: { critiques: FrameCritique[] }) {
  const flagged = critiques.filter((critique) => critique.flagged);

  if (!flagged.length) {
    return <div className="text-sm text-muted-foreground">No flagged frames yet.</div>;
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-1">
      {flagged.map((critique) => (
        <div
          key={critique.id}
          className={cn(
            "w-[220px] shrink-0 rounded-lg border bg-background p-3",
            critique.flagged ? "border-red-500/50" : "border-border",
          )}
          title={critique.reason || ""}
        >
          <img
            src={`${API}/${critique.image_path}`}
            alt={`Frame ${critique.frame_idx}`}
            className="aspect-video w-full rounded-md object-cover"
          />
          <div className="mt-3 space-y-1">
            <div className="text-xs font-medium text-foreground">
              Frame {critique.frame_idx} · {critique.timestamp_s.toFixed(2)}s
            </div>
            <div className="text-xs text-muted-foreground">{critique.reason}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
