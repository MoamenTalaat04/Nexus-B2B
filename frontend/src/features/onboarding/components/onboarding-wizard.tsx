"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, CheckCircle2, Loader2, Sparkles, Upload, Wand2 } from "lucide-react";
import { Logo } from "@/components/shared/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CUSTOMER_ROUTES } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import { KnowledgeUploader } from "@/features/knowledge/components/knowledge-uploader";
import {
  AutonomyModeCardsSelector,
  FirstTouchModeCardsSelector,
  LanguageDialectSelector,
  ToneCardsSelector,
} from "@/features/settings/components/agent-behavior-controls";
import { GeoRegionSelector } from "@/features/settings/components/geo-region-selector";
import { ProductsEditor } from "@/features/settings/components/products-editor";
import { ApiError, api, apiFetch } from "@/lib/api";
import type { ProductIn, RegionIn, SettingsOut } from "@/lib/settings-types";
import type { AutonomyMode, FirstTouchMode } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: 1, title: "Company", subtitle: "Tell NEXUS about your business" },
  { id: 2, title: "Products & Services", subtitle: "Add what you sell, rent, or offer" },
  { id: 3, title: "Knowledge", subtitle: "Upload catalogs, FAQs, or price lists" },
  { id: 4, title: "Regions", subtitle: "Pick target countries, states, cities, or map radius" },
  { id: 5, title: "Agent Behavior", subtitle: "Set tone, autonomy, and daily cap" },
] as const;

type AiField = "description" | "ideal_customer_text";
type AiMode = "generate" | "enhance";

interface AiFieldActionsProps {
  field: AiField;
  hasText: boolean;
  busyKey: string | null;
  remaining: number;
  generateTooltip: string;
  onRun: (field: AiField, mode: AiMode) => void;
}

function AiFieldActions({ field, hasText, busyKey, remaining, generateTooltip, onRun }: AiFieldActionsProps) {
  const isGenerating = busyKey === `${field}:generate`;
  const isEnhancing = busyKey === `${field}:enhance`;
  const isFieldBusy = isGenerating || isEnhancing;
  const exhausted = remaining <= 0;

  return (
    <TooltipProvider delay={150}>
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            "text-[10px] font-semibold tabular-nums",
            exhausted ? "text-red-500 dark:text-red-400" : "text-muted-foreground",
          )}
        >
          {remaining}/3
        </span>
        <Tooltip>
          <TooltipTrigger
            render={
              <button
                type="button"
                disabled={isFieldBusy || exhausted}
                onClick={() => onRun(field, "generate")}
                aria-label={generateTooltip}
                className="inline-flex size-8 items-center justify-center rounded-full border border-border/80 bg-surface/85 text-muted-foreground shadow-xs transition-colors hover:border-primary/50 hover:bg-primary/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-45 dark:border-[#223D27] dark:bg-[#0A140C]/85 dark:hover:border-lime-400/50 dark:hover:text-lime-300"
              />
            }
          >
            {isGenerating ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
          </TooltipTrigger>
          <TooltipContent side="top">
            {exhausted ? "All 3 AI attempts used for this field" : generateTooltip}
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <button
                type="button"
                disabled={isFieldBusy || exhausted}
                onClick={() => onRun(field, "enhance")}
                aria-label="Enhance & structure your draft with AI"
                className={cn(
                  "inline-flex size-8 items-center justify-center rounded-full border border-border/80 bg-surface/85 shadow-xs transition-colors disabled:cursor-not-allowed disabled:opacity-45 dark:border-[#223D27] dark:bg-[#0A140C]/85",
                  hasText
                    ? "text-muted-foreground hover:border-primary/50 hover:bg-primary/10 hover:text-primary dark:hover:border-lime-400/50 dark:hover:text-lime-300"
                    : "text-muted-foreground/45 hover:text-muted-foreground/70",
                )}
              />
            }
          >
            {isEnhancing ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
          </TooltipTrigger>
          <TooltipContent side="top">
            {exhausted
              ? "All 3 AI attempts used for this field"
              : hasText
                ? "Enhance & structure your draft with AI"
                : "Write a short draft first, then click to enhance with AI"}
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}

