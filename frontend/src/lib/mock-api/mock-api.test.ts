import { beforeEach, describe, expect, it } from "vitest";
import { canAccessRoute, getDefaultRouteForRole } from "@/config/routes";
import {
  addSandboxPaymentMethod,
  authorizePlatformGateway,
  createAdmin,
  DEMO_CREDENTIALS,
  getAdmins,
  getCurrentTenant,
  getCurrentTenantResources,
  getCurrentUser,
  getCustomerBilling,
  getCustomers,
  getPlatformBillingOverview,
  getTenantById,
  login,
  logout,
  MockApiError,
  reactivateCustomer,
  registerCustomer,
  resetMockDatabase,
  selectCustomerPlan,
  suspendCustomer,
} from "@/lib/mock-api";

describe("NEXUS Mock Auth, RBAC, and Multi-Tenant Isolation", () => {
  beforeEach(async () => {
    await resetMockDatabase();
  });

  it("authenticates all 4 seeded demo accounts and resolves correct default routes", async () => {
    const superRes = await login(DEMO_CREDENTIALS.superAdmin.email, DEMO_CREDENTIALS.superAdmin.password);
    expect(superRes.user.role).toBe("super_admin");
    expect(superRes.user.tenantId).toBeNull();
    expect(getDefaultRouteForRole(superRes.user.role)).toBe("/admin");
    await logout();

    const adminRes = await login(DEMO_CREDENTIALS.platformAdmin.email, DEMO_CREDENTIALS.platformAdmin.password);
    expect(adminRes.user.role).toBe("platform_admin");
    expect(adminRes.user.tenantId).toBeNull();
    expect(getDefaultRouteForRole(adminRes.user.role)).toBe("/admin");
    await logout();

    const cust1Res = await login(DEMO_CREDENTIALS.customer1.email, DEMO_CREDENTIALS.customer1.password);
    expect(cust1Res.user.role).toBe("tenant_owner");
    expect(cust1Res.user.tenantId).toBe("tenant_001");
    expect(getDefaultRouteForRole(cust1Res.user.role)).toBe("/dashboard");
    await logout();

    const cust2Res = await login(DEMO_CREDENTIALS.customer2.email, DEMO_CREDENTIALS.customer2.password);
    expect(cust2Res.user.role).toBe("tenant_owner");
    expect(cust2Res.user.tenantId).toBe("tenant_002");
    expect(getDefaultRouteForRole(cust2Res.user.role)).toBe("/dashboard");
  });

  it("enforces public registration as tenant_owner only and creates an isolated tenant", async () => {
    const reg = await registerCustomer({
      email: "newowner@example.com",
      password: "Password123!",
      fullName: "New Owner",
      companyName: "Nile Apparel",
    });

    expect(reg.user.role).toBe("tenant_owner");
    expect(reg.tenant?.name).toBe("Nile Apparel");
    expect(reg.user.tenantId).toBe(reg.tenant?.id);

    const currentUser = await getCurrentUser();
    const currentTenant = await getCurrentTenant();
    expect(currentUser?.id).toBe(reg.user.id);
    expect(currentTenant?.id).toBe(reg.tenant?.id);

    await expect(
      registerCustomer({
        email: "attacker@example.com",
        password: "Password123!",
        fullName: "Attacker",
        companyName: "Fake Co",
        // @ts-expect-error testing runtime rejection of privilege escalation
        role: "super_admin",
      }),
    ).rejects.toMatchObject({ status: 403 });
  });

  it("enforces Super Admin-only createAdmin and blocks Platform Admin & Customers", async () => {
    await login(DEMO_CREDENTIALS.platformAdmin.email, DEMO_CREDENTIALS.platformAdmin.password);
    await expect(
      createAdmin({ email: "newadmin@nexus.local", password: "Password123!", fullName: "Blocked Admin" }),
    ).rejects.toMatchObject({ status: 403 });
    await expect(getAdmins()).rejects.toMatchObject({ status: 403 });
    await logout();

    await login(DEMO_CREDENTIALS.superAdmin.email, DEMO_CREDENTIALS.superAdmin.password);
    const created = await createAdmin({
      email: "opsadmin@nexus.local",
      password: "Password123!",
      fullName: "Ops Admin",
    });
    expect(created.role).toBe("platform_admin");
    expect(created.tenantId).toBeNull();

    await expect(
      createAdmin({
        email: "another-super@nexus.local",
        password: "Password123!",
        fullName: "Second Super",
        role: "super_admin",
      }),
    ).rejects.toMatchObject({ status: 403 });

    await logout();
    const newAdminLogin = await login("opsadmin@nexus.local", "Password123!");
    expect(newAdminLogin.user.role).toBe("platform_admin");
  });

  it("enforces multi-tenant isolation between Customer 1 and Customer 2", async () => {
    await login(DEMO_CREDENTIALS.customer1.email, DEMO_CREDENTIALS.customer1.password);
    const own = await getCurrentTenantResources();
    expect(own.tenant.id).toBe("tenant_001");
    await expect(getTenantById("tenant_002")).rejects.toBeInstanceOf(MockApiError);
    await expect(getTenantById("tenant_002")).rejects.toMatchObject({ status: 403 });
    await expect(getCustomers()).rejects.toMatchObject({ status: 403 });
    await logout();

    await login(DEMO_CREDENTIALS.customer2.email, DEMO_CREDENTIALS.customer2.password);
    const own2 = await getCurrentTenantResources();
    expect(own2.tenant.id).toBe("tenant_002");
    await expect(getTenantById("tenant_001")).rejects.toMatchObject({ status: 403 });
  });

  it("supports suspending and reactivating customer workspaces", async () => {
    await login(DEMO_CREDENTIALS.platformAdmin.email, DEMO_CREDENTIALS.platformAdmin.password);
    const suspended = await suspendCustomer("tenant_001");
    expect(suspended.status).toBe("suspended");
    await logout();

    await expect(
      login(DEMO_CREDENTIALS.customer1.email, DEMO_CREDENTIALS.customer1.password),
    ).rejects.toMatchObject({ status: 403 });

    await login(DEMO_CREDENTIALS.platformAdmin.email, DEMO_CREDENTIALS.platformAdmin.password);
    const active = await reactivateCustomer("tenant_001");
    expect(active.status).toBe("active");
    await logout();

    const cust1 = await login(DEMO_CREDENTIALS.customer1.email, DEMO_CREDENTIALS.customer1.password);
    expect(cust1.tenant?.status).toBe("active");
  });

  it("validates route permission helpers for all roles", () => {
    expect(canAccessRoute("super_admin", "/admin/admins")).toBe(true);
    expect(canAccessRoute("super_admin", "/admin/billing")).toBe(true);
    expect(canAccessRoute("platform_admin", "/admin/admins")).toBe(false);
    expect(canAccessRoute("platform_admin", "/admin/billing")).toBe(false);
    expect(canAccessRoute("platform_admin", "/admin/customers")).toBe(true);
    expect(canAccessRoute("platform_admin", "/leads")).toBe(false);
    expect(canAccessRoute("tenant_owner", "/leads")).toBe(true);
    expect(canAccessRoute("tenant_owner", "/admin")).toBe(false);
    expect(canAccessRoute("tenant_owner", "/admin/billing")).toBe(false);
  });

  it("enforces Super Admin-only platform billing & gateway authorization and sandbox customer billing", async () => {
    await login(DEMO_CREDENTIALS.platformAdmin.email, DEMO_CREDENTIALS.platformAdmin.password);
    await expect(getPlatformBillingOverview()).rejects.toMatchObject({ status: 403 });
    await expect(
      authorizePlatformGateway({ gatewayId: "fawry", sandboxAccountLabel: "test", connect: true }),
    ).rejects.toMatchObject({ status: 403 });
    await logout();

    await login(DEMO_CREDENTIALS.superAdmin.email, DEMO_CREDENTIALS.superAdmin.password);
    const overview = await getPlatformBillingOverview();
    expect(overview.gateways.length).toBeGreaterThanOrEqual(5);
    const updatedGateways = await authorizePlatformGateway({
      gatewayId: "fawry",
      sandboxAccountLabel: "fawry_sb_01",
      connect: true,
    });
    expect(updatedGateways.find((g) => g.id === "fawry")?.connected).toBe(true);
    await logout();

    await login(DEMO_CREDENTIALS.customer1.email, DEMO_CREDENTIALS.customer1.password);
    await expect(getPlatformBillingOverview()).rejects.toMatchObject({ status: 403 });
    const pmRes = await addSandboxPaymentMethod({
      gateway: "stripe",
      label: "Stripe (Sandbox)",
      details: "•••• 4242",
    });
    expect(pmRes.paymentMethods).toHaveLength(1);
    const planRes = await selectCustomerPlan({
      planId: "growth",
      planName: "Growth",
      channel: "omnichannel",
      cycle: "monthly",
      amountUsd: 99,
    });
    expect(planRes.invoices).toHaveLength(1);
    const fetched = await getCustomerBilling();
    expect(fetched.activePlanId).toBe("growth");
  });
});

