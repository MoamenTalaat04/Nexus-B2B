import { RouteGuard } from "@/components/auth/route-guard";

export default function AdminAdminsPage() {
  return (
    <RouteGuard allowedRoles={["super_admin"]}>
      <div className="space-y-1">
        <h1 className="text-xl font-bold tracking-tight text-foreground">Admin Management</h1>
      </div>
    </RouteGuard>
  );
}

