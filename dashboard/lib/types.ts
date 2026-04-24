export type Plan = {
  prompt_class: "landscape" | "portrait" | "action" | "abstract";
  checks_to_run: string[];
  frame_sample_count: number;
  temporal_drift_threshold: number;
  rationale: string;
};

export type RunSummary = {
  id: string;
  prompt: string;
  model: string;
  status: string;
  overall_score: number | null;
  total_cost_usd: number;
  created_at: string;
};

export type CheckResult = {
  id: number;
  run_id: string;
  check_name: string;
  score: number | null;
  passed: boolean | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type FrameCritique = {
  id: number;
  frame_id: number;
  check_name: string;
  score: number | null;
  flagged: boolean | null;
  reason: string | null;
  frame_idx: number;
  timestamp_s: number;
  image_path: string;
};

export type RunDetail = {
  id: string;
  created_at: string;
  prompt: string;
  model: string;
  video_path: string | null;
  status: string;
  total_cost_usd: number;
  total_latency_s: number;
  overall_score: number | null;
  verdict: string | null;
  raw_config: {
    prompt: string;
    model: string;
    duration_s: number;
    plan?: Plan;
  };
  check_results: CheckResult[];
  frame_critiques: FrameCritique[];
};

export type StreamEvent = {
  stage: string;
  message?: string;
  plan?: Plan;
  latency_s?: number;
  cost_usd?: number;
  count?: number;
  check?: string;
  frame_idx?: number;
  score?: number;
  overall_score?: number | null;
  verdict?: string;
};
