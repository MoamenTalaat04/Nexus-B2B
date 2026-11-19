import { GeometricPattern } from "@/components/effects/geometric-pattern";
import { SectionContainer } from "@/components/shared/section-container";
import { SectionHeading } from "@/components/shared/section-heading";
import { AuroraText } from "@/components/ui/aurora-text";
import { Card, CardContent } from "@/components/ui/card";
import { ShineBorder } from "@/components/ui/shine-border";
import { designSystem } from "@/config/design-system";
import { MotionReveal } from "@/lib/libraries/motion";

const TESTIMONIALS = [
  {
    quote:
      "NEXUS cut our prospecting time in half and helped us focus on real B2B opportunities. (Sample story)",
    author: "Ahmed Salem",
    role: "CEO, TechWave (Placeholder)",
    initials: "AS",
    featured: false,
  },
  {
    quote:
      "The AI research and qualification are incredibly accurate. It's like having an extra sales analyst. (Sample story)",
    author: "Laila Ibrahim",
    role: "Head of Sales, Orbit Systems (Placeholder)",
    initials: "LI",
    featured: true,
  },
  {
    quote:
      "We went from scattered lists to a clear, actionable pipeline in days. (Sample story)",
    author: "Omar Nabil",
    role: "Founder, Delta Solutions (Placeholder)",
    initials: "ON",
    featured: false,
  },
];

export function TestimonialsSection() {
  return (
    <SectionContainer id="testimonials" className="bg-surface/60">
      <GeometricPattern variant="curved-lines" />

      <SectionHeading
        title={
          <>
            Built for teams that think beyond the next{" "}
            <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
              lead.
            </AuroraText>
          </>
        }
        description="Sample customer story cards — ready to be replaced with verified customer testimonials."
      />

      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {TESTIMONIALS.map((item, idx) => (
          <MotionReveal key={item.author} delay={idx * 0.08}>
            <Card
              className={`relative h-full overflow-hidden rounded-2xl border-border bg-card shadow-xs ${
                item.featured ? "border-primary/40 bg-primary-light/25 shadow-md dark:bg-surface-secondary/50" : ""
              }`}
            >
              {item.featured && <ShineBorder shineColor={[...designSystem.shineColors]} borderWidth={1.5} />}
              <CardContent className="flex h-full flex-col justify-between p-6">
                <p className="text-sm leading-relaxed text-foreground">&ldquo;{item.quote}&rdquo;</p>
                <div className="mt-6 flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-light text-xs font-bold text-emerald-dark dark:bg-surface-secondary dark:text-primary">
                    {item.initials}
                  </span>
                  <div>
                    <p className="text-sm font-bold text-foreground">{item.author}</p>
                    <p className="text-xs text-muted-foreground">{item.role}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </MotionReveal>
        ))}
      </div>
    </SectionContainer>
  );
}

