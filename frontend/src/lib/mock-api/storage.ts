import { createInitialMockDatabase } from "@/lib/mock-api/seed";
import type { MockDatabase, MockSession } from "@/lib/mock-api/types";

export const MOCK_DB_STORAGE_KEY = "nexus_mock_database_v1";
export const MOCK_SESSION_STORAGE_KEY = "nexus_mock_session_v1";

let memoryDb: MockDatabase | null = null;
let memorySession: MockSession | null = null;

function hasLocalStorage(): boolean {
  try {
    return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
  } catch {
    return false;
  }
}

export async function readMockDatabase(): Promise<MockDatabase> {
  if (hasLocalStorage()) {
    const raw = window.localStorage.getItem(MOCK_DB_STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as MockDatabase;
        if (parsed && parsed.version === 1 && Array.isArray(parsed.users) && Array.isArray(parsed.tenants)) {
          return parsed;
        }
      } catch {
        // Re-seed if stored JSON is corrupted.
      }
    }
    const initial = await createInitialMockDatabase();
    window.localStorage.setItem(MOCK_DB_STORAGE_KEY, JSON.stringify(initial));
    return initial;
  }

  if (!memoryDb) {
    memoryDb = await createInitialMockDatabase();
  }
  return memoryDb;
}

export function writeMockDatabase(db: MockDatabase): void {
  if (hasLocalStorage()) {
    window.localStorage.setItem(MOCK_DB_STORAGE_KEY, JSON.stringify(db));
  } else {
    memoryDb = db;
  }
}

export function readMockSession(): MockSession | null {
  if (hasLocalStorage()) {
    const raw = window.localStorage.getItem(MOCK_SESSION_STORAGE_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as MockSession;
      if (!parsed || !parsed.accessToken || !parsed.userId || !parsed.role) return null;
      if (parsed.expiresAt && new Date(parsed.expiresAt).getTime() <= Date.now()) {
        window.localStorage.removeItem(MOCK_SESSION_STORAGE_KEY);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }
  return memorySession;
}

export function writeMockSession(session: MockSession | null): void {
  if (hasLocalStorage()) {
    if (session) {
      window.localStorage.setItem(MOCK_SESSION_STORAGE_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(MOCK_SESSION_STORAGE_KEY);
    }
  } else {
    memorySession = session;
  }
}

/** Development-only helper to restore the mock database to its initial seeded state. */
export async function resetMockDatabase(): Promise<MockDatabase> {
  const initial = await createInitialMockDatabase();
  writeMockDatabase(initial);
  writeMockSession(null);
  return initial;
}

