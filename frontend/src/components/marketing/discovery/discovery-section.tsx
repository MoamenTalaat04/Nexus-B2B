"use client";

import { AuroraText } from "@/components/ui/aurora-text";
import { DottedMap, type Marker } from "@/components/ui/dotted-map";
import { NumberTicker } from "@/components/ui/number-ticker";
import { MotionReveal } from "@/lib/libraries/motion";

const MAP_MARKERS: Marker[] = [
  { lat: 30.0444, lng: 31.2357, size: 1.2 }, // Cairo
  { lat: 51.5072, lng: -0.1276, size: 1.0 }, // London
  { lat: 40.7128, lng: -74.006, size: 1.1 }, // New York
  { lat: -23.5505, lng: -46.6333, size: 1.0 }, // Sao Paulo
  { lat: 25.2048, lng: 55.2708, size: 1.0 }, // Dubai
  { lat: 35.6762, lng: 139.6503, size: 1.1 }, // Tokyo
  { lat: -33.8688, lng: 151.2093, size: 0.95 }, // Sydney
];

const SAMPLE_METRICS = [
  { label: "Prospects Discovered", value: 8898, suffix: "+" },
  { label: "Qualified Leads", value: 2324, suffix: "+" },
  { label: "Outreach Activities", value: 6267, suffix: "+" },
  { label: "Avg. Conversion Rate", value: 17, suffix: "%" },
];

export function DiscoveryAndMetricsSection() {
  return (
    <section id="discovery" className="relative overflow-hidden bg-background py-20 md:py-28">
      {/* Subtle full-section corner emerald washes */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-24 -right-24 size-96 rounded-full bg-primary-light/60 blur-3xl dark:bg-emerald-500/10"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-24 -left-24 size-80 rounded-full bg-primary-light/50 blur-3xl dark:bg-emerald-500/10"
      />

      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <MotionReveal className="grid items-center gap-10 md:grid-cols-12 lg:gap-12">
          {/* Left Column (33% on desktop): Heading, Description & Integrated 2x2 Metrics */}
          <div className="md:col-span-5 lg:col-span-4">
            <div className="space-y-4">
              <h2 className="text-[clamp(1.9rem,3.4vw,2.75rem)] leading-[1.1] font-extrabold tracking-tight text-foreground">
                <span className="block">Your next</span>
                <span className="block">opportunity could</span>
                <span className="block">
                  be{" "}
                  <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
                    anywhere.
                  </AuroraText>
                </span>
              </h2>

              <p className="max-w-sm text-sm leading-relaxed text-muted-foreground sm:text-base">
                Discover and engage relevant businesses across target markets and regions.
              </p>
            </div>

            {/* Integrated 2x2 Typography Metrics (No card/container) */}
            <div className="mt-8 border-t border-border/60 pt-6">
              <p className="mb-4 text-[11px] font-semibold tracking-wider text-muted-foreground/80 uppercase">
                Sample Benchmark Metrics
              </p>

              <div className="grid grid-cols-2 gap-x-6 gap-y-5">
                {SAMPLE_METRICS.map((m) => (
                  <div key={m.label}>
                    <p className="text-2xl font-extrabold tracking-tight text-primary sm:text-3xl">
                      <NumberTicker value={m.value} />
                      {m.suffix}
                    </p>
                    <p className="mt-1 text-xs font-medium text-muted-foreground">{m.label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column (67% on desktop): Prominent Unobstructed Dotted World Map */}
          <div
            aria-hidden="true"
            className="pointer-events-none relative h-[240px] w-full sm:h-[320px] md:col-span-7 md:h-[380px] lg:col-span-8 lg:h-[460px]"
          >
            <DottedMap
              markers={MAP_MARKERS}
              dotColor="currentColor"
              markerColor="#84CC16"
              dotRadius={0.22}
              pulse
              className="size-full text-[#0f1f12]/75 dark:text-lime-300/50"
            />
          </div>
        </MotionReveal>
      </div>
    </section>
  );
}
