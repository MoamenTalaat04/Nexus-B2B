import { generateMockToken, generateSalt, hashPassword, verifyPassword } from "@/lib/mock-api/crypto";
import {
  readMockDatabase,
  readMockSession,
  writeMockDatabase,
  writeMockSession,
} from "@/lib/mock-api/storage";
import {
  MockApiError,
  type AuthResponse,
  type MockSession,
  type MockTenant,
  type MockUser,
  type PublicUser,
  type RegisterCustomerInput,
} from "@/lib/mock-api/types";

export function toPublicUser(user: MockUser): PublicUser {
  const { passwordHash: _hash, passwordSalt: _salt, ...rest } = user;
  void _hash;
  void _salt;
  return rest;
}

function buildSession(user: MockUser): MockSession {
  const issuedAt = new Date();
  const expiresAt = new Date(issuedAt.getTime() + 7 * 24 * 60 * 60 * 1000);
  return {
    accessToken: generateMockToken(user.id),
    userId: user.id,
    role: user.role,
    tenantId: user.tenantId,
    issuedAt: issuedAt.toISOString(),
    expiresAt: expiresAt.toISOString(),
  };
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const normalizedEmail = email.trim().toLowerCase();
  if (!normalizedEmail || !password) {
    throw new MockApiError("validation_error", "Email and password are required.", 400);
  }

  const db = await readMockDatabase();
  const user = db.users.find((u) => u.email.toLowerCase() === normalizedEmail);
  if (!user) {
    throw new MockApiError("invalid_credentials", "Invalid email or password.", 401);
  }

  const valid = await verifyPassword(password, user.passwordSalt, user.passwordHash);
  if (!valid) {
    throw new MockApiError("invalid_credentials", "Invalid email or password.", 401);
  }

  if (!user.isActive) {
    throw new MockApiError("account_disabled", "This user account has been disabled.", 403);
  }

  let tenant: MockTenant | null = null;
  if (user.tenantId) {
    tenant = db.tenants.find((t) => t.id === user.tenantId) ?? null;
    if (!tenant) {
      throw new MockApiError("tenant_not_found", "Workspace not found for this account.", 404);
    }
    if (tenant.status === "suspended") {
      throw new MockApiError(
        "tenant_suspended",
        "Your workspace is currently suspended. Please contact support.",
        403,
      );
    }
  }

  const session = buildSession(user);
  writeMockSession(session);

  return {
    session,
    user: toPublicUser(user),
    tenant,
  };
}

/**
 * Public customer registration.
 * SECURITY RULE: Always creates a new tenant and assigns `tenant_owner` internally.
 * Public registration can NEVER create `platform_admin` or `super_admin` accounts.
 */
export async function registerCustomer(input: RegisterCustomerInput): Promise<AuthResponse> {
  const normalizedEmail = input.email.trim().toLowerCase();
  const fullName = input.fullName.trim();
  const companyName = input.companyName.trim();

  if (!normalizedEmail || !input.password || !fullName || !companyName) {
    throw new MockApiError("validation_error", "All registration fields are required.", 400);
  }
  if (input.password.length < 8) {
    throw new MockApiError("validation_error", "Password must be at least 8 characters long.", 400);
  }

  // Reject any attempt to smuggle a privileged role via untyped callers.
  const rawInput = input as unknown as Record<string, unknown>;
  if ("role" in rawInput && rawInput.role !== undefined && rawInput.role !== "tenant_owner") {
    throw new MockApiError(
      "forbidden",
      "Public registration only creates customer tenant_owner accounts.",
      403,
    );
  }

  const db = await readMockDatabase();
  if (db.users.some((u) => u.email.toLowerCase() === normalizedEmail)) {
    throw new MockApiError("email_taken", "An account with this email already exists.", 409);
  }

  const now = new Date().toISOString();
  const tenantId = `tenant_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  const userId = `usr_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;

  const newTenant: MockTenant = {
    id: tenantId,
    name: companyName,
    status: "active",
    plan: "Starter",
    createdAt: now,
  };

  const salt = generateSalt();
  const passwordHash = await hashPassword(input.password, salt);

  const newUser: MockUser = {
    id: userId,
    email: normalizedEmail,
    fullName,
    role: "tenant_owner",
    tenantId,
    passwordHash,
    passwordSalt: salt,
    isActive: true,
    createdAt: now,
  };

  writeMockDatabase({
    ...db,
    tenants: [...db.tenants, newTenant],
    users: [...db.users, newUser],
  });

  const session = buildSession(newUser);
  writeMockSession(session);

  return {
    session,
    user: toPublicUser(newUser),
    tenant: newTenant,
  };
}

export async function logout(): Promise<void> {
  writeMockSession(null);
}

export async function getCurrentSession(): Promise<MockSession | null> {
  return readMockSession();
}

export async function getCurrentUser(): Promise<PublicUser | null> {
  const session = readMockSession();
  if (!session) return null;

  const db = await readMockDatabase();
  const user = db.users.find((u) => u.id === session.userId);
  if (!user || !user.isActive) {
    writeMockSession(null);
    return null;
  }
  return toPublicUser(user);
}

export async function getCurrentTenant(): Promise<MockTenant | null> {
  const user = await getCurrentUser();
  if (!user || !user.tenantId) return null;

  const db = await readMockDatabase();
  return db.tenants.find((t) => t.id === user.tenantId) ?? null;
}

export async function requireAuthenticatedUser(): Promise<PublicUser> {
  const user = await getCurrentUser();
  if (!user) {
    throw new MockApiError("unauthorized", "Authentication required.", 401);
  }
  return user;
}

