import { Layers, Search, Send, Target } from "lucide-react";
import { SectionContainer } from "@/components/shared/section-container";
import { SectionHeading } from "@/components/shared/section-heading";
import { AuroraText } from "@/components/ui/aurora-text";
import { MotionReveal } from "@/lib/libraries/motion";
import { cn } from "@/lib/utils";

const WORKFLOW_STEPS = [
  {
    step: "1. Define",
    icon: Target,
    colorClass: "border-emerald-500/30 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
    description: "Tell NEXUS about your business, ideal customers, and targeting criteria.",
  },
  {
    step: "2. Discover",
    icon: Search,
    colorClass: "border-sky-500/30 bg-sky-500/15 text-sky-600 dark:text-sky-400",
    description: "AI agents find relevant companies and prospects across trusted sources.",
  },
  {
    step: "3. Qualify",
    icon: Layers,
    colorClass: "border-amber-500/30 bg-amber-500/15 text-amber-600 dark:text-amber-400",
    description: "Evaluate and score prospects based on your criteria and business fit.",
  },
  {
    step: "4. Engage",
    icon: Send,
    colorClass: "border-indigo-500/30 bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
    description: "Generate personalized outreach and manage conversations in one place.",
  },
];

export function WorkflowSection() {
  return (
    <SectionContainer id="workflow" className="bg-background">
      <SectionHeading
        title={
          <>
            From business goals to qualified{" "}
            <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
              opportunities.
            </AuroraText>
          </>
        }
        description="A structured four-step AI workflow where you stay in full control of approvals and messaging."
      />

      <div className="mt-14 grid gap-8 md:grid-cols-4 md:gap-6">
        {WORKFLOW_STEPS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <MotionReveal key={item.step} delay={idx * 0.08} className="flex flex-col items-center text-center">
              <div
                className={cn(
                  "flex size-16 items-center justify-center rounded-2xl border shadow-sm transition-transform hover:scale-105",
                  item.colorClass,
                )}
              >
                <Icon className="size-7" />
              </div>
              <h3 className="mt-5 text-base font-bold text-foreground">{item.step}</h3>
              <p className="mt-2 max-w-[230px] text-sm leading-relaxed text-muted-foreground">{item.description}</p>
            </MotionReveal>
          );
        })}
      </div>
    </SectionContainer>
  );
}
