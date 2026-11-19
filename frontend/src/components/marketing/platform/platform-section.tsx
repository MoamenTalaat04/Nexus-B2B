"use client";

import { useState } from "react";
import { BarChart3, ChevronLeft, ChevronRight, LayoutDashboard, MessageSquare, Search, TrendingUp, Users } from "lucide-react";
import { AuroraText } from "@/components/ui/aurora-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GridPattern } from "@/components/ui/grid-pattern";
import { LiquidGlass } from "@/components/ui/liquid-glass";
import { Safari } from "@/components/ui/safari";
import { MotionReveal } from "@/lib/libraries/motion";

const SLIDES = [
  {
    id: "pipeline",
    title: "Pipeline Management",
    subtitle: "Track every qualified lead from first touch to closed deal.",
    icon: Users,
    kpis: [
      { label: "Active Leads", value: "64", delta: "+18%" },
      { label: "Qualified", value: "32", delta: "+22%" },
      { label: "In Outreach", value: "24", delta: "+14%" },
      { label: "Won Deals", value: "8", delta: "+5.2pp" },
    ],
    columns: [
      { name: "New (32)", items: ["TechWave Solutions", "Rivermind Systems"] },
      { name: "Contacted (24)", items: ["Delta Logistics", "Orbit Manufacturing"] },
      { name: "In Progress (8)", items: ["ComTech Group", "Nile Apparel"] },
    ],
  },
  {
    id: "outreach",
    title: "Approval Queue & Outreach",
    subtitle: "Review AI-personalized messages before sending via WhatsApp.",
    icon: MessageSquare,
    kpis: [
      { label: "Pending Review", value: "6", delta: "Ready" },
      { label: "Queued", value: "12", delta: "Cap 20/d" },
      { label: "Replied", value: "9", delta: "+38%" },
      { label: "Escalated", value: "3", delta: "Hot" },
    ],
    columns: [
      { name: "Pending Approval (6)", items: ["Kids Zone Cairo", "Mini Star Baby"] },
      { name: "Queued (12)", items: ["Alpha Industrial", "Nile Tech Co."] },
      { name: "Replied (9)", items: ["Coco Kids Boutique", "Pearl Medical"] },
    ],
  },
  {
    id: "analytics",
    title: "Agent Activity & Cost Analytics",
    subtitle: "Full trace of every AI run, token count, and conversion rate.",
    icon: BarChart3,
    kpis: [
      { label: "AI Runs", value: "12,840", delta: "+18%" },
      { label: "Tokens Used", value: "8.4M", delta: "+22%" },
      { label: "Conversion Rate", value: "24.6%", delta: "+5.2pp" },
      { label: "Estimated Cost", value: "$148.20", delta: "-12%" },
    ],
    columns: [
      { name: "Sourcing Runs", items: ["Batch #12 · Succeeded", "Batch #11 · Succeeded"] },
      { name: "Reply Agent", items: ["Intent: Interested", "Intent: Wants Offer"] },
      { name: "Outcomes", items: ["Won · 28,500 EGP", "Won · 42,000 EGP"] },
    ],
  },
];

