"use client";

import { useState, type FormEvent } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import type { SettingsOut } from "@/lib/settings-types";
import {
  AutonomyModeValues,
  FirstTouchModeValues,
  type AutonomyMode,
  type FirstTouchMode,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const WEEKDAYS = [
  { id: 0, label: "Mon" },
  { id: 1, label: "Tue" },
  { id: 2, label: "Wed" },
  { id: 3, label: "Thu" },
  { id: 4, label: "Fri" },
  { id: 5, label: "Sat" },
  { id: 6, label: "Sun" },
];

export function AgentSettingsPanel({
  settings,
  onUpdated,
}: {
  settings: SettingsOut;
  onUpdated: (next: SettingsOut) => void;
}) {
  const [language, setLanguage] = useState<"ar-EG" | "en">(settings.language);
  const [tone, setTone] = useState<"friendly" | "formal">(settings.tone);
  const [autonomyMode, setAutonomyMode] = useState<AutonomyMode>(settings.autonomy_mode);
  const [firstTouchMode, setFirstTouchMode] = useState<FirstTouchMode>(settings.first_touch_mode);
  const [agentEnabled, setAgentEnabled] = useState(settings.agent_enabled);
  const [allowedOffers, setAllowedOffers] = useState(settings.allowed_offers);
  const [maxDiscount, setMaxDiscount] = useState(settings.max_discount_percent);
  const [scoreThreshold, setScoreThreshold] = useState(settings.score_threshold);
  const [dailyNewLeads, setDailyNewLeads] = useState(settings.daily_new_leads_target);
  const [dailySendCap, setDailySendCap] = useState(settings.daily_send_cap);
  const [quietStart, setQuietStart] = useState(settings.quiet_hours_start);
  const [quietEnd, setQuietEnd] = useState(settings.quiet_hours_end);
  const [workingDays, setWorkingDays] = useState<number[]>(settings.working_days);

  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleDay(dayId: number) {
    setWorkingDays((prev) =>
      prev.includes(dayId)
        ? prev.length > 1
          ? prev.filter((d) => d !== dayId)
          : prev
        : [...prev, dayId].sort((a, b) => a - b),
    );
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    setSaving(true);
    try {
      const updated = await api.put<SettingsOut>("/settings", {
        language,
        tone,
        autonomy_mode: autonomyMode,
        first_touch_mode: firstTouchMode,
        agent_enabled: agentEnabled,
        allowed_offers: allowedOffers.trim(),
        max_discount_percent: Number(maxDiscount),
        score_threshold: Number(scoreThreshold),
        daily_new_leads_target: Number(dailyNewLeads),
        daily_send_cap: Number(dailySendCap),
        quiet_hours_start: quietStart,
        quiet_hours_end: quietEnd,
        working_days: workingDays,
      });
      onUpdated(updated);
      setMessage("Agent behavior, autonomy, and schedule saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save agent settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Voice, Tone & Autonomy</CardTitle>
          <CardDescription>
            Control how the AI SDR writes messages and when human approval is required.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-border/80 bg-surface/50 px-4 py-3 dark:border-[#223D27] dark:bg-[#0A140C]/60">
            <div>
              <p className="text-sm font-medium text-foreground">Agent Enabled</p>
              <p className="text-xs text-muted-foreground">
                Pause or resume automated prospecting and scheduled outreach runs.
              </p>
            </div>
            <input
              type="checkbox"
              checked={agentEnabled}
              onChange={(e) => setAgentEnabled(e.target.checked)}
              className="size-4 accent-primary"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="agent-lang">Language</Label>
              <select
                id="agent-lang"
                value={language}
                onChange={(e) => setLanguage(e.target.value as "ar-EG" | "en")}
                className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
              >
                <option value="ar-EG">Egyptian Arabic (ar-EG)</option>
                <option value="en">English (en)</option>
              </select>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="agent-tone">Tone</Label>
              <select
                id="agent-tone"
                value={tone}
                onChange={(e) => setTone(e.target.value as "friendly" | "formal")}
                className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
              >
                <option value="friendly">Friendly</option>
                <option value="formal">Formal</option>
              </select>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="agent-autonomy">Autonomy mode</Label>
              <select
                id="agent-autonomy"
                value={autonomyMode}
                onChange={(e) => setAutonomyMode(e.target.value as AutonomyMode)}
                className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
              >
                {AutonomyModeValues.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="agent-first-touch">First-touch mode</Label>
              <select
                id="agent-first-touch"
                value={firstTouchMode}
                onChange={(e) => setFirstTouchMode(e.target.value as FirstTouchMode)}
                className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
              >
                {FirstTouchModeValues.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="agent-discount">Max discount (%)</Label>
              <Input
                id="agent-discount"
                type="number"
                min={0}
                max={50}
                value={maxDiscount}
                onChange={(e) => setMaxDiscount(Number(e.target.value))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="agent-score">Lead score threshold (1–10)</Label>
              <Input
                id="agent-score"
                type="number"
                min={1}
                max={10}
                value={scoreThreshold}
                onChange={(e) => setScoreThreshold(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="agent-offers">Allowed offers & guardrails</Label>
            <textarea
              id="agent-offers"
              dir="auto"
              rows={2}
              value={allowedOffers}
              onChange={(e) => setAllowedOffers(e.target.value)}
              placeholder="e.g. Free sample pack for orders above 50 pieces..."
              className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
            />
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Daily Quotas & Sending Window (Africa/Cairo)</CardTitle>
          <CardDescription>Keep outbound volume safe and within business hours.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="agent-leads-target">Daily new leads target (1–200)</Label>
              <Input
                id="agent-leads-target"
                type="number"
                min={1}
                max={200}
                value={dailyNewLeads}
                onChange={(e) => setDailyNewLeads(Number(e.target.value))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="agent-send-cap">Daily send cap (1–200)</Label>
              <Input
                id="agent-send-cap"
                type="number"
                min={1}
                max={200}
                value={dailySendCap}
                onChange={(e) => setDailySendCap(Number(e.target.value))}
              />
            </div>
          </div>

          {dailySendCap > 50 && (
            <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
              <AlertTriangle className="size-4 shrink-0" />
              <span>Sending more than 50 WhatsApp messages/day may trigger quality downgrades.</span>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="agent-window-start">Sending window start</Label>
              <Input
                id="agent-window-start"
                type="time"
                value={quietStart}
                onChange={(e) => setQuietStart(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="agent-window-end">Sending window end</Label>
              <Input
                id="agent-window-end"
                type="time"
                value={quietEnd}
                onChange={(e) => setQuietEnd(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Working days</Label>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAYS.map((day) => {
                const active = workingDays.includes(day.id);
                return (
                  <button
                    key={day.id}
                    type="button"
                    onClick={() => toggleDay(day.id)}
                    className={cn(
                      "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                      active
                        ? "border-primary bg-primary/15 text-primary dark:border-lime-400 dark:bg-lime-500/20 dark:text-lime-200"
                        : "border-border bg-card text-muted-foreground hover:text-foreground dark:border-[#223D27]",
                    )}
                  >
                    {day.label}
                  </button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

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

      <Button type="submit" disabled={saving}>
        {saving ? "Saving..." : "Save Agent Settings"}
      </Button>
    </form>
  );
}
