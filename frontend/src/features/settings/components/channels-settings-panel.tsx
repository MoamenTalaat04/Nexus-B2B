"use client";

import { useState, type FormEvent } from "react";
import { AlertTriangle, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import type { SequenceStepIn, SettingsOut } from "@/lib/settings-types";

export function ChannelsSettingsPanel({
  settings,
  onUpdated,
}: {
  settings: SettingsOut;
  onUpdated: (next: SettingsOut) => void;
}) {
  const [demoMode, setDemoMode] = useState(settings.demo_mode);
  const [whitelist, setWhitelist] = useState<string[]>(settings.demo_whitelist);
  const [phoneInput, setPhoneInput] = useState("");
  const [steps, setSteps] = useState<SequenceStepIn[]>(
    settings.sequence_steps.length > 0
      ? settings.sequence_steps
      : [{ day_offset: 0, purpose: "first_touch", template: "intro" }],
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function addPhone() {
    const trimmed = phoneInput.trim();
    if (!trimmed) return;
    if (whitelist.length >= 5) {
      setError("WhatsApp test whitelist accepts at most 5 phone numbers.");
      return;
    }
    if (!whitelist.includes(trimmed)) {
      setWhitelist([...whitelist, trimmed]);
    }
    setPhoneInput("");
    setError(null);
  }

  function addFollowupStep() {
    if (steps.length >= 4) return;
    const lastOffset = steps[steps.length - 1]?.day_offset ?? 0;
    setSteps([
      ...steps,
      { day_offset: lastOffset + 3, purpose: "followup", template: "followup" },
    ]);
  }

  function updateStep(index: number, patch: Partial<SequenceStepIn>) {
    setSteps(steps.map((s, idx) => (idx === index ? { ...s, ...patch } : s)));
  }

  function removeStep(index: number) {
    if (index === 0 || steps.length <= 1) return;
    setSteps(steps.filter((_, idx) => idx !== index));
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    setSaving(true);
    try {
      const updated = await api.put<SettingsOut>("/settings", {
        demo_mode: demoMode,
        demo_whitelist: whitelist,
        sequence_steps: steps,
      });
      onUpdated(updated);
      setWhitelist(updated.demo_whitelist);
      setMessage("WhatsApp safety, whitelist, and outreach sequence saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save channel settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card className="border-border/80 bg-card">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">WhatsApp Channel & Demo Sandbox</CardTitle>
              <CardDescription>
                Control whether outbound messages go to real leads or only your test whitelist.
              </CardDescription>
            </div>
            <Badge variant={settings.telegram_connected ? "default" : "secondary"}>
              Telegram {settings.telegram_connected ? "Connected" : "Not linked"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-border/80 bg-surface/50 px-4 py-3 dark:border-[#223D27] dark:bg-[#0A140C]/60">
            <div>
              <p className="text-sm font-medium text-foreground">Demo Mode (Sandbox Whitelist)</p>
              <p className="text-xs text-muted-foreground">
                When enabled, WhatsApp messages are delivered only to whitelisted Egyptian numbers.
              </p>
            </div>
            <input
              type="checkbox"
              checked={demoMode}
              onChange={(e) => setDemoMode(e.target.checked)}
              className="size-4 accent-primary"
            />
          </div>

          {!demoMode && (
            <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
              <AlertTriangle className="size-4 shrink-0" />
              <span>Demo mode is OFF — outreach messages will be sent to real lead phone numbers.</span>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="demo-phone-input">Demo Whitelist (Egyptian numbers, max 5)</Label>
            <div className="flex gap-2">
              <Input
                id="demo-phone-input"
                placeholder="01012345678 or +201012345678"
                value={phoneInput}
                onChange={(e) => setPhoneInput(e.target.value)}
              />
              <Button type="button" variant="outline" onClick={addPhone} disabled={whitelist.length >= 5}>
                <Plus className="mr-1 size-4" />
                Add
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              {whitelist.map((phone) => (
                <Badge key={phone} variant="secondary" className="flex items-center gap-1.5 px-3 py-1">
                  <span>{phone}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${phone}`}
                    onClick={() => setWhitelist(whitelist.filter((p) => p !== phone))}
                    className="hover:text-red-600"
                  >
                    <X className="size-3.5" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">WhatsApp Outreach Sequence & Templates</CardTitle>
          <CardDescription>
            Define 1 to 4 steps with increasing day offsets (Day 0 = First Touch).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {steps.map((step, index) => (
            <div
              key={index}
              className="grid gap-3 rounded-xl border border-border/80 bg-surface/50 p-3 sm:grid-cols-[120px_1fr_1fr_auto] sm:items-end dark:border-[#223D27] dark:bg-[#0A140C]/60"
            >
              <div className="grid gap-1">
                <Label>Day offset</Label>
                <Input
                  type="number"
                  min={0}
                  max={60}
                  value={step.day_offset}
                  disabled={index === 0}
                  onChange={(e) => updateStep(index, { day_offset: Number(e.target.value) })}
                />
              </div>
              <div className="grid gap-1">
                <Label>Purpose</Label>
                <Input value={step.purpose} disabled />
              </div>
              <div className="grid gap-1">
                <Label>Template tag</Label>
                <Input
                  value={step.template}
                  onChange={(e) => updateStep(index, { template: e.target.value })}
                />
              </div>
              {index > 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeStep(index)}
                  className="text-muted-foreground hover:text-red-600"
                >
                  <Trash2 className="size-4" />
                </Button>
              )}
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={addFollowupStep} disabled={steps.length >= 4}>
            <Plus className="mr-1.5 size-4" />
            Add Follow-up Step
          </Button>
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
        {saving ? "Saving..." : "Save Channel Settings"}
      </Button>
    </form>
  );
}
