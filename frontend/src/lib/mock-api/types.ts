export type UserRole = "super_admin" | "platform_admin" | "tenant_owner" | "tenant_member";

export type TenantStatus = "active" | "suspended";

export interface MockTenant {
  id: string;
  name: string;
  status: TenantStatus;
  plan: string;
  createdAt: string;
}

export interface MockUser {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  /** Always null for super_admin and platform_admin; non-null for customer workspace users. */
  tenantId: string | null;
  /** Development-only PBKDF2 hash via Web Crypto API (not a replacement for server-side Argon2id). */
  passwordHash: string;
  passwordSalt: string;
  isActive: boolean;
  createdAt: string;
}

export type PublicUser = Omit<MockUser, "passwordHash" | "passwordSalt">;

export interface MockSession {
  /** Clearly marked development mock token (not a signed JWT). */
  accessToken: string;
  userId: string;
  role: UserRole;
  tenantId: string | null;
  issuedAt: string;
  expiresAt: string;
}

export interface MockDatabase {
  version: 1;
  tenants: MockTenant[];
  users: MockUser[];
}

export interface AuthResponse {
  session: MockSession;
  user: PublicUser;
  tenant: MockTenant | null;
}

export interface RegisterCustomerInput {
  email: string;
  password: string;
  fullName: string;
  companyName: string;
}

export interface CreateAdminInput {
  email: string;
  password: string;
  fullName: string;
  /** Rejected if caller attempts to pass "super_admin". */
  role?: string;
}

export class MockApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "MockApiError";
    this.code = code;
    this.status = status;
  }
}

