"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GeoRegionSelector } from "@/features/settings/components/geo-region-selector";
import { ProductsEditor } from "@/features/settings/components/products-editor";
import { ApiError, api } from "@/lib/api";
import type { ProductIn, RegionIn, SettingsOut } from "@/lib/settings-types";

export function BusinessSettingsPanel({
  settings,
  onUpdated,
}: {
  settings: SettingsOut;
  onUpdated: (next: SettingsOut) => void;
}) {
  const [companyName, setCompanyName] = useState(settings.company_name);
  const [website, setWebsite] = useState(settings.website ?? "");
  const [description, setDescription] = useState(settings.description);
  const [idealCustomerText, setIdealCustomerText] = useState(settings.ideal_customer_text);
  const [products, setProducts] = useState<ProductIn[]>(
    settings.products.length > 0
      ? settings.products
      : [{ name: "", description: "", price_range: "", min_order: "" }],
  );
  const [regions, setRegions] = useState<RegionIn[]>(settings.target_regions);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    const cleanedProducts = products.filter((p) => p.name.trim().length > 0);
    if (cleanedProducts.length === 0) {
      setError("Please add at least one product with a name.");
      return;
    }
    if (regions.length === 0) {
      setError("Please select at least one target region.");
      return;
    }
    setSaving(true);
    try {
      const updated = await api.put<SettingsOut>("/settings", {
        company_name: companyName.trim(),
        website: website.trim() || null,
        description: description.trim(),
        ideal_customer_text: idealCustomerText.trim(),
        products: cleanedProducts,
        target_regions: regions,
      });
      onUpdated(updated);
      setMessage("Business profile, products, and target regions saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save business settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Company Profile</CardTitle>
          <CardDescription>
            Core details your AI SDR uses to introduce your business and qualify B2B leads.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="biz-company">Company name *</Label>
              <Input
                id="biz-company"
                dir="auto"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="biz-website">Website</Label>
              <Input
                id="biz-website"
                placeholder="https://example.com"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="biz-desc">Business description</Label>
            <textarea
              id="biz-desc"
              dir="auto"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What do you manufacture or supply?"
              className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm text-foreground dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white"
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="biz-icp">Ideal Customer Description</Label>
            <textarea
              id="biz-icp"
              dir="auto"
              rows={3}
              value={idealCustomerText}
              onChange={(e) => setIdealCustomerText(e.target.value)}
              placeholder="e.g. Kids clothing retail stores and wholesalers in Cairo & Giza..."
              className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm text-foreground dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white"
            />
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Products & Pricing</CardTitle>
          <CardDescription>Catalog items the agent can pitch and quote during outreach.</CardDescription>
        </CardHeader>
        <CardContent>
          <ProductsEditor products={products} onChange={setProducts} />
        </CardContent>
      </Card>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Target Regions</CardTitle>
          <CardDescription>Governorates and cities where NEXUS discovers prospects.</CardDescription>
        </CardHeader>
        <CardContent>
          <GeoRegionSelector regions={regions} onChange={setRegions} />
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
        {saving ? "Saving..." : "Save Business Settings"}
      </Button>
    </form>
  );
}
