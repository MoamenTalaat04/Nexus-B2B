import type { ReactNode } from "react";
import { RouteGuard } from "@/components/auth/route-guard";
import { AdminShell } from "@/components/layout/admin-shell";
import { ADMIN_ROLES } from "@/config/routes";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <RouteGuard allowedRoles={ADMIN_ROLES}>
      <AdminShell>{children}</AdminShell>
    </RouteGuard>
  );
}

