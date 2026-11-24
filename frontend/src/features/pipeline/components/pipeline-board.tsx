"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type DragEvent } from "react";
import {
  ArrowRight,
  Download,
  Loader2,
  MapPin,
  PauseCircle,
  RefreshCw,
  Search,
  Star,
  Trophy,
  X,
  XCircle,
} from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import type { LeadListOut, LeadSummaryOut } from "@/lib/leads-types";
import { cn } from "@/lib/utils";

interface PipelineColumn {
  id: string;
  title: string;
  targetStatus: string;
  statuses: string[];
  accentClass: string;
}

const COLUMNS: PipelineColumn[] = [
  {
    id: "qualified",
    title: "New & Qualified",
    targetStatus: "qualified",
    statuses: ["new", "qualified"],
    accentClass: "border-t-emerald-500/70",
  },
  {
    id: "enriched",
    title: "Enriched",
    targetStatus: "enriched",
    statuses: ["enriched", "no_contact"],
    accentClass: "border-t-sky-500/70",
  },
  {
    id: "contacted",
    title: "Contacted",
    targetStatus: "contacted",
    statuses: ["queued", "contacted"],
    accentClass: "border-t-amber-500/70",
  },
  {
    id: "interested",
    title: "Replied & Interested",
    targetStatus: "interested",
    statuses: ["replied", "interested", "wants_offer", "wants_management", "later"],
    accentClass: "border-t-lime-500/80",
  },
  {
    id: "won",
    title: "Won",
    targetStatus: "won",
    statuses: ["won"],
    accentClass: "border-t-emerald-600",
  },
  {
    id: "lost",
    title: "Lost",
    targetStatus: "lost",
    statuses: ["lost", "not_interested", "disqualified", "wrong_contact", "opted_out"],
    accentClass: "border-t-rose-500/70",
  },
];

