import { requireAuthenticatedUser, toPublicUser } from "@/lib/mock-api/auth";
import { generateSalt, hashPassword } from "@/lib/mock-api/crypto";
import { readMockDatabase, writeMockDatabase } from "@/lib/mock-api/storage";
import {
  MockApiError,
  type CreateAdminInput,
  type MockTenant,
  type MockUser,
  type PublicUser,
} from "@/lib/mock-api/types";

async function requirePlatformAdmin(): Promise<PublicUser> {
  const user = await requireAuthenticatedUser();
  if (user.role !== "super_admin" && user.role !== "platform_admin") {
    throw new MockApiError("forbidden", "Platform administrator access required.", 403);
  }
  return user;
}

async function requireSuperAdmin(): Promise<PublicUser> {
  const user = await requireAuthenticatedUser();
  if (user.role !== "super_admin") {
    throw new MockApiError("forbidden", "Super Admin privileges required.", 403);
  }
  return user;
}

/**
 * Super Admin-only: create a new `platform_admin` account.
 * Rejects non-super_admin callers with 403, rejects duplicate emails with 409,
 * and rejects any attempt to create a `super_admin`.
 */
export async function createAdmin(input: CreateAdminInput): Promise<PublicUser> {
  await requireSuperAdmin();

  if (input.role === "super_admin") {
    throw new MockApiError("forbidden", "Cannot create another super_admin account.", 403);
  }

  const normalizedEmail = input.email.trim().toLowerCase();
  const fullName = input.fullName.trim();
  if (!normalizedEmail || !input.password || !fullName) {
    throw new MockApiError("validation_error", "Email, full name, and password are required.", 400);
  }
  if (input.password.length < 8) {
    throw new MockApiError("validation_error", "Password must be at least 8 characters long.", 400);
  }

  const db = await readMockDatabase();
  if (db.users.some((u) => u.email.toLowerCase() === normalizedEmail)) {
    throw new MockApiError("email_taken", "An account with this email already exists.", 409);
  }

  const salt = generateSalt();
  const passwordHash = await hashPassword(input.password, salt);

  const newAdmin: MockUser = {
    id: `usr_admin_${Date.now().toString(36)}`,
    email: normalizedEmail,
    fullName,
    role: "platform_admin",
    tenantId: null,
    passwordHash,
    passwordSalt: salt,
    isActive: true,
    createdAt: new Date().toISOString(),
  };

  writeMockDatabase({
    ...db,
    users: [...db.users, newAdmin],
  });

  return toPublicUser(newAdmin);
}

export async function getAdmins(): Promise<PublicUser[]> {
  await requireSuperAdmin();
  const db = await readMockDatabase();
  return db.users
    .filter((u) => u.role === "super_admin" || u.role === "platform_admin")
    .map(toPublicUser);
}

export async function getCustomers(): Promise<Array<{ tenant: MockTenant; owner: PublicUser | null }>> {
  await requirePlatformAdmin();
  const db = await readMockDatabase();
  return db.tenants.map((tenant) => {
    const owner = db.users.find((u) => u.tenantId === tenant.id && u.role === "tenant_owner") ?? null;
    return {
      tenant,
      owner: owner ? toPublicUser(owner) : null,
    };
  });
}

export async function getCustomerById(
  tenantId: string,
): Promise<{ tenant: MockTenant; users: PublicUser[] }> {
  await requirePlatformAdmin();
  const db = await readMockDatabase();
  const tenant = db.tenants.find((t) => t.id === tenantId);
  if (!tenant) {
    throw new MockApiError("not_found", "Customer workspace not found.", 404);
  }
  const users = db.users.filter((u) => u.tenantId === tenantId).map(toPublicUser);
  return { tenant, users };
}

export async function suspendCustomer(tenantId: string): Promise<MockTenant> {
  await requirePlatformAdmin();
  const db = await readMockDatabase();
  const idx = db.tenants.findIndex((t) => t.id === tenantId);
  if (idx === -1) {
    throw new MockApiError("not_found", "Customer workspace not found.", 404);
  }
  const updated: MockTenant = { ...db.tenants[idx], status: "suspended" };
  const tenants = [...db.tenants];
  tenants[idx] = updated;
  writeMockDatabase({ ...db, tenants });
  return updated;
}

export async function reactivateCustomer(tenantId: string): Promise<MockTenant> {
  await requirePlatformAdmin();
  const db = await readMockDatabase();
  const idx = db.tenants.findIndex((t) => t.id === tenantId);
  if (idx === -1) {
    throw new MockApiError("not_found", "Customer workspace not found.", 404);
  }
  const updated: MockTenant = { ...db.tenants[idx], status: "active" };
  const tenants = [...db.tenants];
  tenants[idx] = updated;
  writeMockDatabase({ ...db, tenants });
  return updated;
}

