"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { createRun } from "@/lib/api";
import { Button } from "@/components/ui/button";

const MODELS = [
  { value: "bytedance/seedance-1-0-lite-t2v", label: "Seedance Lite" },
  { value: "bytedance/seedance-1-0-pro-t2v", label: "Seedance Pro" },
];

export function NewRunForm() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState(MODELS[0].value);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim() || submitting) return;

    setSubmitting(true);
    try {
      const result = await createRun(prompt.trim(), model);
      router.push(`/runs/${result.run_id}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground" htmlFor="prompt">
          Prompt
        </label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={5}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none ring-0 transition focus:border-ring"
          placeholder="A cat walking on a wooden fence at sunset"
        />
      </div>
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground" htmlFor="model">
          Model
        </label>
        <select
          id="model"
          value={model}
          onChange={(event) => setModel(event.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-ring"
        >
          {MODELS.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Starting..." : "Run Evaluation"}
      </Button>
    </form>
  );
}
