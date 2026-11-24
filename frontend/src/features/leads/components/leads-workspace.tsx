"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Download,
  ExternalLink,
  Globe,
  Loader2,
  MapPin,
  Phone,
  Play,
  Search,
  Star,
  X,
} from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CUSTOMER_ROUTES } from "@/config/routes";
import { ApiError, api } from "@/lib/api";
import type {
  LeadDetailOut,
  LeadListOut,
  LeadStatsOut,
  LeadSummaryOut,
  RunOut,
} from "@/lib/leads-types";
import { LeadStatusValues } from "@/lib/types";

export function LeadsWorkspace() {
  const [leads, setLeads] = useState<LeadSummaryOut[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<LeadStatsOut | null>(null);
  const [loading, setLoading] = useState(true);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [minScore, setMinScore] = useState("");
  const [governorate, setGovernorate] = useState("");
  const [sort, setSort] = useState<"created_at" | "score" | "name">("created_at");

  const [running, setRunning] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeRunStatus, setActiveRunStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [drawerLead, setDrawerLead] = useState<LeadDetailOut | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  const buildParams = useCallback(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (statusFilter) params.set("status", statusFilter);
    if (minScore) params.set("min_score", minScore);
    if (governorate.trim()) params.set("governorate", governorate.trim());
    params.set("sort", sort);
    params.set("order", sort === "name" ? "asc" : "desc");
    return params;
  }, [query, statusFilter, minScore, governorate, sort]);

  const loadData = useCallback(async () => {
    try {
      const params = buildParams();
      const [listRes, statsRes] = await Promise.all([
        api.get<LeadListOut>(`/leads?${params.toString()}`, { suppressUnauthorizedRedirect: true }),
        api.get<LeadStatsOut>("/leads/stats", { suppressUnauthorizedRedirect: true }),
      ]);
      setLeads(listRes.items);
      setTotal(listRes.total);
      setStats(statsRes);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  useEffect(() => {
    void Promise.resolve().then(() => loadData());
  }, [loadData]);

  async function handleRunAgentNow(mode: "live" | "sandbox") {
    setError(null);
    setMessage(null);
    setRunning(true);
    setActiveRunStatus("queued");
    try {
      const { run_id } = await api.post<{ run_id: string }>(
        "/runs/sourcing",
        { mode },
        { suppressUnauthorizedRedirect: true },
      );
      setActiveRunId(run_id);

      for (let i = 0; i < 90; i++) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const run = await api.get<RunOut>(`/runs/${run_id}`, { suppressUnauthorizedRedirect: true });
        setActiveRunStatus(run.status);
        if (run.status === "succeeded") {
          await loadData();
          setMessage(
            mode === "sandbox"
              ? "Sandbox run completed with ICP-matched synthetic leads & whitelist phones!"
              : "Live discovery & scoring run completed!",
          );
          return;
        }
        if (run.status === "failed" || run.status === "cancelled") {
          setError(run.error || "Agent run failed.");
          return;
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start agent run.");
      setActiveRunStatus(null);
    } finally {
      setRunning(false);
    }
  }

  async function openDrawer(leadId: string) {
    setDrawerLoading(true);
    try {
      const detail = await api.get<LeadDetailOut>(`/leads/${leadId}`, {
        suppressUnauthorizedRedirect: true,
      });
      setDrawerLead(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load lead details.");
    } finally {
      setDrawerLoading(false);
    }
  }

  function handleExportExcel() {
    const params = buildParams();
    window.location.href = `/api/v1/leads/export.xlsx?${params.toString()}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Leads</h1>
          <p className="text-sm text-muted-foreground">
            Discovered B2B prospects scored against your active ICP.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" onClick={handleExportExcel}>
            <Download className="mr-1.5 size-4" />
            Export Excel
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={running}
            onClick={() => void handleRunAgentNow("sandbox")}
          >
            {running ? (
              <>
                <Loader2 className="mr-1.5 size-4 animate-spin" />
                Running ({activeRunStatus ?? "queued"})...
              </>
            ) : (
              <>
                <Play className="mr-1.5 size-4" />
                Run Sandbox (Whitelist)
              </>
            )}
          </Button>
          <Button
            type="button"
            disabled={running}
            onClick={() => void handleRunAgentNow("live")}
            className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]"
          >
            {running ? (
              <>
                <Loader2 className="mr-1.5 size-4 animate-spin" />
                Searching ({activeRunStatus ?? "queued"})...
              </>
            ) : (
              <>
                <Globe className="mr-1.5 size-4" />
                Run Live Search
              </>
            )}
          </Button>
        </div>
      </div>

      {activeRunId && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-primary/30 bg-primary/5 px-4 py-2.5 text-xs">
          <span>
            Run <span className="font-mono font-semibold">{activeRunId.slice(0, 8)}</span> status:{" "}
            <strong className="capitalize">{activeRunStatus}</strong>
          </span>
          <Link
            href={CUSTOMER_ROUTES.activityDetail(activeRunId)}
            className="font-semibold text-primary underline underline-offset-4 dark:text-lime-300"
          >
            View live trace →
          </Link>
        </div>
      )}

      {message && (
        <p className="rounded-lg border border-lime-500/30 bg-lime-50 px-3 py-2 text-xs text-lime-800 dark:bg-lime-950/60 dark:text-lime-200">
          {message}
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            { label: "Total Leads", value: stats.total },
            { label: "Qualified", value: stats.qualified_count },
            { label: "Enriched", value: stats.enriched_count },
            { label: "Contacted", value: stats.contacted_count },
            { label: "Avg Score", value: stats.avg_score !== null ? `${stats.avg_score}/10` : "—" },
          ].map((stat) => (
            <Card key={stat.label} className="border-border/80 bg-card">
              <CardContent className="p-3.5">
                <p className="text-[11px] font-medium text-muted-foreground uppercase">{stat.label}</p>
                <p className="mt-1 text-xl font-bold text-foreground">{stat.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card className="border-border/80 bg-card">
        <CardContent className="grid gap-3 p-4 sm:grid-cols-5">
          <div className="relative sm:col-span-2">
            <Search className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
            <Input
              dir="auto"
              placeholder="Search name, category, city, or ref..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
            className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
          >
            <option value="">All statuses</option>
            {LeadStatusValues.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>

          <Input
            type="number"
            min={0}
            max={10}
            placeholder="Min score (0-10)"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
          />

          <div className="flex gap-2">
            <Input
              dir="auto"
              placeholder="Governorate"
              value={governorate}
              onChange={(e) => setGovernorate(e.target.value)}
            />
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as "created_at" | "score" | "name")}
              aria-label="Sort leads"
              className="h-10 rounded-lg border border-input bg-surface/70 px-2.5 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
            >
              <option value="created_at">Newest</option>
              <option value="score">Score</option>
              <option value="name">Name</option>
            </select>
          </div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-border/80 bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface/60 text-xs text-muted-foreground uppercase dark:bg-[#0A140C]">
              <tr>
                <th className="px-4 py-3">Lead</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Rating</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/70">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-xs text-muted-foreground">
                    Loading leads...
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-xs text-muted-foreground">
                    No leads match your filters yet. Click <strong>Run agent now</strong> to discover prospects.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => void openDrawer(lead.id)}
                    className="cursor-pointer transition-colors hover:bg-surface-secondary/60"
                  >
                    <td className="px-4 py-3">
                      <AutoDirText as="p" className="font-semibold text-foreground">
                        {lead.name}
                      </AutoDirText>
                      {lead.category && (
                        <AutoDirText as="p" className="text-xs text-muted-foreground">
                          {lead.category}
                        </AutoDirText>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {[lead.city, lead.governorate].filter(Boolean).join(", ") || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {lead.score !== null ? (
                        <Badge variant={lead.score >= 7 ? "default" : "secondary"}>
                          {lead.score}/10
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className="capitalize">
                        {lead.status.replace(/_/g, " ")}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {lead.rating !== null ? (
                        <span className="inline-flex items-center gap-1">
                          <Star className="size-3.5 fill-amber-400 text-amber-400" />
                          {lead.rating} ({lead.reviews_count ?? 0})
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
          Showing {leads.length} of {total} leads
        </div>
      </Card>

      {(drawerLoading || drawerLead) && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs">
          <div className="h-full w-full max-w-md overflow-y-auto border-l border-border bg-card p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <AutoDirText as="h2" className="text-lg font-bold text-foreground">
                  {drawerLead?.name ?? "Loading..."}
                </AutoDirText>
                {drawerLead?.category && (
                  <AutoDirText as="p" className="text-xs text-muted-foreground">
                    {drawerLead.category}
                  </AutoDirText>
                )}
              </div>
              <Button type="button" variant="ghost" size="icon" onClick={() => setDrawerLead(null)}>
                <X className="size-4" />
              </Button>
            </div>

            {drawerLoading ? (
              <p className="mt-6 text-xs text-muted-foreground">Loading lead details...</p>
            ) : (
              drawerLead && (
                <div className="mt-5 space-y-5 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="capitalize">
                      {drawerLead.status.replace(/_/g, " ")}
                    </Badge>
                    {drawerLead.score !== null && (
                      <Badge>Score: {drawerLead.score}/10</Badge>
                    )}
                    <Badge variant="secondary">#{drawerLead.ref_code}</Badge>
                  </div>

                  {drawerLead.address && (
                    <div className="flex items-start gap-2 text-xs text-muted-foreground">
                      <MapPin className="mt-0.5 size-4 shrink-0" />
                      <AutoDirText>{drawerLead.address}</AutoDirText>
                    </div>
                  )}

                  {drawerLead.website && (
                    <a
                      href={drawerLead.website}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline dark:text-lime-300"
                    >
                      <Globe className="size-3.5" />
                      {drawerLead.website}
                      <ExternalLink className="size-3" />
                    </a>
                  )}

                  {drawerLead.score_reasons.length > 0 && (
                    <div className="space-y-1.5 rounded-xl border border-border/80 bg-surface/50 p-3 dark:border-[#223D27] dark:bg-[#0A140C]/60">
                      <p className="text-xs font-semibold text-foreground uppercase">Scoring Reasons</p>
                      <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                        {drawerLead.score_reasons.map((r, i) => (
                          <li key={i}>
                            <AutoDirText>{r}</AutoDirText>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {drawerLead.disqualify_reason && (
                    <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                      <AutoDirText>{drawerLead.disqualify_reason}</AutoDirText>
                    </p>
                  )}

                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-foreground uppercase">Contacts</p>
                    {drawerLead.contacts.length === 0 ? (
                      <p className="text-xs text-muted-foreground">No contacts discovered yet.</p>
                    ) : (
                      drawerLead.contacts.map((c) => (
                        <div
                          key={c.id}
                          className="flex items-center justify-between rounded-lg border border-border/70 px-3 py-2 text-xs"
                        >
                          <span className="inline-flex items-center gap-1.5 font-medium">
                            <Phone className="size-3.5 text-primary dark:text-lime-400" />
                            {c.value}
                          </span>
                          <Badge variant="secondary">{c.type}</Badge>
                        </div>
                      ))
                    )}
                  </div>

                  <Link href={CUSTOMER_ROUTES.leadDetail(drawerLead.id)} className="block">
                    <Button className="w-full" variant="outline">
                      Open Full Lead Page
                    </Button>
                  </Link>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
