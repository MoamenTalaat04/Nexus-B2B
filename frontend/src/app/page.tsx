"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoaderCircle } from "lucide-react";
import { ADMIN_ROUTES, CUSTOMER_ROUTES, isAdminRole } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";

/**
 * Root `/` dispatcher:
 * - Unauthenticated -> /landing-page
 * - Admin / Super Admin -> /admin
 * - Customer with incomplete onboarding -> /onboarding
 * - Customer with completed onboarding -> /dashboard
 */
export default function RootRedirectPage() {
  const { user, authProvider, onboardingCompleted, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated || !user) {
      router.replace("/landing-page");
      return;
    }
    if (isAdminRole(user.role)) {
      router.replace(ADMIN_ROUTES.dashboard);
      return;
    }
    if (authProvider !== "mock" && !onboardingCompleted) {
      router.replace(CUSTOMER_ROUTES.onboarding);
      return;
    }
    router.replace(CUSTOMER_ROUTES.dashboard);
  }, [isLoading, isAuthenticated, user, authProvider, onboardingCompleted, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
      <div className="flex items-center gap-2.5 text-sm font-medium">
        <LoaderCircle className="size-5 animate-spin text-primary" />
        <span>Redirecting...</span>
      </div>
    </div>
  );
}
