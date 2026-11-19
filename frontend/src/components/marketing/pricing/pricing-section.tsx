import Link from "next/link";
import { Check } from "lucide-react";
import { SectionContainer } from "@/components/shared/section-container";
import { SectionHeading } from "@/components/shared/section-heading";
import { AuroraText } from "@/components/ui/aurora-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { BorderBeam } from "@/components/ui/border-beam";
import { siteConfig } from "@/config/site";
import { MotionReveal } from "@/lib/libraries/motion";

const PLANS = [
  {
    name: "Starter",
    priceLabel: "Custom / TBD",
    description: "For small businesses starting AI-powered B2B discovery.",
    features: [
      "1 workspace & onboarding profile",
      "ICP Builder & lead scoring",
      "Assisted WhatsApp outreach",
      "Built-in CRM pipeline",
    ],
    highlighted: false,
  },
  {
    name: "Growth",
    priceLabel: "Custom / TBD",
    description: "For growing B2B teams scaling automated discovery and outreach.",
    features: [
      "Everything in Starter",
      "Higher daily discovery & outreach caps",
      "Approval queue + Autopilot modes",
      "AI Reply Agent & Telegram alerts",
    ],
    highlighted: true,
  },
  {
    name: "Business",
    priceLabel: "Custom / TBD",
    description: "For established sales teams with multi-region pipelines.",
    features: [
      "Everything in Growth",
      "Multi-member team access",
      "Cost & conversion analytics",
      "Priority onboarding support",
    ],
    highlighted: false,
  },
];

export function PricingSection() {
  return (
    <SectionContainer id="pricing" className="bg-background">
      <SectionHeading
        title={
          <>
            Choose the right starting point for your{" "}
            <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
              growth.
            </AuroraText>
          </>
        }
        description="Placeholder tier structure — final commercial pricing and usage quotas will be published here."
      />

      <div className="mt-12 grid gap-6 lg:grid-cols-3">
        {PLANS.map((plan, idx) => (
          <MotionReveal key={plan.name} delay={idx * 0.08}>
            <Card
              className={`relative flex h-full flex-col justify-between overflow-hidden rounded-2xl bg-card ${
                plan.highlighted
                  ? "border-transparent shadow-lg shadow-emerald-950/10"
                  : "border-border shadow-xs"
              }`}
            >
              {plan.highlighted && (
                <BorderBeam
                  duration={6}
                  size={400}
                  reverse
                  borderWidth={2}
                  colorFrom="#10B981"
                  colorTo="#84CC16"
                />
              )}
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg font-bold text-foreground">{plan.name}</CardTitle>
                  {plan.highlighted && (
                    <Badge className="border-0 bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#032219]">
                      Recommended
                    </Badge>
                  )}
                </div>
                <p className="mt-2 text-2xl font-extrabold text-foreground">{plan.priceLabel}</p>
                <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>
              </CardHeader>

              <CardContent className="space-y-3">
                {plan.features.map((feat) => (
                  <div key={feat} className="flex items-start gap-2.5 text-sm text-foreground">
                    <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span>{feat}</span>
                  </div>
                ))}
              </CardContent>

              <CardFooter>
                <Button
                  className={`w-full rounded-full font-bold ${
                    plan.highlighted
                      ? "bg-gradient-to-r from-[#10B981] to-[#84CC16] text-[#032219] transition-opacity hover:opacity-90"
                      : "bg-surface text-foreground hover:bg-surface-secondary"
                  }`}
                  render={<Link href={siteConfig.links.register}>Start Free Trial</Link>}
                />
              </CardFooter>
            </Card>
          </MotionReveal>
        ))}
      </div>
    </SectionContainer>
  );
}

