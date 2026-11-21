import type { UserRole } from "@/lib/mock-api/types";

export const AUTH_ROUTES = {
  login: "/login",
  register: "/register",
  signup: "/signup",
} as const;

export const CUSTOMER_ROUTES = {
  dashboard: "/",
  icp: "/icp",
  leads: "/leads",
  leadDetail: (id: string) => `/leads/${id}`,
  pipeline: "/pipeline",
  outreach: "/outreach",
  activity: "/activity",
  activityDetail: (id: string) => `/activity/${id}`,
  reports: "/reports",
  support: "/support",
  settings: "/settings",
} as const;

export const ADMIN_ROUTES = {
  dashboard: "/admin",
  customers: "/admin/customers",
  customerDetail: (id: string) => `/admin/customers/${id}`,
  admins: "/admin/admins",
  plans: "/admin/plans",
  billing: "/admin/billing",
  support: "/admin/support",
  supportDetail: (id: string) => `/admin/support/${id}`,
  security: "/admin/security",
} as const;

export const CUSTOMER_ROLES: UserRole[] = ["tenant_owner", "tenant_member"];
export const ADMIN_ROLES: UserRole[] = ["super_admin", "platform_admin"];

export function isAdminRole(role: UserRole): boolean {
  return role === "super_admin" || role === "platform_admin";
}

export function isCustomerRole(role: UserRole): boolean {
  return role === "tenant_owner" || role === "tenant_member";
}

export function getDefaultRouteForRole(role: UserRole): string {
  return isAdminRole(role) ? ADMIN_ROUTES.dashboard : CUSTOMER_ROUTES.dashboard;
}

export function canAccessRoute(role: UserRole, pathname: string): boolean {
  if (pathname.startsWith("/admin/admins") || pathname.startsWith("/admin/billing")) {
    return role === "super_admin";
  }
  if (pathname.startsWith("/admin")) {
    return isAdminRole(role);
  }
  return isCustomerRole(role);
}

