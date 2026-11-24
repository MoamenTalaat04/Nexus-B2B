"use client";

import { useEffect, useRef, useState } from "react";
import { Crosshair, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import type { RegionIn } from "@/lib/settings-types";

interface RegionCircleMapProps {
  onResolved: (regions: RegionIn[]) => void;
}

export function RegionCircleMap({ onResolved }: RegionCircleMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const circleRef = useRef<import("leaflet").Circle | null>(null);
  const markerRef = useRef<import("leaflet").CircleMarker | null>(null);

  const [center, setCenter] = useState<{ lat: number; lng: number }>({
    lat: 30.0444,
    lng: 31.2357,
  });
  const [radiusKm, setRadiusKm] = useState<number>(15);
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let mapInstance: import("leaflet").Map | null = null;

    async function initMap() {
      if (!mapContainerRef.current || mapRef.current) return;
      const L = await import("leaflet");
      if (!document.getElementById("leaflet-css-cdn")) {
        const link = document.createElement("link");
        link.id = "leaflet-css-cdn";
        link.rel = "stylesheet";
        link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(link);
      }
      if (cancelled || !mapContainerRef.current) return;

      mapInstance = L.map(mapContainerRef.current, {
        center: [center.lat, center.lng],
        zoom: 10,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 18,
      }).addTo(mapInstance);

      const circle = L.circle([center.lat, center.lng], {
        radius: radiusKm * 1000,
        color: "#10B981",
        fillColor: "#84CC16",
        fillOpacity: 0.2,
        weight: 2,
      }).addTo(mapInstance);

      const marker = L.circleMarker([center.lat, center.lng], {
        radius: 6,
        color: "#0A140C",
        fillColor: "#84CC16",
        fillOpacity: 1,
        weight: 2,
      }).addTo(mapInstance);

      mapInstance.on("click", (e) => {
        setCenter({ lat: e.latlng.lat, lng: e.latlng.lng });
      });

      mapRef.current = mapInstance;
      circleRef.current = circle;
      markerRef.current = marker;
    }

    void initMap();

    return () => {
      cancelled = true;
      if (mapInstance) {
        mapInstance.remove();
      }
      mapRef.current = null;
      circleRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (circleRef.current) {
      circleRef.current.setLatLng([center.lat, center.lng]);
      circleRef.current.setRadius(radiusKm * 1000);
    }
    if (markerRef.current) {
      markerRef.current.setLatLng([center.lat, center.lng]);
    }
  }, [center, radiusKm]);

  async function handleSearchPlace() {
    const q = searchQuery.trim();
    if (!q) return;
    setError(null);
    setSearching(true);
    try {
      const resp = await fetch(
        `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(q)}`,
      );
      const results = (await resp.json()) as Array<{ lat: string; lon: string }>;
      if (!results || results.length === 0) {
        setError("Location not found. Try another city or click directly on the map.");
        return;
      }
      const lat = Number(results[0].lat);
      const lng = Number(results[0].lon);
      setCenter({ lat, lng });
      mapRef.current?.setView([lat, lng], 11);
    } catch {
      setError("Could not search location right now. Click directly on the map instead.");
    } finally {
      setSearching(false);
    }
  }

  async function handleResolveCircle() {
    setError(null);
    setResolving(true);
    try {
      const res = await api.post<{ regions: RegionIn[] }>(
        "/settings/geo/resolve-circle",
        {
          lat: center.lat,
          lng: center.lng,
          radius_km: radiusKm,
        },
        { suppressUnauthorizedRedirect: true },
      );
      onResolved(res.regions);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not detect regions inside this circle.");
    } finally {
      setResolving(false);
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-border/70 bg-card/70 p-3.5 dark:border-[#223D27] dark:bg-[#112014]/60">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Input
            placeholder="Search center location (e.g. Nasr City, Cairo)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void handleSearchPlace();
              }
            }}
          />
        </div>
        <Button type="button" variant="outline" size="sm" disabled={searching} onClick={() => void handleSearchPlace()}>
          {searching ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Search className="mr-1.5 size-3.5" />}
          Locate
        </Button>
      </div>

      <div
        ref={mapContainerRef}
        className="h-60 w-full overflow-hidden rounded-xl border border-border/80 dark:border-[#223D27]"
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-[220px] flex-1 items-center gap-3">
          <Label htmlFor="circle-radius" className="shrink-0 text-xs">
            Radius: <span className="font-semibold text-foreground">{radiusKm} km</span>
          </Label>
          <input
            id="circle-radius"
            type="range"
            min={1}
            max={100}
            step={1}
            value={radiusKm}
            onChange={(e) => setRadiusKm(Number(e.target.value))}
            className="h-1.5 w-full cursor-pointer accent-emerald-500"
          />
        </div>

        <Button
          type="button"
          size="sm"
          disabled={resolving}
          onClick={() => void handleResolveCircle()}
          className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
        >
          {resolving ? (
            <Loader2 className="mr-1.5 size-3.5 animate-spin" />
          ) : (
            <Crosshair className="mr-1.5 size-3.5" />
          )}
          Add Radius Area
        </Button>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Click anywhere on the map to move the center ({center.lat.toFixed(3)}, {center.lng.toFixed(3)}). Your AI agent
        will target businesses within {radiusKm} km.
      </p>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}
    </div>
  );
}
