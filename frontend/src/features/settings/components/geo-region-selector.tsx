"use client";

import { useEffect, useState } from "react";
import { MapPin, Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { GeoOut, GovernorateOut, RegionIn } from "@/lib/settings-types";
import { cn } from "@/lib/utils";

export function GeoRegionSelector({
  regions,
  onChange,
}: {
  regions: RegionIn[];
  onChange: (next: RegionIn[]) => void;
}) {
  const [governorates, setGovernorates] = useState<GovernorateOut[]>([]);
  const [selectedGov, setSelectedGov] = useState("");
  const [selectedCities, setSelectedCities] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    api
      .get<GeoOut>("/settings/geo", { suppressUnauthorizedRedirect: true })
      .then((res) => {
        if (!active) return;
        setGovernorates(res.governorates);
        if (res.governorates.length > 0) {
          setSelectedGov(res.governorates[0].name);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const currentGov = governorates.find((g) => g.name === selectedGov);

  function toggleCity(cityName: string) {
    setSelectedCities((prev) =>
      prev.includes(cityName) ? prev.filter((c) => c !== cityName) : [...prev, cityName],
    );
  }

  function addRegion() {
    if (!selectedGov) return;
    const withoutGov = regions.filter((r) => r.governorate !== selectedGov);
    onChange([...withoutGov, { governorate: selectedGov, cities: selectedCities }]);
    setSelectedCities([]);
  }

  function removeRegion(govName: string) {
    onChange(regions.filter((r) => r.governorate !== govName));
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <div className="grid gap-1.5">
          <Label htmlFor="geo-governorate">Governorate (Egypt)</Label>
          <select
            id="geo-governorate"
            value={selectedGov}
            onChange={(e) => {
              setSelectedGov(e.target.value);
              setSelectedCities([]);
            }}
            className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm text-foreground dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white"
          >
            {governorates.map((gov) => (
              <option key={gov.name} value={gov.name}>
                {gov.name} — {gov.name_ar}
              </option>
            ))}
          </select>
        </div>

        <Button type="button" variant="outline" onClick={addRegion} disabled={!selectedGov}>
          <Plus className="mr-1.5 size-4" />
          Add Region
        </Button>
      </div>

      {currentGov && currentGov.cities.length > 0 && (
        <div className="space-y-1.5 rounded-xl border border-border/70 bg-surface/50 p-3 dark:border-[#223D27] dark:bg-[#0A140C]/60">
          <p className="text-xs font-medium text-muted-foreground">
            Optional cities in {currentGov.name} (leave empty to target the entire governorate):
          </p>
          <div className="flex flex-wrap gap-1.5">
            {currentGov.cities.map((city) => {
              const active = selectedCities.includes(city.name);
              return (
                <button
                  key={city.name}
                  type="button"
                  onClick={() => toggleCity(city.name)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-xs transition-colors",
                    active
                      ? "border-primary bg-primary/15 font-medium text-primary dark:border-lime-400 dark:bg-lime-500/20 dark:text-lime-200"
                      : "border-border bg-card text-muted-foreground hover:text-foreground dark:border-[#223D27]",
                  )}
                >
                  {city.name} ({city.name_ar})
                </button>
              );
            })}
          </div>
        </div>
      )}

      {regions.length === 0 ? (
        <p className="text-xs text-muted-foreground">No target regions added yet.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {regions.map((reg) => (
            <Badge
              key={reg.governorate}
              variant="secondary"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs"
            >
              <MapPin className="size-3.5 text-primary dark:text-lime-400" />
              <span>
                {reg.governorate}
                {reg.cities.length > 0 ? `: ${reg.cities.join(", ")}` : " (All cities)"}
              </span>
              <button
                type="button"
                aria-label={`Remove ${reg.governorate}`}
                onClick={() => removeRegion(reg.governorate)}
                className="ml-1 rounded hover:text-red-600"
              >
                <X className="size-3.5" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
