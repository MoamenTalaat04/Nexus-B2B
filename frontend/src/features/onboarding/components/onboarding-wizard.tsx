"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CUSTOMER_ROUTES } from "@/config/routes";
import { KnowledgeUploader } from "@/features/knowledge/components/knowledge-uploader";
import { GeoRegionSelector } from "@/features/settings/components/geo-region-selector";
import { ProductsEditor } from "@/features/settings/components/products-editor";
import { ApiError, api } from "@/lib/api";
import type { ProductIn, RegionIn, SettingsOut } from "@/lib/settings-types";
import { AutonomyModeValues, FirstTouchModeValues, type AutonomyMode, type FirstTouchMode } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: 1, title: "Company", subtitle: "Tell NEXUS about your business" },
  { id: 2, title: "Products", subtitle: "Add what you sell or supply" },
  { id: 3, title: "Knowledge", subtitle: "Upload catalogs, FAQs, or price lists" },
  { id: 4, title: "Regions", subtitle: "Pick target governorates & cities" },
  { id: 5, title: "Agent Behavior", subtitle: "Set tone, autonomy, and daily cap" },
] as const;

export function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [companyName, setCompanyName] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [idealCustomerText, setIdealCustomerText] = useState("");
  const [products, setProducts] = useState<ProductIn[]>([
    { name: "", description: "", price_range: "", min_order: "" },
  ]);
  const [knowledgeCount, setKnowledgeCount] = useState(0);
  const [regions, setRegions] = useState<RegionIn[]>([]);
  const [language, setLanguage] = useState<"ar-EG" | "en">("ar-EG");
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
    return () => {
      active = false;
    };
  }, []);

  async function saveAndNext() {
    setError(null);
    if (step === 1 && !companyName.trim()) {
      setError("Company name is required.");
      return;
    }
    if (step === 2 && products.filter((p) => p.name.trim()).length === 0) {
      setError("Please add at least one product with a name.");
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
      router.push(CUSTOMER_ROUTES.settings);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete onboarding.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading onboarding wizard...</p>;
  }

  const currentMeta = STEPS[step - 1];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Workspace Onboarding</h1>
          <p className="text-sm text-muted-foreground">
            Step {step} of {STEPS.length}: {currentMeta.subtitle}
          </p>
        </div>
      </div>

      {/* Stepper header */}
      <ol className="grid grid-cols-5 gap-2">
        {STEPS.map((item) => {
          const done = step > item.id;
          const active = step === item.id;
          return (
            <li
              key={item.id}
              className={cn(
                "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors",
                active
                  ? "border-primary bg-primary/10 font-semibold text-primary dark:border-lime-400 dark:bg-lime-500/15 dark:text-lime-300"
                  : done
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-lime-200"
                    : "border-border/70 bg-card text-muted-foreground",
              )}
            >
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-current text-[11px]">
                {done ? <Check className="size-3" /> : item.id}
              </span>
              <span className="hidden truncate sm:inline">{item.title}</span>
            </li>
          );
        })}
      </ol>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">{currentMeta.title}</CardTitle>
          <CardDescription>{currentMeta.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 1 && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-company">Company name *</Label>
                  <Input
                    id="ob-company"
                    dir="auto"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-website">Website</Label>
                  <Input
                    id="ob-website"
                    placeholder="https://example.com"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="ob-desc">What does your company do?</Label>
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
                <Label htmlFor="ob-icp">Ideal Customer Description</Label>
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
              <KnowledgeUploader onCountChange={setKnowledgeCount} />
              <p className="text-xs text-muted-foreground">
                Uploaded files: {knowledgeCount}. This step is optional — you can add more anytime in Settings.
              </p>
            </div>
          )}

          {step === 4 && <GeoRegionSelector regions={regions} onChange={setRegions} />}

          {step === 5 && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-lang">Outreach language</Label>
                  <select
                    id="ob-lang"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value as "ar-EG" | "en")}
                    className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                  >
                    <option value="ar-EG">Egyptian Arabic (ar-EG)</option>
                    <option value="en">English (en)</option>
                  </select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-tone">Tone</Label>
                  <select
                    id="ob-tone"
                    value={tone}
                    onChange={(e) => setTone(e.target.value as "friendly" | "formal")}
                    className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                  >
                    <option value="friendly">Friendly</option>
                    <option value="formal">Formal</option>
                  </select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-autonomy">Autonomy mode</Label>
                  <select
                    id="ob-autonomy"
                    value={autonomyMode}
                    onChange={(e) => setAutonomyMode(e.target.value as AutonomyMode)}
                    className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                  >
                    {AutonomyModeValues.map((m) => (
                      <option key={m} value={m}>
                        {m.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="ob-first-touch">First-touch mode</Label>
                  <select
                    id="ob-first-touch"
                    value={firstTouchMode}
                    onChange={(e) => setFirstTouchMode(e.target.value as FirstTouchMode)}
                    className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                  >
                    {FirstTouchModeValues.map((m) => (
                      <option key={m} value={m}>
                        {m.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

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
              disabled={step === 1 || saving}
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
                {saving ? "Finishing..." : "Complete Setup"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
