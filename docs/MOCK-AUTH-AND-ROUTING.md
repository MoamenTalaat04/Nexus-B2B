# NEXUS B2B — Frontend Mock Authentication & Routing Foundation

> **Development-only documentation.** This document describes the temporary frontend-only Mock API and routing architecture. It does not alter `docs/CONTRACTS.md` and does not represent real backend endpoints or production security boundaries.

## 1. Storage Keys & Persistence

- **Mock Database Key**: `nexus_mock_database_v1` (stores seeded + newly registered tenants and users in `localStorage`)
- **Mock Session Key**: `nexus_mock_session_v1` (stores `{ accessToken, userId, role, tenantId, issuedAt, expiresAt }`)
- Seed data is initialized **only** when `nexus_mock_database_v1` is absent or invalid, so registered accounts and status changes persist across page refreshes.
- **Dev Reset**: Call `resetMockDatabase()` (or click **Reset mock DB** on `/login`) to restore the initial seeded database and clear the active session.

## 2. Demo Credentials (Development Only)

| Role | Email | Password | Tenant ID | Default Redirect |
|---|---|---|---|---|
| `super_admin` | `superadmin@nexus.local` | `SuperAdmin123!` | `null` | `/admin` |
| `platform_admin` | `admin@nexus.local` | `Admin123!` | `null` | `/admin` |
| `tenant_owner` | `customer1@nexus.local` | `Customer123!` | `tenant_001` | `/` |
| `tenant_owner` | `customer2@nexus.local` | `Customer123!` | `tenant_002` | `/` |

## 3. Password & Token Simulation Notice

- Passwords in the mock store are hashed using the browser **Web Crypto API** (`PBKDF2` + SHA-256 + per-account random salt). This is strictly a development simulation and **never replaces server-side Argon2id or bcrypt**.
- `accessToken` values (`nexus_mock_tok_<userId>_<hex>`) are clearly marked mock tokens and **are not signed JWTs**.

## 4. Role, Permission & Multi-Tenant Rules

- **Public Registration (`/register`, `/signup`)**: Always creates a new tenant and assigns `role: "tenant_owner"` internally. Any attempt to pass an admin role is rejected with `403`.
- **Admin Creation (`createAdmin`)**: Restricted exclusively to `super_admin`. Returns `403 Forbidden` for `platform_admin` and customer roles, and rejects attempts to create `super_admin`.
- **Multi-Tenant Isolation**: `getCurrentTenantResources()` derives `tenantId` solely from the active session. `getTenantById(requestedTenantId)` rejects cross-tenant requests by customers with `403 Forbidden`.
- **Important Limitation**: Frontend checks are for UI/UX flow and local testing only. Real authentication, JWT signing/validation, RBAC, and tenant isolation must be enforced independently by the FastAPI backend.

## 5. Future Backend Integration Points

Replace the functions in `src/lib/mock-api/` (`login`, `registerCustomer`, `logout`, `getCurrentUser`, `getCurrentTenant`, `createAdmin`, `getCustomers`, `getAdmins`, `suspendCustomer`, `reactivateCustomer`) with `fetch("/api/v1/...")` calls against the FastAPI backend while keeping `AuthProvider`, `RouteGuard`, and route definitions in `src/config/routes.ts` unchanged.

