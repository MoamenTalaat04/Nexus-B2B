import type { ReactNode } from "react";
import { RootPortalGate } from "@/components/auth/root-portal-gate";
import { FloatingNavbar } from "@/components/layout/floating-navbar";
import { Footer } from "@/components/layout/footer";
import { Pointer } from "@/components/ui/pointer";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <RootPortalGate
      marketingChildren={
        <div className="relative flex min-h-screen flex-col bg-background text-foreground">
          <Pointer className="fill-[#073F30] stroke-emerald-200/80 text-[#073F30]" />
          <FloatingNavbar />
          <main className="flex-1">{children}</main>
          <Footer />
        </div>
      }
    />
  );
}
