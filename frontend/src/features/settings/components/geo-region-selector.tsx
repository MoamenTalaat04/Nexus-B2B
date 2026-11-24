"use client";

import { useEffect, useMemo, useState } from "react";
import { City, Country, State } from "country-state-city";
import {
  AlertCircle,
  Check,
  Crosshair,
  Globe,
  Map as MapIcon,
  MapPin,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { GeoOut, GovernorateOut, RegionIn } from "@/lib/settings-types";
import { cn } from "@/lib/utils";
import { RegionCircleMap } from "./region-circle-map";

type InputMethod = "manual" | "radius";
type ManualCoverageMode = "entire" | "cities";

function regionKey(reg: RegionIn): string {
  const country = (reg.country ?? "Egypt").trim().toLowerCase();
  const gov = reg.governorate.trim().toLowerCase();
  return `${country}::${gov}`;
}

export function GeoRegionSelector({
  regions,
  onChange,
}: {
  regions: RegionIn[];
  onChange: (next: RegionIn[]) => void;
}) {
  const [egGovernorates, setEgGovernorates] = useState<GovernorateOut[]>([]);
  const allCountries = useMemo(() => Country.getAllCountries(), []);

  const [inputMethod, setInputMethod] = useState<InputMethod>("manual");
  const [selectedCountryCode, setSelectedCountryCode] = useState<string>("EG");
  const [selectedStateCode, setSelectedStateCode] = useState<string>("");
  const [manualCoverage, setManualCoverage] = useState<ManualCoverageMode>("entire");

  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  const [citySearch, setCitySearch] = useState("");
  const [customCity, setCustomCity] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [logicNotice, setLogicNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .get<GeoOut>("/settings/geo", { suppressUnauthorizedRedirect: true })
      .then((res) => {
        if (!active) return;
        setEgGovernorates(res.governorates);
        if (res.governorates.length > 0) {
          setSelectedStateCode((prev) => prev || res.governorates[0].name);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const selectedCountry = useMemo(
    () => allCountries.find((c) => c.isoCode === selectedCountryCode),
    [allCountries, selectedCountryCode],
  );
  const countryName = selectedCountry?.name ?? "Egypt";
  const isEgypt = selectedCountryCode === "EG" && egGovernorates.length > 0;

  const statesForCountry = useMemo(() => {
    if (isEgypt) {
      return egGovernorates.map((g) => ({
        code: g.name,
        name: g.name,
        label: `${g.name} — ${g.name_ar}`,
      }));
    }
    const states = State.getStatesOfCountry(selectedCountryCode);
    if (states.length === 0) {
      return [{ code: countryName, name: countryName, label: `${countryName} (All regions)` }];
    }
    return states.map((s) => ({
      code: s.isoCode,
      name: s.name,
      label: s.name,
    }));
  }, [isEgypt, egGovernorates, selectedCountryCode, countryName]);

  const activeState =
    statesForCountry.find((s) => s.code === selectedStateCode) ?? statesForCountry[0];

  const cityOptions = useMemo(() => {
    if (!activeState) return [];
    if (isEgypt) {
      const gov = egGovernorates.find((g) => g.name === activeState.name);
      return (gov?.cities ?? []).map((c) => ({
        value: c.name,
        label: `${c.name} (${c.name_ar})`,
      }));
    }
    const cities = City.getCitiesOfState(selectedCountryCode, activeState.code);
    return cities.slice(0, 120).map((c) => ({
      value: c.name,
      label: c.name,
    }));
  }, [activeState, isEgypt, egGovernorates, selectedCountryCode]);

  const filteredCities = useMemo(() => {
    const q = citySearch.trim().toLowerCase();
    if (!q) return cityOptions;
    return cityOptions.filter((c) => c.label.toLowerCase().includes(q));
  }, [cityOptions, citySearch]);

  function handleCountryChange(isoCode: string) {
    setSelectedCountryCode(isoCode);
    setSelectedCities([]);
    setCitySearch("");
    setEditingKey(null);
    setLogicNotice(null);
    if (isoCode === "EG" && egGovernorates.length > 0) {
      setSelectedStateCode(egGovernorates[0].name);
    } else {
      const nextStates = State.getStatesOfCountry(isoCode);
      setSelectedStateCode(nextStates[0]?.isoCode ?? "");
    }
  }

  function toggleCity(cityName: string) {
    setLogicNotice(null);
    setSelectedCities((prev) =>
      prev.includes(cityName) ? prev.filter((c) => c !== cityName) : [...prev, cityName],
    );
  }

  function toggleSelectAllFiltered() {
    if (filteredCities.length === 0) return;
    const filteredValues = filteredCities.map((c) => c.value);
    const allSelected = filteredValues.every((val) => selectedCities.includes(val));
    if (allSelected) {
      setSelectedCities((prev) => prev.filter((c) => !filteredValues.includes(c)));
    } else {
      setSelectedCities((prev) => Array.from(new Set([...prev, ...filteredValues])));
    }
  }

  function addCustomCity() {
    const clean = customCity.trim();
    if (!clean) return;
    if (!selectedCities.includes(clean)) {
      setSelectedCities((prev) => [...prev, clean]);
    }
    setCustomCity("");
  }

  function upsertSingleRegion(nextRegion: RegionIn) {
    setLogicNotice(null);
    const key = regionKey(nextRegion);
    const existing = regions.find((r) => regionKey(r) === key);

    if (existing && !editingKey) {
      const existingIsEntire = existing.cities.length === 0 && !existing.radius_km;
      if (existingIsEntire && nextRegion.cities.length > 0 && !nextRegion.radius_km) {
        setLogicNotice(
          `${nextRegion.governorate} is already added as an entire area. Click Edit on it below to switch to specific cities.`,
        );
        return;
      }
      if (existingIsEntire && !nextRegion.radius_km && nextRegion.cities.length === 0) {
        setLogicNotice(`${nextRegion.governorate} is already in your target areas.`);
        return;
      }
    }

    const base = editingKey ? regions.filter((r) => regionKey(r) !== editingKey) : regions;
    const filtered = base.filter((r) => regionKey(r) !== key);
    onChange([...filtered, nextRegion]);
    setSelectedCities([]);
    setCitySearch("");
    setEditingKey(null);
  }

  function upsertCircleRegions(resolvedRegions: RegionIn[]) {
    setLogicNotice(null);
    let nextList = [...regions];
    for (const incoming of resolvedRegions) {
      const key = regionKey(incoming);
      const existing = nextList.find((r) => regionKey(r) === key);
      if (existing && existing.radius_km) {
        const mergedCities = Array.from(new Set([...existing.cities, ...incoming.cities]));
        nextList = nextList.map((r) =>
          regionKey(r) === key ? { ...incoming, cities: mergedCities } : r,
        );
      } else {
        nextList = [...nextList.filter((r) => regionKey(r) !== key), incoming];
      }
    }
    onChange(nextList);
    setEditingKey(null);
  }

  function handleAddFromManual() {
    if (!activeState) return;
    if (manualCoverage === "cities" && selectedCities.length === 0) {
      setLogicNotice("Select at least one city/district, or switch to Entire area.");
      return;
    }
    upsertSingleRegion({
      country: countryName,
      governorate: activeState.name,
      cities: manualCoverage === "cities" ? selectedCities : [],
    });
  }

  function startEditRegion(reg: RegionIn) {
    setLogicNotice(null);
    if (reg.radius_km) {
      setInputMethod("radius");
      setEditingKey(regionKey(reg));
      return;
    }

    setInputMethod("manual");
    const countryObj = allCountries.find(
      (c) => c.name.toLowerCase() === (reg.country ?? "Egypt").toLowerCase(),
    );
    const iso = countryObj?.isoCode ?? "EG";
    setSelectedCountryCode(iso);

    if (iso === "EG") {
      setSelectedStateCode(reg.governorate);
    } else {
      const matchedState = State.getStatesOfCountry(iso).find(
        (s) => s.name.toLowerCase() === reg.governorate.toLowerCase(),
      );
      setSelectedStateCode(matchedState?.isoCode ?? reg.governorate);
    }

    if (reg.cities.length > 0) {
      setManualCoverage("cities");
      setSelectedCities(reg.cities);
    } else {
      setManualCoverage("entire");
      setSelectedCities([]);
    }
    setEditingKey(regionKey(reg));
  }

  function removeRegion(target: RegionIn) {
    const key = regionKey(target);
    if (editingKey === key) setEditingKey(null);
    onChange(regions.filter((r) => regionKey(r) !== key));
  }

  const areaUnitLabel = isEgypt ? "governorate" : "state";

  return (
    <div className="space-y-5">
      {/* Step 1: Choose Input Method (Manual vs Custom Radius) */}
      <div className="space-y-4 rounded-2xl border border-border/80 bg-surface/40 p-4 dark:border-[#223D27] dark:bg-[#0A140C]/55">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-foreground">
              {editingKey ? "Edit target area" : "How would you like to add target areas?"}
            </p>
            <p className="text-xs text-muted-foreground">
              Pick locations manually by country &amp; state, or draw a radius circle on the map.
            </p>
          </div>
          {editingKey && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditingKey(null);
                setSelectedCities([]);
                setLogicNotice(null);
              }}
              className="h-7 text-xs"
            >
              Cancel edit
            </Button>
          )}
        </div>

        {/* Input Method Cards */}
        <div className="grid gap-2.5 sm:grid-cols-2">
          {[
            {
              id: "manual" as const,
              title: "Manual Selection",
              desc: "Choose country, state/governorate, and cities or entire area.",
              icon: Globe,
            },
            {
              id: "radius" as const,
              title: "Custom Radius on Map",
              desc: "Set a circle on the map — auto-adds all states & cities inside.",
              icon: Crosshair,
            },
          ].map((opt) => {
            const Icon = opt.icon;
            const active = inputMethod === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  setInputMethod(opt.id);
                  setLogicNotice(null);
                }}
                className={cn(
                  "flex items-start gap-3 rounded-xl border p-3 text-left transition-all",
                  active
                    ? "border-primary bg-primary/10 shadow-xs dark:border-lime-400 dark:bg-lime-500/15"
                    : "border-border/80 bg-card/70 hover:border-primary/45 dark:border-[#223D27] dark:bg-[#112014]/70 dark:hover:border-lime-400/45",
                )}
              >
                <span
                  className={cn(
                    "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border",
                    active
                      ? "border-primary/40 bg-primary text-primary-foreground dark:border-lime-400/50 dark:bg-lime-400 dark:text-[#0A140C]"
                      : "border-border/80 bg-surface/70 text-muted-foreground dark:border-[#223D27] dark:bg-[#0A140C]",
                  )}
                >
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-xs font-semibold text-foreground">{opt.title}</span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    {opt.desc}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        {/* Manual Flow */}
        {inputMethod === "manual" && (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="geo-country" className="text-xs">
                  1. Country
                </Label>
                <select
                  id="geo-country"
                  value={selectedCountryCode}
                  onChange={(e) => handleCountryChange(e.target.value)}
                  className="h-10 rounded-lg border border-input bg-card px-3 text-sm text-foreground dark:border-[#223D27] dark:bg-[#112014] dark:text-white"
                >
                  {allCountries.map((country) => (
                    <option key={country.isoCode} value={country.isoCode}>
                      {country.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="geo-governorate" className="text-xs">
                  2. {isEgypt ? "Governorate" : "State / Region"}
                </Label>
                <select
                  id="geo-governorate"
                  value={activeState?.code ?? ""}
                  onChange={(e) => {
                    setSelectedStateCode(e.target.value);
                    setSelectedCities([]);
                    setCitySearch("");
                    setLogicNotice(null);
                  }}
                  className="h-10 rounded-lg border border-input bg-card px-3 text-sm text-foreground dark:border-[#223D27] dark:bg-[#112014] dark:text-white"
                >
                  {statesForCountry.map((state) => (
                    <option key={state.code} value={state.code}>
                      {state.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs">3. Which areas should we cover?</Label>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {[
                  {
                    id: "entire" as const,
                    title: `Entire ${areaUnitLabel}`,
                    desc: `Target all of ${activeState?.name ?? countryName}.`,
                    icon: MapIcon,
                    badge: "Recommended",
                  },
                  {
                    id: "cities" as const,
                    title: "Specific cities & districts",
                    desc: "Choose only the cities or neighborhoods you want.",
                    icon: MapPin,
                  },
                ].map((opt) => {
                  const Icon = opt.icon;
                  const active = manualCoverage === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        setManualCoverage(opt.id);
                        setLogicNotice(null);
                      }}
                      className={cn(
                        "flex flex-col items-start gap-1.5 rounded-xl border p-3 text-left transition-all",
                        active
                          ? "border-primary bg-primary/10 shadow-xs dark:border-lime-400 dark:bg-lime-500/15"
                          : "border-border/80 bg-card/70 hover:border-primary/45 dark:border-[#223D27] dark:bg-[#112014]/70 dark:hover:border-lime-400/45",
                      )}
                    >
                      <div className="flex w-full items-center justify-between gap-2">
                        <span
                          className={cn(
                            "flex size-7 items-center justify-center rounded-lg border",
                            active
                              ? "border-primary/40 bg-primary text-primary-foreground dark:border-lime-400/50 dark:bg-lime-400 dark:text-[#0A140C]"
                              : "border-border/80 bg-surface/70 text-muted-foreground dark:border-[#223D27] dark:bg-[#0A140C]",
                          )}
                        >
                          <Icon className="size-3.5" />
                        </span>
                        {opt.badge && (
                          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-lime-300">
                            {opt.badge}
                          </span>
                        )}
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-foreground">{opt.title}</p>
                        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{opt.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {manualCoverage === "entire" && activeState && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 dark:border-lime-400/30 dark:bg-lime-500/10">
                <div className="flex items-center gap-2.5">
                  <span className="flex size-6 items-center justify-center rounded-full bg-emerald-500 text-white dark:bg-lime-400 dark:text-[#0A140C]">
                    <Check className="size-3.5" />
                  </span>
                  <div>
                    <p className="text-xs font-semibold text-foreground">
                      {activeState.name}, {countryName}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Your AI agent will search for leads across the entire {areaUnitLabel}.
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  onClick={handleAddFromManual}
                  className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                >
                  <Plus className="mr-1.5 size-3.5" />
                  {editingKey ? "Update Target Area" : "Add Target Area"}
                </Button>
              </div>
            )}

            {manualCoverage === "cities" && activeState && (
              <div className="space-y-3 rounded-xl border border-border/70 bg-card/70 p-3.5 dark:border-[#223D27] dark:bg-[#112014]/60">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-foreground">
                    Select target areas in {activeState.name}
                  </p>
                  <span className="text-[11px] font-medium text-primary dark:text-lime-300">
                    {selectedCities.length} area{selectedCities.length === 1 ? "" : "s"} selected
                  </span>
                </div>

                {cityOptions.length > 0 && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="relative min-w-[180px] flex-1">
                        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          placeholder="Search cities or neighborhoods..."
                          value={citySearch}
                          onChange={(e) => setCitySearch(e.target.value)}
                          className="h-8 pl-8 text-xs"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={toggleSelectAllFiltered}
                        className="h-8 text-xs"
                      >
                        {filteredCities.length > 0 &&
                        filteredCities.every((c) => selectedCities.includes(c.value))
                          ? "Clear visible"
                          : "Select all"}
                      </Button>
                    </div>

                    <div className="grid max-h-44 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2">
                      {filteredCities.map((city) => {
                        const active = selectedCities.includes(city.value);
                        return (
                          <button
                            key={city.value}
                            type="button"
                            onClick={() => toggleCity(city.value)}
                            className={cn(
                              "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-xs transition-colors",
                              active
                                ? "border-primary/60 bg-primary/10 font-medium text-foreground dark:border-lime-400/50 dark:bg-lime-500/15"
                                : "border-border/70 bg-surface/40 text-muted-foreground hover:text-foreground dark:border-[#223D27] dark:bg-[#0A140C]/50",
                            )}
                          >
                            <span
                              className={cn(
                                "flex size-4 shrink-0 items-center justify-center rounded border",
                                active
                                  ? "border-primary bg-primary text-primary-foreground dark:border-lime-400 dark:bg-lime-400 dark:text-[#0A140C]"
                                  : "border-border dark:border-[#2d4d33]",
                              )}
                            >
                              {active && <Check className="size-2.5" />}
                            </span>
                            <span className="truncate">{city.label}</span>
                          </button>
                        );
                      })}
                      {filteredCities.length === 0 && (
                        <p className="col-span-2 py-2 text-center text-xs text-muted-foreground">
                          No matching cities found. Add one manually below.
                        </p>
                      )}
                    </div>
                  </>
                )}

                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Add custom city or neighborhood..."
                    value={customCity}
                    onChange={(e) => setCustomCity(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustomCity();
                      }
                    }}
                    className="h-8 text-xs"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addCustomCity}
                    disabled={!customCity.trim()}
                    className="h-8"
                  >
                    Add
                  </Button>
                </div>

                {selectedCities.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {selectedCities.map((city) => (
                      <Badge key={city} variant="secondary" className="gap-1 text-[11px]">
                        {city}
                        <button
                          type="button"
                          aria-label={`Remove ${city}`}
                          onClick={() => toggleCity(city)}
                          className="rounded hover:text-red-500"
                        >
                          <X className="size-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="flex justify-end pt-1">
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleAddFromManual}
                    className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                  >
                    <Plus className="mr-1.5 size-3.5" />
                    {editingKey ? "Update Target Area" : "Add Target Area"}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Custom Radius on Map Flow (independent of Country/State) */}
        {inputMethod === "radius" && <RegionCircleMap onResolved={upsertCircleRegions} />}

        {logicNotice && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-500/35 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
            <AlertCircle className="size-3.5 shrink-0" />
            <span>{logicNotice}</span>
          </div>
        )}
      </div>

      {/* Review Target Areas Summary Panel */}
      <div className="space-y-2.5 rounded-2xl border border-border/80 bg-card/60 p-4 dark:border-[#223D27] dark:bg-[#112014]/45">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold tracking-wide text-foreground uppercase">
            Your target areas
          </p>
          <Badge variant="secondary" className="text-[11px]">
            {regions.length} {regions.length === 1 ? "Area" : "Areas"}
          </Badge>
        </div>

        {regions.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No target areas added yet. Choose Manual Selection or Custom Radius above.
          </p>
        ) : (
          <div className="space-y-2">
            {regions.map((reg) => {
              const key = regionKey(reg);
              const countryLabel = reg.country ?? "Egypt";
              const typeBadge = reg.radius_km
                ? "Radius"
                : reg.cities.length > 0
                  ? "Selected cities"
                  : "Entire area";
              const detailText = reg.radius_km
                ? `${reg.radius_km} km radius${
                    reg.cities.length > 0
                      ? ` · ${reg.cities.length} inside circle: ${reg.cities.slice(0, 4).join(", ")}${reg.cities.length > 4 ? ` +${reg.cities.length - 4}` : ""}`
                      : ""
                  }`
                : reg.cities.length > 0
                  ? `${reg.cities.length} selected: ${reg.cities.slice(0, 4).join(", ")}${reg.cities.length > 4 ? ` +${reg.cities.length - 4}` : ""}`
                  : "Entire governorate / state";

              return (
                <div
                  key={key}
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3.5 py-2.5 transition-colors",
                    editingKey === key
                      ? "border-primary bg-primary/10 dark:border-lime-400"
                      : "border-border/70 bg-surface/50 dark:border-[#223D27] dark:bg-[#0A140C]/60",
                  )}
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <MapPin className="size-4 shrink-0 text-primary dark:text-lime-400" />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-xs font-semibold text-foreground">
                          {countryLabel} · {reg.governorate}
                        </p>
                        <Badge variant="outline" className="h-5 text-[10px]">
                          {typeBadge}
                        </Badge>
                      </div>
                      <p className="truncate text-[11px] text-muted-foreground">{detailText}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    {!reg.radius_km && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => startEditRegion(reg)}
                        className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                      >
                        <Pencil className="mr-1 size-3" />
                        Edit
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Remove ${reg.governorate}`}
                      onClick={() => removeRegion(reg)}
                      className="size-7 text-muted-foreground hover:text-red-600"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
