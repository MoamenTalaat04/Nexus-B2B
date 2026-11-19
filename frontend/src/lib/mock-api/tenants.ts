import { requireAuthenticatedUser } from "@/lib/mock-api/auth";
import { readMockDatabase } from "@/lib/mock-api/storage";
import { MockApiError, type MockTenant } from "@/lib/mock-api/types";

/**
 * Multi-tenant isolation enforcement in the mock layer:
 * Customers can ONLY access their own authenticated tenantId.
 * Requesting another tenant's ID returns 403 Forbidden.
 * NOTE: Real tenant isolation must always be enforced server-side by the backend.
 */
export async function getTenantById(requestedTenantId: string): Promise<MockTenant> {
  const user = await requireAuthenticatedUser();

  if (user.role === "tenant_owner" || user.role === "tenant_member") {
    if (!user.tenantId || user.tenantId !== requestedTenantId) {
      throw new MockApiError(
        "forbidden",
        "You do not have permission to access another workspace.",
        403,
      );
    }
  }

  const db = await readMockDatabase();
  const tenant = db.tenants.find((t) => t.id === requestedTenantId);
  if (!tenant) {
    throw new MockApiError("not_found", "Workspace not found.", 404);
  }
  return tenant;
}

/**
 * Resolves tenant-scoped data strictly from the authenticated user's session.
 */
export async function getCurrentTenantResources(): Promise<{
  tenant: MockTenant;
  memberCount: number;
}> {
  const user = await requireAuthenticatedUser();
  if (!user.tenantId) {
    throw new MockApiError("forbidden", "This action requires a customer workspace.", 403);
  }

  const db = await readMockDatabase();
  const tenant = db.tenants.find((t) => t.id === user.tenantId);
  if (!tenant) {
    throw new MockApiError("not_found", "Workspace not found.", 404);
  }

  const memberCount = db.users.filter((u) => u.tenantId === tenant.id).length;
  return { tenant, memberCount };
}

