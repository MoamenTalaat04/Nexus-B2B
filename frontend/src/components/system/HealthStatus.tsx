"use client";

import { useQuery } from "@tanstack/react-query";

type Health = { status: "ok" | "degraded"; db: "ok" | "error"; redis: "ok" | "error" };

async function fetchHealth(): Promise<Health> {
  // Same-origin call: next.config.ts rewrites /api/* to the FastAPI backend.
  const res = await fetch("/api/v1/health");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as Health;
}

export function HealthStatus() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["health"], queryFn: fetchHealth });

  if (isLoading) return <p className="text-sm text-muted-foreground">Checking backend…</p>;
  if (isError || !data)
    return (
      <p role="status" className="text-sm text-destructive">
        Backend unreachable. Start it with <code>uv run poe api</code> in backend/.
      </p>
    );
  return (
    <p role="status" className="text-sm">
      Backend: <strong>{data.status}</strong> · database {data.db} · redis {data.redis}
    </p>
  );
}
