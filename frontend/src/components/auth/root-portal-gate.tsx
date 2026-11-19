"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { CustomerShell } from "@/components/layout/customer-shell";
import { ADMIN_ROUTES, isAdminRole } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";

/**
 * Handles `/` routing cleanly:
 * - Unauthenticated visitors see the public NEXUS Marketing Landing Page.
 * - Authenticated customers (`tenant_owner` / `tenant_member`) see the Customer Portal Dashboard.
 * - Authenticated platform admins (`super_admin` / `platform_admin`) are redirected to `/admin`.
 */
export function RootPortalGate({ marketingChildren }: { marketingChildren: ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated && user && isAdminRole(user.role)) {
      router.replace(ADMIN_ROUTES.dashboard);
    }
  }, [isLoading, isAuthenticated, user, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <LoaderCircle className="size-5 animate-spin text-primary" />
      </div>
    );
  }

  if (isAuthenticated && user) {
    if (isAdminRole(user.role)) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
          <LoaderCircle className="size-5 animate-spin text-primary" />
        </div>
      );
    }

    return (
      <CustomerShell>
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight text-foreground">Dashboard</h1>
        </div>
      </CustomerShell>
    );
  }

  return <>{marketingChildren}</>;
}

