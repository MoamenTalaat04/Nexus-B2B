"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ChevronDown, ChevronUp, Clock, Cpu } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CUSTOMER_ROUTES } from "@/config/routes";
import { ApiError, api } from "@/lib/api";
import type { RunDetailOut } from "@/lib/leads-types";

export function ActivityDetail({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunDetailOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const loadRun = useCallback(async () => {
    try {
      const detail = await api.get<RunDetailOut>(`/runs/${runId}`, {
        suppressUnauthorizedRedirect: true,
      });
      setRun(detail);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void Promise.resolve().then(() => loadRun());
  }, [loadRun]);

  useEffect(() => {
    if (!run || (run.status !== "queued" && run.status !== "running")) return;
    const timer = window.setInterval(() => {
      void loadRun();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run, loadRun]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading run trace...</p>;
  }

  if (error || !run) {
    return (
      <div className="space-y-4">
        <Link href={CUSTOMER_ROUTES.activity}>
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1.5 size-4" />
            Back to Activity
          </Button>
        </Link>
        <p className="text-sm text-red-600">{error ?? "Run not found."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href={CUSTOMER_ROUTES.activity}>
            <Button variant="outline" size="sm">
              <ArrowLeft className="mr-1.5 size-4" />
              Back
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground">{run.kind}</h1>
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
            <p className="font-mono text-xs text-muted-foreground">{run.id}</p>
          </div>
        </div>
      </div>

      {run.error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {run.error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Duration", value: run.duration_ms !== null ? `${run.duration_ms} ms` : "—" },
          { label: "Input Tokens", value: run.total_input_tokens.toLocaleString() },
          { label: "Output Tokens", value: run.total_output_tokens.toLocaleString() },
          { label: "Cost (USD)", value: `$${run.total_cost_usd.toFixed(5)}` },
        ].map((item) => (
          <Card key={item.label} className="border-border/80 bg-card">
            <CardContent className="p-3.5">
              <p className="text-[11px] font-medium text-muted-foreground uppercase">{item.label}</p>
              <p className="mt-1 text-lg font-bold text-foreground">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {run.output_summary && (
        <Card className="border-border/80 bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Output Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-lg bg-surface/70 p-3 font-mono text-xs dark:bg-[#0A140C]">
              {JSON.stringify(run.output_summary, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground uppercase">
          Execution Timeline ({run.steps.length} steps)
        </h2>

        {run.steps.map((step) => {
          const isOpen = expandedStep === step.id;
          return (
            <Card key={step.id} className="border-border/80 bg-card">
              <CardContent className="space-y-3 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <Badge variant="outline">#{step.seq}</Badge>
                    <Badge variant="secondary">{step.step_type}</Badge>
                    <span className="font-semibold text-foreground">{step.name}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    {step.model && (
                      <span className="inline-flex items-center gap-1 font-mono">
                        <Cpu className="size-3.5" />
                        {step.model}
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1">
                      <Clock className="size-3.5" />
                      {step.latency_ms} ms
                    </span>
                    <span>
                      {(step.input_tokens + step.output_tokens).toLocaleString()} tok · $
                      {step.cost_usd.toFixed(5)}
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setExpandedStep(isOpen ? null : step.id)}
                    >
                      {isOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                      <span className="ml-1 text-xs">JSON</span>
                    </Button>
                  </div>
                </div>

                {isOpen && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="mb-1 text-[11px] font-semibold text-muted-foreground uppercase">
                        Input
                      </p>
                      <pre className="max-h-72 overflow-auto rounded-lg bg-surface/70 p-3 font-mono text-[11px] dark:bg-[#0A140C]">
                        {JSON.stringify(step.input, null, 2)}
                      </pre>
                    </div>
                    <div>
                      <p className="mb-1 text-[11px] font-semibold text-muted-foreground uppercase">
                        Output
                      </p>
                      <pre className="max-h-72 overflow-auto rounded-lg bg-surface/70 p-3 font-mono text-[11px] dark:bg-[#0A140C]">
                        {JSON.stringify(step.output, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