export function PipelineBoard() {
  const [leads, setLeads] = useState<LeadSummaryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverCol, setDragOverCol] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Won / Lost Outcome Modal
  const [outcomeTarget, setOutcomeTarget] = useState<{
    lead: LeadSummaryOut;
    outcome: "won" | "lost";
  } | null>(null);
  const [valueEgp, setValueEgp] = useState("");
  const [reason, setReason] = useState("");
  const [savingOutcome, setSavingOutcome] = useState(false);

  const loadLeads = useCallback(async () => {
    setError(null);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "100", sort: "created_at", order: "desc" });
      if (query.trim()) params.set("q", query.trim());
      const res = await api.get<LeadListOut>(`/leads?${params.toString()}`, {
        suppressUnauthorizedRedirect: true,
      });
      setLeads(res.items);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    void Promise.resolve().then(() => loadLeads());
  }, [loadLeads]);

  const grouped = useMemo(() => {
    const map: Record<string, LeadSummaryOut[]> = {};
    for (const col of COLUMNS) map[col.id] = [];
    for (const lead of leads) {
      const col = COLUMNS.find((c) => c.statuses.includes(lead.status)) ?? COLUMNS[0];
      map[col.id].push(lead);
    }
    return map;
  }, [leads]);

  async function moveLeadToColumn(lead: LeadSummaryOut, col: PipelineColumn) {
    if (col.statuses.includes(lead.status)) return;
    setError(null);

    if (col.targetStatus === "won" || col.targetStatus === "lost") {
      setOutcomeTarget({ lead, outcome: col.targetStatus });
      setValueEgp("");
      setReason("");
      return;
    }

    const previous = leads;
    setUpdatingId(lead.id);
    setLeads((prev) =>
      prev.map((item) => (item.id === lead.id ? { ...item, status: col.targetStatus } : item)),
    );
    try {
      await api.patch(`/leads/${lead.id}`, { status: col.targetStatus }, { suppressUnauthorizedRedirect: true });
    } catch (err) {
      setLeads(previous);
      setError(err instanceof ApiError ? err.message : "Could not move lead.");
    } finally {
      setUpdatingId(null);
    }
  }

  async function submitOutcome() {
    if (!outcomeTarget) return;
    setSavingOutcome(true);
    setError(null);
    try {
      await api.post(
        `/leads/${outcomeTarget.lead.id}/outcome`,
        {
          outcome: outcomeTarget.outcome,
          value_egp: outcomeTarget.outcome === "won" && valueEgp.trim() ? Number(valueEgp) : null,
          reason: reason.trim() || null,
        },
        { suppressUnauthorizedRedirect: true },
      );
      setLeads((prev) =>
        prev.map((item) =>
          item.id === outcomeTarget.lead.id
            ? { ...item, status: outcomeTarget.outcome, agent_paused: true }
            : item,
        ),
      );
      setOutcomeTarget(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record deal outcome.");
    } finally {
      setSavingOutcome(false);
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>, col: PipelineColumn) {
    e.preventDefault();
    setDragOverCol(null);
    const id = e.dataTransfer.getData("text/plain") || draggedId;
    setDraggedId(null);
    if (!id) return;
    const lead = leads.find((l) => l.id === id);
    if (lead) {
      void moveLeadToColumn(lead, col);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">CRM Pipeline</h1>
          <p className="text-sm text-muted-foreground">
            Drag and drop leads across stages or open any card for full details, notes, and messages.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-56">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search leads..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-9 pl-8 text-xs"
            />
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadLeads()}>
            <RefreshCw className="mr-1.5 size-3.5" />
            Refresh
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              window.location.href = "/api/v1/leads/export.xlsx";
            }}
          >
            <Download className="mr-1.5 size-3.5" />
            Export Excel
          </Button>
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}

      {loading ? (
        <div className="flex min-h-[300px] items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin text-primary" />
          Loading pipeline...
        </div>
      ) : (
        <div className="grid gap-3 overflow-x-auto pb-2 lg:grid-cols-6">
          {COLUMNS.map((col) => {
            const colLeads = grouped[col.id] ?? [];
            const isOver = dragOverCol === col.id;
            return (
              <div
                key={col.id}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOverCol(col.id);
                }}
                onDragLeave={() => setDragOverCol((prev) => (prev === col.id ? null : prev))}
                onDrop={(e) => handleDrop(e, col)}
                className={cn(
                  "flex min-h-[420px] min-w-[230px] flex-col rounded-2xl border border-t-4 border-border/80 bg-surface/40 p-2.5 transition-all dark:border-[#223D27] dark:bg-[#0A140C]/55",
                  col.accentClass,
                  isOver && "border-primary bg-primary/10 ring-2 ring-primary/25 dark:border-lime-400",
                )}
              >
                <div className="mb-2.5 flex items-center justify-between px-1">
                  <span className="text-xs font-semibold text-foreground">{col.title}</span>
                  <Badge variant="secondary" className="h-5 px-2 text-[10px]">
                    {colLeads.length}
                  </Badge>
                </div>

                <div className="flex-1 space-y-2 overflow-y-auto">
                  {colLeads.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-border/60 py-6 text-center text-[11px] text-muted-foreground dark:border-[#223D27]">
                      Drop leads here
                    </p>
                  ) : (
                    colLeads.map((lead) => {
                      const isDragging = draggedId === lead.id;
                      const isBusy = updatingId === lead.id;
                      return (
                        <div
                          key={lead.id}
                          draggable
                          onDragStart={(e) => {
                            setDraggedId(lead.id);
                            e.dataTransfer.setData("text/plain", lead.id);
                            e.dataTransfer.effectAllowed = "move";
                          }}
                          onDragEnd={() => {
                            setDraggedId(null);
                            setDragOverCol(null);
                          }}
                          className={cn(
                            "group cursor-grab space-y-2 rounded-xl border border-border/80 bg-card p-3 shadow-xs transition-all hover:border-primary/50 active:cursor-grabbing dark:border-[#223D27] dark:bg-[#112014] dark:hover:border-lime-400/50",
                            isDragging && "border-emerald-500 opacity-95 ring-2 ring-emerald-500/30",
                            isBusy && "opacity-60",
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <Link
                              href={`/leads/${lead.id}`}
                              className="min-w-0 flex-1 text-xs font-semibold text-foreground hover:text-primary dark:hover:text-lime-300"
                            >
                              <AutoDirText as="span" className="line-clamp-2">
                                {lead.name}
                              </AutoDirText>
                            </Link>
                            {lead.score !== null && (
                              <Badge variant="outline" className="h-5 shrink-0 gap-0.5 px-1.5 text-[10px]">
                                <Star className="size-2.5 fill-amber-400 text-amber-400" />
                                {lead.score}
                              </Badge>
                            )}
                          </div>

                          <div className="space-y-1 text-[11px] text-muted-foreground">
                            {lead.category && <p className="truncate">{lead.category}</p>}
                            {(lead.city || lead.governorate) && (
                              <p className="flex items-center gap-1 truncate">
                                <MapPin className="size-3 shrink-0" />
                                {[lead.city, lead.governorate].filter(Boolean).join(", ")}
                              </p>
                            )}
                          </div>

                          <div className="flex items-center justify-between gap-1 pt-1">
                            <div className="flex items-center gap-1">
                              <Badge variant="secondary" className="h-4 px-1.5 text-[10px] capitalize">
                                {lead.status.replace(/_/g, " ")}
                              </Badge>
                              {lead.agent_paused && (
                                <span title="AI Agent paused" className="text-amber-500">
                                  <PauseCircle className="size-3.5" />
                                </span>
                              )}
                            </div>

                            <Link
                              href={`/leads/${lead.id}`}
                              className="inline-flex items-center gap-0.5 text-[11px] font-medium text-primary hover:underline dark:text-lime-300"
                            >
                              Open
                              <ArrowRight className="size-3" />
                            </Link>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Won / Lost Outcome Modal */}
      {outcomeTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setOutcomeTarget(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-border bg-card p-5 shadow-2xl dark:border-[#223D27] dark:bg-[#112014]"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {outcomeTarget.outcome === "won" ? (
                  <Trophy className="size-5 text-emerald-500" />
                ) : (
                  <XCircle className="size-5 text-rose-500" />
                )}
                <h3 className="text-sm font-semibold text-foreground">
                  Mark Deal as {outcomeTarget.outcome === "won" ? "Won" : "Lost"}
                </h3>
              </div>
              <Button type="button" size="icon-sm" variant="ghost" onClick={() => setOutcomeTarget(null)}>
                <X className="size-4" />
              </Button>
            </div>

            <p className="mb-3 text-xs text-muted-foreground">
              Lead: <span className="font-semibold text-foreground">{outcomeTarget.lead.name}</span>
            </p>

            <div className="space-y-3">
              {outcomeTarget.outcome === "won" && (
                <div className="grid gap-1.5">
                  <Label htmlFor="deal-value" className="text-xs">
                    Deal Value (EGP, optional)
                  </Label>
                  <Input
                    id="deal-value"
                    type="number"
                    min={0}
                    placeholder="e.g. 25000"
                    value={valueEgp}
                    onChange={(e) => setValueEgp(e.target.value)}
                  />
                </div>
              )}

              <div className="grid gap-1.5">
                <Label htmlFor="deal-reason" className="text-xs">
                  Reason / Notes (optional)
                </Label>
                <textarea
                  id="deal-reason"
                  rows={3}
                  dir="auto"
                  placeholder={
                    outcomeTarget.outcome === "won"
                      ? "Signed annual contract..."
                      : "Budget mismatch / chose competitor..."
                  }
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                />
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setOutcomeTarget(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={savingOutcome}
                onClick={() => void submitOutcome()}
                className={cn(
                  outcomeTarget.outcome === "won"
                    ? "bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                    : "bg-rose-600 text-white hover:bg-rose-700",
                )}
              >
                {savingOutcome ? "Saving..." : `Confirm ${outcomeTarget.outcome === "won" ? "Won" : "Lost"}`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
