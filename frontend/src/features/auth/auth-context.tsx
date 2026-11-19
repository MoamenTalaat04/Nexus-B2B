"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getCurrentSession,
  getCurrentTenant,
  getCurrentUser,
  login as mockLogin,
  logout as mockLogout,
  registerCustomer as mockRegisterCustomer,
  resetMockDatabase,
  type AuthResponse,
  type MockSession,
  type MockTenant,
  type PublicUser,
  type RegisterCustomerInput,
} from "@/lib/mock-api";

interface AuthContextValue {
  user: PublicUser | null;
  tenant: MockTenant | null;
  session: MockSession | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<AuthResponse>;
  registerCustomer: (input: RegisterCustomerInput) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  resetDemoData: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<PublicUser | null>(null);
  const [tenant, setTenant] = useState<MockTenant | null>(null);
  const [session, setSession] = useState<MockSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshAuth = useCallback(async () => {
    try {
      const [currentSession, currentUser, currentTenant] = await Promise.all([
        getCurrentSession(),
        getCurrentUser(),
        getCurrentTenant(),
      ]);
      setSession(currentUser ? currentSession : null);
      setUser(currentUser);
      setTenant(currentTenant);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAuth();
  }, [refreshAuth]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await mockLogin(email, password);
    setSession(result.session);
    setUser(result.user);
    setTenant(result.tenant);
    return result;
  }, []);

  const registerCustomer = useCallback(async (input: RegisterCustomerInput) => {
    const result = await mockRegisterCustomer(input);
    setSession(result.session);
    setUser(result.user);
    setTenant(result.tenant);
    return result;
  }, []);

  const logout = useCallback(async () => {
    await mockLogout();
    setSession(null);
    setUser(null);
    setTenant(null);
  }, []);

  const resetDemoData = useCallback(async () => {
    await resetMockDatabase();
    setSession(null);
    setUser(null);
    setTenant(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      tenant,
      session,
      isLoading,
      isAuthenticated: !!user && !!session,
      login,
      registerCustomer,
      logout,
      refreshAuth,
      resetDemoData,
    }),
    [user, tenant, session, isLoading, login, registerCustomer, logout, refreshAuth, resetDemoData],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return ctx;
}

