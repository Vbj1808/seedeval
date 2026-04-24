import { RunDetail, RunSummary, StreamEvent } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listRuns(): Promise<RunSummary[]> {
  const response = await fetch(`${API}/runs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load runs: ${response.status}`);
  }
  return response.json();
}

export async function getRun(id: string): Promise<RunDetail> {
  const response = await fetch(`${API}/runs/${id}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load run ${id}: ${response.status}`);
  }
  return response.json();
}

export function streamRun(id: string, onEvent: (event: StreamEvent) => void): () => void {
  const es = new EventSource(`${API}/runs/${id}/stream`);
  es.onmessage = (message) => {
    onEvent(JSON.parse(message.data) as StreamEvent);
  };
  return () => es.close();
}

export async function createRun(prompt: string, model: string): Promise<{ run_id: string }> {
  const response = await fetch(`${API}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, model }),
  });
  if (!response.ok) {
    throw new Error(`Failed to create run: ${response.status}`);
  }
  return response.json();
}