export function PlatformSection() {
  const [index, setIndex] = useState(0);
  const active = SLIDES[index];
  const ActiveIcon = active.icon;

  const prev = () => setIndex((i) => (i - 1 + SLIDES.length) % SLIDES.length);
  const next = () => setIndex((i) => (i + 1) % SLIDES.length);

  return (
    <section
      id="platform"
      className="relative overflow-hidden bg-surface/60 py-20 text-foreground md:py-28 dark:bg-[#0A140C] dark:text-white"
    >
      {/* Derived forest-lime atmospheric glows */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 -left-32 h-[420px] w-[420px] rounded-full bg-lime-400/15 blur-[120px] dark:bg-lime-500/15"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-32 -bottom-32 h-[440px] w-[440px] rounded-full bg-emerald-300/15 blur-[130px] dark:bg-emerald-500/12"
      />
      <GridPattern
        width={48}
        height={48}
        className="fill-lime-600/[0.025] stroke-lime-600/[0.06] [mask-image:radial-gradient(ellipse_at_center,white,transparent_80%)] dark:fill-lime-400/[0.025] dark:stroke-lime-300/[0.06]"
      />

      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid items-center gap-10 lg:grid-cols-12">
          {/* Left Column: Heading */}
          <MotionReveal className="space-y-4 lg:col-span-4">
            <h2 className="text-[clamp(1.85rem,3vw,2.6rem)] leading-[1.15] font-bold tracking-tight text-foreground dark:text-white">
              <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
                Everything
              </AuroraText>{" "}
              you need to build your next customer pipeline.
            </h2>
            <p className="text-base leading-relaxed text-muted-foreground dark:text-lime-100/75">
              A complete workspace for discovery, research, outreach, and deal management.
            </p>
          </MotionReveal>

          {/* Right Column: Theme-Aware Browser + Floating LiquidGlass Card */}
          <MotionReveal delay={0.1} className="lg:col-span-8">
            <div className="relative flex items-center gap-2 sm:gap-4">
              <Button
                variant="outline"
                size="icon"
                onClick={prev}
                aria-label="Previous platform view"
                className="shrink-0 rounded-full border-border bg-card/85 text-foreground backdrop-blur-md hover:bg-surface dark:border-lime-400/25 dark:bg-[#112014]/80 dark:text-lime-100 dark:hover:bg-[#192E1D] dark:hover:text-white"
              >
                <ChevronLeft className="size-4" />
              </Button>

              <div className="relative w-full">
                {/* Browser Frame */}
                <div className="relative w-full overflow-hidden rounded-2xl border border-border/80 bg-card shadow-xl shadow-lime-950/10 dark:border-lime-400/20 dark:bg-[#0D1A10] dark:shadow-2xl dark:shadow-black/60">
                  <Safari url={`app.nexus.ai/${active.id}`} mode="simple" className="pointer-events-none relative z-10 w-full" />

                  <div className="absolute inset-x-0 top-[6.9%] bottom-0 z-20 flex overflow-hidden rounded-b-2xl bg-background text-foreground dark:bg-[#0D1A10] dark:text-lime-50">
                    {/* Mini Sidebar */}
                    <aside className="hidden w-36 shrink-0 border-r border-border bg-surface/80 p-3 sm:block dark:border-lime-500/15 dark:bg-[#0A140C]">
                      <div className="mb-3 flex items-center gap-1.5 text-xs font-bold text-foreground dark:text-white">
                        <span className="flex size-5 items-center justify-center rounded bg-gradient-to-br from-[#10B981] to-[#84CC16] text-[10px] font-extrabold text-[#0A140C]">
                          N
                        </span>
                        NEXUS
                      </div>
                      <div className="space-y-1 text-[11px] text-muted-foreground dark:text-lime-200/65">
                        <div className="flex items-center gap-2 rounded px-2 py-1">
                          <LayoutDashboard className="size-3.5" /> Overview
                        </div>
                        <div className="flex items-center gap-2 rounded px-2 py-1">
                          <Search className="size-3.5" /> Discover
                        </div>
                        <div className="flex items-center gap-2 rounded px-2 py-1">
                          <MessageSquare className="size-3.5" /> Outreach
                        </div>
                        <div className="flex items-center gap-2 rounded bg-primary/10 px-2 py-1 font-semibold text-primary dark:bg-lime-500/15 dark:text-lime-300">
                          <Users className="size-3.5" /> {active.id === "analytics" ? "Analytics" : "Pipeline"}
                        </div>
                        <div className="flex items-center gap-2 rounded px-2 py-1">
                          <TrendingUp className="size-3.5" /> Reports
                        </div>
                      </div>
                    </aside>

                    {/* Main Mock Screen Content */}
                    <div className="flex-1 p-3 sm:p-5">
                      <div className="mb-3 flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-foreground sm:text-sm dark:text-white">{active.title}</p>
                          <p className="hidden text-[10px] text-muted-foreground sm:block dark:text-lime-200/60">{active.subtitle}</p>
                        </div>
                        <Badge className="border border-primary/25 bg-primary-light text-[10px] text-emerald-dark dark:border-lime-400/25 dark:bg-lime-500/15 dark:text-lime-300">
                          Live Preview
                        </Badge>
                      </div>

                      {/* KPI Mini Row */}
                      <div className="mb-3 grid grid-cols-4 gap-2">
                        {active.kpis.map((kpi) => (
                          <div
                            key={kpi.label}
                            className="rounded-lg border border-border bg-surface/70 p-2 dark:border-lime-500/15 dark:bg-[#112014]"
                          >
                            <p className="truncate text-[9px] text-muted-foreground dark:text-lime-200/60">{kpi.label}</p>
                            <p className="mt-0.5 text-xs font-bold text-foreground sm:text-sm dark:text-white">{kpi.value}</p>
                            <p className="text-[9px] font-semibold text-primary dark:text-lime-400">{kpi.delta}</p>
                          </div>
                        ))}
                      </div>

                      {/* Columns */}
                      <div className="grid grid-cols-3 gap-2 sm:gap-3">
                        {active.columns.map((col) => (
                          <div
                            key={col.name}
                            className="rounded-lg border border-border bg-surface/50 p-2 sm:p-2.5 dark:border-lime-500/15 dark:bg-[#0E1A11]"
                          >
                            <p className="mb-2 truncate text-[10px] font-bold text-foreground sm:text-[11px] dark:text-lime-200">
                              {col.name}
                            </p>
                            <div className="space-y-1.5">
                              {col.items.map((card) => (
                                <div
                                  key={card}
                                  className="truncate rounded-md border border-border bg-card p-2 text-[10px] font-medium text-foreground dark:border-lime-500/15 dark:bg-[#152618] dark:text-lime-50"
                                >
                                  {card}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Floating LiquidGlass Card hovering over bottom-left of Browser Mockup */}
                <div className="mt-4 md:absolute md:-bottom-5 md:-left-6 md:z-30 md:mt-0 md:w-[340px]">
                  <LiquidGlass
                    radius={16}
                    className="border border-border/70 bg-white/75 shadow-xl shadow-lime-950/10 dark:border-lime-300/20 dark:bg-[#112014]/75 dark:shadow-2xl dark:shadow-black/60"
                    contentClassName="p-4"
                  >
                    <div className="flex items-start gap-3.5">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary-light text-primary dark:bg-lime-500/20 dark:text-lime-300">
                        <ActiveIcon className="size-5" />
                      </span>
                      <div>
                        <p className="text-sm font-bold text-foreground dark:text-white">{active.title}</p>
                        <p className="mt-1 text-xs leading-relaxed text-muted-foreground dark:text-lime-100/75">{active.subtitle}</p>
                      </div>
                    </div>
                  </LiquidGlass>
                </div>
              </div>

              <Button
                variant="outline"
                size="icon"
                onClick={next}
                aria-label="Next platform view"
                className="shrink-0 rounded-full border-border bg-card/85 text-foreground backdrop-blur-md hover:bg-surface dark:border-lime-400/25 dark:bg-[#112014]/80 dark:text-lime-100 dark:hover:bg-[#192E1D] dark:hover:text-white"
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>

            {/* Pagination Dots */}
            <div className="mt-8 flex justify-center gap-2">
              {SLIDES.map((s, idx) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setIndex(idx)}
                  aria-label={`View ${s.title}`}
                  className={`h-2 rounded-full transition-all ${
                    idx === index
                      ? "w-6 bg-primary dark:bg-lime-400"
                      : "w-2 bg-border hover:bg-primary/40 dark:bg-[#223D27] dark:hover:bg-lime-500/60"
                  }`}
                />
              ))}
            </div>
          </MotionReveal>
        </div>
      </div>
    </section>
  );
}
