import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AuroraText } from "@/components/ui/aurora-text";
import { Button } from "@/components/ui/button";
import { GridPattern } from "@/components/ui/grid-pattern";
import { siteConfig } from "@/config/site";
import { MotionReveal } from "@/lib/libraries/motion";

export function FinalCtaSection() {
  return (
    <section id="cta" className="bg-background py-16 md:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <MotionReveal>
          <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-primary-light/55 px-6 py-12 text-foreground shadow-lg shadow-lime-950/10 sm:px-12 md:py-16 dark:border-lime-500/20 dark:bg-[#0A140C] dark:text-white dark:shadow-xl dark:shadow-black/30">
            <GridPattern
              width={48}
              height={48}
              className="fill-lime-600/[0.03] stroke-lime-600/[0.08] [mask-image:radial-gradient(ellipse_at_center,white,transparent_85%)] dark:fill-lime-400/[0.02] dark:stroke-lime-300/[0.05]"
            />
            <div className="relative z-10 flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
              <div className="max-w-xl space-y-3">
                <h2 className="text-[clamp(1.75rem,3.2vw,2.5rem)] leading-tight font-extrabold tracking-tight text-foreground dark:text-white">
                  Your next customers are{" "}
                  <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
                    waiting.
                  </AuroraText>
                </h2>
                <p className="text-sm leading-relaxed text-muted-foreground sm:text-base dark:text-lime-100/85">
                  Start building smarter connections with AI-powered prospect discovery and automated workflows.
                </p>
              </div>
              <Button
                size="lg"
                className="h-12 shrink-0 rounded-full bg-[#0A140C] px-7 text-sm font-bold text-white shadow-lg transition-colors hover:bg-[#112014] dark:bg-gradient-to-r dark:from-[#10B981] dark:to-[#84CC16] dark:text-[#0A140C] dark:hover:opacity-90"
                render={
                  <Link href={siteConfig.links.register}>
                    Start Free Trial
                    <ArrowRight className="ml-1.5 size-4" />
                  </Link>
                }
              />
            </div>
          </div>
        </MotionReveal>
      </div>
    </section>
  );
}

