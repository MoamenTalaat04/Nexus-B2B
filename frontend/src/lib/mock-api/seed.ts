import { generateSalt, hashPassword } from "@/lib/mock-api/crypto";
import type { MockDatabase, MockTenant, MockUser } from "@/lib/mock-api/types";

export const DEMO_CREDENTIALS = {
  superAdmin: { email: "superadmin@nexus.local", password: "SuperAdmin123!" },
  platformAdmin: { email: "admin@nexus.local", password: "Admin123!" },
  customer1: { email: "customer1@nexus.local", password: "Customer123!" },
  customer2: { email: "customer2@nexus.local", password: "Customer123!" },
} as const;

export async function createInitialMockDatabase(): Promise<MockDatabase> {
  const now = new Date().toISOString();

  const tenants: MockTenant[] = [
    {
      id: "tenant_001",
      name: "Cairo Kids Apparel",
      status: "active",
      plan: "Growth",
      createdAt: now,
    },
    {
      id: "tenant_002",
      name: "Delta Industrial Supply",
      status: "active",
      plan: "Starter",
      createdAt: now,
    },
  ];

  const seedAccounts: Array<{
    id: string;
    email: string;
    password: string;
    fullName: string;
    role: MockUser["role"];
    tenantId: string | null;
  }> = [
    {
      id: "usr_super_001",
      email: DEMO_CREDENTIALS.superAdmin.email,
      password: DEMO_CREDENTIALS.superAdmin.password,
      fullName: "NEXUS Super Admin",
      role: "super_admin",
      tenantId: null,
    },
    {
      id: "usr_admin_001",
      email: DEMO_CREDENTIALS.platformAdmin.email,
      password: DEMO_CREDENTIALS.platformAdmin.password,
      fullName: "NEXUS Platform Admin",
      role: "platform_admin",
      tenantId: null,
    },
    {
      id: "usr_cust_001",
      email: DEMO_CREDENTIALS.customer1.email,
      password: DEMO_CREDENTIALS.customer1.password,
      fullName: "Ahmed Hassan",
      role: "tenant_owner",
      tenantId: "tenant_001",
    },
    {
      id: "usr_cust_002",
      email: DEMO_CREDENTIALS.customer2.email,
      password: DEMO_CREDENTIALS.customer2.password,
      fullName: "Mona El-Sayed",
      role: "tenant_owner",
      tenantId: "tenant_002",
    },
  ];

  const users: MockUser[] = await Promise.all(
    seedAccounts.map(async (acc) => {
      const salt = generateSalt();
      const passwordHash = await hashPassword(acc.password, salt);
      return {
        id: acc.id,
        email: acc.email.toLowerCase(),
        fullName: acc.fullName,
        role: acc.role,
        tenantId: acc.tenantId,
        passwordHash,
        passwordSalt: salt,
        isActive: true,
        createdAt: now,
      };
    }),
  );

  return {
    version: 1,
    tenants,
    users,
  };
}

