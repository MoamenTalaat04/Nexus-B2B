"use client";

import { SectionContainer } from "@/components/shared/section-container";
import { SectionHeading } from "@/components/shared/section-heading";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AuroraText } from "@/components/ui/aurora-text";
import { MotionReveal } from "@/lib/libraries/motion";

const FAQS = [
  {
    q: "What is NEXUS?",
    a: "NEXUS is an AI-powered B2B lead generation and sales development platform that helps businesses discover prospects, qualify opportunities, and manage personalized outreach in one place.",
  },
  {
    q: "How does AI-powered lead generation work?",
    a: "You describe your business and upload company materials. NEXUS builds your Ideal Customer Profile (ICP), searches for matching businesses, scores them with clear reasons, and prepares tailored outreach.",
  },
  {
    q: "How does NEXUS discover prospects?",
    a: "NEXUS uses structured business directory sources such as Google Places along with public business websites (respecting robots.txt) to gather verified business details.",
  },
  {
    q: "Can I define my ideal customer profile?",
    a: "Yes. After onboarding, NEXUS generates an editable ICP with target business types, keywords, regions, and disqualifiers that you can review and refine at any time.",
  },
  {
    q: "Does NEXUS support automated outreach?",
    a: "Yes, with flexible autonomy levels. You can approve every message manually, approve only the first touch, or enable autopilot with daily send caps and quiet hours.",
  },
  {
    q: "Which integrations are available?",
    a: "NEXUS integrates with WhatsApp Cloud API for messaging, Telegram for instant owner notifications and lead escalation, and Google Places for discovery.",
  },
  {
    q: "Is there a free trial?",
    a: "Yes, you can start a free trial with demo mode enabled so you can safely test discovery, qualification, and outreach workflows before contacting real prospects.",
  },
];

export function FaqSection() {
  return (
    <SectionContainer id="faq" className="bg-surface/60">
      <SectionHeading
        title={
          <>
            <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
              Everything
            </AuroraText>{" "}
            you need to know before getting started.
          </>
        }
        description="Answers to the most common questions about NEXUS."
      />

      <MotionReveal className="mx-auto mt-12 max-w-3xl rounded-2xl border border-border bg-card px-6 py-2 shadow-xs">
        <Accordion className="w-full">
          {FAQS.map((item, idx) => (
            <AccordionItem key={item.q} value={`faq-${idx}`}>
              <AccordionTrigger className="py-4 text-left text-sm font-semibold text-foreground hover:no-underline sm:text-base">
                {item.q}
              </AccordionTrigger>
              <AccordionContent className="pb-4 text-sm leading-relaxed text-muted-foreground">
                {item.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </MotionReveal>
    </SectionContainer>
  );
}

