"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ExternalLink,
  Globe,
  History,
  Loader2,
  MapPin,
  MessageSquare,
  PauseCircle,
  Phone,
  PlayCircle,
  Plus,
  Send,
  Star,
  StickyNote,
  Trophy,
  X,
  XCircle,
} from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import type {
  LeadContactOut,
  LeadDetailOut,
  LeadMessageOut,
  LeadNoteOut,
  LeadOutcomeOut,
} from "@/lib/leads-types";
import { ContactTypeValues, LeadStatusValues, type ContactType, type LeadStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export function LeadDetailWorkspace({ leadId }: { leadId: string }) {
  const [lead, setLead] = useState<LeadDetailOut | null>(null);
  const [windowOpen, setWindowOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [togglingPause, setTogglingPause] = useState(false);

  // Add contact
  const [contactType, setContactType] = useState<ContactType>("mobile");
  const [contactValue, setContactValue] = useState("");
  const [addingContact, setAddingContact] = useState(false);

  // Add note
  const [noteBody, setNoteBody] = useState("");
  const [addingNote, setAddingNote] = useState(false);

  // Manual message
  const [msgBody, setMsgBody] = useState("");
  const [sendingMsg, setSendingMsg] = useState(false);

  const [simText, setSimText] = useState("");
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<string | null>(null);

  // Outcome modal
  const [outcomeModal, setOutcomeModal] = useState<"won" | "lost" | null>(null);
  const [dealValue, setDealValue] = useState("");
  const [dealReason, setDealReason] = useState("");
  const [savingOutcome, setSavingOutcome] = useState(false);

  const loadLead = useCallback(async () => {
    try {
      const res = await api.get<LeadDetailOut>(`/leads/${leadId}`, {
        suppressUnauthorizedRedirect: true,
      });
      setLead(res);
      setWindowOpen(
        Boolean(res.window_expires_at && new Date(res.window_expires_at).getTime() > Date.now()),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load lead details.");
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => {
    void Promise.resolve().then(() => loadLead());
  }, [loadLead]);

  async function handleStatusChange(nextStatus: LeadStatus) {
    if (!lead || nextStatus === lead.status) return;
    setError(null);
    setMessage(null);
    setUpdatingStatus(true);
    try {
      const updated = await api.patch<LeadDetailOut>(
        `/leads/${lead.id}`,
        { status: nextStatus },
        { suppressUnauthorizedRedirect: true },
      );
      setLead(updated);
      setMessage(`Status updated to "${nextStatus.replace(/_/g, " ")}".`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update status.");
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleTogglePause() {
    if (!lead) return;
    setError(null);
    setMessage(null);
    setTogglingPause(true);
    try {
      const updated = await api.patch<LeadDetailOut>(
        `/leads/${lead.id}`,
        { agent_paused: !lead.agent_paused },
        { suppressUnauthorizedRedirect: true },
      );
      setLead(updated);
      setMessage(updated.agent_paused ? "AI agent paused for this lead." : "AI agent resumed for this lead.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not toggle AI agent.");
    } finally {
      setTogglingPause(false);
    }
  }

  async function handleAddContact(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!lead || !contactValue.trim()) return;
    setError(null);
    setAddingContact(true);
    try {
      const created = await api.post<LeadContactOut>(
        `/leads/${lead.id}/contacts`,
        { type: contactType, value: contactValue.trim() },
        { suppressUnauthorizedRedirect: true },
      );
      setLead((prev) => (prev ? { ...prev, contacts: [...prev.contacts, created] } : prev));
      setContactValue("");
      setMessage("Contact added.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add contact.");
    } finally {
      setAddingContact(false);
    }
  }

  async function handleAddNote(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!lead || !noteBody.trim()) return;
    setError(null);
    setAddingNote(true);
    try {
      const created = await api.post<LeadNoteOut>(
        `/leads/${lead.id}/notes`,
        { body: noteBody.trim() },
        { suppressUnauthorizedRedirect: true },
      );
      setLead((prev) => (prev ? { ...prev, notes: [created, ...prev.notes] } : prev));
      setNoteBody("");
      setMessage("Note saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add note.");
    } finally {
      setAddingNote(false);
    }
  }

  async function handleSendMessage(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!lead || !msgBody.trim()) return;
    setError(null);
    setSendingMsg(true);
    try {
      const created = await api.post<LeadMessageOut>(
        `/leads/${lead.id}/messages`,
        { body: msgBody.trim() },
        { suppressUnauthorizedRedirect: true },
      );
      setLead((prev) =>
        prev ? { ...prev, messages: [...(prev.messages ?? []), created] } : prev,
      );
      setMsgBody("");
      setMessage("Message queued.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send message.");
    } finally {
      setSendingMsg(false);
    }
  }

  async function handleSaveOutcome() {
    if (!lead || !outcomeModal) return;
    setError(null);
    setSavingOutcome(true);
    try {
      const saved = await api.post<LeadOutcomeOut>(
        `/leads/${lead.id}/outcome`,
        {
          outcome: outcomeModal,
          value_egp: outcomeModal === "won" && dealValue.trim() ? Number(dealValue) : null,
          reason: dealReason.trim() || null,
        },
        { suppressUnauthorizedRedirect: true },
      );
      setLead((prev) =>
        prev
          ? {
              ...prev,
              status: outcomeModal,
              agent_paused: true,
              outcome: saved,
            }
          : prev,
      );
      setOutcomeModal(null);
      setDealValue("");
      setDealReason("");
      setMessage(`Deal marked as ${saved.outcome.toUpperCase()}.`);
      await loadLead();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record deal outcome.");
    } finally {
      setSavingOutcome(false);
    }
  }

  async function handleSimulateInbound(e: FormEvent) {
    e.preventDefault();
    if (!lead || !simText.trim()) return;
    setSimulating(true);
    setError(null);
    setSimResult(null);
    try {
      const res = await api.post<{
        inbound_message_id: string;
        pipeline: {
          status?: string;
          intent?: string;
          reply_status?: string;
          reason?: string;
        };
      }>("/outreach/simulate-inbound", {
        lead_id: lead.id,
        text: simText.trim(),
      });
      setSimText("");
      const p = res.pipeline;
      setSimResult(
        `Reply Agent ran (${p.intent ?? "classified"} → ${p.reply_status ?? p.status ?? "done"}` +
          (p.reason ? `: ${p.reason}` : "") +
          `).`,
      );
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("nexus:outreach-updated"));
      }
      await loadLead();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to simulate inbound reply.");
    } finally {
      setSimulating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[320px] items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin text-primary" />
        Loading lead details...
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="space-y-3">
        <Link href="/pipeline" className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline">
          <ArrowLeft className="size-3.5" />
          Back to Pipeline
        </Link>
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error ?? "Lead not found."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Top Navigation & Lead Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/pipeline"
            className="inline-flex items-center gap-1 rounded-lg border border-border/80 bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground dark:border-[#223D27]"
          >
            <ArrowLeft className="size-3.5" />
            Pipeline
          </Link>
          <Link
            href="/leads"
            className="inline-flex items-center gap-1 rounded-lg border border-border/80 bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground dark:border-[#223D27]"
          >
            All Leads
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Lead status"
            disabled={updatingStatus}
            value={lead.status}
            onChange={(e) => void handleStatusChange(e.target.value as LeadStatus)}
            className="h-8 rounded-lg border border-input bg-card px-2.5 text-xs capitalize dark:border-[#223D27] dark:bg-[#112014]"
          >
            {LeadStatusValues.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>

          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={togglingPause}
            onClick={() => void handleTogglePause()}
          >
            {lead.agent_paused ? (
              <>
                <PlayCircle className="mr-1.5 size-3.5 text-emerald-500" />
                Resume Agent
              </>
            ) : (
              <>
                <PauseCircle className="mr-1.5 size-3.5 text-amber-500" />
                Pause Agent
              </>
            )}
          </Button>

          <Button
            type="button"
            size="sm"
            onClick={() => {
              setOutcomeModal("won");
              setDealValue(lead.outcome?.value_egp ? String(lead.outcome.value_egp) : "");
              setDealReason(lead.outcome?.reason ?? "");
            }}
            className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
          >
            <Trophy className="mr-1.5 size-3.5" />
            Mark Won
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              setOutcomeModal("lost");
              setDealValue("");
              setDealReason(lead.outcome?.reason ?? "");
            }}
            className="border-rose-500/40 text-rose-600 hover:bg-rose-500/10 dark:text-rose-300"
          >
            <XCircle className="mr-1.5 size-3.5" />
            Mark Lost
          </Button>
        </div>
      </div>

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

      {/* Summary Banner */}
      <Card className="border-border/80 bg-card">
        <CardContent className="flex flex-wrap items-start justify-between gap-4 p-5">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <AutoDirText as="h1" className="text-xl font-bold text-foreground">
                {lead.name}
              </AutoDirText>
              <Badge variant="secondary" className="capitalize">
                {lead.status.replace(/_/g, " ")}
              </Badge>
              {lead.score !== null && (
                <Badge variant="outline" className="gap-1">
                  <Star className="size-3 fill-amber-400 text-amber-400" />
                  Score {lead.score}/10
                </Badge>
              )}
              {lead.agent_paused && (
                <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-300">
                  Agent Paused
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              {lead.category && <span>{lead.category}</span>}
              {(lead.city || lead.governorate) && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="size-3.5" />
                  {[lead.address, lead.city, lead.governorate].filter(Boolean).join(", ")}
                </span>
              )}
              {lead.website && (
                <a
                  href={lead.website}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline dark:text-lime-300"
                >
                  <Globe className="size-3.5" />
                  Website
                  <ExternalLink className="size-3" />
                </a>
              )}
              {lead.google_maps_url && (
                <a
                  href={lead.google_maps_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline dark:text-lime-300"
                >
                  Google Maps
                  <ExternalLink className="size-3" />
                </a>
              )}
            </div>
          </div>

          {lead.outcome && (
            <div
              className={cn(
                "rounded-xl border px-3.5 py-2 text-xs",
                lead.outcome.outcome === "won"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-lime-200"
                  : "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-200",
              )}
            >
              <p className="font-semibold uppercase">Deal {lead.outcome.outcome}</p>
              {lead.outcome.value_egp !== null && (
                <p>Value: {lead.outcome.value_egp.toLocaleString()} EGP</p>
              )}
              {lead.outcome.reason && <p className="text-[11px] opacity-85">{lead.outcome.reason}</p>}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Main 2-Column Workspace */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Left Column: Contacts, Score Reasons, Notes */}
        <div className="space-y-5">
          {/* Contacts */}
          <Card className="border-border/80 bg-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Phone className="size-4 text-primary dark:text-lime-400" />
                Contacts
              </CardTitle>
              <CardDescription>Discovered and manually added phone numbers, emails, or social links.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {lead.contacts.length === 0 ? (
                <p className="text-xs text-muted-foreground">No contacts yet.</p>
              ) : (
                <div className="space-y-2">
                  {lead.contacts.map((c) => (
                    <div
                      key={c.id}
                      className="flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-surface/40 px-3 py-2 text-xs dark:border-[#223D27] dark:bg-[#0A140C]/55"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {c.type.replace(/_/g, " ")}
                        </Badge>
                        <span className="truncate font-mono text-foreground">{c.value}</span>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        {c.is_primary && <Badge className="text-[10px]">Primary</Badge>}
                        <span className="text-[10px] text-muted-foreground">{c.source}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <form onSubmit={handleAddContact} className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3 dark:border-[#223D27]">
                <select
                  aria-label="Contact type"
                  value={contactType}
                  onChange={(e) => setContactType(e.target.value as ContactType)}
                  className="h-9 rounded-lg border border-input bg-surface/70 px-2.5 text-xs capitalize dark:border-[#223D27] dark:bg-[#0A140C]"
                >
                  {ContactTypeValues.map((ct) => (
                    <option key={ct} value={ct}>
                      {ct.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
                <Input
                  placeholder="Phone, email, or link..."
                  value={contactValue}
                  onChange={(e) => setContactValue(e.target.value)}
                  className="h-9 min-w-[160px] flex-1 text-xs"
                />
                <Button type="submit" size="sm" disabled={addingContact || !contactValue.trim()}>
                  <Plus className="mr-1 size-3.5" />
                  {addingContact ? "Adding..." : "Add"}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* AI Qualification & Score Reasons */}
          {(lead.score_reasons.length > 0 || lead.disqualify_reason) && (
            <Card className="border-border/80 bg-card">
              <CardHeader>
                <CardTitle className="text-base">AI Qualification Insights</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-xs text-muted-foreground">
                {lead.disqualify_reason && (
                  <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-rose-700 dark:text-rose-200">
                    Disqualified: {lead.disqualify_reason}
                  </p>
                )}
                <ul className="list-disc space-y-1 pl-4">
                  {lead.score_reasons.map((r, idx) => (
                    <li key={idx}>
                      <AutoDirText as="span">{r}</AutoDirText>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Notes */}
          <Card className="border-border/80 bg-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <StickyNote className="size-4 text-primary dark:text-lime-400" />
                Notes
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handleAddNote} className="space-y-2">
                <textarea
                  rows={2}
                  dir="auto"
                  placeholder="Add an internal CRM note..."
                  value={noteBody}
                  onChange={(e) => setNoteBody(e.target.value)}
                  className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-xs dark:border-[#223D27] dark:bg-[#0A140C]"
                />
                <div className="flex justify-end">
                  <Button type="submit" size="sm" disabled={addingNote || !noteBody.trim()}>
                    <Plus className="mr-1 size-3.5" />
                    {addingNote ? "Saving..." : "Add Note"}
                  </Button>
                </div>
              </form>

              {lead.notes.length === 0 ? (
                <p className="text-xs text-muted-foreground">No notes yet.</p>
              ) : (
                <div className="space-y-2">
                  {lead.notes.map((n) => (
                    <div
                      key={n.id}
                      className="rounded-lg border border-border/70 bg-surface/40 p-3 text-xs dark:border-[#223D27] dark:bg-[#0A140C]/55"
                    >
                      <AutoDirText as="p" className="whitespace-pre-wrap text-foreground">
                        {n.body}
                      </AutoDirText>
                      <p className="mt-1 text-[10px] text-muted-foreground">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Conversation & Status History */}
        <div className="space-y-5">
          {/* Messages */}
          <Card className="border-border/80 bg-card">
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <MessageSquare className="size-4 text-primary dark:text-lime-400" />
                  Conversation
                </CardTitle>
                <Badge variant={windowOpen ? "default" : "secondary"} className="text-[10px]">
                  {windowOpen ? "24h Window Open" : "24h Window Closed"}
                </Badge>
              </div>
              <CardDescription>WhatsApp &amp; outreach thread with this lead.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!lead.messages || lead.messages.length === 0 ? (
                <p className="text-xs text-muted-foreground">No messages sent or received yet.</p>
              ) : (
                <div className="max-h-80 space-y-2.5 overflow-y-auto pr-1">
                  {lead.messages.map((m) => {
                    const isOutbound = m.direction === "outbound";
                    return (
                      <div
                        key={m.id}
                        className={cn(
                          "max-w-[85%] rounded-xl border px-3.5 py-2.5 text-xs",
                          isOutbound
                            ? "ml-auto border-emerald-500/30 bg-emerald-500/10 text-foreground dark:border-lime-400/30 dark:bg-lime-500/15"
                            : "mr-auto border-border/80 bg-surface/60 text-foreground dark:border-[#223D27] dark:bg-[#0A140C]/70",
                        )}
                      >
                        <div className="mb-1 flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                          <span className="font-semibold capitalize">
                            {m.author} · {m.direction}
                          </span>
                          <span className="capitalize">{m.status}</span>
                        </div>
                        <AutoDirText as="p" className="whitespace-pre-wrap leading-relaxed">
                          {m.body}
                        </AutoDirText>
                        <p className="mt-1 text-[10px] text-muted-foreground">
                          {new Date(m.sent_at ?? m.created_at).toLocaleString()}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}

              <form onSubmit={handleSendMessage} className="space-y-2 border-t border-border/60 pt-3 dark:border-[#223D27]">
                <textarea
                  rows={2}
                  dir="auto"
                  disabled={!windowOpen || sendingMsg}
                  placeholder={
                    windowOpen
                      ? "Write a manual WhatsApp reply..."
                      : "Manual free-text replies are available only within 24h after an inbound reply."
                  }
                  value={msgBody}
                  onChange={(e) => setMsgBody(e.target.value)}
                  className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-xs disabled:opacity-60 dark:border-[#223D27] dark:bg-[#0A140C]"
                />
                <div className="flex justify-end">
                  <Button type="submit" size="sm" disabled={!windowOpen || sendingMsg || !msgBody.trim()}>
                    <Send className="mr-1.5 size-3.5" />
                    {sendingMsg ? "Sending..." : "Send Reply"}
                  </Button>
                </div>
              </form>

              <form
                onSubmit={handleSimulateInbound}
                className="space-y-2 rounded-lg border border-dashed border-border/80 bg-surface/40 p-3 dark:border-[#223D27] dark:bg-[#0A140C]/40"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-muted-foreground uppercase">
                    Simulate Inbound Reply (Test Reply Agent)
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Input
                    dir="auto"
                    placeholder="e.g. بكام الباقة الشهرية؟ / Interested, send details"
                    value={simText}
                    onChange={(e) => setSimText(e.target.value)}
                    className="h-8 min-w-[180px] flex-1 text-xs"
                  />
                  <Button type="submit" size="sm" variant="outline" disabled={simulating || !simText.trim()}>
                    {simulating ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : null}
                    {simulating ? "Running Agent..." : "Simulate Reply"}
                  </Button>
                </div>
                {simResult && (
                  <p className="text-[11px] font-medium text-emerald-700 dark:text-emerald-300">{simResult}</p>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Status History */}
          <Card className="border-border/80 bg-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="size-4 text-primary dark:text-lime-400" />
                Status History
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!lead.history || lead.history.length === 0 ? (
                <p className="text-xs text-muted-foreground">No status transitions recorded yet.</p>
              ) : (
                <div className="space-y-2">
                  {lead.history.map((h, idx) => (
                    <div
                      key={idx}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 bg-surface/40 px-3 py-2 text-xs dark:border-[#223D27] dark:bg-[#0A140C]/55"
                    >
                      <div>
                        <span className="font-medium text-foreground capitalize">
                          {h.from_status ? `${h.from_status.replace(/_/g, " ")} → ` : ""}
                          {h.to_status.replace(/_/g, " ")}
                        </span>
                        <p className="text-[11px] text-muted-foreground">
                          {h.reason} · by {h.actor}
                        </p>
                      </div>
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(h.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Won / Lost Outcome Modal */}
      {outcomeModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setOutcomeModal(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-border bg-card p-5 shadow-2xl dark:border-[#223D27] dark:bg-[#112014]"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {outcomeModal === "won" ? (
                  <Trophy className="size-5 text-emerald-500" />
                ) : (
                  <XCircle className="size-5 text-rose-500" />
                )}
                <h3 className="text-sm font-semibold text-foreground">
                  Record Deal Outcome ({outcomeModal === "won" ? "Won" : "Lost"})
                </h3>
              </div>
              <Button type="button" size="icon-sm" variant="ghost" onClick={() => setOutcomeModal(null)}>
                <X className="size-4" />
              </Button>
            </div>

            <div className="space-y-3">
              {outcomeModal === "won" && (
                <div className="grid gap-1.5">
                  <Label htmlFor="detail-deal-value" className="text-xs">
                    Deal Value (EGP, optional)
                  </Label>
                  <Input
                    id="detail-deal-value"
                    type="number"
                    min={0}
                    placeholder="e.g. 25000"
                    value={dealValue}
                    onChange={(e) => setDealValue(e.target.value)}
                  />
                </div>
              )}
              <div className="grid gap-1.5">
                <Label htmlFor="detail-deal-reason" className="text-xs">
                  Reason / Notes (optional)
                </Label>
                <textarea
                  id="detail-deal-reason"
                  rows={3}
                  dir="auto"
                  value={dealReason}
                  onChange={(e) => setDealReason(e.target.value)}
                  className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                />
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setOutcomeModal(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={savingOutcome}
                onClick={() => void handleSaveOutcome()}
                className={cn(
                  outcomeModal === "won"
                    ? "bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                    : "bg-rose-600 text-white hover:bg-rose-700",
                )}
              >
                {savingOutcome ? "Saving..." : `Confirm ${outcomeModal === "won" ? "Won" : "Lost"}`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
