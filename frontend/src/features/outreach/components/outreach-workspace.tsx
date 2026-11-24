"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCheck,
  ExternalLink,
  Loader2,
  MessageSquare,
  RefreshCw,
  Send,
  Sparkles,
  XCircle,
} from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface OutreachLeadInfo {
  id: string;
  name: string;
  category: string | null;
  city: string | null;
  status: string;
}

interface OutreachItem {
  id: string;
  lead: OutreachLeadInfo;
  purpose: string | null;
  template_name: string | null;
  template_body: string | null;
  params: string[];
  body: string;
  status: string;
  rationale: string | null;
  created_at: string;
}

interface AssistedItem extends OutreachItem {
  wa_link: string | null;
  wa_link_error: string | null;
}

interface QueueOut {
  items: OutreachItem[];
  total: number;
}

interface AssistedOut {
  items: AssistedItem[];
  total: number;
  sent_today: number;
  daily_cap: number;
}

interface BulkOut {
  approved: string[];
  failed: { id: string; error: string }[];
}

function notifySidebarBadge() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("nexus:outreach-updated"));
  }
}

export function OutreachWorkspace() {
  const [tab, setTab] = useState<"queue" | "assisted">("queue");
  const [queue, setQueue] = useState<OutreachItem[]>([]);
  const [assisted, setAssisted] = useState<AssistedItem[]>([]);
  const [sentToday, setSentToday] = useState(0);
  const [dailyCap, setDailyCap] = useState(50);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [draftBodies, setDraftBodies] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [qRes, aRes] = await Promise.all([
        api.get<QueueOut>("/outreach/queue"),
        api.get<AssistedOut>("/outreach/assisted"),
      ]);
      setQueue(qRes.items);
      setAssisted(aRes.items);
      setSentToday(aRes.sent_today);
      setDailyCap(aRes.daily_cap);

      const nextDrafts: Record<string, string> = {};
      for (const item of [...qRes.items, ...aRes.items]) {
        nextDrafts[item.id] = item.body;
      }
      setDraftBodies((prev) => ({ ...nextDrafts, ...prev }));
      setSelectedIds((prev) => {
        const valid = new Set(qRes.items.map((i) => i.id));
        return new Set([...prev].filter((id) => valid.has(id)));
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load outreach queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.get<QueueOut>("/outreach/queue"),
      api.get<AssistedOut>("/outreach/assisted"),
    ])
      .then(([qRes, aRes]) => {
        if (!active) return;
        setError(null);
        setQueue(qRes.items);
        setAssisted(aRes.items);
        setSentToday(aRes.sent_today);
        setDailyCap(aRes.daily_cap);

        const nextDrafts: Record<string, string> = {};
        for (const item of [...qRes.items, ...aRes.items]) {
          nextDrafts[item.id] = item.body;
        }
        setDraftBodies((prev) => ({ ...nextDrafts, ...prev }));
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load outreach queue.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectedIds.size === queue.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(queue.map((i) => i.id)));
    }
  }

  async function handleApprove(item: OutreachItem) {
    setBusyId(item.id);
    setError(null);
    setNotice(null);
    try {
      const editedBody = draftBodies[item.id] ?? item.body;
      const payload = editedBody !== item.body ? { body: editedBody } : {};
      await api.post<OutreachItem>(`/outreach/messages/${item.id}/approve`, payload);
      setNotice(`Approved message for ${item.lead.name}.`);
      await loadAll();
      notifySidebarBadge();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not approve message.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(item: OutreachItem) {
    setBusyId(item.id);
    setError(null);
    setNotice(null);
    try {
      await api.post<OutreachItem>(`/outreach/messages/${item.id}/reject`, {});
      setNotice(`Rejected draft for ${item.lead.name} and paused AI outreach for this lead.`);
      await loadAll();
      notifySidebarBadge();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reject message.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleBulkApprove() {
    if (selectedIds.size === 0) return;
    setBulkBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.post<BulkOut>("/outreach/approve-bulk", {
        ids: Array.from(selectedIds),
      });
      setNotice(
        `Bulk approved ${res.approved.length} message(s)` +
          (res.failed.length > 0 ? ` (${res.failed.length} failed).` : "."),
      );
      setSelectedIds(new Set());
      await loadAll();
      notifySidebarBadge();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bulk approve failed.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function handleMarkSent(item: AssistedItem) {
    setBusyId(item.id);
    setError(null);
    setNotice(null);
    try {
      const editedBody = draftBodies[item.id] ?? item.body;
      const payload = editedBody !== item.body ? { body: editedBody } : {};
      await api.post<OutreachItem>(`/outreach/messages/${item.id}/mark-sent`, payload);
      setNotice(`Marked message to ${item.lead.name} as sent.`);
      await loadAll();
      notifySidebarBadge();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not mark message as sent.");
    } finally {
      setBusyId(null);
    }
  }

  const capPct = dailyCap > 0 ? Math.min(100, Math.round((sentToday / dailyCap) * 100)) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Outreach &amp; Approvals</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Review AI-drafted outreach before sending, or send manually in Assisted WhatsApp Mode.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            setLoading(true);
            void loadAll();
          }}
        >
          <RefreshCw className={cn("mr-1.5 size-3.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Daily Cap Banner */}
      <Card className="border-border/80 bg-card">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Daily Outreach Quota
            </p>
            <p className="text-sm font-medium text-foreground">
              <span className="text-lg font-bold text-primary dark:text-lime-400">{sentToday}</span> / {dailyCap} messages sent today
            </p>
          </div>
          <div className="w-full max-w-xs space-y-1">
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-secondary">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[#10B981] to-[#84CC16] transition-all"
                style={{ width: `${capPct}%` }}
              />
            </div>
            <p className="text-right text-[11px] text-muted-foreground">{capPct}% used</p>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-200">
          <AlertCircle className="size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {notice && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
          <Check className="size-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTab("queue")}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors",
              tab === "queue"
                ? "bg-primary/15 text-primary dark:bg-lime-500/15 dark:text-lime-300"
                : "text-muted-foreground hover:bg-surface-secondary hover:text-foreground",
            )}
          >
            <Sparkles className="size-3.5" />
            Pending Approvals
            <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
              {queue.length}
            </Badge>
          </button>

          <button
            type="button"
            onClick={() => setTab("assisted")}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors",
              tab === "assisted"
                ? "bg-primary/15 text-primary dark:bg-lime-500/15 dark:text-lime-300"
                : "text-muted-foreground hover:bg-surface-secondary hover:text-foreground",
            )}
          >
            <MessageSquare className="size-3.5" />
            Assisted WhatsApp Mode
            <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
              {assisted.length}
            </Badge>
          </button>
        </div>

        {tab === "queue" && queue.length > 0 && (
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={toggleSelectAll}>
              {selectedIds.size === queue.length ? "Clear Selection" : `Select All (${queue.length})`}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={selectedIds.size === 0 || bulkBusy}
              onClick={() => void handleBulkApprove()}
              className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
            >
              {bulkBusy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <CheckCheck className="mr-1.5 size-3.5" />}
              Bulk Approve ({selectedIds.size})
            </Button>
          </div>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex min-h-[240px] items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin text-primary" />
          Loading outreach queue...
        </div>
      ) : tab === "queue" ? (
        queue.length === 0 ? (
          <Card className="border-border/80 bg-card">
            <CardContent className="py-12 text-center">
              <Send className="mx-auto size-8 text-muted-foreground/60" />
              <p className="mt-3 text-sm font-semibold text-foreground">No pending approvals</p>
              <p className="mt-1 text-xs text-muted-foreground">
                AI-drafted first-touch messages and replies awaiting review will appear here.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {queue.map((item) => {
              const isBusy = busyId === item.id;
              const isSelected = selectedIds.has(item.id);
              return (
                <Card
                  key={item.id}
                  className={cn(
                    "border-border/80 bg-card transition-colors",
                    isSelected && "border-primary/50 dark:border-lime-400/50",
                  )}
                >
                  <CardHeader className="pb-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(item.id)}
                          aria-label={`Select message for ${item.lead.name}`}
                          className="mt-1 size-4 accent-emerald-600"
                        />
                        <div>
                          <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                            <Link href={`/leads/${item.lead.id}`} className="hover:text-primary hover:underline">
                              <AutoDirText as="span">{item.lead.name}</AutoDirText>
                            </Link>
                            {item.purpose && (
                              <Badge variant="outline" className="text-[10px] capitalize">
                                {item.purpose.replace(/_/g, " ")}
                              </Badge>
                            )}
                            {item.template_name && (
                              <Badge variant="secondary" className="text-[10px]">
                                Template: {item.template_name}
                              </Badge>
                            )}
                          </CardTitle>
                          <CardDescription className="mt-0.5 text-xs">
                            {[item.lead.category, item.lead.city].filter(Boolean).join(" · ") || "Lead"} · Status:{" "}
                            <span className="capitalize">{item.lead.status}</span>
                          </CardDescription>
                        </div>
                      </div>

                      <span className="text-[11px] text-muted-foreground">
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {item.rationale && (
                      <div className="rounded-lg border border-border/60 bg-surface/50 px-3 py-2 text-xs text-muted-foreground dark:border-[#223D27] dark:bg-[#0A140C]/60">
                        <span className="font-semibold text-foreground">AI Rationale: </span>
                        <AutoDirText as="span">{item.rationale}</AutoDirText>
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-muted-foreground uppercase">
                        Message Draft (Editable)
                      </label>
                      <textarea
                        rows={3}
                        dir="auto"
                        value={draftBodies[item.id] ?? item.body}
                        onChange={(e) =>
                          setDraftBodies((prev) => ({
                            ...prev,
                            [item.id]: e.target.value,
                          }))
                        }
                        className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-xs leading-relaxed dark:border-[#223D27] dark:bg-[#0A140C]"
                      />
                    </div>

                    <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isBusy}
                        onClick={() => void handleReject(item)}
                        className="text-rose-600 hover:text-rose-700 dark:text-rose-400"
                      >
                        <XCircle className="mr-1.5 size-3.5" />
                        Reject &amp; Pause
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        disabled={isBusy || !(draftBodies[item.id] ?? item.body).trim()}
                        onClick={() => void handleApprove(item)}
                        className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                      >
                        {isBusy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Check className="mr-1.5 size-3.5" />}
                        Approve &amp; Send
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )
      ) : assisted.length === 0 ? (
        <Card className="border-border/80 bg-card">
          <CardContent className="py-12 text-center">
            <MessageSquare className="mx-auto size-8 text-muted-foreground/60" />
            <p className="mt-3 text-sm font-semibold text-foreground">No assisted messages waiting</p>
            <p className="mt-1 text-xs text-muted-foreground">
              When Assisted Mode is active, approved drafts appear here with a one-click WhatsApp link.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {assisted.map((item) => {
            const isBusy = busyId === item.id;
            return (
              <Card key={item.id} className="border-border/80 bg-card">
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Link href={`/leads/${item.lead.id}`} className="hover:text-primary hover:underline">
                          <AutoDirText as="span">{item.lead.name}</AutoDirText>
                        </Link>
                        <Badge variant="secondary" className="text-[10px]">
                          Awaiting Manual Send
                        </Badge>
                      </CardTitle>
                      <CardDescription className="mt-0.5 text-xs">
                        {[item.lead.category, item.lead.city].filter(Boolean).join(" · ") || "Lead"}
                      </CardDescription>
                    </div>
                    <span className="text-[11px] text-muted-foreground">
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <textarea
                    rows={3}
                    dir="auto"
                    value={draftBodies[item.id] ?? item.body}
                    onChange={(e) =>
                      setDraftBodies((prev) => ({
                        ...prev,
                        [item.id]: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-xs leading-relaxed dark:border-[#223D27] dark:bg-[#0A140C]"
                  />

                  {item.wa_link_error && (
                    <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                      {item.wa_link_error}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {item.wa_link && (
                      <a
                        href={item.wa_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 text-xs font-semibold text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-300"
                      >
                        <ExternalLink className="size-3.5" />
                        Open in WhatsApp
                      </a>
                    )}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isBusy}
                      onClick={() => void handleReject(item)}
                    >
                      Skip
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={isBusy || !(draftBodies[item.id] ?? item.body).trim()}
                      onClick={() => void handleMarkSent(item)}
                      className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                    >
                      {isBusy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Check className="mr-1.5 size-3.5" />}
                      I sent it
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
