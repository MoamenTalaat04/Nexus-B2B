"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { RouteGuard } from "@/components/auth/route-guard";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { Button } from "@/components/ui/button";
import { SmokeShaderBackground } from "@/components/ui/smoke-shader-background";
import { AUTH_ROUTES, CUSTOMER_ROLES } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import { OnboardingWizard } from "@/features/onboarding/components/onboarding-wizard";

function OnboardingShell() {
  const { logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.replace(AUTH_ROUTES.login);
  }

  return (
    <div className="relative flex min-h-svh flex-col items-center justify-center overflow-hidden bg-background px-4 py-12 text-foreground">
      <SmokeShaderBackground />

      <div className="fixed top-4 right-4 z-30 flex items-center gap-1 rounded-full border border-border/80 bg-card/85 p-1 shadow-sm backdrop-blur-md dark:border-[#223D27] dark:bg-[#112014]/85">
        <ThemeToggle />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 rounded-full px-3 text-xs font-medium"
          onClick={() => void handleLogout()}
        >
          <LogOut className="mr-1.5 size-3.5" />
          Log out
        </Button>
      </div>

      <main className="relative z-10 w-full max-w-4xl">
        <OnboardingWizard />
      </main>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <RouteGuard allowedRoles={CUSTOMER_ROLES}>
      <OnboardingShell />
    </RouteGuard>
  );
}
