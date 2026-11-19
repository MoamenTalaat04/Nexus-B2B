import Link from "next/link";
import { CheckCircle2, Search, ShieldCheck, Sparkles } from "lucide-react";
import { BrowserDemo } from "@/components/effects/browser-demo";
import { HeroTypingHeadline } from "@/components/marketing/hero/hero-typing-headline";
import { ShapeDivider } from "@/components/shared/shape-divider";
import { Button } from "@/components/ui/button";
import { SmokeShaderBackground } from "@/components/ui/smoke-shader-background";
import { siteConfig } from "@/config/site";
import { MotionReveal } from "@/lib/libraries/motion";

const HERO_FEATURES = [
  { icon: Search, label: "Discover prospects" },
  { icon: Sparkles, label: "AI qualification" },
  { icon: ShieldCheck, label: "Human-approved outreach" },
  { icon: CheckCircle2, label: "Manage relationships" },
];

export function HeroSection() {
  return (
    <section className="relative overflow-hidden text-foreground dark:text-white">
      <SmokeShaderBackground />

      <div className="relative z-10 mx-auto max-w-6xl px-4 pt-32 pb-16 sm:px-6 md:pt-40 md:pb-24 lg:px-8">
        {/* Centered Header Content */}
        <MotionReveal className="mx-auto flex max-w-4xl flex-col items-center text-center">
          <HeroTypingHeadline />

          <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base dark:text-lime-100/75">
            NEXUS helps businesses discover relevant prospects, research their businesses, qualify opportunities, and
            automate personalized outreach — all in one intelligent platform.
          </p>

          {/* Single Centered CTA Button */}
          <div className="mt-7 flex items-center justify-center">
            <Button
              size="lg"
              className="h-11 rounded-full bg-[#0A140C] px-7 text-sm font-bold text-white shadow-lg shadow-lime-950/20 transition-colors hover:bg-[#112014] dark:bg-white dark:text-[#0A140C] dark:shadow-black/40 dark:hover:bg-lime-50"
              render={<Link href={siteConfig.links.register}>Start Free Trial</Link>}
            />
          </div>

          {/* Feature Icons Row */}
          <div className="mt-7 flex flex-wrap items-center justify-center gap-x-7 gap-y-3 text-xs font-medium text-foreground/80 sm:text-sm dark:text-lime-100/80">
            {HERO_FEATURES.map((item) => {
              const Icon = item.icon;
              return (
                <span key={item.label} className="inline-flex items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-full border border-lime-600/25 bg-lime-500/10 text-lime-700 dark:border-lime-400/30 dark:bg-lime-500/15 dark:text-lime-300">
                    <Icon className="size-3.5" />
                  </span>
                  {item.label}
                </span>
              );
            })}
          </div>
        </MotionReveal>

        {/* Centered Browser Video Mockup */}
        <MotionReveal delay={0.14} className="mx-auto mt-12 max-w-5xl">
          <BrowserDemo />
        </MotionReveal>
      </div>

      {/* Organic Flowing SVG Divider */}
      <ShapeDivider variant="hero-wave" />
    </section>
  );
}
