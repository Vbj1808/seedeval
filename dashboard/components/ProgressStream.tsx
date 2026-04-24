"use client";

import { useEffect, useState } from "react";

import { streamRun } from "@/lib/api";
import { StreamEvent } from "@/lib/types";

export function ProgressStream({
  runId,
  initialDone,
}: {
  runId: string;
  initialDone: boolean;
}) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [done, setDone] = useState(initialDone);

  useEffect(() => {
    if (done) return;
    const close = streamRun(runId, (event) => {
      setEvents((prev) => [event, ...prev]);
      if (event.stage === "done") {
        setDone(true);
        window.location.reload();
      }
    });
    return close;
  }, [runId, done]);

  if (done) return null;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Progress
      </div>
      <div className="space-y-1 font-mono text-xs">
        {events.length === 0 ? (
          <div className="text-muted-foreground">Waiting for first event...</div>
        ) : (
          events.map((event, index) => (
            <div key={`${event.stage}-${index}`} className="text-muted-foreground">
              [{new Date().toISOString().slice(11, 19)}] {event.stage}:{" "}
              {event.message || JSON.stringify(event)}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
