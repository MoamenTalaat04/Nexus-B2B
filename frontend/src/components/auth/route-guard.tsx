"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";
import { LoaderCircle, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AUTH_ROUTES, CUSTOMER_ROUTES, getDefaultRouteForRole, isCustomerRole } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import type { UserRole } from "@/lib/mock-api";

interface RouteGuardProps {
  allowedRoles: UserRole[];
  children: ReactNode;
}

function RouteGuardInner({ allowedRoles, children }: RouteGuardProps) {
  const { user, authProvider, onboardingCompleted, isLoading, isAuthenticated } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const mustCompleteOnboarding =
    Boolean(user) &&
    isCustomerRole(user!.role) &&
    authProvider !== "mock" &&
    !onboardingCompleted;

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      const nextParam = pathname ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`${AUTH_ROUTES.login}${nextParam}`);
      return;
    }
    if (mustCompleteOnboarding && pathname !== CUSTOMER_ROUTES.onboarding) {
      router.replace(CUSTOMER_ROUTES.onboarding);
    }
  }, [isLoading, isAuthenticated, mustCompleteOnboarding, pathname, router]);

  if (
    isLoading ||
    !isAuthenticated ||
    !user ||
    (mustCompleteOnboarding && pathname !== CUSTOMER_ROUTES.onboarding)
  ) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div className="flex items-center gap-2.5 text-sm font-medium">
          <LoaderCircle className="size-4 animate-spin text-primary" />
          <span>Loading workspace...</span>
        </div>
      </div>
    );
  }

  if (!allowedRoles.includes(user.role)) {
    const fallbackRoute = getDefaultRouteForRole(user.role);
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <ShieldAlert className="size-6" />
          </div>
          <h1 className="text-lg font-bold text-foreground">Access Denied (403)</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your account role (<code className="font-semibold text-foreground">{user.role}</code>) does not have
            permission to view this page.
          </p>
          <div className="mt-6 flex justify-center">
            <Button render={<Link href={fallbackRoute}>Return to your portal</Link>} />
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function RouteGuard(props: RouteGuardProps) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin text-primary" />
        </div>
      }
    >
      <RouteGuardInner {...props} />
    </Suspense>
  );
}
