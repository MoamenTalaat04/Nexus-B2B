import { Check, X } from "lucide-react";
import { GeometricPattern } from "@/components/effects/geometric-pattern";
import { Logo } from "@/components/shared/logo";
import { SectionContainer } from "@/components/shared/section-container";
import { SectionHeading } from "@/components/shared/section-heading";
import { AuroraText } from "@/components/ui/aurora-text";
import { LiquidGlass } from "@/components/ui/liquid-glass";
import { MotionReveal } from "@/lib/libraries/motion";

const COMPARISON_POINTS = [
  "AI-powered prospect discovery",
  "Structured company & contact insights",
  "Intelligent ICP lead qualification",
  "Personalized, human-approved outreach",
  "Centralized CRM & reply management",
] as const;

export function ProblemSection() {
  return (
    <SectionContainer id="problem" className="bg-surface/60">
      <GeometricPattern variant="dots-corners" />

      <SectionHeading
        title={
          <>
            Finding customers shouldn&apos;t feel like{" "}
            <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
              searching
            </AuroraText>{" "}
            endlessly.
          </>
        }
        description="Everything you need to discover, qualify, and engage B2B prospects — compared to traditional tools."
      />

      <MotionReveal delay={0.08} className="mx-auto mt-14 max-w-4xl py-4">
        <div className="relative grid grid-cols-12 items-stretch rounded-2xl border border-border bg-card shadow-sm">
          {/* Left Column: Comparison Points */}
          <div className="col-span-6 divide-y divide-border sm:col-span-6">
            <div className="flex h-16 items-center px-5 sm:h-20 sm:px-7">
              <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
                Capabilities
              </span>
            </div>
            {COMPARISON_POINTS.map((point) => (
              <div key={point} className="flex h-16 items-center px-5 sm:px-7">
                <span className="text-xs font-semibold text-foreground sm:text-sm">{point}</span>
              </div>
            ))}
          </div>

          {/* Middle Column: Highlighted Elevated NEXUS Column with LiquidGlass */}
          <LiquidGlass
            radius={16}
            className="relative z-10 col-span-3 -my-4 border border-primary/25 shadow-xl shadow-lime-950/10 dark:border-primary/30 dark:shadow-black/40"
            contentClassName="flex h-full flex-col divide-y divide-lime-600/15 bg-lime-500/[0.08] dark:bg-lime-400/[0.08]"
          >
            <div className="flex h-20 items-center justify-center px-2 sm:h-24">
              <Logo className="scale-90 sm:scale-100" />
            </div>
            {COMPARISON_POINTS.map((point) => (
              <div key={point} className="flex h-16 items-center justify-center">
                <Check className="size-5 text-lime-700 dark:text-lime-300" strokeWidth={2.75} />
              </div>
            ))}
            <div className="h-4 border-none" />
          </LiquidGlass>

          {/* Right Column: Others */}
          <div className="col-span-3 divide-y divide-border">
            <div className="flex h-16 items-center justify-center px-2 sm:h-20">
              <span className="text-sm font-bold text-foreground sm:text-base">Others</span>
            </div>
            {COMPARISON_POINTS.map((point) => (
              <div key={point} className="flex h-16 items-center justify-center">
                <X className="size-5 text-rose-500/85 dark:text-rose-400/85" strokeWidth={2.5} />
              </div>
            ))}
          </div>
        </div>
      </MotionReveal>
    </SectionContainer>
  );
}