export function OnboardingWizard() {
  const router = useRouter();
  const { refreshAuth } = useAuth();

  // step 0 = Welcome intro screen, 1..5 = setup steps
  const [step, setStep] = useState(0);
  const [phase, setPhase] = useState<"editing" | "finalizing" | "completed">("editing");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [aiBusyKey, setAiBusyKey] = useState<string | null>(null);
  const [aiQuota, setAiQuota] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const [companyName, setCompanyName] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [idealCustomerText, setIdealCustomerText] = useState("");
  const [products, setProducts] = useState<ProductIn[]>([
    { kind: "product", name: "", description: "", price_range: "", min_order: "" },
  ]);
  const [extractingOfferings, setExtractingOfferings] = useState<"website" | "upload" | null>(null);
  const catalogInputRef = useRef<HTMLInputElement>(null);
  const [knowledgeCount, setKnowledgeCount] = useState(0);
  const [regions, setRegions] = useState<RegionIn[]>([]);
  const [language, setLanguage] = useState<string>("ar-EG");
  const [tone, setTone] = useState<"friendly" | "formal">("friendly");
  const [autonomyMode, setAutonomyMode] = useState<AutonomyMode>("approve_all");
  const [firstTouchMode, setFirstTouchMode] = useState<FirstTouchMode>("assisted");
  const [dailySendCap, setDailySendCap] = useState(25);
  const [quietStart, setQuietStart] = useState("10:00");
  const [quietEnd, setQuietEnd] = useState("20:00");

  useEffect(() => {
    let active = true;
    api
      .get<SettingsOut>("/settings", { suppressUnauthorizedRedirect: true })
      .then((res) => {
        if (!active) return;
        setCompanyName(res.company_name);
        setWebsite(res.website ?? "");
        setDescription(res.description);
        setIdealCustomerText(res.ideal_customer_text);
        if (res.products.length > 0) setProducts(res.products);
        setRegions(res.target_regions);
        setLanguage(res.language);
        setTone(res.tone);
        setAutonomyMode(res.autonomy_mode);
        setFirstTouchMode(res.first_touch_mode);
        setDailySendCap(res.daily_send_cap);
        setQuietStart(res.quiet_hours_start);
        setQuietEnd(res.quiet_hours_end);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Could not load workspace settings.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    api
      .get<{ limit: number; remaining: Record<string, number> }>("/settings/ai-quota", {
        suppressUnauthorizedRedirect: true,
      })
      .then((q) => {
        if (active) setAiQuota(q.remaining);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  function refreshAiQuota() {
    api
      .get<{ limit: number; remaining: Record<string, number> }>("/settings/ai-quota", {
        suppressUnauthorizedRedirect: true,
      })
      .then((q) => setAiQuota(q.remaining))
      .catch(() => {});
  }

  async function saveAndNext() {
    setError(null);
    if (step === 1 && !companyName.trim()) {
      setError("Company name is required.");
      return;
    }
    if (step === 2 && products.filter((p) => p.name.trim()).length === 0) {
      setError("Please add at least one product or service with a name.");
      return;
    }
    if (step === 4 && regions.length === 0) {
      setError("Please add at least one target region.");
      return;
    }

    setSaving(true);
    try {
      if (step === 1) {
        await api.put("/settings", {
          company_name: companyName.trim(),
          website: website.trim() || null,
          description: description.trim(),
          ideal_customer_text: idealCustomerText.trim(),
        });
      } else if (step === 2) {
        await api.put("/settings", {
          products: products.filter((p) => p.name.trim()),
        });
      } else if (step === 4) {
        await api.put("/settings", { target_regions: regions });
      }
      setStep((prev) => Math.min(5, prev + 1));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save step.");
    } finally {
      setSaving(false);
    }
  }

  async function finishOnboarding() {
    setError(null);
    setSaving(true);
    setPhase("finalizing");
    try {
      await api.put("/settings", {
        company_name: companyName.trim(),
        products: products.filter((p) => p.name.trim()),
        target_regions: regions,
        language,
        tone,
        autonomy_mode: autonomyMode,
        first_touch_mode: firstTouchMode,
        daily_send_cap: Number(dailySendCap),
        quiet_hours_start: quietStart,
        quiet_hours_end: quietEnd,
        onboarding_completed: true,
      });
      await refreshAuth();
      setPhase("completed");
      window.setTimeout(() => {
        router.replace(CUSTOMER_ROUTES.dashboard);
      }, 1800);
    } catch (err) {
      setPhase("editing");
      setError(err instanceof ApiError ? err.message : "Could not complete onboarding.");
    } finally {
      setSaving(false);
    }
  }

  function canNavigateToStep(targetStep: number): boolean {
    if (targetStep === step) return false;
    if (targetStep < step) return true;
    const hasCompany = Boolean(companyName.trim());
    const hasProducts = products.some((p) => p.name.trim().length > 0);
    const hasRegions = regions.length > 0;
    if (targetStep === 2) return hasCompany;
    if (targetStep === 3 || targetStep === 4) return hasCompany && hasProducts;
    if (targetStep === 5) return hasCompany && hasProducts && hasRegions;
    return false;
  }

  async function goToStep(targetStep: number) {
    if (!canNavigateToStep(targetStep) || saving) return;
    setError(null);
    if (targetStep < step) {
      setStep(targetStep);
      return;
    }

    setSaving(true);
    try {
      if (step === 1) {
        await api.put("/settings", {
          company_name: companyName.trim(),
          website: website.trim() || null,
          description: description.trim(),
          ideal_customer_text: idealCustomerText.trim(),
        });
      } else if (step === 2) {
        await api.put("/settings", {
          products: products.filter((p) => p.name.trim()),
        });
      } else if (step === 4) {
        await api.put("/settings", { target_regions: regions });
      }
      setStep(targetStep);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save step.");
    } finally {
      setSaving(false);
    }
  }

  async function runAiAssist(field: AiField, mode: AiMode) {
    setError(null);
    const currentText = field === "description" ? description : idealCustomerText;
    const otherText = field === "description" ? idealCustomerText : description;

    if (mode === "enhance" && !currentText.trim()) {
      setError("Write a short draft in that field first so AI can enhance and structure it.");
      return;
    }
    if (mode === "generate" && !website.trim()) {
      setError("Add your website URL first so AI can analyze it.");
      return;
    }

    const key = `${field}:${mode}`;
    setAiBusyKey(key);
    try {
      const res = await api.post<{ text: string; source_summary: string }>("/settings/ai-assist", {
        field,
        mode,
        company_name: companyName.trim(),
        website: website.trim() || null,
        current_text: currentText,
        other_text: otherText,
      });
      if (field === "description") {
        setDescription(res.text);
      } else {
        setIdealCustomerText(res.text);
      }
      refreshAiQuota();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate text with AI.");
    } finally {
      setAiBusyKey(null);
    }
  }

  function mergeExtractedOfferings(extracted: ProductIn[]) {
    setProducts((prev) => {
      const hasOnlyBlank = prev.length === 1 && !prev[0].name.trim();
      const base = hasOnlyBlank ? [] : prev;
      const seen = new Set(base.map((item) => item.name.trim().toLowerCase()));
      const next = [...base];
      for (const item of extracted) {
        const key = item.name.trim().toLowerCase();
        if (!key || seen.has(key) || next.length >= 30) continue;
        seen.add(key);
        next.push({
          kind: item.kind ?? "product",
          name: item.name,
          description: item.description ?? "",
          price_range: item.price_range ?? "",
          min_order: item.min_order ?? "",
        });
      }
      return next.length > 0 ? next : prev;
    });
  }

  async function runOfferingsExtract(file?: File) {
    setError(null);
    if (!file && !website.trim()) {
      setError("Add your website URL in Step 1 first, or upload a catalog file.");
      return;
    }
    setExtractingOfferings(file ? "upload" : "website");
    try {
      const form = new FormData();
      if (file) form.append("file", file);
      form.append("company_name", companyName.trim());
      form.append("website", website.trim());
      form.append("description", description.trim());
      const res = await apiFetch<{ items: ProductIn[]; source_summary: string }>(
        "/settings/ai-extract-offerings",
        { method: "POST", body: form },
      );
      mergeExtractedOfferings(res.items);
      refreshAiQuota();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not extract products & services with AI.");
    } finally {
      setExtractingOfferings(null);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin text-primary" />
          <span>Preparing your NEXUS workspace...</span>
        </div>
      </div>
    );
  }

  if (phase === "finalizing") {
    return (
      <Card className="mx-auto max-w-lg rounded-3xl border border-border/80 bg-card/90 text-center shadow-2xl shadow-lime-950/10 backdrop-blur-xl dark:border-[#223D27] dark:bg-[#112014]/90 dark:shadow-black/60">
        <CardContent className="space-y-4 p-10">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-primary/10">
            <Loader2 className="size-8 animate-spin text-primary dark:text-lime-400" />
          </div>
          <h2 className="text-xl font-bold text-foreground">Setting up your AI workspace...</h2>
          <p className="text-sm text-muted-foreground">
            Saving your company profile, products, target regions, and AI SDR guardrails.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (phase === "completed") {
    return (
      <Card className="mx-auto max-w-lg rounded-3xl border border-emerald-500/30 bg-card/90 text-center shadow-2xl shadow-lime-950/10 backdrop-blur-xl dark:bg-[#112014]/90 dark:shadow-black/60">
        <CardContent className="space-y-5 p-10">
          <div className="mx-auto flex size-16 animate-bounce items-center justify-center rounded-full bg-gradient-to-r from-[#10B981] to-[#84CC16] text-[#0A140C] shadow-lg">
            <CheckCircle2 className="size-9" />
          </div>
          <div className="space-y-1.5">
            <h2 className="text-2xl font-bold text-foreground">Everything is okay!</h2>
            <p className="text-sm text-muted-foreground">
              Your workspace is configured and ready. Redirecting you to your dashboard...
            </p>
          </div>
          <Button
            type="button"
            onClick={() => router.replace(CUSTOMER_ROUTES.dashboard)}
            className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]"
          >
            Go to Dashboard
            <ArrowRight className="ml-1.5 size-4" />
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (step === 0) {
    return (
      <Card className="mx-auto max-w-2xl rounded-3xl border border-border/80 bg-card/90 shadow-2xl shadow-lime-950/10 backdrop-blur-xl dark:border-[#223D27] dark:bg-[#112014]/90 dark:shadow-black/60">
        <CardContent className="space-y-6 p-8 md:p-10">
          <div className="space-y-3 text-center">
            <div className="mb-2 flex justify-center">
              <Logo />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Welcome to NEXUS</h1>
            <p className="mx-auto max-w-lg text-sm leading-relaxed text-muted-foreground">
              Before entering your dashboard, let&apos;s set up your business profile in 5 quick steps so your AI B2B SDR knows what you sell, who to target, and how to communicate.
            </p>
          </div>

          <div className="grid gap-2.5 sm:grid-cols-5">
            {STEPS.map((item) => (
              <div
                key={item.id}
                className="rounded-xl border border-border/70 bg-surface/50 p-3 text-center dark:border-[#223D27] dark:bg-[#0A140C]/60"
              >
                <span className="mx-auto mb-1.5 flex size-6 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary dark:text-lime-300">
                  {item.id}
                </span>
                <p className="text-xs font-semibold text-foreground">{item.title}</p>
              </div>
            ))}
          </div>

          <div className="flex justify-center pt-2">
            <Button
              type="button"
              size="lg"
              onClick={() => setStep(1)}
              className="bg-gradient-to-r from-[#10B981] to-[#84CC16] px-8 font-bold text-[#0A140C]"
            >
              Start Setup
              <ArrowRight className="ml-2 size-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const currentMeta = STEPS[step - 1];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground">Workspace Onboarding</h1>
        <p className="text-sm text-muted-foreground">
          Step {step} of {STEPS.length}: {currentMeta.subtitle}
        </p>
      </div>

      {/* Stepper header */}
      <ol className="grid grid-cols-5 gap-2">
        {STEPS.map((item) => {
          const done = step > item.id;
          const active = step === item.id;
          const clickable = canNavigateToStep(item.id);
          return (
            <li key={item.id}>
              <button
                type="button"
                disabled={!clickable || saving}
                onClick={() => void goToStep(item.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs transition-colors",
                  active
                    ? "border-primary bg-primary/10 font-semibold text-primary dark:border-lime-400 dark:bg-lime-500/15 dark:text-lime-300"
                    : done
                      ? "cursor-pointer border-emerald-500/30 bg-emerald-500/10 text-emerald-700 hover:border-emerald-500/60 dark:text-lime-200 dark:hover:border-lime-400/60"
                      : clickable
                        ? "cursor-pointer border-border/80 bg-card text-foreground/80 hover:border-primary/50 dark:hover:border-lime-400/50"
                        : "cursor-not-allowed border-border/70 bg-card text-muted-foreground opacity-60",
                )}
              >
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-current text-[11px]">
                  {done ? <Check className="size-3" /> : item.id}
                </span>
                <span className="hidden truncate sm:inline">{item.title}</span>
              </button>
            </li>
          );
        })}
      </ol>

      <Card className="border-border/80 bg-card">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="text-base">{currentMeta.title}</CardTitle>
            <CardDescription>{currentMeta.subtitle}</CardDescription>
          </div>
          {step === 2 && (
            <TooltipProvider delay={150}>
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "text-[10px] font-semibold tabular-nums",
                    (aiQuota.offerings ?? 3) <= 0 ? "text-red-500 dark:text-red-400" : "text-muted-foreground",
                  )}
                >
                  {aiQuota.offerings ?? 3}/3
                </span>
                <input
                  ref={catalogInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.md,.csv"
                  className="hidden"
                  onChange={(e) => {
                    const selected = e.target.files?.[0];
                    e.target.value = "";
                    if (selected) void runOfferingsExtract(selected);
                  }}
                />
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <button
                        type="button"
                        disabled={extractingOfferings !== null || (aiQuota.offerings ?? 3) <= 0}
                        onClick={() => void runOfferingsExtract()}
                        aria-label="Auto-extract products & services from website"
                        className="inline-flex size-8 items-center justify-center rounded-full border border-border/80 bg-surface/85 text-muted-foreground shadow-xs transition-colors hover:border-primary/50 hover:bg-primary/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-45 dark:border-[#223D27] dark:bg-[#0A140C]/85 dark:hover:border-lime-400/50 dark:hover:text-lime-300"
                      />
                    }
                  >
                    {extractingOfferings === "website" ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Wand2 className="size-3.5" />
                    )}
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    {(aiQuota.offerings ?? 3) <= 0
                      ? "All 3 AI attempts used for Products & Services"
                      : website.trim()
                        ? "Auto-extract products & services from your website"
                        : "Add your website URL in Step 1 to auto-extract"}
                  </TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger
                    render={
                      <button
                        type="button"
                        disabled={extractingOfferings !== null || (aiQuota.offerings ?? 3) <= 0}
                        onClick={() => catalogInputRef.current?.click()}
                        aria-label="Upload catalog or brochure to extract with AI"
                        className="inline-flex size-8 items-center justify-center rounded-full border border-border/80 bg-surface/85 text-muted-foreground shadow-xs transition-colors hover:border-primary/50 hover:bg-primary/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-45 dark:border-[#223D27] dark:bg-[#0A140C]/85 dark:hover:border-lime-400/50 dark:hover:text-lime-300"
                      />
                    }
                  >
                    {extractingOfferings === "upload" ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Upload className="size-3.5" />
                    )}
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    {(aiQuota.offerings ?? 3) <= 0
                      ? "All 3 AI attempts used for Products & Services"
                      : "Upload catalog (PDF, DOCX, TXT, CSV) to extract with AI"}
                  </TooltipContent>
                </Tooltip>
              </div>
            </TooltipProvider>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 1 && (
            <div className="space-y-4">
              <div className="grid items-start gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="ob-company" className="min-h-5">
                    Company name *
                  </Label>
                  <Input
                    id="ob-company"
                    dir="auto"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="ob-website" className="min-h-5">
                    Website <span className="text-xs font-normal text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="ob-website"
                    placeholder="https://example.com"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                  />
                  <p className="text-[11px] leading-snug text-muted-foreground">
                    Adding your website unlocks AI auto-fill for your company profile, offerings, and knowledge docs.
                  </p>
                </div>
              </div>
              <div className="grid gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="ob-desc">What does your company do?</Label>
                  <AiFieldActions
                    field="description"
                    hasText={Boolean(description.trim())}
                    busyKey={aiBusyKey}
                    remaining={aiQuota.description ?? 3}
                    generateTooltip={
                      website.trim()
                        ? "Auto-fill from your website"
                        : "Add your website URL first to auto-fill with AI"
                    }
                    onRun={(f, m) => void runAiAssist(f, m)}
                  />
                </div>
                <textarea
                  id="ob-desc"
                  dir="auto"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                />
              </div>
              <div className="grid gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="ob-icp">Ideal Customer Description</Label>
                  <AiFieldActions
                    field="ideal_customer_text"
                    hasText={Boolean(idealCustomerText.trim())}
                    busyKey={aiBusyKey}
                    remaining={aiQuota.ideal_customer_text ?? 3}
                    generateTooltip={
                      website.trim()
                        ? "Auto-fill ideal customer from your website"
                        : "Add your website URL first to auto-fill with AI"
                    }
                    onRun={(f, m) => void runAiAssist(f, m)}
                  />
                </div>
                <textarea
                  id="ob-icp"
                  dir="auto"
                  rows={3}
                  value={idealCustomerText}
                  onChange={(e) => setIdealCustomerText(e.target.value)}
                  className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                />
              </div>
            </div>
          )}

          {step === 2 && <ProductsEditor products={products} onChange={setProducts} />}

          {step === 3 && (
            <div className="space-y-3">
              <KnowledgeUploader
                onCountChange={setKnowledgeCount}
                aiContext={{
                  companyName,
                  website,
                  description,
                  idealCustomerText,
                }}
                aiQuota={aiQuota}
                onQuotaRefresh={refreshAiQuota}
              />
              <p className="text-xs text-muted-foreground">
                Uploaded files: {knowledgeCount}. You can upload or generate docs now, or add more later in Settings.
              </p>
            </div>
          )}

          {step === 4 && <GeoRegionSelector regions={regions} onChange={setRegions} />}

          {step === 5 && (
            <div className="space-y-5">
              <LanguageDialectSelector value={language} onChange={setLanguage} idPrefix="ob" />
              <ToneCardsSelector value={tone} onChange={setTone} />
              <AutonomyModeCardsSelector value={autonomyMode} onChange={setAutonomyMode} />
              <FirstTouchModeCardsSelector value={firstTouchMode} onChange={setFirstTouchMode} />

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-cap">Daily send cap</Label>
                  <Input
                    id="ob-cap"
                    type="number"
                    min={1}
                    max={200}
                    value={dailySendCap}
                    onChange={(e) => setDailySendCap(Number(e.target.value))}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-start">Window start</Label>
                  <Input
                    id="ob-start"
                    type="time"
                    value={quietStart}
                    onChange={(e) => setQuietStart(e.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-end">Window end</Label>
                  <Input
                    id="ob-end"
                    type="time"
                    value={quietEnd}
                    onChange={(e) => setQuietEnd(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
              {error}
            </p>
          )}

          <div className="flex items-center justify-between pt-2">
            <Button
              type="button"
              variant="outline"
              disabled={step <= 1 || saving}
              onClick={() => {
                setError(null);
                setStep((prev) => Math.max(1, prev - 1));
              }}
            >
              Back
            </Button>

            {step < 5 ? (
              <Button type="button" disabled={saving} onClick={() => void saveAndNext()}>
                {saving ? "Saving..." : "Save & Continue"}
              </Button>
            ) : (
              <Button
                type="button"
                disabled={saving}
                onClick={() => void finishOnboarding()}
                className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]"
              >
                <Sparkles className="mr-1.5 size-4" />
                Complete Setup
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
