import type { ReactNode } from "react";
import { RouteGuard } from "@/components/auth/route-guard";
import { CustomerShell } from "@/components/layout/customer-shell";
import { CUSTOMER_ROLES } from "@/config/routes";

export default function ApplicationLayout({ children }: { children: ReactNode }) {
  return (
    <RouteGuard allowedRoles={CUSTOMER_ROLES}>
      <CustomerShell>{children}</CustomerShell>
    </RouteGuard>
  );
}

