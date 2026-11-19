import { FinalCtaSection } from "@/components/marketing/cta/final-cta-section";
import { DiscoveryAndMetricsSection } from "@/components/marketing/discovery/discovery-section";
import { FaqSection } from "@/components/marketing/faq/faq-section";
import { HeroSection } from "@/components/marketing/hero/hero-section";
import { IntegrationsSection } from "@/components/marketing/integrations/integrations-section";
import { PlatformSection } from "@/components/marketing/platform/platform-section";
import { PricingSection } from "@/components/marketing/pricing/pricing-section";
import { ProblemSection } from "@/components/marketing/problem/problem-section";
import { TestimonialsSection } from "@/components/marketing/testimonials/testimonials-section";
import { TrustStripSection } from "@/components/marketing/trust/trust-strip-section";
import { WorkflowSection } from "@/components/marketing/workflow/workflow-section";

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <TrustStripSection />
      <ProblemSection />
      <WorkflowSection />
      <PlatformSection />
      <DiscoveryAndMetricsSection />
      <IntegrationsSection />
      <TestimonialsSection />
      <PricingSection />
      <FaqSection />
      <FinalCtaSection />
    </>
  );
}

