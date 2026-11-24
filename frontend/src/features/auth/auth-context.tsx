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
import { ApiError, api } from "@/lib/api";
import {
  DEMO_CREDENTIALS,
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
  type UserRole,
} from "@/lib/mock-api";

interface BackendAuthMeResponse {
  user: {
    id: string;
    email: string;
    full_name: string;
    role: string;
    tenant_id: string;
  };
  tenant: {
    id: string;
    name: string;
  };
  tenant_id: string;
  onboarding_completed: boolean;
  auth_provider: string;
}

interface AuthContextValue {
  user: PublicUser | null;
  tenant: MockTenant | null;
  session: MockSession | null;
  authProvider: "auth0" | "local" | "mock";
  onboardingCompleted: boolean;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<AuthResponse>;
  sendRegistrationOtp: (email: string) => Promise<{ ok: boolean; message: string }>;
  verifyRegistrationOtp: (input: RegisterCustomerInput & { otp: string }) => Promise<AuthResponse>;
  registerCustomer: (input: RegisterCustomerInput) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  resetDemoData: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const DEMO_EMAILS = new Set<string>(
  Object.values(DEMO_CREDENTIALS).map((item) => item.email.toLowerCase()),
);

function mapBackendRole(role: string): UserRole {
  if (role === "owner" || role === "tenant_owner") return "tenant_owner";
  if (role === "super_admin" || role === "platform_admin") return role;
  return "tenant_member";
}

function mapBackendAuthResponse(payload: BackendAuthMeResponse): AuthResponse {
  const role = mapBackendRole(payload.user.role);
  const now = new Date().toISOString();
  const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
  return {
    user: {
      id: payload.user.id,
      email: payload.user.email,
      fullName: payload.user.full_name,
      role,
      tenantId: payload.user.tenant_id,
      isActive: true,
      createdAt: now,
    },
    tenant: {
      id: payload.tenant.id,
      name: payload.tenant.name,
      status: "active",
      plan: "starter",
      createdAt: now,
    },
    session: {
      accessToken: "httponly-cookie",
      userId: payload.user.id,
      role,
      tenantId: payload.user.tenant_id,
      issuedAt: now,
      expiresAt,
    },
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<PublicUser | null>(null);
  const [tenant, setTenant] = useState<MockTenant | null>(null);
  const [session, setSession] = useState<MockSession | null>(null);
  const [authProvider, setAuthProvider] = useState<"auth0" | "local" | "mock">("local");
  const [onboardingCompleted, setOnboardingCompleted] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

  const refreshAuth = useCallback(async () => {
    try {
      try {
        const backendMe = await api.get<BackendAuthMeResponse>("/auth/me", {
          suppressUnauthorizedRedirect: true,
        });
        const mapped = mapBackendAuthResponse(backendMe);
        setSession(mapped.session);
        setUser(mapped.user);
        setTenant(mapped.tenant);
        setAuthProvider(backendMe.auth_provider === "auth0" ? "auth0" : "local");
        setOnboardingCompleted(backendMe.onboarding_completed);
        return;
      } catch {
        // Fall back to mock session if backend cookie is not present (e.g. Admin demo accounts).
      }

      const [currentSession, currentUser, currentTenant] = await Promise.all([
        getCurrentSession(),
        getCurrentUser(),
        getCurrentTenant(),
      ]);
      setSession(currentUser ? currentSession : null);
      setUser(currentUser);
      setTenant(currentTenant);
      if (currentUser) {
        setAuthProvider("mock");
        setOnboardingCompleted(true);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => refreshAuth());
  }, [refreshAuth]);

  const login = useCallback(async (email: string, password: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    try {
      const backendAuth = await api.post<BackendAuthMeResponse>(
        "/auth/login",
        { email: normalizedEmail, password },
        { suppressUnauthorizedRedirect: true },
      );
      const mapped = mapBackendAuthResponse(backendAuth);
      setSession(mapped.session);
      setUser(mapped.user);
      setTenant(mapped.tenant);
      setAuthProvider(backendAuth.auth_provider === "auth0" ? "auth0" : "local");
      setOnboardingCompleted(backendAuth.onboarding_completed);
      return mapped;
    } catch (err) {
      const isServerDown = err instanceof ApiError ? err.status >= 500 : true;
      if (DEMO_EMAILS.has(normalizedEmail) || isServerDown) {
        const result = await mockLogin(email, password);
        setSession(result.session);
        setUser(result.user);
        setTenant(result.tenant);
        setAuthProvider("mock");
        setOnboardingCompleted(true);
        return result;
      }
      throw err;
    }
  }, []);

  const sendRegistrationOtp = useCallback(async (email: string) => {
    return api.post<{ ok: boolean; message: string }>(
      "/auth/register/send-otp",
      { email: email.trim().toLowerCase() },
      { suppressUnauthorizedRedirect: true },
    );
  }, []);

  const verifyRegistrationOtp = useCallback(
    async (input: RegisterCustomerInput & { otp: string }) => {
      const backendAuth = await api.post<BackendAuthMeResponse>(
        "/auth/register/verify-otp",
        {
          email: input.email.trim().toLowerCase(),
          password: input.password,
          full_name: input.fullName.trim(),
          company_name: input.companyName.trim(),
          otp: input.otp.trim(),
        },
        { suppressUnauthorizedRedirect: true },
      );
      const mapped = mapBackendAuthResponse(backendAuth);
      setSession(mapped.session);
      setUser(mapped.user);
      setTenant(mapped.tenant);
      setAuthProvider(backendAuth.auth_provider === "auth0" ? "auth0" : "local");
      setOnboardingCompleted(backendAuth.onboarding_completed);
      return mapped;
    },
    [],
  );

  const registerCustomer = useCallback(async (input: RegisterCustomerInput) => {
    try {
      const backendAuth = await api.post<BackendAuthMeResponse>(
        "/auth/register",
        {
          email: input.email.trim().toLowerCase(),
          password: input.password,
          full_name: input.fullName.trim(),
          company_name: input.companyName.trim(),
        },
        { suppressUnauthorizedRedirect: true },
      );
      const mapped = mapBackendAuthResponse(backendAuth);
      setSession(mapped.session);
      setUser(mapped.user);
      setTenant(mapped.tenant);
      setAuthProvider(backendAuth.auth_provider === "auth0" ? "auth0" : "local");
      setOnboardingCompleted(backendAuth.onboarding_completed);
      return mapped;
    } catch (err) {
      const isServerDown = err instanceof ApiError ? err.status >= 500 : true;
      if (isServerDown) {
        const result = await mockRegisterCustomer(input);
        setSession(result.session);
        setUser(result.user);
        setTenant(result.tenant);
        setAuthProvider("mock");
        return result;
      }
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    await Promise.allSettled([
      api.post("/auth/logout", undefined, { suppressUnauthorizedRedirect: true }),
      mockLogout(),
    ]);
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
      authProvider,
      onboardingCompleted,
      isLoading,
      isAuthenticated: Boolean(user && session),
      login,
      sendRegistrationOtp,
      verifyRegistrationOtp,
      registerCustomer,
      logout,
      refreshAuth,
      resetDemoData,
    }),
    [
      user,
      tenant,
      session,
      authProvider,
      onboardingCompleted,
      isLoading,
      login,
      sendRegistrationOtp,
      verifyRegistrationOtp,
      registerCustomer,
      logout,
      refreshAuth,
      resetDemoData,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
