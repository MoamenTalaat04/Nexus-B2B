"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, ArrowRight, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CUSTOMER_ROUTES } from "@/config/routes";
import { ApiError, api } from "@/lib/api";
import type { RunListOut, RunOut } from "@/lib/leads-types";
import { AgentRunKindValues, AgentRunStatusValues } from "@/lib/types";

export function ActivityList() {
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [total, setTotal] = useState(0);
  const [kindFilter, setKindFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (kindFilter) params.set("kind", kindFilter);
      if (statusFilter) params.set("status", statusFilter);
      const res = await api.get<RunListOut>(`/runs?${params.toString()}`, {
        suppressUnauthorizedRedirect: true,
      });
      setRuns(res.items);
      setTotal(res.total);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [kindFilter, statusFilter]);

  useEffect(() => {
    void Promise.resolve().then(() => loadRuns());
  }, [loadRuns]);

  const hasActive = runs.some((r) => r.status === "queued" || r.status === "running");

  useEffect(() => {
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void loadRuns();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActive, loadRuns]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Agent Activity</h1>
          <p className="text-sm text-muted-foreground">
            Live execution logs, LLM token usage, and step-by-step traces.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadRuns()}>
          <RefreshCw className="mr-1.5 size-4" />
          Refresh
        </Button>
      </div>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          aria-label="Filter by kind"
          className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
        >
          <option value="">All kinds</option>
          {AgentRunKindValues.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
        >
          <option value="">All statuses</option>
          {AgentRunStatusValues.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <Card className="overflow-hidden border-border/80 bg-card">
        <CardContent className="divide-y divide-border/70 p-0">
          {loading ? (
            <p className="p-6 text-center text-xs text-muted-foreground">Loading runs...</p>
          ) : runs.length === 0 ? (
            <p className="p-6 text-center text-xs text-muted-foreground">No agent runs recorded yet.</p>
          ) : (
            runs.map((run) => (
              <Link
                key={run.id}
                href={CUSTOMER_ROUTES.activityDetail(run.id)}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-surface-secondary/60"
              >
                <div className="flex items-center gap-3">
                  <Activity className="size-4 text-primary dark:text-lime-400" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground">{run.kind}</span>
                      <Badge
                        variant={
                          run.status === "succeeded"
                            ? "default"
                            : run.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {run.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {new Date(run.created_at).toLocaleString()} · trigger: {run.trigger}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>
                    {(run.total_input_tokens + run.total_output_tokens).toLocaleString()} tokens
                  </span>
                  <span>${run.total_cost_usd.toFixed(4)}</span>
                  <span>{run.duration_ms !== null ? `${run.duration_ms} ms` : "—"}</span>
                  <ArrowRight className="size-4" />
                </div>
              </Link>
            ))
          )}
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">Total runs: {total}</p>
    </div>
  );
}
